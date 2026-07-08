from ..extensions import db
from datetime import datetime


class FreeSession(db.Model):
    """
    История на Free-план сесиите (аналог на PlanGrant/GoldGrant, но за Free).

    ЗАЩО Е НУЖЕН: user.library_test_id / user.library_selected_at са
    ЕДИНИЧНИ полета на User модела - при всяко (пре)избиране на нов тест те
    се ПРЕЗАПИСВАТ, затова Free план НЯМАШЕ никаква запазена история (за
    разлика от Basic/Plus/Gold, при които всяка покупка си е отделен ред в
    PlanGrant/GoldGrant). Тази таблица създава РЕД при всяко (пре)избиране,
    за да може Free да се вижда в Usage/Billing историята по същия начин
    като платените планове - кога е активирана сесията, докога е важала.
    """
    __tablename__ = 'free_session'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    activated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)

    test = db.relationship('Test', foreign_keys=[test_id])
