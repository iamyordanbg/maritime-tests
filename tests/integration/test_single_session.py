"""One active session per account: a new login signs the account out on the other device."""
import pytest

from app.models.user import User

AJAX = {'X-Requested-With': 'XMLHttpRequest'}


@pytest.fixture
def two_devices(app):
    return app.test_client(), app.test_client()


def _login(client, user):
    res = client.post('/login', data={'email': user.email, 'password': 'Test123'}, headers=AJAX)
    assert res.get_json()['success']


def test_second_login_signs_out_the_first_device(two_devices, db, basic_user):
    phone, desktop = two_devices
    _login(phone, basic_user)
    assert phone.get('/dashboard').status_code == 200
    _login(desktop, basic_user)
    assert desktop.get('/dashboard').status_code == 200
    res = phone.get('/dashboard')
    assert res.status_code == 302 and res.headers['Location'].endswith('/?login=1&replaced=1')
    assert phone.get('/dashboard').status_code == 302          # still signed out


@pytest.mark.parametrize('path', ['/ping', '/api/review/should-prompt'])
def test_signed_out_device_gets_json_401_for_api_and_ping(two_devices, db, basic_user, path):
    phone, desktop = two_devices
    _login(phone, basic_user)
    _login(desktop, basic_user)
    res = phone.get(path)
    assert res.status_code == 401 and res.get_json()['error'] == 'session_replaced'


def test_same_device_keeps_working_and_can_log_in_again(client, db, basic_user):
    _login(client, basic_user)
    for _ in range(3):
        assert client.get('/dashboard').status_code == 200
    client.get('/logout')
    _login(client, basic_user)
    assert client.get('/dashboard').status_code == 200


def test_signed_out_device_can_log_in_again_and_replaces_the_other(two_devices, db, basic_user):
    phone, desktop = two_devices
    _login(phone, basic_user)
    _login(desktop, basic_user)
    assert phone.get('/dashboard').status_code == 302
    _login(phone, basic_user)
    assert phone.get('/dashboard').status_code == 200
    assert desktop.get('/dashboard').status_code == 302


def test_different_accounts_do_not_affect_each_other(two_devices, db, basic_user, free_user):
    a, b = two_devices
    _login(a, basic_user)
    b.post('/login', data={'email': free_user.email, 'password': 'Test123'}, headers=AJAX)
    assert a.get('/dashboard').status_code == 200


def test_legacy_session_without_token_stays_valid(client, db, basic_user):
    with client.session_transaction() as s:
        s['user_id'] = basic_user.id
    assert User.query.get(basic_user.id).active_session_token is None
    assert client.get('/dashboard').status_code == 200


def test_legacy_session_is_signed_out_after_a_new_login(two_devices, db, basic_user):
    legacy, desktop = two_devices
    with legacy.session_transaction() as s:
        s['user_id'] = basic_user.id
    _login(desktop, basic_user)
    assert legacy.get('/dashboard').status_code == 302
