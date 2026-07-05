import os
from datetime import timedelta

def _resolve_database_url():
    """
    Връща работещ connection string за PostgreSQL.
    Опитва по ред: DATABASE_URL → DATABASE_PUBLIC_URL → построен от PG* частите.
    Reference variables (DATABASE_URL = ${{Postgres.DATABASE_URL}}) понякога не се
    резолват надеждно при определени Railway deploy сценарии — затова имаме и
    построяване директно от отделните PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE
    стойности, които Railway инжектира директно (не като reference) за linked services.
    """
    direct = os.environ.get('DATABASE_URL') or os.environ.get('DATABASE_PUBLIC_URL')
    if direct:
        return direct

    pg_host = os.environ.get('PGHOST')
    pg_port = os.environ.get('PGPORT', '5432')
    pg_user = os.environ.get('PGUSER')
    pg_password = os.environ.get('PGPASSWORD')
    pg_database = os.environ.get('PGDATABASE')

    if pg_host and pg_user and pg_password and pg_database:
        return f'postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_database}'

    return 'sqlite:///maritime.db'


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')

    _db_url = _resolve_database_url()
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Connection pooling — БЕЗ това всяка заявка може да отваря нова TCP+SSL връзка
    # към Postgres от нулата (реален мрежов handshake, стотици ms), вместо да
    # преизползва вече отворена връзка от pool-а. pool_pre_ping проверява връзката
    # преди употреба (Railway/Postgres може тихо да затвори бездействащи връзки).
    # pool_size/max_overflow са невалидни за SQLite (локален fallback), затова само за Postgres.
    if _db_url.startswith('postgresql://'):
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_recycle': 280,      # рециклира връзки преди típичен 300s idle timeout на Postgres/proxy
            'pool_size': 5,
            'max_overflow': 10,
            # Без това, ALTER TABLE миграциите при старт могат да увиснат БЕЗКРАЙНО,
            # ако стара инстанция все още държи връзка/lock по време на rolling deploy
            # (замразен deploy, зареждащ вечно). lock_timeout кара DDL да се провали
            # бързо и ясно вместо да блокира целия старт на приложението.
            'connect_args': {'options': '-c lock_timeout=10s -c statement_timeout=30s'},
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}

    PERMANENT_SESSION_LIFETIME = timedelta(days=7)   # абсолютен максимум на сесията
    INACTIVITY_TIMEOUT_MINUTES = 30                  # автоматичен logout след толкова неактивност
    BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
    MAIL_FROM = os.environ.get('MAIL_FROM', 'noreply@maritimetests.bg')
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
    RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY', '')
    RECAPTCHA_SITE_KEY = os.environ.get('RECAPTCHA_SITE_KEY', '')
    STRIPE_SECRET_KEY      = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
    STRIPE_WEBHOOK_SECRET  = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')

    # Диагностика: Railway автоматично инжектира RAILWAY_GIT_COMMIT_SHA с commit-а,
    # който РЕАЛНО е деплойнат в момента. Показва се като скрит HTML коментар в
    # base.html — вижда се с "View Page Source", за да е ясно веднага дали
    # последният push изобщо е стигнал до сървъра (вместо да се гадае).
    DEPLOYED_COMMIT = os.environ.get('RAILWAY_GIT_COMMIT_SHA', 'no-commit-sha-env-var')

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': ProductionConfig
}

# Диагностичен лог — показва точно кой източник е използван за връзката с базата,
# за да се вижда ясно в Railway логовете дали се ползва PostgreSQL или ефемерен SQLite.
_env = os.environ.get('FLASK_ENV', 'production')
if _env == 'production':
    _uri = Config.SQLALCHEMY_DATABASE_URI
    if _uri.startswith('sqlite'):
        print(
            "⚠️ ПРЕДУПРЕЖДЕНИЕ: Не намерих нито DATABASE_URL, нито DATABASE_PUBLIC_URL, "
            "нито PGHOST/PGUSER/PGPASSWORD/PGDATABASE! Ползвам ефемерен SQLite файл — "
            "данните ще се губят при всеки restart. Провери Railway Variables.",
            flush=True
        )
    else:
        print(f"✓ Database connection resolved: {_uri.split('@')[-1] if '@' in _uri else 'postgresql'}", flush=True)
