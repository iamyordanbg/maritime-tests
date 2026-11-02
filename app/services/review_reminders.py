"""
app/services/review_reminders.py
================================
Седмица след "Not now" в прозореца за отзив потребителят получава имейл с два избора
(No thanks / Submit review). Тук са: линкът за "No thanks", изпращането на напомнянията
и фоновата нишка, която ги проверява периодично.
"""
import threading
import time
from datetime import datetime

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.extensions import db
from app.models.review import Review
from app.models.review_prompt import ReviewPrompt
from app.models.user import User
from app.services import email as mailer

DECLINE_TOKEN_SALT = 'review-decline'
DECLINE_TOKEN_MAX_AGE_DAYS = 60
CHECK_INTERVAL_SECONDS = 3600  # колко често фонът проверява за дължими напомняния
STARTUP_DELAY_SECONDS = 60


def _serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=DECLINE_TOKEN_SALT)


def make_decline_token(user_id):
    return _serializer().dumps(user_id)


def read_decline_token(token):
    """user_id от линка "No thanks" или None, ако е невалиден/изтекъл."""
    try:
        return _serializer().loads(token, max_age=DECLINE_TOKEN_MAX_AGE_DAYS * 86400)
    except (BadSignature, SignatureExpired):
        return None


def _claim_due(now):
    """Атомарно "заключва" дължимите напомняния (reminder_sent_at = now), така че при
    няколко процеса/worker-а всяко се изпраща точно веднъж. Връща списък user_id."""
    due = ReviewPrompt.query.filter(
        ReviewPrompt.declined.is_(False),
        ReviewPrompt.remind_at <= now,
        ReviewPrompt.reminder_sent_at.is_(None),
    ).all()
    claimed = []
    for state in due:
        updated = ReviewPrompt.query.filter_by(id=state.id, reminder_sent_at=None).update(
            {'reminder_sent_at': now}, synchronize_session=False)
        db.session.commit()
        if updated == 1:
            claimed.append(state.user_id)
    return claimed


def _release(user_id):
    """Връща напомнянето в "чакащо" (неуспешно изпращане) - следващата проверка опитва пак."""
    ReviewPrompt.query.filter_by(user_id=user_id).update({'reminder_sent_at': None})
    db.session.commit()


def send_due_reminders(now=None):
    """Изпраща всички дължими напомняния. Връща броя успешно изпратени."""
    now = now or datetime.utcnow()
    sent = 0
    for user_id in _claim_due(now):
        user = db.session.get(User, user_id)
        if not user or not user.email or Review.query.filter_by(user_id=user_id).first():
            continue  # няма на кого / вече е оставил отзив - без имейл (остава "изпратено")
        base = mailer.base_url()
        ok = mailer.send_review_reminder_email(
            user.email,
            decline_url=f"{base}/review/decline/{make_decline_token(user_id)}",
            dashboard_url=f"{base}/dashboard",
        )
        if ok:
            sent += 1
        else:
            current_app.logger.warning("review reminder to user %s failed; will retry", user_id)
            _release(user_id)
    return sent


def start_reminder_scheduler(app):
    """Фонова нишка (daemon): на всеки час изпраща дължимите напомняния."""
    def _loop():
        time.sleep(STARTUP_DELAY_SECONDS)
        while True:
            try:
                with app.app_context():
                    send_due_reminders()
            except Exception:
                app.logger.exception("review reminder sweep failed")
            time.sleep(CHECK_INTERVAL_SECONDS)

    threading.Thread(target=_loop, name='review-reminders', daemon=True).start()
