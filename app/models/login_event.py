from datetime import datetime

from ..extensions import db


class LoginEvent(db.Model):
    """One sign-in (or IP change of a signed-in browser). Feeds the admin security signals; pruned after RETENTION_DAYS."""
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    device_id  = db.Column(db.String(64), nullable=False)      # random id kept in the browser's 'did' cookie
    slot       = db.Column(db.String(10), default='')          # 'phone' / 'computer'
    ip         = db.Column(db.String(64), default='')
    country    = db.Column(db.String(60), default='')
    city       = db.Column(db.String(100), default='')
    lat        = db.Column(db.Float, nullable=True)
    lon        = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
