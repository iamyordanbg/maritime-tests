"""
app/routes/activate.py
=======================
/activate — активиране на Gold промокод.

Стъпки:
  1. GET  /activate?code=GOLD-XXXX        — валидира кода, пита за login ако трябва
  2. POST /activate/department            — избор на департмент (deck/engine)
  3. POST /activate/level                 — избор на level (Operational/Management)
  4. POST /activate/confirm               — потвърждение на 2-та теста → активира плана
"""

import json
from io import BytesIO
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response, abort, current_app

from app.extensions import db
from app.models.user import User
from app.models.test import Test
from app.models.promo import PromoCode

activate_bp = Blueprint('activate', __name__)

PROMO_SESSION_KEY = 'activate_flow'


@activate_bp.route('/qr/<code>.png')
def qr_image(code):
    """
    Хоства QR кода като реален PNG URL (не base64/data URI) —
    Gmail и повечето имейл клиенти блокират вградени data: изображения по подразбиране.
    """
    code = (code or '').strip().upper()
    promo = PromoCode.query.filter_by(code=code).first()
    if not promo:
        abort(404)

    import os
    import qrcode
    base_url = os.environ.get("BASE_URL", "https://web-production-ca6b6.up.railway.app")
    activate_url = f"{base_url}/activate?code={code}"

    img = qrcode.make(activate_url, box_size=8, border=2)
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return Response(buf.getvalue(), mimetype='image/png',
                     headers={'Cache-Control': 'public, max-age=86400'})


def _get_valid_promo(code: str):
    if not code:
        return None
    promo = PromoCode.query.filter_by(code=code.strip().upper()).first()
    if not promo:
        return None
    if promo.is_used or not promo.is_active:
        return None
    if promo.expires_at and promo.expires_at < datetime.utcnow():
        return None
    return promo


@activate_bp.route('/activate')
def activate_start():
    code = (request.args.get('code') or '').strip().upper()
    promo = _get_valid_promo(code)

    if not code:
        return render_template('activate/enter_code.html')

    if not promo:
        flash('Невалиден, използван или изтекъл код.', 'error')
        return render_template('activate/enter_code.html')

    if 'user_id' not in session:
        # Запазваме кода и пращаме към login/register — после се връщаме тук
        session['pending_activation_code'] = code
        flash('Влез или се регистрирай, за да активираш кода.', 'warning')
        return redirect(url_for('auth.index') + '?login=1')

    session[PROMO_SESSION_KEY] = {'code': code}
    return redirect(url_for('activate.choose_department'))


@activate_bp.route('/billing/my-codes')
def my_codes():
    if 'user_id' not in session:
        return redirect(url_for('auth.index'))

    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('auth.index'))

    promos = PromoCode.query.filter_by(
        created_by_user_id=user.id, plan='gold'
    ).order_by(PromoCode.id.asc()).all()

    return render_template('activate/my_codes.html', promos=promos)


@activate_bp.route('/promo/share', methods=['GET', 'POST'])
def share_promo():
    code = (request.args.get('code') or request.form.get('code') or '').strip().upper()
    promo = _get_valid_promo(code)

    if not promo:
        flash('Този код вече не е валиден за споделяне (използван или изтекъл).', 'error')
        return render_template('activate/share.html', code=code, promo=None)

    if request.method == 'POST':
        recipient_email = (request.form.get('recipient_email_addr') or '').strip()
        from_name = (request.form.get('sender_display_name') or 'A colleague').strip() or 'A colleague'

        if not recipient_email or '@' not in recipient_email:
            flash('Въведи валиден имейл на получателя.', 'error')
            return render_template('activate/share.html', code=code, promo=promo)

        from app.services.email import send_shared_promo_code, send_share_confirmation
        sent = send_shared_promo_code(recipient_email, from_name, promo.code, promo.expires_at)

        if sent:
            promo.shared_to = recipient_email
            promo.shared_at = datetime.utcnow()
            promo.shared_count = (promo.shared_count or 0) + 1
            db.session.commit()
            flash(f'Кодът е изпратен на {recipient_email}.', 'success')

            # Официално потвърждение до платеца, не само popup на сайта.
            # Приоритет: логнатият в момента потребител (реалният, който натиска Share) →
            # fallback: собственикът на кода по created_by_user_id (ако споделя от линк без login).
            owner = None
            if 'user_id' in session:
                owner = User.query.get(session['user_id'])
            if not owner and promo.created_by_user_id:
                owner = User.query.get(promo.created_by_user_id)

            if owner and owner.email:
                try:
                    confirm_sent = send_share_confirmation(owner.email, promo.code, recipient_email)
                    if not confirm_sent:
                        current_app.logger.warning(
                            f"Share confirmation email failed to send to {owner.email} for code {promo.code}"
                        )
                except Exception as e:
                    current_app.logger.error(f"Share confirmation error: {e}")
            else:
                current_app.logger.warning(
                    f"No owner found for promo {promo.code} (created_by_user_id={promo.created_by_user_id}) — "
                    f"confirmation email not sent"
                )
        else:
            flash('Грешка при изпращане на имейла. Опитай отново.', 'error')
        return render_template('activate/share.html', code=code, promo=promo, sent=sent)

    return render_template('activate/share.html', code=code, promo=promo)


@activate_bp.route('/activate/department', methods=['GET', 'POST'])
def choose_department():
    flow = session.get(PROMO_SESSION_KEY)
    if not flow or 'user_id' not in session:
        return redirect(url_for('activate.activate_start'))

    promo = _get_valid_promo(flow['code'])
    if not promo:
        session.pop(PROMO_SESSION_KEY, None)
        flash('Кодът вече не е валиден.', 'error')
        return redirect(url_for('activate.activate_start'))

    if request.method == 'POST':
        department = request.form.get('department')
        if department not in ('deck', 'engine'):
            flash('Избери департамент.', 'error')
        else:
            flow['department'] = department
            session[PROMO_SESSION_KEY] = flow
            return redirect(url_for('activate.choose_level'))

    return render_template('activate/department.html', code=promo.code)


@activate_bp.route('/activate/level', methods=['GET', 'POST'])
def choose_level():
    flow = session.get(PROMO_SESSION_KEY)
    if not flow or 'department' not in flow:
        return redirect(url_for('activate.activate_start'))

    if request.method == 'POST':
        level = request.form.get('level')
        if level not in ('Operational Level', 'Management Level'):
            flash('Избери level.', 'error')
        else:
            flow['level'] = level
            session[PROMO_SESSION_KEY] = flow
            return redirect(url_for('activate.confirm'))

    return render_template('activate/level.html', department=flow['department'])


@activate_bp.route('/activate/confirm', methods=['GET', 'POST'])
def confirm():
    flow = session.get(PROMO_SESSION_KEY)
    if not flow or 'level' not in flow:
        return redirect(url_for('activate.activate_start'))

    promo = _get_valid_promo(flow['code'])
    if not promo:
        session.pop(PROMO_SESSION_KEY, None)
        flash('Кодът вече не е валиден.', 'error')
        return redirect(url_for('activate.activate_start'))

    matching_tests = Test.query.filter_by(
        category=flow['department'], level=flow['level']
    ).order_by(Test.id.asc()).all()

    if request.method == 'POST':
        chosen_ids = request.form.getlist('test_ids')
        chosen_ids = [int(i) for i in chosen_ids if i.isdigit()]
        valid_ids = {t.id for t in matching_tests}
        chosen_ids = [i for i in chosen_ids if i in valid_ids][:2]

        if len(chosen_ids) == 0:
            flash('Избери поне 1 тест.', 'error')
            return render_template('activate/confirm.html', tests=matching_tests, flow=flow)

        user = User.query.get(session['user_id'])
        if not user:
            return redirect(url_for('auth.index'))

        now = datetime.utcnow()

        # НЕ позволяваме Gold активацията да презаписва мълчаливо все още валиден Basic/Plus —
        # това би унищожило пълния им достъп в замяна на ограничения 2-тестов Gold достъп.
        if (user.plan in ('basic', 'plus') and user.plan_expires_at and user.plan_expires_at > now):
            days_left = (user.plan_expires_at - now).days
            flash(
                f'Имаш активен {user.plan.capitalize()} план с още {days_left} дни. '
                f'Активирането на Gold код сега ще спре текущия ти план предсрочно. '
                f'Изчакай {user.plan.capitalize()} планът да изтече на {user.plan_expires_at.strftime("%d.%m.%Y")}, '
                f'или се свържи с поддръжка, за да го активираме ръчно.',
                'error'
            )
            return redirect(url_for('activate.activate_start', code=flow.get('code')))

        # Активираме Gold за този код — стакваме ако вече има активен Gold период
        if user.plan == 'gold' and user.plan_expires_at and user.plan_expires_at > now:
            new_expires = user.plan_expires_at + timedelta(days=30)
            existing_ids = []
            try:
                existing_ids = json.loads(user.gold_test_ids or '[]')
            except Exception:
                existing_ids = []
            merged_ids = list({*existing_ids, *chosen_ids})[:2] if existing_ids else chosen_ids
        else:
            new_expires = now + timedelta(days=30)
            merged_ids = chosen_ids

        user.plan = 'gold'
        user.is_active = True
        user.category = flow['department']
        user.level = flow['level']
        user.plan_activated_at = now
        user.plan_expires_at = new_expires
        user.gold_test_ids = json.dumps(merged_ids)
        user.plan_grace_until = new_expires + timedelta(days=promo.mistakes_grace_days or 60)
        user.tests_used = 0

        promo.is_used = True
        promo.used_by = user.email
        promo.used_at = now
        promo.department = flow['department']
        promo.level = flow['level']
        promo.selected_test_ids = json.dumps(chosen_ids)
        promo.activated_at = now

        db.session.commit()

        session.pop(PROMO_SESSION_KEY, None)
        flash('Gold кодът е активиран успешно! 30 дни пълен достъп.', 'success')
        return redirect(url_for('dashboard.user_dashboard'))

    return render_template('activate/confirm.html', tests=matching_tests, flow=flow)
