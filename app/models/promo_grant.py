"""
app/models/promo_grant.py
==========================
Отделен от GoldGrant - по изрично искане. Преди тази промяна, активиране
на Custom Promo код (PromoCode.is_custom=True, ръчно генериран от admin в
Plans & Promo формата) създаваше GoldGrant ред - СЪЩАТА таблица като
стандартните Gold 10-пакет кодове (Stripe покупка). Технически работеше
(is_custom флагът вече разграничаваше типа за DISPLAY цели), но
архитектурно Promo и Gold са различни продукти и трябва да имат отделни
таблици - не споделена инфраструктура.

Всяка активация на Custom Promo код създава свой собствен, напълно
автономен PromoGrant запис - свои тестове, свой лимит, свой срок.
Структурата огледално копира GoldGrant (същите полета/методи), за да
остане логиката за четене/изчисляване на квота идентична и предвидима.
"""

from datetime import datetime
from ..extensions import db


class PromoGrant(db.Model):
    __tablename__ = 'promo_grant'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    department = db.Column(db.String(10))          # deck / engine
    level = db.Column(db.String(50))                # Operational Level / Management Level
    test_ids = db.Column(db.Text, nullable=False)    # JSON [id1, id2]

    quota = db.Column(db.Integer, default=50)
    tests_used = db.Column(db.Integer, default=0)

    activated_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    grace_until = db.Column(db.DateTime, nullable=True)

    promo_code = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def test_id_list(self):
        import json
        try:
            return json.loads(self.test_ids or '[]')
        except Exception:
            return []

    def is_active(self, now=None):
        now = now or datetime.utcnow()
        return self.expires_at and self.expires_at > now

    def in_grace(self, now=None):
        now = now or datetime.utcnow()
        return self.expires_at and self.grace_until and self.expires_at <= now <= self.grace_until
