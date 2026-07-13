"""
app/utils/grant_cache.py
==========================
ИСТОРИЧЕСКА БЕЛЕЖКА: този модул преди имаше in-memory TTL кеш за
GoldGrant/PromoGrant/PlanGrant по потребител. Премахнат изцяло, защото
причини 2 отделни реални бъга в production: Railway стартира приложението
с `--workers 2` (виж Procfile/railway.toml) — 2 ОТДЕЛНИ Python процеса,
всеки със СВОЯ собствена копие на кеша (in-memory dict, не Redis/споделена
памет). invalidate_cached_grants() инвалидираше кеша само на worker-а,
обработил конкретната заявка (напр. POST /library/select) - ако
СЛЕДВАЩАТА заявка (GET /dashboard) попаднеше на ДРУГИЯ worker, той никога
не е бил инвалидиран и продължаваше да показва данни отпреди до 15
секунди. Резултат: потребител избира тест, вижда dashboard без него -
изглеждаше сякаш изборът не е минал, макар да Е записан коректно в базата.

fetch_all_grants() сега винаги чете директно от базата - никакво кеширане,
никаква възможност за stale данни между worker процеси. Малка загуба на
performance (1 допълнителна заявка на бързи последователни заявки), за
сметка на гарантирана коректност - приемлив компромис.
"""


def fetch_all_grants(user_id):
    """
    Връща (gold_grants, promo_grants, plan_grants) за потребителя - ВИНАГИ
    директно от базата, без кеширане (виж модул docstring за причината).
    PromoGrant е ОТДЕЛНА таблица от GoldGrant (по изрично искане - Promo и
    Gold са различни продукти, не споделена инфраструктура).
    """
    from app.models.gold_grant import GoldGrant
    from app.models.promo_grant import PromoGrant
    from app.models.plan_grant import PlanGrant
    gold_grants = GoldGrant.query.filter_by(user_id=user_id).all()
    promo_grants = PromoGrant.query.filter_by(user_id=user_id).all()
    plan_grants = PlanGrant.query.filter_by(user_id=user_id).all()
    return gold_grants, promo_grants, plan_grants


def invalidate_cached_grants(user_id):
    """No-op — запазена само за обратна съвместимост (извиквана от
    съществуващи caller-и след промяна на grant-ове). Няма какво да се
    инвалидира вече, тъй като fetch_all_grants() вече не кешира нищо."""
    pass
