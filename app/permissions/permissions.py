"""
app/permissions/permissions.py
==============================
Feature constants и матрица план → позволени функции.

Използване:
    from app.permissions.permissions import Feature, plan_has_feature

    if plan_has_feature(user, Feature.SIMULATOR):
        # покажи бутон Симулатор
        ...

    # Всички features за план:
    features = features_for_plan(user)
"""

from __future__ import annotations
from app.permissions.roles import Plan, get_plan


# ---------------------------------------------------------------------------
# Feature constants
# ---------------------------------------------------------------------------

class Feature:
    # --- Тестове ---
    FULL_LIBRARY       = "full_library"        # достъп до всички тестове
    LIBRARY_PICK       = "library_pick"        # 1 избор / 7 дни (free)
    SIMULATOR          = "simulator"           # симулаторен режим
    MIX_MODE           = "mix_mode"            # разбъркан режим
    MISTAKES_MODE      = "mistakes_mode"       # режим грешки (нужни ≥ 2 резултата)
    DEMO_TESTS         = "demo_tests"          # безплатни демо тестове

    # --- История и статистики ---
    HISTORY            = "history"             # история на резултати
    HISTORY_EXTENDED   = "history_extended"    # пълна история (plus/gold)
    PROGRESS_CHARTS    = "progress_charts"     # графики с прогрес

    # --- Поддръжка ---
    SUPPORT_TICKET     = "support_ticket"      # support tickets
    PRIORITY_SUPPORT   = "priority_support"    # приоритетна поддръжка (gold)

    # --- Нотификации ---
    NOTIFICATIONS      = "notifications"       # имейл известия


# ---------------------------------------------------------------------------
# Матрица: план → set от Features
# ---------------------------------------------------------------------------
# Всеки план наследява всичко от предишния.

_PLAN_FEATURES: dict[Plan, set[str]] = {

    Plan.FREE: {
        Feature.DEMO_TESTS,
        Feature.LIBRARY_PICK,
        Feature.SIMULATOR,          # само за избрания тест (логиката е в roles.py)
        Feature.MIX_MODE,
        Feature.MISTAKES_MODE,
        Feature.HISTORY,
        Feature.SUPPORT_TICKET,
        Feature.NOTIFICATIONS,
    },

    Plan.BASIC: {
        Feature.FULL_LIBRARY,
        Feature.HISTORY_EXTENDED,
        Feature.PROGRESS_CHARTS,
    },

    Plan.PLUS: set(),  # допълнителни features ще се добавят

    Plan.GOLD: {
        Feature.PRIORITY_SUPPORT,
    },
}


def _build_cumulative() -> dict[Plan, frozenset[str]]:
    """Строи кумулативна матрица (всеки план съдържа правата на по-ниските)."""
    ordered = [Plan.FREE, Plan.BASIC, Plan.PLUS, Plan.GOLD]
    cumulative: dict[Plan, frozenset[str]] = {}
    accumulated: set[str] = set()
    for plan in ordered:
        accumulated |= _PLAN_FEATURES.get(plan, set())
        cumulative[plan] = frozenset(accumulated)
    # Admin → всичко
    all_features = frozenset(accumulated)
    cumulative[Plan._ADMIN_SENTINEL] = all_features  # type: ignore[index]
    return cumulative


_CUMULATIVE: dict[Plan, frozenset[str]] = _build_cumulative()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def plan_has_feature(user, feature: str) -> bool:
    """Дали потребителят (по своя план) има достъп до feature."""
    plan = get_plan(user)
    return feature in _CUMULATIVE.get(plan, frozenset())


def features_for_plan(user) -> frozenset[str]:
    """Всички features за плана на потребителя."""
    plan = get_plan(user)
    return _CUMULATIVE.get(plan, frozenset())


def plan_limits(user) -> dict:
    """
    Конкретни числови лимити по план.
    Удобно за Jinja шаблони: {{ limits.max_history_rows }}
    """
    plan = get_plan(user)

    # Базови лимити (free)
    limits = {
        "max_history_rows":    20,
        "library_window_days": 7,
        "simulator_per_day":   1,
        "support_tickets":     3,
    }

    if plan >= Plan.BASIC:
        limits.update({
            "max_history_rows": 500,
            "support_tickets":  10,
        })

    if plan >= Plan.PLUS:
        limits.update({
            "max_history_rows":  2000,
            "support_tickets":   30,
        })

    if plan >= Plan.GOLD:
        limits.update({
            "max_history_rows":  -1,   # неограничен (-1 = unlimited)
            "support_tickets":   -1,
        })

    return limits
