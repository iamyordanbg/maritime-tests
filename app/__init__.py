import os
from flask import Flask
from .extensions import db
from .routes import register_blueprints
from .models import User, Test, TestImage, DemoVisit, TestResult, PromoCode, MonthlySnapshot, Signal, Post, PostComment, FreeSession
from config import config
from werkzeug.security import generate_password_hash
from .services.db_migrations import migrate_db
from .services.bootstrap import create_admin, create_test_user

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "production")

    app = Flask(__name__, 
                template_folder="templates",
                static_folder="static")
    app.config.from_object(config[config_name])

    # Кара браузъра да пази снимките дълго локално, вместо да пита сървъра
    # "промениха ли се?" при всяко зареждане на страница — за тест с много
    # снимки, това означава реални мрежови "разговора" при ВСЯКО повторно
    # отваряне на СЪЩИЯ тест, дори снимките изобщо да не са се променили.
    # 30 дни е разумен баланс — снимките към въпроси не се сменят често.
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 60 * 60 * 24 * 30

    # Инициализираме extensions
    db.init_app(app)

    # ==== CACHE-BUSTING за JS/CSS static файлове ====
    # SEND_FILE_MAX_AGE_DEFAULT (30 дни) е нарочно дълъг за снимките (виж
    # коментара по-горе), но същото важи и за JS/CSS файлове по подразбиране
    # в Flask - при всяка поправка на JS бъг, браузърите на потребителите
    # продължават да сервират СТАРАТА кеширана версия до 30 дни, дори след
    # успешен redeploy (URL-ът никога не се сменя: /static/js/x.js винаги
    # същия адрес). static_url() добавя ?v=<mtime> query параметър, базиран
    # на реалното време на последна промяна на файла на диска - браузърът
    # вижда това като НОВ адрес при всяка промяна и презарежда файла, без да
    # губим дългото кеширане за файлове, които РЕАЛНО не са се променили.
    from flask import url_for as _url_for
    def static_url(filename):
        filepath = os.path.join(app.static_folder, filename)
        try:
            v = int(os.path.getmtime(filepath))
        except OSError:
            v = 0
        return f"{_url_for('static', filename=filename)}?v={v}"
    app.jinja_env.globals['static_url'] = static_url

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
    def inject_pending_reviews():
        # Само за админ сесия: брой отзиви в pending -> жълт индикатор на "Reviews"
        # в страничното меню (layouts/admin_sidebar.html). За останалите: 0, без заявка.
        from flask import session
        count = 0
        try:
            if session.get("is_admin"):
                from app.services.reviews import count_pending_reviews
                count = count_pending_reviews()
        except Exception:
            # Не скриваме грешката мълчаливо - индикаторът просто не се показва.
            app.logger.exception("pending reviews count failed")
        return dict(pending_reviews_count=count)

    @app.context_processor
    def inject_site_name():
        from app.services.site import SITE_NAME, SITE_SHORT_NAME
        return dict(site_name=SITE_NAME, site_short_name=SITE_SHORT_NAME)

    @app.context_processor
    def inject_recaptcha():
        return dict(recaptcha_site_key=app.config.get("RECAPTCHA_SITE_KEY", ""))

    @app.before_request
    def _enforce_inactivity_timeout():
        """
        Автоматичен logout след N минути реална неактивност. /ping НЕ се брои
        за активност (той е keep-alive от JS таймер, не истинско действие на
        потребителя) — иначе сесията никога не би могла да изтече сама.
        """
        from flask import session as _session, request as _request
        from datetime import datetime as _dt
        if _request.endpoint in ('auth.ping', 'dashboard.ping') or _request.path.startswith('/static'):
            return

        if 'user_id' in _session:
            now_ts = _dt.utcnow().timestamp()
            last = _session.get('last_activity')
            timeout_seconds = app.config.get('INACTIVITY_TIMEOUT_MINUTES', 30) * 60

            if last and (now_ts - last) > timeout_seconds:
                _session.clear()
                if _request.path.startswith('/api/') or _request.endpoint in ('dashboard.support_unread',):
                    from flask import jsonify as _jsonify
                    return _jsonify({'error': 'session_expired'}), 401
                from flask import redirect as _redirect, url_for as _url_for
                return _redirect(_url_for('auth.login'))

            _session['last_activity'] = now_ts

    @app.context_processor
    def inject_plans():
        # billing/plans.html разчита на 'plans' — прави се include от sidebar модала
        # на много страници, не само от /billing/plans route-а, затова трябва да е
        # глобално достъпна, а не подавана ръчно от всеки отделен route.
        from app.services.plans import PLANS, FREE_PLAN
        return dict(plans=PLANS, free_plan=FREE_PLAN)

    @app.context_processor
    def inject_now_and_usage():
        import math
        from datetime import datetime
        from flask import session
        now = datetime.utcnow()
        usage_days_left = 0
        # Темата се инжектира глобално тук (реизползва вече заявения User
        # обект по-долу, нулева допълнителна DB заявка), за да може ВСЕКИ
        # темплейт да сложи data-theme="{{ user_pref_theme }}" директно при
        # ПЪРВОНАЧАЛНОТО рендиране - БЪГ ФИКС: преди темата се получаваше
        # само през async fetch('/api/test-preferences') в reading-prefs.js
        # СЛЕД като страницата вече е показала default (dark) стила -
        # видим "флаш" на грешна тема при всяко зареждане, докато fetch-ът
        # не отговори. Сега темата е налична в самия HTML отговор.
        user_pref_theme = 'dark'
        try:
            if session.get("user_id"):
                u = User.query.get(session["user_id"])
                if u and u.plan in ('basic', 'plus', 'gold') and u.plan_expires_at:
                    secs = (u.plan_expires_at - now).total_seconds()
                    usage_days_left = max(0, math.ceil(secs / 86400))
                if u and u.pref_theme:
                    user_pref_theme = u.pref_theme
        except Exception:
            pass
        return dict(now=now, usage_days_left=usage_days_left, user_pref_theme=user_pref_theme)

    with app.app_context():
        migrate_db(app)
        create_admin(app)
        create_test_user(app)

        # Изтриваме само orphan test_result редове с user_id = NULL
        try:
            from sqlalchemy import text as _text
            with db.engine.connect() as _conn:
                _conn.execute(_text('DELETE FROM test_result WHERE user_id IS NULL'))
                _conn.commit()
        except Exception as e:
            print(f"✗ Cleanup error: {e}", flush=True)

    if not app.config.get('TESTING'):
        from app.services.review_reminders import start_reminder_scheduler
        start_reminder_scheduler(app)  # седмично напомняне след "Not now" (виж review_reminders.py)

    return app
