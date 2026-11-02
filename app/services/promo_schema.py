"""
app/services/promo_schema.py
============================
Добавя колоната `all_mistakes` в `promo_code` и `promo_grant` на съществуващи бази
(вика се от _migrate_db в app/__init__.py).
"""
from sqlalchemy import text

PROMO_ALL_MISTAKES_SQL = {
    'promo_code': 'ALTER TABLE promo_code ADD COLUMN all_mistakes BOOLEAN NOT NULL DEFAULT FALSE',
    'promo_grant': 'ALTER TABLE promo_grant ADD COLUMN all_mistakes BOOLEAN NOT NULL DEFAULT FALSE',
}


def migrate_promo_all_mistakes(app, db, inspector):
    tables = inspector.get_table_names()
    with db.engine.connect() as conn:
        for table, sql in PROMO_ALL_MISTAKES_SQL.items():
            if table not in tables:
                continue
            if 'all_mistakes' in {c['name'] for c in inspector.get_columns(table)}:
                continue
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                conn.rollback()
                app.logger.exception("all_mistakes column migration failed: %s", table)


REVOKED_AT_SQL = {
    'payment': 'ALTER TABLE payment ADD COLUMN revoked_at TIMESTAMP NULL',
    'promo_code': 'ALTER TABLE promo_code ADD COLUMN revoked_at TIMESTAMP NULL',
}


def migrate_revoked_at(app, db, inspector):
    """Колона `revoked_at` в payment и promo_code (меко отнемане от админ)."""
    tables = inspector.get_table_names()
    with db.engine.connect() as conn:
        for table, sql in REVOKED_AT_SQL.items():
            if table not in tables:
                continue
            if 'revoked_at' in {c['name'] for c in inspector.get_columns(table)}:
                continue
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                conn.rollback()
                app.logger.exception("revoked_at column migration failed: %s", table)
