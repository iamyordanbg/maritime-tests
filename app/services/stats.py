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
    Сумира нетните суми (след Stripe такса) от Payment таблицата.
    Ако net_amount не е наличен — използва amount като fallback.
    """
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    try:
        income_all = db.session.query(
            db.func.coalesce(db.func.sum(Payment.net_amount), 0)
        ).scalar()

        income_month = db.session.query(
            db.func.coalesce(db.func.sum(Payment.net_amount), 0)
        ).filter(Payment.paid_at >= month_start).scalar()

        if float(income_all) == 0:
            raise Exception("net_amount empty, fallback to amount")

    except Exception:
        income_all = db.session.query(
            db.func.coalesce(db.func.sum(Payment.amount), 0)
        ).scalar()

        income_month = db.session.query(
            db.func.coalesce(db.func.sum(Payment.amount), 0)
        ).filter(Payment.paid_at >= month_start).scalar()

    return round(float(income_all), 2), round(float(income_month), 2)


def get_admin_stats():
    """Всички статистики за admin dashboard"""
    _user_stats = (db.session.query(
                     db.func.count(User.id),
                     db.func.sum(db.case((User.is_active == True, 1), else_=0))
                   ).filter(User.is_admin == False).first())
    total_users = _user_stats[0] or 0
    active_users = _user_stats[1] or 0
    demo_users   = total_users - active_users
    demo_sessions = _get_demo_count()

    from datetime import datetime as _dt
    now_dt = _dt.utcnow()

    # 4 - Demo тестове в платформата
    demo_tests_count = Test.query.filter_by(is_demo=True).count()

    # 5 - Всички промокодове (Gold = 10 на покупка)
    gold_payments = Payment.query.filter_by(plan='gold').count()
    other_promos  = PromoCode.query.filter(PromoCode.access_type != 'gold').count()
    promo_all     = (gold_payments * 10) + other_promos

    # 6 - Активни промокодове (is_active=True, is_used=False, не изтекли)
    active_promos = PromoCode.query.filter(
        PromoCode.is_active == True,
        PromoCode.is_used == False,
        db.or_(PromoCode.expires_at == None, PromoCode.expires_at > now_dt)
    ).count()

    # 7 - Stand-by: Gold промокодове неизползвани (в рамките на 12 месеца)
    promo_standby = PromoCode.query.filter(
        PromoCode.is_used == False,
        PromoCode.access_type == 'gold',
        db.or_(PromoCode.expires_at == None, PromoCode.expires_at > now_dt)
    ).count()

    # 8 - Изтекли планове (plan_expires_at < now)
    used_promos = User.query.filter(
        User.is_admin == False,
        User.plan.in_(['basic', 'plus', 'gold']),
        User.plan_expires_at < now_dt
    ).count()

    # Брой решени тестове (от TestResult) — deck и engine в ЕДНА заявка вместо 2
    _dept_counts = (db.session.query(Test.category, db.func.count(TestResult.id))
                    .join(Test, TestResult.test_id == Test.id)
                    .filter(Test.category.in_(['deck', 'engine']))
                    .group_by(Test.category).all())
    _dept_map = dict(_dept_counts)
    deck_q = _dept_map.get('deck', 0)
    engine_q = _dept_map.get('engine', 0)
    open_signals = 0

    income_all, income_month = _calc_income()

    return dict(
        total_users=total_users, active_users=active_users,
        demo_users=demo_users, demo_sessions=demo_sessions, demo_tests_count=demo_tests_count,
        promo_all=promo_all, active_promos=active_promos,
        promo_standby=promo_standby, used_promos=used_promos,
        deck_q=deck_q, engine_q=engine_q,
        open_signals=open_signals,
        income_all=income_all,
        income_month=income_month,
        income_all_trend=0,
        income_month_trend=0,
    )
