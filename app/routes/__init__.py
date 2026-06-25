from .auth import auth
from .dashboard import dashboard
from .tests import tests
from .admin import admin
from .feed import feed

def register_blueprints(app):
    app.register_blueprint(auth)
    app.register_blueprint(dashboard)
    app.register_blueprint(tests)
    app.register_blueprint(admin)
    app.register_blueprint(feed)
