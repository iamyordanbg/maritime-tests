"""Admin security signal [Sharing]: a 3rd device far (>70 km) from another device of the account within 30 minutes."""
from datetime import datetime, timedelta

import pytest

from app.extensions import db as _db
from app.models.login_event import LoginEvent
from app.models.signal import Signal
from app.services import device_signals, geoip

AJAX = {'X-Requested-With': 'XMLHttpRequest'}
SOFIA = {'country': 'Bulgaria', 'city': 'Sofia', 'lat': 42.70, 'lon': 23.32}
LONDON = {'country': 'United Kingdom', 'city': 'London', 'lat': 51.51, 'lon': -0.13}
PERNIK = {'country': 'Bulgaria', 'city': 'Pernik', 'lat': 42.60, 'lon': 23.04}     # ~30 km from Sofia
VARNA = {'country': 'Bulgaria', 'city': 'Varna', 'lat': 43.21, 'lon': 27.91}       # ~380 km from Sofia
GEO = {'1.1.1.1': SOFIA, '2.2.2.2': LONDON, '3.3.3.3': PERNIK, '4.4.4.4': VARNA}


@pytest.fixture(autouse=True)
def fake_geo(monkeypatch):
    monkeypatch.setattr(geoip, 'lookup', lambda ip: GEO.get(ip))


@pytest.fixture(autouse=True)
def clean_tables(db):
    """The test database is shared between tests: start each one without events and signals."""
    LoginEvent.query.delete()
    Signal.query.delete()
    _db.session.commit()


def _login(app, user, ip, ua='Mozilla/5.0 (Windows NT 10.0) Chrome/120'):
    client = app.test_client()      # fresh client = fresh browser = new 'did' cookie
    res = client.post('/login', data={'email': user.email, 'password': 'Test123'}, headers={**AJAX, 'X-Forwarded-For': ip,
                                                                                                'User-Agent': ua})
    assert res.get_json()['success']
    return client


def _security():
    return Signal.query.filter_by(type='security').all()


def _kinds(prefix):
    return [x for x in _security() if x.message.startswith(prefix)]


def _signin(client, ip, user):
    client.post('/login', data={'email': user.email, 'password': 'Test123'}, headers={**AJAX, 'X-Forwarded-For': ip})


def _browsers(app, n):
    return [app.test_client() for _ in range(n)]     # each test client = a new browser = a new 'did' cookie


def test_distance_haversine():
    assert 1500 < device_signals.distance_km(42.70, 23.32, 51.51, -0.13) < 2200
    assert device_signals.distance_km(42.70, 23.32, 42.70, 23.32) == 0


def test_login_creates_event_with_device_cookie_and_location(app, db, basic_user):
    client = _login(app, basic_user, '1.1.1.1')
    ev = LoginEvent.query.one()
    assert ev.user_id == basic_user.id and ev.ip == '1.1.1.1' and ev.city == 'Sofia'
    assert client.get_cookie('did').value == ev.device_id
    assert _security() == []


def test_same_browser_keeps_its_device_id(app, db, basic_user):
    client = _login(app, basic_user, '1.1.1.1')
    _signin(client, '1.1.1.1', basic_user)
    assert len({e.device_id for e in LoginEvent.query.all()}) == 1


def test_two_devices_far_apart_raise_nothing(app, db, basic_user):
    a, b = _browsers(app, 2)
    _signin(a, '1.1.1.1', basic_user)
    _signin(b, '2.2.2.2', basic_user)                # Sofia + London within a minute, but only 2 devices
    assert _security() == []


def test_two_devices_taking_turns_raise_nothing(app, db, basic_user):
    a, b = _browsers(app, 2)
    for i in range(6):
        _signin(a if i % 2 == 0 else b, '1.1.1.1' if i % 2 == 0 else '2.2.2.2', basic_user)
    assert _security() == []


def test_third_device_far_away_within_minutes_raises_signal(app, db, basic_user):
    a, b, c = _browsers(app, 3)
    _signin(a, '1.1.1.1', basic_user)
    _signin(b, '1.1.1.1', basic_user)
    assert _security() == []
    _signin(c, '2.2.2.2', basic_user)                # London, while a and b were just in Sofia
    sig = _security()
    assert len(sig) == 1 and sig[0].message.startswith('[Sharing]')
    assert 'Sofia' in sig[0].message and 'London' in sig[0].message
    assert sig[0].user_id is None and sig[0].user_email == basic_user.email   # never shown in the user's own list
    d = app.test_client()
    _signin(d, '4.4.4.4', basic_user)
    assert len(_security()) == 1                     # no spam inside the window


def test_third_device_in_the_same_city_raises_nothing(app, db, basic_user):
    for client, ip in zip(_browsers(app, 4), ('1.1.1.1', '1.1.1.1', '1.1.1.1', '3.3.3.3')):   # last one: Pernik ~30 km
        _signin(client, ip, basic_user)
    assert _security() == []


def test_a_few_hundred_km_counts(app, db, basic_user):
    a, b, c = _browsers(app, 3)
    _signin(a, '1.1.1.1', basic_user)
    _signin(b, '1.1.1.1', basic_user)
    _signin(c, '4.4.4.4', basic_user)                # Varna ~380 km
    assert [x.message[:9] for x in _security()] == ['[Sharing]']


def test_third_device_far_but_hours_later_raises_nothing(app, db, basic_user):
    a, b, c = _browsers(app, 3)
    _signin(a, '1.1.1.1', basic_user)
    _signin(b, '1.1.1.1', basic_user)
    LoginEvent.query.update({'created_at': datetime.utcnow() - timedelta(hours=3)})
    _db.session.commit()
    _signin(c, '2.2.2.2', basic_user)
    assert _security() == []


def test_unknown_location_never_raises_signal(app, db, basic_user):
    a, b, c = _browsers(app, 3)
    _signin(a, '1.1.1.1', basic_user)
    _signin(b, '1.1.1.1', basic_user)
    _signin(c, '9.9.9.9', basic_user)                # lookup fails -> None
    assert _security() == []


def test_ip_change_of_a_third_device_seen_by_ping_is_checked(app, db, basic_user):
    a, b, c = _browsers(app, 3)
    for client in (a, b, c):
        _signin(client, '1.1.1.1', basic_user)
    c.get('/ping', headers={'X-Forwarded-For': '1.1.1.1'})
    assert LoginEvent.query.count() == 3             # same IP: nothing recorded
    c.get('/ping', headers={'X-Forwarded-For': '2.2.2.2'})
    assert LoginEvent.query.count() == 4
    assert [x.message[:9] for x in _security()] == ['[Sharing]']


def test_old_events_are_pruned(app, db, basic_user):
    _login(app, basic_user, '1.1.1.1')
    LoginEvent.query.update({'created_at': datetime.utcnow() - timedelta(days=40)})
    _db.session.commit()
    _login(app, basic_user, '1.1.1.1')
    assert LoginEvent.query.count() == 1


def test_security_signal_renders_in_admin_page(app, db, basic_user, admin_user):
    a, b, c = _browsers(app, 3)
    _signin(a, '1.1.1.1', basic_user)
    _signin(b, '1.1.1.1', basic_user)
    _signin(c, '2.2.2.2', basic_user)
    admin = app.test_client()
    admin.post('/login', data={'email': admin_user.email, 'password': 'Admin123'}, headers=AJAX)
    html = admin.get('/admin/signals').get_data(as_text=True)
    assert 'sg-type-security' in html and '[Sharing]' in html


def test_geoip_skips_private_ips(monkeypatch):
    monkeypatch.undo()
    assert geoip.lookup('127.0.0.1') is None and geoip.lookup('10.0.0.5') is None and geoip.lookup('') is None


PHONE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148'
PC_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36'


def _device(app, ua):
    client = app.test_client()
    client.environ_base['HTTP_USER_AGENT'] = ua
    return client


def _ok(client):
    return client.get('/dashboard').status_code == 200


def test_violating_third_device_is_signed_out_with_warning_and_the_first_two_keep_working(app, db, basic_user):
    from app.services.session_guard import VIOLATION_MESSAGE
    phone, pc = _device(app, PHONE_UA), _device(app, PC_UA)
    _signin(phone, '1.1.1.1', basic_user)
    _signin(pc, '1.1.1.1', basic_user)
    third_phone = _device(app, PHONE_UA)             # same slot as the first phone, but in London
    _signin(third_phone, '2.2.2.2', basic_user)
    res = third_phone.get('/dashboard')
    assert res.status_code == 302 and res.headers['Location'].endswith('/?login=1&violation=1')
    assert _ok(phone) and _ok(pc)                    # nobody else was touched, the phone was not replaced
    landing = third_phone.get('/?login=1&violation=1').get_data(as_text=True)
    assert 'violationMessage' in landing and 'Terms of Use were violated' in landing
    assert 'Terms of Use were violated' in VIOLATION_MESSAGE


def test_third_device_close_by_is_allowed_to_sign_in(app, db, basic_user):
    phone, pc = _device(app, PHONE_UA), _device(app, PC_UA)
    _signin(phone, '1.1.1.1', basic_user)
    _signin(pc, '1.1.1.1', basic_user)
    third = _device(app, PHONE_UA)
    _signin(third, '3.3.3.3', basic_user)            # Pernik ~30 km: normal slot takeover, no violation
    assert _ok(third) and not _ok(phone) and _ok(pc)


def test_violating_third_device_can_try_again_and_is_blocked_again(app, db, basic_user):
    phone, pc = _device(app, PHONE_UA), _device(app, PC_UA)
    _signin(phone, '1.1.1.1', basic_user)
    _signin(pc, '1.1.1.1', basic_user)
    third = _device(app, PHONE_UA)
    for _ in range(2):
        _signin(third, '2.2.2.2', basic_user)
        assert third.get('/dashboard').status_code == 302
    assert _ok(phone) and _ok(pc)
    assert len(_kinds('[Sharing]')) == 1             # one admin signal, not one per attempt


def test_third_device_moving_far_while_signed_in_is_signed_out_by_ping(app, db, basic_user):
    phone, pc = _device(app, PHONE_UA), _device(app, PC_UA)
    _signin(phone, '1.1.1.1', basic_user)
    _signin(pc, '1.1.1.1', basic_user)
    third = _device(app, PHONE_UA)
    _signin(third, '1.1.1.1', basic_user)            # same city: allowed, took the phone slot
    assert _ok(third)
    res = third.get('/ping', headers={'X-Forwarded-For': '2.2.2.2', 'X-Requested-With': 'XMLHttpRequest'})
    assert res.status_code == 401 and res.get_json()['error'] == 'device_violation'
    assert third.get('/dashboard').status_code == 302
    assert _ok(pc)


def test_first_two_devices_are_never_signed_out_whatever_their_distance(app, db, basic_user):
    phone, pc = _device(app, PHONE_UA), _device(app, PC_UA)
    _signin(phone, '1.1.1.1', basic_user)
    _signin(pc, '2.2.2.2', basic_user)
    assert _ok(phone) and _ok(pc)
    assert pc.get('/ping', headers={'X-Forwarded-For': '4.4.4.4'}).status_code == 200
    assert _security() == []
