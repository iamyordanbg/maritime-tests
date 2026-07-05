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
from app.utils.codes import subscription_code, result_public_code, get_or_create_subscription_code
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
    _all_gold, _all_plan = fetch_all_grants(user.id)
    gold_c = {user.id: _all_gold}
    plan_c = {user.id: _all_plan}
    grant_ts_cache = {}

    # Извличаме малко повече от нужното, за да компенсираме резултатите,
    # които ще бъдат скрити (grant изтекъл преди >30 дни), без да чупим
    # пагинацията — филтрираме in-memory и пълним до `limit`.
    all_results = (TestResult.query
                   .options(db.joinedload(TestResult.test))
                   .filter_by(user_id=user.id).order_by(TestResult.taken_at.desc())
                   .all())

    visible_results = []
    for r in all_results:
        status, grant = find_result_grant(r, now, gold_c, plan_c)
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
            public_code = result_public_code(grant.id, r.taken_at, seq, grant_type=grant_type)

        items.append({
            'title': r.test.title[:45] + ('...' if len(r.test.title) > 45 else ''),
            'taken_at': r.taken_at.strftime('%d.%m.%Y %H:%M'),
            'percent': r.percent,
            'score': r.score,
            'total': r.total,
            'passed': r.passed,
            'test_type': type_labels.get(r.test_type, r.test_type.title() if r.test_type else 'Test'),
            'result_id': r.id,
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
    from app.models.plan_grant import PlanGrant
    from app.utils.grant_cache import fetch_all_grants
    _all_gold_grants, _all_plan_grants = fetch_all_grants(user.id)
    _now = datetime.utcnow()
    # "Затопляме" кеша на User модела (has_active_plan/effective_plan_label/...
    # четат self._cached_gold_grants/_cached_plan_grants) — иначе те биха
    # тригернали СВОИ собствени, отделни заявки при първо извикване по-долу
    # или в темплейта, дублирайки вече изтегленото тук.
    user._cached_gold_grants = [g for g in _all_gold_grants if g.expires_at > _now]
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

    # Без избран тест → задължително към library. Изключения: Gold (избира през
    # /activate) и Basic/Plus с ВЕЧЕ избран тест за всичките си активни grant-ове.
    if (user.plan != 'gold'
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

    # Gold: всеки активиран код е автономна карта (собствени тестове, лимит, срок)
    gold_cards = []
    test_grant_info = {}
    if user.plan == 'gold':
        from app.models.gold_grant import GoldGrant
        active_grants = sorted([g for g in _all_gold_grants if g.expires_at > _now], key=lambda g: g.activated_at)
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
            gold_cards.append({
                'grant': g, 'tests': g_tests, 'days_left': g_days_left,
                'tests_remaining': g_remaining, 'tests_quota': g.quota,
                'department': g.department, 'plan_label': 'Gold',
                'subscription_code': get_or_create_subscription_code('gold', g.id),
            })
            for t in g_tests:
                test_grant_info[t.id] = {
                    'days_left': g_days_left, 'tests_remaining': g_remaining,
                    'tests_quota': g.quota, 'grant_id': g.id, 'activated_at': g.activated_at,
                    'subscription_code': get_or_create_subscription_code('gold', g.id),
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
    mistakes_unlocked_by_test = {}
    if user.has_active_plan():
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
                           all_cards=gold_cards + plan_cards,
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
        # Free поток — непроменено легаси поведение (1 избран тест/седмица)
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

    return render_template('user/library.html', tests=tests_data, library_state=library_state, user=user)


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

    # Free поток (легаси единично поле) — непроменено поведение
    user.library_refresh_if_expired()
    if user.library_window_active():
        return jsonify({'success': False, 'message': 'Вече имаш избран тест за тази седмица.'}), 400

    user.library_test_id = test.id
    user.library_selected_at = datetime.utcnow()
    user.library_last_simulator_at = None
    db.session.commit()

    return jsonify({'success': True, 'test_id': test.id, 'test_title': test.title})


from app.utils.images import inject_images
def user_can_access_test(user, test):
    """Дали потребителят има право да достъпи даден тест (test/mix/mistakes режими, НЕ симулатор)."""
    if user.is_admin or user.is_active:
        return True
    if test.is_demo:
        return True
    user.library_refresh_if_expired()
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
    return render_template('user/test.html', test=test, questions=questions, shuffle=shuffle, is_free_plan=is_free_plan, is_demo=False)

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
        return redirect(url_for('admin.admin_tests'))
    
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

    if not (user.is_admin or user.is_active):
        user.library_refresh_if_expired()
        if not (user.library_window_active() and user.library_test_id == test_id):
            flash('Симулаторът е достъпен само за теста, който си избрал в Library.', 'warning')
            return redirect(url_for('dashboard.library'))
        if not user.library_simulator_available():
            flash('Вече реши симулаторен тест днес. Опитай отново утре.', 'warning')
            return redirect(url_for('dashboard.library'))
        user.library_last_simulator_at = datetime.utcnow()
        db.session.commit()
    elif not user.is_admin:
        locked, _owning_grant = test_access_lock(user, test_id)
        if locked:
            return redirect(url_for('dashboard.user_dashboard', quota_exceeded=1))

    questions = test.get_questions()
    questions = inject_images(test_id, questions)
    rnd.shuffle(questions)
    questions = questions[:45]  # Max 45 въпроса за 60 мин
    return render_template('user/simulator.html', test=test, questions=questions, time_limit=60)

@dashboard.route('/history')
@login_required
def history():
    user = User.query.get(session['user_id'])
    if user and user.is_admin:
        return redirect(url_for('admin.admin_dashboard'))
    results = TestResult.query.filter_by(user_id=user.id).order_by(TestResult.taken_at.desc()).all()
    return render_template('user/history.html', user=user, results=results)

@dashboard.route('/signal', methods=['POST'])
@login_required
def submit_signal():
    from app.services.email import send_signal_notification
    msg = request.form.get('message', '').strip()[:500]
    sig_type = request.form.get('type', 'bug')
    user = User.query.get(session['user_id'])
    if msg:
        signal = Signal(
            user_id=user.id,
            user_name=user.name,
            user_email=user.email,
            type=sig_type,
            message=msg
        )
        db.session.add(signal)
        db.session.commit()
        # Изпращаме имейл до admin
        send_signal_notification(user.name, user.email, sig_type, msg)
    return jsonify({'success': True})

@dashboard.route('/signals/unread')
@login_required
def unread_signals():
    user_id = session['user_id']
    count = Signal.query.filter_by(user_id=user_id, is_read=False).filter(Signal.reply != None).count()
    return jsonify({'count': count})

@dashboard.route('/signals/read/<int:signal_id>', methods=['POST'])
@login_required
def mark_signal_read(signal_id):
    signal = Signal.query.filter_by(id=signal_id, user_id=session['user_id']).first()
    if signal:
        signal.is_read = True
        db.session.commit()
    return jsonify({'success': True})

@dashboard.route('/signals/my')
@login_required
def my_signals():
    signals = Signal.query.filter_by(user_id=session['user_id']).order_by(Signal.created_at.desc()).all()
    return jsonify([{
        'id': s.id,
        'type': s.type,
        'message': s.message,
        'reply': s.reply,
        'replied_at': s.replied_at.strftime('%d.%m.%Y %H:%M') if s.replied_at else None,
        'is_read': s.is_read,
        'created_at': s.created_at.strftime('%d.%m.%Y %H:%M')
    } for s in signals])


# ============================================================
#  SUPPORT CENTER ROUTES
# ============================================================

@dashboard.route('/support/tickets')
@login_required
def get_tickets():
    """Всички tickets на потребителя"""
    user_id = session['user_id']
    tickets = Ticket.query.filter_by(user_id=user_id).order_by(Ticket.updated_at.desc()).all()
    result = []
    for t in tickets:
        unread = TicketMessage.query.filter_by(
            ticket_id=t.id, sender='admin', is_read=False).count()
        last_msg = TicketMessage.query.filter_by(
            ticket_id=t.id).order_by(TicketMessage.created_at.desc()).first()
        result.append({
            'id': t.id,
            'subject': t.subject,
            'type': t.type,
            'status': t.status,
            'unread': unread,
            'last_message': last_msg.body[:80] + '...' if last_msg and len(last_msg.body) > 80 else (last_msg.body if last_msg else ''),
            'updated_at': t.updated_at.strftime('%d.%m.%Y %H:%M')
        })
    return jsonify(result)

@dashboard.route('/support/tickets/<int:ticket_id>/messages')
@login_required
def get_ticket_messages(ticket_id):
    """Съобщенията в ticket"""
    ticket = Ticket.query.filter_by(id=ticket_id, user_id=session['user_id']).first_or_404()
    # Маркираме admin съобщенията като прочетени
    TicketMessage.query.filter_by(
        ticket_id=ticket_id, sender='admin', is_read=False).update({'is_read': True})
    db.session.commit()
    msgs = TicketMessage.query.filter_by(ticket_id=ticket_id).order_by(TicketMessage.created_at).all()
    return jsonify({
        'ticket': {
            'id': ticket.id,
            'subject': ticket.subject,
            'type': ticket.type,
            'status': ticket.status
        },
        'messages': [{
            'id': m.id,
            'sender': m.sender,
            'body': m.body,
            'created_at': m.created_at.strftime('%d.%m.%Y %H:%M')
        } for m in msgs]
    })

@dashboard.route('/support/tickets', methods=['POST'])
@login_required
def create_ticket():
    """Нов ticket"""
    from app.services.email import send_new_ticket_notification
    user_id = session['user_id']
    user = User.query.get(user_id)
    subject = request.form.get('subject', '').strip()[:200]
    body = request.form.get('body', '').replace('<', '&lt;').strip()[:500]
    ticket_type = request.form.get('type', 'question')
    if not subject or not body:
        return jsonify({'success': False, 'message': 'Попълнете всички полета'})
    ticket = Ticket(user_id=user_id, subject=subject, type=ticket_type)
    db.session.add(ticket)
    db.session.flush()
    msg = TicketMessage(ticket_id=ticket.id, sender='user', body=body)
    db.session.add(msg)
    db.session.commit()
    send_new_ticket_notification(user.name, user.email, subject, body, ticket.id)
    return jsonify({'success': True, 'ticket_id': ticket.id})

@dashboard.route('/support/tickets/<int:ticket_id>/reply', methods=['POST'])
@login_required
def reply_ticket(ticket_id):
    """Потребителят отговаря на ticket"""
    from app.services.email import send_user_reply_notification
    ticket = Ticket.query.filter_by(id=ticket_id, user_id=session['user_id']).first_or_404()
    user = User.query.get(session['user_id'])
    body = request.form.get('body', '').replace('<', '&lt;').strip()[:500]
    if not body:
        return jsonify({'success': False, 'message': 'Празно съобщение'})
    ticket.status = 'open'
    ticket.updated_at = datetime.utcnow()
    msg = TicketMessage(ticket_id=ticket_id, sender='user', body=body)
    db.session.add(msg)
    db.session.commit()
    send_user_reply_notification(user.name, user.email, ticket.subject, body, ticket_id)
    return jsonify({'success': True})

@dashboard.route('/support/unread')
@login_required
def support_unread():
    """Брой непрочетени отговори"""
    user_id = session['user_id']
    count = (TicketMessage.query
             .join(Ticket, TicketMessage.ticket_id == Ticket.id)
             .filter(Ticket.user_id == user_id,
                     TicketMessage.sender == 'admin',
                     TicketMessage.is_read == False)
             .count())
    return jsonify({'count': count})

# ============================================================
#  ADMIN ROUTES
# ============================================================


@dashboard.route('/api/random-ad')
def api_random_ad():
    from app.models.ad import Ad
    ad = Ad.query.filter_by(is_active=True).order_by(db.func.random()).first()
    if not ad:
        return jsonify({'ad': None})
    ad.impressions = (ad.impressions or 0) + 1
    db.session.commit()
    return jsonify({'ad': {
        'id': ad.id, 'title': ad.title, 'image_url': ad.image_url or '',
        'link_url': ad.link_url or '', 'body': ad.body or '',
    }})


@dashboard.route('/api/ad-click/<int:ad_id>', methods=['POST'])
def api_ad_click(ad_id):
    from app.models.ad import Ad
    ad = Ad.query.get(ad_id)
    if ad:
        ad.clicks = (ad.clicks or 0) + 1
        db.session.commit()
    return jsonify({'success': True})


@dashboard.route('/api/my-usage')
@login_required
def api_my_usage():
    from app.models.gold_grant import GoldGrant
    from app.models.plan_grant import PlanGrant
    import math
    user = User.query.get(session['user_id'])
    now = datetime.utcnow()
    cards = []

    for g in GoldGrant.query.filter(GoldGrant.user_id == user.id, GoldGrant.expires_at > now).order_by(GoldGrant.activated_at.asc()).all():
        test_ids = g.test_id_list()
        titles = [t.title for t in Test.query.filter(Test.id.in_(test_ids)).all()] if test_ids else []
        # Реален брой решени — директно от TestResult, не от съхранено поле
        # (което никога не се актуализира надеждно) — вижте същата логика, ползвана
        # за самите карти на dashboard-а, за да няма разминаване между двете места.
        used_real = (TestResult.query
                     .filter(TestResult.user_id == user.id,
                             TestResult.test_id.in_(test_ids),
                             TestResult.taken_at >= g.activated_at)
                     .count()) if test_ids else 0
        total_seconds = max(1, (g.expires_at - g.activated_at).total_seconds())
        elapsed_seconds = max(0, (now - g.activated_at).total_seconds())
        cards.append({
            'plan': 'Gold', 'test_names': titles,
            'quota': g.quota, 'tests_used': used_real,
            'tests_remaining': max(0, g.quota - used_real),
            'activated_at': g.activated_at.strftime('%d %b %Y, %H:%M') + ' (UTC)',
            'expires_at': g.expires_at.strftime('%d %b %Y, %H:%M') + ' (UTC)',
            'days_remaining': max(0, math.ceil((g.expires_at - now).total_seconds() / 86400)),
            'pct_remaining': max(0, min(100, int(100 - (elapsed_seconds / total_seconds * 100)))),
            'subscription_code': get_or_create_subscription_code('gold', g.id),
            '_activated_raw': g.activated_at,
        })

    for g in PlanGrant.query.filter(PlanGrant.user_id == user.id, PlanGrant.expires_at > now).order_by(PlanGrant.activated_at.asc()).all():
        title = None
        if g.library_test_id:
            t = Test.query.get(g.library_test_id)
            title = t.title if t else None
        used_real = (TestResult.query
                     .filter(TestResult.user_id == user.id,
                             TestResult.test_id == g.library_test_id,
                             TestResult.taken_at >= g.activated_at)
                     .count()) if g.library_test_id else 0
        total_seconds = max(1, (g.expires_at - g.activated_at).total_seconds())
        elapsed_seconds = max(0, (now - g.activated_at).total_seconds())
        cards.append({
            'plan': g.plan.capitalize(), 'test_names': [title] if title else [],
            'quota': g.quota, 'tests_used': used_real,
            'tests_remaining': max(0, g.quota - used_real),
            'activated_at': g.activated_at.strftime('%d %b %Y, %H:%M') + ' (UTC)',
            'expires_at': g.expires_at.strftime('%d %b %Y, %H:%M') + ' (UTC)',
            'days_remaining': max(0, math.ceil((g.expires_at - now).total_seconds() / 86400)),
            'pct_remaining': max(0, min(100, int(100 - (elapsed_seconds / total_seconds * 100)))),
            'subscription_code': get_or_create_subscription_code('plan', g.id),
            '_activated_raw': g.activated_at,
        })

    # Сортираме ЦЯЛОСТНИЯ списък (Gold + Basic/Plus смесени) по реалната дата
    # на активиране - най-старият план най-отгоре, най-скоро активираният
    # най-отдолу. По-горе всеки тип се append-ва отделно (Gold, после
    # Plan), затова е нужен този финален merge-sort, за да е вярно и при
    # потребители с активни грантове от двата типа едновременно.
    cards.sort(key=lambda c: c['_activated_raw'])
    for c in cards:
        del c['_activated_raw']

    return jsonify({'cards': cards})


@dashboard.route('/api/my-billing')
@login_required
def api_my_billing():
    from app.models.payment import Payment
    from app.models.promo import PromoCode
    from app.models.plan_grant import PlanGrant
    from app.models.gold_grant import GoldGrant
    user = User.query.get(session['user_id'])
    payments = Payment.query.filter_by(user_id=user.id).order_by(Payment.paid_at.desc()).all()

    result = []
    for p in payments:
        entry = {
            'id': p.id,
            'plan': p.plan,
            'amount': p.amount,
            'paid_at': p.paid_at.strftime('%d.%m.%Y %H:%M'),
            'promo_email_sent': bool(p.promo_email_sent),
            'codes': [],
            'loaded_test': None,
            'active_from': None,
            'active_until': None,
        }
        if p.plan == 'gold' and p.stripe_payment_intent:
            codes = PromoCode.query.filter_by(
                stripe_payment_intent=p.stripe_payment_intent
            ).order_by(PromoCode.id.asc()).all()
            code_entries = []
            for c in codes:
                code_entry = {
                    'code': c.code,
                    'is_used': bool(c.is_used),
                    'used_by': c.used_by or '',
                    'shared_to': c.shared_to or '',
                    'active_from': None,
                    'active_until': None,
                    'activate_by': None,
                }
                if c.is_used:
                    g = GoldGrant.query.filter_by(promo_code=c.code).first()
                    if g:
                        if g.activated_at:
                            code_entry['active_from'] = g.activated_at.strftime('%d.%m.%Y %H:%M')
                        if g.expires_at:
                            code_entry['active_until'] = g.expires_at.strftime('%d.%m.%Y %H:%M')
                elif c.expires_at:
                    code_entry['activate_by'] = c.expires_at.strftime('%d.%m.%Y %H:%M')
                code_entries.append(code_entry)
            entry['codes'] = code_entries
        elif p.plan in ('basic', 'plus'):
            grant = PlanGrant.query.filter_by(payment_id=p.id).first()
            if grant:
                if grant.library_test_id:
                    t = Test.query.get(grant.library_test_id)
                    entry['loaded_test'] = t.title if t else None
                if grant.activated_at:
                    entry['active_from'] = grant.activated_at.strftime('%d.%m.%Y %H:%M')
                if grant.expires_at:
                    entry['active_until'] = grant.expires_at.strftime('%d.%m.%Y %H:%M')
        result.append(entry)

    return jsonify({'payments': result})


@dashboard.route('/settings')
@login_required
def settings():
    user = User.query.get(session['user_id'])
    if user and user.is_admin:
        return redirect(url_for('admin.admin_dashboard'))

    from app.models.payment import Payment
    from app.models.promo import PromoCode
    from app.utils.codes import get_or_create_subscription_code
    payments = Payment.query.filter_by(user_id=user.id).order_by(Payment.paid_at.desc()).all()

    gold_codes_by_payment = {}
    for p in payments:
        if p.plan == 'gold' and p.stripe_payment_intent:
            gold_codes_by_payment[p.id] = PromoCode.query.filter_by(
                stripe_payment_intent=p.stripe_payment_intent
            ).order_by(PromoCode.id.asc()).all()

    # Същият четим код (BG + буква-цифра x3), използван вече за абонаментите
    # в dashboard изгледа — вместо суровия PlanGrant.id/GoldGrant.id badge в
    # Billing таба (виж app/utils/codes.py за самия алгоритъм).
    plan_grant_codes = {g.id: get_or_create_subscription_code('plan', g.id) for g in user.active_plan_grants()}
    gold_grant_codes = {g.id: get_or_create_subscription_code('gold', g.id) for g in user.active_gold_grants()}

    return render_template('user/settings.html', user=user, payments=payments,
                            gold_codes_by_payment=gold_codes_by_payment,
                            plan_grant_codes=plan_grant_codes,
                            gold_grant_codes=gold_grant_codes)

@dashboard.route('/settings/profile', methods=['POST'])
@login_required
def settings_profile():
    try:
        user = User.query.get(session['user_id'])
        user.nick = request.form.get('nick', '').strip()
        user.firstname = request.form.get('firstname', '').strip()
        user.lastname = request.form.get('lastname', '').strip()
        db.session.commit()
        return jsonify({'success': True, 'message': '✓ Профилът е запазен'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})



@dashboard.route('/settings/check-password', methods=['POST'])
@login_required
def check_password():
    from werkzeug.security import check_password_hash
    user = User.query.get(session['user_id'])
    cur = request.form.get('current_password', '')
    valid = check_password_hash(user.password, cur)
    return jsonify({'valid': valid})

@dashboard.route('/settings/notifications', methods=['POST'])
@login_required
def settings_notifications():
    user = User.query.get(session['user_id'])
    data = request.get_json()
    user.notif_subscription = data.get('notif_subscription', True)
    db.session.commit()
    return jsonify({'success': True})

@dashboard.route('/logout-all', methods=['POST'])
@login_required
def logout_all():
    session.clear()
    return jsonify({'success': True})

@dashboard.route('/settings/delete-account', methods=['POST'])
@login_required
def delete_account():
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'success': False, 'message': 'Акаунтът не е намерен.'})
    try:
        from app.models.payment import Payment
        Payment.query.filter_by(user_id=user.id).delete()
        TestResult.query.filter_by(user_id=user.id).delete()
        db.session.delete(user)
        db.session.commit()
        session.clear()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@dashboard.route('/settings/password', methods=['POST'])
@login_required
def settings_password():
    user = User.query.get(session['user_id'])
    cur = request.form.get('current_password', '')
    new_pass = request.form.get('new_password', '')
    if not check_password_hash(user.password, cur):
        return jsonify({'success': False, 'message': 'Грешна текуща парола'})
    if len(new_pass) < 6:
        return jsonify({'success': False, 'message': 'Паролата е прекалено кратка'})
    user.password = generate_password_hash(new_pass)
    db.session.commit()
    return jsonify({'success': True, 'message': '✓ Паролата е сменена'})

@dashboard.route('/admin/api/snapshots/<metric>')
@admin_required
def admin_snapshots(metric):
    """Връща данни за графика по метрика и период"""
    period = request.args.get('period', '1Y')  # 6M, 1Y, 2Y, 3Y, 5Y, ALL
    
    now = datetime.utcnow()
    
    if period == '6M':
        from_date = datetime(now.year, now.month, 1) - timedelta(days=180)
    elif period == '1Y':
        from_date = datetime(now.year - 1, now.month, 1)
    elif period == '2Y':
        from_date = datetime(now.year - 2, now.month, 1)
    elif period == '3Y':
        from_date = datetime(now.year - 3, now.month, 1)
    elif period == '5Y':
        from_date = datetime(now.year - 5, now.month, 1)
    else:  # ALL
        from_date = datetime(2020, 1, 1)
    
    snapshots = MonthlySnapshot.query.filter(
        MonthlySnapshot.year > from_date.year,
        db.or_(
            MonthlySnapshot.year > from_date.year,
            db.and_(MonthlySnapshot.year == from_date.year, MonthlySnapshot.month >= from_date.month)
        )
    ).order_by(MonthlySnapshot.year, MonthlySnapshot.month).all()
    
    valid = ['total_users', 'active_users', 'passive_users', 'demo_users']
    if metric not in valid:
        return jsonify({'error': 'Invalid metric'}), 400
    
    return jsonify({
        'metric': metric,
        'period': period,
        'labels': [s.label for s in snapshots],
        'data': [getattr(s, metric) for s in snapshots],
    })

@dashboard.route('/admin/api/snapshots/record', methods=['POST'])
@admin_required
def admin_record_snapshot():
    """Ръчно записване на snapshot"""
    snap = record_monthly_snapshot()
    return jsonify({'success': True, 'message': f'Snapshot {snap.year}-{snap.month:02d} записан'})

@dashboard.route('/demo')
def demo():
    # Прост брояч — без лични данни
    import json
    from pathlib import Path
    counter_file = Path(__file__).parent.parent / 'static' / 'demo_counter.json'
    try:
        data = json.loads(counter_file.read_text()) if counter_file.exists() else {'count': 0}
        data['count'] = data.get('count', 0) + 1
        counter_file.write_text(json.dumps(data))
    except Exception:
        pass

    # Send ALL tests - demo ones playable, others informative
    demo_tests_raw = Test.query.options(db.defer(Test.questions_json)).order_by(Test.category, Test.level).all()
    
    level_map = {
        'Operational Level': 'operational',
        'operational level': 'operational',
        'operational': 'operational',
        'Оперативно ниво': 'operational',
        'Management Level': 'management',
        'management level': 'management',
        'management': 'management',
        'Мениджърско ниво': 'management',
        'ETO': 'eto',
        'eto': 'eto',
        'Master Level': 'master',
        'master level': 'master',
        'master': 'master',
        'Капитанско ниво': 'master',
        'Support Level': 'operational',
        'support level': 'operational',
    }
    
    # Only expose safe fields - never expose questions_json or internal data
    tests_data = []
    for t in demo_tests_raw:
        level_key = level_map.get(t.level) or level_map.get(t.level.strip()) or 'operational'
        cat = t.category.lower().strip()
        if cat not in ('deck', 'engine'):
            cat = 'deck' if 'deck' in cat or 'палуб' in cat.lower() else 'engine'
        tests_data.append({
            'id': t.id,
            'title': t.title,
            'category': cat,
            'level_key': level_key,
            'question_count': t.question_count,
            'is_demo': t.is_demo
        })
    
    return render_template('demo.html', demo_tests=tests_data, recaptcha_site_key=RECAPTCHA_SITE_KEY)


@dashboard.route('/admin/demo')
@admin_required
def admin_demo():
    tests = Test.query.filter_by(is_demo=True).order_by(Test.category, Test.level, Test.title).all()
    demo_count = Test.query.filter_by(is_demo=True).count()
    deck_demo = Test.query.filter_by(is_demo=True, category='deck').count()
    engine_demo = Test.query.filter_by(is_demo=True, category='engine').count()
    return render_template('admin/demo.html',
        active='demo',
        tests=tests,
        demo_count=demo_count,
        deck_demo=deck_demo,
        engine_demo=engine_demo
    )

@dashboard.route('/admin/demo/toggle/<int:test_id>', methods=['POST'])
@admin_required
def admin_demo_toggle(test_id):
    # Extra security: verify request is AJAX from same origin
    if not request.is_json and request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        # Accept both JSON and same-origin fetch
        pass
    
    # Validate test_id is positive integer (already done by Flask route)
    test = Test.query.get_or_404(test_id)
    
    # Toggle demo status
    test.is_demo = not test.is_demo
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_demo': test.is_demo,
        'test_id': test.id
    })


@dashboard.route('/admin/demo/reset-all', methods=['POST'])
@admin_required  
def admin_demo_reset_all():
    """Reset ALL tests to is_demo=False - emergency fix"""
    Test.query.update({Test.is_demo: False})
    db.session.commit()
    count = Test.query.count()
    return jsonify({'success': True, 'message': f'Reset {count} tests to is_demo=False'})




def get_google_redirect_uri():
    return os.environ.get('BASE_URL', 'https://web-production-ca6b6.up.railway.app') + '/auth/google/callback'

@dashboard.route('/auth/google')
def google_login():
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': get_google_redirect_uri(),
        'response_type': 'code',
        'scope': 'openid email profile',
        'access_type': 'offline',
        'prompt': 'select_account'
    }
    return redirect(GOOGLE_AUTH_URL + '?' + urlencode(params))

@dashboard.route('/auth/google/callback')
def google_callback():
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error or not code:
        flash('Google вход е отказан.', 'error')
        return redirect(url_for('login'))
    
    # Exchange code for token
    token_data = {
        'code': code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': get_google_redirect_uri(),
        'grant_type': 'authorization_code'
    }
    token_resp = http_requests.post(GOOGLE_TOKEN_URL, data=token_data)
    if not token_resp.ok:
        flash('Грешка при Google автентикация.', 'error')
        return redirect(url_for('login'))
    
    access_token = token_resp.json().get('access_token')
    
    # Get user info
    user_info = http_requests.get(
        GOOGLE_USERINFO_URL,
        headers={'Authorization': f'Bearer {access_token}'}
    ).json()
    
    google_email = user_info.get('email', '').lower().strip()
    google_name = user_info.get('name', '')
    google_id = user_info.get('sub', '')
    
    if not google_email:
        flash('Не може да се получи имейл от Google.', 'error')
        return redirect(url_for('login'))
    
    # Find or create user
    user = User.query.filter_by(email=google_email).first()
    
    if user:
        # Existing user - log in
        session['user_id'] = user.id
        redirect_url = url_for('admin_dashboard') if user.is_admin else url_for('user_dashboard')
        # Return JSON for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'redirect': redirect_url})
        return redirect(redirect_url)
    else:
        # New user - create account
        new_user = User(
            name=google_name or google_email.split('@')[0],
            email=google_email,
            password=generate_password_hash(google_id + GOOGLE_CLIENT_SECRET[:8]),
            is_admin=False,
            is_active=True
        )
        db.session.add(new_user)
        db.session.commit()
        session['user_id'] = new_user.id
        flash(f'Добре дошъл, {new_user.name}! Акаунтът ти е създаден с Google.', 'success')
        return redirect(url_for('user_dashboard'))


@dashboard.route('/debug-env')
def debug_env():
    import os
    return jsonify({
        'RECAPTCHA_SITE_KEY': os.environ.get('RECAPTCHA_SITE_KEY', 'NOT SET'),
        'RECAPTCHA_SITE_KEY_len': len(os.environ.get('RECAPTCHA_SITE_KEY', '')),
        'GOOGLE_CLIENT_ID': os.environ.get('GOOGLE_CLIENT_ID', 'NOT SET')[:20] + '...',
        'module_level_key': RECAPTCHA_SITE_KEY[:20] if RECAPTCHA_SITE_KEY else 'EMPTY'
    })




@dashboard.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    email = session.get('pending_verify_email')
    if not email:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        otp = request.form.get('otp', '').strip()
        user = User.query.filter_by(email=email).first()
        
        if not user:
            flash('Грешка. Опитай отново.', 'error')
            return render_template('verify_otp.html')
        
        if user.otp_expires and datetime.utcnow() > user.otp_expires:
            flash('Кодът е изтекъл. Регистрирай се отново.', 'error')
            return render_template('verify_otp.html', expired=True)
        
        if user.otp_code != otp:
            flash('Грешен код. Опитай отново.', 'error')
            return render_template('verify_otp.html')
        
        # Verify user
        user.email_verified = True
        user.otp_code = None
        user.otp_expires = None
        db.session.commit()
        
        session.pop('pending_verify_email', None)
        session['user_id'] = user.id
        session['user_name'] = user.name
        session['is_admin'] = user.is_admin
        session['just_logged_in'] = True
        flash('Акаунтът е активиран! Добре дошъл!', 'success')
        return redirect(url_for('admin_dashboard') if user.is_admin else url_for('user_dashboard'))
    
    return render_template('verify_otp.html', email=email)


@dashboard.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = request.form.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False, 'message': 'Имейлът не е регистриран.'})
    
    import random
    otp = str(random.randint(100000, 999999))
    user.verification_token = None
    user.otp_code = otp
    from datetime import timedelta as _td2
    user.otp_expires = datetime.utcnow() + _td2(minutes=5)
    db.session.commit()
    
    if BREVO_API_KEY:
        send_otp_async(email, otp)
    
    return jsonify({'success': True})


@dashboard.route('/reset-password', methods=['GET', 'POST'])
def reset_password_otp():
    email = session.get('forgot_email')
    
    if request.method == 'POST':
        # Step 1: email submitted - send OTP
        if 'email' in request.form and 'otp' not in request.form:
            email = request.form.get('email', '').strip().lower()
            user = User.query.filter_by(email=email).first()
            if not user:
                return jsonify({'success': False, 'message': 'Имейлът не е регистриран.'})
            import random
            from datetime import timedelta as _td3
            otp = str(random.randint(100000, 999999))
            user.otp_code = otp
            user.otp_expires = datetime.utcnow() + _td3(minutes=5)
            db.session.commit()
            if BREVO_API_KEY:
                send_otp_async(email, otp)
            session['forgot_email'] = email
            return jsonify({'success': True})
        
        # Step 2: OTP submitted
        if 'otp' in request.form and 'password' not in request.form:
            otp = request.form.get('otp', '').strip()
            user = User.query.filter_by(email=email).first()
            if not user or user.otp_code != otp:
                return jsonify({'success': False, 'message': 'Грешен код.'})
            if user.otp_expires and datetime.utcnow() > user.otp_expires:
                return jsonify({'success': False, 'message': 'Кодът е изтекъл.'})
            session['forgot_otp_verified'] = True
            return jsonify({'success': True})
        
        # Step 3: new password submitted
        if 'password' in request.form:
            if not session.get('forgot_otp_verified'):
                return jsonify({'success': False, 'message': 'Невалидна сесия.'})
            password = request.form.get('password', '')
            confirm = request.form.get('confirm_password', '')
            if password != confirm:
                return jsonify({'success': False, 'message': 'Паролите не съвпадат.'})
            if len(password) < 6:
                return jsonify({'success': False, 'message': 'Паролата е прекалено кратка.'})
            user = User.query.filter_by(email=email).first()
            if not user:
                return jsonify({'success': False, 'message': 'Грешка. Опитай отново.'})
            user.password = generate_password_hash(password)
            user.otp_code = None
            user.otp_expires = None
            db.session.commit()
            session.pop('forgot_email', None)
            session.pop('forgot_otp_verified', None)
            return jsonify({'success': True, 'redirect': '/?login=1'})
    
    return render_template('reset_password.html')




@dashboard.route('/resend-otp', methods=['POST'])
def resend_otp():
    email = session.get('pending_verify_email')
    if not email:
        return jsonify({'success': False, 'message': 'Сесията е изтекла.'})
    
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False})
    
    import random
    otp = str(random.randint(100000, 999999))
    user.otp_code = otp
    user.otp_expires = datetime.utcnow() + __import__('datetime').timedelta(minutes=5)
    db.session.commit()
    
    send_otp_async(email, otp)
    return jsonify({'success': True})

@dashboard.route('/verify-pending')
def verify_pending():
    return render_template('verify_pending.html')

@dashboard.route('/verify-email/<token>')
def verify_email(token):
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        flash('Невалиден или изтекъл верификационен линк.', 'error')
        return redirect(url_for('index'))
    user.email_verified = True
    user.verification_token = None
    db.session.commit()
    session['user_id'] = user.id
    flash('Имейлът е потвърден! Добре дошъл!', 'success')
    return redirect(url_for('admin_dashboard') if user.is_admin else url_for('user_dashboard'))

@dashboard.route('/ping')
def ping():
    return 'ok', 200


@dashboard.route('/dashboard/test-errors-status')
@login_required
def test_errors_status():
    """Проверява дали потребителят има поне 2 резултата за даден тест (за Errors бутон)"""
    test_id = request.args.get('test_id', type=int)
    if not test_id:
        return jsonify({'has_errors': False})
    count = TestResult.query.filter_by(
        user_id=session['user_id'],
        test_id=test_id
    ).filter(
        TestResult.test_type.in_(['test', 'mix'])
    ).count()
    return jsonify({'has_errors': count >= 2})


def record_monthly_snapshot():
    """Записва snapshot за текущия месец"""
    now = datetime.utcnow()
    year, month = now.year, now.month
    existing = MonthlySnapshot.query.filter_by(year=year, month=month).first()
    if existing:
        snap = existing
    else:
        snap = MonthlySnapshot(year=year, month=month)
        db.session.add(snap)
    
    snap.total_users  = User.query.filter_by(is_admin=False).count()
    snap.active_users = User.query.filter_by(is_admin=False, is_active=True).count()
    snap.passive_users = snap.total_users - snap.active_users
    snap.demo_users   = User.query.filter_by(is_admin=False, is_active=False).count()
    db.session.commit()
    return snap

@dashboard.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user and user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('user_dashboard'))
    return render_template('landing.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

@dashboard.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            # Block unverified users (only if API key is set)
            if BREVO_API_KEY and not user.is_admin and not user.email_verified:
                flash('Моля потвърди имейла си преди да влезеш.', 'error')
                return render_template('login.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['is_admin'] = user.is_admin
            redirect_url = url_for('admin_dashboard') if user.is_admin else url_for('user_dashboard')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'redirect': redirect_url})
            return redirect(redirect_url)
        flash('Грешен имейл или парола', 'error')
    return render_template('login.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

# Simple rate limiting store
_reg_attempts = {}

@dashboard.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Rate limiting disabled during testing
        ip = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1').split(',')[0].strip()
        now = datetime.utcnow()

        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        promo = request.form.get('promo_code', '').strip()

        # Basic validation
        if not email or not password:
            flash('Имейлът и паролата са задължителни.', 'error')
            return render_template('register.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)



        if len(password) < 6:
            flash('Паролата трябва да е поне 6 символа.', 'error')
            return render_template('register.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

        import re as _re
        if not (_re.search(r'[a-zA-Zа-яА-Я]', password) and _re.search(r'[0-9]', password)):
            flash('Паролата трябва да съдържа букви И цифри.', 'error')
            return render_template('register.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

        # Basic email format validation
        import re as _re
        if not _re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
            flash('Невалиден имейл адрес.', 'error')
            return render_template('register.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

        if User.query.filter_by(email=email).first():
            flash('Имейлът вече е регистриран. Влез в профила си.', 'error')
            return render_template('register.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

        # Create user
        name = request.form.get('name', '').strip() or email.split('@')[0]
        user = User(
            name=name,
            email=email,
            password=generate_password_hash(password),
            is_active=True,
            email_verified=False
        )
        db.session.add(user)

        # Apply promo code if provided
        if promo:
            promo_obj = PromoCode.query.filter_by(code=promo, is_active=True, is_used=False).first()
            if promo_obj:
                promo_obj.is_used = True
                promo_obj.used_by = email
                promo_obj.used_at = datetime.utcnow()
                promo_obj.is_active = False
                user.is_active = True
                db.session.commit()
                session['user_id'] = user.id
                # Известяване на admin
                try:
                    admin = User.query.filter_by(is_admin=True).first()
                    if admin and getattr(admin, 'notif_subscription', True) and BREVO_API_KEY:
                        send_email(admin.email, '🚢 Нов абонамент!',
                            f'Потребител {email} активира промокод {promo_obj.code}.')
                except:
                    pass
                flash('Акаунтът е създаден и промокодът е активиран!', 'success')
                return redirect(url_for('user_dashboard'))

        # Generate verification token
        import secrets
        token = secrets.token_urlsafe(32)
        user.verification_token = token
        db.session.commit()
        
        # Generate OTP
        import random
        otp = str(random.randint(100000, 999999))
        user.otp_code = otp
        user.otp_expires = datetime.utcnow() + __import__('datetime').timedelta(minutes=5)
        db.session.commit()
        
        # Send OTP email
        if BREVO_API_KEY:
            send_otp_async(email, otp)
            session['pending_verify_email'] = email
            return redirect(url_for('verify_otp'))
        else:
            user.email_verified = True
            db.session.commit()
            session['user_id'] = user.id
            flash('Добре дошъл!', 'success')
            session['user_id'] = user.id
            flash('Добре дошъл! Акаунтът ти е създаден.', 'success')
        return redirect(url_for('user_dashboard'))

    return render_template('register.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

@dashboard.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ============================================================
#  USER ROUTES
# ============================================================


@dashboard.route('/demo/test/<int:test_id>')
def demo_test(test_id):
    """Демо тест - без регистрация"""
    import random as rnd
    test = Test.query.get_or_404(test_id)
    if not test.is_demo:
        return redirect(url_for('dashboard.demo'))
    mode = request.args.get('mode', 'test')
    questions = test.get_questions()
    questions = inject_images(test_id, questions)

    if mode == 'simulator':
        rnd.shuffle(questions)
        questions = questions[:45]
        return render_template('user/simulator.html', test=test, questions=questions, time_limit=60, is_demo=True)
    elif mode == 'mix':
        rnd.shuffle(questions)
        return render_template('user/test.html', test=test, questions=questions, shuffle=True, test_type='mix', is_demo=True, is_free_plan=True)
    elif mode == 'mistakes':
        # За демо - микс (няма история на грешките)
        rnd.shuffle(questions)
        return render_template('user/test.html', test=test, questions=questions, shuffle=True, test_type='mistakes', is_demo=True, is_free_plan=True)
    else:
        return render_template('user/test.html', test=test, questions=questions, shuffle=False, test_type='test', is_demo=True, is_free_plan=True)

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
