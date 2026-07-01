import os
import requests
import threading

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
MAIL_FROM = os.environ.get("MAIL_FROM", "noreply@maritimetests.bg")
MAIL_FROM_NAME = os.environ.get("MAIL_FROM_NAME", "Морски Тестове")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@maritimetests.bg")

PLAN_LABELS = {
    'basic': 'Basic — 7 дни достъп',
    'plus':  'Plus — 30 дни достъп',
    'gold':  'Gold — 10 промокода',
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


def send_otp_email(to_email, otp_code):
    html_content = (
        '<div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:32px;background:#071a2e;border-radius:16px">'
        '<h2 style="color:#e8a020;font-size:22px;margin-bottom:12px">⚓ Морски Тестове</h2>'
        '<h3 style="color:#fff;margin-bottom:16px">Потвърди акаунта си</h3>'
        '<p style="color:rgba(232,237,242,0.8);margin-bottom:24px">Въведи кода по-долу. Кодът е валиден 5 минути.</p>'
        '<div style="background:#635BFF;border-radius:12px;padding:24px;text-align:center;margin-bottom:24px">'
        '<span style="color:#fff;font-size:36px;font-weight:700;letter-spacing:8px">' + str(otp_code) + '</span>'
        '</div>'
        '<p style="color:rgba(232,237,242,0.4);font-size:12px">Ако не си се регистрирал — игнорирай този имейл.</p>'
        '</div>'
    )
    text_content = f'Твоят код за верификация е: {otp_code}\n\nВалиден е 5 минути.'
    subject = f'Код за верификация: {otp_code} — Морски Тестове'
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
    BASE_URL = os.environ.get("BASE_URL", "https://web-production-ca6b6.up.railway.app")
    verify_url = f"{BASE_URL}/verify-email/{token}"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:32px;background:#071a2e;border-radius:16px">
      <h2 style="color:#e8a020;font-size:22px;margin-bottom:12px">⚓ Морски Тестове</h2>
      <h3 style="color:#fff;margin-bottom:16px">Потвърди имейла си</h3>
      <p style="color:rgba(232,237,242,0.8);margin-bottom:24px">Благодарим за регистрацията! Натисни бутона за да активираш акаунта си.</p>
      <a href="{verify_url}" style="display:inline-block;background:#635BFF;color:#fff;padding:14px 32px;border-radius:10px;text-decoration:none;font-weight:600;font-size:15px">Потвърди акаунта →</a>
      <p style="color:rgba(232,237,242,0.4);font-size:12px;margin-top:24px">Линкът е валиден 24 часа.</p>
    </div>
    """
    text = f"Потвърди имейла си:\n\n{verify_url}\n\nЛинкът е валиден 24 часа."
    return _brevo_send(to_email, "Потвърди имейла си — Морски Тестове", text, html)


def send_verification_email_async(to_email, token):
    t = threading.Thread(target=send_verification_email, args=(to_email, token))
    t.daemon = True
    t.start()


def send_signal_notification(user_name, user_email, sig_type, message):
    type_labels = {'bug': 'Проблем', 'suggestion': 'Предложение', 'question': 'Въпрос'}
    type_label = type_labels.get(sig_type, sig_type)
    subject = f"[Морски Тестове] Нов сигнал: {type_label}"
    body = f"Нов сигнал от потребител\n\nОт: {user_name} ({user_email})\nТип: {type_label}\n\nСъобщение:\n{message}\n\n---\nОтговорете от Admin панела: https://web-production-ca6b6.up.railway.app/admin/signals"
    _brevo_send(ADMIN_EMAIL, subject, body)


def send_reply_notification(user_email, user_name, reply):
    subject = "Отговор на вашето съобщение | Морски Тестове"
    body = f"Здравейте, {user_name}!\n\nПолучихте отговор:\n\n{reply}\n\n---\nhttps://web-production-ca6b6.up.railway.app/dashboard\n\nМорски Тестове"
    _brevo_send(user_email, subject, body)


def send_new_ticket_notification(user_name, user_email, subject, body, ticket_id):
    _brevo_send(ADMIN_EMAIL,
        f"[Support] Нов ticket: {subject}",
        f"От: {user_name} ({user_email})\n\n{body}\n\nОтговорете: https://web-production-ca6b6.up.railway.app/admin/support")


def send_user_reply_notification(user_name, user_email, subject, body, ticket_id):
    _brevo_send(ADMIN_EMAIL,
        f"[Support] Нов отговор: {subject}",
        f"От: {user_name} ({user_email})\n\n{body}\n\nВижте: https://web-production-ca6b6.up.railway.app/admin/support")


def send_admin_reply_notification(user_email, user_name, subject, body, ticket_id):
    _brevo_send(user_email,
        "Отговор на вашето запитване | Морски Тестове",
        f"Здравейте, {user_name}!\n\nПолучихте отговор на: {subject}\n\n{body}\n\nhttps://web-production-ca6b6.up.railway.app/dashboard\n\nМорски Тестове")


# ---------------------------------------------------------------------------
# Billing известия
# ---------------------------------------------------------------------------

def send_plan_activated(to_email: str, user_name: str, plan_name: str) -> bool:
    """Клиентът получава потвърждение след активиран Basic/Plus план."""
    plan_label = PLAN_LABELS.get(plan_name, plan_name.capitalize())
    html = (
        '<div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:32px;background:#071a2e;border-radius:16px">'
        '<h2 style="color:#e8a020;font-size:22px;margin-bottom:12px">⚓ Морски Тестове</h2>'
        f'<h3 style="color:#fff;margin-bottom:16px">Планът ти е активиран! 🎉</h3>'
        f'<p style="color:rgba(232,237,242,0.8);margin-bottom:8px">Здравей, <strong style="color:#fff">{user_name}</strong>!</p>'
        f'<p style="color:rgba(232,237,242,0.8);margin-bottom:24px">Успешно активира план <strong style="color:#e8a020">{plan_label}</strong>. Вече имаш пълен достъп до всички тестове.</p>'
        '<a href="https://web-production-ca6b6.up.railway.app/dashboard" style="display:inline-block;background:#635BFF;color:#fff;padding:14px 32px;border-radius:10px;text-decoration:none;font-weight:600;font-size:15px">Към платформата →</a>'
        '<p style="color:rgba(232,237,242,0.4);font-size:12px;margin-top:24px">Морски Тестове · maritimetests.bg</p>'
        '</div>'
    )
    text = f"Здравей, {user_name}!\n\nПланът ти {plan_label} е активиран успешно.\n\nhttps://web-production-ca6b6.up.railway.app/dashboard\n\nМорски Тестове"
    return _brevo_send(to_email, f'Планът ти е активиран — {plan_label} | Морски Тестове', text, html)


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
    BASE_URL = os.environ.get("BASE_URL", "https://web-production-ca6b6.up.railway.app")
    expires_label = expires_at.strftime('%d %b %Y') if expires_at else ''

    cards_html = []
    for code in codes:
        activate_url = f"{BASE_URL}/activate?code={code}"
        qr_b64 = _make_qr_base64(activate_url)
        qr_img = (
            f'<img src="data:image/png;base64,{qr_b64}" width="100" height="100" '
            f'style="display:block;border-radius:6px;background:#fff;padding:6px" />'
            if qr_b64 else ''
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
        '<h2 style="color:#e8a020;font-size:22px;margin-bottom:12px">⚓ Maritime Tests</h2>'
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
    text = f"Hi {user_name},\n\nYour 10 Gold promo codes (valid until {expires_label}):\n\n{codes_text}\n\nMaritime Tests"
    return _brevo_send(to_email, 'Your Gold promo codes — Maritime Tests', text, html)


def send_shared_promo_code(to_email: str, from_name: str, code: str, expires_at=None) -> bool:
    """
    Изпраща ЕДИН промокод (с вградено QR изображение) до имейла на получателя,
    когато подателят го споделя от 'Share this code' страницата.
    """
    BASE_URL = os.environ.get("BASE_URL", "https://web-production-ca6b6.up.railway.app")
    activate_url = f"{BASE_URL}/activate?code={code}"
    expires_label = expires_at.strftime('%d %b %Y') if expires_at else ''
    qr_b64 = _make_qr_base64(activate_url)
    qr_img = (
        f'<img src="data:image/png;base64,{qr_b64}" width="140" height="140" '
        f'style="display:block;border-radius:8px;background:#fff;padding:8px;margin:0 auto" />'
        if qr_b64 else ''
    )
    html = (
        '<div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:32px;background:#071a2e;border-radius:16px;text-align:center">'
        '<h2 style="color:#e8a020;font-size:22px;margin-bottom:12px">⚓ Maritime Tests</h2>'
        f'<h3 style="color:#fff;margin-bottom:16px">{from_name} shared a Gold code with you 🥇</h3>'
        f'{qr_img}'
        f'<div style="font-family:monospace;font-size:20px;color:#e8a020;letter-spacing:2px;margin:20px 0 6px">{code}</div>'
        f'<div style="color:rgba(232,237,242,0.6);font-size:12px;margin-bottom:24px">Valid until {expires_label}</div>'
        f'<a href="{activate_url}" style="display:inline-block;background:#635BFF;color:#fff;padding:14px 32px;'
        f'border-radius:10px;text-decoration:none;font-weight:600;font-size:15px">Activate now →</a>'
        '<p style="color:rgba(232,237,242,0.5);font-size:12px;margin-top:24px">Scan the QR code or tap the button above. '
        'Gives 30 days of full access to Maritime Tests.</p>'
        '<p style="color:rgba(232,237,242,0.4);font-size:12px;margin-top:24px">© 2026 maradtest.com. All rights reserved.</p>'
        '</div>'
    )
    text = (
        f"{from_name} shared a Maritime Tests Gold code with you:\n\n{code}\n\n"
        f"Activate it here: {activate_url}\n\nValid until {expires_label}."
    )
    return _brevo_send(to_email, f'{from_name} shared a Gold code with you — Maritime Tests', text, html)


def send_admin_new_payment(user_name: str, user_email: str, plan_name: str) -> bool:
    """Админът получава известие при всяко ново плащане."""
    plan_label = PLAN_LABELS.get(plan_name, plan_name.capitalize())
    subject = f'[Плащане] {user_name} — {plan_label}'
    body = (
        f'Ново плащане получено!\n\n'
        f'Потребител: {user_name}\n'
        f'Имейл: {user_email}\n'
        f'План: {plan_label}\n\n'
        f'https://web-production-ca6b6.up.railway.app/admin/users'
    )
    return _brevo_send(ADMIN_EMAIL, subject, body)
