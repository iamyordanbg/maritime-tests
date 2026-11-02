"""
tests/integration/test_smoke_all_pages.py
=========================================
Smoke тест: отваря ВСЯКА GET страница/API (потребителски и админ) със смесени реални данни
(Basic, Plus, Gold, Custom промо, All Mistakes, изтекли планове, резултати от всички видове,
тикети, сигнали, отзиви) и пада при всяка 5xx грешка. Ловиш точно грешки като 500 на
/admin/promos, които обикновените тестове с по един ред данни не виждат.
"""
import re
import json
from datetime import datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

from app.models.user import User
from app.models.test import Test
from app.models.result import TestResult
from app.models.payment import Payment
from app.models.plan_grant import PlanGrant
from app.models.gold_grant import GoldGrant
from app.models.promo_grant import PromoGrant
from app.models.promo import PromoCode
from app.models.all_mistakes_pass import AllMistakesPass
from app.models.ticket import Ticket, TicketMessage
from app.models.signal import Signal
from app.models.review import Review

AJAX = {'X-Requested-With': 'XMLHttpRequest'}
PASSWORD = 'Test123'

# Страници, които не са за обхождане: изходят/пренасочват навън, викат Stripe или искат файл/токен.
SKIP_ENDPOINTS = {
    'static', 'auth.logout', 'auth.google_login', 'auth.google_callback', 'billing.checkout',
    'feed.feed_image', 'test_taking.serve_qimage', 'auth.verify_email', 'reviews.review_decline_page',
    'admin.admin_snapshots',
}
MODELS_TO_CLEAN = (AllMistakesPass, GoldGrant, PromoGrant, PlanGrant, Payment, PromoCode, TestResult,
                   TicketMessage, Ticket, Signal, Review)


def _q(i):
    return {'id': i, 'question': f'Question {i}?',
            'options': [{'text': 'right', 'isCorrect': True}, {'text': 'wrong', 'isCorrect': False}]}


@pytest.fixture
def world(db):
    """Смесен свят: потребители в различни състояния + данни, които админ страниците показват."""
    now = datetime.utcnow()
    tests = [Test(title=f'Smoke {i}', level='Operational Level', category='deck', is_demo=(i == 0),
                  questions_json=json.dumps([_q(1), _q(2), _q(3)])) for i in range(3)]
    db.session.add_all(tests)
    users = {}
    for key in ('admin', 'free', 'basic', 'plus', 'gold', 'gold_old', 'promo', 'ampass', 'expired'):
        u = User(name=f'Smoke {key}', email=f'smoke_{key}@t.bg', password=generate_password_hash(PASSWORD),
                 plan='free' if key in ('free', 'ampass') else ('plus' if key == 'plus' else 'basic'),
                 is_active=key != 'free', is_admin=key == 'admin', email_verified=True)
        db.session.add(u)
        users[key] = u
    db.session.commit()
    t0, t1, t2 = tests

    def pay(u, plan, amount, days_ago=0):
        p = Payment(user_id=u.id, plan=plan, amount=amount, paid_at=now - timedelta(days=days_ago),
                    stripe_session_id=f'cs_{plan}_{u.id}_{days_ago}', stripe_payment_intent=f'pi_{plan}_{u.id}_{days_ago}')
        db.session.add(p)
        db.session.flush()
        return p

    pb = pay(users['basic'], 'basic', 5)
    db.session.add(PlanGrant(user_id=users['basic'].id, plan='basic', quota=15, activated_at=now,
                             expires_at=now + timedelta(days=1), payment_id=pb.id, library_test_id=t1.id))
    pp = pay(users['plus'], 'plus', 9)
    db.session.add(PlanGrant(user_id=users['plus'].id, plan='plus', quota=50, activated_at=now,
                             expires_at=now + timedelta(days=1), payment_id=pp.id, library_test_id=t1.id))
    pe = pay(users['expired'], 'plus', 9, days_ago=60)
    db.session.add(PlanGrant(user_id=users['expired'].id, plan='plus', quota=50, activated_at=now - timedelta(days=60),
                             expires_at=now - timedelta(days=30), payment_id=pe.id, library_test_id=t1.id))
    pay(users['gold'], 'gold', 299.99)
    for i in range(3):
        db.session.add(PromoCode(code=f'SMOKEG{i}', client_name='Smoke gold', access_type='gold', price=0,
                                 expires_at=now + timedelta(days=2), created_by_user_id=users['gold'].id,
                                 stripe_payment_intent=f'pi_gold_{users["gold"].id}_0',
                                 is_used=(i == 0), used_by=users['gold_old'].email if i == 0 else ''))
    db.session.add(GoldGrant(user_id=users['gold_old'].id, department='deck', level='Operational Level',
                             test_ids=json.dumps([t1.id, t2.id]), quota=15, tests_used=3, activated_at=now,
                             expires_at=now + timedelta(days=1), promo_code='SMOKEG0'))
    db.session.add(PromoCode(code='SMOKECU', client_name='Custom', access_type='Custom', is_custom=True,
                             all_mistakes=True, used_by=users['promo'].email, is_used=True, usage_limit_type='multiple',
                             expires_at=now + timedelta(days=5)))
    db.session.add(PromoGrant(user_id=users['promo'].id, department='deck', level='Operational Level',
                              test_ids=json.dumps([t1.id]), quota=50, activated_at=now,
                              expires_at=now + timedelta(days=5), promo_code='SMOKECU', all_mistakes=True))
    pa = pay(users['ampass'], 'all_mistakes', 9.99)
    db.session.add(AllMistakesPass(user_id=users['ampass'].id, test_id=t1.id, quota=100, activated_at=now,
                                   expires_at=now + timedelta(days=30), payment_id=pa.id))

    result_ids = []
    for key in ('basic', 'plus', 'gold_old', 'promo', 'ampass', 'expired'):
        for k, ttype in enumerate(('test', 'mix', 'mistakes', 'simulator', 'all_mistakes', 'test', 'mix')):
            r = TestResult(user_id=users[key].id, test_id=t1.id, score=1, total=3, percent=33, passed=False,
                           answers_json=json.dumps({'1': 1, '2': 0, '3': 1}), test_type=ttype, duration=5,
                           question_ids_json='[1,2,3]', taken_at=now - timedelta(minutes=30 - k))
            db.session.add(r)
            db.session.flush()
            result_ids.append(r.id)
    tk = Ticket(user_id=users['basic'].id, subject='Help', type='question')
    db.session.add(tk)
    db.session.flush()
    db.session.add(TicketMessage(ticket_id=tk.id, sender='user', body='hello'))
    db.session.add(TicketMessage(ticket_id=tk.id, sender='admin', body='reply'))
    db.session.add(Signal(user_id=users['basic'].id, user_name='b', user_email='b@t.bg', type='bug', message='x',
                          reply='ok', replied_at=now))
    db.session.add(Review(user_id=users['plus'].id, stars=5, text='great', status='pending'))
    db.session.add(Review(user_id=users['basic'].id, stars=4, text='fine', status='approved', admin_reply='thx'))
    db.session.commit()

    yield {'users': users, 'tests': tests, 'result_id': result_ids[0], 'ticket_id': tk.id}

    db.session.rollback()
    for model in MODELS_TO_CLEAN:
        model.query.delete()
    for t in tests:
        Test.query.filter_by(id=t.id).delete()
    User.query.filter(User.email.like('smoke_%@t.bg')).delete(synchronize_session=False)
    db.session.commit()


def _fill(rule, world):
    """Стойности за параметрите на URL-а (само от засетените данни)."""
    args = {}
    for name in rule.arguments:
        args[name] = {
            'test_id': world['tests'][1].id, 'user_id': world['users']['plus'].id, 'result_id': world['result_id'],
            'ticket_id': world['ticket_id'], 'post_id': 1, 'code': 'SMOKEG1', 'plan_name': 'plus', 'token': 'x',
            'metric': 'users', 'filename': 'x.png',
        }.get(name, 1)
    return args


def _login(client, user):
    client.get('/logout')
    resp = client.post('/login', data={'email': user.email, 'password': PASSWORD}, headers=AJAX)
    assert resp.status_code in (200, 302), f'login failed for {user.email}: {resp.status_code}'


_INLINE_HANDLER = re.compile(r'<[a-zA-Z][^>]*\son(?:click|input|change|keydown|keyup|submit|focus|blur|mouseover|mouseout|mousedown|load|error)\s*=', re.S)


def test_every_page_renders_without_server_error(app, client, world):
    rules = [r for r in app.url_map.iter_rules() if 'GET' in r.methods and r.endpoint not in SKIP_ENDPOINTS]
    failures, visited, codes = [], 0, {}
    for key, user in world['users'].items():
        _login(client, user)
        for rule in rules:
            try:
                url = rule.build(_fill(rule, world))[1] if rule.arguments else rule.rule
            except Exception:       # rule.build може да откаже при странни конвертори - не е грешка на страницата
                continue
            resp = client.get(url)
            visited += 1
            codes[(key == 'admin', resp.status_code)] = codes.get((key == 'admin', resp.status_code), 0) + 1
            if resp.status_code >= 500:
                failures.append(f'{key:9} {resp.status_code} {url}')
            elif resp.status_code == 200 and 'text/html' in (resp.content_type or ''):
                body = resp.get_data(as_text=True)
                # CLAUDE.md rule 1: no inline JS handlers; declarative data-on-* needs ui-actions.js
                if _INLINE_HANDLER.search(body):
                    failures.append(f'{key:9} inline on*= handler in {url}: ' + _INLINE_HANDLER.search(body).group(0)[-120:])
                if 'data-on-' in body and 'js/ui-actions.js' not in body:
                    failures.append(f'{key:9} data-on-* without ui-actions.js in {url}')
    print('STATUS', sorted(codes.items()))
    assert visited > 500, f'too few pages visited: {visited}'
    assert not failures, 'Server errors:\n' + '\n'.join(failures)
