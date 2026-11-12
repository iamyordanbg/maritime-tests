"""Sign-in recording: every login (and IP change seen by /ping) becomes a LoginEvent with the IP and the device type."""
from datetime import datetime, timedelta

import pytest

from app.extensions import db as _db
from app.models.login_event import LoginEvent

AJAX = {'X-Requested-With': 'XMLHttpRequest'}
PHONE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148'
PC_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36'


@pytest.fixture(autouse=True)
def clean_tables(db):
    """The test database is shared between tests: start each one without events."""
    LoginEvent.query.delete()
    _db.session.commit()


def _signin(client, ip, user, ua=PC_UA):
    res = client.post('/login', data={'email': user.email, 'password': 'Test123'},
                      headers={**AJAX, 'X-Forwarded-For': ip, 'User-Agent': ua})
    assert res.get_json()['success']


def test_login_creates_event_with_ip_device_type_and_device_cookie(app, db, basic_user):
    client = app.test_client()
    _signin(client, '1.1.1.1', basic_user, PHONE_UA)
    ev = LoginEvent.query.one()
    assert ev.user_id == basic_user.id and ev.ip == '1.1.1.1' and ev.slot == 'phone'
    assert client.get_cookie('did').value == ev.device_id and ev.last_seen_at is not None


def test_same_browser_keeps_its_device_id(app, db, basic_user):
    client = app.test_client()
    _signin(client, '1.1.1.1', basic_user)
    _signin(client, '1.1.1.1', basic_user)
    assert len({e.device_id for e in LoginEvent.query.all()}) == 1


def test_different_browsers_get_different_device_ids(app, db, basic_user):
    a, b = app.test_client(), app.test_client()
    _signin(a, '1.1.1.1', basic_user)
    _signin(b, '1.1.1.1', basic_user)
    assert len({e.device_id for e in LoginEvent.query.all()}) == 2


def test_ping_records_an_ip_change_but_not_the_same_ip(app, db, basic_user):
    client = app.test_client()
    _signin(client, '1.1.1.1', basic_user)
    client.get('/ping', headers={'X-Forwarded-For': '1.1.1.1'})
    assert LoginEvent.query.count() == 1
    assert client.get('/ping', headers={'X-Forwarded-For': '2.2.2.2'}).status_code == 200
    assert sorted(e.ip for e in LoginEvent.query.all()) == ['1.1.1.1', '2.2.2.2']


def test_ping_of_a_signed_out_browser_is_harmless(client):
    assert client.get('/ping').status_code == 200
    assert LoginEvent.query.count() == 0


def test_old_events_are_pruned(app, db, basic_user):
    client = app.test_client()
    _signin(client, '1.1.1.1', basic_user)
    LoginEvent.query.update({'created_at': datetime.utcnow() - timedelta(days=40)})
    _db.session.commit()
    _signin(client, '1.1.1.1', basic_user)
    assert LoginEvent.query.count() == 1
