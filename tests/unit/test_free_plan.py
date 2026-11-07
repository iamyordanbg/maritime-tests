"""Free plan = 30 days; one source of truth in services/plans.py::FREE_PLAN."""
from app.services import plans
from app.models.user import User


def test_free_plan_config():
    assert plans.FREE_PLAN['days'] == 30
    assert plans.FREE_PLAN['simulator_per_day'] == 1


def test_library_window_follows_free_plan_when_not_testing(monkeypatch):
    monkeypatch.setattr(plans, 'TESTING_MODE', False)
    assert User().LIBRARY_WINDOW_DAYS == 30


def test_testing_mode_still_shrinks_the_window(monkeypatch):
    monkeypatch.setattr(plans, 'TESTING_MODE', True)
    assert User().LIBRARY_WINDOW_DAYS == plans.TESTING_DAYS


def test_landing_shows_free_days_from_config(client):
    html = client.get('/').get_data(as_text=True)
    assert f"{plans.FREE_PLAN['days']} days" in html
