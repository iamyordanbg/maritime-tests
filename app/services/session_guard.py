"""
app/services/session_guard.py
=============================
Device rule: an account can be used on 2 devices at once - 1 phone and 1 computer or tablet.

Every login fills the slot of the device it comes from ('phone' or 'computer'): a random token is stored on the
user (User.phone_session_token / computer_session_token) and in that browser's session cookie (session['sid'],
session['slot']). On each request the cookie token must equal the stored one of its slot, so signing in on a second
phone signs the first phone out (a computer stays signed in) and the other way round.
Sessions created before this check existed (no 'sid') stay valid until their slot is filled by a new login.
"""
import secrets

from flask import jsonify, redirect, request, session

from app.extensions import db
from app.models.user import User

# Shown to the user in the "You selected <test>" popup (library) - one place for the wording.
DEVICE_POLICY_NOTICE = 'Your account can be used on 2 devices at the same time: 1 phone and 1 computer or tablet.'

# What the signed-out device is told, by the slot that was taken over (landing.js builds the same text from ?replaced=)
REPLACED_MESSAGES = {
    'phone': 'You were signed out because this account was signed in on another phone.',
    'computer': 'You were signed out because this account was signed in on another computer or tablet.',
}


def device_slot():
    """'phone' for phones, 'computer' for desktops and tablets (iPad / Android tablets count with the computer)."""
    ua = request.headers.get('User-Agent', '')
    if 'iPad' in ua or 'Tablet' in ua:
        return 'computer'
    return 'phone' if 'Mobi' in ua else 'computer'


def _token_column(slot):
    return f'{slot}_session_token'


def start_single_session(user):
    """Call right after a login: this browser takes the slot of its device type. Commits."""
    slot = device_slot()
    token = secrets.token_hex(16)
    setattr(user, _token_column(slot), token)
    db.session.commit()
    session['sid'] = token
    session['slot'] = slot


def _is_current(user):
    slot = session.get('slot') or device_slot()
    stored = getattr(user, _token_column(slot))
    sid = session.get('sid')
    if sid is None:
        return stored is None   # legacy session; nobody has signed in on this kind of device since the rule exists
    return sid == stored


def enforce_single_session():
    """before_request: sign this browser out if its slot was taken by a newer login."""
    user_id = session.get('user_id')
    if not user_id or request.path.startswith('/static'):
        return None
    user = db.session.get(User, user_id)
    if user is None or _is_current(user):
        return None
    slot = session.get('slot') or device_slot()
    session.clear()
    if (request.path.startswith('/api/') or request.path == '/ping'
            or request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
        return jsonify({'error': 'session_replaced', 'slot': slot, 'message': REPLACED_MESSAGES[slot]}), 401
    return redirect(f'/?login=1&replaced={slot}')
