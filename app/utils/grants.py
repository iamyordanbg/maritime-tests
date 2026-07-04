"""
app/utils/grants.py
=====================
Споделена логика за намиране на КОНКРЕТНИЯ grant (Gold или Basic/Plus),
покривал точно даден тест по времето на решаването му. Ползва се и от
admin.py (Last Results таблица), и от dashboard.py (собствена история
на потребителя) — за да няма дублиране и разминаване на логиката.
"""


def find_result_grant(r, now, gold_cache=None, plan_cache=None):
    """
    Връща (is_active: bool, grant или None).
    gold_cache/plan_cache — по избор, {user_id: [grants]} за преизползване
    между много резултати на един и същ потребител (избягва повторни заявки).
    """
    from app.models.gold_grant import GoldGrant
    from app.models.plan_grant import PlanGrant

    if gold_cache is not None:
        if r.user_id not in gold_cache:
            gold_cache[r.user_id] = GoldGrant.query.filter_by(user_id=r.user_id).all()
        gold_grants = gold_cache[r.user_id]
    else:
        gold_grants = GoldGrant.query.filter_by(user_id=r.user_id).all()

    for g in gold_grants:
        if r.test_id in g.test_id_list() and g.activated_at and g.activated_at <= r.taken_at:
            return g.expires_at > now, g

    if plan_cache is not None:
        if r.user_id not in plan_cache:
            plan_cache[r.user_id] = PlanGrant.query.filter_by(user_id=r.user_id).all()
        plan_grants = plan_cache[r.user_id]
    else:
        plan_grants = PlanGrant.query.filter_by(user_id=r.user_id, library_test_id=r.test_id).all()

    for g in plan_grants:
        if g.library_test_id == r.test_id and g.activated_at and g.activated_at <= r.taken_at:
            return g.expires_at > now, g

    return False, None
