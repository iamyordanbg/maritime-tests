"""Cloudflare Turnstile on login/register: off without keys, fail-closed when keys are set."""
import pytest
import requests

from app.services import turnstile

AJAX = {'X-Requested-With': 'XMLHttpRequest'}


class _Resp:
    def __init__(self, ok):
        self._ok = ok

    def json(self):
        return {'success': self._ok}


@pytest.fixture
def keys(app):
    app.config.update(RECAPTCHA_SITE_KEY='site-key-x', RECAPTCHA_SECRET_KEY='secret-x')
    yield
    app.config.update(RECAPTCHA_SITE_KEY='', RECAPTCHA_SECRET_KEY='')


def _login(client, user, **extra):
    return client.post('/login', data={'email': user.email, 'password': 'Test123', **extra}, headers=AJAX)


def test_off_without_keys(client, db, basic_user):
    assert _login(client, basic_user).get_json()['success']
    assert b'cf-turnstile' not in client.get('/?login=1').data.replace(b'cf-turnstile-response', b'')


def test_widget_rendered_when_enabled(client, keys):
    html = client.get('/').data
    assert b'class="cf-turnstile' in html and b'data-sitekey="site-key-x"' in html
    assert b'challenges.cloudflare.com/turnstile/v0/api.js' in html


def test_login_without_token_rejected(client, db, basic_user, keys):
    res = _login(client, basic_user)
    assert res.status_code == 400 and 'Anti-bot' in res.get_json()['message']


def test_login_invalid_token_rejected(client, db, basic_user, keys, monkeypatch):
    monkeypatch.setattr(turnstile.requests, 'post', lambda *a, **k: _Resp(False))
    assert _login(client, basic_user, **{'cf-turnstile-response': 'bad'}).status_code == 400


def test_login_valid_token_ok_and_secret_sent(client, db, basic_user, keys, monkeypatch):
    seen = {}

    def fake(url, **kw):
        seen.update(url=url, **kw)
        return _Resp(True)
    monkeypatch.setattr(turnstile.requests, 'post', fake)
    assert _login(client, basic_user, **{'cf-turnstile-response': 'good'}).get_json()['success']
    assert seen['url'] == turnstile.VERIFY_URL and seen['data']['secret'] == 'secret-x' and seen['data']['response'] == 'good'


def test_cloudflare_unreachable_fails_closed(client, db, basic_user, keys, monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError()
    monkeypatch.setattr(turnstile.requests, 'post', boom)
    assert _login(client, basic_user, **{'cf-turnstile-response': 'x'}).status_code == 400


def test_register_rejected_without_token_and_creates_no_user(client, db, keys):
    from app.models.user import User
    res = client.post('/register', data={'email': 'bot@x.com', 'password': 'abc12345'})
    assert b'Anti-bot verification failed' in res.data
    assert User.query.filter_by(email='bot@x.com').first() is None


def test_register_valid_token_passes_check(client, db, keys, monkeypatch):
    monkeypatch.setattr(turnstile.requests, 'post', lambda *a, **k: _Resp(True))
    res = client.post('/register', data={'email': 'human@x.com', 'password': 'abc12345', 'cf-turnstile-response': 't'})
    assert b'Anti-bot verification failed' not in res.data
