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
    plan = db.Column(db.String(20), default='free')  # free, basic, plus, gold
    plan_activated_at = db.Column(db.DateTime, nullable=True)   # кога е активиран планът
    plan_expires_at   = db.Column(db.DateTime, nullable=True)   # кога изтича планът
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

    # Предпочитания за четене на тестовете (font size/theme/family) - от
    # менюто с 3-те чертички в хедъра на теста/симулатора. Записват се
    # веднъж в акаунта на потребителя, важат за ВСИЧКИ функции за решаване
    # на тестове (Test/Mix/Mistakes/Simulator).
    # Отделни размери/шрифтове за ВЪПРОСА и за ОТГОВОРИТЕ (слайдери 0-10).
    pref_q_font_size = db.Column(db.Integer, default=5)              # 0-10 (слайдер), скалира px
    pref_a_font_size = db.Column(db.Integer, default=5)               # 0-10 (слайдер), скалира px
    pref_theme = db.Column(db.String(10), default='dark')            # dark / light / sepia
    pref_q_font_family = db.Column(db.String(20), default='default')  # шрифт на въпроса
    pref_a_font_family = db.Column(db.String(20), default='default')  # шрифт на отговорите
    library_selected_at = db.Column(db.DateTime, nullable=True)        # начало на 7-дневния прозорец
    library_last_simulator_at = db.Column(db.DateTime, nullable=True)  # последно пускане на симулатор (1/ден лимит)
    tests_used = db.Column(db.Integer, default=0)  # брой решени теста за текущия план
    gold_test_ids = db.Column(db.Text, nullable=True)         # JSON [id1, id2] — избрани тестове при Gold активация
    plan_grace_until = db.Column(db.DateTime, nullable=True)  # край на All Mistakes grace период (след изтичане на плана)

    results = db.relationship('TestResult', backref='user', lazy=True)

    # ------------------------------------------------------------------
    # Library helpers (free план — 1 избран тест за 7 дни)
    # ------------------------------------------------------------------
    @property
    def LIBRARY_WINDOW_DAYS(self):
        try:
            from app.services.plans import TESTING_MODE, TESTING_DAYS
            if TESTING_MODE:
                return TESTING_DAYS
        except Exception:
            pass
        return 7

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

    # ------------------------------------------------------------------
    # Реален статус на плана — проверява истинска валидност (GoldGrant/
    # plan_expires_at), а не суровото поле user.plan, което остава зададено
    # завинаги дори след като достъпът реално е изтекъл.
    # ------------------------------------------------------------------
    def active_gold_grants(self):
        if not hasattr(self, '_cached_gold_grants'):
            from app.models.gold_grant import GoldGrant
            from datetime import datetime
            self._cached_gold_grants = GoldGrant.query.filter(
                GoldGrant.user_id == self.id, GoldGrant.expires_at > datetime.utcnow()
            ).all()
        return self._cached_gold_grants

    def active_plan_grants(self):
        """Активни Basic/Plus grant-ове (автономни покупки, огледално на Gold)."""
        if not hasattr(self, '_cached_plan_grants'):
            from app.models.plan_grant import PlanGrant
            from datetime import datetime
            self._cached_plan_grants = PlanGrant.query.filter(
                PlanGrant.user_id == self.id, PlanGrant.expires_at > datetime.utcnow()
            ).all()
        return self._cached_plan_grants

    def has_active_plan(self):
        return len(self.active_plan_grants()) > 0 or len(self.active_gold_grants()) > 0

    def effective_plan_label(self):
        plan_grants = self.active_plan_grants()
        gold_grants = self.active_gold_grants()
        labels = []
        if plan_grants:
            # ако има и basic и plus едновременно, показваме и двата
            for p in ('plus', 'basic'):
                if any(g.plan == p for g in plan_grants):
                    labels.append(p.capitalize())
        if gold_grants:
            labels.append('Gold')
        return ' + '.join(labels) if labels else 'Free'

    def effective_days_left(self):
        from datetime import datetime
        import math
        now = datetime.utcnow()
        candidates = [g.expires_at for g in self.active_plan_grants()]
        candidates.extend(g.expires_at for g in self.active_gold_grants())
        if not candidates:
            return 0
        return max(0, math.ceil((max(candidates) - now).total_seconds() / 86400))

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
