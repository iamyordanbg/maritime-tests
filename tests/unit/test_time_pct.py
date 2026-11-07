"""The dashboard card bar and Settings > Usage share one time-remaining formula."""
from datetime import datetime, timedelta
from app.services.usage import time_pct_remaining

S = datetime(2026, 11, 2, 10, 0)


def test_full_half_and_last_hour():
    e = S + timedelta(days=10)
    assert time_pct_remaining(S, e, S) == 100
    assert time_pct_remaining(S, e, S + timedelta(days=5)) == 50
    assert time_pct_remaining(S, S + timedelta(days=1), S + timedelta(hours=22)) == 8   # ~9% left of a 1-day plan


def test_clamped():
    e = S + timedelta(days=1)
    assert time_pct_remaining(S, e, e + timedelta(days=3)) == 0
    assert time_pct_remaining(S, e, S - timedelta(hours=5)) == 100
    assert time_pct_remaining(S, S, S) == 100   # zero-length period does not divide by zero
