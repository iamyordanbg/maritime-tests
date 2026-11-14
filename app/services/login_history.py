"""
app/services/login_history.py
=============================
The sign-in history of an account (LoginEvent rows, kept RETENTION_DAYS), as plain dicts for two screens:
the user's own Settings > Privacy list and the admin "IP entry" window. Both use history_payload().
"""
from app.models.login_event import LoginEvent
from app.services.device_signals import RETENTION_DAYS

LIMIT = 200
DEVICE_NAMES = {'phone': 'Phone', 'computer': 'Computer / tablet'}


def duration_text(seconds):
    if seconds < 60:
        return '< 1 min'
    minutes = seconds // 60
    if minutes < 60:
        return f'{minutes} min'
    return f'{minutes // 60} h {minutes % 60} min'


def _iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ') if dt else ''


def _entry(e, current_id):
    seconds = max(0, int((e.last_seen_at - e.created_at).total_seconds())) if e.last_seen_at and e.created_at else 0
    return {
        'id': e.id,
        'at': _iso(e.created_at),
        'ip': e.ip or '',
        'device': DEVICE_NAMES.get(e.slot, ''),
        'duration': duration_text(seconds),
        'current': e.id == current_id,
    }


def build_entries(user_id, current_id=None):
    """Newest first."""
    events = (LoginEvent.query.filter_by(user_id=user_id)
              .order_by(LoginEvent.created_at.desc(), LoginEvent.id.desc()).limit(LIMIT).all())
    return [_entry(e, current_id) for e in events]


def history_payload(user_id, current_id=None):
    return {'entries': build_entries(user_id, current_id), 'retention_days': RETENTION_DAYS}
