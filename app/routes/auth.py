from urllib.parse import urlencode
import requests as http_requests
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.models.user import User
from app.models.test import Test
from app.models.promo import PromoCode
from app.services.email import send_otp_email, send_otp_async, send_verification_email, OTP_VALID_MINUTES
from app.services.plans import PLANS
import os
RECAPTCHA_SITE_KEY = os.environ.get("RECAPTCHA_SITE_KEY", "")
RECAPTCHA_SECRET_KEY = os.environ.get("RECAPTCHA_SECRET_KEY", "")
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo' 

def get_google_redirect_uri():
    return os.environ.get('BASE_URL', 'https://web-production-ca6b6.up.railway.app') + '/auth/google/callback'

import os, random, string
from datetime import datetime

auth = Blueprint("auth", __name__)


def _chosen_plan(value):
    """Избран на landing страницата план -> валидно име от PLANS, иначе None."""
    value = (value or '').strip()
    return value if value in PLANS else None


def post_login_redirect_url(user):
    from flask import session as _session
    if user.is_admin:
        return url_for('admin.admin_dashboard')
    # Ако потребителят е дошъл за активиране на Gold код
    pending_code = _session.pop('pending_activation_code', None)
    if pending_code:
        return url_for('activate.activate_start', code=pending_code)
    # Ако потребителят е искал да купи план преди регистрация
    pending_plan = _session.pop('pending_plan', None)
    if pending_plan:
        return url_for('billing.checkout', plan_name=pending_plan)
    user.library_refresh_if_expired()
    # Once per login: a user who still has to choose a test (no subscription, or a plan without a chosen
    # test) lands in the Library. It is optional - they can leave it and use the dashboard; the dashboard
    # itself never forces them back. Next login asks again.
    from app.services.dashboard_stats import needs_test_selection
    if needs_test_selection(user):
        return url_for('dashboard.library')
    return url_for('dashboard.user_dashboard')

@auth.route('/auth/google')
def google_login():
    # Избран план от plans modal: пазим го в session, post_login_redirect_url()
    # го изважда след callback-а и праща потребителя директно към плащане.
    plan = _chosen_plan(request.args.get('plan'))
    if plan:
        session['pending_plan'] = plan
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
        flash('Google sign-in was declined.', 'error')
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
        flash('Google authentication error.', 'error')
        return redirect(url_for('auth.login'))
    
    access_token = token_resp.json().get('access_token')
    
    # Get user info
    user_info = http_requests.get(
        GOOGLE_USERINFO_URL,
        headers={'Authorization': f'Bearer {access_token}'}
    ).json()
    
    google_email = user_info.get('email', '').lower().strip()
    google_name = user_info.get('name', '')
    google_firstname = user_info.get('given_name', '')
    google_lastname = user_info.get('family_name', '')
    google_picture = user_info.get('picture', '')
    # Ако няма given/family - разделяме name
    if not google_firstname and google_name:
        parts = google_name.split(' ', 1)
        google_firstname = parts[0]
        google_lastname = parts[1] if len(parts) > 1 else ''
    google_id = user_info.get('sub', '')
    
    if not google_email:
        flash('Could not get an email address from Google.', 'error')
        return redirect(url_for('auth.login'))
    
    # Find or create user
    user = User.query.filter_by(email=google_email).first()
    
    if user:
        # Existing user - log in
        session['user_id'] = user.id
        session['is_admin'] = user.is_admin
        if google_picture:
            user.google_picture_url = google_picture
        if google_id and not user.google_id:
            user.google_id = google_id
        redirect_url = post_login_redirect_url(user)
        db.session.commit()
        # Return JSON for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'redirect': redirect_url})
        return redirect(redirect_url)
    else:
        # New user - create account
        new_user = User(
            name=google_name or google_email.split('@')[0],
            firstname=google_firstname,
            lastname=google_lastname,
            email=google_email,
            google_id=google_id,
            google_picture_url=google_picture,
            password=generate_password_hash(google_id + GOOGLE_CLIENT_SECRET[:8]),
            is_admin=False,
            is_active=False
        )
        db.session.add(new_user)
        db.session.commit()
        session['user_id'] = new_user.id
        session['is_admin'] = False
        flash(f'Welcome, {new_user.name}! Your account was created with Google.', 'success')
        return redirect(post_login_redirect_url(new_user))




@auth.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            redirect_url = post_login_redirect_url(user)
            db.session.commit()
            return redirect(redirect_url)
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
                flash('Please confirm your email before logging in.', 'error')
                return render_template('auth/login.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)
            session['user_id'] = user.id
            session['user_name'] = (user.firstname or '') + ' ' + (user.lastname or '')
            session['is_admin'] = user.is_admin
            # Ако идва от plans modal с pending_plan — запазваме за redirect
            pending_plan = _chosen_plan(request.form.get('pending_plan'))
            if pending_plan:
                session['pending_plan'] = pending_plan
            redirect_url = post_login_redirect_url(user)
            db.session.commit()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'redirect': redirect_url})
            return redirect(redirect_url)
        flash('Wrong email or password', 'error')
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
            flash('Email and password are required.', 'error')
            return render_template('auth/register.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)



        if len(password) < 6:
            flash('The password must be at least 6 characters.', 'error')
            return render_template('auth/register.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

        import re as _re
        if not (_re.search(r'[a-zA-Zа-яА-Я]', password) and _re.search(r'[0-9]', password)):
            flash('The password must contain both letters and digits.', 'error')
            return render_template('auth/register.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

        # Basic email format validation
        import re as _re
        if not _re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
            flash('Invalid email address.', 'error')
            return render_template('auth/register.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

        if User.query.filter_by(email=email).first():
            flash('This email is already registered. Log in to your account.', 'error')
            return render_template('auth/register.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

        # НЕ създаваме акаунт преди верификация — пазим в session
        name = request.form.get('name', '').strip() or email.split('@')[0]

        # Проверяваме промокода предварително
        promo_valid = False
        if promo:
            promo_obj = PromoCode.query.filter_by(code=promo, is_active=True, is_used=False).first()
            if promo_obj:
                promo_valid = True

        if BREVO_API_KEY:
            # Пазим данните в session, акаунтът се създава след OTP
            import random
            otp = str(random.randint(100000, 999999))
            session['pending_verify_email'] = email
            session['pending_verify_name'] = name
            session['pending_verify_password'] = generate_password_hash(password)
            session['pending_verify_otp'] = otp
            session['pending_verify_otp_expires'] = (datetime.utcnow() + __import__('datetime').timedelta(minutes=OTP_VALID_MINUTES)).isoformat()
            session['pending_verify_promo'] = promo if promo_valid else ''
            # Запазваме избрания план ако е дошъл от plans modal
            pending_plan = _chosen_plan(request.form.get('pending_plan'))
            if pending_plan:
                session['pending_plan'] = pending_plan
            send_otp_async(email, otp)
            return redirect(url_for('auth.verify_otp'))
        else:
            # Без имейл верификация — създаваме директно
            user = User(
                name=name, email=email,
                password=generate_password_hash(password),
                is_active=promo_valid, email_verified=True
            )
            db.session.add(user)
            if promo_valid:
                promo_obj = PromoCode.query.filter_by(code=promo, is_active=True, is_used=False).first()
                if promo_obj:
                    promo_obj.is_used = True; promo_obj.used_by = email
                    promo_obj.used_at = datetime.utcnow(); promo_obj.is_active = False
            db.session.commit()
            session['user_id'] = user.id
            session['is_admin'] = user.is_admin
            flash('Welcome!', 'success')
            return redirect(post_login_redirect_url(user))

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

        # Проверяваме дали OTP идва от регистрация (в session) или от съществуващ user
        pending_otp = session.get('pending_verify_otp')
        pending_expires = session.get('pending_verify_otp_expires')

        if pending_otp:
            # Регистрация — данните са в session
            from datetime import datetime as _dt
            if pending_expires and _dt.utcnow() > _dt.fromisoformat(pending_expires):
                flash('The code has expired. Please register again.', 'error')
                return render_template('auth/verify_otp.html', expired=True)

            if pending_otp != otp:
                flash('Wrong code. Try again.', 'error')
                return render_template('auth/verify_otp.html', email=email)

            # Създаваме акаунта СЕГА след успешна верификация
            name = session.get('pending_verify_name', email.split('@')[0])
            password = session.get('pending_verify_password', '')
            promo_code = session.get('pending_verify_promo', '')

            # Потребителят вече съществува — обновяваме само паролата (re-registration или double submit)
            existing = User.query.filter_by(email=email).first()
            if existing:
                from sqlalchemy import text as _text
                db.session.execute(_text(
                    "UPDATE \"user\" SET password=:pw, name=:name, email_verified=true WHERE id=:uid"
                ), {'pw': password, 'name': name, 'uid': existing.id})
                db.session.commit()
                for k in ['pending_verify_email','pending_verify_name','pending_verify_password',
                          'pending_verify_otp','pending_verify_otp_expires','pending_verify_promo']:
                    session.pop(k, None)
                db.session.refresh(existing)
                session['user_id'] = existing.id
                session['is_admin'] = existing.is_admin
                session['just_logged_in'] = True
                flash('Your account is activated! Welcome!', 'success')
                # Същият redirect като при нов акаунт/login: избран план -> директно плащане.
                redirect_url = post_login_redirect_url(existing)
                db.session.commit()
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
                    return jsonify({'success': True, 'redirect': redirect_url})
                return redirect(redirect_url)

            user = User(
                name=name, email=email,
                password=password,
                is_active=False, email_verified=True
            )
            try:
                db.session.add(user)
                db.session.flush()
            except Exception:
                db.session.rollback()
                existing = User.query.filter_by(email=email).first()
                if existing:
                    for k in ['pending_verify_email','pending_verify_name','pending_verify_password',
                              'pending_verify_otp','pending_verify_otp_expires','pending_verify_promo']:
                        session.pop(k, None)
                    session['user_id'] = existing.id
                    session['is_admin'] = existing.is_admin
                    return redirect(post_login_redirect_url(existing))
                raise

            if promo_code:
                promo_obj = PromoCode.query.filter_by(code=promo_code, is_active=True, is_used=False).first()
                if promo_obj:
                    promo_obj.is_used = True; promo_obj.used_by = email
                    promo_obj.used_at = datetime.utcnow(); promo_obj.is_active = False
                    user.is_active = True

            db.session.commit()

            # Чистим session
            for k in ['pending_verify_email','pending_verify_name','pending_verify_password',
                      'pending_verify_otp','pending_verify_otp_expires','pending_verify_promo']:
                session.pop(k, None)

            session['user_id'] = user.id
            session['is_admin'] = user.is_admin
            session['just_logged_in'] = True
            flash('Your account is activated! Welcome!', 'success')
            redirect_url = post_login_redirect_url(user)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
                return jsonify({'success': True, 'redirect': redirect_url})
            return redirect(redirect_url)

        else:
            # Съществуващ user (login OTP или forgot password)
            user = User.query.filter_by(email=email).first()
            if not user:
                flash('Something went wrong. Try again.', 'error')
                return render_template('auth/verify_otp.html')

            if user.otp_expires and datetime.utcnow() > user.otp_expires:
                flash('The code has expired. Try again.', 'error')
                return render_template('auth/verify_otp.html', expired=True)

            if user.otp_code != otp:
                flash('Wrong code. Try again.', 'error')
                return render_template('auth/verify_otp.html')

            user.email_verified = True
            user.otp_code = None
            user.otp_expires = None
            db.session.commit()

            session.pop('pending_verify_email', None)
            session['user_id'] = user.id
            session['is_admin'] = user.is_admin
            session['just_logged_in'] = True
            flash('Your account is activated! Welcome!', 'success')
            redirect_url = post_login_redirect_url(user)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
                return jsonify({'success': True, 'redirect': redirect_url})
            return redirect(redirect_url)

    return render_template('auth/verify_otp.html', email=email)


@auth.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = request.form.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False, 'message': 'This email is not registered.'})
    
    import random
    otp = str(random.randint(100000, 999999))
    user.verification_token = None
    user.otp_code = otp
    from datetime import timedelta as _td2
    user.otp_expires = datetime.utcnow() + _td2(minutes=OTP_VALID_MINUTES)
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
                return jsonify({'success': False, 'message': 'This email is not registered.'})
            import random
            from datetime import timedelta as _td3
            otp = str(random.randint(100000, 999999))
            user.otp_code = otp
            user.otp_expires = datetime.utcnow() + _td3(minutes=OTP_VALID_MINUTES)
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
                return jsonify({'success': False, 'message': 'Wrong code.'})
            if user.otp_expires and datetime.utcnow() > user.otp_expires:
                return jsonify({'success': False, 'message': 'The code has expired.'})
            session['forgot_otp_verified'] = True
            return jsonify({'success': True})
        
        # Step 3: new password submitted
        if 'password' in request.form:
            if not session.get('forgot_otp_verified'):
                return jsonify({'success': False, 'message': 'Invalid session.'})
            password = request.form.get('password', '')
            confirm = request.form.get('confirm_password', '')
            if password != confirm:
                return jsonify({'success': False, 'message': 'The passwords do not match.'})
            if len(password) < 6:
                return jsonify({'success': False, 'message': 'The password is too short.'})
            user = User.query.filter_by(email=email).first()
            if not user:
                return jsonify({'success': False, 'message': 'Something went wrong. Try again.'})
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
        return jsonify({'success': False, 'message': 'The session has expired.'})

    import random
    otp = str(random.randint(100000, 999999))

    # Register flow: потребителят все още не съществува в базата - OTP-то
    # живее само в session (виж register(), редове ~234-240). resend тук
    # трябва да презапише СЪЩИТЕ session ключове, не user.otp_code (user
    # обектът не съществува все още, filter_by(email=email).first() връща
    # None и старата логика тихо се проваляше с 'Something went wrong. Try again.').
    if session.get('pending_verify_otp'):
        session['pending_verify_otp'] = otp
        session['pending_verify_otp_expires'] = (datetime.utcnow() + __import__('datetime').timedelta(minutes=OTP_VALID_MINUTES)).isoformat()
        send_otp_async(email, otp)
        return jsonify({'success': True})

    # Existing-user flow (login OTP / forgot password): OTP-то е в user.otp_code
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False})

    user.otp_code = otp
    user.otp_expires = datetime.utcnow() + __import__('datetime').timedelta(minutes=OTP_VALID_MINUTES)
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
        flash('Invalid or expired verification link.', 'error')
        return redirect(url_for('auth.index'))
    user.email_verified = True
    user.verification_token = None
    db.session.commit()
    session['user_id'] = user.id
    session['is_admin'] = user.is_admin
    flash('Your email is confirmed! Welcome!', 'success')
    redirect_url = post_login_redirect_url(user)
    db.session.commit()
    return redirect(redirect_url)

@auth.route('/ping')
def ping():
    return 'ok', 200

@auth.route('/demo')
def demo():
    import json
    from pathlib import Path
    counter_file = Path(__file__).parent.parent / 'static' / 'demo_counter.json'
    try:
        data = json.loads(counter_file.read_text()) if counter_file.exists() else {'count': 0}
        data['count'] = data.get('count', 0) + 1
        counter_file.write_text(json.dumps(data))
    except Exception:
        pass

    demo_tests_raw = Test.query.order_by(Test.category, Test.level).all()
    level_map = {
        'Operational Level': 'operational', 'operational level': 'operational',
        'operational': 'operational', 'Оперативно ниво': 'operational',
        'Management Level': 'management', 'management level': 'management',
        'management': 'management', 'Мениджърско ниво': 'management',
        'ETO': 'eto', 'eto': 'eto',
        'Master Level': 'master', 'master level': 'master',
        'master': 'master', 'Капитанско ниво': 'master',
        'Support Level': 'support', 'support level': 'support',
        'support': 'support',
    }
    tests_data = []
    for t in demo_tests_raw:
        level_key = level_map.get(t.level) or level_map.get((t.level or '').strip()) or 'operational'
        cat = t.category.lower().strip()
        if cat not in ('deck', 'engine'):
            cat = 'deck' if 'deck' in cat or 'палуб' in cat.lower() else 'engine'
        tests_data.append({
            'id': t.id, 'title': t.title, 'category': cat,
            'level_key': level_key, 'question_count': t.question_count,
            'is_demo': t.is_demo
        })
    return render_template('demo.html', demo_tests=tests_data, recaptcha_site_key=RECAPTCHA_SITE_KEY)

@auth.route('/terms')
def terms():
    return render_template('terms.html')

@auth.route('/privacy')
def privacy():
    return render_template('privacy.html')

@auth.route('/cookies')
def cookies():
    return render_template('cookies.html')

@auth.route('/about')
def about():
    from flask import render_template_string
    return render_template('about.html')

@auth.route('/contact')
def contact():
    return render_template('contact.html')
