"""News posts show likes / comments / shares to everybody; views are an admin-only figure."""
import pytest
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import Post, PostShare, PostView, User

H = {'X-Requested-With': 'XMLHttpRequest'}


@pytest.fixture
def world(app):
    with app.app_context():
        u = User(name="Reader", email="r1@test.bg", password=generate_password_hash("Test123"), plan="free", is_active=False, email_verified=True)
        a = User(name="Adm", email="adm1@test.bg", password=generate_password_hash("Test123"), plan="free", is_active=False, email_verified=True, is_admin=True)
        p = Post(title="P", body="Body", image_url="")
        db.session.add_all([u, a, p]); db.session.commit()
        ids = (u.id, a.id, p.id)
    yield ids
    with app.app_context():
        PostShare.query.delete(); PostView.query.delete()
        Post.query.filter_by(id=ids[2]).delete()
        User.query.filter(User.id.in_(ids[:2])).delete(synchronize_session=False)
        db.session.commit()


def _login(app, email):
    c = app.test_client()
    c.post('/login', data={'email': email, 'password': 'Test123'}, headers=H)
    return c


def test_views_only_for_admin(app, world):
    _, _, pid = world
    u, a = _login(app, 'r1@test.bg'), _login(app, 'adm1@test.bg')
    assert 'views' not in u.get(f'/feed/post/{pid}').get_json()
    assert 'views' not in u.get('/feed/latest?limit=5').get_json()[0]
    assert 'views' not in app.test_client().get('/feed/latest?limit=5').get_json()[0]
    assert a.get('/feed/latest?limit=5').get_json()[0]['views'] >= 1        # views are still counted
    assert a.get(f'/feed/post/{pid}').get_json()['views'] >= 1


def test_share_counted_once_per_user(app, world):
    _, _, pid = world
    u, a = _login(app, 'r1@test.bg'), _login(app, 'adm1@test.bg')
    assert app.test_client().post(f'/feed/share/{pid}').status_code == 401
    assert u.post(f'/feed/share/{pid}').get_json() == {'shares': 1}
    assert u.post(f'/feed/share/{pid}').get_json() == {'shares': 1}          # same user again: not counted twice
    assert a.post(f'/feed/share/{pid}').get_json() == {'shares': 2}
    assert u.get('/feed/latest?limit=5').get_json()[0]['shares'] == 2
    assert u.get(f'/feed/post/{pid}').get_json()['shares'] == 2
    assert u.post('/feed/share/999999').status_code == 404
