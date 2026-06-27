"""
tests/conftest.py
=================
Споделени pytest fixtures за unit и integration тестове.
"""

import pytest
from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.models.test import Test
from werkzeug.security import generate_password_hash


@pytest.fixture(scope="session")
def app():
    """Flask app с in-memory SQLite за тестове."""
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture(scope="function")
def db(app):
    """Чиста БД за всеки тест — rollback след теста."""
    with app.app_context():
        yield _db
        _db.session.rollback()


@pytest.fixture(scope="function")
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture(scope="function")
def free_user(db):
    user = User(
        name="Free User", email="free@test.bg",
        password=generate_password_hash("Test123"),
        plan="free", is_active=False, is_admin=False, email_verified=True,
    )
    db.session.add(user)
    db.session.commit()
    yield user
    db.session.delete(user)
    db.session.commit()


@pytest.fixture(scope="function")
def basic_user(db):
    user = User(
        name="Basic User", email="basic@test.bg",
        password=generate_password_hash("Test123"),
        plan="basic", is_active=True, is_admin=False, email_verified=True,
    )
    db.session.add(user)
    db.session.commit()
    yield user
    db.session.delete(user)
    db.session.commit()


@pytest.fixture(scope="function")
def gold_user(db):
    user = User(
        name="Gold User", email="gold@test.bg",
        password=generate_password_hash("Test123"),
        plan="gold", is_active=True, is_admin=False, email_verified=True,
    )
    db.session.add(user)
    db.session.commit()
    yield user
    db.session.delete(user)
    db.session.commit()


@pytest.fixture(scope="function")
def admin_user(db):
    user = User(
        name="Admin", email="admin@test.bg",
        password=generate_password_hash("Admin123"),
        plan="free", is_active=True, is_admin=True, email_verified=True,
    )
    db.session.add(user)
    db.session.commit()
    yield user
    db.session.delete(user)
    db.session.commit()


@pytest.fixture(scope="function")
def demo_test(db):
    test = Test(
        title="Demo Test", category="deck",
        level="Operational Level", is_demo=True, questions_json="[]",
    )
    db.session.add(test)
    db.session.commit()
    yield test
    db.session.delete(test)
    db.session.commit()


@pytest.fixture(scope="function")
def regular_test(db):
    test = Test(
        title="Regular Test", category="deck",
        level="Operational Level", is_demo=False, questions_json="[]",
    )
    db.session.add(test)
    db.session.commit()
    yield test
    db.session.delete(test)
    db.session.commit()
