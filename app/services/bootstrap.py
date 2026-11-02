"""
First-run bootstrap: administrator account and the development test user.
Moved out of app/__init__.py to keep that file small (CLAUDE.md rule 5).
"""
from app.extensions import db


def create_admin(app):
    """Създава администратор и прави DB миграция"""
    with app.app_context():
        from sqlalchemy import text, inspect
        from werkzeug.security import generate_password_hash
        import os

        db.create_all()
        try:
            inspector = inspect(db.engine)

            # test_result колони
            existing_cols = [c['name'] for c in inspector.get_columns('test_result')]
            with db.engine.connect() as conn:
                for col, sql in [
                    ('test_type', 'ALTER TABLE test_result ADD COLUMN test_type VARCHAR(20) DEFAULT \'test\''),
                    ('duration', 'ALTER TABLE test_result ADD COLUMN duration INTEGER DEFAULT 0'),
                    ('question_ids_json', 'ALTER TABLE test_result ADD COLUMN question_ids_json TEXT DEFAULT \'[]\''),
                    ('user_seq', 'ALTER TABLE test_result ADD COLUMN user_seq INTEGER'),
                ]:
                    if col not in existing_cols:
                        try:
                            conn.execute(text(sql))
                            conn.commit()
                        except Exception:
                            pass

            # Изтриваме orphan test_result редове с user_id = null
            with db.engine.connect() as conn:
                try:
                    conn.execute(text('DELETE FROM test_result WHERE user_id IS NULL'))
                    conn.commit()
                except Exception:
                    pass

            # Еднократен backfill: попълва user_seq за СЪЩЕСТВУВАЩИ резултати
            # (нови NULL колони при първо добавяне) - пореден номер ПО
            # ПОТРЕБИТЕЛ, хронологично по taken_at. Postgres има вграден
            # ROW_NUMBER() window function - работи директно. При грешка
            # (напр. локален SQLite при разработка) тихо се прескача.
            with db.engine.connect() as conn:
                try:
                    conn.execute(text('CREATE TABLE IF NOT EXISTS _applied_migrations (name VARCHAR(100) PRIMARY KEY)'))
                    conn.commit()
                except Exception:
                    pass
                already_backfilled = False
                try:
                    row = conn.execute(text("SELECT 1 FROM _applied_migrations WHERE name = 'user_seq_backfill'")).fetchone()
                    already_backfilled = row is not None
                except Exception:
                    pass
                if not already_backfilled:
                    try:
                        conn.execute(text('''
                            UPDATE test_result
                            SET user_seq = sub.rn
                            FROM (
                                SELECT id, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY taken_at) AS rn
                                FROM test_result
                            ) AS sub
                            WHERE test_result.id = sub.id AND test_result.user_seq IS NULL
                        '''))
                        # user.lifetime_test_count = максималния user_seq, който вече има
                        conn.execute(text('''
                            UPDATE "user"
                            SET lifetime_test_count = COALESCE((
                                SELECT MAX(user_seq) FROM test_result WHERE test_result.user_id = "user".id
                            ), 0)
                        '''))
                        conn.execute(text("INSERT INTO _applied_migrations (name) VALUES ('user_seq_backfill') ON CONFLICT DO NOTHING"))
                        conn.commit()
                        print("✓ user_seq backfill applied")
                    except Exception as _e:
                        conn.rollback()
                        print(f"⚠ user_seq backfill skipped ({_e})")

            # Еднократен backfill: is_custom за СЪЩЕСТВУВАЩИ промо кодове,
            # генерирани в 19-минутния прозорец преди този флаг да
            # съществуваше в кода (реален случай, засечен от потребител -
            # код с всички custom настройки правилно записани, но
            # is_custom=False, защото колоната не съществуваше още при
            # INSERT-а). Надежден сигнал: автоматичните 10-пакет кодове
            # ВИНАГИ имат access_type='gold' (буквално, от generate_gold_
            # promos()) - ръчният admin генератор НИКОГА не произвежда
            # точно тази стойност (dropdown му предлага 'Regular tests' /
            # 'Refresh package' / 'Individual gift'). Затова всеки ред с
            # is_custom=False И access_type != 'gold' е гарантирано ръчно
            # генериран - маркираме го коректно, автоматично, за всички
            # засегнати записи наведнъж (не само един ръчно избран ред).
            with db.engine.connect() as conn:
                already_backfilled_custom = False
                try:
                    row = conn.execute(text("SELECT 1 FROM _applied_migrations WHERE name = 'promo_is_custom_backfill'")).fetchone()
                    already_backfilled_custom = row is not None
                except Exception:
                    pass
                if not already_backfilled_custom:
                    try:
                        result = conn.execute(text('''
                            UPDATE promo_code
                            SET is_custom = TRUE
                            WHERE (is_custom IS NULL OR is_custom = FALSE)
                              AND access_type IS NOT NULL
                              AND access_type != 'gold'
                        '''))
                        conn.execute(text("INSERT INTO _applied_migrations (name) VALUES ('promo_is_custom_backfill') ON CONFLICT DO NOTHING"))
                        conn.commit()
                        print(f"✓ promo_code.is_custom backfill applied ({result.rowcount} rows fixed)")
                    except Exception as _e:
                        conn.rollback()
                        print(f"⚠ promo_code.is_custom backfill skipped ({_e})")

            # Еднократен backfill: legacy GoldGrant записи за Custom Promo
            # кодове (is_custom=True), активирани ПРЕДИ PromoGrant
            # разделянето (activate.py, GrantModel = PromoGrant if
            # promo.is_custom else GoldGrant). Тези кодове реално седят
            # като GoldGrant записи в базата и се показват грешно като
            # "Gold" вместо "Custom" в admin панела - display логиката
            # чете правилно КАКВОТО Е в базата, проблемът е чисто данни,
            # не логика. Мести засегнатите записи в PromoGrant (копира
            # всички полета, трие стария GoldGrant ред), еднократно.
            with db.engine.connect() as conn:
                already_backfilled_grants = False
                try:
                    row = conn.execute(text("SELECT 1 FROM _applied_migrations WHERE name = 'gold_to_promo_grant_backfill'")).fetchone()
                    already_backfilled_grants = row is not None
                except Exception:
                    pass
                if not already_backfilled_grants:
                    try:
                        result = conn.execute(text('''
                            INSERT INTO promo_grant
                                (user_id, department, level, test_ids, quota, tests_used,
                                 activated_at, expires_at, grace_until, promo_code, created_at)
                            SELECT g.user_id, g.department, g.level, g.test_ids, g.quota, g.tests_used,
                                   g.activated_at, g.expires_at, g.grace_until, g.promo_code, g.created_at
                            FROM gold_grant g
                            JOIN promo_code p ON p.code = g.promo_code
                            WHERE p.is_custom = TRUE
                        '''))
                        moved_count = result.rowcount
                        conn.execute(text('''
                            DELETE FROM gold_grant
                            WHERE id IN (
                                SELECT g.id FROM gold_grant g
                                JOIN promo_code p ON p.code = g.promo_code
                                WHERE p.is_custom = TRUE
                            )
                        '''))
                        conn.execute(text("INSERT INTO _applied_migrations (name) VALUES ('gold_to_promo_grant_backfill') ON CONFLICT DO NOTHING"))
                        conn.commit()
                        print(f"✓ gold_grant->promo_grant backfill applied ({moved_count} records moved)")
                    except Exception as _e:
                        conn.rollback()
                        print(f"⚠ gold_grant->promo_grant backfill skipped ({_e})")

            # test колони
            test_cols = [c['name'] for c in inspector.get_columns('test')]
            if 'is_demo' not in test_cols:
                with db.engine.connect() as conn:
                    try:
                        conn.execute(text('ALTER TABLE test ADD COLUMN is_demo BOOLEAN DEFAULT 0'))
                        conn.commit()
                    except Exception:
                        pass

            # test_image колони — снимките вече се пазят в базата (persistent),
            # не на диска на контейнера (ephemeral, изтрива се при redeploy)
            if 'test_image' in inspector.get_table_names():
                ti_cols = [c['name'] for c in inspector.get_columns('test_image')]
                if 'format' not in ti_cols:
                    with db.engine.connect() as conn:
                        try:
                            conn.execute(text("ALTER TABLE test_image ADD COLUMN format VARCHAR(10) DEFAULT 'jpg'"))
                            conn.commit()
                        except Exception:
                            pass
                with db.engine.connect() as conn:
                    try:
                        conn.execute(text(
                            'CREATE UNIQUE INDEX IF NOT EXISTS ix_test_image_test_question '
                            'ON test_image (test_id, question_id)'
                        ))
                        conn.commit()
                    except Exception:
                        pass

            # user колони
            user_cols = [c['name'] for c in inspector.get_columns('user')]
            with db.engine.connect() as conn:
                for col, sql in [
                    ('last_seen', 'ALTER TABLE "user" ADD COLUMN last_seen TIMESTAMP'),
                    ('email_verified', 'ALTER TABLE "user" ADD COLUMN email_verified BOOLEAN DEFAULT 0'),
                    ('verification_token', 'ALTER TABLE "user" ADD COLUMN verification_token VARCHAR(64)'),
                    ('otp_code', 'ALTER TABLE "user" ADD COLUMN otp_code VARCHAR(6)'),
                    ('otp_expires', 'ALTER TABLE "user" ADD COLUMN otp_expires TIMESTAMP'),
                    ('reset_token_expires', 'ALTER TABLE "user" ADD COLUMN reset_token_expires TIMESTAMP'),
                    ('notif_subscription', 'ALTER TABLE "user" ADD COLUMN notif_subscription BOOLEAN DEFAULT 1'),
                    ('firstname', 'ALTER TABLE "user" ADD COLUMN firstname VARCHAR(100) DEFAULT \'\''),
                    ('lastname', 'ALTER TABLE "user" ADD COLUMN lastname VARCHAR(100) DEFAULT \'\''),
                    ('nick', 'ALTER TABLE "user" ADD COLUMN nick VARCHAR(100) DEFAULT \'\''),
                    ('fullname', 'ALTER TABLE "user" ADD COLUMN fullname VARCHAR(100) DEFAULT \'\''),
                    ('google_id', 'ALTER TABLE "user" ADD COLUMN google_id VARCHAR(200)'),
                    ('is_active', 'ALTER TABLE "user" ADD COLUMN is_active BOOLEAN DEFAULT 0'),
                    ('library_test_id', 'ALTER TABLE "user" ADD COLUMN library_test_id INTEGER'),
                    ('library_selected_at', 'ALTER TABLE "user" ADD COLUMN library_selected_at TIMESTAMP'),
                    ('library_last_simulator_at', 'ALTER TABLE "user" ADD COLUMN library_last_simulator_at TIMESTAMP'),
                    ('lifetime_test_count', 'ALTER TABLE "user" ADD COLUMN lifetime_test_count INTEGER DEFAULT 0'),
                ]:
                    if col not in user_cols:
                        try:
                            conn.execute(text(sql))
                            conn.commit()
                        except Exception:
                            pass

            # MonthlySnapshot
            if 'monthly_snapshot' not in inspector.get_table_names():
                from app.models.snapshot import MonthlySnapshot
                MonthlySnapshot.__table__.create(db.engine)

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

            # Payment колони
            if 'payment' in inspector.get_table_names():
                pay_cols = [c['name'] for c in inspector.get_columns('payment')]
                with db.engine.connect() as conn:
                    for col, sql in [
                        ('stripe_fee', 'ALTER TABLE payment ADD COLUMN stripe_fee FLOAT'),
                        ('net_amount', 'ALTER TABLE payment ADD COLUMN net_amount FLOAT'),
                        ('promo_email_sent', 'ALTER TABLE payment ADD COLUMN promo_email_sent BOOLEAN DEFAULT FALSE'),
                        ('promo_email_sent_at', 'ALTER TABLE payment ADD COLUMN promo_email_sent_at TIMESTAMP'),
                    ]:
                        if col not in pay_cols:
                            try:
                                conn.execute(text(sql))
                                conn.commit()
                            except Exception:
                                pass

            print("✓ DB migration OK")
        except Exception as e:
            print(f"Migration note: {e}")

        # Създаваме admin акаунт
        try:
            from app.models.user import User
            admin_pass = os.environ.get('ADMIN_PASSWORD', 'admin123')
            admin_user = User.query.filter_by(is_admin=True).first()
            if not admin_user:
                admin_user = User(
                    name='Administrator',
                    email='admin@maritime.bg',
                    password=generate_password_hash(admin_pass),
                    is_admin=True,
                    email_verified=True
                )
                db.session.add(admin_user)
                db.session.commit()
                print("✓ Administrator created")
            elif os.environ.get('ADMIN_PASSWORD'):
                admin_user.password = generate_password_hash(admin_pass)
                db.session.commit()
        except Exception:
            db.session.rollback()


def create_test_user(app):
    """Тестов потребител - само за разработка"""
    with app.app_context():
        from werkzeug.security import generate_password_hash
        from app.models.user import User
        try:
            test = User.query.filter_by(email='test@maritime.bg').first()
            if not test:
                test = User(
                    name='Test User',
                    email='test@maritime.bg',
                    password=generate_password_hash('test123'),
                    is_admin=False,
                    is_active=False,
                    email_verified=True,
                )
                db.session.add(test)
                db.session.commit()
                print("✓ Test user created: test@maritime.bg / test123")
            else:
                if test.is_active:
                    test.is_active = False
                    db.session.commit()
                    print("✓ Test user reset to the Free plan")
        except Exception as e:
            db.session.rollback()
            print(f"Test user error: {e}")
