"""
app/services/turnstile.py
=========================
Cloudflare Turnstile (anti-bot) for the login and register forms.

Enabled only when BOTH RECAPTCHA_SITE_KEY and RECAPTCHA_SECRET_KEY are configured (these Railway variables hold
the Cloudflare Turnstile site/secret keys; the names are historical). Without keys the
forms work as before (nothing is faked or defaulted) and a warning is logged at startup.
When enabled, verification fails closed: a missing/invalid token or an unreachable Cloudflare = rejected.
"""
import requests
from flask import current_app, request

VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
FIELD = 'cf-turnstile-response'
TIMEOUT_SECONDS = 5


def is_enabled():
    cfg = current_app.config
    return bool(cfg.get('RECAPTCHA_SITE_KEY') and cfg.get('RECAPTCHA_SECRET_KEY'))


def site_key():
    """Public key for the widget; '' when protection is off (templates render nothing)."""
    return current_app.config['RECAPTCHA_SITE_KEY'] if is_enabled() else ''


def client_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()


def verify_request():
    """True when protection is off or the token of the current form post is valid."""
    if not is_enabled():
        return True
    token = (request.form.get(FIELD) or '').strip()
    if not token:
        return False
    try:
        res = requests.post(VERIFY_URL, timeout=TIMEOUT_SECONDS, data={
            'secret': current_app.config['RECAPTCHA_SECRET_KEY'], 'response': token, 'remoteip': client_ip(),
        })
        return bool(res.json().get('success'))
    except (requests.RequestException, ValueError):
        current_app.logger.warning('Turnstile verification could not be completed')
        return False
