import os
import requests
import threading

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
MAIL_FROM = os.environ.get("MAIL_FROM", "noreply@maritimetests.bg")
MAIL_FROM_NAME = os.environ.get("MAIL_FROM_NAME", "Морски Тестове")

def send_otp_email(to_email, otp_code):
    """Send OTP code via Brevo API"""
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
    text_content = 'Твоят код за верификация е: ' + str(otp_code) + '\n\nВалиден е 5 минути.'
    subject = 'Код за верификация: ' + str(otp_code) + ' — Морски Тестове'
    
    try:
        payload = {
            'sender': {'name': MAIL_FROM_NAME, 'email': MAIL_FROM},
            'to': [{'email': to_email}],
            'subject': subject,
            'htmlContent': html_content,
            'textContent': text_content
        }
        headers = {
            'api-key': BREVO_API_KEY,
            'Content-Type': 'application/json'
        }
        response = http_requests.post(
            'https://api.brevo.com/v3/smtp/email',
            headers=headers,
            json=payload,
            timeout=15
        )
        if response.status_code == 201:
            print(f"✓ OTP sent to {to_email}")
            return True
        else:
            print(f"OTP email error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"OTP email error: {e}")
        return False

def send_otp_async(to_email, otp_code):
    import threading
    t = threading.Thread(target=send_otp_email, args=(to_email, otp_code))
    t.daemon = True
    t.start()

def send_verification_email(to_email, token):
    """Send verification email via Brevo API (HTTPS)"""
    verify_url = f"{BASE_URL}/verify-email/{token}"
    
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:32px;background:#071a2e;border-radius:16px">
      <h2 style="color:#e8a020;font-size:22px;margin-bottom:12px">⚓ Морски Тестове</h2>
      <h3 style="color:#fff;margin-bottom:16px">Потвърди имейла си</h3>
      <p style="color:rgba(232,237,242,0.8);margin-bottom:24px">
        Благодарим за регистрацията! Натисни бутона за да активираш акаунта си.
      </p>
      <a href="{verify_url}" 
         style="display:inline-block;background:#635BFF;color:#fff;padding:14px 32px;border-radius:10px;text-decoration:none;font-weight:600;font-size:15px">
        Потвърди акаунта →
      </a>
      <p style="color:rgba(232,237,242,0.4);font-size:12px;margin-top:24px">
        Линкът е валиден 24 часа. Ако не си се регистрирал — игнорирай този имейл.
      </p>
    </div>
    """
    
    text = f"Потвърди имейла си:\n\n{verify_url}\n\nЛинкът е валиден 24 часа."
    
    try:
        payload = {
            "sender": {"name": MAIL_FROM_NAME, "email": MAIL_FROM},
            "to": [{"email": to_email}],
            "subject": "Потвърди имейла си — Морски Тестове",
            "htmlContent": html,
            "textContent": text
        }
        
        response = http_requests.post(
            'https://api.brevo.com/v3/smtp/email',
            headers={
                'api-key': BREVO_API_KEY,
                'Content-Type': 'application/json'
            },
            json=payload,
            timeout=15
        )
        
        if response.status_code == 201:
            print(f"✓ Verification email sent to {to_email}")
            return True
        else:
            print(f"Email error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Email error: {e}")
        return False

def send_verification_email_async(to_email, token):
    """Send email in background thread"""
    import threading
    t = threading.Thread(target=send_verification_email, args=(to_email, token))
    t.daemon = True
    t.start()



from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import xlrd, json, random, string

app = Flask(__name__)
app.config['SECRET_KEY'] = 'maritime-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///maritime.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
os.makedirs('/tmp/uploads', exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

db = SQLAlchemy(app)

# ============================================================
#  МОДЕЛИ (Таблици в базата данни)
# ============================================================


def send_email(to_email, subject, body):
    """Изпраща общ имейл чрез Brevo"""
    if not BREVO_API_KEY:
        return False
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"api-key": BREVO_API_KEY, "Content-Type": "application/json"}
    payload = {
        "sender": {"name": "Морски Тестове", "email": MAIL_FROM},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": body
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        return r.status_code == 201
    except Exception:
        return False


def send_signal_notification(user_name, user_email, sig_type, message):
    """Изпраща имейл до admin при нов сигнал"""
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@maritimetests.bg')
    type_labels = {'bug': 'Проблем', 'suggestion': 'Предложение', 'question': 'Въпрос'}
    type_label = type_labels.get(sig_type, sig_type)
    subject = f"[Морски Тестове] Нов сигнал: {type_label}"
    body = f"""Нов сигнал от потребител

От: {user_name} ({user_email})
Тип: {type_label}

Съобщение:
{message}

---
Отговорете от Admin панела: https://web-production-ca6b6.up.railway.app/admin/signals
"""
    send_email(admin_email, subject, body)


def send_reply_notification(user_email, user_name, reply):
    """Изпраща имейл до потребителя при отговор от admin"""
    subject = "Отговор на вашето съобщение | Морски Тестове"
    body = f"""Здравейте, {user_name}!

Получихте отговор на вашето съобщение в Морски Тестове:

{reply}

---
Влезте в платформата за да видите пълната кореспонденция:
https://web-production-ca6b6.up.railway.app/dashboard

Морски Тестове
"""
    send_email(user_email, subject, body)


def send_new_ticket_notification(user_name, user_email, subject, body, ticket_id):
    """Admin получава имейл за нов ticket"""
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@maritimetests.bg')
    send_email(admin_email,
        f"[Support] Нов ticket: {subject}",
        f"От: {user_name} ({user_email})\n\n{body}\n\nОтговорете: https://web-production-ca6b6.up.railway.app/admin/support")

def send_user_reply_notification(user_name, user_email, subject, body, ticket_id):
    """Admin получава имейл за отговор от user"""
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@maritimetests.bg')
    send_email(admin_email,
        f"[Support] Нов отговор: {subject}",
        f"От: {user_name} ({user_email})\n\n{body}\n\nВижте: https://web-production-ca6b6.up.railway.app/admin/support")

def send_admin_reply_notification(user_email, user_name, subject, body, ticket_id):
    """User получава имейл за отговор от admin"""
    send_email(user_email,
        f"Отговор на вашето запитване | Морски Тестове",
        f"Здравейте, {user_name}!\n\nПолучихте отговор на: {subject}\n\n{body}\n\nВлезте за да отговорите:\nhttps://web-production-ca6b6.up.railway.app/dashboard\n\nМорски Тестове")
