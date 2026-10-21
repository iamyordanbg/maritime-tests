"""
tests/integration/test_library_first_selection.py
=================================================
Веднага след плащане на Basic/Plus планът още няма избран тест. /library трябва да
подаде needs_first_selection=True (library.js тогава не заключва нито един тест),
а след избора - False (останалите тестове се заключват както преди).
"""

import json
import re
from datetime import datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

from app.models.plan_grant import PlanGrant
from app.models.test import Test
from app.models.user import User


@pytest.fixture
def paid_user(db):
    user = User(name="Pay Er", email="payer@test.bg", password=generate_password_hash("Test123"),
                plan="basic", is_active=True, is_admin=False, email_verified=True)
    test = Test(title="First Pick", level="Operational Level", category="deck", is_demo=False,
                questions_json=json.dumps([{"id": 1, "question": "Q",
                                            "options": [{"text": "A", "isCorrect": True}]}]))
    db.session.add_all([user, test])
    db.session.commit()
    grant = PlanGrant(user_id=user.id, plan='basic', quota=5, tests_used=0, library_test_id=None,
                      activated_at=datetime.utcnow(), expires_at=datetime.utcnow() + timedelta(days=7))
    db.session.add(grant)
    db.session.commit()
    yield user, test, grant
    db.session.delete(grant)
    db.session.delete(test)
    db.session.delete(user)
    db.session.commit()


def _lib_state(client):
    client.post('/login', data={'email': 'payer@test.bg', 'password': 'Test123'},
                headers={'X-Requested-With': 'XMLHttpRequest'})
    html = client.get('/library').get_data(as_text=True)
    return json.loads(re.search(r'var LIB = (\{.*?\});', html, re.S).group(1))


def test_fresh_paid_plan_needs_first_selection(client, paid_user):
    lib = _lib_state(client)
    assert lib['is_premium'] is True
    assert lib['needs_first_selection'] is True


def test_after_selection_first_selection_not_needed(client, db, paid_user):
    _, test, grant = paid_user
    grant.library_test_id = test.id
    db.session.commit()
    lib = _lib_state(client)
    assert lib['needs_first_selection'] is False
    assert lib['selected_test_ids'] == [test.id]
