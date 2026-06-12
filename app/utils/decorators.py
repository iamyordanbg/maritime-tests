from functools import wraps
from flask import session, redirect, url_for
from app.extensions import db

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        # Проверяваме от базата — не само от сесията
        from app.models.user import User
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated
