"""
app/models/payment.py
=====================
Записва всяко успешно плащане като отделен ред.
Независимо колко пъти един потребител е платил — всяко се пази.
"""

from ..extensions import db
from datetime import datetime


class Payment(db.Model):
    __tablename__ = 'payment'

    id                     = db.Column(db.Integer, primary_key=True)
    user_id                = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan                   = db.Column(db.String(20), nullable=False)   # basic / plus / gold
    amount                 = db.Column(db.Float, nullable=False)        # EUR
    stripe_payment_intent  = db.Column(db.String(200), nullable=True)
    stripe_session_id      = db.Column(db.String(200), nullable=True)
    paid_at                = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('payments', lazy=True))

    def to_dict(self):
        return {
            'id':       self.id,
            'user_id':  self.user_id,
            'plan':     self.plan,
            'amount':   self.amount,
            'paid_at':  self.paid_at.strftime('%d.%m.%Y %H:%M'),
        }
