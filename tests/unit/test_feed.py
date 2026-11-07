"""Feed: login-only comments/likes, unique views, reply notifications."""
import pytest
from unittest.mock import patch
from werkzeug.security import generate_password_hash
from app.models import Post, PostComment, PostLike, PostView, Notification, User


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
    for m in (Notification, PostLike, PostView):
        m.query.delete()
    PostComment.query.update({'parent_id': None})
    for m in (PostComment, Post):
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
    from app.models import Post
    post, users = setup
    views = lambda: Post.query.get(post.id).views     # the API shows views to admins only; they are still counted for everybody
    client.get(f'/feed/post/{post.id}'); client.get(f'/feed/post/{post.id}')
    assert views() == 1
    client.get(f'/feed/post/{post.id}/comments')
    _login(client, users[0])
    client.get(f'/feed/post/{post.id}')
    assert views() == 2
    app.test_client().get(f'/feed/post/{post.id}')
    assert views() == 3


def test_comment_notifies_previous_commenters_only(client, app, setup):
    post, (a, b, c) = setup
    with patch('app.services.email.send_post_reply_email_async') as mail:
        ca = app.test_client(); _login(ca, a)
        assert ca.post(f'/feed/comment/{post.id}', json={'body': 'first'}).status_code == 200
        assert Notification.query.count() == 0   # nobody to notify yet
        cb = app.test_client(); _login(cb, b)
        cb.post(f'/feed/comment/{post.id}', json={'body': 'answer from b'})
        n = Notification.query.filter_by(user_id=a.id).one()
        assert n.post_id == post.id and n.kind == 'comment' and not n.is_read and 'answer from b' in n.body
        assert Notification.query.filter_by(user_id=b.id).count() == 0
        assert mail.call_count == 1 and mail.call_args[0][0] == a.email
        assert ca.get('/notifications/unread').get_json()['count'] == 1
        items = ca.get('/notifications').get_json()['items']
        assert items[0]['post_title'] == 'Hello' and items[0]['actor'] == 'U1'
        cc = app.test_client(); _login(cc, c)
        assert cc.get('/notifications/unread').get_json()['count'] == 0
        assert ca.post(f'/notifications/{n.id}/read').status_code == 200
        assert ca.get('/notifications/unread').get_json()['count'] == 0
        assert client.get('/notifications').status_code in (302, 401)   # login required


def test_reply_to_comment_is_threaded_and_notifies_its_author(client, app, setup):
    post, (a, b, c) = setup
    with patch('app.services.email.send_post_reply_email_async'):
        ca = app.test_client(); _login(ca, a)
        root = ca.post(f'/feed/comment/{post.id}', json={'body': 'root'}).get_json()
        cb = app.test_client(); _login(cb, b)
        cb.post(f'/feed/comment/{post.id}', json={'body': 'other'})
        cc = app.test_client(); _login(cc, c)
        r = cc.post(f'/feed/comment/{post.id}', json={'body': 'to a', 'parent_id': root['id']}).get_json()
        assert r['parent_id'] == root['id']
        assert Notification.query.filter_by(user_id=a.id, kind='reply').count() == 1
        assert Notification.query.filter_by(user_id=b.id, kind='comment').count() == 1
        comments = client.get(f'/feed/post/{post.id}/comments').get_json()['comments']
        assert [x['parent_id'] for x in comments] == [None, None, root['id']]
        assert cc.post(f'/feed/comment/{post.id}', json={'body': 'x', 'parent_id': 99999}).status_code == 400


def test_admin_is_shown_as_administrator(client, app, setup):
    post, (a, _, _) = setup
    a.is_admin = True; a.name = 'Администратор'
    from app.extensions import db
    db.session.commit()
    ca = app.test_client(); _login(ca, a)
    assert ca.post(f'/feed/comment/{post.id}', json={'body': 'hi'}).get_json()['user'] == 'Administrator'
    a.is_admin = False; db.session.commit()
