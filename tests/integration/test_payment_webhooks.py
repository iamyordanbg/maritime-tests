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


def test_gold_code_terms_come_only_from_plan_config(monkeypatch):
    from types import SimpleNamespace
    from app.services import plans
    std = SimpleNamespace(is_custom=False, duration_days=30, tests_quota_override=50)
    assert plans.gold_code_terms(std) == (plans.PLANS['gold']['valid_days_per_code'], plans.PLANS['gold']['tests_quota'])
    monkeypatch.setitem(plans.PLANS['gold'], 'valid_days_per_code', 7)
    monkeypatch.setitem(plans.PLANS['gold'], 'tests_quota', 11)
    assert plans.gold_code_terms(std) == (7, 11)                       # стойностите на самия код не се ползват за Gold
    custom = SimpleNamespace(is_custom=True, duration_days=45, tests_quota_override=60)
    assert plans.gold_code_terms(custom) == (45, 60)                   # Custom промо: настройките на админа
    legacy = SimpleNamespace(is_custom=True, duration_days=None, tests_quota_override=None)
    assert plans.gold_code_terms(legacy) == (7, 11)                    # стар ред без стойности -> конфигурацията


def _activate(client, buyer, code):
    client.post('/login', data={'email': buyer.user.email, 'password': 'Test123'}, headers={'X-Requested-With': 'XMLHttpRequest'})
    with client.session_transaction() as sess:
        sess['activate_flow'] = {'code': code, 'department': 'deck', 'level': 'Operational Level'}
    return client.post('/activate/confirm', data={'test_ids': [str(buyer.test.id)]}, follow_redirects=False)


def test_activate_confirm_gold_uses_plan_config_even_if_code_row_says_30(client, db, buyer):
    from app.models.gold_grant import GoldGrant
    from app.services.plans import PLANS
    stripe_service._handle_checkout_completed(_session(buyer, 'gold', 'cs_gold_act'))
    promo = PromoCode.query.filter_by(created_by_user_id=buyer.user.id).first()
    promo.duration_days, promo.tests_quota_override = 30, 50          # стойности на самия ред - не трябва да се ползват
    db.session.commit()
    assert _activate(client, buyer, promo.code).status_code == 302
    g = GoldGrant.query.filter_by(user_id=buyer.user.id).one()
    assert g.quota == PLANS['gold']['tests_quota']
    assert abs((g.expires_at - g.activated_at).total_seconds() - PLANS['gold']['valid_days_per_code'] * 86400) < 5
    GoldGrant.query.filter_by(user_id=buyer.user.id).delete()
    db.session.commit()


def test_activate_confirm_custom_promo_uses_its_own_terms(client, db, buyer):
    from app.models.promo_grant import PromoGrant
    db.session.add(PromoCode(code='CUSTOMX1', client_name='c', access_type='Custom', is_custom=True, is_active=True,
                             duration_days=45, tests_quota_override=60, usage_limit_type='single',
                             expires_at=datetime.utcnow().replace(year=2099)))
    db.session.commit()
    assert _activate(client, buyer, 'CUSTOMX1').status_code == 302
    g = PromoGrant.query.filter_by(user_id=buyer.user.id).one()
    assert g.quota == 60 and abs((g.expires_at - g.activated_at).total_seconds() - 45 * 86400) < 5
    PromoGrant.query.filter_by(user_id=buyer.user.id).delete()
    db.session.commit()
