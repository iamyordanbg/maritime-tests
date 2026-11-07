"""
tests/integration/test_review_initials.py
=========================================
Ревю с името от акаунта и без снимка: на ландинга излизат инициалите като в иконата на акаунта.
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
    return next(i for i in client.get('/api/reviews/public').get_json() if i['text'] == 'Initials?')


def _submit_and_approve(client, db, user, visibility):
    client.post('/login', data={'email': user.email, 'password': 'Test123'}, headers=AJAX)
    res = client.post('/api/review/submit', data={'stars': 5, 'text': 'Initials?', 'visibility': visibility})
    assert res.get_json()['success']
    Review.query.filter_by(user_id=user.id).one().status = 'approved'
    db.session.commit()


def test_account_review_without_picture_gets_initials(client, db, basic_user):
    basic_user.firstname, basic_user.lastname = 'Ivan', 'Petrov'
    basic_user.google_picture_url = None
    db.session.commit()
    _submit_and_approve(client, db, basic_user, 'account')
    item = _item(client)
    assert item['name'] == 'Ivan Petrov' and item['initials'] == 'IP' and item['avatar'] is None


def test_anonymous_review_has_no_initials(client, db, basic_user):
    _submit_and_approve(client, db, basic_user, 'anonymous')
    item = _item(client)
    assert item['initials'] == '' and item['avatar'] is not None
