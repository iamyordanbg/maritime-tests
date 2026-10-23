"""
tests/integration/test_review_verified.py
=========================================
'Verified user' бадж: отзив от потребител с платен достъп; с името от акаунта и без снимка
на ландинга се показват инициалите като в иконата на акаунта.
"""
import pytest

from app.models.review import Review
from app.services.reviews import user_has_paid

AJAX = {'X-Requested-With': 'XMLHttpRequest'}


@pytest.fixture(autouse=True)
def _clean_reviews(db):
    Review.query.delete()
    db.session.commit()
    yield
    Review.query.delete()
    db.session.commit()


def _login(client, email, pw='Test123'):
    client.post('/login', data={'email': email, 'password': pw}, headers=AJAX)


def _submit(client, visibility):
    return client.post('/api/review/submit', data={'stars': 5, 'text': 'Verified?', 'visibility': visibility})


def _item(client):
    return next(i for i in client.get('/api/reviews/public').get_json() if i['text'] == 'Verified?')


def test_paid_user_review_is_verified(client, db, basic_user):
    assert user_has_paid(basic_user)
    _login(client, 'basic@test.bg')
    assert _submit(client, 'anonymous').get_json()['success']
    r = Review.query.filter_by(user_id=basic_user.id).one()
    assert r.verified is True
    r.status = 'approved'
    db.session.commit()
    item = _item(client)
    assert item['verified'] is True and item['initials'] == ''  # анонимен: без инициали


def test_unpaid_user_review_not_verified(client, db, free_user):
    assert not user_has_paid(free_user)
    _login(client, 'free@test.bg')
    _submit(client, 'anonymous')
    r = Review.query.filter_by(user_id=free_user.id).one()
    assert r.verified is False


def test_account_review_without_picture_gets_initials(client, db, basic_user):
    basic_user.firstname, basic_user.lastname = 'Ivan', 'Petrov'
    basic_user.google_picture_url = None
    db.session.commit()
    _login(client, 'basic@test.bg')
    assert _submit(client, 'account').get_json()['success']
    r = Review.query.filter_by(user_id=basic_user.id).one()
    r.status = 'approved'
    db.session.commit()
    item = _item(client)
    assert item['name'] == 'Ivan Petrov' and item['initials'] == 'IP'
    assert item['avatar'] is None and item['verified'] is True
