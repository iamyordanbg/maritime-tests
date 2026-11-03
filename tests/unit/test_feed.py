"""Feed: login-only comments/likes, unique views, reply notifications."""
import pytest
from unittest.mock import patch
from werkzeug.security import generate_password_hash
from app.models import Post, PostComment, PostLike, PostView, User
from app.models.ticket import Ticket, TicketMessage


def _user(db, n):
    u = User(name=f"U{n}", email=f"feed{n}@test.bg", password=generate_password_hash("x"),
             plan="free", email_verified=True)
    db.session.add(u); db.session.commit()
    return u


@pytest.fixture
def setup(db):
    post = Post(title="Hello", body="Body")
    db.session.add(post)
    users = [_user(db, i) for i in range(3)]
    db.session.commit()
    yield post, users
    for m in (TicketMessage, Ticket, PostLike, PostView, PostComment, Post):
        m.query.delete()
    for u in users:
        db.session.delete(u)
    db.session.commit()


def _login(client, user):
    with client.session_transaction() as s:
        s['user_id'] = user.id


def test_anonymous_cannot_comment_or_like(client, setup):
    post, _ = setup
    assert client.post(f'/feed/comment/{post.id}', json={'body': 'hi'}).status_code == 401
    assert client.post(f'/feed/like/{post.id}').status_code == 401


def test_unknown_user_id_cannot_comment(client, setup):
    post, _ = setup
    with client.session_transaction() as s:
        s['user_id'] = 999999
    assert client.post(f'/feed/comment/{post.id}', json={'body': 'hi'}).status_code == 401


def test_like_toggle_and_latest_counts(client, setup):
    post, users = setup
    _login(client, users[0])
    assert client.post(f'/feed/like/{post.id}').get_json() == {'liked': True, 'likes': 1}
    item = client.get('/feed/latest').get_json()[0]
    assert item['likes'] == 1 and item['liked'] is True
    assert client.post(f'/feed/like/{post.id}').get_json() == {'liked': False, 'likes': 0}


def test_views_are_unique_per_viewer_and_comments_endpoint_does_not_count(client, setup, app):
    post, users = setup
    client.get(f'/feed/post/{post.id}'); client.get(f'/feed/post/{post.id}')
    assert client.get(f'/feed/post/{post.id}').get_json()['views'] == 1
    client.get(f'/feed/post/{post.id}/comments')
    _login(client, users[0])
    assert client.get(f'/feed/post/{post.id}').get_json()['views'] == 2
    other = app.test_client()
    assert other.get(f'/feed/post/{post.id}').get_json()['views'] == 3


def test_reply_notifies_previous_commenters_only(client, app, setup):
    post, (a, b, c) = setup
    with patch('app.services.email.send_post_reply_email_async') as mail:
        ca = app.test_client(); _login(ca, a)
        assert ca.post(f'/feed/comment/{post.id}', json={'body': 'first'}).status_code == 200
        assert Ticket.query.filter_by(type='notification').count() == 0   # nobody to notify yet
        cb = app.test_client(); _login(cb, b)
        cb.post(f'/feed/comment/{post.id}', json={'body': 'reply from b'})
        t = Ticket.query.filter_by(user_id=a.id, type='notification').one()
        msg = TicketMessage.query.filter_by(ticket_id=t.id).one()
        assert msg.sender == 'admin' and not msg.is_read and 'reply from b' in msg.body
        assert Ticket.query.filter_by(user_id=b.id, type='notification').count() == 0
        assert mail.call_count == 1 and mail.call_args[0][0] == a.email
        # a user who never commented gets nothing; unread count is exposed
        ca2 = app.test_client(); _login(ca2, a)
        assert ca2.get('/support/unread').get_json()['count'] == 1
        assert ca2.post(f'/support/tickets/{t.id}/reply', data={'body': 'x'}).status_code == 400
        cc = app.test_client(); _login(cc, c)
        assert cc.get('/support/unread').get_json()['count'] == 0
