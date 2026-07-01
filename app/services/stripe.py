"""
app/services/stripe.py
======================
Stripe интеграция — Checkout Session, webhook обработка.
"""

import os
import stripe
from flask import current_app
from datetime import datetime

from app.extensions import db
from app.models.user import User
from app.models.payment import Payment
from app.services.plans import activate_plan, generate_gold_promos, get_plan_config

PLAN_PRICES = {'basic': 19.99, 'plus': 39.99, 'gold': 299.99}


def _stripe():
    stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY') or os.environ.get('STRIPE_SECRET_KEY')
    return stripe


# ---------------------------------------------------------------------------
# Checkout Session
# ---------------------------------------------------------------------------

def create_checkout_session(user, plan_name: str, success_url: str, cancel_url: str) -> str | None:
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
                    'unit_amount': int(config['price'] * 100),
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
    s = _stripe()
    webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET') or os.environ.get('STRIPE_WEBHOOK_SECRET')
    return s.Webhook.construct_event(payload, sig_header, webhook_secret)


def handle_webhook_event(event: dict) -> tuple[bool, str]:
    event_type = event.get('type')
    if event_type == 'checkout.session.completed':
        return _handle_checkout_completed(event['data']['object'])
    return True, f"Event {event_type} ignored"


def _get_stripe_fee_and_net(payment_intent_id: str) -> tuple[float, float]:
    """
    Взима точната Stripe такса и нетната сума от balance_transaction.
    Връща (stripe_fee, net_amount) в EUR.
    """
    try:
        s = _stripe()
        pi = s.PaymentIntent.retrieve(payment_intent_id, expand=['latest_charge.balance_transaction'])
        bt = pi.latest_charge.balance_transaction
        fee = round(bt.fee / 100, 2)
        net = round(bt.net / 100, 2)
        return fee, net
    except Exception as e:
        current_app.logger.warning(f"Could not fetch balance_transaction: {e}")
        return 0.0, 0.0


def _record_payment(user: User, plan_name: str, session: dict) -> None:
    """Записва плащането с брутна сума, Stripe такса и нетна сума."""
    amount = PLAN_PRICES.get(plan_name, 0)
    payment_intent_id = session.get('payment_intent', '')

    stripe_fee, net_amount = _get_stripe_fee_and_net(payment_intent_id)

    p = Payment(
        user_id               = user.id,
        plan                  = plan_name,
        amount                = amount,
        stripe_fee            = stripe_fee,
        net_amount            = net_amount if net_amount > 0 else round(amount - (amount * 0.029 + 0.30), 2),
        stripe_payment_intent = payment_intent_id,
        stripe_session_id     = session.get('id', ''),
        paid_at               = datetime.utcnow(),
    )
    db.session.add(p)


def _handle_checkout_completed(session: dict) -> tuple[bool, str]:
    metadata       = session.get('metadata', {})
    user_id        = metadata.get('user_id')
    plan_name      = metadata.get('plan_name')
    payment_intent = session.get('payment_intent', '')
    session_id     = session.get('id', '')

    if not user_id or not plan_name:
        return False, "Missing metadata"

    # Проверяваме дали вече е обработен този session
    if session_id:
        from app.models.payment import Payment
        already = Payment.query.filter_by(stripe_session_id=session_id).first()
        if already:
            current_app.logger.info(f"Webhook session {session_id} already processed, skipping")
            return True, f"Session {session_id} already processed"

    user = User.query.get(int(user_id))
    if not user:
        # Потребителят може да е пресъздаден — търсим по имейл от session
        customer_email = session.get('customer_email') or session.get('customer_details', {}).get('email')
        if customer_email:
            user = User.query.filter_by(email=customer_email).first()
        if not user:
            return False, f"User {user_id} not found"

    try:
        if plan_name == 'gold':
            # ВАЖНО: не ъпгрейдваме автоматично акаунта на купувача тук.
            # Gold плащането купува 10 промокода за раздаване — самият купувач
            # получава достъп само ако сам активира един от своите кодове през /activate,
            # точно като всеки друг получател на код.
            codes = generate_gold_promos(user, payment_intent)
            _record_payment(user, plan_name, session)
            db.session.commit()

            try:
                from app.services.email import send_gold_promo_codes, send_admin_new_payment
                from app.models.promo import PromoCode as _PC
                from app.models.payment import Payment as _Payment
                first_promo = _PC.query.filter_by(stripe_payment_intent=payment_intent).first()
                codes_expiry = first_promo.expires_at if first_promo else None
                email_sent = send_gold_promo_codes(user.email, user.name, codes, codes_expiry)
                send_admin_new_payment(user.name, user.email, 'gold')

                # Официален запис, че кодовете са изпратени на платеца
                pay_row = _Payment.query.filter_by(stripe_payment_intent=payment_intent).first()
                if pay_row and email_sent:
                    pay_row.promo_email_sent = True
                    pay_row.promo_email_sent_at = datetime.utcnow()
                    db.session.commit()
            except Exception as e:
                current_app.logger.warning(f"Gold promo email failed: {e}")

            return True, f"Gold: {len(codes)} promo codes generated for user {user_id}"

        else:
            activate_plan(user, plan_name)
            _record_payment(user, plan_name, session)
            db.session.commit()

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
