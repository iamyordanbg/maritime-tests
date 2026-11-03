"""
Automatic database migration run on app start (called from create_app).
Moved out of app/__init__.py to keep that file small (CLAUDE.md rule 5).
"""
from app.extensions import db
from app.models import MonthlySnapshot


def migrate_db(app):
    """Автоматична DB миграция"""
    from sqlalchemy import inspect, text
    with app.app_context():
        # За Postgres с няколко gunicorn worker-а: всеки процес независимо вика
        # create_app() -> _migrate_db(), значи 2+ процеса могат едновременно да
        # опитат СЪЩИТЕ ALTER TABLE заявки — точно причината за замръзналия deploy
        # (взаимно чакане на lock). Advisory lock гарантира, че само ЕДИН worker
        # реално мигрира; останалите прескачат веднага (не чакат, не се бъркат).
        is_postgres = db.engine.dialect.name == 'postgresql'
        lock_conn = None
        got_lock = True
        if is_postgres:
            try:
                lock_conn = db.engine.connect()
                got_lock = bool(lock_conn.execute(text("SELECT pg_try_advisory_lock(727384910)")).scalar())
            except Exception:
                got_lock = True  # ако locking логиката гръмне, не блокираме стартирането

        if not got_lock:
            print("⏭  Another worker already migrated the database — skipping.")
            if lock_conn:
                lock_conn.close()
            return

        try:
            db.create_all()
            inspector = inspect(db.engine)

            # User колони
            user_cols = [c["name"] for c in inspector.get_columns("user")]
            migrations = [
                ("plan", 'ALTER TABLE "user" ADD COLUMN plan VARCHAR(20) DEFAULT \'free\''),
                ("plan_update", 'UPDATE "user" SET plan = \'free\' WHERE plan IS NULL'),
                ("nick", 'ALTER TABLE "user" ADD COLUMN nick VARCHAR(100) DEFAULT \'\''),
                ("fullname", 'ALTER TABLE "user" ADD COLUMN fullname VARCHAR(100) DEFAULT \'\''),
                ("notif_subscription", 'ALTER TABLE "user" ADD COLUMN notif_subscription BOOLEAN DEFAULT 1'),
                ("email_verified", 'ALTER TABLE "user" ADD COLUMN email_verified BOOLEAN DEFAULT 0'),
                ("email_verified_fix", 'UPDATE "user" SET email_verified = TRUE WHERE email_verified = FALSE AND id > 0'),
                ("google_id", 'ALTER TABLE "user" ADD COLUMN google_id VARCHAR(200)'),
                ("last_seen", 'ALTER TABLE "user" ADD COLUMN last_seen TIMESTAMP'),
                ("is_active", 'ALTER TABLE "user" ADD COLUMN is_active BOOLEAN DEFAULT 0'),
                ("is_admin", 'ALTER TABLE "user" ADD COLUMN is_admin BOOLEAN DEFAULT 0'),
                ("library_test_id", 'ALTER TABLE "user" ADD COLUMN library_test_id INTEGER'),
                ("library_selected_at", 'ALTER TABLE "user" ADD COLUMN library_selected_at TIMESTAMP'),
                ("library_last_simulator_at", 'ALTER TABLE "user" ADD COLUMN library_last_simulator_at TIMESTAMP'),
                ("lifetime_test_count", 'ALTER TABLE "user" ADD COLUMN lifetime_test_count INTEGER DEFAULT 0'),
                ("plan_activated_at", 'ALTER TABLE "user" ADD COLUMN plan_activated_at TIMESTAMP'),
                ("plan_expires_at", 'ALTER TABLE "user" ADD COLUMN plan_expires_at TIMESTAMP'),
                ("gold_test_ids", 'ALTER TABLE "user" ADD COLUMN gold_test_ids TEXT'),
                ("plan_grace_until", 'ALTER TABLE "user" ADD COLUMN plan_grace_until TIMESTAMP'),
            ]
            with db.engine.connect() as conn:
                # Създаваме таблица за приложени миграции
                try:
                    conn.execute(text('CREATE TABLE IF NOT EXISTS _applied_migrations (name VARCHAR(100) PRIMARY KEY)'))
                    conn.commit()
                except Exception:
                    pass
                applied = set()
                try:
                    rows = conn.execute(text('SELECT name FROM _applied_migrations')).fetchall()
                    applied = {r[0] for r in rows}
                except Exception:
                    pass

                for col, sql in migrations:
                    # ALTER TABLE — само ако колоната липсва
                    if sql.strip().upper().startswith('ALTER') and col in user_cols:
                        continue
                    # UPDATE/INSERT — само ако не е вече приложена
                    if not sql.strip().upper().startswith('ALTER') and col in applied:
                        continue
                    try:
                        conn.execute(text(sql))
                        conn.commit()
                        if not sql.strip().upper().startswith('ALTER'):
                            conn.execute(text('INSERT INTO _applied_migrations (name) VALUES (:n) ON CONFLICT DO NOTHING'), {'n': col})
                            conn.commit()
                    except Exception:
                            pass

            # MonthlySnapshot таблица
            if "monthly_snapshot" not in inspector.get_table_names():
                MonthlySnapshot.__table__.create(db.engine)

            # Post comment replies (parent_id) + drop the earlier ticket-based notifications
            if 'post_comment' in inspector.get_table_names():
                pc_cols = [c['name'] for c in inspector.get_columns('post_comment')]
                if 'parent_id' not in pc_cols:
                    try:
                        with db.engine.connect() as conn:
                            conn.execute(text('ALTER TABLE post_comment ADD COLUMN parent_id INTEGER'))
                            conn.commit()
                    except Exception:
                        pass
            try:
                with db.engine.connect() as conn:
                    conn.execute(text("DELETE FROM ticket_message WHERE ticket_id IN (SELECT id FROM ticket WHERE type = 'notification')"))
                    conn.execute(text("DELETE FROM ticket WHERE type = 'notification'"))
                    conn.commit()
            except Exception:
                pass

            # Signal колони
            if 'signal' in inspector.get_table_names():
                sig_cols = [c['name'] for c in inspector.get_columns('signal')]
                with db.engine.connect() as conn:
                    for col, sql in [
                        ('user_email', 'ALTER TABLE signal ADD COLUMN user_email VARCHAR(120) DEFAULT \'\''),
                        ('reply', 'ALTER TABLE signal ADD COLUMN reply VARCHAR(500)'),
                        ('replied_at', 'ALTER TABLE signal ADD COLUMN replied_at TIMESTAMP'),
                        ('is_read', 'ALTER TABLE signal ADD COLUMN is_read BOOLEAN DEFAULT 0'),
                    ]:
                        if col not in sig_cols:
                            try:
                                conn.execute(text(sql))
                                conn.commit()
                            except Exception:
                                pass

            # Review колони (отговор на сайта, verified) - app/services/review_schema.py
            from app.services.review_schema import migrate_review_columns
            migrate_review_columns(app, db, inspector)

            # All Mistakes флаг на промо кодове/grant-ове - app/services/promo_schema.py
            from app.services.promo_schema import migrate_promo_all_mistakes
            migrate_promo_all_mistakes(app, db, inspector)
            from app.services.promo_schema import migrate_revoked_at
            migrate_revoked_at(app, db, inspector)

            # TestImage колони — R2 поддръжка. image_data става nullable
            # (снимките в R2 не пазят base64 в базата, само reference),
            # storage маркира откъде да се чете ('db' старите, 'r2' новите),
            # r2_key пази пътя в bucket-a за trigger при delete.
            if 'test_image' in inspector.get_table_names():
                ti_cols = [c['name'] for c in inspector.get_columns('test_image')]
                with db.engine.connect() as conn:
                    for col, sql in [
                        ('storage', "ALTER TABLE test_image ADD COLUMN storage VARCHAR(10) DEFAULT 'db'"),
                        ('r2_key', 'ALTER TABLE test_image ADD COLUMN r2_key VARCHAR(255)'),
                    ]:
                        if col not in ti_cols:
                            try:
                                conn.execute(text(sql))
                                conn.commit()
                            except Exception:
                                pass
                    try:
                        conn.execute(text('ALTER TABLE test_image ALTER COLUMN image_data DROP NOT NULL'))
                        conn.commit()
                    except Exception:
                        pass

            # Ticket таблици
            if 'ticket' not in inspector.get_table_names():
                from app.models.ticket import Ticket, TicketMessage
                Ticket.__table__.create(db.engine)
                TicketMessage.__table__.create(db.engine)

            # tests_used колона в user
            user_cols2 = [c['name'] for c in inspector.get_columns('user')]
            if 'tests_used' not in user_cols2:
                with db.engine.connect() as conn:
                    try:
                        conn.execute(text('ALTER TABLE "user" ADD COLUMN tests_used INTEGER DEFAULT 0'))
                        conn.commit()
                    except Exception:
                        pass

            # pref_q_font_size / pref_a_font_size / pref_theme /
            # pref_q_font_family / pref_a_font_family - настройки за четене
            # на тестовете (менюто с 3-те чертички в хедъра), отделни
            # слайдери (0-10) и шрифтове за въпрос vs отговори
            user_cols_prefs = [c['name'] for c in inspector.get_columns('user')]
            with db.engine.connect() as conn:
                for col, sql in [
                    ('pref_q_font_size', "ALTER TABLE \"user\" ADD COLUMN pref_q_font_size INTEGER DEFAULT 5"),
                    ('pref_a_font_size', "ALTER TABLE \"user\" ADD COLUMN pref_a_font_size INTEGER DEFAULT 5"),
                    ('pref_highlight_intensity', "ALTER TABLE \"user\" ADD COLUMN pref_highlight_intensity INTEGER DEFAULT 5"),
                    ('pref_theme', "ALTER TABLE \"user\" ADD COLUMN pref_theme VARCHAR(10) DEFAULT 'dark'"),
                    ('pref_bg_brightness', "ALTER TABLE \"user\" ADD COLUMN pref_bg_brightness INTEGER DEFAULT 5"),
                    ('pref_font_weight', "ALTER TABLE \"user\" ADD COLUMN pref_font_weight INTEGER DEFAULT 5"),
                    ('pref_q_font_family', "ALTER TABLE \"user\" ADD COLUMN pref_q_font_family VARCHAR(20) DEFAULT 'default'"),
                    ('pref_a_font_family', "ALTER TABLE \"user\" ADD COLUMN pref_a_font_family VARCHAR(20) DEFAULT 'default'"),
                    ('pref_q_bold', "ALTER TABLE \"user\" ADD COLUMN pref_q_bold BOOLEAN DEFAULT TRUE"),
                    ('pref_a_bold', "ALTER TABLE \"user\" ADD COLUMN pref_a_bold BOOLEAN DEFAULT FALSE"),
                ]:
                    if col not in user_cols_prefs:
                        try:
                            conn.execute(text(sql))
                            conn.commit()
                        except Exception:
                            pass

            # tests_used колона в user
            user_cols_ext = [c['name'] for c in inspector.get_columns('user')]
            if 'tests_used' not in user_cols_ext:
                with db.engine.connect() as conn:
                    try:
                        conn.execute(text('ALTER TABLE "user" ADD COLUMN tests_used INTEGER DEFAULT 0'))
                        conn.commit()
                    except Exception:
                        pass

            # Payment колони
            if 'payment' in inspector.get_table_names():
                pay_cols = [c['name'] for c in inspector.get_columns('payment')]
                with db.engine.connect() as conn:
                    for col, sql in [
                        ('stripe_fee', 'ALTER TABLE payment ADD COLUMN stripe_fee FLOAT'),
                        ('net_amount', 'ALTER TABLE payment ADD COLUMN net_amount FLOAT'),
                    ]:
                        if col not in pay_cols:
                            try:
                                conn.execute(text(sql))
                                conn.commit()
                            except Exception:
                                pass

            # PromoCode колони (Gold активация)
            if 'promo_code' in inspector.get_table_names():
                promo_cols = [c['name'] for c in inspector.get_columns('promo_code')]
                with db.engine.connect() as conn:
                    for col, sql in [
                        ('plan', "ALTER TABLE promo_code ADD COLUMN plan VARCHAR(20) DEFAULT 'gold'"),
                        ('department', 'ALTER TABLE promo_code ADD COLUMN department VARCHAR(10)'),
                        ('level', 'ALTER TABLE promo_code ADD COLUMN level VARCHAR(50)'),
                        ('selected_test_ids', 'ALTER TABLE promo_code ADD COLUMN selected_test_ids TEXT'),
                        ('mistakes_grace_days', 'ALTER TABLE promo_code ADD COLUMN mistakes_grace_days INTEGER DEFAULT 60'),
                        ('activated_at', 'ALTER TABLE promo_code ADD COLUMN activated_at TIMESTAMP'),
                        ('shared_to', 'ALTER TABLE promo_code ADD COLUMN shared_to VARCHAR(120)'),
                        ('shared_at', 'ALTER TABLE promo_code ADD COLUMN shared_at TIMESTAMP'),
                        ('shared_count', 'ALTER TABLE promo_code ADD COLUMN shared_count INTEGER DEFAULT 0'),
                        ('promo_name', 'ALTER TABLE promo_code ADD COLUMN promo_name VARCHAR(200)'),
                        ('internal_note', 'ALTER TABLE promo_code ADD COLUMN internal_note TEXT'),
                        ('department_restriction', 'ALTER TABLE promo_code ADD COLUMN department_restriction VARCHAR(10)'),
                        ('duration_days', 'ALTER TABLE promo_code ADD COLUMN duration_days INTEGER DEFAULT 30'),
                        ('activation_window_days', 'ALTER TABLE promo_code ADD COLUMN activation_window_days INTEGER DEFAULT 30'),
                        ('topics_allowed', 'ALTER TABLE promo_code ADD COLUMN topics_allowed INTEGER DEFAULT 1'),
                        ('tests_quota_override', 'ALTER TABLE promo_code ADD COLUMN tests_quota_override INTEGER DEFAULT 50'),
                        ('restricted_email', 'ALTER TABLE promo_code ADD COLUMN restricted_email VARCHAR(120)'),
                        ('usage_limit_type', "ALTER TABLE promo_code ADD COLUMN usage_limit_type VARCHAR(10) DEFAULT 'single'"),
                        ('usage_limit_count', 'ALTER TABLE promo_code ADD COLUMN usage_limit_count INTEGER'),
                        ('used_count', 'ALTER TABLE promo_code ADD COLUMN used_count INTEGER DEFAULT 0'),
                        ('is_custom', 'ALTER TABLE promo_code ADD COLUMN is_custom BOOLEAN DEFAULT FALSE'),
                    ]:
                        if col not in promo_cols:
                            try:
                                conn.execute(text(sql))
                                conn.commit()
                            except Exception:
                                pass

            # Индекси за често филтрираните колони — без тях, заявки към растящи
            # таблици (TestResult расте с всеки решен тест) правят пълно
            # последователно сканиране вместо бърз индексиран lookup. CREATE
            # INDEX IF NOT EXISTS е безопасно — не пипа данни, само ускорява четенето.
            index_statements = [
                'CREATE INDEX IF NOT EXISTS ix_test_result_user_id ON test_result (user_id)',
                'CREATE INDEX IF NOT EXISTS ix_test_result_test_id ON test_result (test_id)',
                'CREATE INDEX IF NOT EXISTS ix_test_result_taken_at ON test_result (taken_at)',
                'CREATE INDEX IF NOT EXISTS ix_gold_grant_user_id ON gold_grant (user_id)',
                'CREATE INDEX IF NOT EXISTS ix_plan_grant_user_id ON plan_grant (user_id)',
                'CREATE INDEX IF NOT EXISTS ix_ticket_user_id ON ticket (user_id)',
                'CREATE INDEX IF NOT EXISTS ix_ticket_message_ticket_id ON ticket_message (ticket_id)',
            ]
            with db.engine.connect() as conn:
                for sql in index_statements:
                    try:
                        conn.execute(text(sql))
                        conn.commit()
                    except Exception:
                        pass

            # google_picture_url - за Review системата (снимка от Google
            # OAuth профила, показвана при visibility='google' отзиви)
            user_cols_review = [c['name'] for c in inspector.get_columns('user')]
            if 'google_picture_url' not in user_cols_review:
                with db.engine.connect() as conn:
                    try:
                        conn.execute(text('ALTER TABLE "user" ADD COLUMN google_picture_url VARCHAR(500)'))
                        conn.commit()
                    except Exception:
                        pass

            print("✓ DB migration OK")
        except Exception as e:
            print(f"Migration error: {e}")
        finally:
            if is_postgres and lock_conn:
                try:
                    lock_conn.execute(text("SELECT pg_advisory_unlock(727384910)"))
                except Exception:
                    pass
                lock_conn.close()
