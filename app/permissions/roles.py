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
    """Дали акаунтът е активиран (платен или ръчно активиран).

    ПОПРАВКА: преди проверяваше само остарялата user.is_active boolean
    колона, която не е надеждно синхронизирана с по-новата grant-базирана
    система (PlanGrant/GoldGrant/PromoGrant с expires_at). Реален бъг:
    Basic план потребител с валиден, активен PlanGrant получаваше отказ
    на достъп (напр. Mistakes функцията го препращаше към Library),
    защото user.is_active оставаше False въпреки активния план.
    """
    if getattr(user, "is_active", False):
        return True
    if hasattr(user, "has_active_plan"):
        return user.has_active_plan()
    return False


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
        if (getattr(user, "plan", None) or "") == "gold":
            from datetime import datetime as _dt
            from app.models.gold_grant import GoldGrant
            from app.models.promo_grant import PromoGrant
            now = _dt.utcnow()
            # GoldGrant И PromoGrant - ОТДЕЛНИ таблици (по изрично искане),
            # но ДВЕТЕ трябва да ограничават достъпа еднакво - иначе Promo
            # потребител (само 1 тема купена) щеше грешно да пада в
            # legacy fallback-а по-долу и да получи достъп до ВСИЧКИ
            # тестове, вместо само до купения си (реален бъг, открит при
            # раздялата на моделите - GoldGrant.query сам по себе си вече
            # НЕ вижда Promo grant-овете).
            grants = GoldGrant.query.filter(
                GoldGrant.user_id == user.id, GoldGrant.expires_at > now
            ).all()
            grants += PromoGrant.query.filter(
                PromoGrant.user_id == user.id, PromoGrant.expires_at > now
            ).all()
            if grants:
                allowed_ids = set()
                for g in grants:
                    allowed_ids.update(g.test_id_list())
                if test.id not in allowed_ids:
                    return getattr(test, "is_demo", False)
            # ако няма нито един активен grant (легаси данни отпреди GoldGrant) —
            # пада обратно към старото поле за обратна съвместимост
            elif getattr(user, "gold_test_ids", None):
                import json as _json
                try:
                    legacy_ids = set(_json.loads(user.gold_test_ids or "[]"))
                except Exception:
                    legacy_ids = set()
                if legacy_ids and test.id not in legacy_ids:
                    return getattr(test, "is_demo", False)
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


def user_in_mistakes_grace_period(user) -> bool:
    """
    Дали потребителят е в grace период — планът е изтекъл, но All Mistakes
    остава достъпен още N дни (user.plan_grace_until, зададен при Gold активация).
    """
    from datetime import datetime
    grace_until = getattr(user, "plan_grace_until", None)
    expires_at = getattr(user, "plan_expires_at", None)
    if not grace_until or not expires_at:
        return False
    now = datetime.utcnow()
    return expires_at < now <= grace_until


def user_can_access_mistakes(user, test) -> bool:
    """
    Достъп до All Mistakes режима — позволен и по време на grace период
    (дори ако is_active вече не важи за обикновени тестове).
    """
    if user_can_access_test(user, test):
        return True
    return user_in_mistakes_grace_period(user)


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
