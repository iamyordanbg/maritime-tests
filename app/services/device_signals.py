"""
app/services/device_signals.py
==============================
Admin security signals about account sharing. Nothing here blocks a user - it only creates a Signal (type
'security') in the admin Signals page. One rule, [Sharing], needs BOTH conditions:

  1. the device is not one of the account's first ALLOWED_DEVICES devices (a device = the 'did' cookie of a
     browser; the first two ever seen are the allowed ones, so 1,2,1,2 taking turns is normal use), and
  2. within JUMP_MINUTES another device of the account was seen at least JUMP_KM away (approximate IP location).

Two devices in one city, or a third device next door, raise nothing; the signal appears when an extra device shows
up far from where the account was just in use.

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

ALLOWED_DEVICES = 2
JUMP_KM = 50
JUMP_MINUTES = 30
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
    _check_sharing(user, event)


def _already_signalled(user, tag, minutes):
    since = datetime.utcnow() - timedelta(minutes=minutes)
    return Signal.query.filter(Signal.type == 'security', Signal.user_email == user.email,
                               Signal.message.like(tag + '%'), Signal.created_at >= since).first() is not None


def _add_signal(user, message):
    # user_id stays empty on purpose: a signal with a user_id is shown to that user in their own support list.
    db.session.add(Signal(user_id=None, user_name=user.name, user_email=user.email, type='security',
                          message=message[:500]))
    db.session.commit()


def _is_extra_device(user, event):
    """True when this event's device is not among the first ALLOWED_DEVICES devices the account was seen on."""
    first_seen = (db.session.query(LoginEvent.device_id, db.func.min(LoginEvent.id))
                  .filter(LoginEvent.user_id == user.id).group_by(LoginEvent.device_id)
                  .order_by(db.func.min(LoginEvent.id)).limit(ALLOWED_DEVICES).all())
    return event.device_id not in {d for d, _ in first_seen}


def _check_sharing(user, event):
    if event.lat is None or not _is_extra_device(user, event):
        return
    since = event.created_at - timedelta(minutes=JUMP_MINUTES)
    others = (LoginEvent.query.filter(LoginEvent.user_id == user.id, LoginEvent.id < event.id,
                                      LoginEvent.created_at >= since, LoginEvent.lat.isnot(None),
                                      LoginEvent.device_id != event.device_id)
              .order_by(LoginEvent.id.desc()).all())
    far = [(o, distance_km(o.lat, o.lon, event.lat, event.lon)) for o in others]
    far = [(o, km) for o, km in far if km > JUMP_KM]
    if not far or _already_signalled(user, '[Sharing]', JUMP_MINUTES):
        return
    other, km = max(far, key=lambda t: t[1])
    minutes = max(1, round((event.created_at - other.created_at).total_seconds() / 60))
    _add_signal(user, f'[Sharing] A 3rd device signed in {round(km)} km from another device of this account within '
                      f'{minutes} min: {_place(other)} ({other.ip}) -> {_place(event)} ({event.ip}).')
