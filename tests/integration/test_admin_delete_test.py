"""
tests/integration/test_admin_delete_test.py
===========================================
Админ триене на тест: трябва да изтрие и ВСИЧКО свързано (free_session,
резултати, изключения, снимки), да зачисти избора на тест в акаунтите и
плановете, а при грешка да не губи нищо (rollback + JSON съобщение).
Production Postgres налага FK ограничения - тук ги включваме и в SQLite.
"""
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from app.models.all_mistakes_exclusion import AllMistakesExclusion
from app.models.free_session import FreeSession
from app.models.payment import Payment
from app.models.plan_grant import PlanGrant
from app.models.result import TestResult
from app.models.test import Test, TestImage

AJAX = {'X-Requested-With': 'XMLHttpRequest'}


@pytest.fixture
def fk_on(db, admin_user, free_user):
    """FK ON за теста; зависи от user фикстурите, за да се почисти ПРЕДИ тях."""
    db.session.commit()
    db.session.execute(text('PRAGMA foreign_keys=ON'))
    yield
    db.session.rollback()
    from app.models.user import User
    for model in (FreeSession, AllMistakesExclusion, TestResult, TestImage):
        model.query.delete()
    User.query.update({'library_test_id': None})
    PlanGrant.query.delete()
    Payment.query.delete()
    Test.query.filter(Test.title == 'To Delete').delete()
    db.session.commit()
    db.session.execute(text('PRAGMA foreign_keys=OFF'))


def _login_admin(client, admin_user):
    client.post('/login', data={'email': admin_user.email, 'password': 'Admin123'}, headers=AJAX)


def _make_test(db, user):
    test = Test(title='To Delete', category='deck', level='Operational Level',
                questions_json=json.dumps([{'id': 1, 'question': 'Q', 'options': []}]))
    db.session.add(test)
    db.session.commit()
    now = datetime.utcnow()
    db.session.add(FreeSession(user_id=user.id, test_id=test.id, activated_at=now,
                               expires_at=now + timedelta(days=1)))
    db.session.add(AllMistakesExclusion(user_id=user.id, test_id=test.id, question_id='1'))
    db.session.add(TestImage(test_id=test.id, question_id=1, image_data='AAAA', format='png', storage='db'))
    db.session.add(TestResult(user_id=user.id, test_id=test.id, score=1, total=1, percent=100,
                              answers_json='{}', taken_at=now))
    user.library_test_id = test.id
    user.library_selected_at = now
    db.session.commit()
    return test


def test_fk_is_really_enforced_in_this_suite(db, free_user, fk_on):
    """Контрола: без чистене на free_session триенето на теста пада, както в Postgres."""
    test = _make_test(db, free_user)
    tid = test.id
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        db.session.delete(test)
        db.session.commit()
    db.session.rollback()
    assert Test.query.get(tid) is not None


def test_delete_removes_test_and_everything_linked(client, db, admin_user, free_user, fk_on):
    test = _make_test(db, free_user)
    tid, uid = test.id, free_user.id
    now = datetime.utcnow()
    pay = Payment(user_id=uid, plan='basic', amount=5.0, paid_at=now)
    db.session.add(pay)
    db.session.flush()
    grant = PlanGrant(user_id=uid, plan='basic', quota=3, activated_at=now,
                      expires_at=now + timedelta(days=1), payment_id=pay.id,
                      library_test_id=tid, library_selected_at=now)
    db.session.add(grant)
    db.session.commit()
    gid, pid = grant.id, pay.id
    _login_admin(client, admin_user)

    resp = client.post(f'/admin/tests/{tid}/delete')
    assert resp.status_code == 200 and resp.get_json()['success'] is True

    db.session.expire_all()
    assert Test.query.get(tid) is None
    assert FreeSession.query.filter_by(test_id=tid).count() == 0
    assert AllMistakesExclusion.query.filter_by(test_id=tid).count() == 0
    assert TestImage.query.filter_by(test_id=tid).count() == 0
    assert TestResult.query.filter_by(test_id=tid).count() == 0
    from app.models.user import User
    u = User.query.get(uid)
    assert u.library_test_id is None and u.library_selected_at is None
    g = PlanGrant.query.get(gid)
    assert g is not None and g.library_test_id is None and g.library_selected_at is None
    assert Payment.query.get(pid) is not None   # плащането/планът остават


def test_delete_failure_rolls_back_and_returns_json(client, db, admin_user, free_user, monkeypatch, fk_on):
    test = _make_test(db, free_user)
    tid = test.id
    _login_admin(client, admin_user)
    from app.services import test_deletion

    def boom(_):
        raise RuntimeError('boom')
    monkeypatch.setattr(test_deletion, 'remove_test_image_rows', boom)

    resp = client.post(f'/admin/tests/{tid}/delete')
    assert resp.status_code == 500
    body = resp.get_json()
    assert body['success'] is False and 'error' in body

    db.session.expire_all()
    assert Test.query.get(tid) is not None                       # нищо не е изтрито
    assert FreeSession.query.filter_by(test_id=tid).count() == 1
    assert TestImage.query.filter_by(test_id=tid).count() == 1
    assert TestResult.query.filter_by(test_id=tid).count() == 1
    from app.models.user import User
    assert User.query.get(free_user.id).library_test_id == tid
