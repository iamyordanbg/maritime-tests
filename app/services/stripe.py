"""
app/services/stripe.py
======================
Stripe интеграция — Checkout Session, webhook обработка.

Използване:
    from app.services.stripe import (
        create_checkout_session,
        handle_webhook_event,
    )
"""

import os
import stripe
from flask import current_app
from datetime import datetime

from app.extensions import db
from app.models.user import User
from app.services.plans import activate_plan, generate_gold_promos, get_plan_config


# ---------------------------------------------------------------------------
# Stripe клиент
# ---------------------------------------------------------------------------

def _stripe():
    """Инициализира stripe с SECRET_KEY от config."""
    stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY') or os.environ.get('STRIPE_SECRET_KEY')
    return stripe


# ---------------------------------------------------------------------------
# Checkout Session
# ---------------------------------------------------------------------------

def create_checkout_session(user, plan_name: str, success_url: str, cancel_url: str) -> str | None:
    """
    Създава Stripe Checkout Session и връща URL за пренасочване.
    Връща None при грешка.

    Параметри:
        user         — User обект
        plan_name    — 'basic', 'plus' или 'gold'
        success_url  — URL след успешно плащане (с ?session_id={CHECKOUT_SESSION_ID})
        cancel_url   — URL при отказ
    """
    config = get_plan_config(plan_name)
    if not config:
        return None

    s = _stripe()

    try:
        session = s.checkout.Session.create(
            payment_method_types=['card'],
            mode='payment',
            customer_email=user.email,
            line_items=[{
                'price_data': {
                    'currency': config['currency'],
                    'unit_amount': int(config['price'] * 100),  # cents
                    'product_data': {
                        'name': f"Maritime Tests — {config['name']}",
                        'description': config['description'],
                    },
                },
                'quantity': 1,
            }],
            metadata={
                'user_id':   str(user.id),
                'plan_name': plan_name,
            },
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return session.url

    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe checkout error: {e}")
        return None


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

def construct_webhook_event(payload: bytes, sig_header: str):
    """
    Верифицира и конструира Stripe webhook event.
    Хвърля stripe.error.SignatureVerificationError при невалиден подпис.
    """
    s = _stripe()
    webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET') or os.environ.get('STRIPE_WEBHOOK_SECRET')
    return s.Webhook.construct_event(payload, sig_header, webhook_secret)


def handle_webhook_event(event: dict) -> tuple[bool, str]:
    """
    Обработва Stripe webhook event.
    Връща (success: bool, message: str).

    Поддържани events:
        checkout.session.completed — активира план след успешно плащане
    """
    event_type = event.get('type')

    if event_type == 'checkout.session.completed':
        return _handle_checkout_completed(event['data']['object'])

    # Останалите events игнорираме засега
    return True, f"Event {event_type} ignored"


def _handle_checkout_completed(session: dict) -> tuple[bool, str]:
    """Активира план след checkout.session.completed."""
    metadata  = session.get('metadata', {})
    user_id   = metadata.get('user_id')
    plan_name = metadata.get('plan_name')
    payment_intent = session.get('payment_intent', '')

    if not user_id or not plan_name:
        return False, "Missing metadata"

    user = User.query.get(int(user_id))
    if not user:
        return False, f"User {user_id} not found"

    try:
        if plan_name == 'gold':
            # Gold → генерира промокодове, не активира директно
            user.plan = 'gold'
            user.plan_activated_at = datetime.utcnow()
            codes = generate_gold_promos(user, payment_intent)
            db.session.commit()

            # Изпрати промокодовете до клиента + известие до admin
            try:
                from app.services.email import send_gold_promo_codes, send_admin_new_payment
                send_gold_promo_codes(user.email, user.name, codes)
                send_admin_new_payment(user.name, user.email, 'gold')
            except Exception as e:
                current_app.logger.warning(f"Gold promo email failed: {e}")

            return True, f"Gold: {len(codes)} promo codes generated for user {user_id}"

        else:
            # Basic / Plus → активира директно
            activate_plan(user, plan_name)
            db.session.commit()

            # Изпрати потвърждение до клиента
            try:
                from app.services.email import send_plan_activated, send_admin_new_payment
                send_plan_activated(user.email, user.name, plan_name)
                send_admin_new_payment(user.name, user.email, plan_name)
            except Exception as e:
                current_app.logger.warning(f"Plan activation email failed: {e}")

            return True, f"Plan {plan_name} activated for user {user_id}"

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Webhook handler error: {e}")
        return False, str(e)
