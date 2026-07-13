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


@dashboard.route('/api/debug-my-grants')
@login_required
def api_debug_my_grants():
    """ВРЕМЕНЕН diagnostic endpoint - ще се изтрие след разследването.
    Показва суровите grant данни на текущия потребител, за да видим точно
    какво е записано в базата, вместо да гадаем."""
    from app.models.gold_grant import GoldGrant
    from app.models.promo_grant import PromoGrant
    from app.models.plan_grant import PlanGrant
    now = datetime.utcnow()
    user_id = session['user_id']

    def fmt(g, extra=None):
        d = {
            'id': g.id,
            'library_test_id': getattr(g, 'library_test_id', None),
            'test_ids': getattr(g, 'test_ids', None),
            'activated_at': g.activated_at.isoformat() if g.activated_at else None,
            'expires_at': g.expires_at.isoformat() if g.expires_at else None,
            'is_active_now': g.expires_at > now if g.expires_at else None,
            'quota': getattr(g, 'quota', None),
        }
        if extra:
            d.update(extra)
        return d

    plan_grants = PlanGrant.query.filter_by(user_id=user_id).all()
    gold_grants = GoldGrant.query.filter_by(user_id=user_id).all()
    promo_grants = PromoGrant.query.filter_by(user_id=user_id).all()

    return jsonify({
        'now_utc': now.isoformat(),
        'plan_grants': [fmt(g, {'plan': g.plan}) for g in plan_grants],
        'gold_grants': [fmt(g) for g in gold_grants],
        'promo_grants': [fmt(g, {'promo_code': g.promo_code}) for g in promo_grants],
    })


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
    free_c = {}

    all_results = TestResult.query.filter_by(user_id=user.id).order_by(TestResult.taken_at.desc()).all()
    results = []
    for r in all_results:
        status, grant = find_result_grant(r, now, gold_c, plan_c, promo_c, free_c)
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


# ── support routes ──


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


# ── Support Center (Tickets) ──

@dashboard.route('/support/tickets')
@login_required
def get_tickets():
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
    ticket = Ticket.query.filter_by(id=ticket_id, user_id=session['user_id']).first_or_404()
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
    user_id = session['user_id']
    count = (TicketMessage.query
             .join(Ticket, TicketMessage.ticket_id == Ticket.id)
             .filter(Ticket.user_id == user_id,
                     TicketMessage.sender == 'admin',
                     TicketMessage.is_read == False)
             .count())
    return jsonify({'count': count})



# ── user_settings routes ──


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

    plan_grant_codes = {g.id: get_or_create_subscription_code('plan', g.id) for g in user.active_plan_grants()}
    gold_grant_codes = {g.id: (g.promo_code or get_or_create_subscription_code('gold', g.id)) for g in user.active_gold_grants()}

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


