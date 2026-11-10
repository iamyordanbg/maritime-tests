"""
app/services/device_signals.py
==============================
Admin security signals about account sharing. Nothing here blocks a user - it only creates a Signal (type
'security') in the admin Signals page when something looks like one account used by several people:

  1. [Devices]  the account signed in from DEVICE_LIMIT or more different devices within DEVICE_WINDOW_HOURS
                (a device = the 'did' cookie of a browser; the IP is never used to count devices, ships change IPs).
  2. [Location] two sign-ins / IP changes of the account within JUMP_MINUTES whose approximate locations are at
                least JUMP_KM apart.

  3. [Switching] the same slot (phone / computer) was taken over by a different device SWITCH_LIMIT or more times
                within SWITCH_WINDOW_HOURS (A signs in, B signs A out, A signs B out...). Works for people in the
                same city, where distance and IP tell nothing.

Every sign-in (and every IP change seen by /ping on a signed-in browser) is stored as a LoginEvent; events older
than RETENTION_DAYS are deleted. The geo lookup runs in a background thread so a login never waits for it.
"""
import math
import secrets
import threading
from datetime import datetime, timedelta

from flask import current_app, request, session

from app.extensions import db
from app.models.login_event import LoginEvent
from app.models.signal import Signal
from app.models.user import User
from app.services import geoip
from app.services.turnstile import client_ip

DEVICE_LIMIT = 4
DEVICE_WINDOW_HOURS = 24
JUMP_KM = 800
JUMP_MINUTES = 30
SWITCH_LIMIT = 4
SWITCH_WINDOW_HOURS = 24
RETENTION_DAYS = 30
COOKIE_NAME = 'did'
NEW_ID_KEY = 'maradtest.new_device_id'
COOKIE_MAX_AGE = 60 * 60 * 24 * 365


# ---------- device id cookie ----------
def device_id():
    """The id of this browser; a new one is generated (and set by set_device_cookie) when it has none."""
    existing = request.cookies.get(COOKIE_NAME)
    if existing:
        return existing[:64]
    # kept on the request itself (not flask.g) so it can never leak into another request
    return request.environ.setdefault(NEW_ID_KEY, secrets.token_hex(16))


def set_device_cookie(response):
    """after_request: persist a freshly generated device id."""
    new_id = request.environ.get(NEW_ID_KEY)
    if new_id:
        response.set_cookie(COOKIE_NAME, new_id, max_age=COOKIE_MAX_AGE, httponly=True, samesite='Lax',
                            secure=request.is_secure)
    return response


# ---------- recording ----------
def record_login(user, slot):
    """Store this sign-in and analyse it. Never raises: security bookkeeping must not break a login."""
    ip = client_ip()
    session['ip'] = ip
    _record(user, slot, ip)


def note_ip_change():
    """Called by /ping: a signed-in browser whose IP changed since the last event is recorded as a new event."""
    user_id = session.get('user_id')
    if not user_id:
        return
    ip = client_ip()
    known = session.get('ip')
    session['ip'] = ip
    if known is None or known == ip:   # legacy session without a stored IP, or nothing changed
        return
    user = db.session.get(User, user_id)
    if user:
        _record(user, session.get('slot') or '', ip)


def _record(user, slot, ip):
    try:
        event = LoginEvent(user_id=user.id, device_id=device_id(), slot=slot, ip=ip)
        db.session.add(event)
        db.session.commit()
        app = current_app._get_current_object()
        if app.testing:
            _analyze(event.id)
        else:
            threading.Thread(target=_analyze_in_context, args=(app, event.id), daemon=True).start()
    except Exception as e:
        db.session.rollback()
        print(f'device_signals: could not record event: {e}')


def _analyze_in_context(app, event_id):
    with app.app_context():
        try:
            _analyze(event_id)
        except Exception as e:
            db.session.rollback()
            print(f'device_signals: analysis failed: {e}')


# ---------- analysis ----------
def distance_km(lat1, lon1, lat2, lon2):
    """Great-circle (haversine) distance."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(a))


def _place(e):
    return ', '.join(x for x in (e.city, e.country) if x) or e.ip


def _analyze(event_id):
    event = db.session.get(LoginEvent, event_id)
    user = db.session.get(User, event.user_id) if event else None
    if not event or not user:
        return
    geo = geoip.lookup(event.ip)
    if geo:
        event.country, event.city, event.lat, event.lon = geo['country'], geo['city'], geo['lat'], geo['lon']
    LoginEvent.query.filter(LoginEvent.created_at < datetime.utcnow() - timedelta(days=RETENTION_DAYS)).delete()
    db.session.commit()
    _check_devices(user, event)
    _check_location_jump(user, event)
    _check_slot_switching(user, event)


def _already_signalled(user, tag, minutes):
    since = datetime.utcnow() - timedelta(minutes=minutes)
    return Signal.query.filter(Signal.type == 'security', Signal.user_email == user.email,
                               Signal.message.like(tag + '%'), Signal.created_at >= since).first() is not None


def _add_signal(user, message):
    # user_id stays empty on purpose: a signal with a user_id is shown to that user in their own support list.
    db.session.add(Signal(user_id=None, user_name=user.name, user_email=user.email, type='security',
                          message=message[:500]))
    db.session.commit()


def _check_devices(user, event):
    since = datetime.utcnow() - timedelta(hours=DEVICE_WINDOW_HOURS)
    devices = {d for (d,) in db.session.query(LoginEvent.device_id)
               .filter(LoginEvent.user_id == user.id, LoginEvent.created_at >= since).distinct()}
    if len(devices) >= DEVICE_LIMIT and not _already_signalled(user, '[Devices]', DEVICE_WINDOW_HOURS * 60):
        _add_signal(user, f'[Devices] {len(devices)} different devices signed in to this account within '
                          f'{DEVICE_WINDOW_HOURS} hours.')


def _check_location_jump(user, event):
    if event.lat is None:
        return
    since = event.created_at - timedelta(minutes=JUMP_MINUTES)
    previous = (LoginEvent.query.filter(LoginEvent.user_id == user.id, LoginEvent.id < event.id,
                                        LoginEvent.created_at >= since, LoginEvent.lat.isnot(None),
                                        LoginEvent.ip != event.ip)
                .order_by(LoginEvent.id.desc()).first())
    if not previous:
        return
    km = distance_km(previous.lat, previous.lon, event.lat, event.lon)
    if km >= JUMP_KM and not _already_signalled(user, '[Location]', JUMP_MINUTES):
        minutes = max(1, round((event.created_at - previous.created_at).total_seconds() / 60))
        _add_signal(user, f'[Location] Location changed by about {round(km)} km within {minutes} min: '
                          f'{_place(previous)} ({previous.ip}) -> {_place(event)} ({event.ip}).')


def _check_slot_switching(user, event):
    if not event.slot:
        return
    since = datetime.utcnow() - timedelta(hours=SWITCH_WINDOW_HOURS)
    devices = [d for (d,) in db.session.query(LoginEvent.device_id)
               .filter(LoginEvent.user_id == user.id, LoginEvent.slot == event.slot, LoginEvent.created_at >= since)
               .order_by(LoginEvent.id)]
    switches = sum(1 for a, b in zip(devices, devices[1:]) if a != b)
    if switches >= SWITCH_LIMIT and not _already_signalled(user, '[Switching]', SWITCH_WINDOW_HOURS * 60):
        _add_signal(user, f'[Switching] The {event.slot} slot of this account changed hands between different '
                          f'devices {switches} times within {SWITCH_WINDOW_HOURS} hours (devices sign each other out).')
