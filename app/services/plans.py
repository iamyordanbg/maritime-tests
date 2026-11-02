"""
app/services/plans.py
=====================
Конфигурация на абонаментните планове.

Използване:
    from app.services.plans import PLANS, get_plan_config, activate_plan

    config = get_plan_config('basic')
    activate_plan(user, 'plus')
"""

from datetime import datetime, timedelta
from app.extensions import db


# ===========================================================================
# ⚠️  ВРЕМЕНЕН ТЕСТОВ РЕЖИМ — НАРОЧНО ОСТАВЕН ТАКА  ⚠️
#
# Докато е True: всеки план (Free/Basic/Plus/Gold код) е свит (1 ден
# библиотечен прозорец, 2 дни Gold активационен прозорец, 15 теста квота)
# вместо реалните стойности (7 дни Free, 365 дни/12 месеца Gold активация,
# истинските планови продължителности) - НАРОЧНО решение на потребителя,
# за да може да се тества бързо целият flow (изтичане на карти, лимити,
# промо кодове) преди реален launch, без да чака дни/месеци реално време.
#
# НЕ Е ЗАБРАВЕН БЪГ. НЕ го сменяй на False без изрично потвърждение от
# потребителя - той изрично помоли да остане така засега.
#
# ПРЕДИ РЕАЛЕН PRODUCTION LAUNCH: смени на False. Реалните числа НЕ са
# пипани никъде долу - просто спират да се презаписват и всичко се връща
# автоматично както си е било по дизайн (виж PLANS речника по-долу).
# ===========================================================================
TESTING_MODE = True
TESTING_DAYS = 1
TESTING_QUOTA = 15
TESTING_ACTIVATION_DAYS = 2   # вместо реалните 12 месеца (365 дни) за активиране на Gold код


# ---------------------------------------------------------------------------
# План конфигурация
# ---------------------------------------------------------------------------

PLANS = {
    'basic': {
        'name':        'Basic',
        'price':       19.99,
        'currency':    'eur',
        'days':        7,
        'description': '7 days of full access to all tests',
        'features': [
            'Full test library',
            'Simulator mode',
            'Mistakes mode',
            'Results history',
        ],
        'promo_codes':  None,
        'validity_months': None,
        'tests_quota': 50,
        'rating_level': True,
        'display': {
            'access': '7 days', 'tests': '50', 'themes': '1',
            'errors': True, 'all_errors': False,
            'functions': ['Test', 'Mix', 'Mistakes', 'Simulator'],
            'valid': 'Immediately', 'ads': False, 'subscription': '1'
        },
    },

    'plus': {
        'name':        'Plus',
        'price':       39.99,
        'currency':    'eur',
        'days':        30,
        'description': '30 days of full access to all tests',
        'features': [
            'Everything in Basic',
            '30 days of access',
            'Priority support',
            'Extended history',
        ],
        'promo_codes':  None,
        'validity_months': None,
        'tests_quota': 100,
        'rating_level': True,
        'display': {
            'access': '30 days', 'tests': '100', 'themes': '1',
            'errors': True, 'all_errors': True,
            'functions': ['Test', 'Mix', 'Mistakes', 'Simulator'],
            'valid': 'Immediately', 'ads': False, 'subscription': '1'
        },
    },

    'gold': {
        'name':        'Gold',
        'price':       299.99,
        'currency':    'eur',
        'days':        30,           # дни на 1 активация
        'description': '10 promo codes — each gives 30 days of access, valid for 12 months',
        'features': [
            'Everything in Plus',
            '10 promo codes to share',
            'Each code = 30 days of access',
            'Codes are valid for 12 months',
            'Ideal for companies and agencies',
        ],
        'promo_codes':     10,
        'validity_months': 12,
        'tests_quota': 150,
        'rating_level': True,
        'themes': 2,
        'valid_days_per_code': 30,
        'code_validity_months': 12,
        'mistakes_grace_days': 60,
        'display': {
            'access': '30 days (per code)', 'tests': '150 / code', 'themes': '2',
            'errors': True, 'all_errors': True,
            'functions': ['Test', 'Mix', 'Mistakes', 'Simulator'],
            'valid': 'Immediately', 'ads': False, 'subscription': '10 codes'
        },
    },
}


# ---------------------------------------------------------------------------
# All Mistakes - правила и допълнителен платен достъп (единственото място за тези числа)
# ---------------------------------------------------------------------------
ALL_MISTAKES = {
    'name':         'All Mistakes access',
    'description':  '1 month access to solve the All Mistakes test of one test',
    'price':        9.99,
    'currency':     'eur',
    'days':         30,    # продължителност на платения достъп
    'tests_quota':  100,   # решавания, включени в платения достъп
    'review_days':  30,    # колко дни след края на абонамента грешките остават за преглед
    'unlock_tests': 10,    # решени Test/Mix/Simulator по теста, за да се отключи All Mistakes
}


# ---------------------------------------------------------------------------
# Прилагане на тестовия режим (виж TESTING_MODE горе) — НЕ пипа реалните
# числа в речника по-горе, само ги "покрива" временно при рендиране/логика.
# ---------------------------------------------------------------------------
if TESTING_MODE:
    for _pk in ('basic', 'plus', 'gold'):
        PLANS[_pk]['days'] = TESTING_DAYS
        PLANS[_pk]['tests_quota'] = TESTING_QUOTA
        PLANS[_pk]['display']['access'] = f'{TESTING_DAYS} day (TEST MODE)'
        PLANS[_pk]['display']['tests'] = str(TESTING_QUOTA)
    PLANS['gold']['valid_days_per_code'] = TESTING_DAYS
    PLANS['gold']['display']['tests'] = f'{TESTING_QUOTA} / code (TEST MODE)'
    PLANS['gold']['validity_months'] = None
    PLANS['gold']['code_validity_months'] = None
    PLANS['gold']['display']['valid'] = f'{TESTING_ACTIVATION_DAYS} days to activate (TEST MODE)'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_plan_config(plan_name: str) -> dict | None:
    """Връща конфигурацията за даден план или None."""
    return PLANS.get(plan_name)


def activate_plan(user, plan_name: str, payment_id: int = None) -> bool:
    """
    Активира Basic/Plus план — създава НОВ автономен PlanGrant, не презаписва
    предишен. Купуването на 2-ри/3-ти план (дори същия тип) отваря нова карта.
    Не прави db.session.commit() — извикващият го прави.
    """
    from app.models.plan_grant import PlanGrant

    config = get_plan_config(plan_name)
    if not config:
        return False

    now = datetime.utcnow()
    days = config['days']
    quota = config.get('tests_quota', 0)

    grant = PlanGrant(
        user_id=user.id,
        plan=plan_name,
        quota=quota,
        tests_used=0,
        activated_at=now,
        expires_at=now + timedelta(days=days),
        payment_id=payment_id,
    )
    db.session.add(grant)
    from app.utils.grant_cache import invalidate_cached_grants
    invalidate_cached_grants(user.id)

    # Легаси полета — пазим само за обратна съвместимост с по-стар код,
    # отразяват НАЙ-КЪСНО изтичащия активен grant (не са източник на истина).
    if not user.plan_expires_at or grant.expires_at > user.plan_expires_at:
        user.plan = plan_name
        user.is_active = True
        user.plan_activated_at = now
        user.plan_expires_at = grant.expires_at

    return True


def gold_code_terms(promo) -> tuple[int, int]:
    """(дни достъп, квота тестове) при активиране на код - ЕДИНСТВЕНОТО място за тази сметка.

    Стандартен Gold код: само от PLANS['gold'] (в тестов режим - съкратените стойности).
    Custom промо: собствените му настройки от админа; липсваща стойност (стар ред) -> PLANS['gold'].
    """
    cfg = PLANS['gold']
    if getattr(promo, 'is_custom', False):
        return (promo.duration_days or cfg['valid_days_per_code'],
                promo.tests_quota_override or cfg['tests_quota'])
    return cfg['valid_days_per_code'], cfg['tests_quota']


def generate_gold_promos(user, stripe_payment_intent_id: str) -> list[str]:
    """
    Генерира 10 промокода за Gold план.
    Кодовете важат 12 месеца от момента на плащането.

    ВАЖНО: кодовете вече ползват СЪЩАТА формула като Basic/Plus subscription
    кодовете (BG + alternating_code, детерминирано от уникалното ID в базата -
    виж app/utils/codes.py) - НЕ случаен hex както преди (GOLD-{hex}).
    Всеки промокод получава свой собствен уникален код (различен ред в
    PromoCode таблицата = различен ID = различен код), по СЪЩИЯ принцип,
    по който всеки отделен Basic/Plus grant си има собствен код.

    Връща list с кодовете.
    """
    from app.models.promo import PromoCode
    from app.utils.codes import subscription_code

    activation_window_days = TESTING_ACTIVATION_DAYS if TESTING_MODE else 365
    expires_at = datetime.utcnow() + timedelta(days=activation_window_days)
    codes = []

    for i in range(10):
        promo = PromoCode(
            code=f"__pending__{i}",  # временна стойност, само за да мине NOT NULL/UNIQUE до flush-а
            client_name=user.name,
            access_type='gold',
            price=0,              # вече платено
            is_active=True,
            is_used=False,
            expires_at=expires_at,
            created_by_user_id=user.id,
            stripe_payment_intent=stripe_payment_intent_id,
        )
        db.session.add(promo)
        db.session.flush()  # присвоява реално auto-increment ID, без пълен commit
        real_code = subscription_code(promo.id, grant_type='promo')
        promo.code = real_code
        codes.append(real_code)

    return codes


def get_plan_display(user) -> dict:
    """
    Връща display данни за текущия план на потребителя.
    Удобно за Jinja шаблони.
    """
    plan_name = getattr(user, 'plan', 'free') or 'free'
    config = PLANS.get(plan_name, {})
    expires_at = getattr(user, 'plan_expires_at', None)

    days_left = 0
    if expires_at and isinstance(expires_at, datetime):
        delta = expires_at - datetime.utcnow()
        days_left = max(0, delta.days)

    return {
        'plan':      plan_name,
        'name':      config.get('name', 'Free'),
        'price':     config.get('price', 0),
        'days_left': days_left,
        'expires_at': expires_at,
        'is_active': getattr(user, 'is_active', False),
        'features':  config.get('features', []),
    }
