"""
app/models/all_mistakes_pass.py
===============================
Платен допълнителен достъп (1 месец) до решаване на All Mistakes за ЕДИН тест, след като
абонаментът му е изтекъл. Всяка покупка е собствен запис със собствен лимит от решавания.
"""
from datetime import datetime
from ..extensions import db


class AllMistakesPass(db.Model):
    __tablename__ = 'all_mistakes_pass'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    test_id = db.Column(db.Integer, nullable=False, index=True)
    quota = db.Column(db.Integer, nullable=False)           # колко решавания включва достъпът
    activated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
