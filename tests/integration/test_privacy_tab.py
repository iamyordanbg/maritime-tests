"""Settings > Privacy: e-mail switch, data download, legal links."""
import json
import pytest
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models.user import User


@pytest.fixture
def client(app):
    with app.app_context():
        u = User(name="Priv User", email="priv@test.bg", password=generate_password_hash("Test123"),
                 plan="free", is_active=False, email_verified=True)
        db.session.add(u); db.session.commit()
        uid = u.id
    c = app.test_client()
    c.post('/login', data={'email': 'priv@test.bg', 'password': 'Test123'}, headers={'X-Requested-With': 'XMLHttpRequest'})
    yield c, uid
    with app.app_context():
        User.query.filter_by(id=uid).delete(); db.session.commit()


def test_privacy_tab_has_real_content(client):
    c, _ = client
    html = c.get('/dashboard').get_data(as_text=True)
    assert 'Coming soon' not in html.split('stab-content-privacy')[1].split('stab-content-billing')[0]
    assert 'privacyEmailToggle' in html and 'checked' in html.split('privacyEmailToggle')[1][:300]
    assert 'settings/export' in html and '/privacy' in html and '/terms' in html and '/cookies' in html


def test_email_switch_is_saved_and_shown(app, client):
    c, uid = client
    assert c.post('/settings/notifications', json={'notif_subscription': False}).get_json()['success']
    with app.app_context():
        assert User.query.get(uid).notif_subscription is False
    html = c.get('/dashboard').get_data(as_text=True)
    assert 'checked' not in html.split('privacyEmailToggle')[1][:300]


def test_export_contains_own_data_and_no_secrets(client):
    c, _ = client
    r = c.get('/settings/export')
    assert r.status_code == 200 and 'attachment' in r.headers['Content-Disposition']
    data = json.loads(r.get_data(as_text=True))
    assert data['profile']['email'] == 'priv@test.bg'
    assert set(data) >= {'profile', 'test_results', 'payments', 'comments'}
    raw = r.get_data(as_text=True)
    assert 'password' not in raw and 'otp' not in raw and 'token' not in raw


def test_export_requires_login(app):
    assert app.test_client().get('/settings/export').status_code in (302, 401)
