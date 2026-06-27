"""
app/permissions/decorators.py
==============================
Flask route декоратори за maritime-tests.

Re-exportва login_required и admin_required от utils/decorators.py,
за да може целият код да импортира само от едно място:

    from app.permissions.decorators import (
        login_required,
        admin_required,
        active_required,
        plan_required,
        feature_required,
    )

Нови декоратори
---------------
active_required
    Изисква user.is_active = True (платен план).
    Flash + redirect към /billing при отказ.

plan_required(min_plan)
    Изисква план ≥ min_plan (Plan enum).
    Flash + redirect при отказ.

    Пример:
        @plan_required(Plan.BASIC)
        def some_view(): ...

feature_required(feature)
    Изисква конкретна feature (Feature constant).
    Flash + redirect при отказ.

    Пример:
        @feature_required(Feature.PROGRESS_CHARTS)
        def charts(): ...

json_required
    За API routes — връща JSON 401/403 вместо redirect.
    Комбинира се с login_required/admin_required.
"""

from functools import wraps
from flask import session, redirect, url_for, flash, jsonify, request

# Re-export от utils за единен import path
from app.utils.decorators import login_required, admin_required  # noqa: F401

from app.permissions.roles import Plan, plan_gte, get_plan, is_active_user
from app.permissions.permissions import plan_has_feature


# ---------------------------------------------------------------------------
# active_required
# ---------------------------------------------------------------------------

def active_required(f):
    """
    Изисква user.is_active = True.
    Admin минава без проверка.
    При отказ: flash + redirect към /billing.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))

        from app.models.user import User
        user = User.query.get(session["user_id"])

        if not user:
            return redirect(url_for("auth.login"))

        if user.is_admin or is_active_user(user):
            return f(*args, **kwargs)

        flash("Необходим е активен абонамент за тази функция.", "warning")
        return redirect(url_for("billing.plans"))

    return decorated


# ---------------------------------------------------------------------------
# plan_required
# ---------------------------------------------------------------------------

def plan_required(min_plan: Plan):
    """
    Factory декоратор — изисква план ≥ min_plan.

    Използване:
        @plan_required(Plan.BASIC)
        def view(): ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("auth.login"))

            from app.models.user import User
            user = User.query.get(session["user_id"])

            if not user:
                return redirect(url_for("auth.login"))

            if plan_gte(user, min_plan):
                return f(*args, **kwargs)

            _plan_names = {
                Plan.FREE:  "Free",
                Plan.BASIC: "Basic",
                Plan.PLUS:  "Plus",
                Plan.GOLD:  "Gold",
            }
            needed = _plan_names.get(min_plan, str(min_plan))
            flash(f"Тази функция изисква план {needed} или по-висок.", "warning")
            return redirect(url_for("billing.plans"))

        return decorated
    return decorator


# ---------------------------------------------------------------------------
# feature_required
# ---------------------------------------------------------------------------

def feature_required(feature: str):
    """
    Factory декоратор — изисква конкретна feature.

    Използване:
        @feature_required(Feature.PROGRESS_CHARTS)
        def charts(): ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("auth.login"))

            from app.models.user import User
            user = User.query.get(session["user_id"])

            if not user:
                return redirect(url_for("auth.login"))

            if plan_has_feature(user, feature):
                return f(*args, **kwargs)

            flash("Тази функция не е включена в твоя план.", "warning")
            return redirect(url_for("billing.plans"))

        return decorated
    return decorator


# ---------------------------------------------------------------------------
# json_required  (за API endpoints)
# ---------------------------------------------------------------------------

def json_login_required(f):
    """
    Като login_required, но връща JSON 401 вместо redirect.
    Подходящо за /api/ routes.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def json_active_required(f):
    """
    Като active_required, но връща JSON 403 вместо redirect.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"success": False, "error": "Unauthorized"}), 401

        from app.models.user import User
        user = User.query.get(session["user_id"])

        if not user:
            return jsonify({"success": False, "error": "Unauthorized"}), 401

        if user.is_admin or is_active_user(user):
            return f(*args, **kwargs)

        return jsonify({
            "success": False,
            "error": "active_plan_required",
            "message": "Необходим е активен абонамент."
        }), 403

    return decorated


def json_admin_required(f):
    """
    Като admin_required, но връща JSON 403 вместо redirect.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"success": False, "error": "Unauthorized"}), 401

        from app.models.user import User
        user = User.query.get(session["user_id"])

        if not user or not user.is_admin:
            return jsonify({"success": False, "error": "Forbidden"}), 403

        return f(*args, **kwargs)

    return decorated
