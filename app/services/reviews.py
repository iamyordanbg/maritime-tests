"""
app/services/reviews.py
========================
Тригер логика за 'остави отзив' попъпа - показва се, ако потребителят е
близо до изтичане на активен план (Basic/Plus/Gold/Custom), и никога не е
оставял отзив досега (once-per-account).
"""
from datetime import datetime, timedelta, date as date_cls
from app.extensions import db
from app.models.review import Review

DAYS_BEFORE_EXPIRY = 2
TESTS_REMAINING_THRESHOLD = 5


def count_pending_reviews():
    """Колко отзива чакат одобрение (за индикацията в страничното меню на админа)."""
    return Review.query.filter_by(status='pending').count()


REPLY_MAX_LENGTH = 500
TEXT_MAX_LENGTH = 1000
NAME_MAX_LENGTH = 150
ROLE_MAX_LENGTH = 150


class ReviewInputError(ValueError):
    """Невалидни данни при ръчно добавяне/промяна на отзив от админа."""


class ReplyError(ReviewInputError):
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


def parse_review_date(value):
    """'YYYY-MM-DD' -> date. Грешка при невалидна стойност или дата в бъдещето."""
    try:
        d = date_cls.fromisoformat((value or '').strip())
    except ValueError:
        raise ReviewInputError('Enter a valid date.')
    if d > datetime.utcnow().date():
        raise ReviewInputError('The date cannot be in the future.')
    return d


def set_review_date(review, value):
    """Сменя датата на отзива (часът от деня се запазва). Не прави commit."""
    d = parse_review_date(value)
    review.created_at = datetime.combine(d, (review.created_at or datetime.utcnow()).time())


def clean_review_fields(data, named):
    """Проверява и почиства текст, звезди, име и роля (общо за добавяне и редакция).
    Връща dict; ReviewInputError при невалидни данни."""
    text = (data.get('text') or '').strip()
    if not text:
        raise ReviewInputError('Write the review text.')
    if len(text) > TEXT_MAX_LENGTH:
        raise ReviewInputError(f'Review is too long (max {TEXT_MAX_LENGTH} characters).')
    try:
        stars = int(data.get('stars'))
    except (TypeError, ValueError):
        stars = 0
    if not 1 <= stars <= 5:
        raise ReviewInputError('Choose a rating from 1 to 5 stars.')
    name = (data.get('name') or '').strip()[:NAME_MAX_LENGTH]
    if named and not name:
        raise ReviewInputError('Enter the reviewer name or choose anonymous.')
    role = (data.get('role') or '').strip()[:ROLE_MAX_LENGTH]
    return {'text': text, 'stars': stars, 'name': name, 'role': role or None}


def create_admin_review(admin_user, data, photo_url=None):
    """Ръчно добавен от админа отзив - веднага одобрен. 'named' -> показва се с въведеното
    име (инициали като в акаунт), иначе е анонимен (генерирано име и морски аватар).
    Принадлежи на админския акаунт. photo_url - снимка на автора (само при отзив с име,
    показва се на мястото на аватара). Връща Review (commit е направен)."""
    named = data.get('visibility') == 'account'
    f = clean_review_fields(data, named)
    review = Review(
        user_id=admin_user.id, stars=f['stars'], text=f['text'],
        visibility='account' if named else 'anonymous',
        display_name=f['name'] if named else 'Anonymous Sailor',
        display_picture_url=photo_url if named else None,
        role=f['role'], status='approved',
    )
    set_review_date(review, data.get('date') or datetime.utcnow().date().isoformat())
    set_admin_reply(review, data.get('reply'))
    db.session.add(review)
    db.session.commit()
    return review


def review_is_admin_made(review):
    """Отзивът е добавен ръчно от админ (само тогава админът задава снимката на автора)."""
    return bool(review.author and review.author.is_admin)


def update_review(review, data, photo_url=None):
    """Редакция на отзив от админа: текст, звезди, роля и (само за отзиви с име) името.
    photo_url: None = снимката не се променя, '' = махни я, друго = нова (само за ръчно
    добавени отзиви с име). Не прави commit."""
    from app.services.review_persona import NAMED_VISIBILITIES
    named = review.visibility in NAMED_VISIBILITIES
    payload = dict(data)
    if not named:
        payload['name'] = review.display_name  # анонимният остава анонимен
    f = clean_review_fields(payload, named)
    review.text, review.stars, review.role = f['text'], f['stars'], f['role']
    if named:
        review.display_name = f['name']
        if photo_url is not None and review_is_admin_made(review):
            review.display_picture_url = photo_url or None
