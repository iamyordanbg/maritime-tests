from ..extensions import db
from datetime import datetime

class User(db.Model):
    """Моряци / потребители"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    nick = db.Column(db.String(100), default='')          # Как да се обръщаме
    firstname = db.Column(db.String(100), default='')     # Първо име
    lastname  = db.Column(db.String(100), default='')     # Фамилия
    rank = db.Column(db.String(100), default='')
    company = db.Column(db.String(100), default='')
    category = db.Column(db.String(20), default='deck')
    level = db.Column(db.String(30), default='Operational Level')
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(64), nullable=True)
    otp_code = db.Column(db.String(6), nullable=True)
    otp_expires = db.Column(db.DateTime, nullable=True)
    reset_token_expires = db.Column(db.DateTime, nullable=True)
    last_seen = db.Column(db.DateTime, default=None)
    google_id = db.Column(db.String(200), nullable=True)
    promo_code = db.Column(db.String(50), default='')
    notif_subscription = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- Library: избран тест за free план (1 тест / 7 дни) ---
    library_test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=True)
    library_selected_at = db.Column(db.DateTime, nullable=True)        # начало на 7-дневния прозорец
    library_last_simulator_at = db.Column(db.DateTime, nullable=True)  # последно пускане на симулатор (1/ден лимит)

    results = db.relationship('TestResult', backref='user', lazy=True)

    # ------------------------------------------------------------------
    # Library helpers (free план — 1 избран тест за 7 дни)
    # ------------------------------------------------------------------
    LIBRARY_WINDOW_DAYS = 7

    def library_window_expires_at(self):
        if not self.library_selected_at:
            return None
        from datetime import timedelta, datetime as _dt, timezone
        selected = self.library_selected_at
        if isinstance(selected, str):
            try:
                selected = _dt.fromisoformat(selected.replace('Z', '+00:00').split('+')[0])
            except Exception:
                return None
        # Конвертирай до naive UTC ако има timezone
        if hasattr(selected, 'tzinfo') and selected.tzinfo is not None:
            selected = selected.astimezone(timezone.utc).replace(tzinfo=None)
        return selected + timedelta(days=self.LIBRARY_WINDOW_DAYS)

    def library_days_left(self):
        """Колко дни остават до изтичане на 7-дневния прозорец (0 ако е изтекъл/няма избор)."""
        expires = self.library_window_expires_at()
        if not expires:
            return 0
        from datetime import datetime as _dt, timezone
        import math
        # Нормализирай expires до naive UTC
        if isinstance(expires, str):
            try:
                expires = _dt.fromisoformat(expires.replace('Z', '+00:00').split('+')[0])
            except Exception:
                return 0
        # Ако expires има timezone info, конвертирай до naive UTC
        if hasattr(expires, 'tzinfo') and expires.tzinfo is not None:
            expires = expires.astimezone(timezone.utc).replace(tzinfo=None)
        now = _dt.utcnow()
        delta = expires - now
        if delta.total_seconds() <= 0:
            return 0
        return max(0, math.ceil(delta.total_seconds() / 86400))

    def library_window_active(self):
        return self.library_test_id is not None and self.library_days_left() > 0

    def library_refresh_if_expired(self):
        """Ако прозорецът е изтекъл, рестартира го автоматично със същия избран тест."""
        from datetime import datetime as _dt
        if self.library_test_id and self.library_selected_at:
            expires = self.library_window_expires_at()
            if expires and _dt.utcnow() >= expires:
                self.library_selected_at = _dt.utcnow()
                self.library_last_simulator_at = None
                return True
        return False

    def library_simulator_available(self):
        """Дали потребителят може да пусне симулатор днес (1 път на ден, в рамките на 7-те дни)."""
        if not self.library_last_simulator_at:
            return True
        from datetime import datetime as _dt
        last = self.library_last_simulator_at
        now = _dt.utcnow()
        return last.date() != now.date()
