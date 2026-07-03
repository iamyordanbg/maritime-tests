"""
app/models/plan_grant.py
=========================
Всяка покупка на Basic/Plus план е свой собствен, напълно автономен запис —
собствен избран тест, собствен лимит, собствен срок. Купуването на втори
план (дори същия тип) НЕ презаписва/слива предишния — появява се нова карта.
"""

from datetime import datetime
from ..extensions import db


class PlanGrant(db.Model):
    __tablename__ = 'plan_grant'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    plan = db.Column(db.String(20), nullable=False)     # basic / plus

    quota = db.Column(db.Integer, default=0)
    tests_used = db.Column(db.Integer, default=0)

    # Собствен избран тест за тази конкретна покупка (както Free/старият модел,
    # но вече за ВСЕКИ grant поотделно, не един общ за целия акаунт)
    library_test_id = db.Column(db.Integer, nullable=True)
    library_selected_at = db.Column(db.DateTime, nullable=True)

    activated_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_active(self, now=None):
        now = now or datetime.utcnow()
        return self.expires_at and self.expires_at > now
