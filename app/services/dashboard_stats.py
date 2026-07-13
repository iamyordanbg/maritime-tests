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
    plan_grant_awaiting_test = any(g.library_test_id is None for g in active_plan_grants_qs)

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
    if user.plan == 'gold':
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
