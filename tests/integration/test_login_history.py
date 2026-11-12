"""Sign-in history by IP: the user's own list (Privacy) and the admin 'IP entry' window with distance alerts."""
from datetime import datetime, timedelta

import pytest

from app.extensions import db as _db
from app.models.login_event import LoginEvent
from app.models.signal import Signal
from app.services import geoip
from app.services.login_history import build_entries, duration_text

AJAX = {'X-Requested-With': 'XMLHttpRequest'}
SOFIA = {'country': 'Bulgaria', 'city': 'Sofia', 'lat': 42.70, 'lon': 23.32}
LONDON = {'country': 'United Kingdom', 'city': 'London', 'lat': 51.51, 'lon': -0.13}
PERNIK = {'country': 'Bulgaria', 'city': 'Pernik', 'lat': 42.60, 'lon': 23.04}
GEO = {'1.1.1.1': SOFIA, '2.2.2.2': LONDON, '3.3.3.3': PERNIK}
PHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1'
PC = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36'


@pytest.fixture(autouse=True)
def fake_geo(monkeypatch):
    monkeypatch.setattr(geoip, 'lookup', lambda ip: GEO.get(ip))


@pytest.fixture(autouse=True)
def clean_tables(db):
    LoginEvent.query.delete()
    Signal.query.delete()
    _db.session.commit()


def _login(app, email, password, ip, ua=PC):
    client = app.test_client()
    res = client.post('/login', data={'email': email, 'password': password},
                      headers={**AJAX, 'X-Forwarded-For': ip, 'User-Agent': ua})
    assert res.get_json()['success']
    return client


def _add(user, ip, minutes_ago, geo, seen_minutes_later=0):
    created = datetime.utcnow() - timedelta(minutes=minutes_ago)
    e = LoginEvent(user_id=user.id, device_id='d' + ip, slot='computer', ip=ip, created_at=created,
                   last_seen_at=created + timedelta(minutes=seen_minutes_later),
                   country=geo['country'], city=geo['city'], lat=geo['lat'], lon=geo['lon'])
    _db.session.add(e)
    _db.session.commit()
    return e


@pytest.mark.parametrize('seconds,text', [(0, '< 1 min'), (59, '< 1 min'), (60, '1 min'), (3599, '59 min'), (3600, '1 h 0 min'), (5400, '1 h 30 min')])
def test_duration_text(seconds, text):
    assert duration_text(seconds) == text


def test_login_creates_an_entry_with_ip_and_device_type(app, db, basic_user):
    _login(app, basic_user.email, 'Test123', '1.1.1.1', PHONE)
    [e] = build_entries(basic_user.id)
    assert e['ip'] == '1.1.1.1' and e['device'] == 'Phone' and e['place'] == 'Sofia, Bulgaria' and e['duration'] == '< 1 min'


def test_ping_extends_the_duration_of_the_current_entry(app, db, basic_user):
    client = _login(app, basic_user.email, 'Test123', '1.1.1.1')
    ev = LoginEvent.query.filter_by(user_id=basic_user.id).one()
    ev.created_at = datetime.utcnow() - timedelta(minutes=25)
    _db.session.commit()
    assert client.get('/ping', headers={'X-Forwarded-For': '1.1.1.1'}).status_code == 200
    [e] = build_entries(basic_user.id)
    assert e['duration'] in ('25 min', '24 min', '26 min')


def test_user_sees_only_their_own_history_and_the_current_device(app, db, basic_user, free_user):
    _add(free_user, '9.9.9.9', 5, SOFIA)
    client = _login(app, basic_user.email, 'Test123', '1.1.1.1')
    data = client.get('/settings/login-history').get_json()
    assert [e['ip'] for e in data['entries']] == ['1.1.1.1']
    assert data['entries'][0]['current'] is True and 'km' not in data['entries'][0]
    assert data['retention_days'] == 30


def test_history_requires_login(client):
    assert client.get('/settings/login-history').status_code in (302, 401)


def test_admin_entries_flag_an_impossible_jump(app, db, basic_user, admin_user):
    _add(basic_user, '1.1.1.1', 20, SOFIA)
    _add(basic_user, '2.2.2.2', 10, LONDON)          # ~2000 km in 10 min
    _add(basic_user, '3.3.3.3', 5, PERNIK)           # London -> Pernik in 5 min: also a jump
    admin = _login(app, admin_user.email, 'Admin123', '1.1.1.1')
    data = admin.get(f'/admin/users/{basic_user.id}/ip-entries').get_json()
    newest_first = data['entries']
    assert [e['ip'] for e in newest_first] == ['3.3.3.3', '2.2.2.2', '1.1.1.1']
    assert newest_first[2]['km'] is None and newest_first[2]['alert'] is False   # nothing before the first entry
    assert newest_first[1]['alert'] is True and newest_first[1]['km'] > 1000 and newest_first[1]['gap_min'] == 10
    assert newest_first[0]['alert'] is True
    assert data['alerts'] == 2 and data['jump_km'] == 70 and data['jump_minutes'] == 30


def test_no_alert_when_close_or_far_apart_in_time(app, db, basic_user, admin_user):
    _add(basic_user, '1.1.1.1', 300, SOFIA)
    _add(basic_user, '2.2.2.2', 100, LONDON)         # far, but 3 hours later: a flight is possible
    _add(basic_user, '3.3.3.3', 95, PERNIK)          # London -> Pernik 5 min later: a real jump
    _add(basic_user, '1.1.1.1', 90, SOFIA)
    admin = _login(app, admin_user.email, 'Admin123', '1.1.1.1')
    entries = admin.get(f'/admin/users/{basic_user.id}/ip-entries').get_json()['entries']
    by_gap = {(e['ip'], e['gap_min']): e for e in entries}
    assert by_gap[('2.2.2.2', 200)]['alert'] is False
    assert by_gap[('3.3.3.3', 5)]['alert'] is True
    assert by_gap[('1.1.1.1', 5)]['alert'] is False          # Pernik -> Sofia is ~30 km


def test_entry_without_location_is_not_compared(app, db, basic_user, admin_user):
    _add(basic_user, '1.1.1.1', 20, SOFIA)
    _db.session.add(LoginEvent(user_id=basic_user.id, device_id='x', slot='phone', ip='8.8.8.8',
                               created_at=datetime.utcnow() - timedelta(minutes=5), last_seen_at=datetime.utcnow()))
    _db.session.commit()
    admin = _login(app, admin_user.email, 'Admin123', '1.1.1.1')
    entries = admin.get(f'/admin/users/{basic_user.id}/ip-entries').get_json()['entries']
    assert entries[0]['ip'] == '8.8.8.8' and entries[0]['km'] is None and entries[0]['alert'] is False


def test_admin_entries_are_admin_only(app, db, basic_user, free_user):
    user = _login(app, free_user.email, 'Test123', '1.1.1.1')
    assert user.get(f'/admin/users/{basic_user.id}/ip-entries').status_code in (302, 401, 403)
    assert app.test_client().get(f'/admin/users/{basic_user.id}/ip-entries').status_code in (302, 401, 403)


def test_admin_users_page_has_the_ip_entry_link(app, db, admin_user, basic_user):
    admin = _login(app, admin_user.email, 'Admin123', '1.1.1.1')
    html = admin.get('/admin/users').get_data(as_text=True)
    assert 'us-ip-link' in html and 'IP entry' in html and 'id="ipEntryOverlay"' in html


def test_privacy_tab_has_the_history_section(app, db, basic_user):
    client = _login(app, basic_user.email, 'Test123', '1.1.1.1')
    html = client.get('/dashboard').get_data(as_text=True)
    assert 'Sign-in history' in html and 'toggleLoginHistory' in html and 'login-history.js' in html


def test_last_seen_column_is_added_to_an_old_database(app):
    from sqlalchemy import inspect, text
    from app.services import db_migrations
    with app.app_context():
        with _db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE login_event DROP COLUMN last_seen_at'))
            conn.commit()
        db_migrations.migrate_db(app)
        assert 'last_seen_at' in [c['name'] for c in inspect(_db.engine).get_columns('login_event')]
