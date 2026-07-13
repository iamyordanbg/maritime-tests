import os
import json
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.models.user import User
from app.models.test import Test
from app.models.result import TestResult
from app.models.signal import Signal
from app.models.ticket import Ticket, TicketMessage
from app.models.snapshot import MonthlySnapshot
from app.utils.decorators import admin_required, login_required, admin_required
from app.utils.codes import subscription_code, result_public_code, get_or_create_subscription_code, free_code
import math
from datetime import datetime

dashboard = Blueprint("dashboard", __name__)


@dashboard.route('/api/history')
@login_required
def api_history():
    """API за History — първоначално зареждане (асинхронно, за бърз first paint) + load more пагинация"""
    from app.utils.grants import find_result_grant, result_visible, auto_delete_expired_results
    import bisect
    user = User.query.get(session['user_id'])
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 5, type=int)

    # Опортюнистично почистване на резултати с изтекъл grant (>30 дни) —
    # не разчитаме само на зареждане на admin dashboard-а за това.
    auto_delete_expired_results()

    type_labels = {'test': 'Test', 'mix': 'Mix', 'mistakes': 'Mistakes', 'simulator': 'Simulator'}

    now = datetime.utcnow()
    from app.utils.grant_cache import fetch_all_grants
    _all_gold, _all_promo, _all_plan = fetch_all_grants(user.id)
    gold_c = {user.id: _all_gold}
    promo_c = {user.id: _all_promo}
    plan_c = {user.id: _all_plan}
    grant_ts_cache = {}

    # Извличаме малко повече от нужното, за да компенсираме резултатите,
    # които ще бъдат скрити (grant изтекъл преди >30 дни), без да чупим
    # пагинацията — филтрираме in-memory и пълним до `limit`.
    all_results = (TestResult.query
                   .options(db.joinedload(TestResult.test))
                   .filter_by(user_id=user.id).order_by(TestResult.taken_at.desc())
                   .all())

    # #N трябва да е ПОРЕДЕН НОМЕР САМО за този потребител (1-вия му решен
    # тест = #1, 2-рия = #2 и т.н.), НЕ суровото TestResult.id (database
    # primary key, глобален за ВСИЧКИ потребители - точно затова user #2
    # виждаше '#37', продължавайки номерацията от друг потребител, вместо
    # своя реален пореден номер '#1'). all_results вече е ФИЛТРИРАН по
    # user_id по-горе, значи е коректно да номерираме по хронологичен ред
    # (най-старият тест на ТОЗИ потребител = #1), независимо от план.
    # #N вече се чете НАПРАВО от r.user_seq (записан веднъж при submit,
    # никога не се преизчислява от оцелелите редове) - гарантира, че
    # номерацията не се разбърква, ако стари резултати бъдат изтрити
    # (напр. изтекла Free сесия). Fallback към старата "позиция сред
    # оцелелите" логика само за много стари редове отпреди тази промяна,
    # на които user_seq все още е NULL (ако backfill миграцията не е
    # успяла по някаква причина).
    all_results_asc = sorted(all_results, key=lambda r: r.taken_at)
    user_seq_by_result_id = {r.id: idx + 1 for idx, r in enumerate(all_results_asc)}

    visible_results = []
    for r in all_results:
        status, grant = find_result_grant(r, now, gold_c, plan_c, promo_c)
        if result_visible(r, status, grant, now):
            visible_results.append((r, status, grant))

    total_count = len(visible_results)
    page = visible_results[offset:offset + limit]

    items = []
    for r, status, grant in page:
        public_code = None
        if grant:
            if grant.id not in grant_ts_cache:
                test_ids = grant.test_id_list() if hasattr(grant, 'test_id_list') else [grant.library_test_id]
                rows = (TestResult.query.with_entities(TestResult.taken_at)
                        .filter(TestResult.user_id == r.user_id, TestResult.test_id.in_(test_ids),
                                TestResult.taken_at >= grant.activated_at).all())
                grant_ts_cache[grant.id] = sorted(row[0] for row in rows)
            seq = bisect.bisect_right(grant_ts_cache[grant.id], r.taken_at)
            grant_type = 'gold' if hasattr(grant, 'test_id_list') else 'plan'
            # ПОПРАВКА (същия клас бъг като dashboard картите): за Gold не
            # преизчисляваме код от grant.id - ползваме РЕАЛНИЯ активиран
            # код (grant.promo_code), запазен веднъж при активирането.
            if grant_type == 'gold':
                base_code = grant.promo_code or subscription_code(grant.id, grant_type='gold')
            else:
                base_code = get_or_create_subscription_code('plan', grant.id)
            public_code = f"{base_code}{r.taken_at.strftime('%d%m%y')}-{seq:03d}"

        items.append({
            'title': r.test.title[:45] + ('...' if len(r.test.title) > 45 else ''),
            'taken_at': r.taken_at.strftime('%d.%m.%Y %H:%M'),
            'percent': r.percent,
            'score': r.score,
            'total': r.total,
            'passed': r.passed,
            'test_type': type_labels.get(r.test_type, r.test_type.title() if r.test_type else 'Test'),
            'result_id': r.id,
            'display_seq': r.user_seq or user_seq_by_result_id.get(r.id, r.id),
            'display_id': public_code or r.display_id,
            'test_id': r.test_id
        })

    return jsonify({
        'items': items,
        'has_more': (offset + limit) < total_count,
        'total_count': total_count
    })


@dashboard.route('/dashboard')
@login_required
def user_dashboard():
    user = User.query.get(session['user_id'])
    if user and user.is_admin:
        return redirect(url_for('admin.admin_dashboard'))
    _stats_row = (db.session.query(
                    db.func.count(TestResult.id),
                    db.func.sum(db.case((TestResult.passed == True, 1), else_=0))
                  ).filter(TestResult.user_id == user.id).first())
    total_tests = _stats_row[0] or 0
    passed_tests = _stats_row[1] or 0

    # Всички grant-ове на потребителя — ЕДНО теглене, преизползвано навсякъде
    # по-долу (строене на картите), вместо да се тегли по два пъти през различни пътища.
    from app.models.gold_grant import GoldGrant
    from app.models.promo_grant import PromoGrant
    from app.models.plan_grant import PlanGrant
    from app.utils.grant_cache import fetch_all_grants
    _all_gold_grants, _all_promo_grants, _all_plan_grants = fetch_all_grants(user.id)
    _now = datetime.utcnow()
    # "Затопляме" кеша на User модела (has_active_plan/effective_plan_label/...
    # четат self._cached_gold_grants/_cached_plan_grants) — иначе те биха
    # тригернали СВОИ собствени, отделни заявки при първо извикване по-долу
    # или в темплейта, дублирайки вече изтегленото тук.
    user._cached_gold_grants = [g for g in _all_gold_grants if g.expires_at > _now]
    user._cached_promo_grants = [g for g in _all_promo_grants if g.expires_at > _now]
    user._cached_plan_grants = [g for g in _all_plan_grants if g.expires_at > _now]

    # История ("Last Results") вече НЕ се тегли тук — зарежда се асинхронно
    # през /api/history след първоначалния рендер, за да не блокира first paint
    # с допълнителни заявки/изчисления, които не са критични за самата страница.
    results = []
    result_code_by_id = {}

    # Само тестовете, за които потребителят реално има достъп — не целия каталог.
    # Определяме нужните ID-та ПРЕДИ да питаме Test таблицата.
    needed_test_ids = set()
    if user.library_test_id:
        needed_test_ids.add(user.library_test_id)
    for g in _all_gold_grants:
        if g.expires_at > _now:
            needed_test_ids.update(g.test_id_list())
    for g in _all_promo_grants:
        if g.expires_at > _now:
            needed_test_ids.update(g.test_id_list())
    for g in _all_plan_grants:
        if g.expires_at > _now and g.library_test_id:
            needed_test_ids.add(g.library_test_id)

    all_tests = (Test.query
                 .options(db.defer(Test.questions_json))
                 .filter(Test.id.in_(needed_test_ids)).all()
                 if needed_test_ids else [])

    refreshed = user.library_refresh_if_expired()
    if refreshed:
        db.session.commit()
        session['library_just_refreshed'] = True

    # Toast се показва само веднъж — при първото зареждане след refresh
    show_refresh_toast = session.pop('library_just_refreshed', False)

    now = datetime.utcnow()

    # Оставащи дни от плана — реална валидност (GoldGrant/plan_expires_at), не суровото поле
    plan_days_left = user.effective_days_left()

    library_state = {
        'is_premium': user.has_active_plan(),
        'selected_test_id': user.library_test_id,
        'days_left': user.library_days_left(),
        'window_active': user.library_window_active(),
        'simulator_available_today': user.library_simulator_available(),
    }

    from app.models.plan_grant import PlanGrant
    active_plan_grants_qs = sorted([g for g in _all_plan_grants if g.expires_at > _now], key=lambda g: g.activated_at)
    plan_grant_awaiting_test = any(g.library_test_id is None for g in active_plan_grants_qs)

    # Без избран тест → задължително към library. Изключения: Gold/Promo
    # (избира през /activate) и Basic/Plus с ВЕЧЕ избран тест за всичките
    # си активни grant-ове.
    # ПОПРАВКА: проверяваме РЕАЛНО съществуващи активни GoldGrant/PromoGrant
    # записи (_all_gold_grants/_all_promo_grants), не user.plan == 'gold'
    # (легаси поле, установено да се разсинхронизира - реален случай, при
    # който Gold потребител с валиден активен grant беше пращан обратно
    # към library при всяко влизане).
    has_active_gold = any(g.expires_at > _now for g in _all_gold_grants) or any(g.expires_at > _now for g in _all_promo_grants)
    if (not has_active_gold
            and not active_plan_grants_qs
            and not user.library_window_active()
            and user.library_test_id is None):
        return redirect(url_for('dashboard.library'))
    if active_plan_grants_qs and plan_grant_awaiting_test:
        return redirect(url_for('dashboard.library'))

    # Free потребител с активен избор — само избраният тест (без демо)
    if user.library_window_active() and user.library_test_id:
        tests = [t for t in all_tests if t.id == user.library_test_id]
    elif user.is_active and user.library_test_id:
        tests = [t for t in all_tests if t.id == user.library_test_id]
    else:
        tests = []

    # Gold/Promo: всеки активиран код е автономна карта (собствени тестове,
    # лимит, срок). GoldGrant (Gold 10-пакет) и PromoGrant (Custom Promo)
    # са ОТДЕЛНИ таблици (по изрично искане), но визуално се показват
    # заедно в едно и също 'gold_cards' множество, сортирани по дата.
    gold_cards = []
    test_grant_info = {}
    if user.plan == 'gold':
        from app.models.gold_grant import GoldGrant
        from app.models.promo_grant import PromoGrant
        from app.models.promo import PromoCode
        active_grants = sorted(
            [g for g in _all_gold_grants if g.expires_at > _now] + [g for g in _all_promo_grants if g.expires_at > _now],
            key=lambda g: g.activated_at
        )
        gold_tests_union = []
        for g in active_grants:
            g_test_ids = g.test_id_list()
            g_tests = [t for t in all_tests if t.id in g_test_ids]
            g_days_left = max(0, math.ceil((g.expires_at - now).total_seconds() / 86400))
            # Реален брой решени — от TestResult записите за ТОЗИ тест(ове), от
            # активацията на ТОЗИ grant нататък. Не вярваме на отделно поле,
            # което може да разминее — броим директно от сесията на потребителя.
            g_used_real = (TestResult.query
                           .filter(TestResult.user_id == user.id,
                                   TestResult.test_id.in_(g_test_ids),
                                   TestResult.taken_at >= g.activated_at)
                           .count()) if g_test_ids else 0
            g_remaining = max(0, g.quota - g_used_real)
            # Централизирана 'Custom' vs 'Gold' логика - app/utils/grants.py
            # (виж коментара там за защо не се нуждае от отделна PromoCode заявка).
            from app.utils.grants import grant_plan_label
            g_plan_label = grant_plan_label(g)
            gold_cards.append({
                'grant': g, 'tests': g_tests, 'days_left': g_days_left,
                'tests_remaining': g_remaining, 'tests_quota': g.quota,
                'department': g.department, 'plan_label': g_plan_label,
                'subscription_code': (g.promo_code or get_or_create_subscription_code('gold', g.id)),
            })
            for t in g_tests:
                test_grant_info[t.id] = {
                    'days_left': g_days_left, 'tests_remaining': g_remaining,
                    'tests_quota': g.quota, 'grant_id': g.id, 'activated_at': g.activated_at,
                    'subscription_code': (g.promo_code or get_or_create_subscription_code('gold', g.id)),
                }
            gold_tests_union.extend(g_tests)

        if active_grants:
            # Обединяваме тестовете от ВСИЧКИ активни Gold grant-ове — всеки запазва
            # собствения си лимит/срок (виж test_grant_info), но се показва в
            # обичайния Deck/Engine изглед, без да губим стария layout.
            tests = gold_tests_union

    # Basic/Plus: всяка покупка е автономна карта (собствен избран тест, лимит, срок)
    plan_cards = []
    plan_tests_union = []
    for g in active_plan_grants_qs:
        if not g.library_test_id:
            continue
        g_test = next((t for t in all_tests if t.id == g.library_test_id), None)
        if not g_test:
            continue
        g_days_left = max(0, math.ceil((g.expires_at - now).total_seconds() / 86400))
        # Реален брой решени — директно от TestResult записите за ТОЗИ конкретен
        # тест, от активацията на ТОЗИ grant нататък (не съхранено поле).
        g_used_real = (TestResult.query
                       .filter(TestResult.user_id == user.id,
                               TestResult.test_id == g.library_test_id,
                               TestResult.taken_at >= g.activated_at)
                       .count())
        g_remaining = max(0, g.quota - g_used_real)
        plan_cards.append({
            'grant': g, 'tests': [g_test], 'days_left': g_days_left,
            'tests_remaining': g_remaining, 'tests_quota': g.quota,
            'department': (g_test.category or '').lower(), 'plan_label': g.plan.capitalize(),
            'subscription_code': get_or_create_subscription_code('plan', g.id),
        })
        test_grant_info[g_test.id] = {
            'days_left': g_days_left, 'tests_remaining': g_remaining,
            'tests_quota': g.quota, 'grant_id': g.id, 'activated_at': g.activated_at,
            'subscription_code': get_or_create_subscription_code('plan', g.id),
        }
        plan_tests_union.append(g_test)

    if plan_tests_union:
        # Ако вече имаше нещо от Gold, добавяме към него; иначе заместваме free списъка
        tests = (tests or []) + [t for t in plan_tests_union if t not in tests]

    # Free потребител (без активен Gold/Basic/Plus) с избран тест през
    # library прозореца - преди тази промяна изобщо НЕ се показваше карта
    # в Available Tests (all_cards идваше само от gold_cards+plan_cards),
    # клиентът трябваше да го намери по друг начин. Сега получава СЪЩАТА
    # визуална карта, само с 'Free' етикет вместо BG код.
    # РЕАЛНА квота (не 9999 placeholder) - FREE_QUOTA теста в рамките на
    # 7-дневния прозорец, преброени директно от TestResult записите (същия
    # паттерн като Basic/Plus grant-овете).
    FREE_QUOTA = 7
    free_cards = []
    if not gold_cards and not plan_cards and user.library_window_active() and user.library_test_id:
        free_test = next((t for t in all_tests if t.id == user.library_test_id), None)
        if free_test:
            free_days_left = user.library_days_left()
            free_used_real = (TestResult.query
                               .filter(TestResult.user_id == user.id,
                                       TestResult.test_id == free_test.id,
                                       TestResult.taken_at >= (user.library_selected_at or now))
                               .count())
            free_remaining = max(0, FREE_QUOTA - free_used_real)
            free_cards.append({
                'grant': None, 'tests': [free_test], 'days_left': free_days_left,
                'tests_remaining': free_remaining, 'tests_quota': FREE_QUOTA,
                'department': (free_test.category or '').lower(), 'plan_label': 'Free',
                'subscription_code': f"BG{free_code(user.id)}",
                'sim_available': user.library_simulator_available(),
            })
            test_grant_info[free_test.id] = {
                'days_left': free_days_left, 'tests_remaining': free_remaining,
                'tests_quota': FREE_QUOTA, 'grant_id': None,
                'activated_at': user.library_selected_at,
                'subscription_code': f"BG{free_code(user.id)}",
            }

    # Quota по план — сбор от ВСИЧКИ активни grant-ове (Gold + Basic/Plus), не legacy полета
    all_active_cards = gold_cards + plan_cards
    if all_active_cards:
        tests_quota = sum(c['tests_quota'] for c in all_active_cards)
        tests_remaining = sum(c['tests_remaining'] for c in all_active_cards)
        tests_used = tests_quota - tests_remaining
    else:
        # Няма никакъв реално валиден план (дори полето user.plan да казва друго) —
        # нула квота, брояча не се показва изобщо.
        tests_quota = 0
        tests_used = 0
        tests_remaining = 0

    # Mistakes се отключва само ако има ≥2 решения (Test/Mix) на КОНКРЕТНИЯ тест,
    # направени СЛЕД активирането на ТОЗИ КОНКРЕТЕН grant — не стари резултати
    # от предишен, вече неактивен план, дори да е бил на същия test_id.
    # Условието вече покрива и Free (test_grant_info вече носи запис за
    # free_test.id по-горе), не само has_active_plan().
    mistakes_unlocked_by_test = {}
    if user.has_active_plan() or free_cards:
        for tid, info in test_grant_info.items():
            grant_activated_at = info.get('activated_at')
            if not grant_activated_at:
                continue
            cnt = TestResult.query.filter(
                TestResult.user_id == user.id,
                TestResult.test_id == tid,
                TestResult.test_type.in_(['test', 'mix']),
                TestResult.taken_at >= grant_activated_at,
            ).count()
            mistakes_unlocked_by_test[tid] = cnt >= 2

    # Billing таба в user_sidebar.html очаква тези речници (grant.id -> четим
    # код) - за ВСИЧКИ активни grant-ове, не само тези в gold_cards/plan_cards
    # (които филтрират само по вече избран library_test_id). Иначе план,
    # купен но без избран тест още, показва суровия 'BG'+id fallback вместо
    # истинския алгоритмичен код (точно това потребителят засече в скрийншот).
    from app.utils.codes import get_or_create_subscription_code as _gocsc
    plan_grant_codes = {g.id: _gocsc('plan', g.id) for g in user.active_plan_grants()}
    gold_grant_codes = {g.id: _gocsc('gold', g.id) for g in user.active_gold_grants()}

    return render_template('user/dashboard.html', user=user, results=results,
                           total_tests=total_tests, passed_tests=passed_tests, tests=tests,
                           library_state=library_state, library_refreshed=show_refresh_toast,
                           plan_days_left=plan_days_left, mistakes_unlocked_by_test=mistakes_unlocked_by_test,
                           tests_quota=tests_quota, tests_used=tests_used, tests_remaining=tests_remaining,
                           gold_cards=gold_cards, plan_cards=plan_cards, test_grant_info=test_grant_info,
                           all_cards=gold_cards + plan_cards + free_cards,
                           result_code_by_id=result_code_by_id,
                           plan_grant_codes=plan_grant_codes, gold_grant_codes=gold_grant_codes)


LEVEL_MAP = {
    'Operational Level': 'operational', 'operational level': 'operational',
    'operational': 'operational', 'Оперативно ниво': 'operational',
    'Management Level': 'management', 'management level': 'management',
    'management': 'management', 'Мениджърско ниво': 'management',
    'ETO': 'eto', 'eto': 'eto',
    'Master Level': 'master', 'master level': 'master',
    'master': 'master', 'Капитанско ниво': 'master',
    'Support Level': 'operational', 'support level': 'operational',
}


@dashboard.route('/library')
@login_required
def library():
    user = User.query.get(session['user_id'])
    if user.is_admin:
        return redirect(url_for('admin.admin_dashboard'))

    # Gold код в процес на активиране (виж activate.py::activate_start) -
    # потребителят е дошъl тук СПЕЦИАЛНО за да избере тестове за новия си
    # Gold grant, не обичайния Free/Basic/Plus избор. Показваме библиотеката
    # нормално, но JS-ът поема специален flow: 1-ви клик избира първи тест
    # (не завършва веднага), показва popup "избери още 1 - планът позволява
    # 2", 2-ри клик завършва активацията.
    from app.routes.activate import PROMO_SESSION_KEY, _get_valid_promo
    gold_flow = session.get(PROMO_SESSION_KEY)
    gold_activation = None
    if gold_flow and gold_flow.get('code'):
        promo = _get_valid_promo(gold_flow['code'])
        if promo:
            gold_activation = {
                'code': promo.code,
                'first_test_id': session.get('gold_first_test_id'),
                'first_test_title': session.get('gold_first_test_title'),
            }
        else:
            session.pop(PROMO_SESSION_KEY, None)
            session.pop('gold_first_test_id', None)
            session.pop('gold_first_test_title', None)

    # Ако 7-дневният прозорец е изтекъл — рестартирай го автоматично със същия тест
    refreshed = user.library_refresh_if_expired()
    if refreshed:
        db.session.commit()

    all_tests_raw = Test.query.options(db.defer(Test.questions_json)).order_by(Test.category, Test.level).all()

    from app.models.plan_grant import PlanGrant
    from app.utils.grants import grant_real_used
    now = datetime.utcnow()
    active_grants = (PlanGrant.query
                      .filter(PlanGrant.user_id == user.id, PlanGrant.expires_at > now)
                      .all())
    is_premium_plan = user.has_active_plan() and bool(active_grants)

    tests_data = []
    for t in all_tests_raw:
        if is_premium_plan and t.is_demo:
            continue  # платен клиент — демото изобщо не се показва
        level_key = LEVEL_MAP.get(t.level) or LEVEL_MAP.get((t.level or '').strip()) or 'operational'
        cat = (t.category or '').lower().strip()
        if cat not in ('deck', 'engine'):
            cat = 'deck' if 'deck' in cat or 'палуб' in cat else 'engine'
        tests_data.append({
            'id': t.id, 'title': t.title, 'category': cat,
            'level_key': level_key, 'question_count': t.question_count,
            'is_demo': t.is_demo
        })

    if is_premium_plan:
        # Клиентът избира 1 тест наведнъж от ЦЯЛАТА библиотека (без демо).
        # Преизбирането е ВИНАГИ позволено (клиентът може да си промени
        # избора когато поиска, особено ако е изчерпал лимита си за текущия
        # избран тест и иска да опита с друг/същия отново).
        already_selected_ids = [g.library_test_id for g in active_grants if g.library_test_id]
        # "Има ли за какво да преизбира" — свободен (None) или изчерпан grant,
        # или ако има само 1 активен grant общо (винаги преизбираем тогава).
        waiting_grant = next((g for g in active_grants
                              if g.library_test_id is None
                              or grant_real_used(g, user.id) >= g.quota), None)
        if not waiting_grant and len(active_grants) == 1:
            waiting_grant = active_grants[0]
        library_state = {
            'is_premium': True,
            'selected_test_id': already_selected_ids[0] if already_selected_ids else None,
            'selected_test_ids': already_selected_ids,
            'awaiting_selection': waiting_grant is not None,
            # По-точен флаг САМО за случая "изобщо няма избран тест още"
            # (напр. клиентът е платил и е затворил страницата преди избор).
            # awaiting_selection по-горе е "предозиран" - става True и когато
            # има само 1 активен grant с ВЕЧЕ избран тест (за да позволи
            # преизбиране), затова не е подходящ за еднократния popup.
            'needs_first_selection': any(g.library_test_id is None for g in active_grants),
            'days_left': user.effective_days_left(),
            'window_active': False,
            'simulator_available_today': user.library_simulator_available(),
        }
    else:
        # Free поток - легаси поведение (1 избран тест/седмица). ОТ ПОПРАВКАТА
        # НАСАМ: library_refresh_if_expired() по-горе вече ИЗЧИСТВА избора
        # при изтичане (както Basic/Plus/Gold), затова user.library_window_active()
        # тук коректно е False след изтичане - картата изчезва и потребителят
        # вижда ЦЯЛАТА библиотека, за да избере нов тест.
        # Отделен edge case: дали текущият "свободен" избран тест реално идва от
        # ПРЕМИУМ историята му (същия test_id, който преди е бил избран в
        # изтекъл PlanGrant) - това означава, че клиентът никога не е избирал
        # този тест през истинския free поток, а просто вижда наследено
        # състояние от премиум плана си. Само тогава го изчистваме отделно.
        if user.library_test_id:
            was_premium_selection = PlanGrant.query.filter_by(
                user_id=user.id, library_test_id=user.library_test_id
            ).first() is not None
            if was_premium_selection and not is_premium_plan:
                user.library_test_id = None
                user.library_selected_at = None
                db.session.commit()

        library_state = {
            'is_premium': user.has_active_plan(),
            'selected_test_id': user.library_test_id,
            'selected_test_ids': [user.library_test_id] if user.library_test_id else [],
            'awaiting_selection': user.library_test_id is None,
            'needs_first_selection': False,
            'days_left': user.library_days_left(),
            'window_active': user.library_window_active(),
            'simulator_available_today': user.library_simulator_available(),
        }

    return render_template('user/library.html', tests=tests_data, library_state=library_state, user=user, gold_activation=gold_activation)


@dashboard.route('/library/select', methods=['POST'])
@login_required
def library_select():
    user = User.query.get(session['user_id'])
    if user.is_admin:
        return jsonify({'success': False, 'message': 'Невалидно действие.'}), 400

    test_id = request.json.get('test_id') if request.is_json else request.form.get('test_id')
    test = Test.query.get(test_id) if test_id else None
    if not test:
        return jsonify({'success': False, 'message': 'Невалиден тест.'}), 400

    # --- Gold код в процес на активиране ---
    # 1-ви клик: запазва избора в сесията и връща gold_prompt_second=True
    # (JS показва popup "избери още 1 - планът позволява 2", БЕЗ redirect).
    # 2-ри клик (различен тест): създава GoldGrant с ДВАТА теста, консумира
    # промо кода, чисти сесийното състояние - точно както преди правеше
    # activate/confirm.html, само вече през Library интерфейса.
    from app.routes.activate import PROMO_SESSION_KEY, _get_valid_promo
    from datetime import timedelta
    gold_flow = session.get(PROMO_SESSION_KEY)
    if gold_flow and gold_flow.get('code'):
        promo = _get_valid_promo(gold_flow['code'])
        if not promo:
            session.pop(PROMO_SESSION_KEY, None)
            session.pop('gold_first_test_id', None)
            session.pop('gold_first_test_title', None)
            return jsonify({'success': False, 'message': 'Кодът вече не е валиден.'}), 400

        first_test_id = session.get('gold_first_test_id')
        # Ограничение на департамент (ако admin го е задал при генериране на кода)
        if promo.department_restriction and (test.category or '').lower() != promo.department_restriction:
            return jsonify({'success': False, 'message': f'Този код е валиден само за {promo.department_restriction.capitalize()} тестове.'}), 400

        topics_allowed = promo.topics_allowed or 1

        # БЪГ ФИКС: преди тук ВИНАГИ се искаше 2-ри тест (gold_prompt_second),
        # независимо от topics_allowed - проверката за "само 1 департамент"
        # идваше чак СЛЕД избора на 2-ри тест и само ограничаваше категорията
        # му, вместо да спре искането за 2-ри тест изобщо. Сега: ако планът
        # позволява само 1 тема (topics_allowed<=1), 1-вият избор завършва
        # активацията директно, с САМО този тест.
        if not first_test_id and topics_allowed <= 1:
            first_test = test
            chosen_ids = [test.id]
        elif not first_test_id:
            # Планът позволява >1 тема - запомняме 1-вия избор, питаме за 2-ри.
            session['gold_first_test_id'] = test.id
            session['gold_first_test_title'] = test.title
            return jsonify({'success': True, 'gold_prompt_second': True, 'first_test_title': test.title})
        else:
            # Ограничение на теми/департаменти (topics_allowed) - ако е 1,
            # 2-рият избран тест трябва да е от СЪЩИЯ департамент като 1-вия
            # (тук вече не се стига при topics_allowed<=1 - горният клон я
            # хваща на 1-вия избор - но проверката остава като defensive
            # guard, ако някога промо междинно бъде понижен).
            first_test = Test.query.get(first_test_id)
            if topics_allowed <= 1 and first_test and (first_test.category or '').lower() != (test.category or '').lower():
                return jsonify({'success': False, 'message': 'Този код позволява тестове само от 1 департамент - избери от същата тема като първия тест.'}), 400
            chosen_ids = [first_test_id, test.id] if test.id != first_test_id else [first_test_id]
        from app.models.gold_grant import GoldGrant
        from app.models.promo_grant import PromoGrant
        from app.services.plans import PLANS, TESTING_MODE, TESTING_DAYS
        gold_cfg = PLANS['gold']
        now = datetime.utcnow()
        # Promo-специфични стойности (зададени от admin при генериране), с
        # fallback към глобалните default-и само ако липсват (стари редове).
        duration_days = promo.duration_days or gold_cfg.get('valid_days_per_code', 30)
        quota = promo.tests_quota_override or gold_cfg.get('tests_quota', 150)
        new_expires = now + timedelta(days=duration_days)
        # GoldGrant е ЗА GOLD (10-пакет от Stripe покупка), PromoGrant е ЗА
        # PROMO (ръчно генериран Custom код от admin) - ОТДЕЛНИ таблици, по
        # изрично искане - Promo НЯМА нищо общо с Gold архитектурно, дори
        # да са били исторически споделяли инфраструктура.
        GrantModel = PromoGrant if promo.is_custom else GoldGrant
        grant = GrantModel(
            user_id=user.id, department=(first_test.category or test.category or 'deck').lower(),
            level=test.level, test_ids=json.dumps(chosen_ids),
            quota=quota, tests_used=0,
            activated_at=now, expires_at=new_expires,
            grace_until=new_expires + timedelta(days=promo.mistakes_grace_days or 60),
            promo_code=promo.code,
        )
        db.session.add(grant)
        from app.utils.grant_cache import invalidate_cached_grants
        invalidate_cached_grants(user.id)

        user.plan = 'gold'
        user.is_active = True
        if not user.plan_expires_at or new_expires > user.plan_expires_at:
            user.plan_expires_at = new_expires
            user.plan_grace_until = grant.grace_until
        user.plan_activated_at = user.plan_activated_at or now

        # Usage tracking - зависи от usage_limit_type, не просто is_used=True
        # завинаги (иначе 'custom'/'multiple' кодове биха се блокирали след
        # първата активация от когото и да е).
        promo.used_count = (promo.used_count or 0) + 1
        limit_type = promo.usage_limit_type or 'single'
        if limit_type == 'single' or (limit_type == 'custom' and promo.used_count >= (promo.usage_limit_count or 1)):
            promo.is_used = True
        promo.used_by = user.email
        promo.used_at = now
        promo.department = grant.department
        promo.level = test.level
        promo.selected_test_ids = json.dumps(chosen_ids)
        promo.activated_at = now

        session.pop(PROMO_SESSION_KEY, None)
        session.pop('gold_first_test_id', None)
        session.pop('gold_first_test_title', None)
        db.session.commit()
        return jsonify({'success': True, 'test_id': test.id, 'test_title': test.title})

    # Клиентът избира тест от ЦЯЛАТА библиотека (без демо) за някой от
    # активните си Basic/Plus grant-ове. Преизбирането е ВИНАГИ позволено —
    # приоритет: свободен (никога необвързан) grant → изчерпан (лимитът му
    # свърши, иска да опита с друг/същия тест отново) → ако има само 1
    # активен grant общо, него (винаги преизбираем тогава).
    from app.models.plan_grant import PlanGrant
    from app.utils.grants import grant_real_used
    now = datetime.utcnow()
    candidate_grants = (PlanGrant.query
                        .filter(PlanGrant.user_id == user.id, PlanGrant.expires_at > now)
                        .order_by(PlanGrant.activated_at.asc())
                        .all())
    waiting_grant = next((g for g in candidate_grants
                          if g.library_test_id is None
                          or grant_real_used(g, user.id) >= g.quota), None)
    if not waiting_grant and len(candidate_grants) == 1:
        waiting_grant = candidate_grants[0]
    if waiting_grant:
        waiting_grant.library_test_id = test.id
        waiting_grant.library_selected_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'test_id': test.id, 'test_title': test.title})

    # Free поток (легаси единично поле) - преизбирането вече е ВИНАГИ
    # позволено, като при Basic/Plus (same философия - клиентът може да си
    # смени избрания тест когато поиска, не само след като изтекат 7-те
    # дни). Всяко (пре)избиране рестартира свеж 7-дневен прозорец за НОВИЯ
    # тест. Преди тази промяна тук имаше блокиращо съобщение "вече имаш
    # избран тест за тази седмица", което не позволяваше смяна на темата.
    user.library_test_id = test.id
    user.library_selected_at = datetime.utcnow()
    user.library_last_simulator_at = None

    # Запис в историята (FreeSession) - за да се вижда Free план в
    # Usage/Billing попъпа на админа, точно както Basic/Plus/Gold.
    from app.models.free_session import FreeSession
    window_days = user.LIBRARY_WINDOW_DAYS
    from datetime import timedelta
    session_row = FreeSession(
        user_id=user.id, test_id=test.id,
        activated_at=user.library_selected_at,
        expires_at=user.library_selected_at + timedelta(days=window_days),
    )
    db.session.add(session_row)
    db.session.commit()

    return jsonify({'success': True, 'test_id': test.id, 'test_title': test.title})


@dashboard.route('/library/gold-finish', methods=['POST'])
@login_required
def library_gold_finish():
    """Завършва Gold активацията само с 1-я избран тест (потребителят не иска
    да добавя втори, макар планът да позволява до 2)."""
    user = User.query.get(session['user_id'])
    from app.routes.activate import PROMO_SESSION_KEY, _get_valid_promo
    from datetime import timedelta
    gold_flow = session.get(PROMO_SESSION_KEY)
    first_test_id = session.get('gold_first_test_id')
    if not gold_flow or not first_test_id:
        return jsonify({'success': False, 'message': 'Няма активен Gold избор.'}), 400
    promo = _get_valid_promo(gold_flow.get('code'))
    if not promo:
        session.pop(PROMO_SESSION_KEY, None)
        session.pop('gold_first_test_id', None)
        session.pop('gold_first_test_title', None)
        return jsonify({'success': False, 'message': 'Кодът вече не е валиден.'}), 400

    test = Test.query.get(first_test_id)
    if not test:
        return jsonify({'success': False, 'message': 'Невалиден тест.'}), 400

    from app.models.gold_grant import GoldGrant
    from app.models.promo_grant import PromoGrant
    from app.services.plans import PLANS
    gold_cfg = PLANS['gold']
    now = datetime.utcnow()
    duration_days = promo.duration_days or gold_cfg.get('valid_days_per_code', 30)
    quota = promo.tests_quota_override or gold_cfg.get('tests_quota', 150)
    new_expires = now + timedelta(days=duration_days)
    GrantModel = PromoGrant if promo.is_custom else GoldGrant
    grant = GrantModel(
        user_id=user.id, department=(test.category or 'deck').lower(),
        level=test.level, test_ids=json.dumps([test.id]),
        quota=quota, tests_used=0,
        activated_at=now, expires_at=new_expires,
        grace_until=new_expires + timedelta(days=promo.mistakes_grace_days or 60),
        promo_code=promo.code,
    )
    db.session.add(grant)
    from app.utils.grant_cache import invalidate_cached_grants
    invalidate_cached_grants(user.id)

    user.plan = 'gold'
    user.is_active = True
    if not user.plan_expires_at or new_expires > user.plan_expires_at:
        user.plan_expires_at = new_expires
        user.plan_grace_until = grant.grace_until
    user.plan_activated_at = user.plan_activated_at or now

    promo.used_count = (promo.used_count or 0) + 1
    limit_type = promo.usage_limit_type or 'single'
    if limit_type == 'single' or (limit_type == 'custom' and promo.used_count >= (promo.usage_limit_count or 1)):
        promo.is_used = True
    promo.used_by = user.email
    promo.used_at = now
    promo.department = grant.department
    promo.level = test.level
    promo.selected_test_ids = json.dumps([test.id])
    promo.activated_at = now

    session.pop(PROMO_SESSION_KEY, None)
    session.pop('gold_first_test_id', None)
    session.pop('gold_first_test_title', None)
    db.session.commit()
    return jsonify({'success': True})


from app.utils.images import inject_images
def user_can_access_test(user, test):
    """Дали потребителят има право да достъпи даден тест (test/mix/mistakes режими, НЕ симулатор)."""
    # Същият is_active vs has_active_plan() бъг като в simulator() по-долу -
    # is_active е легаси "имал ли е ИЗОБЩО план" флаг, не пада на False след
    # изтичане. Преди тази поправка, потребител с отдавна изтекъл план
    # получаваше НЕОГРАНИЧЕН достъп до ВСЕКИ тест в библиотеката (не само
    # избрания си), защото проверката тук изобщо не гледаше текущия статус.
    if user.is_admin or user.has_active_plan():
        return True
    if test.is_demo:
        return True
    if user.library_refresh_if_expired():
        db.session.commit()
    return user.library_window_active() and user.library_test_id == test.id


@dashboard.route('/test/<int:test_id>')
@login_required
def take_test(test_id):
    import random as rnd
    from app.utils.grants import test_access_lock
    user = User.query.get(session['user_id'])
    test = Test.query.get_or_404(test_id)
    if not user_can_access_test(user, test):
        flash('Този тест не е достъпен в твоя план. Избери го от Library или направи ъпгрейд.', 'warning')
        return redirect(url_for('dashboard.library'))
    locked, _owning_grant = test_access_lock(user, test_id)
    if locked:
        return redirect(url_for('dashboard.user_dashboard', quota_exceeded=1))
    questions = test.get_questions()
    questions = inject_images(test_id, questions)
    shuffle = request.args.get('shuffle') == 'true'
    if shuffle:
        questions = list(questions)
        rnd.shuffle(questions)
    is_free_plan = not user.is_admin and not user.has_active_plan()
    test_type = 'mix' if shuffle else 'test'
    return render_template('user/test.html', test=test, questions=questions, shuffle=shuffle, test_type=test_type, is_free_plan=is_free_plan, is_demo=False)

@dashboard.route('/test/<int:test_id>/mistakes')
@login_required
def test_mistakes(test_id):

    import random as rnd
    from app.permissions.roles import user_can_access_mistakes
    from app.utils.grants import test_access_lock
    user = User.query.get(session['user_id'])
    test = Test.query.get_or_404(test_id)
    if not user_can_access_mistakes(user, test):
        flash('Този тест не е достъпен в твоя план. Избери го от Library или направи ъпгрейд.', 'warning')
        return redirect(url_for('dashboard.library'))
    locked, _owning_grant = test_access_lock(user, test_id)
    if locked:
        return redirect(url_for('dashboard.user_dashboard', quota_exceeded=1))
    
    # Намери grant-а, който притежава ТОЗИ тест — резултатите преди неговата
    # активация не се броят (иначе стар план на същия test_id лъжливо отключва).
    grant_activated_at = None
    for g in user.active_gold_grants():
        if test_id in g.test_id_list():
            grant_activated_at = g.activated_at
            break
    if grant_activated_at is None:
        for g in user.active_plan_grants():
            if g.library_test_id == test_id:
                grant_activated_at = g.activated_at
                break

    # Вземи последните 2 резултата от обикновен тест или микс, СЛЕД активацията на grant-а
    results_query = TestResult.query.filter_by(
        user_id=session['user_id'],
        test_id=test_id
    ).filter(
        TestResult.test_type.in_(['test', 'mix'])
    )
    if grant_activated_at:
        results_query = results_query.filter(TestResult.taken_at >= grant_activated_at)
    last_results = results_query.order_by(TestResult.taken_at.desc()).limit(2).all()
    
    if len(last_results) < 2:
        flash('Трябват поне 2 решени теста (Тест или Микс) за тази функция', 'error')
        return redirect(url_for('dashboard.user_dashboard'))
    
    # Събери грешно отговорените въпроси
    all_questions = test.get_questions()
    q_map = {str(q['id']): q for q in all_questions}
    
    # Въпрос се включва в грешките ако е грешен в ПОНЕ ЕДИН от последните 2 теста
    # Въпрос се премахва само ако е верен И В ДВАТА последни теста
    
    # Намери всички въпроси отговорени в двата теста
    answered_in = [{}, {}]  # {q_id: is_correct} за всеки тест
    for i, result in enumerate(last_results):
        answers = json.loads(result.answers_json)
        for q_id_str, o_idx in answers.items():
            q = q_map.get(str(q_id_str))
            if q:
                try:
                    is_correct = q['options'][int(o_idx)]['isCorrect']
                    answered_in[i][str(q_id_str)] = is_correct
                except (IndexError, KeyError):
                    answered_in[i][str(q_id_str)] = False
    
    wrong_ids = set()
    all_answered = set(answered_in[0].keys()) | set(answered_in[1].keys())
    
    for q_id_str in all_answered:
        correct_in_0 = answered_in[0].get(q_id_str, None)
        correct_in_1 = answered_in[1].get(q_id_str, None)
        
        # Грешен ако е грешен в поне един тест
        # Верен само ако е верен в ДВАТА теста
        if correct_in_0 is False or correct_in_1 is False:
            wrong_ids.add(q_id_str)
        elif correct_in_0 is None or correct_in_1 is None:
            # Отговорен само в един тест — включи ако е грешен
            val = correct_in_0 if correct_in_0 is not None else correct_in_1
            if not val:
                wrong_ids.add(q_id_str)
    
    if not wrong_ids:
        flash('Нямаш грешки от последните 2 теста!', 'success')
        return redirect(url_for('dashboard.user_dashboard'))
    
    # Вземи въпросите с грешки
    wrong_questions = [q for q in all_questions if str(q['id']) in wrong_ids]
    wrong_questions = inject_images(test_id, wrong_questions)
    rnd.shuffle(wrong_questions)
    
    return render_template('user/test.html', test=test, questions=wrong_questions, 
                         shuffle=True, test_type='mistakes', is_demo=False)

@dashboard.route('/test/<int:test_id>/simulator')
@login_required
def simulator(test_id):

    import random as rnd
    from app.utils.grants import test_access_lock
    user = User.query.get(session['user_id'])
    test = Test.query.get_or_404(test_id)

    # БЪГ ФИКС: демо тестовете (test.is_demo) трябва да са ВИНАГИ свободно
    # достъпни за Simulator, без да минават през изискването "първо избери
    # този тест в Library" - точно както вече работи за Test/Mix/Mistakes
    # (виж user_can_access_test() по-горе, която изрично bypass-ва is_demo).
    # Преди тази поправка симулаторът НЯМАШЕ този bypass и връщаше всеки
    # опит за демо симулатор обратно към /library с грешка "не е твоят
    # избран тест" - демото трябваше да е достъпно за всеки, без избор.
    if user.is_admin or test.is_demo:
        pass
    elif not user.has_active_plan():
        if user.library_refresh_if_expired():
            db.session.commit()
        if not (user.library_window_active() and user.library_test_id == test_id):
            flash('Този тест не е твоят активно избран тест в Library. Отвори картата му и натисни бутона за избор, за да отключиш Simulator за него.', 'warning')
            return redirect(url_for('dashboard.library'))
        if not user.library_simulator_available():
            # Free план: 1 симулатор на ден. Тих redirect към dashboard,
            # без popup/toast (потвърдено предпочитание от предишна сесия) -
            # клиентът просто остава на dashboard-а, вижда картата си там.
            return redirect(url_for('dashboard.user_dashboard'))
        # ВАЖНО (бъг поправка): library_last_simulator_at СЕ ЗАПИСВА едва при
        # реален SUBMIT (виж submit_test в app/routes/tests.py), НЕ тук при
        # обикновено зареждане на страницата. Преди тази поправка
        # потребител, който само отваря симулатора и НЕ отговори на нито
        # един въпрос (после затваря страницата/акаунта), губеше дневния си
        # лимит без резултат в историята - сериозен бъг, докладван от
        # потребител. Сега лимитът се "изразходва" само при действително
        # завършен и предаден тест.
    else:
        locked, _owning_grant = test_access_lock(user, test_id)
        if locked:
            return redirect(url_for('dashboard.user_dashboard', quota_exceeded=1))

    questions = test.get_questions()
    questions = inject_images(test_id, questions)
    rnd.shuffle(questions)
    questions = questions[:45]  # Max 45 въпроса за 60 мин
    is_free_plan = not user.is_admin and not user.has_active_plan()
    return render_template('user/simulator.html', test=test, questions=questions, time_limit=60, is_free_plan=is_free_plan)

@dashboard.route('/history')
@login_required
def history():
    user = User.query.get(session['user_id'])
    if user and user.is_admin:
        return redirect(url_for('admin.admin_dashboard'))

    # Същата 30-дневна grace логика, ползвана вече от dashboard джаджата
    # (/api/history) - резултат от изтекъл grant остава видим ОЩЕ 30 дни
    # след expires_at, не изчезва веднага. Преди тази промяна пълната
    # /history страница нямаше никакво филтриране (показваше всичко
    # завинаги) - несъответствие с dashboard джаджата, сега уеднаквено.
    from app.utils.grants import find_result_grant, result_visible, auto_delete_expired_results
    auto_delete_expired_results()

    now = datetime.utcnow()
    from app.utils.grant_cache import fetch_all_grants
    _all_gold, _all_promo, _all_plan = fetch_all_grants(user.id)
    gold_c = {user.id: _all_gold}
    promo_c = {user.id: _all_promo}
    plan_c = {user.id: _all_plan}

    all_results = TestResult.query.filter_by(user_id=user.id).order_by(TestResult.taken_at.desc()).all()
    results = []
    for r in all_results:
        status, grant = find_result_grant(r, now, gold_c, plan_c, promo_c)
        if result_visible(r, status, grant, now):
            results.append(r)

    return render_template('user/history.html', user=user, results=results)

# ============================================================
#  SUPPORT CENTER ROUTES → app/routes/support.py
# ============================================================

# ============================================================
#  ADMIN ROUTES
# ============================================================


# User API routes (preferences, usage, billing, ads) → app/routes/user_settings.py


# Admin routes → app/routes/admin.py


@dashboard.route('/demo/test/<int:test_id>')
def demo_test(test_id):
    """Демо тест - без регистрация"""
    import random as rnd
    test = Test.query.get_or_404(test_id)
    if not test.is_demo:
        flash('Този тест вече не е достъпен като демо. Избери друг тест от списъка.', 'warning')
        return redirect(url_for('dashboard.demo'))
    mode = request.args.get('mode', 'test')
    questions = test.get_questions()
    questions = inject_images(test_id, questions)

    # Маркетингово решение: демото (публичната /demo секция, зареждана от
    # landing страницата) показва САМО Simulator - НЕ Test/Mix/Mistakes.
    # Заключено и тук на сървъра (не само скрито от UI-то), за да не може
    # някой просто да редактира ?mode= в адреса и да заобиколи ограничението.
    rnd.shuffle(questions)
    questions = questions[:45]
    return render_template('user/simulator.html', test=test, questions=questions, time_limit=60, is_demo=True, is_free_plan=True)

@dashboard.route('/demo/test/<int:test_id>/submit', methods=['POST'])
def demo_submit(test_id):
    """Оценяване на демо тест - без регистрация"""
    test = Test.query.get_or_404(test_id)
    all_questions = test.get_questions()
    answers = request.json.get('answers', {})
    answers_norm = {str(k): int(v) for k, v in answers.items()}
    score = 0
    for q in all_questions:
        selected = answers_norm.get(str(q['id']))
        if selected is not None:
            try:
                if q['options'][int(selected)]['isCorrect']:
                    score += 1
            except (IndexError, KeyError):
                pass
    total = len(all_questions)
    percent = round((score / total) * 100, 1) if total > 0 else 0
    passed = percent >= 90
    return jsonify({'score': score, 'total': total, 'percent': percent, 'passed': passed})

@dashboard.route('/qimage/<int:test_id>/<path:filename>')
def serve_qimage(test_id, filename):
    """Legacy route — все още активен за снимки, останали в Postgres
    (storage='db'), и като fallback за стари линкове/кеш в браузъра.
    Новите снимки (storage='r2') вече идват директно от R2 URL, инжектиран
    от inject_images() — този route не се удря за тях в нормалния поток."""
    from flask import abort, Response, redirect
    from app.utils.images import get_image_bytes
    from app.models.test import TestImage
    from app.utils import r2_storage
    try:
        question_id = int(filename.rsplit('.', 1)[0])
    except (ValueError, IndexError):
        abort(404)

    row = TestImage.query.filter_by(test_id=test_id, question_id=question_id).first()
    if row and row.storage == 'r2' and row.r2_key:
        return redirect(r2_storage.public_url_for(row.r2_key), code=301)

    result = get_image_bytes(test_id, question_id)
    if not result:
        abort(404)
    img_bytes, fmt = result
    mimetype = 'image/png' if fmt == 'png' else 'image/jpeg'
    resp = Response(img_bytes, mimetype=mimetype)
    resp.headers['Cache-Control'] = 'public, max-age=2592000'  # 30 дни, снимките не се менят
    return resp


@dashboard.route('/library/search')
@login_required
def library_search():
    from flask import jsonify
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    results = Test.query.filter(Test.title.ilike(f'%{q}%')).limit(20).all()
    return jsonify([{
        'id': t.id,
        'title': t.title,
        'category': t.category,
        'question_count': t.question_count,
        'is_demo': t.is_demo
    } for t in results])
