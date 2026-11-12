"""Device rule: 1 phone + 1 computer/tablet per account. A new login only replaces the device of its own kind."""
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


def test_phone_and_computer_can_be_signed_in_together(device, db, basic_user):
    phone, pc = device('iphone'), device('windows')
    _login(phone, basic_user)
    _login(pc, basic_user)
    assert _ok(phone) and _ok(pc)


def test_second_phone_signs_out_the_first_phone_only(device, db, basic_user):
    phone1, phone2, pc = device('iphone'), device('android_phone'), device('windows')
    _login(phone1, basic_user)
    _login(pc, basic_user)
    _login(phone2, basic_user)
    res = phone1.get('/dashboard')
    assert res.status_code == 302 and res.headers['Location'].endswith('/?replaced=phone')
    assert _ok(phone2) and _ok(pc)


def test_second_computer_signs_out_the_first_computer_only(device, db, basic_user):
    pc1, pc2, phone = device('windows'), device('windows'), device('iphone')
    _login(pc1, basic_user)
    _login(phone, basic_user)
    _login(pc2, basic_user)
    res = pc1.get('/dashboard')
    assert res.status_code == 302 and res.headers['Location'].endswith('/?replaced=computer')
    assert _ok(pc2) and _ok(phone)


def test_tablet_shares_the_computer_slot(device, db, basic_user):
    pc, tablet = device('windows'), device('ipad')
    _login(pc, basic_user)
    _login(tablet, basic_user)
    assert _ok(tablet) and pc.get('/dashboard').status_code == 302


@pytest.mark.parametrize('path', ['/ping', '/api/review/should-prompt'])
def test_signed_out_device_gets_json_401_with_slot(device, db, basic_user, path):
    phone1, phone2 = device('iphone'), device('iphone')
    _login(phone1, basic_user)
    _login(phone2, basic_user)
    res = phone1.get(path)
    body = res.get_json()
    assert res.status_code == 401 and body['error'] == 'session_replaced' and body['slot'] == 'phone'
    assert 'another phone' in body['message']


def test_same_device_keeps_working_and_can_log_in_again(device, db, basic_user):
    pc = device('windows')
    _login(pc, basic_user)
    for _ in range(3):
        assert _ok(pc)
    pc.get('/logout')
    _login(pc, basic_user)
    assert _ok(pc)


def test_signed_out_device_logs_in_again_and_replaces_the_other(device, db, basic_user):
    phone1, phone2 = device('iphone'), device('iphone')
    _login(phone1, basic_user)
    _login(phone2, basic_user)
    assert phone1.get('/dashboard').status_code == 302
    _login(phone1, basic_user)
    assert _ok(phone1) and phone2.get('/dashboard').status_code == 302


def test_different_accounts_do_not_affect_each_other(device, db, basic_user, free_user):
    a, b = device('iphone'), device('iphone')
    _login(a, basic_user)
    b.post('/login', data={'email': free_user.email, 'password': 'Test123'}, headers=AJAX)
    assert _ok(a)


def test_legacy_session_stays_valid_until_its_slot_is_taken(device, db, basic_user):
    legacy, other_phone, pc = device('iphone'), device('android_phone'), device('windows')
    with legacy.session_transaction() as s:
        s['user_id'] = basic_user.id
    assert User.query.get(basic_user.id).phone_session_token is None and _ok(legacy)
    _login(pc, basic_user)               # a computer login does not touch the legacy phone session
    assert _ok(legacy)
    _login(other_phone, basic_user)      # another phone takes the phone slot
    assert legacy.get('/dashboard').status_code == 302


def test_library_popup_mentions_the_device_rule(device, db, basic_user):
    pc = device('windows')
    _login(pc, basic_user)
    html = pc.get('/library').get_data(as_text=True)
    assert session_guard.DEVICE_POLICY_NOTICE in html


def test_kicked_device_can_sign_in_again_with_its_old_cookie(device, db, basic_user):
    phone1, phone2 = device('iphone'), device('android_phone')
    _login(phone1, basic_user)
    _login(phone2, basic_user)          # phone1 is now replaced but still holds its old session cookie
    _login(phone1, basic_user)          # must work, not 401
    assert _ok(phone1) and not _ok(phone2)
