import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')

    # Оправяме PostgreSQL URL за SQLAlchemy
    _db_url = os.environ.get('DATABASE_URL', 'sqlite:///maritime.db')
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

# КРИТИЧНА ЗАЩИТА: ако приложението стартира в production режим (FLASK_ENV=production,
# който е default стойността), но DATABASE_URL липсва — приложението ТИХО пада обратно
# на локален SQLite файл в ефемерния контейнер диск на Railway. Тоя файл се губи
# напълно при всеки restart/redeploy, давайки илюзията, че "всичко се трие".
# Спираме това тук, изрично, веднага при import на тоя модул.
_env = os.environ.get('FLASK_ENV', 'production')
if _env == 'production' and not os.environ.get('DATABASE_URL'):
    raise RuntimeError(
        "КРИТИЧНА ГРЕШКА: DATABASE_URL не е зададена в production среда! "
        "Приложението щеше тихо да ползва ефемерен локален SQLite файл, който "
        "се губи при всеки restart/deploy — точно това изглежда като 'изтрити акаунти'. "
        "Провери Railway → приложението → Variables → DATABASE_URL трябва да сочи "
        "към PostgreSQL услугата (обикновено се свързва автоматично от Railway, "
        "но провери дали реално присъства в списъка при стартиране)."
    )
