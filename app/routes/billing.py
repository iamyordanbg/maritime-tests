"""
app/routes/billing.py
=====================
Billing routes — планове, Stripe checkout, webhook, success.
"""

import os
import stripe
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, jsonify, session, current_app
)
from app.extensions import db
from app.models.user import User
from app.permissions.decorators import login_required
from app.services.plans import PLANS, get_plan_display
from app.services.stripe import (
    create_checkout_session,
    construct_webhook_event,
    handle_webhook_event,
)

billing = Blueprint('billing', __name__, url_prefix='/billing')


# ---------------------------------------------------------------------------
# Страница с планове
# ---------------------------------------------------------------------------

@billing.route('/plans')
def plans():
    """Публична страница с планове — достъпна и без login."""
    user = None
    plan_display = None

    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            plan_display = get_plan_display(user)

    return render_template(
        'billing/plans_page.html',
        plans=PLANS,
        user=user,
        plan_display=plan_display,
    )


# ---------------------------------------------------------------------------
# Checkout — стартира Stripe плащане
# ---------------------------------------------------------------------------

@billing.route('/checkout/<plan_name>', methods=['GET', 'POST'])
def checkout(plan_name):
    """Създава Stripe Checkout Session и пренасочва към Stripe."""
    if plan_name not in PLANS:
        flash('Невалиден план.', 'error')
        return redirect(url_for('dashboard.user_dashboard'))

    if 'user_id' not in session:
        session['pending_plan'] = plan_name
        return redirect(url_for('auth.index') + '?register=1')

    user = User.query.get(session['user_id'])
    if not user:
        session['pending_plan'] = plan_name
        return redirect(url_for('auth.index') + '?register=1')

    # БЪГ ФИКС: преди тук се ползваше статичния BASE_URL env var (сочи
    # трайно към production URL-а) - Stripe success_url/cancel_url винаги
    # водеха към production, дори когато заявката реално идваше от Railway
    # PR preview среда (напр. web-maritime-tests-pr-14.up.railway.app).
    # Потребител, тестващ плащане на PR preview, след успешно плащане
    # завършваше пренасочен към production - объркващо, и технически грешно
    # (плащането е валидно, но резултатът/сесията са на друг домейн).
    # request.host_url отразява РЕАЛНИЯ домейн на текущата заявка -
    # коректно и за production, и за всяка PR preview среда, без нужда
    # от отделна BASE_URL стойност per-environment (Railway PR gotcha:
    # редактиране на env var в съществуваща PR среда не се прилага
    # надеждно - този фикс го заобикаля напълно).
    base_url = request.host_url.rstrip('/')

    success_url = f"{base_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}&plan={plan_name}"
    # БЪГ ФИКС: billing/plans.html е modal fragment (display:none, {% include %}
    # в user_sidebar.html), НЕ самостоятелна страница - няма <html>/<head>/CSS/JS
    # обвивка. При директна навигация (напр. Stripe cancel redirect) браузърът
    # получава само скрития div - технически валиден HTML, 0 JS грешки, но
    # изцяло невидим (blank screen). cancel_url вече сочи към dashboard -
    # реална пълна страница, коректна дестинация след cancel на плащане.
    cancel_url  = f"{base_url}/dashboard"

    checkout_url = create_checkout_session(user, plan_name, success_url, cancel_url)

    if not checkout_url:
        flash('Грешка при свързване със Stripe. Опитай отново.', 'error')
        return redirect(url_for('dashboard.user_dashboard'))

    return redirect(checkout_url)


# ---------------------------------------------------------------------------
# Success — след успешно плащане
# ---------------------------------------------------------------------------

@billing.route('/success')
@login_required
def success():
    """Stripe пренасочва тук след успешно плащане."""
    plan_name = request.args.get('plan', '')
    session_id = request.args.get('session_id', '')
    plan_config = PLANS.get(plan_name, {})

    # Fallback grant: Stripe webhook-ът е фиксиран URL (сочи само към
    # production) - плащане от PR preview среда никога не получава webhook
    # event там. Verify-ваме checkout session-а директно тук и grant-ваме,
    # ако webhook-ът все още не го е обработил (идемпотентно - виж
    # verify_and_grant_checkout_session docstring).
    if session_id:
        from app.services.stripe import verify_and_grant_checkout_session
        ok, message = verify_and_grant_checkout_session(session_id)
        if not ok:
            current_app.logger.warning(f"billing/success verify_and_grant failed: {message}")

    user = User.query.get(session['user_id'])
    plan_display = get_plan_display(user) if user else None

    plan_display_data = plan_config.get('display', {}) if plan_config else {}

    return render_template(
        'billing/success.html',
        plan_name=plan_name,
        plan_config=plan_config,
        plan_display=plan_display,
        plan_display_data=plan_display_data,
        user=user,
    )


# ---------------------------------------------------------------------------
# Webhook — Stripe изпраща events тук
# ---------------------------------------------------------------------------

@billing.route('/webhook', methods=['POST'])
def webhook():
    """
    Stripe webhook endpoint.
    Трябва да е изключен от CSRF protection (ако има такава).
    В Railway Variables: STRIPE_WEBHOOK_SECRET=whsec_...
    """
    payload    = request.get_data()
    sig_header = request.headers.get('Stripe-Signature', '')

    try:
        event = construct_webhook_event(payload, sig_header)
    except stripe.error.SignatureVerificationError as e:
        current_app.logger.warning(f"Webhook signature failed: {e}")
        return jsonify({'error': 'Invalid signature'}), 400
    except Exception as e:
        current_app.logger.error(f"Webhook error: {e}")
        return jsonify({'error': str(e)}), 400

    success, message = handle_webhook_event(event)
    current_app.logger.info(f"Webhook {event['type']}: {message}")

    if not success:
        return jsonify({'error': message}), 500

    return jsonify({'status': 'ok'}), 200


# ---------------------------------------------------------------------------
# API — текущ план на потребителя
# ---------------------------------------------------------------------------

@billing.route('/api/my-plan')
@login_required
def api_my_plan():
    """Връща текущия план на потребителя като JSON."""
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(get_plan_display(user))
