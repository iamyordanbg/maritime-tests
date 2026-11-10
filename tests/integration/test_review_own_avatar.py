"""
tests/integration/test_review_own_avatar.py
===========================================
A review published under the account name shows the author's own profile photo (the one uploaded in Settings),
not only the Google photo; it follows later changes; anonymous reviews never show it.
"""
import pytest

from app.models.review import Review

AJAX = {'X-Requested-With': 'XMLHttpRequest'}


@pytest.fixture(autouse=True)
def _clean_reviews(db):
    Review.query.delete()
    db.session.commit()
    yield
    Review.query.delete()
    db.session.commit()


def _item(client):
    return next(i for i in client.get('/api/reviews/public').get_json() if i['text'] == 'Own photo?')


def _review(client, db, user, visibility):
    client.post('/login', data={'email': user.email, 'password': 'Test123'}, headers=AJAX)
    assert client.post('/api/review/submit', data={'stars': 5, 'text': 'Own photo?', 'visibility': visibility}).get_json()['success']
    Review.query.filter_by(user_id=user.id).one().status = 'approved'
    db.session.commit()


def test_account_review_shows_own_uploaded_photo(client, db, basic_user):
    basic_user.firstname, basic_user.lastname = 'Ivan', 'Petrov'
    basic_user.google_picture_url = None
    basic_user.avatar_data, basic_user.avatar_version = b'\xff\xd8jpeg', 3
    db.session.commit()
    _review(client, db, basic_user, 'account')
    item = _item(client)
    assert item['picture'] == f'/feed/avatar/{basic_user.id}?v=3'
    assert item['initials'] == '' and item['avatar'] is None
    assert client.get(item['picture']).status_code == 200


def test_photo_uploaded_after_the_review_is_used(client, db, basic_user):
    basic_user.firstname, basic_user.lastname, basic_user.google_picture_url = 'Ivan', 'Petrov', None
    db.session.commit()
    _review(client, db, basic_user, 'account')
    assert _item(client)['initials'] == 'IP'
    basic_user.avatar_data, basic_user.avatar_version = b'\xff\xd8jpeg', 1
    db.session.commit()
    assert _item(client)['picture'].startswith('/feed/avatar/')


def test_anonymous_review_never_shows_the_photo(client, db, basic_user):
    basic_user.avatar_data, basic_user.avatar_version = b'\xff\xd8jpeg', 1
    db.session.commit()
    _review(client, db, basic_user, 'anonymous')
    item = _item(client)
    assert not item['picture'] and item['avatar'] is not None
