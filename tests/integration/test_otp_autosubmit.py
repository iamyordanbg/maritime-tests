"""
tests/integration/test_otp_autosubmit.py
========================================
Регресия: OTP формата се изпраща автоматично след 6-ата цифра със синтетично
'submit' събитие. Събития се обработват делегирано от ui-actions.js на ниво
document, затова събитието ТРЯБВА да е с bubbles:true - иначе нищо не се
случва след въвеждане на кода (реален бъг от production). Пълният браузърен
тест (писане, поставяне, грешен код) е пуснат ръчно с Playwright.
"""
import re
from pathlib import Path

BASE_JS = Path(__file__).resolve().parents[2] / 'app' / 'static' / 'js' / 'base.js'


def test_every_synthetic_otp_submit_bubbles():
    src = BASE_JS.read_text(encoding='utf-8')
    events = re.findall(r"new Event\('submit'\s*,\s*\{([^}]*)\}\)", src)
    assert len(events) >= 2
    for opts in events:
        assert 'bubbles: true' in opts, f"synthetic submit event without bubbles: {opts}"


def test_otp_double_submit_guard_is_not_reset_before_the_request():
    src = BASE_JS.read_text(encoding='utf-8')
    body = src[src.index('async function submitOTP'):src.index('let forgotTimerInt')]
    before_fetch = body[:body.index("fetch('/verify-otp'")]
    # единственото нулиране преди заявката е при непълен код (връщане от функцията)
    assert before_fetch.count('_otpSubmitting = false') == 1
    assert "if (otp.length < 6) {\n    _otpSubmitting = false;" in before_fetch
