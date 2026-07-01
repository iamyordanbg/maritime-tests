"""
app/models/payment.py
=====================
Записва всяко успешно плащане като отделен ред.
"""

from ..extensions import db
from datetime import datetime


class Payment(db.Model):
    __tablename__ = 'payment'

    id                     = db.Column(db.Integer, primary_key=True)
    user_id                = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan                   = db.Column(db.String(20), nullable=False)
    amount                 = db.Column(db.Float, nullable=False)        # брутна сума EUR
    stripe_fee             = db.Column(db.Float, nullable=True)         # Stripe такса EUR
    net_amount             = db.Column(db.Float, nullable=True)         # нетна сума EUR
    stripe_payment_intent  = db.Column(db.String(200), nullable=True)
    stripe_session_id      = db.Column(db.String(200), nullable=True)
    paid_at                = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    promo_email_sent       = db.Column(db.Boolean, default=False)       # официално потвърждение, че 10-те кода са изпратени
    promo_email_sent_at    = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref=db.backref('payments', lazy=True, cascade="all, delete-orphan"), passive_deletes=True)

    def to_dict(self):
        return {
            'id':         self.id,
            'user_id':    self.user_id,
            'plan':       self.plan,
            'amount':     self.amount,
            'stripe_fee': self.stripe_fee,
            'net_amount': self.net_amount,
            'paid_at':    self.paid_at.strftime('%d.%m.%Y %H:%M'),
            'promo_email_sent': self.promo_email_sent,
            'promo_email_sent_at': self.promo_email_sent_at.strftime('%d.%m.%Y %H:%M') if self.promo_email_sent_at else None,
        }
