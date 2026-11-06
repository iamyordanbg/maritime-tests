"""Choosing a test is optional: only the login suggests the Library (once); the dashboard never forces it."""
import json
from datetime import datetime, timedelta
import pytest
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models.user import User
from app.models.test import Test
from app.models.plan_grant import PlanGrant


@pytest.fixture
def world(app):
    with app.app_context():
        u = User(name="Nav User", email="nav@test.bg", password=generate_password_hash("Test123"),
                 plan="free", is_active=False, email_verified=True)
        qs = json.dumps([{"id": 1, "question": "Q", "options": [{"text": "A", "isCorrect": True}, {"text": "B"}]}])
        t1 = Test(title="NavT1", level="Operational Level", category="deck", is_demo=False, questions_json=qs, question_count=1)
        t2 = Test(title="NavT2", level="Operational Level", category="deck", is_demo=False, questions_json=qs, question_count=1)
        db.session.add_all([u, t1, t2]); db.session.commit()
        ids = (u.id, t1.id, t2.id)
    yield ids
    with app.app_context():
        PlanGrant.query.filter_by(user_id=ids[0]).delete()
        User.query.filter_by(id=ids[0]).delete()
        Test.query.filter(Test.id.in_(ids[1:])).delete(synchronize_session=False)
        db.session.commit()


def _grant(app, uid, test_id, start, end, plan='basic'):
    with app.app_context():
        db.session.add(PlanGrant(user_id=uid, plan=plan, quota=15, tests_used=0, library_test_id=test_id,
                                 activated_at=start, expires_at=end))
        db.session.commit()


def _login(app):
    c = app.test_client()
    r = c.post('/login', data={'email': 'nav@test.bg', 'password': 'Test123'}, headers={'X-Requested-With': 'XMLHttpRequest'})
    return c, r.get_json()['redirect']


def test_no_subscription_login_goes_to_library_but_dashboard_is_open(app, world):
    c, target = _login(app)
    assert target == '/library'
    assert c.get('/dashboard').status_code == 200          # never bounced back
    assert c.get('/dashboard').status_code == 200


def test_two_plans_one_expired_goes_straight_to_dashboard(app, world):
    uid, t1, t2 = world
    now = datetime.utcnow()
    _grant(app, uid, t1, now - timedelta(days=2), now - timedelta(minutes=12), 'plus')
    _grant(app, uid, t2, now - timedelta(hours=20), now + timedelta(hours=2))
    c, target = _login(app)
    assert target == '/dashboard'
    assert c.get('/dashboard').status_code == 200


def test_active_plan_without_chosen_test_suggests_library_at_login_only(app, world):
    uid, _, _ = world
    now = datetime.utcnow()
    _grant(app, uid, None, now - timedelta(hours=1), now + timedelta(hours=5))
    c, target = _login(app)
    assert target == '/library'
    assert c.get('/dashboard').status_code == 200


def test_account_card_has_a_single_notifications_item(app, world):
    c, _ = _login(app)
    html = c.get('/dashboard').get_data(as_text=True)
    assert html.count('fa-bell"></i> Notifications') == 1


def test_lighthouse_intro_only_on_first_dashboard_after_login(app, world):
    uid, t1, _ = world
    now = datetime.utcnow()
    _grant(app, uid, t1, now - timedelta(hours=1), now + timedelta(days=1))
    c, _ = _login(app)
    first = c.get('/dashboard').get_data(as_text=True)
    assert 'mhdr--intro' in first
    assert 'mhdr--intro' not in c.get('/dashboard').get_data(as_text=True)   # a plain reload: no intro
    c.get('/logout'); c2, _ = _login(app)
    assert 'mhdr--intro' in c2.get('/dashboard').get_data(as_text=True)       # next login: intro again
