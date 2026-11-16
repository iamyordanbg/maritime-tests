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


def test_otp_submit_guard_is_taken_before_request_and_always_released():
    src = BASE_JS.read_text(encoding='utf-8')
    body = src[src.index('async function submitOTP'):src.index('let forgotTimerInt')]
    assert 'if (_otpSubmitting) return;' in body
    # непълен код: съобщение, без заключване
    assert body.index('otp.length < 6') < body.index('_otpSubmitting = true')
    # заключване преди заявката
    assert body.index('_otpSubmitting = true') < body.index("fetch('/verify-otp'")
    # мрежова грешка/грешен код никога не оставят формата заключена
    assert 'catch' in body and 'finally' in body
    assert body.index('finally') < body.rindex('_otpSubmitting = false')


def test_otp_modal_has_visible_verify_button():
    html = (Path(__file__).resolve().parents[2] / 'app' / 'templates' / 'layouts' / 'base.html').read_text(encoding='utf-8')
    m = re.search(r'<button[^>]*id="otpSubmit"[^>]*>', html)
    assert m, 'Verify button missing'
    assert 'display:none' not in m.group(0).replace(' ', '')
    assert 'type="submit"' in m.group(0)


def test_forgot_password_send_button_is_guarded_against_double_click():
    """Всеки POST /reset-password създава нов код и праща имейл (старият спира да важи) -
    затова 'Send code' не може да праща втора заявка, докато първата тече."""
    src = BASE_JS.read_text(encoding='utf-8')
    body = src[src.index('async function forgotSendOTP'):src.index('function startForgotTimer')]
    assert 'if (_forgotSending) return;' in body
    assert body.index('_forgotSending = true') < body.index("fetch('/reset-password'")
    assert 'finally' in body and '_forgotSending = false' in body       # пак може да се натисне след грешка
    html = (Path(__file__).resolve().parents[2] / 'app' / 'templates' / 'layouts' / 'base.html').read_text(encoding='utf-8')
    assert '[["forgotSendOTP","$this"]]' in html
