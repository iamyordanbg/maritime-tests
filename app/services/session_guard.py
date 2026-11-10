"""
app/services/session_guard.py
=============================
One active session per account: signing in on a new device signs the account out everywhere else.

Every login stores a fresh random token on the user (User.active_session_token) and in that browser's
session cookie (session['sid']). On each request the cookie token must equal the stored one; an older device
holds an outdated token and is signed out on its next request.
Sessions created before this check existed (no 'sid') stay valid until the account is signed in again.
"""
import secrets

from flask import jsonify, redirect, request, session

from app.extensions import db
from app.models.user import User

REPLACED_MESSAGE = 'You were signed out because this account was signed in on another device.'


def start_single_session(user):
    """Call right after a login: makes this browser the only active session of the account. Commits."""
    token = secrets.token_hex(16)
    user.active_session_token = token
    db.session.commit()
    session['sid'] = token


def _is_current(user):
    sid = session.get('sid')
    if sid is None:
        return user.active_session_token is None   # legacy session, nobody has signed in since the rule exists
    return sid == user.active_session_token


def enforce_single_session():
    """before_request: sign this browser out if the account was signed in somewhere else since."""
    user_id = session.get('user_id')
    if not user_id or request.path.startswith('/static'):
        return None
    user = db.session.get(User, user_id)
    if user is None or _is_current(user):
        return None
    session.clear()
    if (request.path.startswith('/api/') or request.path == '/ping'
            or request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
        return jsonify({'error': 'session_replaced', 'message': REPLACED_MESSAGE}), 401
    return redirect('/?login=1&replaced=1')
