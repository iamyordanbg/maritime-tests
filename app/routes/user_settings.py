"""
app/routes/user_settings.py
============================
User Settings (profile/password/notifications/delete account) — extraction-нат
от dashboard.py (Group A audit, File Limits).
"""
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.models.user import User
from app.models.result import TestResult
from app.utils.decorators import login_required

user_settings = Blueprint("user_settings", __name__)


@user_settings.route('/settings')
@login_required
def settings():
    user = User.query.get(session['user_id'])
    if user and user.is_admin:
        return redirect(url_for('admin.admin_dashboard'))

    from app.models.payment import Payment
    from app.models.promo import PromoCode
    from app.utils.codes import get_or_create_subscription_code
    payments = Payment.query.filter_by(user_id=user.id).order_by(Payment.paid_at.desc()).all()

    gold_codes_by_payment = {}
    for p in payments:
        if p.plan == 'gold' and p.stripe_payment_intent:
            gold_codes_by_payment[p.id] = PromoCode.query.filter_by(
                stripe_payment_intent=p.stripe_payment_intent
            ).order_by(PromoCode.id.asc()).all()

    plan_grant_codes = {g.id: get_or_create_subscription_code('plan', g.id) for g in user.active_plan_grants()}
    gold_grant_codes = {g.id: (g.promo_code or get_or_create_subscription_code('gold', g.id)) for g in user.active_gold_grants()}

    return render_template('user/settings.html', user=user, payments=payments,
                            gold_codes_by_payment=gold_codes_by_payment,
                            plan_grant_codes=plan_grant_codes,
                            gold_grant_codes=gold_grant_codes)


@user_settings.route('/settings/profile', methods=['POST'])
@login_required
def settings_profile():
    try:
        user = User.query.get(session['user_id'])
        user.nick = request.form.get('nick', '').strip()
        user.firstname = request.form.get('firstname', '').strip()
        user.lastname = request.form.get('lastname', '').strip()
        db.session.commit()
        return jsonify({'success': True, 'message': '✓ Профилът е запазен'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@user_settings.route('/settings/check-password', methods=['POST'])
@login_required
def check_password():
    user = User.query.get(session['user_id'])
    cur = request.form.get('current_password', '')
    valid = check_password_hash(user.password, cur)
    return jsonify({'valid': valid})


@user_settings.route('/settings/notifications', methods=['POST'])
@login_required
def settings_notifications():
    user = User.query.get(session['user_id'])
    data = request.get_json()
    user.notif_subscription = data.get('notif_subscription', True)
    db.session.commit()
    return jsonify({'success': True})


@user_settings.route('/logout-all', methods=['POST'])
@login_required
def logout_all():
    session.clear()
    return jsonify({'success': True})


@user_settings.route('/settings/delete-account', methods=['POST'])
@login_required
def delete_account():
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'success': False, 'message': 'Акаунтът не е намерен.'})
    try:
        from app.models.payment import Payment
        Payment.query.filter_by(user_id=user.id).delete()
        TestResult.query.filter_by(user_id=user.id).delete()
        db.session.delete(user)
        db.session.commit()
        session.clear()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@user_settings.route('/settings/password', methods=['POST'])
@login_required
def settings_password():
    user = User.query.get(session['user_id'])
    cur = request.form.get('current_password', '')
    new_pass = request.form.get('new_password', '')
    if not check_password_hash(user.password, cur):
        return jsonify({'success': False, 'message': 'Грешна текуща парола'})
    if len(new_pass) < 6:
        return jsonify({'success': False, 'message': 'Паролата е прекалено кратка'})
    user.password = generate_password_hash(new_pass)
    db.session.commit()
    return jsonify({'success': True, 'message': '✓ Паролата е сменена'})
