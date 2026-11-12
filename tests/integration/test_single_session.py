"""Device rule: one active session per account. A new login on any device signs the previous one out."""
import pytest

from app.models.user import User
from app.services import session_guard

AJAX = {'X-Requested-With': 'XMLHttpRequest'}
UA = {
    'iphone': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    'android_phone': 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36',
    'windows': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'ipad': 'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    'android_tablet': 'Mozilla/5.0 (Linux; Android 13; SM-X700) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
}


@pytest.fixture
def device(app):
    def make(kind):
        client = app.test_client()
        client.environ_base['HTTP_USER_AGENT'] = UA[kind]
        return client
    return make


def _login(client, user):
    res = client.post('/login', data={'email': user.email, 'password': 'Test123'}, headers=AJAX)
    assert res.get_json()['success']


def _ok(client):
    return client.get('/dashboard').status_code == 200


@pytest.mark.parametrize('kind,slot', [('iphone', 'phone'), ('android_phone', 'phone'), ('windows', 'computer'),
                                       ('ipad', 'computer'), ('android_tablet', 'computer')])
def test_device_slot_by_user_agent(app, kind, slot):
    with app.test_request_context('/', headers={'User-Agent': UA[kind]}):
        assert session_guard.device_slot() == slot


@pytest.mark.parametrize('first,second', [('iphone', 'windows'), ('windows', 'iphone'), ('iphone', 'android_phone'),
                                          ('windows', 'windows'), ('windows', 'ipad')])
def test_new_login_signs_out_the_previous_device_whatever_the_type(device, db, basic_user, first, second):
    a, b = device(first), device(second)
    _login(a, basic_user)
    assert _ok(a)
    _login(b, basic_user)
    assert _ok(b)
    res = a.get('/dashboard')
    assert res.status_code == 302 and res.headers['Location'].startswith('/?replaced=1')


def test_redirect_carries_the_ip_of_the_new_login(device, db, basic_user):
    a, b = device('iphone'), device('windows')
    _login(a, basic_user)
    b.environ_base['REMOTE_ADDR'] = '203.0.113.7'
    _login(b, basic_user)
    assert a.get('/dashboard').headers['Location'] == '/?replaced=1&ip=203.0.113.7'


@pytest.mark.parametrize('path', ['/ping', '/api/review/should-prompt'])
def test_signed_out_device_gets_json_401_with_ip(device, db, basic_user, path):
    a, b = device('iphone'), device('windows')
    _login(a, basic_user)
    b.environ_base['REMOTE_ADDR'] = '203.0.113.7'
    _login(b, basic_user)
    res = a.get(path)
    body = res.get_json()
    assert res.status_code == 401 and body['error'] == 'session_replaced' and body['ip'] == '203.0.113.7'
    assert 'another device' in body['message']


def test_same_device_keeps_working_and_can_log_in_again(device, db, basic_user):
    pc = device('windows')
    _login(pc, basic_user)
    for _ in range(3):
        assert _ok(pc)
    pc.get('/logout')
    _login(pc, basic_user)
    assert _ok(pc)


def test_signed_out_device_logs_in_again_and_replaces_the_other(device, db, basic_user):
    phone, pc = device('iphone'), device('windows')
    _login(phone, basic_user)
    _login(pc, basic_user)
    assert phone.get('/dashboard').status_code == 302
    _login(phone, basic_user)            # the kicked device holds its old cookie and must still be able to sign in
    assert _ok(phone) and pc.get('/dashboard').status_code == 302


def test_different_accounts_do_not_affect_each_other(device, db, basic_user, free_user):
    a, b = device('iphone'), device('iphone')
    _login(a, basic_user)
    b.post('/login', data={'email': free_user.email, 'password': 'Test123'}, headers=AJAX)
    assert _ok(a)


def test_legacy_session_stays_valid_until_the_next_login(device, db, basic_user):
    legacy, other = device('iphone'), device('windows')
    with legacy.session_transaction() as s:
        s['user_id'] = basic_user.id
    assert User.query.get(basic_user.id).session_token is None and _ok(legacy)
    _login(other, basic_user)
    assert legacy.get('/dashboard').status_code == 302


def test_sign_out_all_devices_ends_every_session(device, db, basic_user):
    phone, pc = device('iphone'), device('windows')
    _login(phone, basic_user)
    _login(pc, basic_user)
    res = pc.post('/settings/sign-out-all')
    assert res.get_json()['success']
    assert pc.get('/dashboard').status_code == 302 and phone.get('/dashboard').status_code == 302
    _login(pc, basic_user)               # signing in again works
    assert _ok(pc)


def test_sign_out_all_requires_login(device, db):
    assert device('windows').post('/settings/sign-out-all').status_code in (302, 401)


def test_privacy_tab_has_the_sign_out_all_button(device, db, basic_user):
    pc = device('windows')
    _login(pc, basic_user)
    html = pc.get('/dashboard').get_data(as_text=True)
    assert 'Sign out of all devices' in html and 'signOutAllDevices' in html


def test_landing_has_the_replaced_popup(client):
    html = client.get('/').get_data(as_text=True)
    assert 'id="deviceNoticeModal"' in html and 'Sign out of all devices' in html and 'change your password' in html


def test_library_popup_mentions_the_device_rule(device, db, basic_user):
    pc = device('windows')
    _login(pc, basic_user)
    html = pc.get('/library').get_data(as_text=True)
    assert session_guard.DEVICE_POLICY_NOTICE in html
