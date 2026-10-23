"""
app/services/review_schema.py
=============================
Добавя липсващите колони на таблица `review` в съществуващи бази
(викa се от _migrate_db в app/__init__.py).
"""
from sqlalchemy import text

# колона -> ALTER TABLE
REVIEW_COLUMNS = {
    'admin_reply': 'ALTER TABLE review ADD COLUMN admin_reply VARCHAR(500)',
    'admin_reply_at': 'ALTER TABLE review ADD COLUMN admin_reply_at TIMESTAMP',
    'admin_reply_image': 'ALTER TABLE review ADD COLUMN admin_reply_image VARCHAR(300)',
}


def migrate_review_columns(app, db, inspector):
    if 'review' not in inspector.get_table_names():
        return
    existing = {c['name'] for c in inspector.get_columns('review')}
    with db.engine.connect() as conn:
        for col, sql in REVIEW_COLUMNS.items():
            if col in existing:
                continue
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                conn.rollback()
                app.logger.exception("review column migration failed: %s", col)
