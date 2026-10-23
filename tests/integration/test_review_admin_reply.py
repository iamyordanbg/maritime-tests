"""
tests/integration/test_review_admin_reply.py
============================================
Админът може да остави един публичен отговор (MARADTEST) само под одобрен отзив;
отговорът излиза в /api/reviews/public.
"""
import pytest

from app.models.review import Review
from app.services.reviews import set_admin_reply, ReplyError, REPLY_MAX_LENGTH

AJAX = {'X-Requested-With': 'XMLHttpRequest'}


def _admin(client):
    client.post('/login', data={'email': 'admin@test.bg', 'password': 'Admin123'}, headers=AJAX)


def _review(db, user, status='approved'):
    r = Review(user_id=user.id, stars=5, text='Reply target', status=status,
               visibility='anonymous', display_name='Anonymous Sailor')
    db.session.add(r)
    db.session.commit()
    return r


def _public_item(client):
    return next(i for i in client.get('/api/reviews/public').get_json() if i['text'] == 'Reply target')


def test_reply_saved_and_public(client, db, admin_user, free_user):
    r = _review(db, free_user)
    _admin(client)
    res = client.post(f'/admin/reviews/{r.id}/reply', json={'reply': '  Thank you!  '})
    assert res.get_json() == {'success': True, 'reply': 'Thank you!', 'image': ''}
    item = _public_item(client)
    assert item['reply'] == 'Thank you!' and 'reply_date' not in item


def test_reply_cleared_with_empty_text(client, db, admin_user, free_user):
    r = _review(db, free_user)
    _admin(client)
    client.post(f'/admin/reviews/{r.id}/reply', json={'reply': 'Hi'})
    client.post(f'/admin/reviews/{r.id}/reply', json={'reply': ''})
    item = _public_item(client)
    assert item['reply'] == ''


def test_reply_rejected_for_unapproved(client, db, admin_user, free_user):
    r = _review(db, free_user, status='pending')
    _admin(client)
    res = client.post(f'/admin/reviews/{r.id}/reply', json={'reply': 'Hi'})
    assert res.status_code == 400 and not res.get_json()['success']
    assert Review.query.get(r.id).admin_reply is None


def test_reply_too_long_rejected(client, db, admin_user, free_user):
    r = _review(db, free_user)
    _admin(client)
    res = client.post(f'/admin/reviews/{r.id}/reply', json={'reply': 'x' * (REPLY_MAX_LENGTH + 1)})
    assert res.status_code == 400


def test_reply_requires_admin(client, db, free_user):
    r = _review(db, free_user)
    client.post('/login', data={'email': 'free@test.bg', 'password': 'Test123'}, headers=AJAX)
    res = client.post(f'/admin/reviews/{r.id}/reply', json={'reply': 'Hi'})
    assert res.status_code != 200 or not res.is_json
    assert Review.query.get(r.id).admin_reply is None


def test_admin_page_shows_reply_box_only_for_approved(client, db, admin_user, free_user):
    r = _review(db, free_user)
    _admin(client)
    assert 'Reply as MARADTEST' in client.get('/admin/reviews?status=approved').get_data(as_text=True)
    r.status = 'pending'
    db.session.commit()
    assert 'Reply as MARADTEST' not in client.get('/admin/reviews?status=pending').get_data(as_text=True)


def test_service_unapproved_raises(db, free_user):
    r = _review(db, free_user, status='rejected')
    with pytest.raises(ReplyError):
        set_admin_reply(r, 'Hi')
