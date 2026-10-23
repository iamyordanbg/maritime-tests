"""
tests/integration/test_plan_after_auth.py
=========================================
Потребител избира план на landing страницата, после се регистрира / влиза / влиза с Google ->
системата го праща директно към плащане (/billing/checkout/<план>), не в профила.
"""

from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from app.models.user import User

AJAX = {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}


def _pending_registration(client, email, plan='basic'):
    with client.session_transaction() as s:
        s['pending_verify_email'] = email
        s['pending_verify_name'] = 'Plan Buyer'
        s['pending_verify_password'] = generate_password_hash('Test123')
        s['pending_verify_otp'] = '123456'
        s['pending_verify_otp_expires'] = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
        s['pending_verify_promo'] = ''
        if plan:
            s['pending_plan'] = plan


class TestOtpRegistration:

    def test_new_account_goes_to_checkout(self, client, db):
        _pending_registration(client, 'newbuyer@test.bg')
        res = client.post('/verify-otp', data={'otp': '123456'}, headers=AJAX)
        assert res.get_json() == {'success': True, 'redirect': '/billing/checkout/basic'}
        User.query.filter_by(email='newbuyer@test.bg').delete()
        db.session.commit()

    def test_existing_email_goes_to_checkout_too(self, client, db):
        db.session.add(User(name='Old', email='again@test.bg', password=generate_password_hash('x'),
                            plan='free', is_active=False, is_admin=False, email_verified=True))
        db.session.commit()
        _pending_registration(client, 'again@test.bg', plan='plus')
        res = client.post('/verify-otp', data={'otp': '123456'}, headers=AJAX)
        assert res.get_json() == {'success': True, 'redirect': '/billing/checkout/plus'}
        User.query.filter_by(email='again@test.bg').delete()
        db.session.commit()

    def test_no_plan_keeps_old_behaviour(self, client, db):
        _pending_registration(client, 'noplan@test.bg', plan=None)
        res = client.post('/verify-otp', data={'otp': '123456'}, headers=AJAX)
        assert '/billing/checkout' not in res.get_json()['redirect']
        User.query.filter_by(email='noplan@test.bg').delete()
        db.session.commit()


class TestLoginAndGoogle:

    def test_login_with_pending_plan_goes_to_checkout(self, client, free_user):
        res = client.post('/login', data={'email': 'free@test.bg', 'password': 'Test123',
                                          'pending_plan': 'gold'}, headers=AJAX)
        assert res.get_json()['redirect'] == '/billing/checkout/gold'

    def test_google_login_stores_valid_plan(self, client):
        res = client.get('/auth/google?plan=basic')
        assert res.status_code == 302
        with client.session_transaction() as s:
            assert s['pending_plan'] == 'basic'

    def test_google_login_ignores_invalid_plan(self, client):
        client.get('/auth/google?plan=evil')
        with client.session_transaction() as s:
            assert 'pending_plan' not in s


class TestChosenPlanHelper:

    def test_accepts_every_configured_plan_and_nothing_else(self):
        from app.routes.auth import _chosen_plan
        from app.services.plans import PLANS
        for name in PLANS:
            assert _chosen_plan(name) == name
            assert _chosen_plan(f' {name} ') == name
        for bad in ('evil', '', None, 'BASIC '):
            assert _chosen_plan(bad) is None
