import os
from flask import Flask
from .extensions import db
from .routes import register_blueprints
from .models import User, Test, TestImage, DemoVisit, TestResult, PromoCode, MonthlySnapshot, Signal
from config import config
from werkzeug.security import generate_password_hash

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "production")

    app = Flask(__name__, 
                template_folder="templates",
                static_folder="static")
    app.config.from_object(config[config_name])

    # Инициализираме extensions
    db.init_app(app)

    # Регистрираме blueprints
    register_blueprints(app)

    # Context processors
    @app.context_processor
    def inject_greeting():
        from flask import session
        try:
            just_logged_in = session.pop("just_logged_in", False)
        except Exception:
            just_logged_in = False
        return dict(just_logged_in=just_logged_in)

    @app.context_processor
    def inject_admin_user():
        from flask import session
        admin_user = None
        try:
            if session.get("is_admin") and session.get("user_id"):
                admin_user = User.query.get(session["user_id"])
        except Exception:
            pass
        return dict(admin_user=admin_user)

    @app.context_processor
    def inject_recaptcha():
        return dict(recaptcha_site_key=app.config.get("RECAPTCHA_SITE_KEY", ""))

    with app.app_context():
        _migrate_db(app)
        _create_admin(app)
        _create_test_user(app)

    return app


def parse_xls_colors(filepath):
    """Чете XLS/XLSX и открива верни отговори по цвят на шрифта"""
    OPT_LETTERS = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
    questions = []

    if filepath.endswith('.xlsx'):
        import openpyxl
        wb = openpyxl.load_workbook(filepath)
        ws = wb.active

        # Извличаме снимките — всяка снимка принадлежи на въпроса НАД нея
        image_map = {}
        try:
            all_images = ws._images
            print(f"PARSE: Found {len(all_images)} images in worksheet")
        except Exception as e:
            print(f"PARSE: Cannot access _images: {e}")
            all_images = []
        
        for img in all_images:
            try:
                anchor_row_0idx = img.anchor._from.row
                ws_row_of_image = anchor_row_0idx + 1
                question_ws_row = ws_row_of_image - 1
                # Try different methods to get image data
                try:
                    img_data = img._data()
                except:
                    try:
                        img_data = img.ref.blob
                    except:
                        img_data = bytes(img.ref._data)
                fmt = 'jpg' if img_data[:2] == b'\xff\xd8' else 'png'
                image_map[question_ws_row] = (img_data, fmt)
            except Exception as e:
                print(f"PARSE: Image error: {e}")

        for r_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
            q_cell = row[0]
            if not q_cell.value or str(q_cell.value).strip() == '':
                continue
            q_text = str(q_cell.value).strip()
            options = []
            opt_idx = 0

            for cell in row[1:]:
                if not cell.value or str(cell.value).strip() == '':
                    continue
                text = str(cell.value).strip()
                is_correct = False
                if cell.font and cell.font.color:
                    color = cell.font.color
                    if color.type == 'rgb':
                        rgb = color.rgb
                        if rgb not in ('00000000', 'FF000000', '000000'):
                            is_correct = True
                    elif color.type == 'theme':
                        if color.theme not in (0, 1):
                            is_correct = True
                options.append({
                    'letter': OPT_LETTERS[opt_idx] if opt_idx < len(OPT_LETTERS) else 'x',
                    'text': text,
                    'isCorrect': is_correct
                })
                opt_idx += 1

            if options and not any(o['isCorrect'] for o in options):
                options[0]['isCorrect'] = True

            q_id = len(questions) + 1  # 1, 2, 3... последователно
            q = {'id': q_id, 'question': q_text, 'options': options}
            if r_idx in image_map:
                q['has_image'] = True
                q['_image_data'] = image_map[r_idx]
            questions.append(q)

    else:
        # XLS - използваме xlrd
        BLACK_IDX = 8
        wb = xlrd.open_workbook(filepath, formatting_info=True)
        ws = wb.sheet_by_index(0)

        for r in range(1, ws.nrows):
            q_val = ws.cell(r, 0).value
            if not q_val or str(q_val).strip() == '':
                continue
            q_text = str(q_val).strip()
            options = []
            opt_idx = 0

            for c in range(1, ws.ncols):
                cell = ws.cell(r, c)
                if not cell.value or str(cell.value).strip() == '':
                    continue
                text = str(cell.value).strip()
                xf_idx = ws.cell_xf_index(r, c)
                xf = wb.xf_list[xf_idx]
                font = wb.font_list[xf.font_index]
                is_correct = (font.colour_index != BLACK_IDX)
                options.append({
                    'letter': OPT_LETTERS[opt_idx] if opt_idx < len(OPT_LETTERS) else 'x',
                    'text': text,
                    'isCorrect': is_correct
                })
                opt_idx += 1

            if options and not any(o['isCorrect'] for o in options):
                options[0]['isCorrect'] = True

            questions.append({'id': len(questions) + 1, 'question': q_text, 'options': options})

    return questions

def generate_promo_code(prefix='MAR'):
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{suffix}"

# ============================================================
#  AUTH ROUTES
# ============================================================

def inject_images(test_id, questions):
    """Добавя снимките към въпросите — URL вместо base64"""
    img_dir = f"/tmp/qimages/{test_id}"
    if not os.path.exists(img_dir):
        print(f"INJECT: No image dir found for test {test_id}")
        return questions
    
    loaded = 0
    for q in questions:
        if q.get('has_image'):
            for fmt in ['jpg', 'png']:
                img_path = f"{img_dir}/{q['id']}.{fmt}"
                if os.path.exists(img_path):
                    # URL вместо base64 — браузърът зарежда при нужда
                    q['image'] = f"/qimage/{test_id}/{q['id']}.{fmt}"
                    loaded += 1
                    break
    print(f"INJECT: Loaded {loaded} images for test {test_id}")
    return questions


def _migrate_db(app):
    """Автоматична DB миграция"""
    from sqlalchemy import inspect, text
    with app.app_context():
        try:
            db.create_all()
            inspector = inspect(db.engine)

            # User колони
            user_cols = [c["name"] for c in inspector.get_columns("user")]
            migrations = [
                ("nick", "ALTER TABLE user ADD COLUMN nick VARCHAR(100) DEFAULT \"\""),
                ("fullname", "ALTER TABLE user ADD COLUMN fullname VARCHAR(100) DEFAULT \"\""),
                ("notif_subscription", "ALTER TABLE user ADD COLUMN notif_subscription BOOLEAN DEFAULT 1"),
                ("email_verified", "ALTER TABLE user ADD COLUMN email_verified BOOLEAN DEFAULT 0"),
                ("google_id", "ALTER TABLE user ADD COLUMN google_id VARCHAR(200)"),
                ("last_seen", "ALTER TABLE user ADD COLUMN last_seen DATETIME"),
                ("is_active", "ALTER TABLE user ADD COLUMN is_active BOOLEAN DEFAULT 0"),
                ("is_admin", "ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0"),
            ]
            with db.engine.connect() as conn:
                for col, sql in migrations:
                    if col not in user_cols:
                        try:
                            conn.execute(text(sql))
                            conn.commit()
                        except Exception:
                            pass

            # MonthlySnapshot таблица
            if "monthly_snapshot" not in inspector.get_table_names():
                MonthlySnapshot.__table__.create(db.engine)

            print("✓ DB migration OK")
        except Exception as e:
            print(f"Migration error: {e}")


def _create_admin(app):
    """Създава администратор при първо стартиране"""
    
        db.create_all()
        # Добавя test_type колона ако не съществува
        try:
            from sqlalchemy import text, inspect
            # Create test_image table if not exists
            db.create_all()
            inspector = inspect(db.engine)
                existing_cols = [c['name'] for c in inspector.get_columns('test_result')]
            with db.engine.connect() as conn:
                if 'test_type' not in existing_cols:
                    conn.execute(text('ALTER TABLE test_result ADD COLUMN test_type VARCHAR(20) DEFAULT "test"'))
                    conn.commit()
                if 'duration' not in existing_cols:
                    conn.execute(text('ALTER TABLE test_result ADD COLUMN duration INTEGER DEFAULT 0'))
                    conn.commit()
                if 'question_ids_json' not in existing_cols:
                    conn.execute(text('ALTER TABLE test_result ADD COLUMN question_ids_json TEXT DEFAULT "[]"'))
                    conn.commit()
            # Add is_demo to test table
            test_cols = [c['name'] for c in inspector.get_columns('test')]
            if 'is_demo' not in test_cols:
                with db.engine.connect() as conn2:
                    conn2.execute(text('ALTER TABLE test ADD COLUMN is_demo BOOLEAN DEFAULT 0'))
                    conn2.commit()
            # Create demo_visit table
            db.create_all()
            # Add last_seen to user table
            user_cols2 = [c['name'] for c in inspector.get_columns('user')]
            if 'last_seen' not in user_cols2:
                with db.engine.connect() as conn3:
                    conn3.execute(text('ALTER TABLE user ADD COLUMN last_seen DATETIME'))
                    conn3.commit()
            # Add email_verified and verification_token to user table
            user_cols = [c['name'] for c in inspector.get_columns('user')]
            if 'email_verified' not in user_cols:
                with db.engine.connect() as conn2:
                    conn2.execute(text('ALTER TABLE user ADD COLUMN email_verified BOOLEAN DEFAULT 0'))
                    conn2.commit()
            if 'verification_token' not in user_cols:
                with db.engine.connect() as conn3:
                    conn3.execute(text('ALTER TABLE user ADD COLUMN verification_token VARCHAR(64)'))
                    conn3.commit()
            if 'otp_code' not in user_cols:
                with db.engine.connect() as conn4:
                    conn4.execute(text('ALTER TABLE user ADD COLUMN otp_code VARCHAR(6)'))
                    conn4.commit()
            if 'otp_expires' not in user_cols:
                with db.engine.connect() as conn5:
                    conn5.execute(text('ALTER TABLE user ADD COLUMN otp_expires DATETIME'))
                    conn5.commit()
            # Re-read columns for latest additions
            user_cols_fresh = [c['name'] for c in inspector.get_columns('user')]
            if 'reset_token_expires' not in user_cols_fresh:
                with db.engine.connect() as conn6:
                    conn6.execute(text('ALTER TABLE user ADD COLUMN reset_token_expires DATETIME'))
                    conn6.commit()
            # notif_subscription колона
            user_cols_n = [c['name'] for c in inspector.get_columns('user')]
            if 'notif_subscription' not in user_cols_n:
                with db.engine.connect() as conn_n:
                    conn_n.execute(text('ALTER TABLE user ADD COLUMN notif_subscription BOOLEAN DEFAULT 1'))
                    conn_n.commit()
            if 'nick' not in user_cols_n:
                with db.engine.connect() as conn_nick:
                    conn_nick.execute(text('ALTER TABLE user ADD COLUMN nick VARCHAR(100) DEFAULT ""'))
                    conn_nick.commit()
            if 'fullname' not in user_cols_n:
                with db.engine.connect() as conn_fn:
                    conn_fn.execute(text('ALTER TABLE user ADD COLUMN fullname VARCHAR(100) DEFAULT ""'))
                    conn_fn.commit()
            # MonthlySnapshot таблица
                existing = [t for t in inspector.get_table_names()]
            if 'monthly_snapshot' not in existing:
                MonthlySnapshot.__table__.create(db.engine)
                    print("✓ MonthlySnapshot таблица създадена")
                print("✓ DB migration OK")
        except Exception as e:
                print(f"Migration note: {e}")
        try:
            import os
                admin_user = User.query.filter_by(is_admin=True).first()
                admin_pass = os.environ.get('ADMIN_PASSWORD', 'admin123')
            if not admin_user:
                    admin_user = User(
                    name='Администратор',
                    email='admin@maritime.bg',
                    password=generate_password_hash(admin_pass),
                    is_admin=True
                )
                    db.session.add(admin_user)
                    db.session.commit()
                    print("✓ Администратор създаден")
            else:
                # Update password if ADMIN_PASSWORD env var is set
                if os.environ.get('ADMIN_PASSWORD'):
                        admin_user.password = generate_password_hash(admin_pass)
                        db.session.commit()
                        print("✓ Админ парола обновена")
            if False:  # dummy to keep indentation
                    print("✓ Администратор създаден: admin@maritime.bg / admin123")
        except Exception:
                db.session.rollback()

# Инициализация на базата - работи и на Railway и локално - v2.1


def _create_test_user(app):
    """Тестов потребител - само за разработка, да се махне в production"""
    
        try:
            test = User.query.filter_by(email='test@maritime.bg').first()
            if not test:
                test = User(
                    name='Test User',
                    email='test@maritime.bg',
                    password=generate_password_hash('test123'),
                    is_admin=False,
                    is_active=True,  # тестов акаунт - активен
                    email_verified=True,
                    rank='Captain',
                    company='Maritime Tests',
                    category='deck',
                    level='Operational Level'
                )
                db.session.add(test)
                db.session.commit()
                print("✓ Тестов потребител създаден: test@maritime.bg / test123")
        except Exception as e:
            db.session.rollback()
            print(f"Test user error: {e}")
