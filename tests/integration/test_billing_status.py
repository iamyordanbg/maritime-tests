"""
tests/integration/test_billing_status.py
========================================
Settings -> Billing: всяка покупка/код получава is_active (true = ACTIVE, false = EXPIRED).
"""

from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from app.models.payment import Payment
from app.models.plan_grant import PlanGrant
from app.models.user import User
from app.services.usage import _grant_is_active, build_billing_data

NOW = datetime.utcnow()


def _user(db):
    u = User(name='Bill', email='bill@test.bg', password=generate_password_hash('Test123'),
             plan='basic', is_active=True, is_admin=False, email_verified=True)
    db.session.add(u)
    db.session.commit()
    return u


def _payment_with_grant(db, user, activated_days_ago, expires_in_days, amount):
    p = Payment(user_id=user.id, plan='basic', amount=amount,
                paid_at=NOW - timedelta(days=activated_days_ago))
    db.session.add(p)
    db.session.commit()
    g = PlanGrant(user_id=user.id, plan='basic', quota=5, tests_used=0, library_test_id=None,
                  activated_at=NOW - timedelta(days=activated_days_ago),
                  expires_at=NOW + timedelta(days=expires_in_days), payment_id=p.id)
    db.session.add(g)
    db.session.commit()
    return p, g


class TestGrantIsActive:

    class _G:
        def __init__(self, a, e):
            self.activated_at, self.expires_at = a, e

    def test_running_grant(self):
        assert _grant_is_active(self._G(NOW - timedelta(days=1), NOW + timedelta(days=1)), NOW) is True

    def test_expired_grant(self):
        assert _grant_is_active(self._G(NOW - timedelta(days=3), NOW - timedelta(seconds=1)), NOW) is False

    def test_not_started_or_missing(self):
        assert _grant_is_active(self._G(NOW + timedelta(days=1), NOW + timedelta(days=2)), NOW) is False
        assert _grant_is_active(None, NOW) is False
        assert _grant_is_active(self._G(NOW, None), NOW) is False


def test_two_basic_payments_one_active_one_expired(client, db):
    u = _user(db)
    p_old, g_old = _payment_with_grant(db, u, activated_days_ago=5, expires_in_days=-4, amount=19.99)
    p_new, g_new = _payment_with_grant(db, u, activated_days_ago=0, expires_in_days=1, amount=19.99)
    client.post('/login', data={'email': 'bill@test.bg', 'password': 'Test123'},
                headers={'X-Requested-With': 'XMLHttpRequest'})
    data = client.get('/api/my-billing').get_json()
    by_id = {p['id']: p for p in data['payments']}
    assert by_id[p_new.id]['is_active'] is True
    assert by_id[p_old.id]['is_active'] is False
    for obj in (g_old, g_new, p_old, p_new, u):
        db.session.delete(obj)
    db.session.commit()


def test_payment_without_grant_has_no_status(db):
    u = _user(db)
    p = Payment(user_id=u.id, plan='basic', amount=19.99)
    db.session.add(p)
    db.session.commit()
    payments, _ = build_billing_data(u)
    assert payments[0]['is_active'] is None
    db.session.delete(p)
    db.session.delete(u)
    db.session.commit()
