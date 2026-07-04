"""
app/utils/grant_cache.py
==========================
Лек in-memory кеш (TTL) за GoldGrant/PlanGrant по потребител. Не изисква
Redis/Memcached — просто пести повторно теглене, ако same потребител прави
няколко бързи заявки (напр. dashboard + async history) в рамките на секунди.

ВНИМАНИЕ: работи само в РАМКИТЕ на един worker процес (не се споделя между
workers/машини) — достатъчно за целта (намаляване на дублирано теглене в
кратък прозорец), не е заместител на истински distributed cache.
"""

import time
import threading

_CACHE = {}
_LOCK = threading.Lock()
_TTL_SECONDS = 15  # достатъчно кратко, за да не показва остарели данни за дълго


def get_cached_grants(user_id):
    """Връща (gold_grants, plan_grants) от кеша, ако е свеж (< TTL), иначе None."""
    with _LOCK:
        entry = _CACHE.get(user_id)
        if entry and (time.time() - entry[0]) < _TTL_SECONDS:
            return entry[1], entry[2]
    return None


def set_cached_grants(user_id, gold_grants, plan_grants):
    with _LOCK:
        _CACHE[user_id] = (time.time(), gold_grants, plan_grants)


def invalidate_cached_grants(user_id):
    """Вика се при активиране на нов план/код, за да не показва остарели данни."""
    with _LOCK:
        _CACHE.pop(user_id, None)


def fetch_all_grants(user_id):
    """
    Връща (gold_grants, plan_grants) за потребителя — от кеша, ако е свеж,
    иначе от базата (и попълва кеша за следващата бърза заявка).
    """
    cached = get_cached_grants(user_id)
    if cached is not None:
        return cached

    from app.models.gold_grant import GoldGrant
    from app.models.plan_grant import PlanGrant
    gold_grants = GoldGrant.query.filter_by(user_id=user_id).all()
    plan_grants = PlanGrant.query.filter_by(user_id=user_id).all()
    set_cached_grants(user_id, gold_grants, plan_grants)
    return gold_grants, plan_grants
