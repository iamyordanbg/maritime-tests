"""
tests/integration/test_billing.py
===================================
Integration тестове за billing routes и webhook.
"""

import pytest
import json
from unittest.mock import patch, MagicMock


class TestPlansPage:

    def test_plans_page_public(self, client):
        """Страницата с планове е достъпна без login."""
        res = client.get('/billing/plans')
        assert res.status_code == 200
        assert 'Basic' in res.data.decode()
        assert 'Plus' in res.data.decode()
        assert 'Gold' in res.data.decode()

    def test_plans_page_shows_prices(self, client):
        res = client.get('/billing/plans')
        data = res.data.decode()
        assert '19.99' in data
        assert '39.99' in data
        assert '299.99' in data


class TestCheckout:

    def test_checkout_requires_login(self, client):
        res = client.post('/billing/checkout/basic')
        assert res.status_code == 302
        # Реалният flow праща госта на landing страницата с отворен
        # register/login попъп ('/?register=1'), не отделен /login или
        # /auth URL - потвърждаваме, че НЕ отива директно на checkout/dashboard.
        assert 'register' in res.location or 'login' in res.location or res.location == '/'

    def test_checkout_invalid_plan(self, client, basic_user):
        client.post('/login', data={
            'email': 'basic@test.bg', 'password': 'Test123'
        })
        res = client.post('/billing/checkout/nonexistent')
        assert res.status_code == 302
        # billing/plans.html е modal fragment (display:none), не самостоятелна
        # страница - директна навигация показва празен екран. checkout() затова
        # редиректва невалидни планове към /dashboard (виж коментара в
        # app/routes/billing.py при cancel_url за същата причина).
        assert 'dashboard' in res.location

    @patch('app.services.stripe.stripe')
    def test_checkout_redirects_to_stripe(self, mock_stripe, client, free_user):
        mock_session = MagicMock()
        mock_session.url = 'https://checkout.stripe.com/test'
        mock_stripe.checkout.Session.create.return_value = mock_session

        client.post('/login', data={
            'email': 'free@test.bg', 'password': 'Test123'
        })
        res = client.post('/billing/checkout/basic')
        assert res.status_code == 302
        assert 'stripe.com' in res.location


class TestWebhook:

    def test_webhook_invalid_signature(self, client):
        res = client.post('/billing/webhook',
            data=b'{}',
            headers={'Stripe-Signature': 'invalid', 'Content-Type': 'application/json'}
        )
        assert res.status_code == 400

    @patch('app.routes.billing.construct_webhook_event')
    @patch('app.routes.billing.handle_webhook_event')
    def test_webhook_checkout_completed(self, mock_handle, mock_construct, client):
        mock_construct.return_value = {
            'type': 'checkout.session.completed',
            'data': {'object': {}}
        }
        mock_handle.return_value = (True, 'OK')

        res = client.post('/billing/webhook',
            data=b'{}',
            headers={'Stripe-Signature': 'test', 'Content-Type': 'application/json'}
        )
        assert res.status_code == 200
        assert res.get_json()['status'] == 'ok'


class TestMyPlanAPI:

    def test_my_plan_requires_login(self, client):
        res = client.get('/billing/api/my-plan')
        assert res.status_code == 302

    def test_my_plan_returns_json(self, client, basic_user):
        client.post('/login', data={
            'email': 'basic@test.bg', 'password': 'Test123'
        })
        res = client.get('/billing/api/my-plan')
        assert res.status_code == 200
        data = res.get_json()
        assert data['plan'] == 'basic'
        assert data['is_active'] is True
