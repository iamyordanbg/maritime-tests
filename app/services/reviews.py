"""
app/services/reviews.py
========================
Тригер логика за 'остави отзив' попъпа - показва се, ако потребителят е
близо до изтичане на активен план (Basic/Plus/Gold/Custom), и никога не е
оставял отзив досега (once-per-account).
"""
from datetime import datetime, timedelta
from app.models.review import Review

DAYS_BEFORE_EXPIRY = 2
TESTS_REMAINING_THRESHOLD = 5


def count_pending_reviews():
    """Колко отзива чакат одобрение (за индикацията в страничното меню на админа)."""
    return Review.query.filter_by(status='pending').count()


REPLY_MAX_LENGTH = 500


class ReplyError(ValueError):
    """Невалиден отговор (ревюто не е одобрено, прекалено дълъг текст)."""


def set_admin_reply(review, text):
    """Записва (или изтрива при празен текст) единствения отговор на сайта.
    Само одобрени отзиви могат да получат отговор. Не прави commit."""
    text = (text or '').strip()
    if not text:
        review.admin_reply = None
        review.admin_reply_at = None
        return
    if review.status != 'approved':
        raise ReplyError('Only approved reviews can be replied to.')
    if len(text) > REPLY_MAX_LENGTH:
        raise ReplyError(f'Reply is too long (max {REPLY_MAX_LENGTH} characters).')
    review.admin_reply = text
    review.admin_reply_at = datetime.utcnow()


def account_display_name(user):
    """Имената на потребителя както ги е въвел в акаунта си: име + фамилия, иначе
    user.name. Празен низ, ако няма нищо (тогава отзивът с имената не е възможен)."""
    full = ' '.join(p.strip() for p in (user.firstname, user.lastname) if p and p.strip())
    return full or (user.name or '').strip()


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
    for grant in user.active_promo_grants():
        if _grant_is_near_expiry(grant, now):
            return True
    return False
