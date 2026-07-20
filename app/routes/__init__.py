from .auth import auth
from .dashboard import dashboard
from .support import support
from .user_settings import user_settings
from .tests import tests
from .admin import admin
from .feed import feed
from .billing import billing
from .activate import activate_bp

def register_blueprints(app):
    app.register_blueprint(auth)
    app.register_blueprint(dashboard)
    app.register_blueprint(support)
    app.register_blueprint(user_settings)
    app.register_blueprint(tests)
    app.register_blueprint(admin)
    app.register_blueprint(feed)
    app.register_blueprint(billing)
    app.register_blueprint(activate_bp)
