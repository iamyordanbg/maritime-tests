"""
app/services/all_mistakes_pass.py
=================================
Платен допълнителен достъп до All Mistakes (цена, срок и лимит - ALL_MISTAKES в
app/services/plans.py) за един тест: или след като абонаментът му е изтекъл, или когато планът му
изобщо няма функцията (Basic). Плащането е през
същия Stripe Checkout като плановете; след успех се създава AllMistakesPass.
"""
from datetime import datetime, timedelta

import stripe
from flask import current_app

from app.extensions import db
from app.models.all_mistakes_pass import AllMistakesPass
from app.models.test import Test
from app.services import all_mistakes as am
from app.services.plans import ALL_MISTAKES

PLAN_KEY = 'all_mistakes'  # стойност на Payment.plan и на metadata.plan_name в Stripe


def can_buy(user, test_id):
    """Покупката е възможна в режим 'offer' (планът няма функцията) или 'review' (изтекъл абонамент,
    функцията е била включена и е отключена)."""
    ent = am.entitlement_for_test(user, test_id)
    if not ent:
        return False
    return ent['mode'] == 'offer' or (ent['mode'] == 'review' and am.is_open(user.id, test_id, ent))


def create_checkout(user, test_id, success_url, cancel_url):
    """URL на Stripe Checkout или None при грешка."""
    from app.services.stripe import _stripe
    test = Test.query.get(test_id)
    try:
        session = _stripe().checkout.Session.create(
            payment_method_types=['card'], mode='payment', customer_email=user.email,
            line_items=[{'price_data': {
                'currency': ALL_MISTAKES['currency'],
                'unit_amount': int(round(ALL_MISTAKES['price'] * 100)),
                'product_data': {'name': f"Maritime Tests — {ALL_MISTAKES['name']}"
                                         f"{' — ' + test.title if test else ''}",
                                 'description': ALL_MISTAKES['description']},
            }, 'quantity': 1}],
            metadata={'user_id': str(user.id), 'plan_name': PLAN_KEY, 'test_id': str(test_id)},
            success_url=success_url, cancel_url=cancel_url,
        )
        return session.url
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe all-mistakes checkout error: {e}")
        return None


def grant_pass(user, test_id, payment_id=None, now=None):
    """Създава платения достъп (ALL_MISTAKES['days'] дни, ALL_MISTAKES['tests_quota'] решавания)."""
    now = now or datetime.utcnow()
    p = AllMistakesPass(user_id=user.id, test_id=test_id, quota=ALL_MISTAKES['tests_quota'],
                        activated_at=now, expires_at=now + timedelta(days=ALL_MISTAKES['days']),
                        payment_id=payment_id)
    db.session.add(p)
    return p
