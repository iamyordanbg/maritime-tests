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


def result_visible(r, is_active, grant, now):
    """
    Дали даден резултат трябва да се показва в историята в момента.
    - Активен grant → винаги видим.
    - Изтекъл grant → видим само до HISTORY_GRACE_DAYS след expires_at.
    - Няма никакъв grant (Gold/Plan) — типично free-план резултат:
        - Ако е СИМУЛАТОР на free план → видим само HISTORY_GRACE_DAYS
          дни от taken_at (тук няма expires_at, отброяваме direct от
          момента на решаването, тъй като free симулаторът няма grant).
        - Друг тип резултат без grant (стари/несигурни данни) → не пипаме,
          винаги видим.
    """
    if is_active:
        return True
    if grant:
        return (now - grant.expires_at).days < HISTORY_GRACE_DAYS

    user = r.user
    if user and user.plan == 'free' and r.test_type == 'simulator':
        return (now - r.taken_at).days < HISTORY_GRACE_DAYS

    return True


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
        if is_active:
            continue
        if grant:
            if (now - grant.expires_at).days >= grace_days:
                db.session.delete(r)
                deleted += 1
            continue
        # Няма grant — free-план симулатор резултат, трие се grace_days
        # след taken_at (директно, тъй като няма grant expires_at).
        user = r.user
        if user and user.plan == 'free' and r.test_type == 'simulator':
            if (now - r.taken_at).days >= grace_days:
                db.session.delete(r)
                deleted += 1

    if deleted:
        db.session.commit()
    return deleted


def find_active_grant_for_test(user, test_id, now=None):
    """
    Намира АКТИВНИЯ Gold/PlanGrant, който в момента покрива test_id за дадения
    потребител (за разлика от find_result_grant, който гледа кой grant е
    покривал резултат В МИНАЛОТО по taken_at). Ползва се за проверка дали
    потребителят все още има оставащ лимит ПРЕДИ да зареди/реши тест.
    Връща grant обект или None (напр. free план, или тест извън всеки grant).
    """
    from datetime import datetime
    now = now or datetime.utcnow()

    if user.plan == 'gold':
        from app.models.gold_grant import GoldGrant
        grants = (GoldGrant.query
                  .filter(GoldGrant.user_id == user.id, GoldGrant.expires_at > now)
                  .all())
        return next((g for g in grants if test_id in g.test_id_list()), None)
    else:
        from app.models.plan_grant import PlanGrant
        grants = (PlanGrant.query
                  .filter(PlanGrant.user_id == user.id, PlanGrant.expires_at > now)
                  .all())
        return next((g for g in grants if g.library_test_id == test_id), None)


def grant_quota_exceeded(grant):
    """Дали дадения grant е изчерпал напълно лимита си от тестове."""
    if not grant:
        return False
    return (grant.tests_used or 0) >= grant.quota
