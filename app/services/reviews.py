"""
app/services/reviews.py
========================
Тригер логика за 'остави отзив' попъпа - показва се, ако потребителят е
близо до изтичане на активен план (Basic/Plus/Gold), и никога не е
оставял отзив досега (once-per-account).
"""
from datetime import datetime, timedelta
from app.models.review import Review

DAYS_BEFORE_EXPIRY = 2
TESTS_REMAINING_THRESHOLD = 5


def _grant_is_near_expiry(grant, now):
    """Общ helper за PlanGrant/GoldGrant - и двата модела имат
    quota/tests_used/expires_at със същата семантика."""
    if not grant.expires_at or grant.expires_at <= now:
        return False  # вече изтекъл, не "близо до"
    days_left = (grant.expires_at - now).total_seconds() / 86400
    if days_left <= DAYS_BEFORE_EXPIRY:
        return True
    tests_remaining = (grant.quota or 0) - (grant.tests_used or 0)
    if tests_remaining < TESTS_REMAINING_THRESHOLD:
        return True
    return False


def should_prompt_review(user):
    """Дали да покажем 'Остави отзив' попъпа на този потребител точно сега."""
    if user.is_admin:
        return False

    # Once-per-account - ако вече има запис (независимо status), никога повече
    already_asked = Review.query.filter_by(user_id=user.id).first()
    if already_asked:
        return False

    now = datetime.utcnow()
    for grant in user.active_plan_grants():
        if _grant_is_near_expiry(grant, now):
            return True
    for grant in user.active_gold_grants():
        if _grant_is_near_expiry(grant, now):
            return True
    return False
