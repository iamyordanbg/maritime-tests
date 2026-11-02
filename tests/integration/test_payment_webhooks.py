"""
tests/integration/test_payment_webhooks.py
==========================================
Стъпката "платено" за ВСЕКИ продукт през реалния _handle_checkout_completed: Basic, Plus, Gold, All Mistakes.
За всеки: записва се плащане, получава се достъп, праща се имейл; повторен webhook за същата сесия не
дублира нищо; счупен имейл не губи плащането; липсващ потребител/метаданни не гърми.
"""
import json
from datetime import datetime

import pytest
from werkzeug.security import generate_password_hash

from app.models.user import User
from app.models.test import Test
from app.models.payment import Payment
from app.models.plan_grant import PlanGrant
from app.models.promo import PromoCode
from app.models.all_mistakes_pass import AllMistakesPass
from app.services import stripe as stripe_service
from app.services import email as email_service


@pytest.fixture
def buyer(db, monkeypatch):
    sent = []
    monkeypatch.setattr(email_service, '_brevo_send', lambda to, subj, text, html=None: sent.append((to, subj)) or True)
    monkeypatch.setattr(stripe_service, '_get_stripe_fee_and_net', lambda pi: (0.0, 0.0))
    test = Test(title='Pay Test', level='Operational Level', category='deck', is_demo=False,
                questions_json=json.dumps([{'id': 1, 'question': 'Q', 'options': [{'text': 'a', 'isCorrect': True}]}]))
    u = User(name='Buyer', email='buyer_hooks@t.bg', password=generate_password_hash('Test123'),
             plan='free', is_active=False, email_verified=True)
    db.session.add_all([test, u])
    db.session.commit()
    yield type('B', (), {'user': u, 'test': test, 'sent': sent})
    db.session.rollback()
    for model in (AllMistakesPass, PlanGrant, PromoCode, Payment):
        model.query.delete()
    Test.query.filter_by(id=test.id).delete()
    User.query.filter_by(email='buyer_hooks@t.bg').delete()
    db.session.commit()


def _session(buyer, plan, sid, **meta):
    return {'id': sid, 'payment_intent': f'pi_{sid}', 'payment_status': 'paid',
            'metadata': {'user_id': str(buyer.user.id), 'plan_name': plan, **meta}}


@pytest.mark.parametrize('plan', ['basic', 'plus'])
def test_plan_payment_activates_grant_and_emails_once(buyer, plan):
    ok, _ = stripe_service._handle_checkout_completed(_session(buyer, plan, f'cs_{plan}'))
    assert ok
    pay = Payment.query.filter_by(user_id=buyer.user.id, plan=plan).one()
    grant = PlanGrant.query.filter_by(user_id=buyer.user.id, payment_id=pay.id).one()
    assert grant.plan == plan and grant.expires_at > datetime.utcnow()
    assert any(to == buyer.user.email for to, _s in buyer.sent)
    stripe_service._handle_checkout_completed(_session(buyer, plan, f'cs_{plan}'))     # повторен webhook
    assert Payment.query.filter_by(user_id=buyer.user.id).count() == 1
    assert PlanGrant.query.filter_by(user_id=buyer.user.id).count() == 1


def test_gold_payment_creates_ten_codes_and_emails_once(buyer):
    ok, _ = stripe_service._handle_checkout_completed(_session(buyer, 'gold', 'cs_gold'))
    assert ok
    codes = PromoCode.query.filter_by(created_by_user_id=buyer.user.id, plan='gold').all()
    assert len(codes) == 10 and len({c.code for c in codes}) == 10
    assert all(c.is_active and not c.is_used and c.expires_at > datetime.utcnow() for c in codes)
    assert Payment.query.filter_by(user_id=buyer.user.id, plan='gold').one().promo_email_sent is True
    stripe_service._handle_checkout_completed(_session(buyer, 'gold', 'cs_gold'))
    assert PromoCode.query.filter_by(created_by_user_id=buyer.user.id).count() == 10
    assert Payment.query.filter_by(user_id=buyer.user.id).count() == 1
    # Gold плащането не ъпгрейдва автоматично акаунта на купувача (само дава кодове)
    assert PlanGrant.query.filter_by(user_id=buyer.user.id).count() == 0


def test_all_mistakes_payment_grants_pass_for_the_chosen_test(buyer):
    ok, _ = stripe_service._handle_checkout_completed(_session(buyer, 'all_mistakes', 'cs_am', test_id=str(buyer.test.id)))
    assert ok
    ps = AllMistakesPass.query.filter_by(user_id=buyer.user.id).one()
    assert ps.test_id == buyer.test.id and ps.payment_id == Payment.query.filter_by(plan='all_mistakes').one().id
    stripe_service._handle_checkout_completed(_session(buyer, 'all_mistakes', 'cs_am', test_id=str(buyer.test.id)))
    assert AllMistakesPass.query.filter_by(user_id=buyer.user.id).count() == 1


def test_all_mistakes_without_test_id_is_rejected_and_nothing_is_saved(buyer):
    ok, _ = stripe_service._handle_checkout_completed(_session(buyer, 'all_mistakes', 'cs_am_bad'))
    assert not ok
    assert Payment.query.filter_by(user_id=buyer.user.id).count() == 0
    assert AllMistakesPass.query.filter_by(user_id=buyer.user.id).count() == 0


@pytest.mark.parametrize('plan,meta', [('plus', {}), ('gold', {}), ('all_mistakes', {'test_id': 'TEST'})])
def test_broken_email_does_not_lose_the_payment(buyer, monkeypatch, plan, meta):
    def boom(*a, **k):
        raise RuntimeError('brevo down')
    monkeypatch.setattr(email_service, '_brevo_send', boom)
    meta = {k: str(buyer.test.id) if v == 'TEST' else v for k, v in meta.items()}
    ok, _ = stripe_service._handle_checkout_completed(_session(buyer, plan, f'cs_boom_{plan}', **meta))
    assert ok
    assert Payment.query.filter_by(user_id=buyer.user.id, plan=plan).count() == 1


def test_missing_metadata_and_unknown_user_do_not_crash(buyer):
    assert stripe_service._handle_checkout_completed({'id': 'cs_x', 'metadata': {}})[0] is False
    ok, _ = stripe_service._handle_checkout_completed(
        {'id': 'cs_y', 'payment_status': 'paid', 'metadata': {'user_id': '999999', 'plan_name': 'plus'}})
    assert ok is False
    assert Payment.query.count() == 0
