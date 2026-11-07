"""
tests/integration/test_review_account_name.py
=============================================
Отзив: "Anonymous account" или "My account" (имената от акаунта на платформата).
"""

from werkzeug.security import generate_password_hash

from app.models.review import Review
from app.models.user import User
from app.services.review_persona import public_identity
from app.services.reviews import account_display_name

AJAX = {'X-Requested-With': 'XMLHttpRequest'}


def _user(db, **kw):
    base = dict(name='Ivan P', email='rev@test.bg', password=generate_password_hash('Test123'),
                plan='free', is_active=False, is_admin=False, email_verified=True)
    base.update(kw)
    u = User(**base)
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, email='rev@test.bg'):
    client.post('/login', data={'email': email, 'password': 'Test123'}, headers=AJAX)


def _cleanup(db, user):
    Review.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()


class TestAccountDisplayName:

    def test_first_and_last_name_as_entered(self, db):
        u = _user(db, firstname='Ivan', lastname='Petrov')
        assert account_display_name(u) == 'Ivan Petrov'
        _cleanup(db, u)

    def test_falls_back_to_account_name(self, db):
        u = _user(db, firstname='', lastname='', name='Ivan P')
        assert account_display_name(u) == 'Ivan P'
        _cleanup(db, u)

    def test_empty_when_nothing(self, db):
        u = _user(db, firstname='', lastname='', name='')
        assert account_display_name(u) == ''
        _cleanup(db, u)


class TestSubmit:

    def test_account_visibility_uses_account_names(self, client, db):
        u = _user(db, firstname='Ivan', lastname='Petrov')
        _login(client)
        res = client.post('/api/review/submit', data={'stars': 5, 'text': 'Great', 'visibility': 'account'})
        assert res.get_json()['success'] is True
        r = Review.query.filter_by(user_id=u.id).one()
        assert r.visibility == 'account' and r.display_name == 'Ivan Petrov'
        assert public_identity(r)[0] == 'Ivan Petrov'  # реално име, не измислено
        _cleanup(db, u)

    def test_anonymous_stays_anonymous(self, client, db):
        u = _user(db, firstname='Ivan', lastname='Petrov')
        _login(client)
        client.post('/api/review/submit', data={'stars': 4, 'text': 'Ok', 'visibility': 'anonymous'})
        r = Review.query.filter_by(user_id=u.id).one()
        assert r.visibility == 'anonymous' and 'Ivan' not in (r.display_name or '')
        assert public_identity(r)[0] != 'Ivan Petrov'
        _cleanup(db, u)

    def test_account_without_any_name_is_rejected(self, client, db):
        u = _user(db, firstname='', lastname='', name='')
        _login(client)
        res = client.post('/api/review/submit', data={'stars': 5, 'text': 'x', 'visibility': 'account'})
        assert res.status_code == 400 and Review.query.filter_by(user_id=u.id).count() == 0
        _cleanup(db, u)

    def test_old_google_value_is_not_accepted_anymore(self, client, db):
        u = _user(db, firstname='Ivan', lastname='Petrov')
        _login(client)
        client.post('/api/review/submit', data={'stars': 5, 'text': 'x', 'visibility': 'google'})
        assert Review.query.filter_by(user_id=u.id).one().visibility == 'anonymous'
        _cleanup(db, u)


def test_should_prompt_returns_display_name(client, db):
    u = _user(db, firstname='Ivan', lastname='Petrov')
    _login(client)
    data = client.get('/api/review/should-prompt').get_json()
    assert data['display_name'] == 'Ivan Petrov'
    _cleanup(db, u)


def test_legacy_google_reviews_still_show_real_name(db):
    u = _user(db)
    r = Review(user_id=u.id, stars=5, text='old', status='approved', visibility='google',
               display_name='Ivan Petrov', display_picture_url=None)
    db.session.add(r)
    db.session.commit()
    assert public_identity(r)[0] == 'Ivan Petrov'
    _cleanup(db, u)
