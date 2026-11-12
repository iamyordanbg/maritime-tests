"""
app/services/login_history.py
=============================
The sign-in history of an account (LoginEvent rows, kept RETENTION_DAYS), as plain dicts for two screens:
the user's own Settings > Privacy list and the admin's "IP entry" window (with_distance=True).

Admin view only: every entry is compared with the one before it that has a known location. When the distance is
more than JUMP_KM within JUMP_MINUTES (the same numbers as the [Sharing] rule in device_signals.py) the entry is
flagged as an alert.
"""
from app.models.login_event import LoginEvent
from app.services.device_signals import JUMP_KM, JUMP_MINUTES, RETENTION_DAYS, distance_km

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
        'place': ', '.join(x for x in (e.city, e.country) if x),
        'device': DEVICE_NAMES.get(e.slot, ''),
        'duration': duration_text(seconds),
        'current': e.id == current_id,
    }


def build_entries(user_id, with_distance=False, current_id=None):
    """Newest first. Distance/alert fields are added only when with_distance is True."""
    events = (LoginEvent.query.filter_by(user_id=user_id)
              .order_by(LoginEvent.created_at.desc(), LoginEvent.id.desc()).limit(LIMIT).all())
    entries = [_entry(e, current_id) for e in events]
    if with_distance:
        _add_distances(events, entries)
    return entries


def _add_distances(events, entries):
    """events/entries are newest first; each entry is compared with the nearest older one that has coordinates."""
    for i, (e, entry) in enumerate(zip(events, entries)):
        entry.update(km=None, gap_min=None, alert=False)
        if e.lat is None:
            continue
        for older in events[i + 1:]:
            if older.lat is None:
                continue
            km = distance_km(older.lat, older.lon, e.lat, e.lon)
            gap = max(0, round((e.created_at - older.created_at).total_seconds() / 60))
            entry.update(km=round(km), gap_min=gap, alert=km > JUMP_KM and gap <= JUMP_MINUTES)
            break


def summary(entries):
    return {'alerts': sum(1 for e in entries if e.get('alert')), 'retention_days': RETENTION_DAYS,
            'jump_km': JUMP_KM, 'jump_minutes': JUMP_MINUTES}
