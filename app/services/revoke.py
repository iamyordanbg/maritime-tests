"""
app/services/revoke.py
======================
Меко отнемане на достъп от админ: планът спира веднага, но Payment/PromoCode/Grant
редовете ОСТАВАТ - клиентът вижда пълната си история (активни и неактивни), а
тестовите му резултати и броячи не се губят. Скрива се само от админ списъка.
"""
from datetime import datetime


def _end_grant(grant, now):
    """Прекратява достъпа по grant (не го трие)."""
    if grant.expires_at and grant.expires_at > now:
        grant.expires_at = now
    if getattr(grant, 'grace_until', None):
        grant.grace_until = None


def revoke_payment(payment, now=None):
    """Basic/Plus/All Mistakes плащане: спира свързания достъп, пази реда."""
    from app.models.plan_grant import PlanGrant
    now = now or datetime.utcnow()
    for g in PlanGrant.query.filter_by(payment_id=payment.id).all():
        _end_grant(g, now)
    from app.models.all_mistakes_pass import AllMistakesPass
    for ps in AllMistakesPass.query.filter_by(payment_id=payment.id).all():
        _end_grant(ps, now)
    payment.revoked_at = now


def revoke_promo(promo, now=None):
    """Gold/Custom код: блокира активиране и спира вече активираните grant-ове, пази реда."""
    from app.models.gold_grant import GoldGrant
    from app.models.promo_grant import PromoGrant
    now = now or datetime.utcnow()
    for model in (GoldGrant, PromoGrant):
        for g in model.query.filter_by(promo_code=promo.code).all():
            _end_grant(g, now)
    if not promo.is_used and (not promo.expires_at or promo.expires_at > now):
        promo.expires_at = now   # стоящ в stand-by код вече не може да се активира
    promo.is_active = False
    promo.revoked_at = now
