"""create_all failure (parallel-start race) must not stop the column migrations."""
from sqlalchemy import inspect, text

from app.extensions import db
from app.services import db_migrations


def test_columns_added_even_if_create_all_fails(app, monkeypatch):
    with app.app_context():
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE "user" DROP COLUMN google_picture_url'))
            conn.commit()
        assert 'google_picture_url' not in [c['name'] for c in inspect(db.engine).get_columns('user')]

        def boom(*a, **k):
            raise RuntimeError('duplicate key (race)')
        monkeypatch.setattr(db, 'create_all', boom)
        db_migrations.migrate_db(app)
        assert 'google_picture_url' in [c['name'] for c in inspect(db.engine).get_columns('user')]


def test_active_session_token_column_is_added_to_an_old_database(app):
    with app.app_context():
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE "user" DROP COLUMN session_token'))
            conn.commit()
        db_migrations.migrate_db(app)
        assert 'session_token' in [c['name'] for c in inspect(db.engine).get_columns('user')]
