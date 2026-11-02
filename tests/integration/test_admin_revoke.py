"""
tests/integration/test_admin_revoke.py
======================================
Админ 'Delete' на план/код = меко отнемане: достъпът спира, но записът остава в
историята на клиента (Billing), скрит само от админ списъка.
"""
from datetime import datetime, timedelta

import pytest

from app.models.payment import Payment
from app.models.plan_grant import PlanGrant
from app.models.promo import PromoCode
from app.models.gold_grant import GoldGrant
from app.services.usage import build_billing_data

AJAX = {'X-Requested-With': 'XMLHttpRequest'}


@pytest.fixture(autouse=True)
def _cleanup(db):
    """Фикстурите не чистят grant/payment/promo редове - не ги оставяме за други тестове (повторно ползвани user id)."""
    yield
    db.session.rollback()
    for model in (GoldGrant, PlanGrant, Payment, PromoCode):
        model.query.delete()
    db.session.commit()


def _admin(client, admin_user):
    client.post('/login', data={'email': admin_user.email, 'password': 'Admin123'}, headers=AJAX)


def test_admin_delete_payment_keeps_it_in_user_billing(client, db, admin_user, basic_user):
    now = datetime.utcnow()
    pay = Payment(user_id=basic_user.id, plan='plus', amount=9.0, paid_at=now)
    db.session.add(pay)
    db.session.flush()
    db.session.add(PlanGrant(user_id=basic_user.id, plan='plus', quota=15, activated_at=now,
                             expires_at=now + timedelta(days=1), payment_id=pay.id))
    db.session.commit()
    pid = pay.id
    _admin(client, admin_user)

    assert client.post(f'/admin/payments/{pid}/delete').get_json()['success']

    db.session.expire_all()
    pay = Payment.query.get(pid)
    assert pay is not None and pay.revoked_at is not None
    grant = PlanGrant.query.filter_by(payment_id=pid).first()
    assert grant is not None and grant.expires_at <= datetime.utcnow()
    entries = build_billing_data(basic_user)[0]
    row = [e for e in entries if e['id'] == pid]
    assert row and row[0]['is_active'] is False


def test_admin_delete_promo_keeps_grant_and_hides_from_admin_list(client, db, admin_user, basic_user):
    now = datetime.utcnow()
    promo = PromoCode(code='GOLDREV1', is_used=True, used_by=basic_user.email, plan='gold')
    db.session.add(promo)
    db.session.add(GoldGrant(user_id=basic_user.id, test_ids='[1]', quota=15, activated_at=now,
                             expires_at=now + timedelta(days=1), promo_code='GOLDREV1'))
    db.session.commit()
    pid = promo.id
    _admin(client, admin_user)

    assert client.post(f'/admin/promos/{pid}/delete').get_json()['success']

    db.session.expire_all()
    promo = PromoCode.query.get(pid)
    assert promo is not None and promo.revoked_at is not None and promo.is_active is False
    g = GoldGrant.query.filter_by(promo_code='GOLDREV1').first()
    assert g is not None and g.expires_at <= datetime.utcnow()
    assert 'GOLDREV1' not in client.get('/admin/promos').get_data(as_text=True)


def test_revoked_standby_code_cannot_be_activated(client, db, admin_user):
    promo = PromoCode(code='STANDBY1', is_used=False, plan='gold',
                      expires_at=datetime.utcnow() + timedelta(days=5))
    db.session.add(promo)
    db.session.commit()
    _admin(client, admin_user)
    assert client.post('/admin/promos/bulk-delete', json={'ids': [promo.id]}).get_json()['deleted'] == 1
    db.session.expire_all()
    p = PromoCode.query.get(promo.id)
    assert p.is_active is False and p.expires_at <= datetime.utcnow()


def test_revoked_at_migration_adds_column(app, db):
    from sqlalchemy import inspect
    cols = {c['name'] for c in inspect(db.engine).get_columns('payment')}
    assert 'revoked_at' in cols


def test_admin_promos_shows_gold_payer_email_before_activation(client, db, admin_user, basic_user):
    now = datetime.utcnow()
    pay = Payment(user_id=basic_user.id, plan='gold', amount=99.0, paid_at=now, stripe_payment_intent='pi_test_holder')
    db.session.add(pay)
    db.session.add(PromoCode(code='BGHOLDER1', plan='gold', client_name='Some Nick', is_used=False,
                             stripe_payment_intent='pi_test_holder', expires_at=now + timedelta(days=2)))
    db.session.commit()
    _admin(client, admin_user)
    html = client.get('/admin/promos').get_data(as_text=True)
    assert 'BGHOLDER1' in html and basic_user.email in html
    assert client.get('/admin/promos?q=' + basic_user.email).get_data(as_text=True).count('BGHOLDER1') >= 1
