"""
app/permissions/__init__.py
===========================
Публичен API на permissions пакета.

    from app.permissions import (
        Role, Plan, get_plan, plan_gte, user_role,
        is_active_user, user_can_access_test, user_can_access_simulator,
        Feature, plan_has_feature, features_for_plan, plan_limits,
        login_required, admin_required,
        active_required, plan_required, feature_required,
        json_login_required, json_active_required, json_admin_required,
    )
"""

from app.permissions.roles import (  # noqa: F401
    Role, Plan, get_plan, plan_gte, plan_eq, user_role,
    is_active_user, user_can_access_test, user_can_access_simulator,
)

from app.permissions.permissions import (  # noqa: F401
    Feature, plan_has_feature, features_for_plan, plan_limits,
)

from app.permissions.decorators import (  # noqa: F401
    login_required, admin_required,
    active_required, plan_required, feature_required,
    json_login_required, json_active_required, json_admin_required,
)
