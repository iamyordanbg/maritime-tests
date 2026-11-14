"""
app/services/session_guard.py
=============================
Device rule: an account can be used on 2 devices (for the subscription), but only ONE is signed in at a time.

Every login stores a random token on the user (User.session_token) and in that browser's session cookie
(session['sid']). On each request the cookie token must equal the stored one, so signing in on another device signs
the previous one out. That device is sent to the landing page with a warning popup that names the IP address of the
new sign-in. "Sign out of all devices" (Settings > Privacy) replaces the token, which ends every session at once.
Each login is also recorded in the sign-in history (device_signals.py), with the device type
('phone' / 'computer') taken from the User-Agent.
Sessions created before this check existed (no 'sid') stay valid until the next login of the account.
"""
import secrets
from urllib.parse import quote

from flask import jsonify, redirect, request, session

from app.extensions import db
from app.models.login_event import LoginEvent
from app.models.user import User
from app.services.device_signals import device_id, record_login

# Shown to the user in the "You selected <test>" popup (library) - one place for the wording.
DEVICE_POLICY_NOTICE = 'Your account can be used on 2 devices, but only one at a time: signing in on another device signs you out here.'

# Sign-in posts are never blocked by the old session's check
LOGIN_POSTS = ('/login', '/register')

# What the signed-out device is told (the landing page shows its own popup for ?replaced=1)
REPLACED_MESSAGE = 'You were signed out because this account was signed in on another device.'


def device_slot():
    """'phone' for phones, 'computer' for desktops and tablets (iPad / Android tablets count with the computer)."""
    ua = request.headers.get('User-Agent', '')
    if 'iPad' in ua or 'Tablet' in ua:
        return 'computer'
    return 'phone' if 'Mobi' in ua else 'computer'


def _new_token():
    return secrets.token_hex(16)


def start_single_session(user):
    """Call right after a login: this browser becomes the only active session of the account. Commits."""
    slot = device_slot()
    token = _new_token()
    user.session_token = token
    db.session.commit()
    session['sid'] = token
    session['slot'] = slot
    record_login(user, slot)


def sign_out_all_devices(user):
    """Ends every session of the account (this browser included): the stored token no longer matches any cookie."""
    user.session_token = _new_token()
    db.session.commit()
    session.clear()


def _is_current(user):
    sid = session.get('sid')
    if sid is None:
        return user.session_token is None   # legacy session; nobody has signed in since the rule exists
    return sid == user.session_token


def _replacing_ip(user):
    """IP address of the newest sign-in from another device, or '' when unknown."""
    event = (LoginEvent.query.filter(LoginEvent.user_id == user.id, LoginEvent.device_id != device_id())
             .order_by(LoginEvent.created_at.desc(), LoginEvent.id.desc()).first())
    return event.ip if event and event.ip else ''


def enforce_single_session():
    """before_request: sign this browser out if the account was signed in somewhere else since."""
    user_id = session.get('user_id')
    if not user_id or request.path.startswith('/static'):
        return None
    if request.method == 'POST' and request.path in LOGIN_POSTS:
        return None   # a login replaces the old session anyway; a kicked device must still be able to sign in again
    user = db.session.get(User, user_id)
    if user is None or _is_current(user):
        return None
    ip = _replacing_ip(user)
    session.clear()
    if _wants_json():
        return jsonify({'error': 'session_replaced', 'ip': ip, 'message': REPLACED_MESSAGE}), 401
    return redirect('/?replaced=1' + (f'&ip={quote(ip)}' if ip else ''))


def _wants_json():
    return (request.path.startswith('/api/') or request.path == '/ping'
            or request.headers.get('X-Requested-With') == 'XMLHttpRequest')
