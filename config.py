import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')

    # Оправяме PostgreSQL URL за SQLAlchemy.
    # Railway понякога излага само DATABASE_PUBLIC_URL при определени мрежови
    # конфигурации (private networking variations) — пробваме и двете имена.
    _db_url = (
        os.environ.get('DATABASE_URL')
        or os.environ.get('DATABASE_PUBLIC_URL')
        or 'sqlite:///maritime.db'
    )
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
    MAIL_FROM = os.environ.get('MAIL_FROM', 'noreply@maritimetests.bg')
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
    RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY', '')
    RECAPTCHA_SITE_KEY = os.environ.get('RECAPTCHA_SITE_KEY', '')

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': ProductionConfig
}

# ПРЕДУПРЕЖДЕНИЕ (не блокира стартирането): ако в production няма нито DATABASE_URL,
# нито DATABASE_PUBLIC_URL — приложението ще ползва ефемерен SQLite файл, който се
# губи при всеки restart/redeploy. Логваме това ясно, за да се вижда в Railway логовете,
# без да спираме напълно стартирането (за да не получим downtime при cold-start race condition).
_env = os.environ.get('FLASK_ENV', 'production')
if _env == 'production' and not (os.environ.get('DATABASE_URL') or os.environ.get('DATABASE_PUBLIC_URL')):
    print(
        "⚠️ ПРЕДУПРЕЖДЕНИЕ: Нито DATABASE_URL, нито DATABASE_PUBLIC_URL са зададени! "
        "Приложението ще ползва ефемерен SQLite файл — данните ще се губят при всеки restart. "
        "Провери Railway Variables.",
        flush=True
    )
