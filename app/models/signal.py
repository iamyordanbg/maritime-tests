from ..extensions import db
from datetime import datetime

class Signal(db.Model):
    """Сигнали / съобщения от потребители"""
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user_name  = db.Column(db.String(100), default='Анонимен')
    user_email = db.Column(db.String(120), default='')
    type       = db.Column(db.String(50), default='bug')   # bug / suggestion / question
    message    = db.Column(db.String(500), nullable=False)
    status     = db.Column(db.String(20), default='open')  # open / resolved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Admin отговор
    reply      = db.Column(db.String(500), nullable=True)
    replied_at = db.Column(db.DateTime, nullable=True)
    is_read    = db.Column(db.Boolean, default=False)      # прочетено от user
