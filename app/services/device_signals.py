"""
app/services/device_signals.py
==============================
Sign-in recording. Every login (and every IP change of a signed-in browser, seen by /ping) is stored as a LoginEvent
with the IP address and the device type; /ping also keeps the last activity of the browser fresh, which gives the
duration. The rows feed the sign-in history (services/login_history.py) and are pruned after RETENTION_DAYS.
A device = the 'did' cookie of a browser.
"""
import secrets
from datetime import datetime, timedelta

from flask import request, session

from app.extensions import db
from app.models.login_event import LoginEvent
from app.models.user import User
from app.services.turnstile import client_ip

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
    """Store this sign-in. Never raises: bookkeeping must not break a login."""
    ip = client_ip()
    session['ip'] = ip
    _record(user, slot, ip)


def note_ip_change():
    """Called by /ping: keeps this browser's last activity fresh and records a new entry when its IP changed."""
    user_id = session.get('user_id')
    if not user_id:
        return
    _touch_event()
    ip = client_ip()
    known = session.get('ip')
    session['ip'] = ip
    if known is None or known == ip:   # legacy session without a stored IP, or nothing changed
        return
    user = db.session.get(User, user_id)
    if user:
        _record(user, session.get('slot') or '', ip)


def _touch_event():
    """Mark the current sign-in entry of this browser as active now (its duration grows). Never raises."""
    event_id = session.get('event_id')
    if not event_id:
        return
    try:
        LoginEvent.query.filter_by(id=event_id).update({'last_seen_at': datetime.utcnow()})
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f'device_signals: could not update last activity: {e}')


def _prune():
    LoginEvent.query.filter(LoginEvent.created_at < datetime.utcnow() - timedelta(days=RETENTION_DAYS)).delete()


def _record(user, slot, ip):
    try:
        event = LoginEvent(user_id=user.id, device_id=device_id(), slot=slot, ip=ip, last_seen_at=datetime.utcnow())
        db.session.add(event)
        _prune()
        db.session.commit()
        session['event_id'] = event.id   # this browser's current entry: /ping keeps its last_seen_at fresh
    except Exception as e:
        db.session.rollback()
        print(f'device_signals: could not record event: {e}')
