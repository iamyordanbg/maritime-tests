"""A user whose comment gets a reply sees a notification; the account menu has an entry on every device class."""
import pytest
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import Post, PostComment, User
from app.models.notification import Notification

H = {'X-Requested-With': 'XMLHttpRequest'}


@pytest.fixture
def world(app):
    with app.app_context():
        a = User(name="Author", email="author@test.bg", password=generate_password_hash("Test123"), plan="free", is_active=False, email_verified=True)
        b = User(name="Replier", email="replier@test.bg", password=generate_password_hash("Test123"), plan="free", is_active=False, email_verified=True)
        p = Post(title="Notif post", body="x", image_url="")
        db.session.add_all([a, b, p]); db.session.commit()
        ids = (a.id, b.id, p.id)
    yield ids
    with app.app_context():
        Notification.query.delete()
        PostComment.query.delete()
        Post.query.filter_by(id=ids[2]).delete()
        User.query.filter(User.id.in_(ids[:2])).delete(synchronize_session=False)
        db.session.commit()


def _login(app, email):
    c = app.test_client()
    c.post('/login', data={'email': email, 'password': 'Test123'}, headers=H)
    return c


def test_reply_creates_notification_for_comment_author(app, world):
    _, _, pid = world
    a, b = _login(app, 'author@test.bg'), _login(app, 'replier@test.bg')
    cid = a.post(f'/feed/comment/{pid}', json={'body': 'mine'}).get_json()['id']
    assert a.get('/notifications/unread').get_json()['count'] == 0       # own comment: nothing
    assert b.post(f'/feed/comment/{pid}', json={'body': 'answer', 'parent_id': cid}).status_code == 200
    assert a.get('/notifications/unread').get_json()['count'] == 1
    items = a.get('/notifications').get_json()['items']
    assert items[0]['kind'] == 'reply' and items[0]['post_id'] == pid and items[0]['actor'] == 'Replier'
    assert b.get('/notifications/unread').get_json()['count'] == 0       # replier is not notified of own reply


def test_notifications_entry_in_every_layout(app, world):
    a = _login(app, 'author@test.bg')
    html = a.get('/dashboard').get_data(as_text=True)
    assert 'sidebar-notif-link' in html and 'data-notif-dot' in html       # desktop / tablet sidebar
    assert 'mobile-more-item' in html and 'openNotifications' in html      # phone account menu
