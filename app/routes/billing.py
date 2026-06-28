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
        'billing/plans.html',
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
        return redirect(url_for('billing.plans'))

    if 'user_id' not in session:
        session['pending_plan'] = plan_name
        return redirect(url_for('auth.index'))

    user = User.query.get(session['user_id'])
    if not user:
        session['pending_plan'] = plan_name
        return redirect(url_for('auth.index'))

    base_url = current_app.config.get('BASE_URL') or os.environ.get('BASE_URL', 'http://localhost:5000')

    success_url = f"{base_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}&plan={plan_name}"
    cancel_url  = f"{base_url}/billing/plans"

    checkout_url = create_checkout_session(user, plan_name, success_url, cancel_url)

    if not checkout_url:
        flash('Грешка при свързване със Stripe. Опитай отново.', 'error')
        return redirect(url_for('billing.plans'))

    return redirect(checkout_url)


# ---------------------------------------------------------------------------
# Success — след успешно плащане
# ---------------------------------------------------------------------------

@billing.route('/success')
@login_required
def success():
    """Stripe пренасочва тук след успешно плащане."""
    plan_name = request.args.get('plan', '')
    plan_config = PLANS.get(plan_name, {})

    user = User.query.get(session['user_id'])
    plan_display = get_plan_display(user) if user else None

    return render_template(
        'billing/success.html',
        plan_name=plan_name,
        plan_config=plan_config,
        plan_display=plan_display,
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
