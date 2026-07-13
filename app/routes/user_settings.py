# app/routes/user_settings.py
# User settings routes — извлечени от app/routes/dashboard.py.
# Правило 4 + 5 (NEXT_SESSION_PROMPT.md).

from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.models.user import User
from app.models.result import TestResult
from app.utils.decorators import login_required

user_settings = Blueprint('user_settings', __name__)


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


@user_settings.route('/api/test-preferences', methods=['GET', 'POST'])
@login_required
def api_test_preferences():
    """
    Настройки за четене на тестовете (font size/theme/family) - от
    менюто с 3-те чертички в хедъра на всеки тест/симулатор. Отделни
    слайдери (0-10) и шрифтове за ВЪПРОСА и за ОТГОВОРИТЕ поотделно.
    Записват се веднъж в акаунта, важат за ВСИЧКИ функции за решаване на
    тестове.
    """
    user = User.query.get(session['user_id'])
    if request.method == 'GET':
        return jsonify({
            'q_font_size': user.pref_q_font_size if user.pref_q_font_size is not None else 5,
            'a_font_size': user.pref_a_font_size if user.pref_a_font_size is not None else 5,
            'highlight_intensity': user.pref_highlight_intensity if user.pref_highlight_intensity is not None else 5,
            'theme': user.pref_theme or 'dark',
            'q_font_family': user.pref_q_font_family or 'default',
            'a_font_family': user.pref_a_font_family or 'default',
            'q_bold': user.pref_q_bold if user.pref_q_bold is not None else True,
            'a_bold': user.pref_a_bold if user.pref_a_bold is not None else False,
        })

    data = request.get_json(silent=True) or {}

    # Бутонът 'Reset to Default' в менюто - връща ВСИЧКИ настройки на
    # стойностите по подразбиране. Стойностите по подразбиране могат да
    # се сменят по-късно от потребителя (засега: средата на всеки слайдер,
    # тъмна тема, стандартен шрифт, удебелен въпрос/неудебелени отговори).
    if data.get('reset'):
        user.pref_q_font_size = 5
        user.pref_a_font_size = 5
        user.pref_highlight_intensity = 5
        user.pref_theme = 'dark'
        user.pref_q_font_family = 'default'
        user.pref_a_font_family = 'default'
        user.pref_q_bold = True
        user.pref_a_bold = False
        db.session.commit()
        return jsonify({'success': True, 'reset': True})

    if 'q_font_size' in data:
        try:
            v = int(data['q_font_size'])
            if 0 <= v <= 10:
                user.pref_q_font_size = v
        except (TypeError, ValueError):
            pass
    if 'a_font_size' in data:
        try:
            v = int(data['a_font_size'])
            if 0 <= v <= 10:
                user.pref_a_font_size = v
        except (TypeError, ValueError):
            pass
    if 'highlight_intensity' in data:
        try:
            v = int(data['highlight_intensity'])
            if 0 <= v <= 10:
                user.pref_highlight_intensity = v
        except (TypeError, ValueError):
            pass
    if 'theme' in data and data['theme'] in ('dark', 'light', 'sepia', 'ink'):
        user.pref_theme = data['theme']
    if 'q_font_family' in data and data['q_font_family'] in ('default', 'georgia', 'times', 'verdana', 'arial', 'roboto', 'opensans', 'montserrat', 'poppins', 'lato', 'nunito', 'worksans', 'raleway', 'sourcesans', 'notosans', 'merriweather', 'playfair', 'ptserif', 'oswald', 'rubik', 'ubuntu'):
        user.pref_q_font_family = data['q_font_family']
    if 'a_font_family' in data and data['a_font_family'] in ('default', 'georgia', 'times', 'verdana', 'arial', 'roboto', 'opensans', 'montserrat', 'poppins', 'lato', 'nunito', 'worksans', 'raleway', 'sourcesans', 'notosans', 'merriweather', 'playfair', 'ptserif', 'oswald', 'rubik', 'ubuntu'):
        user.pref_a_font_family = data['a_font_family']
    if 'q_bold' in data:
        user.pref_q_bold = bool(data['q_bold'])
    if 'a_bold' in data:
        user.pref_a_bold = bool(data['a_bold'])
    db.session.commit()
    return jsonify({'success': True})

@user_settings.route('/api/random-ad')
def api_random_ad():
    from app.models.ad import Ad
    ad = Ad.query.filter_by(is_active=True).order_by(db.func.random()).first()
    if not ad:
        return jsonify({'ad': None})
    ad.impressions = (ad.impressions or 0) + 1
    db.session.commit()
    return jsonify({'ad': {
        'id': ad.id, 'title': ad.title, 'image_url': ad.image_url or '',
        'link_url': ad.link_url or '', 'body': ad.body or '',
    }})


@user_settings.route('/api/ad-click/<int:ad_id>', methods=['POST'])
def api_ad_click(ad_id):
    from app.models.ad import Ad
    ad = Ad.query.get(ad_id)
    if ad:
        ad.clicks = (ad.clicks or 0) + 1
        db.session.commit()
    return jsonify({'success': True})


@user_settings.route('/api/my-usage')
@login_required
def api_my_usage():
    from app.models.gold_grant import GoldGrant
    from app.models.promo_grant import PromoGrant
    from app.models.plan_grant import PlanGrant
    from app.models.promo import PromoCode
    import math
    user = User.query.get(session['user_id'])
    now = datetime.utcnow()
    cards = []

    def _build_gold_or_promo_card(g, grant_type):
        test_ids = g.test_id_list()
        titles = [t.title for t in Test.query.filter(Test.id.in_(test_ids)).all()] if test_ids else []
        # Реален брой решени — директно от TestResult, не от съхранено поле
        # (което никога не се актуализира надеждно) — вижте същата логика, ползвана
        # за самите карти на dashboard-а, за да няма разминаване между двете места.
        used_real = (TestResult.query
                     .filter(TestResult.user_id == user.id,
                             TestResult.test_id.in_(test_ids),
                             TestResult.taken_at >= g.activated_at)
                     .count()) if test_ids else 0
        total_seconds = max(1, (g.expires_at - g.activated_at).total_seconds())
        elapsed_seconds = max(0, (now - g.activated_at).total_seconds())
        from app.utils.grants import grant_plan_label
        _plan_label = grant_plan_label(g)
        return {
            'plan': _plan_label, 'test_names': titles,
            'quota': g.quota, 'tests_used': used_real,
            'tests_remaining': max(0, g.quota - used_real),
            'activated_at': g.activated_at.strftime('%d %b %Y, %H:%M') + ' (UTC)',
            'expires_at': g.expires_at.strftime('%d %b %Y, %H:%M') + ' (UTC)',
            'days_remaining': max(0, math.ceil((g.expires_at - now).total_seconds() / 86400)),
            'pct_remaining': max(0, min(100, int(100 - (elapsed_seconds / total_seconds * 100)))),
            'subscription_code': (g.promo_code or get_or_create_subscription_code(grant_type, g.id)),
            '_activated_raw': g.activated_at,
        }

    for g in GoldGrant.query.filter(GoldGrant.user_id == user.id, GoldGrant.expires_at > now).order_by(GoldGrant.activated_at.asc()).all():
        cards.append(_build_gold_or_promo_card(g, 'gold'))

    # PromoGrant - ОТДЕЛЕН от GoldGrant (по изрично искане - Promo и Gold
    # са различни продукти, различни таблици). Използва СЪЩАТА card-building
    # логика (_build_gold_or_promo_card) - структурата на картите е
    # идентична, само таблицата-източник е различна.
    for g in PromoGrant.query.filter(PromoGrant.user_id == user.id, PromoGrant.expires_at > now).order_by(PromoGrant.activated_at.asc()).all():
        cards.append(_build_gold_or_promo_card(g, 'promo'))

    for g in PlanGrant.query.filter(PlanGrant.user_id == user.id, PlanGrant.expires_at > now).order_by(PlanGrant.activated_at.asc()).all():
        title = None
        if g.library_test_id:
            t = Test.query.get(g.library_test_id)
            title = t.title if t else None
        used_real = (TestResult.query
                     .filter(TestResult.user_id == user.id,
                             TestResult.test_id == g.library_test_id,
                             TestResult.taken_at >= g.activated_at)
                     .count()) if g.library_test_id else 0
        total_seconds = max(1, (g.expires_at - g.activated_at).total_seconds())
        elapsed_seconds = max(0, (now - g.activated_at).total_seconds())
        cards.append({
            'plan': g.plan.capitalize(), 'test_names': [title] if title else [],
            'quota': g.quota, 'tests_used': used_real,
            'tests_remaining': max(0, g.quota - used_real),
            'activated_at': g.activated_at.strftime('%d %b %Y, %H:%M') + ' (UTC)',
            'expires_at': g.expires_at.strftime('%d %b %Y, %H:%M') + ' (UTC)',
            'days_remaining': max(0, math.ceil((g.expires_at - now).total_seconds() / 86400)),
            'pct_remaining': max(0, min(100, int(100 - (elapsed_seconds / total_seconds * 100)))),
            'subscription_code': get_or_create_subscription_code('plan', g.id),
            '_activated_raw': g.activated_at,
        })

    # Free план карта - активната (текуща) сесия от FreeSession, СЪЩАТА
    # структура като Gold/Basic/Plus по-горе, за да се вижда Free в
    # потребителския Usage таб (преди изобщо не се показваше нищо тук за
    # Free потребители - празен списък -> само "Upgrade" бутон, дори с
    # активно избран тест и оставащи дни/тестове).
    if user.library_refresh_if_expired():
        db.session.commit()
    if not user.has_active_plan() and user.library_test_id and user.library_window_active():
        FREE_QUOTA = 7
        free_test = Test.query.get(user.library_test_id)
        used_real = (TestResult.query
                     .filter(TestResult.user_id == user.id,
                             TestResult.test_id == user.library_test_id,
                             TestResult.taken_at >= (user.library_selected_at or now))
                     .count())
        expires_at = user.library_window_expires_at()
        total_seconds = max(1, (expires_at - user.library_selected_at).total_seconds())
        elapsed_seconds = max(0, (now - user.library_selected_at).total_seconds())
        cards.append({
            'plan': 'Free', 'test_names': [free_test.title] if free_test else [],
            'quota': FREE_QUOTA, 'tests_used': used_real,
            'tests_remaining': max(0, FREE_QUOTA - used_real),
            'activated_at': user.library_selected_at.strftime('%d %b %Y, %H:%M') + ' (UTC)',
            'expires_at': expires_at.strftime('%d %b %Y, %H:%M') + ' (UTC)',
            'days_remaining': max(0, math.ceil((expires_at - now).total_seconds() / 86400)),
            'pct_remaining': max(0, min(100, int(100 - (elapsed_seconds / total_seconds * 100)))),
            'subscription_code': f"BG{free_code(user.id)}",
            '_activated_raw': user.library_selected_at,
        })

    # Сортираме ЦЯЛОСТНИЯ списък (Gold + Basic/Plus + Free смесени) по
    # реалната дата на активиране - най-старият план най-отгоре,
    # най-скоро активираният най-отдолу. По-горе всеки тип се append-ва
    # отделно, затова е нужен този финален merge-sort, за да е вярно и
    # при потребители с активни грантове от няколко типа едновременно.
    cards.sort(key=lambda c: c['_activated_raw'])
    for c in cards:
        del c['_activated_raw']

    return jsonify({'cards': cards})


@user_settings.route('/api/my-billing')
@login_required
def api_my_billing():
    from app.models.payment import Payment
    from app.models.promo import PromoCode
    from app.models.plan_grant import PlanGrant
    from app.models.gold_grant import GoldGrant
    user = User.query.get(session['user_id'])
    payments = Payment.query.filter_by(user_id=user.id).order_by(Payment.paid_at.desc()).all()

    result = []
    for p in payments:
        entry = {
            'id': p.id,
            'plan': p.plan,
            'amount': p.amount,
            'paid_at': p.paid_at.strftime('%d.%m.%Y %H:%M'),
            'promo_email_sent': bool(p.promo_email_sent),
            'codes': [],
            'loaded_test': None,
            'active_from': None,
            'active_until': None,
        }
        if p.plan == 'gold' and p.stripe_payment_intent:
            codes = PromoCode.query.filter_by(
                stripe_payment_intent=p.stripe_payment_intent
            ).order_by(PromoCode.id.asc()).all()
            code_entries = []
            for c in codes:
                code_entry = {
                    'code': c.code,
                    'is_used': bool(c.is_used),
                    'used_by': c.used_by or '',
                    'shared_to': c.shared_to or '',
                    'active_from': None,
                    'active_until': None,
                    'activate_by': None,
                }
                if c.is_used:
                    g = GoldGrant.query.filter_by(promo_code=c.code).first()
                    if g:
                        if g.activated_at:
                            code_entry['active_from'] = g.activated_at.strftime('%d.%m.%Y %H:%M') + ' (UTC)'
                        if g.expires_at:
                            code_entry['active_until'] = g.expires_at.strftime('%d.%m.%Y %H:%M') + ' (UTC)'
                elif c.expires_at:
                    code_entry['activate_by'] = c.expires_at.strftime('%d.%m.%Y %H:%M')
                code_entries.append(code_entry)
            entry['codes'] = code_entries
        elif p.plan in ('basic', 'plus'):
            grant = PlanGrant.query.filter_by(payment_id=p.id).first()
            if grant:
                if grant.library_test_id:
                    t = Test.query.get(grant.library_test_id)
                    entry['loaded_test'] = t.title if t else None
                if grant.activated_at:
                    entry['active_from'] = grant.activated_at.strftime('%d.%m.%Y %H:%M') + ' (UTC)'
                if grant.expires_at:
                    entry['active_until'] = grant.expires_at.strftime('%d.%m.%Y %H:%M') + ' (UTC)'
        result.append(entry)

    # Активирани промо кодове, КОИТО ТОЗИ потребител Е ИЗПОЛЗВАЛ, но НЕ Е
    # ПЛАТИЛ лично (получил ги е от друг) - отделна карта в Billing, за да
    # се вижда И реалният платец (само имейл), не само собствения достъп
    # (който вече се вижда в Usage таба).
    activated_codes = []
    my_gold_grants = GoldGrant.query.filter_by(user_id=user.id).order_by(GoldGrant.activated_at.desc()).all()
    for g in my_gold_grants:
        if not g.promo_code:
            continue
        promo = PromoCode.query.filter_by(code=g.promo_code).first()
        if not promo or not promo.created_by_user_id:
            continue
        if promo.created_by_user_id == user.id:
            continue  # той самият е купувачът - вече се вижда в 'payments' по-горе
        payer = User.query.get(promo.created_by_user_id)
        activated_codes.append({
            'plan': 'gold',
            'code': g.promo_code,
            'paid_by_email': payer.email if payer else 'Unknown',
            'active_from': g.activated_at.strftime('%d.%m.%Y %H:%M') + ' (UTC)' if g.activated_at else None,
            'active_until': g.expires_at.strftime('%d.%m.%Y %H:%M') + ' (UTC)' if g.expires_at else None,
        })

    return jsonify({'payments': result, 'activated_codes': activated_codes})


