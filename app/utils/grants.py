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


# Колко дни след изтичане на конкретния grant резултатът остава видим в
# историята на потребителя, преди да бъде окончателно скрит/изтрит.
HISTORY_GRACE_DAYS = 30


def result_visible(is_active, grant, now):
    """
    Дали даден резултат трябва да се показва в историята в момента.
    - Активен grant, или няма намерен grant изобщо (несигурни/стари данни,
      не пипаме) → винаги видим.
    - Изтекъл grant → видим само до HISTORY_GRACE_DAYS след expires_at.
    """
    if is_active or not grant:
        return True
    return (now - grant.expires_at).days < HISTORY_GRACE_DAYS


def auto_delete_expired_results(grace_days=HISTORY_GRACE_DAYS):
    """
    Автоматично трие резултати, чийто конкретен grant е изтекъл преди
    ПОВЕЧЕ ОТ grace_days дни. Вика се опортюнистично при зареждане на
    admin dashboard-а И на потребителска история/dashboard (няма отделен
    cron в тази среда).
    """
    from datetime import datetime, timedelta
    from app.extensions import db
    from app.models.result import TestResult

    now = datetime.utcnow()
    cutoff_candidates = now - timedelta(days=grace_days)
    # Само резултати, взети достатъчно отдавна, за да е изобщо възможно
    # техният grace период вече да е минал — пести ненужна работа.
    candidates = TestResult.query.filter(TestResult.taken_at < cutoff_candidates).all()

    gold_cache, plan_cache = {}, {}
    deleted = 0
    for r in candidates:
        is_active, grant = find_result_grant(r, now, gold_cache, plan_cache)
        if is_active or not grant:
            continue  # активен, или няма намерен grant — не пипаме несигурни данни
        if (now - grant.expires_at).days >= grace_days:
            db.session.delete(r)
            deleted += 1

    if deleted:
        db.session.commit()
    return deleted
