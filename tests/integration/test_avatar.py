"""Profile photo: upload, serve, remove, validation."""
import io
import pytest
from PIL import Image
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models.user import User


def _png(w=600, h=300, color=(200, 30, 30)):
    b = io.BytesIO(); Image.new('RGB', (w, h), color).save(b, 'PNG'); b.seek(0); return b


@pytest.fixture
def client(app):
    with app.app_context():
        u = User(name="Av User", email="av@test.bg", password=generate_password_hash("Test123"),
                 plan="free", is_active=False, email_verified=True)
        db.session.add(u); db.session.commit()
        uid = u.id
    c = app.test_client()
    c.post('/login', data={'email': 'av@test.bg', 'password': 'Test123'}, headers={'X-Requested-With': 'XMLHttpRequest'})
    yield c, uid
    with app.app_context():
        User.query.filter_by(id=uid).delete(); db.session.commit()


def test_upload_serves_square_jpeg_and_shows_in_pages(client):
    c, _ = client
    assert c.get('/settings/avatar').status_code == 404
    r = c.post('/settings/avatar', data={'avatar': (_png(), 'me.png')}, content_type='multipart/form-data')
    assert r.get_json() == {'success': True, 'version': 1}
    img = Image.open(io.BytesIO(c.get('/settings/avatar').data))
    assert img.format == 'JPEG' and img.size == (256, 256)
    assert '/settings/avatar?v=1' in c.get('/dashboard').get_data(as_text=True)


def test_remove_returns_to_initials(client):
    c, _ = client
    c.post('/settings/avatar', data={'avatar': (_png(), 'me.png')}, content_type='multipart/form-data')
    assert c.post('/settings/avatar/remove').get_json()['success']
    assert c.get('/settings/avatar').status_code == 404
    assert '/settings/avatar?v=' not in c.get('/dashboard').get_data(as_text=True)


@pytest.mark.parametrize('payload', [b'not an image', b'', b'<svg xmlns="http://www.w3.org/2000/svg"/>'])
def test_rejects_non_images(client, payload):
    c, _ = client
    r = c.post('/settings/avatar', data={'avatar': (io.BytesIO(payload), 'x.png')}, content_type='multipart/form-data')
    assert r.status_code == 400 and r.get_json()['success'] is False


def test_rejects_oversized_upload(client):
    c, _ = client
    r = c.post('/settings/avatar', data={'avatar': (io.BytesIO(b'0' * (5 * 1024 * 1024 + 10)), 'big.png')}, content_type='multipart/form-data')
    assert r.status_code == 400


def test_requires_login(app):
    c = app.test_client()
    assert c.get('/settings/avatar').status_code in (302, 401)
    assert c.post('/settings/avatar').status_code in (302, 401)


# ---------------------------------------------------------------------------
# Admin: Settings > Profile has Change / Remove photo and the sidebar shows the photo
# ---------------------------------------------------------------------------
def test_admin_can_set_and_remove_a_photo_from_the_admin_settings(app, db, admin_user):
    c = app.test_client()
    c.post('/login', data={'email': 'admin@test.bg', 'password': 'Admin123'}, headers={'X-Requested-With': 'XMLHttpRequest'})
    page = c.get('/admin').get_data(as_text=True)
    assert 'id="asm-avatar-change-btn"' in page and 'id="avatarFile"' in page and 'js/avatar.js' in page
    assert 'id="avatarRemoveBtn"' in page and 'hidden' in page.split('id="avatarRemoveBtn"')[1].split('>')[0]   # no photo yet
    try:
        r = c.post('/settings/avatar', data={'avatar': (_png(), 'me.png')}, content_type='multipart/form-data')
        assert r.get_json()['success']
        page = c.get('/admin').get_data(as_text=True)
        assert page.count('/settings/avatar?v=1') >= 2                      # sidebar button + Settings > Profile
        assert 'hidden' not in page.split('id="avatarRemoveBtn"')[1].split('>')[0]
        assert c.post('/settings/avatar/remove').get_json()['success']
        assert '/settings/avatar?v=' not in c.get('/admin').get_data(as_text=True)
    finally:
        admin_user.avatar_version, admin_user.avatar_data = 0, None
        db.session.commit()
