"""
app/permissions/roles.py
========================
Роли и планове за maritime-tests.

Йерархия на плановете (нагоре = повече права):
    free < basic < plus < gold < admin

Използване:
    from app.permissions.roles import Role, Plan, user_role, plan_gte

    if plan_gte(user, Plan.BASIC):
        ...  # basic, plus, gold и admin имат достъп

    if user_role(user) == Role.ADMIN:
        ...
"""

from enum import IntEnum


# ---------------------------------------------------------------------------
# Role — системна роля (не е план, а тип акаунт)
# ---------------------------------------------------------------------------

class Role(IntEnum):
    GUEST  = 0   # непотребителски достъп (демо, анонимен)
    USER   = 1   # стандартен потребител (всеки план)
    ADMIN  = 9   # администратор


# ---------------------------------------------------------------------------
# Plan — абонаментен план
# По-високата стойност = повече права.
# ---------------------------------------------------------------------------

class Plan(IntEnum):
    FREE  = 0
    BASIC = 1
    PLUS  = 2
    GOLD  = 3
    # Admin не е план, но при сравнения го третираме като ≥ GOLD
    _ADMIN_SENTINEL = 99


# Низ → Plan (от user.plan полето в БД)
_STR_TO_PLAN: dict[str, Plan] = {
    "free":  Plan.FREE,
    "basic": Plan.BASIC,
    "plus":  Plan.PLUS,
    "gold":  Plan.GOLD,
}


def get_plan(user) -> Plan:
    """Връща Plan за потребител.
    Admin се третира като GOLD за проверки на план.
    """
    if getattr(user, "is_admin", False):
        return Plan._ADMIN_SENTINEL  # type: ignore[return-value]
    raw = (getattr(user, "plan", None) or "free").lower().strip()
    return _STR_TO_PLAN.get(raw, Plan.FREE)


def user_role(user) -> Role:
    """Връща Role на потребителя."""
    if getattr(user, "is_admin", False):
        return Role.ADMIN
    return Role.USER


def plan_gte(user, required: Plan) -> bool:
    """Дали потребителят е на план ≥ required."""
    return get_plan(user) >= required


def plan_eq(user, required: Plan) -> bool:
    """Дали потребителят е точно на даден план."""
    return get_plan(user) == required


# ---------------------------------------------------------------------------
# is_active helper — съвместим с user.is_active от модела
# ---------------------------------------------------------------------------

def is_active_user(user) -> bool:
    """Дали акаунтът е активиран (платен или ръчно активиран)."""
    return bool(getattr(user, "is_active", False))


# ---------------------------------------------------------------------------
# Test-access helper (изнесен от dashboard.py → единно място)
# ---------------------------------------------------------------------------

def user_can_access_test(user, test) -> bool:
    """
    Дали потребителят може да достъпи тест (test / mix / mistakes режими).
    НЕ включва симулатор — за него има отделна логика в routes/dashboard.py.

    Матрица:
        admin / is_active=True → всички тестове
        demo тест             → всеки (включително free без избор)
        free с library избор  → само избраният тест в активен прозорец
        free без избор        → само демо тестове
    """
    if getattr(user, "is_admin", False) or is_active_user(user):
        return True

    if getattr(test, "is_demo", False):
        return True

    # Free план — проверяваме library прозореца
    if hasattr(user, "library_refresh_if_expired"):
        user.library_refresh_if_expired()

    return (
        getattr(user, "library_test_id", None) == test.id
        and hasattr(user, "library_window_active")
        and user.library_window_active()
    )


def user_can_access_simulator(user, test_id: int) -> tuple[bool, str]:
    """
    Дали потребителят може да стартира симулатор за даден тест.
    Връща (allowed: bool, reason: str).

    reason е непразен само при отказ — подходящ за flash съобщение.
    """
    if getattr(user, "is_admin", False) or is_active_user(user):
        return True, ""

    if hasattr(user, "library_refresh_if_expired"):
        user.library_refresh_if_expired()

    if not (
        hasattr(user, "library_window_active")
        and user.library_window_active()
        and getattr(user, "library_test_id", None) == test_id
    ):
        return False, "Симулаторът е достъпен само за теста, който си избрал в Library."

    if hasattr(user, "library_simulator_available") and not user.library_simulator_available():
        return False, "Вече реши симулаторен тест днес. Опитай отново утре."

    return True, ""
