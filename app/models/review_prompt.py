from ..extensions import db


class ReviewPrompt(db.Model):
    """Какво е избрал потребителят в прозореца "Your opinion matters to us".

    declined          -> "No thanks": прозорецът никога повече не се показва.
    remind_at         -> "Not now": кога да му пратим имейл с напомняне (след седмица).
    reminder_sent_at  -> кога е изпратено напомнянето (еднократно; след него на таблото
                         се показва прозорец с две опции - No thanks / Submit review).
    Таблицата се създава от db.create_all() - не са нужни ALTER TABLE миграции.
    """
    __tablename__ = 'review_prompt'

    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    declined         = db.Column(db.Boolean, nullable=False, default=False)
    remind_at        = db.Column(db.DateTime, nullable=True)
    reminder_sent_at = db.Column(db.DateTime, nullable=True)
