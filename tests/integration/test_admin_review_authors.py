"""Admins see the real account behind every review, even an anonymous one; visitors never do."""
import pytest
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import User
from app.models.review import Review

H = {'X-Requested-With': 'XMLHttpRequest'}


@pytest.fixture
def world(app):
    with app.app_context():
        u = User(name="Real Person", firstname="Ivan", lastname="Petrov", email="ivan@test.bg", password=generate_password_hash("Test123"), plan="free", is_active=False, email_verified=True)
        a = User(name="Adm", email="adm2@test.bg", password=generate_password_hash("Test123"), plan="free", is_active=False, email_verified=True, is_admin=True)
        db.session.add_all([u, a]); db.session.commit()
        db.session.add_all([
            Review(user_id=u.id, stars=5, text="great", visibility='anonymous', display_name='Anonymous Sailor', status='approved'),
            Review(user_id=a.id, stars=5, text="added by admin", visibility='account', display_name='Sergey', status='approved'),
        ]); db.session.commit()
        ids = (u.id, a.id)
    yield ids
    with app.app_context():
        Review.query.delete()
        User.query.filter(User.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()


def test_admin_sees_real_author_of_anonymous_review(app, world):
    c = app.test_client()
    c.post('/login', data={'email': 'adm2@test.bg', 'password': 'Test123'}, headers=H)
    html = c.get('/admin/reviews?status=approved').get_data(as_text=True)
    assert 'Anonymous Sailor' in html                                  # public name unchanged
    assert 'Ivan Petrov' in html and 'ivan@test.bg' in html            # real account shown to the admin
    assert 'Added manually by admin' in html and 'adm2@test.bg' in html


def test_public_reviews_do_not_leak_the_account(app, world):
    body = app.test_client().get('/').get_data(as_text=True)
    assert 'ivan@test.bg' not in body and 'Ivan Petrov' not in body
