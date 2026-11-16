"""
app/services/account_deletion.py
================================
Изтриване на акаунт = АНОНИМИЗИРАНЕ.

Реда на потребителя НЕ се трие: към него сочат плащания (счетоводна
история), планове, резултати, коментари и др., които трябва да се запазят.
Махат се само личните данни, а акаунтът става невъзможен за вход:

- име, nick, имейл, фамилия, фирма, ранг, Google данни, снимка -> зачистени;
  имейлът става `deleted-<id>@deleted.invalid` (така същият имейл може да се
  регистрира отново);
- паролата -> случайна (никой не я знае), токени/OTP/сесия -> изтрити;
- историята на влизанията (IP адреси), известията и избора за отзив -> изтрити;
- отзивите му остават, но се показват като анонимни;
- коментарите остават и се показват като "Deleted user" (feed.display_name).

Всичко е в една транзакция - при грешка нищо не се променя.
"""
import secrets
from datetime import datetime

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models.login_event import LoginEvent
from app.models.notification import Notification
from app.models.review import Review
from app.models.review_prompt import ReviewPrompt

DELETED_EMAIL_DOMAIN = 'deleted.invalid'
DELETED_NAME = 'Deleted user'
ANONYMOUS_REVIEW_NAME = 'Anonymous Sailor'


def delete_account(user):
    """Анонимизира акаунта. При грешка прави rollback и повдига изключението."""
    try:
        LoginEvent.query.filter_by(user_id=user.id).delete()
        Notification.query.filter_by(user_id=user.id).delete()
        ReviewPrompt.query.filter_by(user_id=user.id).delete()
        Review.query.filter_by(user_id=user.id).update({
            'visibility': 'anonymous',
            'display_name': ANONYMOUS_REVIEW_NAME,
            'display_picture_url': None,
        })

        user.name = DELETED_NAME
        user.email = f'deleted-{user.id}@{DELETED_EMAIL_DOMAIN}'
        user.nick = ''
        user.firstname = ''
        user.lastname = ''
        user.rank = ''
        user.company = ''
        user.google_id = None
        user.google_picture_url = None
        user.avatar_data = None
        user.avatar_version = 0
        user.password = generate_password_hash(secrets.token_urlsafe(32))
        user.verification_token = None
        user.otp_code = None
        user.otp_expires = None
        user.reset_token_expires = None
        user.session_token = None
        user.email_verified = False
        user.notif_subscription = False
        user.deleted_at = datetime.utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
