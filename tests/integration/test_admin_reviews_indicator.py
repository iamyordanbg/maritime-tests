"""
tests/integration/test_admin_reviews_indicator.py
=================================================
Админ меню: "Reviews" свети в жълто, докато има отзиви в pending; изчиства се при 0.
"""

from app.models.review import Review

AJAX = {'X-Requested-With': 'XMLHttpRequest'}


def _admin(client):
    client.post('/login', data={'email': 'admin@test.bg', 'password': 'Admin123'}, headers=AJAX)


def _review(db, user, status='pending'):
    r = Review(user_id=user.id, stars=5, text='x', status=status, visibility='anonymous',
               display_name='Anonymous Sailor')
    db.session.add(r)
    db.session.commit()
    return r


def _cleanup(db, *reviews):
    for r in reviews:
        db.session.delete(r)
    db.session.commit()


def test_indicator_shown_when_pending(client, db, admin_user, free_user):
    r = _review(db, free_user)
    _admin(client)
    html = client.get('/admin/reviews').get_data(as_text=True)
    assert 'admin-sl--attention' in html and '1 pending' in html
    _cleanup(db, r)


def test_no_indicator_without_pending(client, db, admin_user, free_user):
    r = _review(db, free_user, status='approved')
    _admin(client)
    html = client.get('/admin/reviews').get_data(as_text=True)
    assert 'admin-sl--attention' not in html  # класът е само в външния CSS, не върху линка
    assert 'pending</' not in html
    _cleanup(db, r)


def test_actions_return_remaining_pending_count(client, db, admin_user, free_user):
    r1, r2 = _review(db, free_user), _review(db, free_user)
    _admin(client)
    assert client.post(f'/admin/reviews/{r1.id}/approve').get_json() == {'success': True, 'pending': 1}
    assert client.post(f'/admin/reviews/{r2.id}/reject').get_json() == {'success': True, 'pending': 0}
    _cleanup(db, r1, r2)


def test_delete_returns_pending_count(client, db, admin_user, free_user):
    r = _review(db, free_user)
    _admin(client)
    data = client.post(f'/admin/reviews/{r.id}/delete').get_json()
    assert data == {'success': True, 'pending': 0}


def test_regular_user_gets_no_pending_query_indicator(client, db, free_user):
    r = _review(db, free_user)
    client.post('/login', data={'email': 'free@test.bg', 'password': 'Test123'}, headers=AJAX)
    html = client.get('/library').get_data(as_text=True)
    assert 'admin-sl--attention' not in html
    _cleanup(db, r)
