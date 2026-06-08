from urllib.parse import urlencode
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.models.user import User
from app.services.email import send_otp_email, send_verification_email
import os
RECAPTCHA_SITE_KEY = os.environ.get("RECAPTCHA_SITE_KEY", "")
RECAPTCHA_SECRET_KEY = os.environ.get("RECAPTCHA_SECRET_KEY", "")
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USER_INFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo' 

def get_google_redirect_uri():
    return os.environ.get('BASE_URL', 'https://web-production-ca6b6.up.railway.app') + '/auth/google/callback'

import os, random, string
from datetime import datetime

auth = Blueprint("auth", __name__)

@auth.route('/auth/google')
def google_login():
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': get_google_redirect_uri(),
        'response_type': 'code',
        'scope': 'openid email profile',
        'access_type': 'offline',
        'prompt': 'select_account'
    }
    return redirect(GOOGLE_AUTH_URL + '?' + urlencode(params))

@auth.route('/auth/google/callback')
def google_callback():
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error or not code:
        flash('Google вход е отказан.', 'error')
        return redirect(url_for('auth.login'))
    
    # Exchange code for token
    token_data = {
        'code': code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': get_google_redirect_uri(),
        'grant_type': 'authorization_code'
    }
    token_resp = http_requests.post(GOOGLE_TOKEN_URL, data=token_data)
    if not token_resp.ok:
        flash('Грешка при Google автентикация.', 'error')
        return redirect(url_for('auth.login'))
    
    access_token = token_resp.json().get('access_token')
    
    # Get user info
    user_info = http_requests.get(
        GOOGLE_USERINFO_URL,
        headers={'Authorization': f'Bearer {access_token}'}
    ).json()
    
    google_email = user_info.get('email', '').lower().strip()
    google_name = user_info.get('name', '')
    google_id = user_info.get('sub', '')
    
    if not google_email:
        flash('Не може да се получи имейл от Google.', 'error')
        return redirect(url_for('auth.login'))
    
    # Find or create user
    user = User.query.filter_by(email=google_email).first()
    
    if user:
        # Existing user - log in
        session['user_id'] = user.id
        redirect_url = url_for('admin.admin_dashboard') if user.is_admin else url_for('dashboard.user_dashboard')
        # Return JSON for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'redirect': redirect_url})
        return redirect(redirect_url)
    else:
        # New user - create account
        new_user = User(
            name=google_name or google_email.split('@')[0],
            email=google_email,
            password=generate_password_hash(google_id + GOOGLE_CLIENT_SECRET[:8]),
            is_admin=False,
            is_active=True
        )
        db.session.add(new_user)
        db.session.commit()
        session['user_id'] = new_user.id
        flash(f'Добре дошъл, {new_user.name}! Акаунтът ти е създаден с Google.', 'success')
        return redirect(url_for('dashboard.user_dashboard'))




@auth.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user and user.is_admin:
            return redirect(url_for('admin.admin_dashboard'))
        return redirect(url_for('dashboard.user_dashboard'))
    return render_template('landing.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            # Block unverified users (only if API key is set)
            if BREVO_API_KEY and not user.is_admin and not user.email_verified:
                flash('Моля потвърди имейла си преди да влезеш.', 'error')
                return render_template('auth/login.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['is_admin'] = user.is_admin
            redirect_url = url_for('admin.admin_dashboard') if user.is_admin else url_for('dashboard.user_dashboard')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'redirect': redirect_url})
            return redirect(redirect_url)
        flash('Грешен имейл или парола', 'error')
    return render_template('auth/login.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

# Simple rate limiting store
_reg_attempts = {}

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Rate limiting disabled during testing
        ip = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1').split(',')[0].strip()
        now = datetime.utcnow()

        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        promo = request.form.get('promo_code', '').strip()

        # Basic validation
        if not email or not password:
            flash('Имейлът и паролата са задължителни.', 'error')
            return render_template('auth/register.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)



        if len(password) < 6:
            flash('Паролата трябва да е поне 6 символа.', 'error')
            return render_template('auth/register.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

        import re as _re
        if not (_re.search(r'[a-zA-Zа-яА-Я]', password) and _re.search(r'[0-9]', password)):
            flash('Паролата трябва да съдържа букви И цифри.', 'error')
            return render_template('auth/register.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

        # Basic email format validation
        import re as _re
        if not _re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
            flash('Невалиден имейл адрес.', 'error')
            return render_template('auth/register.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

        if User.query.filter_by(email=email).first():
            flash('Имейлът вече е регистриран. Влез в профила си.', 'error')
            return render_template('auth/register.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

        # Create user
        name = request.form.get('name', '').strip() or email.split('@')[0]
        user = User(
            name=name,
            email=email,
            password=generate_password_hash(password),
            is_active=True,
            email_verified=False
        )
        db.session.add(user)

        # Apply promo code if provided
        if promo:
            promo_obj = PromoCode.query.filter_by(code=promo, is_active=True, is_used=False).first()
            if promo_obj:
                promo_obj.is_used = True
                promo_obj.used_by = email
                promo_obj.used_at = datetime.utcnow()
                promo_obj.is_active = False
                user.is_active = True
                db.session.commit()
                session['user_id'] = user.id
                # Известяване на admin
                try:
                    admin = User.query.filter_by(is_admin=True).first()
                    if admin and getattr(admin, 'notif_subscription', True) and BREVO_API_KEY:
                        send_email(admin.email, '🚢 Нов абонамент!',
                            f'Потребител {email} активира промокод {promo_obj.code}.')
                except:
                    pass
                flash('Акаунтът е създаден и промокодът е активиран!', 'success')
                return redirect(url_for('dashboard.user_dashboard'))

        # Generate verification token
        import secrets
        token = secrets.token_urlsafe(32)
        user.verification_token = token
        db.session.commit()
        
        # Generate OTP
        import random
        otp = str(random.randint(100000, 999999))
        user.otp_code = otp
        user.otp_expires = datetime.utcnow() + __import__('datetime').timedelta(minutes=5)
        db.session.commit()
        
        # Send OTP email
        if BREVO_API_KEY:
            send_otp_async(email, otp)
            session['pending_verify_email'] = email
            return redirect(url_for('auth.verify_otp'))
        else:
            user.email_verified = True
            db.session.commit()
            session['user_id'] = user.id
            flash('Добре дошъл!', 'success')
            session['user_id'] = user.id
            flash('Добре дошъл! Акаунтът ти е създаден.', 'success')
        return redirect(url_for('dashboard.user_dashboard'))

    return render_template('auth/register.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)



@auth.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.index'))

# ============================================================
#  USER ROUTES
# ============================================================


@auth.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    email = session.get('pending_verify_email')
    if not email:
        return redirect(url_for('auth.index'))
    
    if request.method == 'POST':
        otp = request.form.get('otp', '').strip()
        user = User.query.filter_by(email=email).first()
        
        if not user:
            flash('Грешка. Опитай отново.', 'error')
            return render_template('auth/verify_otp.html')
        
        if user.otp_expires and datetime.utcnow() > user.otp_expires:
            flash('Кодът е изтекъл. Регистрирай се отново.', 'error')
            return render_template('auth/verify_otp.html', expired=True)
        
        if user.otp_code != otp:
            flash('Грешен код. Опитай отново.', 'error')
            return render_template('auth/verify_otp.html')
        
        # Verify user
        user.email_verified = True
        user.otp_code = None
        user.otp_expires = None
        db.session.commit()
        
        session.pop('pending_verify_email', None)
        session['user_id'] = user.id
        session['user_name'] = user.name
        session['is_admin'] = user.is_admin
        session['just_logged_in'] = True
        flash('Акаунтът е активиран! Добре дошъл!', 'success')
        return redirect(url_for('admin.admin_dashboard') if user.is_admin else url_for('dashboard.user_dashboard'))
    
    return render_template('auth/verify_otp.html', email=email)


@auth.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = request.form.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False, 'message': 'Имейлът не е регистриран.'})
    
    import random
    otp = str(random.randint(100000, 999999))
    user.verification_token = None
    user.otp_code = otp
    from datetime import timedelta as _td2
    user.otp_expires = datetime.utcnow() + _td2(minutes=5)
    db.session.commit()
    
    if BREVO_API_KEY:
        send_otp_async(email, otp)
    
    return jsonify({'success': True})


@auth.route('/reset-password', methods=['GET', 'POST'])
def reset_password_otp():
    email = session.get('forgot_email')
    
    if request.method == 'POST':
        # Step 1: email submitted - send OTP
        if 'email' in request.form and 'otp' not in request.form:
            email = request.form.get('email', '').strip().lower()
            user = User.query.filter_by(email=email).first()
            if not user:
                return jsonify({'success': False, 'message': 'Имейлът не е регистриран.'})
            import random
            from datetime import timedelta as _td3
            otp = str(random.randint(100000, 999999))
            user.otp_code = otp
            user.otp_expires = datetime.utcnow() + _td3(minutes=5)
            db.session.commit()
            if BREVO_API_KEY:
                send_otp_async(email, otp)
            session['forgot_email'] = email
            return jsonify({'success': True})
        
        # Step 2: OTP submitted
        if 'otp' in request.form and 'password' not in request.form:
            otp = request.form.get('otp', '').strip()
            user = User.query.filter_by(email=email).first()
            if not user or user.otp_code != otp:
                return jsonify({'success': False, 'message': 'Грешен код.'})
            if user.otp_expires and datetime.utcnow() > user.otp_expires:
                return jsonify({'success': False, 'message': 'Кодът е изтекъл.'})
            session['forgot_otp_verified'] = True
            return jsonify({'success': True})
        
        # Step 3: new password submitted
        if 'password' in request.form:
            if not session.get('forgot_otp_verified'):
                return jsonify({'success': False, 'message': 'Невалидна сесия.'})
            password = request.form.get('password', '')
            confirm = request.form.get('confirm_password', '')
            if password != confirm:
                return jsonify({'success': False, 'message': 'Паролите не съвпадат.'})
            if len(password) < 6:
                return jsonify({'success': False, 'message': 'Паролата е прекалено кратка.'})
            user = User.query.filter_by(email=email).first()
            if not user:
                return jsonify({'success': False, 'message': 'Грешка. Опитай отново.'})
            user.password = generate_password_hash(password)
            user.otp_code = None
            user.otp_expires = None
            db.session.commit()
            session.pop('forgot_email', None)
            session.pop('forgot_otp_verified', None)
            return jsonify({'success': True, 'redirect': '/?login=1'})
    
    return render_template('auth/reset.html')




@auth.route('/resend-otp', methods=['POST'])
def resend_otp():
    email = session.get('pending_verify_email')
    if not email:
        return jsonify({'success': False, 'message': 'Сесията е изтекла.'})
    
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False})
    
    import random
    otp = str(random.randint(100000, 999999))
    user.otp_code = otp
    user.otp_expires = datetime.utcnow() + __import__('datetime').timedelta(minutes=5)
    db.session.commit()
    
    send_otp_async(email, otp)
    return jsonify({'success': True})

@auth.route('/verify-pending')
def verify_pending():
    return render_template('auth/verify_pending.html')

@auth.route('/verify-email/<token>')
def verify_email(token):
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        flash('Невалиден или изтекъл верификационен линк.', 'error')
        return redirect(url_for('auth.index'))
    user.email_verified = True
    user.verification_token = None
    db.session.commit()
    session['user_id'] = user.id
    flash('Имейлът е потвърден! Добре дошъл!', 'success')
    return redirect(url_for('admin.admin_dashboard') if user.is_admin else url_for('dashboard.user_dashboard'))

@auth.route('/ping')
def ping():
    return 'ok', 200


def record_monthly_snapshot():
    """Записва snapshot за текущия месец"""
    now = datetime.utcnow()
    year, month = now.year, now.month
    existing = MonthlySnapshot.query.filter_by(year=year, month=month).first()
    if existing:
        snap = existing
    else:
        snap = MonthlySnapshot(year=year, month=month)
        db.session.add(snap)
    
    snap.total_users  = User.query.filter_by(is_admin=False).count()
    snap.active_users = User.query.filter_by(is_admin=False, is_active=True).count()
    snap.passive_users = snap.total_users - snap.active_users
    snap.demo_users   = User.query.filter_by(is_admin=False, is_active=False).count()
    db.session.commit()
    return snap
