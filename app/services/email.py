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


def send_gold_promo_codes(to_email: str, user_name: str, codes: list) -> bool:
    """Клиентът получава 10-те Gold промокода."""
    codes_html = ''.join(
        f'<div style="background:#1a2f4a;border-radius:8px;padding:12px 16px;margin-bottom:8px;font-family:monospace;font-size:18px;color:#e8a020;letter-spacing:2px">{code}</div>'
        for code in codes
    )
    codes_text = '\n'.join(f'  {i+1}. {code}' for i, code in enumerate(codes))
    html = (
        '<div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:32px;background:#071a2e;border-radius:16px">'
        '<h2 style="color:#e8a020;font-size:22px;margin-bottom:12px">⚓ Морски Тестове</h2>'
        '<h3 style="color:#fff;margin-bottom:16px">Твоите Gold промокода 🥇</h3>'
        f'<p style="color:rgba(232,237,242,0.8);margin-bottom:8px">Здравей, <strong style="color:#fff">{user_name}</strong>!</p>'
        '<p style="color:rgba(232,237,242,0.8);margin-bottom:24px">Получаваш 10 промокода. Всеки дава <strong style="color:#e8a020">30 дни пълен достъп</strong> и е валиден 12 месеца.</p>'
        f'{codes_html}'
        '<p style="color:rgba(232,237,242,0.4);font-size:12px;margin-top:24px">Морски Тестове · maritimetests.bg</p>'
        '</div>'
    )
    text = f"Здравей, {user_name}!\n\nТвоите 10 Gold промокода:\n\n{codes_text}\n\nМорски Тестове"
    return _brevo_send(to_email, 'Твоите Gold промокода — Морски Тестове', text, html)


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
