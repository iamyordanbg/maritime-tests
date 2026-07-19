"""
app/services/usage.py
Business логика за 'My Usage' карти (Gold/Custom/Basic/Plus/Free планове) —
извлечена от app/routes/dashboard.py::api_my_usage (Правило 4:
NEXT_SESSION_PROMPT.md, бизнес логика → app/services/, routes само HTTP).
"""
import math
from datetime import datetime
from app.extensions import db
from app.models.test import Test
from app.models.result import TestResult
from app.utils.codes import get_or_create_subscription_code, free_code


def _build_gold_or_promo_card(g, grant_type, user, now):
    """Изгражда карта за GoldGrant или PromoGrant запис (идентична структура,
    само различна таблица-източник — виж коментара в build_usage_cards)."""
    test_ids = g.test_id_list()
    titles = [t.title for t in Test.query.filter(Test.id.in_(test_ids)).all()] if test_ids else []
    # Реален брой решени — директно от TestResult, не от съхранено поле
    # (което никога не се актуализира надеждно) — вижте същата логика, ползвана
    # за самите карти на dashboard-а, за да няма разминаване между двете места.
    used_real = (TestResult.query
                 .filter(TestResult.user_id == user.id,
                         TestResult.test_id.in_(test_ids),
                         TestResult.taken_at >= g.activated_at)
                 .count()) if test_ids else 0
    total_seconds = max(1, (g.expires_at - g.activated_at).total_seconds())
    elapsed_seconds = max(0, (now - g.activated_at).total_seconds())
    from app.utils.grants import grant_plan_label
    plan_label = grant_plan_label(g)
    return {
        'plan': plan_label, 'test_names': titles,
        'quota': g.quota, 'tests_used': used_real,
        'tests_remaining': max(0, g.quota - used_real),
        'activated_at': g.activated_at.strftime('%d %b %Y, %H:%M') + ' (UTC)',
        'expires_at': g.expires_at.strftime('%d %b %Y, %H:%M') + ' (UTC)',
        'days_remaining': max(0, math.ceil((g.expires_at - now).total_seconds() / 86400)),
        'pct_remaining': max(0, min(100, int(100 - (elapsed_seconds / total_seconds * 100)))),
        'subscription_code': (g.promo_code or get_or_create_subscription_code(grant_type, g.id)),
        '_activated_raw': g.activated_at,
    }


def _build_plan_card(g, user, now):
    """Изгражда карта за PlanGrant (Basic/Plus) запис."""
    title = None
    if g.library_test_id:
        t = Test.query.get(g.library_test_id)
        title = t.title if t else None
    used_real = (TestResult.query
                 .filter(TestResult.user_id == user.id,
                         TestResult.test_id == g.library_test_id,
                         TestResult.taken_at >= g.activated_at)
                 .count()) if g.library_test_id else 0
    total_seconds = max(1, (g.expires_at - g.activated_at).total_seconds())
    elapsed_seconds = max(0, (now - g.activated_at).total_seconds())
    return {
        'plan': g.plan.capitalize(), 'test_names': [title] if title else [],
        'quota': g.quota, 'tests_used': used_real,
        'tests_remaining': max(0, g.quota - used_real),
        'activated_at': g.activated_at.strftime('%d %b %Y, %H:%M') + ' (UTC)',
        'expires_at': g.expires_at.strftime('%d %b %Y, %H:%M') + ' (UTC)',
        'days_remaining': max(0, math.ceil((g.expires_at - now).total_seconds() / 86400)),
        'pct_remaining': max(0, min(100, int(100 - (elapsed_seconds / total_seconds * 100)))),
        'subscription_code': get_or_create_subscription_code('plan', g.id),
        '_activated_raw': g.activated_at,
    }


def _build_free_card(user, now):
    """Free план карта - активната (текуща) сесия от FreeSession, СЪЩАТА
    структура като Gold/Basic/Plus, за да се вижда Free в 'My Usage'
    (преди изобщо не се показваше нищо тук за Free потребители)."""
    if not (not user.has_active_plan() and user.library_test_id and user.library_window_active()):
        return None
    FREE_QUOTA = 7
    free_test = Test.query.get(user.library_test_id)
    used_real = (TestResult.query
                 .filter(TestResult.user_id == user.id,
                         TestResult.test_id == user.library_test_id,
                         TestResult.taken_at >= (user.library_selected_at or now))
                 .count())
    expires_at = user.library_window_expires_at()
    total_seconds = max(1, (expires_at - user.library_selected_at).total_seconds())
    elapsed_seconds = max(0, (now - user.library_selected_at).total_seconds())
    return {
        'plan': 'Free', 'test_names': [free_test.title] if free_test else [],
        'quota': FREE_QUOTA, 'tests_used': used_real,
        'tests_remaining': max(0, FREE_QUOTA - used_real),
        'activated_at': user.library_selected_at.strftime('%d %b %Y, %H:%M') + ' (UTC)',
        'expires_at': expires_at.strftime('%d %b %Y, %H:%M') + ' (UTC)',
        'days_remaining': max(0, math.ceil((expires_at - now).total_seconds() / 86400)),
        'pct_remaining': max(0, min(100, int(100 - (elapsed_seconds / total_seconds * 100)))),
        'subscription_code': f"BG{free_code(user.id)}",
        '_activated_raw': user.library_selected_at,
    }


def build_usage_cards(user):
    """Връща сортиран списък от usage карти (Gold/Custom/Basic/Plus/Free)
    за 'My Usage' таба. Единствената логика, извикана от
    dashboard.py::api_my_usage (route-ът остава чист HTTP handler)."""
    from app.models.gold_grant import GoldGrant
    from app.models.promo_grant import PromoGrant
    from app.models.plan_grant import PlanGrant

    now = datetime.utcnow()
    cards = []

    for g in GoldGrant.query.filter(GoldGrant.user_id == user.id, GoldGrant.expires_at > now).order_by(GoldGrant.activated_at.asc()).all():
        cards.append(_build_gold_or_promo_card(g, 'gold', user, now))

    # PromoGrant - ОТДЕЛЕН от GoldGrant (по изрично искане - Promo и Gold
    # са различни продукти, различни таблици). Използва СЪЩАТА card-building
    # логика (_build_gold_or_promo_card) - структурата на картите е
    # идентична, само таблицата-източник е различна.
    for g in PromoGrant.query.filter(PromoGrant.user_id == user.id, PromoGrant.expires_at > now).order_by(PromoGrant.activated_at.asc()).all():
        cards.append(_build_gold_or_promo_card(g, 'promo', user, now))

    for g in PlanGrant.query.filter(PlanGrant.user_id == user.id, PlanGrant.expires_at > now).order_by(PlanGrant.activated_at.asc()).all():
        cards.append(_build_plan_card(g, user, now))

    if user.library_refresh_if_expired():
        db.session.commit()
    free_card = _build_free_card(user, now)
    if free_card:
        cards.append(free_card)

    # Сортираме ЦЯЛОСТНИЯ списък (Gold + Basic/Plus + Free смесени) по
    # реалната дата на активиране - най-старият план най-отгоре,
    # най-скоро активираният най-отдолу. По-горе всеки тип се append-ва
    # отделно, затова е нужен този финален merge-sort, за да е вярно и
    # при потребители с активни грантове от няколко типа едновременно.
    cards.sort(key=lambda c: c['_activated_raw'])
    for c in cards:
        del c['_activated_raw']

    return cards


def build_billing_data(user):
    """Връща (payments, activated_codes) за 'My Billing' таба —
    извлечено от app/routes/dashboard.py::api_my_billing."""
    from app.models.payment import Payment
    from app.models.promo import PromoCode
    from app.models.plan_grant import PlanGrant
    from app.models.gold_grant import GoldGrant
    from app.models.promo_grant import PromoGrant
    from app.models.user import User

    now = datetime.utcnow()
    payments = Payment.query.filter_by(user_id=user.id).order_by(Payment.paid_at.desc()).all()

    result = []
    for p in payments:
        entry = {
            'id': p.id,
            'plan': p.plan,
            'amount': p.amount,
            'paid_at': p.paid_at.strftime('%d.%m.%Y %H:%M'),
            'promo_email_sent': bool(p.promo_email_sent),
            'codes': [],
            'loaded_test': None,
            'active_from': None,
            'active_until': None,
        }
        if p.plan == 'gold' and p.stripe_payment_intent:
            codes = PromoCode.query.filter_by(
                stripe_payment_intent=p.stripe_payment_intent
            ).order_by(PromoCode.id.asc()).all()
            code_entries = []
            for c in codes:
                code_entry = {
                    'code': c.code,
                    'is_used': bool(c.is_used),
                    'used_by': c.used_by or '',
                    'shared_to': c.shared_to or '',
                    'active_from': None,
                    'active_until': None,
                    'activate_by': None,
                }
                if c.is_used:
                    g = GoldGrant.query.filter_by(promo_code=c.code).first()
                    if g:
                        if g.activated_at:
                            code_entry['active_from'] = g.activated_at.strftime('%d.%m.%Y %H:%M') + ' (UTC)'
                        if g.expires_at:
                            code_entry['active_until'] = g.expires_at.strftime('%d.%m.%Y %H:%M') + ' (UTC)'
                elif c.expires_at:
                    code_entry['activate_by'] = c.expires_at.strftime('%d.%m.%Y %H:%M')
                code_entries.append(code_entry)
            entry['codes'] = code_entries
        elif p.plan in ('basic', 'plus'):
            grant = PlanGrant.query.filter_by(payment_id=p.id).first()
            if grant:
                if grant.library_test_id:
                    t = Test.query.get(grant.library_test_id)
                    entry['loaded_test'] = t.title if t else None
                if grant.activated_at:
                    entry['active_from'] = grant.activated_at.strftime('%d.%m.%Y %H:%M') + ' (UTC)'
                if grant.expires_at:
                    entry['active_until'] = grant.expires_at.strftime('%d.%m.%Y %H:%M') + ' (UTC)'
                # БЪГ ФИКС: Purchase History картите (Basic/Plus) никога не
                # показваха собствения си subscription_code (BGxxxxxxxx),
                # въпреки че Custom Promo картите ('activated_codes' по-долу)
                # винаги са го показвали - неконсистентно, потребителят
                # виждаше ID само на едните.
                entry['subscription_code'] = get_or_create_subscription_code('plan', grant.id)
        result.append(entry)

    # Активирани промо кодове, КОИТО ТОЗИ потребител Е ИЗПОЛЗВАЛ, но НЕ Е
    # ПЛАТИЛ лично (получил ги е от друг) - отделна карта в Billing, за да
    # се вижда И реалният платец (само имейл), не само собствения достъп
    # (който вече се вижда в Usage таба).
    activated_codes = []
    my_gold_grants = GoldGrant.query.filter_by(user_id=user.id).order_by(GoldGrant.activated_at.desc()).all()
    for g in my_gold_grants:
        if not g.promo_code:
            continue
        promo = PromoCode.query.filter_by(code=g.promo_code).first()
        if not promo or not promo.created_by_user_id:
            continue
        if promo.created_by_user_id == user.id:
            continue  # той самият е купувачът - вече се вижда в 'payments' по-горе
        payer = User.query.get(promo.created_by_user_id)
        activated_codes.append({
            'plan': 'gold',
            'code': g.promo_code,
            'paid_by_email': payer.email if payer else 'Unknown',
            'active_from': g.activated_at.strftime('%d.%m.%Y %H:%M') + ' (UTC)' if g.activated_at else None,
            'active_until': g.expires_at.strftime('%d.%m.%Y %H:%M') + ' (UTC)' if g.expires_at else None,
        })

    # Custom Promo планове (PromoGrant) — нямат Payment запис (генерирани
    # от Admin, не от Stripe). Показваме ги в 'activated_codes' секцията
    # (същия стил като Gold кодове, получени от друг), защото имат идентична
    # структура: активация от Admin → достъп за потребителя без собствено плащане.
    my_promo_grants = PromoGrant.query.filter_by(user_id=user.id).order_by(PromoGrant.activated_at.desc()).all()
    for g in my_promo_grants:
        promo = PromoCode.query.filter_by(code=g.promo_code).first() if g.promo_code else None
        activated_codes.append({
            'plan': 'Custom',
            'code': g.promo_code or '',
            'paid_by_email': promo.client_name if promo and promo.client_name else 'Admin',
            'active_from': g.activated_at.strftime('%d.%m.%Y %H:%M') + ' (UTC)' if g.activated_at else None,
            'active_until': g.expires_at.strftime('%d.%m.%Y %H:%M') + ' (UTC)' if g.expires_at else None,
            'quota': g.quota,
            'days_remaining': max(0, (g.expires_at - now).days) if g.expires_at else None,
        })

    return result, activated_codes
