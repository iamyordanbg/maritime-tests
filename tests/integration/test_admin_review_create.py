"""
tests/integration/test_admin_review_create.py
=============================================
Админ: ръчно добавяне на отзив (веднага одобрен, излиза на ландинга) и промяна на датата.
"""
from datetime import datetime, timedelta

import pytest

from app.models.review import Review

AJAX = {'X-Requested-With': 'XMLHttpRequest'}
PAST = (datetime.utcnow().date() - timedelta(days=40)).isoformat()


@pytest.fixture(autouse=True)
def _clean_reviews(db):
    Review.query.delete()
    db.session.commit()
    yield
    Review.query.delete()
    db.session.commit()


def _admin(client):
    client.post('/login', data={'email': 'admin@test.bg', 'password': 'Admin123'}, headers=AJAX)


def _payload(**kw):
    base = {'visibility': 'account', 'name': 'Ivan Petrov', 'role': 'Deck cadet', 'stars': '5',
            'date': PAST, 'text': 'Added by admin', 'reply': ''}
    base.update(kw)
    return base


def _public(client):
    return next((i for i in client.get('/api/reviews/public').get_json() if i['text'] == 'Added by admin'), None)


def test_create_named_review_is_approved_and_public(client, db, admin_user):
    _admin(client)
    res = client.post('/admin/reviews/create', json=_payload(reply='Thanks!'))
    assert res.get_json() == {'success': True}
    item = _public(client)
    assert item['name'] == 'Ivan Petrov' and item['initials'] == 'IP' and item['role'] == 'Deck cadet'
    assert item['date'] == PAST and item['reply'] == 'Thanks!' and item['stars'] == 5


def test_create_anonymous_review_has_generated_name(client, db, admin_user):
    _admin(client)
    client.post('/admin/reviews/create', json=_payload(visibility='anonymous', name='Secret'))
    item = _public(client)
    assert 'Secret' not in item['name'] and item['initials'] == '' and item['avatar']


@pytest.mark.parametrize('bad', [
    {'text': '  '}, {'stars': '0'}, {'stars': 'x'}, {'name': ''},
    {'date': 'nope'}, {'date': (datetime.utcnow().date() + timedelta(days=2)).isoformat()},
])
def test_create_rejects_invalid(client, db, admin_user, bad):
    _admin(client)
    res = client.post('/admin/reviews/create', json=_payload(**bad))
    assert res.status_code == 400 and not res.get_json()['success']
    assert Review.query.count() == 0


def test_create_requires_admin(client, db, free_user):
    client.post('/login', data={'email': 'free@test.bg', 'password': 'Test123'}, headers=AJAX)
    res = client.post('/admin/reviews/create', json=_payload())
    assert res.status_code in (301, 302, 401, 403)
    assert Review.query.count() == 0


def test_change_date_keeps_time_and_validates(client, db, admin_user, free_user):
    r = Review(user_id=free_user.id, stars=5, text='x', status='approved', visibility='anonymous',
               created_at=datetime(2026, 10, 5, 14, 30))
    db.session.add(r)
    db.session.commit()
    _admin(client)
    res = client.post(f'/admin/reviews/{r.id}/date', json={'date': '2026-07-01'})
    assert res.get_json() == {'success': True, 'date': '2026-07-01'}
    assert db.session.get(Review, r.id).created_at == datetime(2026, 7, 1, 14, 30)
    assert client.post(f'/admin/reviews/{r.id}/date', json={'date': '2999-01-01'}).status_code == 400
    assert client.post(f'/admin/reviews/{r.id}/date', json={'date': 'bad'}).status_code == 400


def test_change_date_requires_admin(client, db, free_user):
    r = Review(user_id=free_user.id, stars=5, text='x', status='approved', visibility='anonymous')
    db.session.add(r)
    db.session.commit()
    client.post('/login', data={'email': 'free@test.bg', 'password': 'Test123'}, headers=AJAX)
    res = client.post(f'/admin/reviews/{r.id}/date', json={'date': '2026-07-01'})
    assert res.status_code in (301, 302, 401, 403)


def test_admin_page_has_add_form_and_date_inputs(client, db, admin_user, free_user):
    r = Review(user_id=free_user.id, stars=5, text='x', status='approved', visibility='anonymous')
    db.session.add(r)
    db.session.commit()
    _admin(client)
    html = client.get('/admin/reviews?status=approved').get_data(as_text=True)
    assert 'id="revAddForm"' in html and 'rev-date-input' in html and 'admin-reviews.css' in html
