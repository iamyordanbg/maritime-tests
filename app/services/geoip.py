"""
app/services/geoip.py
=====================
IP -> approximate location (country, city, lat, lon) for the admin security signals only.
Uses the free HTTPS service ipwho.is (no key). Returns None when the IP is private/unknown or the lookup fails:
a failed lookup never blocks anything, it just means no location signal for that event.
"""
import ipaddress

import requests

LOOKUP_URL = 'https://ipwho.is/{ip}'
TIMEOUT_SECONDS = 2
_CACHE = {}
_CACHE_MAX = 2000


def _is_public(ip):
    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return False


def lookup(ip):
    """{'country','city','lat','lon'} or None."""
    if not ip or not _is_public(ip):
        return None
    if ip in _CACHE:
        return _CACHE[ip]
    try:
        data = requests.get(LOOKUP_URL.format(ip=ip), timeout=TIMEOUT_SECONDS).json()
        if not data.get('success'):
            return None
        result = {'country': data.get('country') or '', 'city': data.get('city') or '',
                  'lat': data.get('latitude'), 'lon': data.get('longitude')}
    except Exception as e:  # network down, rate limit, bad JSON
        print(f'geoip lookup failed for {ip}: {e}')
        return None
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()
    _CACHE[ip] = result
    return result
