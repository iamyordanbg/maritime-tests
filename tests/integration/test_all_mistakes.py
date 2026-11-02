"""
tests/integration/test_all_mistakes.py
======================================
All Mistakes: достъп по план/промо флаг/срок, натрупване на грешки, страница, старт, submit.
"""
import json
from datetime import datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

from app.models.user import User
from app.models.test import Test
from app.models.result import TestResult
from app.models.plan_grant import PlanGrant
from app.models.gold_grant import GoldGrant
from app.models.promo_grant import PromoGrant
from app.models.promo import PromoCode
from app.services import all_mistakes as svc
from app.services.plans import ALL_MISTAKES
from app.services import all_mistakes_pass as passes
from app.models.all_mistakes_pass import AllMistakesPass
from app.models.payment import Payment

AJAX = {'X-Requested-With': 'XMLHttpRequest'}
UNLOCK = svc.ALL_MISTAKES['unlock_tests']
QUESTIONS = [{'id': i, 'question': f'Q{i}', 'options': [{'text': 'ok', 'isCorrect': True},
                                                       {'text': 'bad', 'isCorrect': False}]} for i in (1, 2, 3)]


@pytest.fixture
def env(db):
    """Тест с 3 въпроса + помощник за създаване на потребители/резултати."""
    test = Test(title='AM Test', level='Operational Level', category='deck', is_demo=False,
                questions_json=json.dumps(QUESTIONS))
    db.session.add(test)
    db.session.commit()
    created = []

    class Env:
        pass
    e = Env()
    e.test = test

    def make_user(name):
        u = User(name=name, email=f'{name}@am.test', password=generate_password_hash('Test123'),
                 plan='free', is_active=True, is_admin=False, email_verified=True)
        db.session.add(u)
        db.session.commit()
        created.append(u)
        return u

    def add_result(user, answers, when=None, test_type='test'):
        r = TestResult(user_id=user.id, test_id=test.id, score=0, total=len(answers), percent=0, passed=False,
                       answers_json=json.dumps(answers), test_type=test_type, duration=1,
                       question_ids_json='[]', taken_at=when or datetime.utcnow())
        db.session.add(r)
        db.session.commit()
        return r

    def plan_grant(user, plan, days=10, started=None):
        g = PlanGrant(user_id=user.id, plan=plan, quota=50, tests_used=0, library_test_id=test.id,
                      activated_at=started or datetime.utcnow() - timedelta(days=1),
                      expires_at=datetime.utcnow() + timedelta(days=days))
        db.session.add(g)
        db.session.commit()
        return g

    def unlock(user, when=None):
        """ALL_MISTAKES['unlock_tests'] верни (без грешки) решавания - отключва All Mistakes."""
        for _ in range(UNLOCK):
            add_result(user, {'1': 0}, when=when, test_type='test')

    e.make_user, e.add_result, e.plan_grant, e.unlock = make_user, add_result, plan_grant, unlock
    yield e
    db.session.rollback()
    for model in (AllMistakesPass, TestResult, PlanGrant, GoldGrant, PromoGrant):
        model.query.filter(model.user_id.in_([u.id for u in created])).delete(synchronize_session=False)
    Payment.query.filter(Payment.user_id.in_([u.id for u in created])).delete(synchronize_session=False)
    for u in created:
        db.session.delete(u)
    db.session.delete(test)
    db.session.commit()


def _login(client, user):
    client.post('/login', data={'email': user.email, 'password': 'Test123'}, headers=AJAX)


# ---------- помощници ----------

def _expire(db, g, days_ago):
    """Прави grant-а изтекъл преди `days_ago` дни."""
    g.expires_at = datetime.utcnow() - timedelta(days=days_ago)
    db.session.commit()


def _gold(db, u, env, expires_in_days, started_days_ago=40):
    now = datetime.utcnow()
    g = GoldGrant(user_id=u.id, test_ids=json.dumps([env.test.id]), quota=150, tests_used=0,
                  activated_at=now - timedelta(days=started_days_ago), expires_at=now + timedelta(days=expires_in_days),
                  grace_until=now + timedelta(days=expires_in_days + 60))
    db.session.add(g)
    db.session.commit()
    return g


def _submit(client, test_id, answers):
    return client.post(f'/test/{test_id}/submit', json={'answers': answers, 'test_type': 'all_mistakes',
                                                        'question_ids': [int(k) for k in answers], 'duration': 5})


def _used_credits(u, env, g):
    return svc.quota_used(u.id, [env.test.id], g.activated_at)


# ---------- кой има функцията и в какъв режим ----------

def test_plus_has_feature_basic_does_not(env):
    plus, basic = env.make_user('plus1'), env.make_user('basic1')
    env.plan_grant(plus, 'plus')
    env.plan_grant(basic, 'basic')
    assert svc.entitlements(plus)[env.test.id]['mode'] == 'active'
    assert svc.entitlements(basic)[env.test.id]['mode'] == 'offer'   # карта има, но е заключена


def test_gold_grant_has_feature(db, env):
    u = env.make_user('gold1')
    _gold(db, u, env, 5)
    assert svc.entitlements(u)[env.test.id]['mode'] == 'active'


def test_promo_grant_needs_flag(db, env):
    with_flag, without = env.make_user('promoyes'), env.make_user('promono')
    now = datetime.utcnow()
    for u, flag in ((with_flag, True), (without, False)):
        db.session.add(PromoGrant(user_id=u.id, test_ids=json.dumps([env.test.id]), quota=50, activated_at=now,
                                  expires_at=now + timedelta(days=5), all_mistakes=flag))
    db.session.commit()
    assert env.test.id in svc.entitlements(with_flag)
    assert svc.entitlements(without)[env.test.id]['mode'] == 'offer'


def test_expired_subscription_is_review_only_for_review_days(db, env):
    plus, gold = env.make_user('plusexp'), env.make_user('goldexp')
    _expire(db, env.plan_grant(plus, 'plus'), 1)
    g = _gold(db, gold, env, -3)
    for u in (plus, gold):
        ent = svc.entitlements(u)[env.test.id]
        assert ent['mode'] == 'review'
    # Gold's stored 60-day grace is NOT used: review window comes from config (review_days)
    assert svc.entitlements(gold)[env.test.id]['ends_at'] == g.expires_at + timedelta(days=svc.ALL_MISTAKES['review_days'])


def test_nothing_after_review_window(db, env):
    plus, gold = env.make_user('plusgone'), env.make_user('goldgone')
    _expire(db, env.plan_grant(plus, 'plus'), svc.ALL_MISTAKES['review_days'] + 1)
    _gold(db, gold, env, -(svc.ALL_MISTAKES['review_days'] + 1))
    assert svc.entitlements(plus) == {} and svc.entitlements(gold) == {}


def test_paid_pass_gives_pass_mode(db, env):
    u = env.make_user('passmode')
    _expire(db, env.plan_grant(u, 'plus'), 2)
    passes.grant_pass(u, env.test.id)
    db.session.commit()
    ent = svc.entitlements(u)[env.test.id]
    assert ent['mode'] == 'pass' and ent['pass_'].quota == svc.ALL_MISTAKES['tests_quota']


def test_pass_survives_past_review_window(db, env):
    u = env.make_user('passlate')
    _expire(db, env.plan_grant(u, 'plus'), svc.ALL_MISTAKES['review_days'] + 5)
    passes.grant_pass(u, env.test.id)
    db.session.commit()
    assert svc.entitlements(u)[env.test.id]['mode'] == 'pass'


# ---------- грешки ----------

def test_mistakes_union_across_all_test_types_and_new_ones_added(env):
    u = env.make_user('union')
    env.plan_grant(u, 'plus')
    env.add_result(u, {'1': 1, '2': 0}, test_type='test')           # грешка: 1
    ent = svc.entitlements(u)[env.test.id]
    assert svc.mistakes_of(u.id, env.test, ent) == {'1'}
    env.add_result(u, {'1': 0, '3': 1}, test_type='mix')            # 1 вече е верен, но остава; нова: 3
    env.add_result(u, {'2': 1}, test_type='simulator')              # нова: 2
    assert svc.mistakes_of(u.id, env.test, ent) == {'1', '2', '3'}


def test_results_before_activation_ignored(env):
    u = env.make_user('before')
    env.plan_grant(u, 'plus', started=datetime.utcnow() - timedelta(days=1))
    env.add_result(u, {'1': 1}, when=datetime.utcnow() - timedelta(days=5))
    assert svc.mistakes_of(u.id, env.test, svc.entitlements(u)[env.test.id]) == set()


def test_mistakes_stop_growing_after_subscription_end(db, env):
    u = env.make_user('capped')
    g = env.plan_grant(u, 'plus', started=datetime.utcnow() - timedelta(days=20))
    env.add_result(u, {'1': 1}, when=datetime.utcnow() - timedelta(days=15))
    _expire(db, g, 5)
    env.add_result(u, {'2': 1}, when=datetime.utcnow())             # решено СЛЕД края (напр. платен достъп)
    assert svc.mistakes_of(u.id, env.test, svc.entitlements(u)[env.test.id]) == {'1'}


def test_other_users_results_not_counted(env):
    a, b = env.make_user('usera'), env.make_user('userb')
    env.plan_grant(a, 'plus')
    env.add_result(b, {'1': 1})
    assert svc.mistakes_of(a.id, env.test, svc.entitlements(a)[env.test.id]) == set()


# ---------- отключване ----------

def test_locked_until_unlock_tests_solved(client, env):
    u = env.make_user('lockedyet')
    env.plan_grant(u, 'plus')
    env.add_result(u, {'1': 1})
    _login(client, u)
    html = client.get('/all-mistakes').get_data(as_text=True)
    assert 'Locked' in html and 'amLockedModal' in html
    assert '>1</span>' in html and 'js-am-locked' in html and f'data-needed="{UNLOCK}"' in html and 'data-solved="1"' in html
    resp = client.get(f'/test/{env.test.id}/all-mistakes')
    assert resp.status_code == 302 and resp.headers['Location'].endswith('/all-mistakes')
    assert client.get(f'/all-mistakes/{env.test.id}/review').status_code == 302
    assert _submit(client, env.test.id, {'1': 0}).status_code == 403


def test_test_mix_and_simulator_count_for_unlock(env):
    u = env.make_user('unlockkinds')
    env.plan_grant(u, 'plus')
    start = svc.entitlements(u)[env.test.id]['start']
    for kind in ('mistakes', 'all_mistakes'):
        env.add_result(u, {'1': 0}, test_type=kind)
    assert svc.unlock_progress(u.id, env.test.id, start) == (0, UNLOCK)
    for kind in ('test', 'mix', 'simulator'):
        env.add_result(u, {'1': 0}, test_type=kind)
    assert svc.unlock_progress(u.id, env.test.id, start)[0] == 3


def test_unlock_threshold_comes_from_config():
    assert svc.ALL_MISTAKES['unlock_tests'] >= 1 and svc.ALL_MISTAKES['price'] > 0
    assert svc.ALL_MISTAKES['tests_quota'] == 100 and svc.ALL_MISTAKES['review_days'] == 30 and svc.ALL_MISTAKES['days'] == 30


# ---------- страници ----------

def test_page_locked_for_basic(client, env):
    u = env.make_user('lockedb')
    env.plan_grant(u, 'basic')
    _login(client, u)
    html = client.get('/all-mistakes').get_data(as_text=True)
    assert 'AM Test' in html and 'Not included in your plan' in html and 'Locked' in html
    assert 'View answers' not in html and '>Solve<' not in html


def test_page_lists_test_with_count_and_two_actions(client, env):
    u = env.make_user('listplus')
    env.plan_grant(u, 'plus')
    env.add_result(u, {'1': 1, '2': 1, '3': 0})
    env.unlock(u)
    _login(client, u)
    html = client.get('/all-mistakes').get_data(as_text=True)
    assert 'AM Test' in html and '>2</span>' in html and 'View answers' in html and '>Solve</a>' in html


def test_page_requires_login(client):
    assert client.get('/all-mistakes').status_code in (302, 401)


def test_start_renders_only_wrong_questions(client, env):
    u = env.make_user('startplus')
    env.plan_grant(u, 'plus')
    env.add_result(u, {'1': 1, '2': 0, '3': 1})
    env.unlock(u)
    _login(client, u)
    html = client.get(f'/test/{env.test.id}/all-mistakes').get_data(as_text=True)
    assert "testType: 'all_mistakes'" in html and 'ALL MISTAKES' in html and 'totalQuestions: 2' in html


def test_start_without_mistakes_redirects_to_page(client, env):
    u = env.make_user('nomist')
    env.plan_grant(u, 'plus')
    env.unlock(u)
    _login(client, u)
    resp = client.get(f'/test/{env.test.id}/all-mistakes')
    assert resp.status_code == 302 and resp.headers['Location'].endswith('/all-mistakes')


def test_start_and_review_denied_for_basic(client, env):
    u = env.make_user('startbasic')
    env.plan_grant(u, 'basic')
    env.add_result(u, {'1': 1})
    _login(client, u)
    for path in (f'/test/{env.test.id}/all-mistakes', f'/all-mistakes/{env.test.id}/review'):
        resp = client.get(path)
        assert resp.status_code == 302 and resp.headers['Location'].endswith(f'/all-mistakes/{env.test.id}/unlock')
    assert _submit(client, env.test.id, {'1': 0}).status_code == 403


def test_review_page_shows_correct_answers(client, env):
    u = env.make_user('reviewer')
    env.plan_grant(u, 'plus')
    env.add_result(u, {'1': 1, '2': 1})
    env.unlock(u)
    _login(client, u)
    html = client.get(f'/all-mistakes/{env.test.id}/review').get_data(as_text=True)
    assert 'Q1' in html and 'Q2' in html and 'Q3' not in html and html.count('is-correct font-bold') == 2 and 'opt-label' in html
    assert 'id="prefsPanel"' in html and 'Review mode' in html   # същият вид и настройки за четене като страницата на теста


# ---------- такса и квота (активен абонамент) ----------

def test_every_solve_costs_one_credit(client, env):
    u = env.make_user('credit')
    g = env.plan_grant(u, 'plus')
    env.add_result(u, {'1': 1})
    env.unlock(u)
    _login(client, u)
    before = _used_credits(u, env, g)
    for answers in ({'1': 0}, {'2': 0}):
        assert _submit(client, env.test.id, answers).status_code == 200
    assert _used_credits(u, env, g) == before + 2
    assert PlanGrant.query.get(g.id).tests_used == 2
    assert f'>{50 - before - 2}/50<' in client.get('/dashboard').get_data(as_text=True)


def test_all_mistakes_blocked_when_quota_exhausted(db, client, env):
    u = env.make_user('exhausted')
    g = env.plan_grant(u, 'plus')
    env.add_result(u, {'1': 1})
    env.unlock(u)
    g.quota = _used_credits(u, env, g)
    db.session.commit()
    _login(client, u)
    resp = client.get(f'/test/{env.test.id}/all-mistakes')
    assert resp.status_code == 302 and 'quota_exceeded' in resp.headers['Location']
    blocked = _submit(client, env.test.id, {'1': 0})
    assert blocked.status_code == 403 and blocked.get_json()['error'] == 'quota_exceeded'


def test_submit_all_mistakes_rejected_for_basic(client, env):
    u = env.make_user('subbasic')
    env.plan_grant(u, 'basic')
    _login(client, u)
    assert _submit(client, env.test.id, {'1': 0}).status_code == 403
    assert TestResult.query.filter_by(user_id=u.id, test_type='all_mistakes').count() == 0


# ---------- изтекъл абонамент: преглед, оферта, плащане ----------

def _expired_plus(db, env, name):
    u = env.make_user(name)
    g = env.plan_grant(u, 'plus', started=datetime.utcnow() - timedelta(days=20))
    env.add_result(u, {'1': 1, '2': 1}, when=datetime.utcnow() - timedelta(days=15))
    env.unlock(u, when=datetime.utcnow() - timedelta(days=14))
    _expire(db, g, 3)
    return u, g


def test_review_mode_can_view_but_solving_goes_to_offer(db, client, env):
    u, _g = _expired_plus(db, env, 'reviewmode')
    _login(client, u)
    assert client.get(f'/all-mistakes/{env.test.id}/review').status_code == 200
    page = client.get('/all-mistakes').get_data(as_text=True)
    assert 'Subscription ended' in page and 'View answers' in page
    resp = client.get(f'/test/{env.test.id}/all-mistakes')
    assert resp.status_code == 302 and resp.headers['Location'].endswith(f'/all-mistakes/{env.test.id}/unlock')
    assert _submit(client, env.test.id, {'1': 0}).get_json()['error'] == 'purchase_required'


def test_offer_page_uses_config_numbers(db, client, env):
    u, _g = _expired_plus(db, env, 'offerpage')
    _login(client, u)
    html = client.get(f'/all-mistakes/{env.test.id}/unlock').get_data(as_text=True)
    cfg = svc.ALL_MISTAKES
    assert f"{cfg['price']:.2f}" in html and f"{cfg['tests_quota']} solves" in html and f"{cfg['days']} days" in html


def test_offer_not_available_for_active_plan_with_feature(client, env):
    active = env.make_user('offeractive')
    env.plan_grant(active, 'plus')
    _login(client, active)
    resp = client.get(f'/all-mistakes/{env.test.id}/unlock')
    assert resp.status_code == 302 and resp.headers['Location'].endswith('/all-mistakes')


def test_basic_offer_page_and_purchase_opens_without_ten_runs(db, client, env):
    u = env.make_user('basicbuy')
    env.plan_grant(u, 'basic')
    env.add_result(u, {'1': 1})
    _login(client, u)
    assert passes.can_buy(u, env.test.id)
    html = client.get(f'/all-mistakes/{env.test.id}/unlock').get_data(as_text=True)
    assert 'not included in your plan' in html and 'Just view answers' not in html
    assert f"{ALL_MISTAKES['price']:.2f}" in html and '9.99' in html
    passes.grant_pass(u, env.test.id)
    db.session.commit()
    ent = svc.entitlements(u)[env.test.id]
    assert ent['mode'] == 'pass' and svc.is_open(u.id, env.test.id, ent)   # платил е - без 10-те решени
    assert client.get(f'/all-mistakes/{env.test.id}/review').status_code == 200
    page = client.get('/all-mistakes').get_data(as_text=True)
    assert 'View answers' in page and 'Solve' in page and 'left</span>' in page
    resp = _submit(client, env.test.id, {'1': 0})
    assert resp.status_code == 200


def test_checkout_redirects_to_stripe_url(db, client, env, monkeypatch):
    u, _g = _expired_plus(db, env, 'checkoutuser')
    seen = {}

    def fake(user, test_id, success, cancel):
        seen.update(user=user.id, test=test_id, success=success)
        return 'https://stripe.test/pay'
    monkeypatch.setattr(passes, 'create_checkout', fake)
    _login(client, u)
    resp = client.post(f'/all-mistakes/{env.test.id}/checkout')
    assert resp.status_code == 302 and resp.headers['Location'] == 'https://stripe.test/pay'
    assert seen['test'] == env.test.id and '{CHECKOUT_SESSION_ID}' in seen['success']


def test_checkout_denied_when_not_eligible(client, env, monkeypatch):
    u = env.make_user('checkoutdenied')
    env.plan_grant(u, 'plus')   # активен абонамент - не се купува
    monkeypatch.setattr(passes, 'create_checkout', lambda *a: pytest.fail('must not reach Stripe'))
    _login(client, u)
    assert client.post(f'/all-mistakes/{env.test.id}/checkout').status_code == 302


def _paid_session(user, test_id, session_id='cs_test_1'):
    return {'id': session_id, 'payment_intent': 'pi_1', 'payment_status': 'paid',
            'metadata': {'user_id': str(user.id), 'plan_name': 'all_mistakes', 'test_id': str(test_id)}}


def test_stripe_payment_grants_pass_once(db, env, monkeypatch):
    from app.services import stripe as stripe_service
    monkeypatch.setattr(stripe_service, '_get_stripe_fee_and_net', lambda pi: (0.0, 0.0))
    u, _g = _expired_plus(db, env, 'paid')
    ok, _msg = stripe_service._handle_checkout_completed(_paid_session(u, env.test.id))
    assert ok
    p = AllMistakesPass.query.filter_by(user_id=u.id).one()
    assert p.test_id == env.test.id and p.quota == svc.ALL_MISTAKES['tests_quota']
    assert (p.expires_at - p.activated_at).days == svc.ALL_MISTAKES['days']
    pay = Payment.query.filter_by(user_id=u.id).one()
    assert pay.plan == 'all_mistakes' and pay.amount == svc.ALL_MISTAKES['price'] and p.payment_id == pay.id
    stripe_service._handle_checkout_completed(_paid_session(u, env.test.id))     # повторен webhook
    assert AllMistakesPass.query.filter_by(user_id=u.id).count() == 1


def test_paid_pass_allows_solving_with_own_counter(db, client, env):
    u, g = _expired_plus(db, env, 'solvepass')
    passes.grant_pass(u, env.test.id)
    db.session.commit()
    _login(client, u)
    assert client.get(f'/test/{env.test.id}/all-mistakes').status_code == 200
    used_before = _used_credits(u, env, g)
    assert _submit(client, env.test.id, {'1': 0}).status_code == 200
    assert _submit(client, env.test.id, {'2': 0}).status_code == 200
    ent = svc.entitlements(u)[env.test.id]
    assert svc.pass_runs_used(u.id, ent['pass_']) == 2
    assert PlanGrant.query.get(g.id).tests_used == 0                       # квотата на плана не се пипа
    page = client.get('/all-mistakes').get_data(as_text=True)
    assert f"{svc.ALL_MISTAKES['tests_quota'] - 2}/{svc.ALL_MISTAKES['tests_quota']} left" in page
    assert used_before >= 0


def test_pass_blocked_when_its_quota_is_used(db, client, env):
    u, _g = _expired_plus(db, env, 'passfull')
    p = passes.grant_pass(u, env.test.id)
    p.quota = 1
    db.session.commit()
    _login(client, u)
    assert _submit(client, env.test.id, {'1': 0}).status_code == 200
    blocked = _submit(client, env.test.id, {'2': 0})
    assert blocked.status_code == 403 and blocked.get_json()['error'] == 'quota_exceeded'
    resp = client.get(f'/test/{env.test.id}/all-mistakes')
    assert resp.status_code == 302 and resp.headers['Location'].endswith('/all-mistakes')


def test_purchased_page_verifies_session_and_redirects(db, client, env, monkeypatch):
    from app.services import stripe as stripe_service
    u, _g = _expired_plus(db, env, 'purchasedpage')
    monkeypatch.setattr(stripe_service, 'verify_and_grant_checkout_session', lambda sid: (True, 'ok'))
    _login(client, u)
    resp = client.get('/all-mistakes/purchased?session_id=cs_x')
    assert resp.status_code == 302 and resp.headers['Location'].endswith('/all-mistakes')


# ---------- останало ----------

def test_result_review_label_for_all_mistakes(client, env):
    u = env.make_user('revlabel')
    env.plan_grant(u, 'plus')
    r = env.add_result(u, {'1': 1}, test_type='all_mistakes')
    _login(client, u)
    assert 'All Mistakes' in client.get(f'/result/{r.id}').get_data(as_text=True)


def test_page_explains_rules_from_config(client, env):
    u = env.make_user('rulestext')
    env.plan_grant(u, 'plus')
    _login(client, u)
    html = client.get('/all-mistakes').get_data(as_text=True)
    assert f"after {svc.ALL_MISTAKES['unlock_tests']} Test, Mix or Simulator" in html and 'uses 1 test credit' in html


def test_apply_promo_flags_copies_only_for_promo_grant():
    promo = PromoCode(code='X', client_name='c', all_mistakes=True)
    pg, gg = PromoGrant(), GoldGrant()
    svc.apply_promo_flags(pg, promo)
    svc.apply_promo_flags(gg, promo)
    assert pg.all_mistakes is True and not hasattr(gg, 'all_mistakes')


def test_admin_creates_promo_with_flag(client, db, admin_user):
    client.post('/login', data={'email': 'admin@test.bg', 'password': 'Admin123'}, headers=AJAX)
    resp = client.post('/admin/promos/create', data={'client_name': 'ACME', 'all_mistakes': '1'})
    code = resp.get_json()['code']
    assert PromoCode.query.filter_by(code=code).one().all_mistakes is True
    resp = client.post('/admin/promos/create', data={'client_name': 'ACME2', 'all_mistakes': '0'})
    assert PromoCode.query.filter_by(code=resp.get_json()['code']).one().all_mistakes is False
    PromoCode.query.filter(PromoCode.client_name.in_(['ACME', 'ACME2'])).delete(synchronize_session=False)
    db.session.commit()


def test_migration_adds_all_mistakes_columns(tmp_path):
    from flask import Flask
    from flask_sqlalchemy import SQLAlchemy
    from sqlalchemy import inspect, text
    from app.services.promo_schema import migrate_promo_all_mistakes
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{tmp_path}/old.db'
    local_db = SQLAlchemy(app)
    with app.app_context():
        with local_db.engine.connect() as conn:
            conn.execute(text('CREATE TABLE promo_code (id INTEGER PRIMARY KEY)'))
            conn.execute(text('CREATE TABLE promo_grant (id INTEGER PRIMARY KEY)'))
            conn.commit()
        migrate_promo_all_mistakes(app, local_db, inspect(local_db.engine))
        migrate_promo_all_mistakes(app, local_db, inspect(local_db.engine))  # повторно - без грешка
        for table in ('promo_code', 'promo_grant'):
            assert 'all_mistakes' in {c['name'] for c in inspect(local_db.engine).get_columns(table)}


def test_test_page_has_header_and_bottom_check_buttons(client, env):
    u = env.make_user('bottomchk')
    env.plan_grant(u, 'plus')
    _login(client, u)
    html = client.get(f'/test/{env.test.id}').get_data(as_text=True)
    assert html.count('onclick="submitTest()"') == 2
    assert 'id="submitBtn"' in html and 'id="submitBtnBottom"' in html and 'css/test-page.css' in html


def test_exactly_ten_mixed_runs_unlock(client, env):
    """9 решени (Test+Mix+Simulator) - заключено; 10-тото отключва."""
    assert svc.ALL_MISTAKES['unlock_tests'] == 10
    u = env.make_user('tenmixed')
    env.plan_grant(u, 'plus')
    kinds = ['test'] * 4 + ['mix'] * 3 + ['simulator'] * 3
    for kind in kinds[:9]:
        env.add_result(u, {'1': 1}, test_type=kind)
    start = svc.entitlements(u)[env.test.id]['start']
    assert svc.unlock_progress(u.id, env.test.id, start) == (9, 10)
    _login(client, u)
    assert client.get(f'/test/{env.test.id}/all-mistakes').status_code == 302
    env.add_result(u, {'1': 1}, test_type=kinds[9])
    assert svc.is_unlocked(u.id, env.test.id, start)
    assert client.get(f'/test/{env.test.id}/all-mistakes').status_code == 200


def test_shared_reading_prefs_panel_still_on_test_and_result_pages(client, db, basic_user):
    """Панелът за настройки е извлечен в споделен partial - трябва да е на тест страницата."""
    from app.models.test import Test as T
    t = T.query.first()
    client.post('/login', data={'email': basic_user.email, 'password': 'Test123'}, headers=AJAX)
    html = client.get(f'/test/{t.id}').get_data(as_text=True)
    assert 'id="prefsPanel"' in html and 'Reset to Default' in html


def test_review_no_check_icon_has_shuffle_and_exclude(client, env):
    u = env.make_user('revtools')
    env.plan_grant(u, 'plus')
    env.add_result(u, {'1': 1, '2': 0, '3': 1})
    env.unlock(u)
    _login(client, u)
    html = client.get(f'/all-mistakes/{env.test.id}/review').get_data(as_text=True)
    assert 'fa-circle-check' not in html
    assert 'id="amShuffle"' in html and html.count('js-am-exclude') == 2


def test_exclude_question_removes_it_from_solving_only(client, env):
    u = env.make_user('exclsolve')
    env.plan_grant(u, 'plus')
    env.add_result(u, {'1': 1, '2': 0, '3': 1})
    env.unlock(u)
    _login(client, u)
    url = f'/all-mistakes/{env.test.id}/exclude'
    r = client.post(url, json={'question_id': '1', 'excluded': True})
    assert r.get_json() == {'success': True, 'included': 1, 'total': 2}
    start = client.get(f'/test/{env.test.id}/all-mistakes').get_data(as_text=True)
    assert 'totalQuestions: 1' in start
    review = client.get(f'/all-mistakes/{env.test.id}/review').get_data(as_text=True)
    assert review.count('am-q--off') >= 1 and 'qbox_1' in review
    r = client.post(url, json={'question_id': '1', 'excluded': False})
    assert r.get_json()['included'] == 2


def test_exclude_denied_for_basic(client, env):
    u = env.make_user('exclbasic')
    env.plan_grant(u, 'basic')
    _login(client, u)
    r = client.post(f'/all-mistakes/{env.test.id}/exclude', json={'question_id': '1', 'excluded': True})
    assert r.status_code in (302, 403)
