"""
app/services/dashboard_stats.py
Business логика за user dashboard изгледа — извлечена от
app/routes/dashboard.py::user_dashboard (Правило 4: NEXT_SESSION_PROMPT.md).

compute_dashboard_view_data() връща ИЛИ {'redirect': True} (когато
потребителят трябва да бъде пренасочен, напр. няма избран тест), ИЛИ
пълния dict с template context за render_template('user/dashboard.html').
Route-ът решава какво да направи с резултата (redirect vs render) - чисто
HTTP решение, business логиката остава pure/тестваема тук.
"""
import math
from datetime import datetime
from app.extensions import db
from app.models.test import Test
from app.models.result import TestResult
from app.utils.codes import get_or_create_subscription_code, free_code


def compute_dashboard_view_data(user):
    from app.models.gold_grant import GoldGrant
    from app.models.promo_grant import PromoGrant
    from app.models.plan_grant import PlanGrant
    from app.utils.grant_cache import fetch_all_grants
    from app.utils.grants import grant_plan_label

    _stats_row = (db.session.query(
                    db.func.count(TestResult.id),
                    db.func.sum(db.case((TestResult.passed == True, 1), else_=0))
                  ).filter(TestResult.user_id == user.id).first())
    total_tests = _stats_row[0] or 0
    passed_tests = _stats_row[1] or 0

    _all_gold_grants, _all_promo_grants, _all_plan_grants = fetch_all_grants(user.id)
    _now = datetime.utcnow()
    user._cached_gold_grants = [g for g in _all_gold_grants if g.expires_at > _now]
    user._cached_promo_grants = [g for g in _all_promo_grants if g.expires_at > _now]
    user._cached_plan_grants = [g for g in _all_plan_grants if g.expires_at > _now]

    results = []
    result_code_by_id = {}

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

    now = datetime.utcnow()
    plan_days_left = user.effective_days_left()

    library_state = {
        'is_premium': user.has_active_plan(),
        'selected_test_id': user.library_test_id,
        'days_left': user.library_days_left(),
        'window_active': user.library_window_active(),
        'simulator_available_today': user.library_simulator_available(),
    }

    active_plan_grants_qs = sorted([g for g in _all_plan_grants if g.expires_at > _now], key=lambda g: g.activated_at)
    # БЪГ ФИКС: преди тук беше any(...) - БЛОКИРАШЕ достъп до dashboard-а
    # дори след като потребителят вече е избрал тест, ако имаше ДРУГ
    # (напр. стар/дублиран от тестване) активен PlanGrant, който все още
    # няма избран тест. Резултат: потребител с 2+ активни Plus/Basic
    # grant-а избира тест за единия -> dashboard вижда другия все още
    # празен -> redirect обратно към library -> library показва 'вече
    # активен план, избери тест' popup-а отново -> безкраен цикъл, дори
    # реалният избор вече е записан успешно. Сега блокираме само ако
    # ВСИЧКИ активни grant-ове нямат избран тест (истински 'изобщо няма
    # първи избор' случай) - конкретен grant с все още неизбран тест вече
    # се показва като non-blocking 'awaiting_selection' покана в library_state.
    plan_grant_awaiting_test = all(g.library_test_id is None for g in active_plan_grants_qs)

    has_active_gold = any(g.expires_at > _now for g in _all_gold_grants) or any(g.expires_at > _now for g in _all_promo_grants)
    if (not has_active_gold
            and not active_plan_grants_qs
            and not user.library_window_active()
            and user.library_test_id is None):
        return {'redirect': True, 'refreshed': refreshed}
    if active_plan_grants_qs and plan_grant_awaiting_test:
        return {'redirect': True, 'refreshed': refreshed}

    if user.library_window_active() and user.library_test_id:
        tests = [t for t in all_tests if t.id == user.library_test_id]
    elif user.is_active and user.library_test_id:
        tests = [t for t in all_tests if t.id == user.library_test_id]
    else:
        tests = []

    gold_cards = []
    test_grant_info = {}
    # БЪГ ФИКС: преди тук беше 'if user.plan == 'gold':' - остаряло legacy
    # поле, което activate_plan() ПРЕЗАПИСВА при всяка нова Basic/Plus
    # активация (сочи към плана с НАЙ-КЪСНО изтичане, не 'дали има активен
    # Gold/Custom grant'). Потребител с активен Custom Promo grant, който
    # ПОСЛЕ активира Basic/Plus - user.plan вече е 'basic'/'plus', не
    # 'gold' - целият Gold/Custom card блок се пропускаше ИЗЦЯЛО на
    # dashboard-а, независимо че PromoGrant/GoldGrant записът е напълно
    # валиден и активен (виждан коректно в Billing/Usage, но не и тук).
    # has_active_gold вече е изчислена по-горе от РЕАЛНИТЕ активни
    # GoldGrant/PromoGrant записи - същата проверка, ползвана за redirect
    # логиката по-горе - сега display логиката тук съвпада с нея.
    if has_active_gold:
        active_grants = sorted(
            [g for g in _all_gold_grants if g.expires_at > _now] + [g for g in _all_promo_grants if g.expires_at > _now],
            key=lambda g: g.activated_at
        )
        gold_tests_union = []
        for g in active_grants:
            g_test_ids = g.test_id_list()
            g_tests = [t for t in all_tests if t.id in g_test_ids]
            g_days_left = max(0, math.ceil((g.expires_at - now).total_seconds() / 86400))
            g_used_real = (TestResult.query
                           .filter(TestResult.user_id == user.id,
                                   TestResult.test_id.in_(g_test_ids),
                                   TestResult.taken_at >= g.activated_at)
                           .count()) if g_test_ids else 0
            g_remaining = max(0, g.quota - g_used_real)
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
            tests = gold_tests_union

    plan_cards = []
    plan_tests_union = []
    for g in active_plan_grants_qs:
        if not g.library_test_id:
            continue
        g_test = next((t for t in all_tests if t.id == g.library_test_id), None)
        if not g_test:
            continue
        g_days_left = max(0, math.ceil((g.expires_at - now).total_seconds() / 86400))
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
        tests = (tests or []) + [t for t in plan_tests_union if t not in tests]

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

    all_active_cards = gold_cards + plan_cards
    if all_active_cards:
        tests_quota = sum(c['tests_quota'] for c in all_active_cards)
        tests_remaining = sum(c['tests_remaining'] for c in all_active_cards)
        tests_used = tests_quota - tests_remaining
    else:
        tests_quota = 0
        tests_used = 0
        tests_remaining = 0

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

    plan_grant_codes = {g.id: get_or_create_subscription_code('plan', g.id) for g in user.active_plan_grants()}
    gold_grant_codes = {g.id: get_or_create_subscription_code('gold', g.id) for g in user.active_gold_grants()}

    return {
        'redirect': False, 'refreshed': refreshed,
        'user': user, 'results': results,
        'total_tests': total_tests, 'passed_tests': passed_tests, 'tests': tests,
        'library_state': library_state,
        'plan_days_left': plan_days_left, 'mistakes_unlocked_by_test': mistakes_unlocked_by_test,
        'tests_quota': tests_quota, 'tests_used': tests_used, 'tests_remaining': tests_remaining,
        'gold_cards': gold_cards, 'plan_cards': plan_cards, 'test_grant_info': test_grant_info,
        'all_cards': gold_cards + plan_cards + free_cards,
        'result_code_by_id': result_code_by_id,
        'plan_grant_codes': plan_grant_codes, 'gold_grant_codes': gold_grant_codes,
    }


def build_library_view_data(user, gold_flow, gold_first_test_id, gold_first_test_title):
    """Business логика за library() route — извлечена от
    app/routes/dashboard.py (Правило 4). Session четенето (gold_flow) става
    в route-а, тук е чиста бизнес логика над вече прочетените стойности.
    Връща (tests_data, library_state, gold_activation, clear_gold_session:bool)."""
    from app.models.plan_grant import PlanGrant
    from app.models.gold_grant import GoldGrant
    from app.models.promo_grant import PromoGrant
    from app.utils.grants import grant_real_used
    from app.routes.activate import _get_valid_promo

    gold_activation = None
    clear_gold_session = False
    if gold_flow and gold_flow.get('code'):
        promo = _get_valid_promo(gold_flow['code'])
        if promo:
            gold_activation = {
                'code': promo.code,
                'first_test_id': gold_first_test_id,
                'first_test_title': gold_first_test_title,
            }
        else:
            clear_gold_session = True

    # Ако 7-дневният прозорец е изтекъл — рестартирай го автоматично със същия тест
    refreshed = user.library_refresh_if_expired()
    if refreshed:
        db.session.commit()

    all_tests_raw = Test.query.options(db.defer(Test.questions_json)).order_by(Test.category, Test.level).all()

    now = datetime.utcnow()
    active_grants = (PlanGrant.query
                      .filter(PlanGrant.user_id == user.id, PlanGrant.expires_at > now)
                      .order_by(PlanGrant.activated_at.desc())
                      .all())
    # БЪГ ФИКС: is_premium_plan/selected тестове тук се смятаха САМО от
    # PlanGrant (Basic/Plus) - GoldGrant и PromoGrant (Custom) изобщо не
    # се проверяваха. Резултат: Gold/Custom клиент падаше в legacy Free
    # клона по-долу, а вече избраните му тестове (записани в test_ids на
    # неговия GoldGrant/PromoGrant при активацията) никога не се показваха
    # като "избрани" в библиотеката - изглеждаше сякаш изборът не е минал.
    # compute_dashboard_view_data() по-горе вече прави тази проверка
    # коректно за 3-те типа - тук просто липсваше същата логика.
    active_gold_grants = (GoldGrant.query
                           .filter(GoldGrant.user_id == user.id, GoldGrant.expires_at > now)
                           .all())
    active_promo_grants = (PromoGrant.query
                            .filter(PromoGrant.user_id == user.id, PromoGrant.expires_at > now)
                            .all())
    is_premium_plan = user.has_active_plan() and bool(active_grants or active_gold_grants or active_promo_grants)

    from app.routes.dashboard import LEVEL_MAP
    tests_data = []
    for t in all_tests_raw:
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
        # Gold/Custom не преизбират тест по-късно - test_ids се фиксира
        # ВЕДНЪЖ при активацията (виж library_select() в dashboard.py).
        # Затова тук само добавяме вече присвоените им тестове към списъка
        # с "избрани", без да пипаме waiting_grant логиката по-долу (тя е
        # само за PlanGrant - единствения тип с преизбираем 1 тест).
        for g in active_gold_grants + active_promo_grants:
            already_selected_ids.extend(g.test_id_list())
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
            'needs_first_selection': all(g.library_test_id is None for g in active_grants),
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

    return tests_data, library_state, gold_activation, clear_gold_session
