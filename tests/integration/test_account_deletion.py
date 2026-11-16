"""
tests/integration/test_account_deletion.py
==========================================
Изтриването на акаунт е АНОНИМИЗИРАНЕ: личните данни (име, имейл, IP история,
известия) се махат и вход вече е невъзможен, но плащанията, плановете,
резултатите и коментарите се запазват. Същият имейл може да се регистрира пак.
"""
import json
from datetime import datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

from app.models.login_event import LoginEvent
from app.models.notification import Notification
from app.models.payment import Payment
from app.models.plan_grant import PlanGrant
from app.models.post import Post, PostComment
from app.models.result import TestResult
from app.models.review import Review
from app.models.test import Test
from app.models.user import User
from app.services import account_deletion
from app.services.feed import display_name

AJAX = {'X-Requested-With': 'XMLHttpRequest'}
EMAIL = 'leaving@test.bg'


@pytest.fixture
def victim(db):
    """Потребител с плащане, план, резултат, коментар, отзив, IP запис и известие."""
    now = datetime.utcnow()
    u = User(name='Ivan Petrov', email=EMAIL, password=generate_password_hash('Test123'),
             nick='Ivo', firstname='Ivan', lastname='Petrov', company='ACME Ltd', rank='Master',
             google_id='g-123', google_picture_url='http://x/y.png', avatar_version=3,
             plan='basic', is_active=True, email_verified=True, session_token='tok')
    db.session.add(u)
    test = Test(title='T', category='deck', level='Operational Level', questions_json=json.dumps([]))
    post = Post(title='P', body='b')
    db.session.add_all([test, post])
    db.session.commit()
    pay = Payment(user_id=u.id, plan='basic', amount=9.0, paid_at=now)
    db.session.add(pay)
    db.session.flush()
    db.session.add_all([
        PlanGrant(user_id=u.id, plan='basic', quota=3, activated_at=now,
                  expires_at=now + timedelta(days=1), payment_id=pay.id),
        TestResult(user_id=u.id, test_id=test.id, score=1, total=1, percent=100, answers_json='{}', taken_at=now),
        PostComment(post_id=post.id, user_id=u.id, body='Nice post'),
        Review(user_id=u.id, stars=5, text='Great', visibility='account', display_name='Ivan Petrov',
               display_picture_url='http://x/y.png', status='approved'),
        LoginEvent(user_id=u.id, device_id='d', slot='computer', ip='1.2.3.4', created_at=now, last_seen_at=now),
        Notification(user_id=u.id, post_id=post.id, kind='reply', actor_name='Someone', body='hi'),
    ])
    db.session.commit()
    ids = dict(uid=u.id, pid=pay.id, tid=test.id, post=post.id)
    yield ids
    db.session.rollback()
    for m in (Notification, LoginEvent, Review, PostComment, TestResult, PlanGrant, Payment):
        m.query.delete()
    User.query.filter(User.id == ids['uid']).delete()
    Test.query.filter_by(id=ids['tid']).delete()
    Post.query.filter_by(id=ids['post']).delete()
    db.session.commit()


def _assert_anonymised(db, ids):
    db.session.expire_all()
    u = User.query.get(ids['uid'])
    assert u.deleted_at is not None
    assert u.name == 'Deleted user' and u.email == f"deleted-{ids['uid']}@deleted.invalid"
    for f in ('nick', 'firstname', 'lastname', 'company', 'rank'):
        assert getattr(u, f) == ''
    assert u.google_id is None and u.google_picture_url is None and u.avatar_version == 0
    assert u.session_token is None and u.email_verified is False
    # личното се маха
    assert LoginEvent.query.filter_by(user_id=ids['uid']).count() == 0
    assert Notification.query.filter_by(user_id=ids['uid']).count() == 0
    # счетоводство и история се запазват
    assert Payment.query.get(ids['pid']) is not None
    assert PlanGrant.query.filter_by(user_id=ids['uid']).count() == 1
    assert TestResult.query.filter_by(user_id=ids['uid']).count() == 1
    # коментарът остава, показва се като "Deleted user"
    c = PostComment.query.filter_by(user_id=ids['uid']).first()
    assert c.body == 'Nice post' and display_name(c.user) == 'Deleted user'
    # отзивът остава, но анонимен
    r = Review.query.filter_by(user_id=ids['uid']).first()
    assert r.text == 'Great' and r.visibility == 'anonymous'
    assert r.display_name == 'Anonymous Sailor' and r.display_picture_url is None


def test_service_anonymises_and_keeps_history(db, victim):
    account_deletion.delete_account(User.query.get(victim['uid']))
    _assert_anonymised(db, victim)


def test_deleted_user_cannot_log_in_and_email_is_free_again(client, db, victim):
    account_deletion.delete_account(User.query.get(victim['uid']))
    r = client.post('/login', data={'email': EMAIL, 'password': 'Test123'}, headers=AJAX)
    assert not (r.get_json() or {}).get('success')
    r = client.post('/login', data={'email': f"deleted-{victim['uid']}@deleted.invalid", 'password': 'Test123'}, headers=AJAX)
    assert not (r.get_json() or {}).get('success')
    # същият имейл вече е свободен (уникалното ограничение не пречи)
    again = User(name='New Ivan', email=EMAIL, password=generate_password_hash('x'))
    db.session.add(again)
    db.session.commit()
    assert User.query.filter_by(email=EMAIL).count() == 1
    db.session.delete(again)
    db.session.commit()


def test_admin_delete_route_anonymises(client, db, admin_user, victim):
    client.post('/login', data={'email': admin_user.email, 'password': 'Admin123'}, headers=AJAX)
    resp = client.post(f"/admin/users/{victim['uid']}/delete")
    assert resp.status_code == 200 and resp.get_json()['success'] is True
    _assert_anonymised(db, victim)
    page = client.get('/admin/users').get_data(as_text=True)
    assert 'deleted.invalid' not in page and EMAIL not in page      # изчезва от списъка с Sailors


def test_admin_cannot_delete_admin(client, db, admin_user):
    client.post('/login', data={'email': admin_user.email, 'password': 'Admin123'}, headers=AJAX)
    resp = client.post(f'/admin/users/{admin_user.id}/delete')
    assert resp.get_json()['success'] is False
    db.session.expire_all()
    assert User.query.get(admin_user.id).deleted_at is None


def test_user_self_delete_keeps_payments(client, db, victim):
    client.post('/login', data={'email': EMAIL, 'password': 'Test123'}, headers=AJAX)
    resp = client.post('/settings/delete-account')
    assert resp.get_json()['success'] is True
    _assert_anonymised(db, victim)


def test_failure_rolls_back(db, victim, monkeypatch):
    u = User.query.get(victim['uid'])

    def boom(*a, **k):
        raise RuntimeError('boom')
    monkeypatch.setattr(account_deletion, 'generate_password_hash', boom)
    with pytest.raises(RuntimeError):
        account_deletion.delete_account(u)
    db.session.expire_all()
    u = User.query.get(victim['uid'])
    assert u.deleted_at is None and u.email == EMAIL and u.name == 'Ivan Petrov'
    assert LoginEvent.query.filter_by(user_id=victim['uid']).count() == 1


def test_open_session_of_deleted_account_is_signed_out(client, db, admin_user, victim):
    other = client.application.test_client()
    other.post('/login', data={'email': EMAIL, 'password': 'Test123'}, headers=AJAX)
    assert other.get('/ping', headers=AJAX).status_code == 200
    admin = client.application.test_client()
    admin.post('/login', data={'email': admin_user.email, 'password': 'Admin123'}, headers=AJAX)
    assert admin.post(f"/admin/users/{victim['uid']}/delete").get_json()['success'] is True
    resp = other.get('/ping', headers=AJAX)
    assert resp.status_code == 401 and resp.get_json()['error'] == 'account_deleted'
    with other.session_transaction() as sess:
        assert 'user_id' not in sess
