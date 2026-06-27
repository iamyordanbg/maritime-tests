"""
tests/unit/test_services.py
===========================
Unit тестове за services/plans.py
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from app.services.plans import (
    PLANS, get_plan_config, activate_plan, get_plan_display
)


class TestPlanConfig:

    def test_all_plans_exist(self):
        for name in ['basic', 'plus', 'gold']:
            assert get_plan_config(name) is not None

    def test_invalid_plan_returns_none(self):
        assert get_plan_config('nonexistent') is None

    def test_basic_price(self):
        assert PLANS['basic']['price'] == 19.99

    def test_plus_price(self):
        assert PLANS['plus']['price'] == 39.99

    def test_gold_price(self):
        assert PLANS['gold']['price'] == 299.99

    def test_basic_days(self):
        assert PLANS['basic']['days'] == 7

    def test_plus_days(self):
        assert PLANS['plus']['days'] == 30

    def test_gold_promo_codes(self):
        assert PLANS['gold']['promo_codes'] == 10

    def test_gold_validity_months(self):
        assert PLANS['gold']['validity_months'] == 12

    def test_all_plans_have_features(self):
        for name, config in PLANS.items():
            assert len(config['features']) > 0


class TestActivatePlan:

    def test_activate_basic(self, free_user, db):
        result = activate_plan(free_user, 'basic')
        db.session.commit()
        assert result is True
        assert free_user.plan == 'basic'
        assert free_user.is_active is True
        assert free_user.plan_expires_at is not None

    def test_activate_plus(self, free_user, db):
        activate_plan(free_user, 'plus')
        db.session.commit()
        assert free_user.plan == 'plus'

    def test_activate_invalid_plan(self, free_user):
        result = activate_plan(free_user, 'nonexistent')
        assert result is False

    def test_expiry_basic_7_days(self, free_user, db):
        activate_plan(free_user, 'basic')
        db.session.commit()
        delta = free_user.plan_expires_at - datetime.utcnow()
        assert 6 <= delta.days <= 7


class TestGetPlanDisplay:

    def test_free_user_display(self, free_user):
        display = get_plan_display(free_user)
        assert display['plan'] == 'free'
        assert display['is_active'] is False

    def test_basic_user_display(self, basic_user):
        display = get_plan_display(basic_user)
        assert display['plan'] == 'basic'
        assert display['is_active'] is True
