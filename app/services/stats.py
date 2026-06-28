"""
app/services/stats.py
"""
from app.extensions import db
from app.models.user import User
from app.models.test import Test, DemoVisit
from app.models.result import TestResult
from app.models.promo import PromoCode
from app.models.payment import Payment
from app.models.snapshot import MonthlySnapshot
from datetime import datetime, timedelta
import json
from pathlib import Path

_DEMO_COUNTER = Path(__file__).parent.parent / 'static' / 'demo_counter.json'

def _get_demo_count():
    try:
        return json.loads(_DEMO_COUNTER.read_text()).get('count', 0) if _DEMO_COUNTER.exists() else 0
    except Exception:
        return 0

def record_monthly_snapshot():
    """Записва snapshot за текущия месец"""
    now = datetime.utcnow()
    year, month = now.year, now.month
    existing = MonthlySnapshot.query.filter_by(year=year, month=month).first()
    snap = existing or MonthlySnapshot(year=year, month=month)
    if not existing:
        db.session.add(snap)

    total = User.query.filter_by(is_admin=False).count()
    snap.total_users   = total
    snap.active_users  = User.query.filter_by(is_admin=False, is_active=True).count()
    snap.passive_users = total - snap.active_users
    snap.demo_users    = _get_demo_count()
    db.session.commit()
    return snap


def _calc_income():
    """
    Сумира всички редове в Payment таблицата.
    income_all   = всички плащания от началото
    income_month = само плащанията в текущия календарен месец
    """
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    income_all = db.session.query(
        db.func.coalesce(db.func.sum(Payment.amount), 0)
    ).scalar()

    income_month = db.session.query(
        db.func.coalesce(db.func.sum(Payment.amount), 0)
    ).filter(Payment.paid_at >= month_start).scalar()

    return round(float(income_all), 2), round(float(income_month), 2)


def get_admin_stats():
    """Всички статистики за admin dashboard"""
    total_users  = User.query.filter_by(is_admin=False).count()
    active_users = User.query.filter_by(is_admin=False, is_active=True).count()
    demo_users   = total_users - active_users
    demo_sessions = _get_demo_count()

    promo_all     = PromoCode.query.count()
    active_promos = PromoCode.query.filter_by(is_active=True, is_used=False).count()
    promo_standby = PromoCode.query.filter_by(is_active=False, is_used=False).count()
    used_promos   = PromoCode.query.filter_by(is_used=True).count()

    deck_q   = db.session.query(db.func.sum(Test.question_count)).filter_by(category="deck").scalar() or 0
    engine_q = db.session.query(db.func.sum(Test.question_count)).filter_by(category="engine").scalar() or 0
    open_signals = 0

    income_all, income_month = _calc_income()

    return dict(
        total_users=total_users, active_users=active_users,
        demo_users=demo_users, demo_sessions=demo_sessions,
        promo_all=promo_all, active_promos=active_promos,
        promo_standby=promo_standby, used_promos=used_promos,
        deck_q=deck_q, engine_q=engine_q,
        open_signals=open_signals,
        income_all=income_all,
        income_month=income_month,
        income_all_trend=0,
        income_month_trend=0,
    )
