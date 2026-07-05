"""
app/models/subscription_history.py
=====================================
Постоянно съхранени subscription кодове — по решение да НЕ се преизчисляват
"на момента" при всяко зареждане на страница, а да се пазят като реален
запис в базата, независим от бъдещи промени в алгоритъма за генериране.
"""

from datetime import datetime
from ..extensions import db


class SubscriptionHistory(db.Model):
    __tablename__ = 'subscription_history'

    id = db.Column(db.Integer, primary_key=True)
    grant_type = db.Column(db.String(10), nullable=False, index=True)   # 'gold' / 'plan'
    grant_id = db.Column(db.Integer, nullable=False, index=True)
    subscription_code = db.Column(db.String(20), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('grant_type', 'grant_id', name='uq_subscription_history_grant'),
    )
