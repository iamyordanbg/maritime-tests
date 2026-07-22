import os
import json
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from app.extensions import db
from app.models.user import User
from app.models.test import Test
from app.models.result import TestResult
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
    free_c = {}
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
        status, grant = find_result_grant(r, now, gold_c, plan_c, promo_c, free_c)
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
    from app.services.dashboard_stats import compute_dashboard_view_data
    user = User.query.get(session['user_id'])
    if user and user.is_admin:
        return redirect(url_for('admin.admin_dashboard'))
    data = compute_dashboard_view_data(user)
    if data['refreshed']:
        session['library_just_refreshed'] = True
    # Toast се показва само веднъж — при първото зареждане след refresh
    show_refresh_toast = session.pop('library_just_refreshed', False)
    if data['redirect']:
        return redirect(url_for('dashboard.library'))
    del data['redirect']
    del data['refreshed']
    data['library_refreshed'] = show_refresh_toast
    return render_template('user/dashboard.html', **data)

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
    from app.services.dashboard_stats import build_library_view_data
    from app.routes.activate import PROMO_SESSION_KEY
    user = User.query.get(session['user_id'])
    if user.is_admin:
        return redirect(url_for('admin.admin_dashboard'))

    gold_flow = session.get(PROMO_SESSION_KEY)
    gold_first_test_id = session.get('gold_first_test_id')
    gold_first_test_title = session.get('gold_first_test_title')

    tests_data, library_state, gold_activation, clear_gold_session = build_library_view_data(
        user, gold_flow, gold_first_test_id, gold_first_test_title)

    if clear_gold_session:
        session.pop(PROMO_SESSION_KEY, None)
        session.pop('gold_first_test_id', None)
        session.pop('gold_first_test_title', None)

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
    #
    # БЪГ ФИКС: преди тук грантовете се подреждаха по activated_at ASC
    # (най-стария първи) - потребител, който ТОКУ-ЩО е купил нов план
    # (напр. Plus, докато вече има стар активен Basic), избираше тест и
    # очакваше той да отиде за НОВИЯ план - но алгоритъмът намираше
    # по-стария Basic grant първи (ако той ПО СЛУЧАЙНОСТ пак отговаряше
    # на 'waiting' условието), и новият Plus grant оставаше БЕЗ избран
    # тест изобщо (виждано реално - Purchase History картата за Plus
    # показваше платен план, но никакъв 'loaded_test' ред). Сега най-
    # новоактивираният grant се проверява ПЪРВИ - логично, защото
    # потребителят, който току-що е платил, най-вероятно избира тест
    # именно ЗА този нов план.
    from app.models.plan_grant import PlanGrant
    from app.utils.grants import grant_real_used
    now = datetime.utcnow()
    candidate_grants = (PlanGrant.query
                        .filter(PlanGrant.user_id == user.id, PlanGrant.expires_at > now)
                        .order_by(PlanGrant.activated_at.desc())
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
        # БЪГ ФИКС: липсваше invalidate на 15-сек grant_cache (виж
        # app/utils/grant_cache.py) - dashboard-ът четеше от кеша, който
        # продължаваше да връща СТАРИЯ (без избран тест) grant запис до
        # 15 секунди, дори след успешен избор. Потребител, избрал тест
        # веднага след покупка/redirect към dashboard, виждаше плана си
        # без прикачения тест - изглеждаше сякаш изборът не е сработил.
        from app.utils.grant_cache import invalidate_cached_grants
        invalidate_cached_grants(user.id)
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
    free_c = {}

    all_results = TestResult.query.filter_by(user_id=user.id).order_by(TestResult.taken_at.desc()).all()
    results = []
    for r in all_results:
        status, grant = find_result_grant(r, now, gold_c, plan_c, promo_c, free_c)
        if result_visible(r, status, grant, now):
            results.append(r)

    return render_template('user/history.html', user=user, results=results)

# ============================================================
#  TEST-TAKING ROUTES (Test/Mix/Mistakes/Simulator/Demo/Images) → app/routes/test_taking.py
# ============================================================

# ============================================================
#  SUPPORT CENTER ROUTES → app/routes/support.py
# ============================================================

# ============================================================
#  ADMIN ROUTES
# ============================================================


# User API routes (preferences, usage, billing, ads) → app/routes/user_settings.py


# Admin routes → app/routes/admin.py


@dashboard.route('/library/search')
@login_required
def library_search():
    from flask import jsonify
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    query = Test.query.filter(Test.title.ilike(f'%{q}%'))
    user = User.query.get(session['user_id'])
    if user and user.has_active_plan():
        # Платен потребител вече вижда цялата истинска библиотека - демо
        # тестовете (upsell преглед за неплатени) не са му нужни в търсенето
        query = query.filter(Test.is_demo == False)
    results = query.limit(20).all()
    return jsonify([{
        'id': t.id,
        'title': t.title,
        'category': t.category,
        'question_count': t.question_count,
        'is_demo': t.is_demo
    } for t in results])


# ── support routes ──


@dashboard.route('/api/test-preferences', methods=['GET', 'POST'])
@login_required
def api_test_preferences():
    """
    Настройки за четене на тестовете (font size/theme/family) - от
    менюто с 3-те чертички в хедъра на всеки тест/симулатор. Отделни
    слайдери (0-10) и шрифтове за ВЪПРОСА и за ОТГОВОРИТЕ поотделно.
    Записват се веднъж в акаунта, важат за ВСИЧКИ функции за решаване на
    тестове.
    """
    user = User.query.get(session['user_id'])
    if request.method == 'GET':
        return jsonify({
            'q_font_size': user.pref_q_font_size if user.pref_q_font_size is not None else 5,
            'a_font_size': user.pref_a_font_size if user.pref_a_font_size is not None else 5,
            'highlight_intensity': user.pref_highlight_intensity if user.pref_highlight_intensity is not None else 5,
            'theme': user.pref_theme or 'dark',
            'q_font_family': user.pref_q_font_family or 'default',
            'a_font_family': user.pref_a_font_family or 'default',
            'q_bold': user.pref_q_bold if user.pref_q_bold is not None else True,
            'a_bold': user.pref_a_bold if user.pref_a_bold is not None else False,
        })

    data = request.get_json(silent=True) or {}

    # Бутонът 'Reset to Default' в менюто - връща ВСИЧКИ настройки на
    # стойностите по подразбиране. Стойностите по подразбиране могат да
    # се сменят по-късно от потребителя (засега: средата на всеки слайдер,
    # тъмна тема, стандартен шрифт, удебелен въпрос/неудебелени отговори).
    if data.get('reset'):
        user.pref_q_font_size = 5
        user.pref_a_font_size = 5
        user.pref_highlight_intensity = 5
        user.pref_theme = 'dark'
        user.pref_q_font_family = 'default'
        user.pref_a_font_family = 'default'
        user.pref_q_bold = True
        user.pref_a_bold = False
        db.session.commit()
        return jsonify({'success': True, 'reset': True})

    if 'q_font_size' in data:
        try:
            v = int(data['q_font_size'])
            if 0 <= v <= 10:
                user.pref_q_font_size = v
        except (TypeError, ValueError):
            pass
    if 'a_font_size' in data:
        try:
            v = int(data['a_font_size'])
            if 0 <= v <= 10:
                user.pref_a_font_size = v
        except (TypeError, ValueError):
            pass
    if 'highlight_intensity' in data:
        try:
            v = int(data['highlight_intensity'])
            if 0 <= v <= 10:
                user.pref_highlight_intensity = v
        except (TypeError, ValueError):
            pass
    if 'theme' in data and data['theme'] in ('dark', 'light', 'sepia', 'ink'):
        user.pref_theme = data['theme']
    if 'q_font_family' in data and data['q_font_family'] in ('default', 'georgia', 'times', 'verdana', 'arial', 'roboto', 'opensans', 'montserrat', 'poppins', 'lato', 'nunito', 'worksans', 'raleway', 'sourcesans', 'notosans', 'merriweather', 'playfair', 'ptserif', 'oswald', 'rubik', 'ubuntu'):
        user.pref_q_font_family = data['q_font_family']
    if 'a_font_family' in data and data['a_font_family'] in ('default', 'georgia', 'times', 'verdana', 'arial', 'roboto', 'opensans', 'montserrat', 'poppins', 'lato', 'nunito', 'worksans', 'raleway', 'sourcesans', 'notosans', 'merriweather', 'playfair', 'ptserif', 'oswald', 'rubik', 'ubuntu'):
        user.pref_a_font_family = data['a_font_family']
    if 'q_bold' in data:
        user.pref_q_bold = bool(data['q_bold'])
    if 'a_bold' in data:
        user.pref_a_bold = bool(data['a_bold'])
    db.session.commit()
    return jsonify({'success': True})

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
    from app.services.usage import build_usage_cards
    user = User.query.get(session['user_id'])
    return jsonify({'cards': build_usage_cards(user)})


@dashboard.route('/api/my-billing')
@login_required
def api_my_billing():
    from app.services.usage import build_billing_data
    user = User.query.get(session['user_id'])
    payments, activated_codes = build_billing_data(user)
    return jsonify({'payments': payments, 'activated_codes': activated_codes})


