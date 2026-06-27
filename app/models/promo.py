from ..extensions import db
from datetime import datetime

class PromoCode(db.Model):
    """Промокодове"""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    client_name = db.Column(db.String(200), default='')
    access_type = db.Column(db.String(100), default='Регулярни тестове')
    price = db.Column(db.Float, default=0)
    is_active = db.Column(db.Boolean, default=True)
    is_used = db.Column(db.Boolean, default=False)
    used_by = db.Column(db.String(120), default='')
    used_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)              # валидност (Gold: 12 месеца)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    stripe_payment_intent = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


