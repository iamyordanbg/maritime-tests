"""
tests/unit/test_models.py
=========================
Unit тестове за модели и permissions логика.
"""

import pytest
from datetime import datetime, timedelta
from app.permissions.roles import Plan, Role, get_plan, plan_gte, user_role, user_can_access_test
from app.permissions.permissions import Feature, plan_has_feature


# ---------------------------------------------------------------------------
# Plan / Role
# ---------------------------------------------------------------------------

class TestPlanHierarchy:

    def test_free_is_lowest(self):
        assert Plan.FREE < Plan.BASIC < Plan.PLUS < Plan.GOLD

    def test_get_plan_free(self, free_user):
        assert get_plan(free_user) == Plan.FREE

    def test_get_plan_basic(self, basic_user):
        assert get_plan(basic_user) == Plan.BASIC

    def test_get_plan_gold(self, gold_user):
        assert get_plan(gold_user) == Plan.GOLD

    def test_get_plan_admin_sentinel(self, admin_user):
        # Admin е над Gold
        assert get_plan(admin_user) > Plan.GOLD

    def test_plan_gte_basic(self, basic_user):
        assert plan_gte(basic_user, Plan.BASIC)
        assert plan_gte(basic_user, Plan.FREE)
        assert not plan_gte(basic_user, Plan.PLUS)

    def test_plan_gte_admin_passes_all(self, admin_user):
        for plan in [Plan.FREE, Plan.BASIC, Plan.PLUS, Plan.GOLD]:
            assert plan_gte(admin_user, plan)

    def test_user_role_admin(self, admin_user):
        assert user_role(admin_user) == Role.ADMIN

    def test_user_role_user(self, free_user):
        assert user_role(free_user) == Role.USER


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------

class TestFeatures:

    def test_free_has_demo_tests(self, free_user):
        assert plan_has_feature(free_user, Feature.DEMO_TESTS)

    def test_free_has_library_pick(self, free_user):
        assert plan_has_feature(free_user, Feature.LIBRARY_PICK)

    def test_free_no_full_library(self, free_user):
        assert not plan_has_feature(free_user, Feature.FULL_LIBRARY)

    def test_basic_has_full_library(self, basic_user):
        assert plan_has_feature(basic_user, Feature.FULL_LIBRARY)

    def test_basic_inherits_free_features(self, basic_user):
        assert plan_has_feature(basic_user, Feature.DEMO_TESTS)
        assert plan_has_feature(basic_user, Feature.SIMULATOR)

    def test_gold_has_priority_support(self, gold_user):
        assert plan_has_feature(gold_user, Feature.PRIORITY_SUPPORT)

    def test_admin_has_all_features(self, admin_user):
        for f in [Feature.FULL_LIBRARY, Feature.SIMULATOR,
                  Feature.PRIORITY_SUPPORT, Feature.PROGRESS_CHARTS]:
            assert plan_has_feature(admin_user, f)


# ---------------------------------------------------------------------------
# Test access
# ---------------------------------------------------------------------------

class TestUserCanAccessTest:

    def test_admin_can_access_any_test(self, admin_user, regular_test):
        assert user_can_access_test(admin_user, regular_test)

    def test_active_user_can_access_any_test(self, basic_user, regular_test):
        assert user_can_access_test(basic_user, regular_test)

    def test_free_user_can_access_demo(self, free_user, demo_test):
        assert user_can_access_test(free_user, demo_test)

    def test_free_user_cannot_access_regular(self, free_user, regular_test):
        assert not user_can_access_test(free_user, regular_test)

    def test_free_user_with_library_selection(self, free_user, regular_test, db):
        free_user.library_test_id = regular_test.id
        free_user.library_selected_at = datetime.utcnow()
        db.session.commit()
        assert user_can_access_test(free_user, regular_test)

    def test_free_user_wrong_library_selection(self, free_user, regular_test, demo_test, db):
        free_user.library_test_id = demo_test.id
        free_user.library_selected_at = datetime.utcnow()
        db.session.commit()
        assert not user_can_access_test(free_user, regular_test)


# ---------------------------------------------------------------------------
# User model helpers
# ---------------------------------------------------------------------------

class TestUserLibraryHelpers:

    def test_library_days_left_no_selection(self, free_user):
        assert free_user.library_days_left() == 0

    def test_library_days_left_active(self, free_user, regular_test, db):
        free_user.library_test_id = regular_test.id
        free_user.library_selected_at = datetime.utcnow()
        db.session.commit()
        assert free_user.library_days_left() > 0

    def test_library_window_expired(self, free_user, regular_test, db):
        free_user.library_test_id = regular_test.id
        free_user.library_selected_at = datetime.utcnow() - timedelta(days=8)
        db.session.commit()
        assert free_user.library_days_left() == 0

    def test_library_simulator_available_first_time(self, free_user):
        assert free_user.library_simulator_available()

    def test_library_simulator_not_available_today(self, free_user, db):
        free_user.library_last_simulator_at = datetime.utcnow()
        db.session.commit()
        assert not free_user.library_simulator_available()
