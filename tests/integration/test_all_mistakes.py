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

AJAX = {'X-Requested-With': 'XMLHttpRequest'}
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

    e.make_user, e.add_result, e.plan_grant = make_user, add_result, plan_grant
    yield e
    db.session.rollback()
    for model in (TestResult, PlanGrant, GoldGrant, PromoGrant):
        model.query.filter(model.user_id.in_([u.id for u in created])).delete(synchronize_session=False)
    for u in created:
        db.session.delete(u)
    db.session.delete(test)
    db.session.commit()


def _login(client, user):
    client.post('/login', data={'email': user.email, 'password': 'Test123'}, headers=AJAX)


# ---------- достъп ----------

def test_plus_has_feature_basic_does_not(env):
    plus, basic = env.make_user('plus1'), env.make_user('basic1')
    env.plan_grant(plus, 'plus')
    env.plan_grant(basic, 'basic')
    assert env.test.id in svc.entitlements(plus)
    assert svc.entitlements(basic) == {}


def test_gold_grant_has_feature(db, env):
    u = env.make_user('gold1')
    now = datetime.utcnow()
    db.session.add(GoldGrant(user_id=u.id, test_ids=json.dumps([env.test.id]), quota=150, activated_at=now,
                             expires_at=now + timedelta(days=5), grace_until=now + timedelta(days=65)))
    db.session.commit()
    assert env.test.id in svc.entitlements(u)


def test_promo_grant_needs_flag(db, env):
    with_flag, without = env.make_user('promoyes'), env.make_user('promono')
    now = datetime.utcnow()
    for u, flag in ((with_flag, True), (without, False)):
        db.session.add(PromoGrant(user_id=u.id, test_ids=json.dumps([env.test.id]), quota=50, activated_at=now,
                                  expires_at=now + timedelta(days=5), all_mistakes=flag))
    db.session.commit()
    assert env.test.id in svc.entitlements(with_flag)
    assert svc.entitlements(without) == {}


def test_expired_plus_has_no_access_but_gold_grace_does(db, env):
    plus, gold = env.make_user('plusexp'), env.make_user('goldgrace')
    env.plan_grant(plus, 'plus', days=-1)
    now = datetime.utcnow()
    db.session.add(GoldGrant(user_id=gold.id, test_ids=json.dumps([env.test.id]), quota=150,
                             activated_at=now - timedelta(days=40), expires_at=now - timedelta(days=10),
                             grace_until=now + timedelta(days=50)))
    db.session.commit()
    assert svc.entitlements(plus) == {}
    ent = svc.entitlements(gold)[env.test.id]
    assert ent['in_grace'] is True


def test_gold_after_grace_has_no_access(db, env):
    u = env.make_user('goldgone')
    now = datetime.utcnow()
    db.session.add(GoldGrant(user_id=u.id, test_ids=json.dumps([env.test.id]), quota=150,
                             activated_at=now - timedelta(days=100), expires_at=now - timedelta(days=80),
                             grace_until=now - timedelta(days=20)))
    db.session.commit()
    assert svc.entitlements(u) == {}


# ---------- грешки ----------

def test_mistakes_union_across_all_test_types_and_new_ones_added(env):
    u = env.make_user('union')
    env.plan_grant(u, 'plus')
    env.add_result(u, {'1': 1, '2': 0}, test_type='test')           # грешка: 1
    ent = svc.entitlements(u)[env.test.id]
    assert svc.wrong_question_ids(u.id, env.test, ent['start']) == {'1'}
    env.add_result(u, {'1': 0, '3': 1}, test_type='mix')            # 1 вече е верен, но остава; нова: 3
    env.add_result(u, {'2': 1}, test_type='simulator')              # нова: 2
    assert svc.wrong_question_ids(u.id, env.test, ent['start']) == {'1', '2', '3'}


def test_results_before_activation_ignored(env):
    u = env.make_user('before')
    env.plan_grant(u, 'plus', started=datetime.utcnow() - timedelta(days=1))
    env.add_result(u, {'1': 1}, when=datetime.utcnow() - timedelta(days=5))
    ent = svc.entitlements(u)[env.test.id]
    assert svc.wrong_question_ids(u.id, env.test, ent['start']) == set()


def test_other_users_results_not_counted(env):
    a, b = env.make_user('usera'), env.make_user('userb')
    env.plan_grant(a, 'plus')
    env.add_result(b, {'1': 1})
    ent = svc.entitlements(a)[env.test.id]
    assert svc.wrong_question_ids(a.id, env.test, ent['start']) == set()


# ---------- страница и старт ----------

def test_page_locked_for_basic(client, env):
    u = env.make_user('lockedb')
    env.plan_grant(u, 'basic')
    _login(client, u)
    html = client.get('/all-mistakes').get_data(as_text=True)
    assert 'not active on your account' in html and 'Plus and Gold' in html


def test_page_lists_test_with_count_for_plus(client, env):
    u = env.make_user('listplus')
    env.plan_grant(u, 'plus')
    env.add_result(u, {'1': 1, '2': 1, '3': 0})
    _login(client, u)
    html = client.get('/all-mistakes').get_data(as_text=True)
    assert 'AM Test' in html and '>2</span>' in html and 'Start' in html


def test_page_requires_login(client):
    assert client.get('/all-mistakes').status_code in (302, 401)


def test_start_renders_only_wrong_questions(client, env):
    u = env.make_user('startplus')
    env.plan_grant(u, 'plus')
    env.add_result(u, {'1': 1, '2': 0, '3': 1})
    _login(client, u)
    resp = client.get(f'/test/{env.test.id}/all-mistakes')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "testType: 'all_mistakes'" in html and 'ALL MISTAKES' in html and 'totalQuestions: 2' in html


def test_start_without_mistakes_redirects_to_page(client, env):
    u = env.make_user('nomist')
    env.plan_grant(u, 'plus')
    _login(client, u)
    resp = client.get(f'/test/{env.test.id}/all-mistakes')
    assert resp.status_code == 302 and '/all-mistakes' in resp.headers['Location']


def test_start_denied_for_basic(client, env):
    u = env.make_user('startbasic')
    env.plan_grant(u, 'basic')
    env.add_result(u, {'1': 1})
    _login(client, u)
    resp = client.get(f'/test/{env.test.id}/all-mistakes')
    assert resp.status_code == 302 and resp.headers['Location'].endswith('/all-mistakes')


# ---------- submit ----------

def _submit(client, test_id, answers):
    return client.post(f'/test/{test_id}/submit', json={'answers': answers, 'test_type': 'all_mistakes',
                                                        'question_ids': [int(k) for k in answers], 'duration': 5})


def test_submit_all_mistakes_saves_result_for_plus(client, env):
    u = env.make_user('subplus')
    g = env.plan_grant(u, 'plus')
    env.add_result(u, {'1': 1})
    _login(client, u)
    data = _submit(client, env.test.id, {'1': 0}).get_json()
    assert data['score'] == 1 and data['percent'] == 100.0
    assert TestResult.query.filter_by(user_id=u.id, test_type='all_mistakes').count() == 1
    assert PlanGrant.query.get(g.id).tests_used == 0  # All Mistakes е безплатно - не харчи квота


def test_submit_all_mistakes_rejected_for_basic(client, env):
    u = env.make_user('subbasic')
    env.plan_grant(u, 'basic')
    _login(client, u)
    assert _submit(client, env.test.id, {'1': 0}).status_code == 403
    assert TestResult.query.filter_by(user_id=u.id, test_type='all_mistakes').count() == 0


def test_submit_in_grace_does_not_consume_quota(db, client, env):
    u = env.make_user('subgrace')
    now = datetime.utcnow()
    g = GoldGrant(user_id=u.id, test_ids=json.dumps([env.test.id]), quota=150, tests_used=7,
                  activated_at=now - timedelta(days=40), expires_at=now - timedelta(days=10),
                  grace_until=now + timedelta(days=50))
    db.session.add(g)
    db.session.commit()
    _login(client, u)
    assert _submit(client, env.test.id, {'1': 0}).status_code == 200
    assert GoldGrant.query.get(g.id).tests_used == 7


def test_result_review_label_for_all_mistakes(client, env):
    u = env.make_user('revlabel')
    env.plan_grant(u, 'plus')
    r = env.add_result(u, {'1': 1}, test_type='all_mistakes')
    _login(client, u)
    assert 'All Mistakes' in client.get(f'/result/{r.id}').get_data(as_text=True)


def test_all_mistakes_works_with_exhausted_quota(db, client, env):
    u = env.make_user('exhausted')
    g = env.plan_grant(u, 'plus')
    g.tests_used = g.quota
    db.session.commit()
    env.add_result(u, {'1': 1})
    _login(client, u)
    assert client.get(f'/test/{env.test.id}/all-mistakes').status_code == 200
    assert _submit(client, env.test.id, {'1': 0}).status_code == 200
    assert PlanGrant.query.get(g.id).tests_used == g.quota


# ---------- promo флаг ----------

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
