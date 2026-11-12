"""Sign-in history by IP: the user's own list (Privacy) and the admin 'IP entry' window with distance alerts."""
from datetime import datetime, timedelta

import pytest

from app.extensions import db as _db
from app.models.login_event import LoginEvent
from app.services.login_history import build_entries, duration_text

AJAX = {'X-Requested-With': 'XMLHttpRequest'}
PHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1'
PC = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36'


@pytest.fixture(autouse=True)
def clean_tables(db):
    LoginEvent.query.delete()
    _db.session.commit()


def _login(app, email, password, ip, ua=PC):
    client = app.test_client()
    res = client.post('/login', data={'email': email, 'password': password},
                      headers={**AJAX, 'X-Forwarded-For': ip, 'User-Agent': ua})
    assert res.get_json()['success']
    return client


def _add(user, ip, minutes_ago, seen_minutes_later=0):
    created = datetime.utcnow() - timedelta(minutes=minutes_ago)
    e = LoginEvent(user_id=user.id, device_id='d' + ip, slot='computer', ip=ip, created_at=created,
                   last_seen_at=created + timedelta(minutes=seen_minutes_later))
    _db.session.add(e)
    _db.session.commit()
    return e


@pytest.mark.parametrize('seconds,text', [(0, '< 1 min'), (59, '< 1 min'), (60, '1 min'), (3599, '59 min'), (3600, '1 h 0 min'), (5400, '1 h 30 min')])
def test_duration_text(seconds, text):
    assert duration_text(seconds) == text


def test_login_creates_an_entry_with_ip_and_device_type(app, db, basic_user):
    _login(app, basic_user.email, 'Test123', '1.1.1.1', PHONE)
    [e] = build_entries(basic_user.id)
    assert e['ip'] == '1.1.1.1' and e['device'] == 'Phone' and e['duration'] == '< 1 min'


def test_ping_extends_the_duration_of_the_current_entry(app, db, basic_user):
    client = _login(app, basic_user.email, 'Test123', '1.1.1.1')
    ev = LoginEvent.query.filter_by(user_id=basic_user.id).one()
    ev.created_at = datetime.utcnow() - timedelta(minutes=25)
    _db.session.commit()
    assert client.get('/ping', headers={'X-Forwarded-For': '1.1.1.1'}).status_code == 200
    [e] = build_entries(basic_user.id)
    assert e['duration'] in ('25 min', '24 min', '26 min')


def test_user_sees_only_their_own_history_and_the_current_device(app, db, basic_user, free_user):
    _add(free_user, '9.9.9.9', 5)
    client = _login(app, basic_user.email, 'Test123', '1.1.1.1')
    data = client.get('/settings/login-history').get_json()
    assert [e['ip'] for e in data['entries']] == ['1.1.1.1']
    assert data['entries'][0]['current'] is True and set(data['entries'][0]) == {'id', 'at', 'ip', 'device', 'duration', 'current'}
    assert data['retention_days'] == 30


def test_history_requires_login(client):
    assert client.get('/settings/login-history').status_code in (302, 401)


def test_admin_sees_all_entries_of_the_user_newest_first(app, db, basic_user, admin_user):
    _add(basic_user, '1.1.1.1', 600, seen_minutes_later=45)
    _add(basic_user, '2.2.2.2', 100, seen_minutes_later=130)
    _add(basic_user, '3.3.3.3', 5)
    admin = _login(app, admin_user.email, 'Admin123', '1.1.1.1')
    data = admin.get(f'/admin/users/{basic_user.id}/ip-entries').get_json()
    assert [(e['ip'], e['duration']) for e in data['entries']] == [('3.3.3.3', '< 1 min'), ('2.2.2.2', '2 h 10 min'), ('1.1.1.1', '45 min')]
    assert data['email'] == basic_user.email and data['retention_days'] == 30
    assert all(set(e) == {'id', 'at', 'ip', 'device', 'duration', 'current'} for e in data['entries'])   # no distance, no location


def test_distance_and_location_logic_is_gone(app):
    import importlib.util
    assert importlib.util.find_spec('app.services.geoip') is None
    from app.services import device_signals
    assert not hasattr(device_signals, 'distance_km')


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
