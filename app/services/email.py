import os
import requests
import threading

from app.services.site import SITE_NAME
OTP_VALID_MINUTES = 5          # срок на OTP кода (email текст + auth.py expiry)
VERIFY_LINK_VALID_HOURS = 24   # срок, обявен в имейла с линк за потвърждение

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
MAIL_FROM = os.environ.get("MAIL_FROM", "noreply@maritimetests.bg")
MAIL_FROM_NAME = os.environ.get("MAIL_FROM_NAME", SITE_NAME)
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@maritimetests.bg")

PLAN_LABELS = {
    'basic': 'Basic — 7 days of access',
    'plus':  'Plus — 30 days of access',
    'gold':  'Gold — 10 promo codes',
    'all_mistakes': 'All Mistakes — extra access',
}


def _brevo_send(to_email, subject, text_content, html_content=None):
    """Базова функция за изпращане през Brevo API."""
    if not BREVO_API_KEY:
        print("BREVO_API_KEY not set", flush=True)
        return False
    payload = {
        'sender': {'name': MAIL_FROM_NAME, 'email': MAIL_FROM},
        'to': [{'email': to_email}],
        'subject': subject,
        'textContent': text_content,
    }
    if html_content:
        payload['htmlContent'] = html_content
    try:
        r = requests.post(
            'https://api.brevo.com/v3/smtp/email',
            headers={'api-key': BREVO_API_KEY, 'Content-Type': 'application/json'},
            json=payload,
            timeout=15
        )
        if r.status_code == 201:
            print(f"✓ Email sent to {to_email}", flush=True)
            return True
        print(f"Brevo error: {r.status_code} - {r.text}", flush=True)
        return False
    except Exception as e:
        print(f"Brevo exception: {e}", flush=True)
        return False


def send_email(to_email, subject, body, html_content=None):
    """Общ имейл — text + опционален HTML."""
    return _brevo_send(to_email, subject, body, html_content)




def _email_card(inner_html):
    """Общата обвивка за верификационните имейли: table layout (работи в Gmail/Outlook/
    мобилни клиенти), горе е името на сайта MARADTEST.COM, ширината се свива на телефон."""
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="padding:0"><tr><td align="center">'
        '<table role="presentation" width="500" cellpadding="0" cellspacing="0" '
        'style="max-width:500px;width:100%;background:#071a2e;border-radius:16px">'
        '<tr><td align="center" style="padding:32px 32px 8px">'
        f'<span style="color:#e8a020;font-size:14px;font-weight:700;letter-spacing:2px;'
        f'font-family:Arial,sans-serif">{SITE_NAME}</span></td></tr>'
        f'<tr><td style="padding:16px 32px 32px;font-family:Arial,sans-serif">{inner_html}</td></tr>'
        '</table></td></tr></table>'
    )


def base_url():
    """Публичният адрес на сайта за линковете в имейлите."""
    return os.environ.get("BASE_URL", "https://web-production-ca6b6.up.railway.app")


def send_otp_email(to_email, otp_code):
    html_content = _email_card(
        '<h3 style="color:#fff;font-size:20px;margin:0 0 12px">Verify your account</h3>'
        '<p style="color:rgba(232,237,242,0.8);font-size:15px;line-height:1.5;margin:0 0 24px">'
        f'Enter the code below to finish creating your account. The code is valid for {OTP_VALID_MINUTES} minutes.</p>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px">'
        '<tr><td align="center" style="background:#635BFF;border-radius:12px;padding:22px 12px">'
        f'<span style="color:#fff;font-size:34px;font-weight:700;letter-spacing:8px">{otp_code}</span>'
        '</td></tr></table>'
        '<p style="color:rgba(232,237,242,0.5);font-size:12px;line-height:1.5;margin:0">'
        'If you did not sign up, you can safely ignore this email.</p>'
    )
    text_content = (
        f'{SITE_NAME}\n\nYour verification code is: {otp_code}\n\n'
        f'It is valid for {OTP_VALID_MINUTES} minutes. If you did not sign up, ignore this email.'
    )
    subject = f'Your verification code: {otp_code} — {SITE_NAME}'
    return _brevo_send(to_email, subject, text_content, html_content)


def send_otp_async(to_email, otp_code):
    def _run():
        try:
            send_otp_email(to_email, otp_code)
        except Exception as e:
            print(f"OTP ASYNC THREAD ERROR: {e}", flush=True)
    t = threading.Thread(target=_run)
    t.daemon = True
    t.start()


def send_verification_email(to_email, token):
    verify_url = f"{base_url()}/verify-email/{token}"
    html = _email_card(
        '<h3 style="color:#fff;font-size:20px;margin:0 0 12px">Confirm your email</h3>'
        '<p style="color:rgba(232,237,242,0.8);font-size:15px;line-height:1.5;margin:0 0 24px">'
        'Thanks for signing up! Tap the button below to activate your account.</p>'
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin-bottom:24px"><tr>'
        '<td align="center" style="background:#635BFF;border-radius:10px">'
        f'<a href="{verify_url}" style="display:inline-block;padding:14px 32px;color:#fff;'
        'text-decoration:none;font-weight:600;font-size:15px">Confirm my account &rarr;</a>'
        '</td></tr></table>'
        '<p style="color:rgba(232,237,242,0.5);font-size:12px;line-height:1.5;margin:0">'
        f'This link is valid for {VERIFY_LINK_VALID_HOURS} hours. If you did not sign up, you can safely ignore this email.</p>'
    )
    text = (
        f"{SITE_NAME}\n\nConfirm your email:\n\n{verify_url}\n\n"
        f"This link is valid for {VERIFY_LINK_VALID_HOURS} hours. If you did not sign up, ignore this email."
    )
    return _brevo_send(to_email, f"Confirm your email — {SITE_NAME}", text, html)


def send_verification_email_async(to_email, token):
    t = threading.Thread(target=send_verification_email, args=(to_email, token))
    t.daemon = True
    t.start()


def send_signal_notification(user_name, user_email, sig_type, message):
    type_labels = {'bug': 'Problem', 'suggestion': 'Suggestion', 'question': 'Question'}
    type_label = type_labels.get(sig_type, sig_type)
    subject = f"[{SITE_NAME}] New signal: {type_label}"
    body = f"New signal from a user\n\nFrom: {user_name} ({user_email})\nType: {type_label}\n\nMessage:\n{message}\n\n---\nReply from the admin panel: {base_url()}/admin/signals"
    _brevo_send(ADMIN_EMAIL, subject, body)


def send_reply_notification(user_email, user_name, reply):
    subject = f"Reply to your message — {SITE_NAME}"
    body = f"Hi {user_name},\n\nYou have received a reply:\n\n{reply}\n\n---\n{base_url()}/dashboard\n\n{SITE_NAME}"
    _brevo_send(user_email, subject, body)


def send_new_ticket_notification(user_name, user_email, subject, body, ticket_id):
    _brevo_send(ADMIN_EMAIL,
        f"[Support] New ticket: {subject}",
        f"From: {user_name} ({user_email})\n\n{body}\n\nReply: {base_url()}/admin/support")


def send_user_reply_notification(user_name, user_email, subject, body, ticket_id):
    _brevo_send(ADMIN_EMAIL,
        f"[Support] New reply: {subject}",
        f"From: {user_name} ({user_email})\n\n{body}\n\nView: {base_url()}/admin/support")


def send_admin_reply_notification(user_email, user_name, subject, body, ticket_id):
    _brevo_send(user_email,
        f"Reply to your request — {SITE_NAME}",
        f"Hi {user_name},\n\nYou have received a reply to: {subject}\n\n{body}\n\n{base_url()}/dashboard\n\n{SITE_NAME}")


# ---------------------------------------------------------------------------
# Billing известия
# ---------------------------------------------------------------------------

def _payment_email(to_email, user_name, title, intro_html, intro_text, subject):
    """Общият шаблон на имейлите за успешно плащане (MARADTEST.COM, на английски)."""
    dash = f"{base_url()}/dashboard"
    html = _email_card(
        f'<h3 style="color:#fff;margin:0 0 16px;font-size:18px">{title}</h3>'
        f'<p style="color:rgba(232,237,242,0.8);margin:0 0 8px">Hi <strong style="color:#fff">{user_name}</strong>,</p>'
        f'<p style="color:rgba(232,237,242,0.8);margin:0 0 24px">{intro_html}</p>'
        f'<a href="{dash}" style="display:inline-block;background:#635BFF;color:#fff;padding:14px 32px;'
        f'border-radius:10px;text-decoration:none;font-weight:600;font-size:15px">Go to the platform →</a>'
        f'<p style="color:rgba(232,237,242,0.4);font-size:12px;margin:24px 0 0">© 2026 {SITE_NAME}. All rights reserved.</p>'
    )
    text = f"Hi {user_name},\n\n{intro_text}\n\n{dash}\n\n{SITE_NAME}"
    return _brevo_send(to_email, subject, text, html)


def send_plan_activated(to_email: str, user_name: str, plan_name: str) -> bool:
    """Customer receives a confirmation after a Basic/Plus plan is activated."""
    plan_label = PLAN_LABELS.get(plan_name, plan_name.capitalize())
    return _payment_email(
        to_email, user_name, 'Your plan is active 🎉',
        f'Your <strong style="color:#e8a020">{plan_label}</strong> plan has been activated. '
        'You now have full access to all tests.',
        f'Your {plan_label} plan has been activated. You now have full access to all tests.',
        f'Your plan is active — {plan_label} | {SITE_NAME}')


def send_all_mistakes_activated(to_email: str, user_name: str, test_title: str, expires_at, quota: int) -> bool:
    """Customer receives a confirmation after buying extra All Mistakes access for one test."""
    until = expires_at.strftime('%d %b %Y') if expires_at else ''
    return _payment_email(
        to_email, user_name, 'All Mistakes access is active 🎉',
        f'Your extra <strong style="color:#e8a020">All Mistakes</strong> access for '
        f'<strong style="color:#fff">{test_title}</strong> is active until '
        f'<strong style="color:#e8a020">{until}</strong> ({quota} solves included).',
        f'Your extra All Mistakes access for {test_title} is active until {until} ({quota} solves included).',
        f'All Mistakes access is active | {SITE_NAME}')


def _make_qr_base64(data: str) -> str:
    """Генерира QR код като base64 PNG за вграждане в имейл (data URI)."""
    try:
        import qrcode
        import base64
        from io import BytesIO
        img = qrcode.make(data, box_size=6, border=2)
        buf = BytesIO()
        img.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception as e:
        print(f"QR generation error: {e}", flush=True)
        return ''


def send_gold_promo_codes(to_email: str, user_name: str, codes: list, expires_at=None) -> bool:
    """Customer receives their 10 Gold promo codes, each with a QR code and a share link."""
    import urllib.parse as _url
    BASE_URL = base_url()
    expires_label = expires_at.strftime('%d %b %Y') if expires_at else ''

    cards_html = []
    for code in codes:
        activate_url = f"{BASE_URL}/activate?code={code}"
        qr_url = f"{BASE_URL}/qr/{code}.png"
        qr_img = (
            f'<img src="{qr_url}" width="100" height="100" alt="QR code" '
            f'style="display:block;border-radius:6px;background:#fff;padding:6px" />'
        )
        share_href = f"{BASE_URL}/promo/share?code={_url.quote(code)}"

        cards_html.append(
            '<table role="presentation" style="width:100%;background:#1a2f4a;border-radius:8px;'
            'margin-bottom:10px"><tr>'
            f'<td style="padding:14px">{qr_img}</td>'
            '<td style="padding:14px;vertical-align:middle">'
            f'<div style="font-family:monospace;font-size:18px;color:#e8a020;letter-spacing:2px;margin-bottom:6px">{code}</div>'
            f'<div style="color:rgba(232,237,242,0.6);font-size:12px;margin-bottom:8px">Valid until {expires_label}</div>'
            f'<a href="{share_href}" style="color:#fff;background:#635BFF;text-decoration:none;font-size:12px;'
            f'font-weight:600;padding:6px 12px;border-radius:6px;display:inline-block">Share this code →</a>'
            '</td></tr></table>'
        )
    codes_html = ''.join(cards_html)
    codes_text = '\n'.join(
        f"  {i+1}. {code} — {BASE_URL}/activate?code={code} (valid until {expires_label})"
        for i, code in enumerate(codes)
    )

    html = (
        '<div style="font-family:Arial,sans-serif;max-width:540px;margin:0 auto;padding:32px;background:#071a2e;border-radius:16px">'
        f'<h2 style="color:#e8a020;font-size:22px;margin-bottom:12px">⚓ {SITE_NAME}</h2>'
        '<h3 style="color:#fff;margin-bottom:16px">Your Gold promo codes 🥇</h3>'
        f'<p style="color:rgba(232,237,242,0.8);margin-bottom:8px">Hi <strong style="color:#fff">{user_name}</strong>,</p>'
        '<p style="color:rgba(232,237,242,0.8);margin-bottom:24px">You\'ve received 10 promo codes. Each one gives '
        f'<strong style="color:#e8a020">30 days of full access</strong> and can be activated until '
        f'<strong style="color:#e8a020">{expires_label}</strong>.</p>'
        f'{codes_html}'
        '<p style="color:rgba(232,237,242,0.8);font-size:13px;margin-top:20px">Scan a QR code or enter a code at '
        f'<a href="{BASE_URL}/activate" style="color:#e8a020">maradtest.com/activate</a>. '
        'Use "Share this code" to forward a code by email — the recipient can scan the QR or open the link to activate it directly.</p>'
        '<p style="color:rgba(232,237,242,0.4);font-size:12px;margin-top:24px">© 2026 maradtest.com. All rights reserved.</p>'
        '</div>'
    )
    text = f"Hi {user_name},\n\nYour 10 Gold promo codes (valid until {expires_label}):\n\n{codes_text}\n\n{SITE_NAME}"
    return _brevo_send(to_email, f'Your Gold promo codes — {SITE_NAME}', text, html)


def send_shared_promo_code(to_email: str, from_name: str, code: str, expires_at=None) -> bool:
    """
    Изпраща ЕДИН промокод (с вградено QR изображение) до имейла на получателя,
    когато подателят го споделя от 'Share this code' страницата.

    ВАЖНО (научени по трудния начин): Gmail и повечето имейл клиенти STRIP-ват
    'position:absolute/relative' от inline стиловете по сигурностни причини -
    затова предишен опит с наслоени <div>-ове за иконата на фара се чупеше и
    се виждаше като безформена буца. Решение: истинско PNG изображение
    (хоствано, точно като QR кода), не CSS форми. Целият layout е с <table>
    вместо <div> с flex/absolute позициониране - table е единственият layout
    механизъм с наистина универсална поддръжка в имейл клиенти.
    """
    BASE_URL = base_url()
    activate_url = f"{BASE_URL}/activate?code={code}"
    expires_label = expires_at.strftime('%d %b %Y') if expires_at else ''
    qr_url = f"{BASE_URL}/qr/{code}.png"
    badge_url = f"{BASE_URL}/static/email/lighthouse-badge.png"

    html = f'''
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#050d18;padding:40px 16px">
<tr><td align="center">
<table role="presentation" width="460" cellpadding="0" cellspacing="0" style="max-width:460px;width:100%;background:#0d1b2f;border-radius:20px;border:1px solid rgba(232,160,32,0.15)">
  <tr><td style="padding:40px 36px 8px" align="center">
    <img src="{badge_url}" width="64" height="64" alt="maradtest.com" style="display:block;border-radius:50%;margin:0 auto 20px">
    <a href="{BASE_URL}" style="color:#e8a020;font-size:12px;font-weight:700;letter-spacing:2px;text-decoration:none">{SITE_NAME}</a>
  </td></tr>
  <tr><td style="padding:10px 36px 0" align="center">
    <p style="color:#ffffff;font-size:19px;font-weight:600;margin:0;line-height:1.4;font-family:Arial,sans-serif">{from_name} shared a Gold code with you 🥇</p>
  </td></tr>
  <tr><td style="padding:28px 36px 0">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:rgba(255,255,255,0.04);border-radius:14px">
      <tr><td style="padding:24px" align="center">
        <img src="{qr_url}" width="150" height="150" alt="QR code" style="display:block;border-radius:10px;margin:0 auto">
        <p style="font-family:monospace;font-size:22px;font-weight:700;color:#e8a020;letter-spacing:3px;margin:20px 0 6px">{code}</p>
        <p style="color:rgba(232,237,242,0.5);font-size:12px;margin:0;font-family:Arial,sans-serif">Valid until {expires_label}</p>
      </td></tr>
    </table>
  </td></tr>
  <tr><td style="padding:24px 36px 0">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr><td align="center" style="background:#e8a020;border-radius:12px">
        <a href="{activate_url}" style="display:block;padding:18px;color:#0d1b2f;text-decoration:none;font-weight:800;font-size:17px;letter-spacing:0.3px;font-family:Arial,sans-serif">Activate now</a>
      </td></tr>
    </table>
  </td></tr>
  <tr><td style="padding:26px 36px 0" align="center">
    <p style="color:rgba(232,237,242,0.45);font-size:12px;line-height:1.6;margin:0;font-family:Arial,sans-serif">Scan the QR code or tap the button above.<br>Gives 30 days of full access to maradtest.com.</p>
  </td></tr>
  <tr><td style="padding:24px 36px 40px" align="center">
    <p style="color:rgba(232,237,242,0.3);font-size:11px;margin:0;font-family:Arial,sans-serif">© 2026 maradtest.com. All rights reserved.</p>
  </td></tr>
</table>
</td></tr>
</table>
'''
    text = (
        f"{from_name} shared a maradtest.com Gold code with you:\n\n{code}\n\n"
        f"Activate it here: {activate_url}\n\nValid until {expires_label}."
    )
    return _brevo_send(to_email, f'{from_name} shared a Gold code with you — maradtest.com', text, html)


def send_share_confirmation(to_email: str, code: str, recipient_email: str) -> bool:
    """Потвърждение до самия платец, че е споделил код — официална следа освен popup-а на сайта."""
    subject = f'Confirmed: you shared {code} with {recipient_email}'
    text = f"This confirms you shared your Gold code {code} with {recipient_email}.\n\n{SITE_NAME}"
    html = (
        '<div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:28px;background:#071a2e;border-radius:16px">'
        '<h3 style="color:#fff;margin-bottom:12px">✓ Share confirmed</h3>'
        f'<p style="color:rgba(232,237,242,0.8);font-size:14px">You shared code '
        f'<strong style="color:#e8a020;font-family:monospace">{code}</strong> with '
        f'<strong style="color:#fff">{recipient_email}</strong>.</p>'
        '<p style="color:rgba(232,237,242,0.4);font-size:12px;margin-top:20px">© 2026 maradtest.com. All rights reserved.</p>'
        '</div>'
    )
    return _brevo_send(to_email, subject, text, html)


def send_admin_new_payment(user_name: str, user_email: str, plan_name: str) -> bool:
    """The admin is notified about every new payment."""
    plan_label = PLAN_LABELS.get(plan_name, plan_name.capitalize())
    subject = f'[Payment] {user_name} — {plan_label}'
    body = (
        f'New payment received!\n\n'
        f'User: {user_name}\n'
        f'Email: {user_email}\n'
        f'Plan: {plan_label}\n\n'
        f'{base_url()}/admin/users'
    )
    return _brevo_send(ADMIN_EMAIL, subject, body)


def send_review_reminder_email(to_email, decline_url, dashboard_url):
    """Напомняне седмица след "Not now": същият прозорец, но само с два избора -
    No thanks (потвърждаваща страница) и Submit review (към таблото)."""
    html = _email_card(
        '<h3 style="color:#fff;font-size:20px;margin:0 0 12px;text-align:center">Your opinion matters to us</h3>'
        '<p style="color:rgba(232,237,242,0.8);font-size:15px;line-height:1.5;margin:0 0 8px;text-align:center">'
        'What do you think about the platform? Did we help improve your results?</p>'
        '<p style="color:#e8a020;font-size:26px;letter-spacing:4px;margin:0 0 24px;text-align:center">&#9733;&#9733;&#9733;&#9733;&#9733;</p>'
        '<table role="presentation" align="center" cellpadding="0" cellspacing="0" style="margin:0 auto 8px"><tr>'
        '<td align="center" style="background:#1f3550;border-radius:8px">'
        f'<a href="{decline_url}" style="display:inline-block;padding:12px 22px;color:#cbd5e1;text-decoration:none;'
        'font-weight:700;font-size:12px;letter-spacing:1px">NO THANKS</a></td>'
        '<td width="12"></td>'
        '<td align="center" style="background:#f59e0b;border-radius:8px">'
        f'<a href="{dashboard_url}" style="display:inline-block;padding:12px 22px;color:#0b132b;text-decoration:none;'
        'font-weight:700;font-size:12px;letter-spacing:1px">SUBMIT REVIEW</a></td>'
        '</tr></table>'
        '<p style="color:rgba(232,237,242,0.5);font-size:12px;line-height:1.5;margin:16px 0 0;text-align:center">'
        'You are receiving this because you chose &ldquo;Not now&rdquo;. Choose &ldquo;No thanks&rdquo; and we will not ask again.</p>'
    )
    text = (
        f"{SITE_NAME}\n\nYour opinion matters to us.\n"
        "What do you think about the platform? Did we help improve your results?\n\n"
        f"Submit review: {dashboard_url}\nNo thanks (we will not ask again): {decline_url}\n"
    )
    return _brevo_send(to_email, f"Your opinion matters to us — {SITE_NAME}", text, html)
