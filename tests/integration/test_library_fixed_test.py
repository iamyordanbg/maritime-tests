"""
tests/integration/test_library_fixed_test.py
============================================
Платен план: веднъж зареденият тест е фиксиран - Библиотеката е информативна, без преизбиране.
"""
import json
from datetime import datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

from app.models.user import User
from app.models.test import Test
from app.models.plan_grant import PlanGrant
from app.services.dashboard_stats import build_library_view_data

AJAX = {'X-Requested-With': 'XMLHttpRequest'}
Q = [{'id': 1, 'question': 'Q', 'options': [{'text': 'a', 'isCorrect': True}]}]


@pytest.fixture
def setup(db):
    t1 = Test(title='First', level='Operational Level', category='deck', is_demo=False, questions_json=json.dumps(Q))
    t2 = Test(title='Second', level='Operational Level', category='deck', is_demo=False, questions_json=json.dumps(Q))
    u = User(name='Lib', email='lib@fixed.test', password=generate_password_hash('Test123'),
             plan='plus', is_active=True, is_admin=False, email_verified=True)
    db.session.add_all([t1, t2, u])
    db.session.commit()
    yield u, t1, t2
    db.session.rollback()
    PlanGrant.query.delete()
    for obj in (u, t1, t2):
        db.session.delete(obj)
    db.session.commit()


def _grant(db, u, test_id):
    now = datetime.utcnow()
    g = PlanGrant(user_id=u.id, plan='plus', quota=15, library_test_id=test_id, activated_at=now,
                  expires_at=now + timedelta(days=1))
    db.session.add(g)
    db.session.commit()
    return g


def _login(client, u):
    client.post('/login', data={'email': u.email, 'password': 'Test123'}, headers=AJAX)


def test_loaded_test_is_not_awaiting_selection_even_with_single_plan(db, setup):
    u, t1, t2 = setup
    _grant(db, u, t1.id)
    _, state, _, _ = build_library_view_data(u, None, None, None)
    assert state['selected_test_ids'] == [t1.id]
    assert state['awaiting_selection'] is False and state['has_unassigned_plan_grant'] is False


def test_exhausted_quota_does_not_reopen_selection(db, setup):
    u, t1, t2 = setup
    g = _grant(db, u, t1.id)
    g.quota = 0
    db.session.commit()
    _, state, _, _ = build_library_view_data(u, None, None, None)
    assert state['awaiting_selection'] is False


def test_unassigned_plan_still_allows_first_pick(db, setup):
    u, t1, t2 = setup
    _grant(db, u, None)
    _, state, _, _ = build_library_view_data(u, None, None, None)
    assert state['awaiting_selection'] is True and state['has_unassigned_plan_grant'] is True


def test_select_rejected_when_test_already_loaded(client, db, setup):
    u, t1, t2 = setup
    g = _grant(db, u, t1.id)
    _login(client, u)
    resp = client.post('/library/select', json={'test_id': t2.id})
    assert resp.status_code == 400 and resp.get_json()['success'] is False
    db.session.expire_all()
    assert PlanGrant.query.get(g.id).library_test_id == t1.id


def test_select_works_for_unassigned_plan(client, db, setup):
    u, t1, t2 = setup
    g = _grant(db, u, None)
    _login(client, u)
    assert client.post('/library/select', json={'test_id': t2.id}).get_json()['success'] is True
    db.session.expire_all()
    assert PlanGrant.query.get(g.id).library_test_id == t2.id
