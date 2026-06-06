from app.extensions import db
from datetime import datetime

class User(db.Model):
    """Моряци / потребители"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    rank = db.Column(db.String(100), default='')          # Длъжност/ранг
    company = db.Column(db.String(100), default='')       # Компания
    category = db.Column(db.String(20), default='deck')   # deck / engine
    level = db.Column(db.String(30), default='Operational Level')
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    email_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(64), nullable=True)
    otp_code = db.Column(db.String(6), nullable=True)
    otp_expires = db.Column(db.DateTime, nullable=True)
    reset_token_expires = db.Column(db.DateTime, nullable=True)
    last_seen = db.Column(db.DateTime, default=None)
    promo_code = db.Column(db.String(50), default='')     # Кода с който се е регистрирал
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    results = db.relationship('TestResult', backref='user', lazy=True)

