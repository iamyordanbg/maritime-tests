"""Admin security signal [Sharing]: a 3rd device far (>50 km) from another device of the account within 30 minutes."""
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
