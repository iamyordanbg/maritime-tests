"""Admin security signals: many devices in 24h, and a big location jump within minutes."""
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
    client.post('/login', data={'email': basic_user.email, 'password': 'Test123'}, headers={**AJAX, 'X-Forwarded-For': '1.1.1.1'})
    assert len({e.device_id for e in LoginEvent.query.all()}) == 1


def test_four_devices_in_24h_raise_one_signal(app, db, basic_user):
    for _ in range(3):
        _login(app, basic_user, '1.1.1.1')
    assert _kinds('[Devices]') == []
    _login(app, basic_user, '1.1.1.1')
    sig = _kinds('[Devices]')
    assert len(sig) == 1 and sig[0].message.startswith('[Devices] 4 different devices')
    assert sig[0].user_id is None and sig[0].user_email == basic_user.email   # never shown in the user's own list
    _login(app, basic_user, '1.1.1.1')
    assert len(_kinds('[Devices]')) == 1                                      # no spam


def test_old_devices_do_not_count(app, db, basic_user):
    for _ in range(3):
        _login(app, basic_user, '1.1.1.1')
    LoginEvent.query.update({'created_at': datetime.utcnow() - timedelta(hours=30)})
    _db.session.commit()
    _login(app, basic_user, '1.1.1.1')
    assert _kinds('[Devices]') == []


def test_far_location_within_minutes_raises_signal(app, db, basic_user):
    _login(app, basic_user, '1.1.1.1')
    _login(app, basic_user, '2.2.2.2')
    sig = _security()
    assert len(sig) == 1 and sig[0].message.startswith('[Location]')
    assert 'Sofia' in sig[0].message and 'London' in sig[0].message


def test_near_location_or_late_second_login_is_fine(app, db, basic_user):
    _login(app, basic_user, '1.1.1.1')
    _login(app, basic_user, '3.3.3.3')            # Sofia -> Pernik, ~30 km
    assert _kinds('[Location]') == []
    LoginEvent.query.update({'created_at': datetime.utcnow() - timedelta(hours=3)})
    _db.session.commit()
    _login(app, basic_user, '2.2.2.2')            # far, but hours later
    assert _kinds('[Location]') == []


def test_a_few_hundred_km_within_minutes_also_raises_signal(app, db, basic_user):
    _login(app, basic_user, '1.1.1.1')
    _login(app, basic_user, '4.4.4.4')            # Sofia -> Varna
    assert [x.message[:10] for x in _security()] == ['[Location]']


def test_unknown_location_never_raises_signal(app, db, basic_user):
    _login(app, basic_user, '1.1.1.1')
    _login(app, basic_user, '9.9.9.9')            # lookup fails -> None
    assert _security() == []


def test_ip_change_seen_by_ping_is_checked(app, db, basic_user):
    client = _login(app, basic_user, '1.1.1.1')
    client.get('/ping', headers={'X-Forwarded-For': '1.1.1.1'})
    assert LoginEvent.query.count() == 1          # same IP: nothing recorded
    client.get('/ping', headers={'X-Forwarded-For': '2.2.2.2'})
    assert LoginEvent.query.count() == 2
    assert [s.message[:10] for s in _security()] == ['[Location]']


def test_old_events_are_pruned(app, db, basic_user):
    _login(app, basic_user, '1.1.1.1')
    LoginEvent.query.update({'created_at': datetime.utcnow() - timedelta(days=40)})
    _db.session.commit()
    _login(app, basic_user, '1.1.1.1')
    assert LoginEvent.query.count() == 1


def test_security_signal_renders_in_admin_page(app, db, basic_user, admin_user):
    _login(app, basic_user, '1.1.1.1')
    _login(app, basic_user, '2.2.2.2')
    admin = app.test_client()
    admin.post('/login', data={'email': admin_user.email, 'password': 'Admin123'}, headers=AJAX)
    html = admin.get('/admin/signals').get_data(as_text=True)
    assert 'sg-type-security' in html and '[Location]' in html


def test_geoip_skips_private_ips(monkeypatch):
    monkeypatch.undo()
    assert geoip.lookup('127.0.0.1') is None and geoip.lookup('10.0.0.5') is None and geoip.lookup('') is None


def test_two_people_in_one_city_taking_turns_raise_switching_signal(app, db, basic_user):
    a, b = app.test_client(), app.test_client()   # same IP (same city), two browsers fighting over the computer slot
    post = lambda c: c.post('/login', data={'email': basic_user.email, 'password': 'Test123'},
                            headers={**AJAX, 'X-Forwarded-For': '1.1.1.1'})
    post(a)
    post(b)                                       # 1 hand-over: could be a replaced computer
    assert _security() == []
    post(a)                                       # 2nd hand-over A -> B -> A: two people
    sig = _security()                             # only 2 devices, so no [Devices], no [Location]
    assert len(sig) == 1 and sig[0].message.startswith('[Switching]')


def test_normal_use_of_one_device_never_switches(app, db, basic_user):
    client = _login(app, basic_user, '1.1.1.1')
    for _ in range(6):
        client.post('/login', data={'email': basic_user.email, 'password': 'Test123'}, headers={**AJAX, 'X-Forwarded-For': '1.1.1.1'})
    assert _security() == []
