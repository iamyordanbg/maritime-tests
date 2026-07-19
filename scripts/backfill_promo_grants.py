"""
Еднократен backfill скрипт: премества legacy GoldGrant записи в PromoGrant.

КОНТЕКСТ: преди PR #13 (merge 2026-07-12 19:40 UTC), activate.py винаги
създаваше GoldGrant при активация на промо код, независимо от
PromoCode.is_custom флага. Custom Promo кодове, активирани ПРЕДИ тази
дата, реално седят като GoldGrant записи в базата - показват се като
"Gold" в admin панела вместо "Custom", въпреки че display логиката вече
е поправена (тя чете правилно КАКВОТО Е в базата, но данните са в
грешната таблица).

Този скрипт намира GoldGrant записи, чийто promo_code сочи към
PromoCode.is_custom=True, и ги премества в PromoGrant (нов ред със
същите стойности + изтриване на стария GoldGrant ред).

БЕЗОПАСНО: пипа само записи, свързани с is_custom=True промо кодове.
Истински Gold кодове (Stripe покупки, is_custom=False) НЕ се пипат.

Употреба (на Railway, през Railway CLI shell):
    python3 scripts/backfill_promo_grants.py            # dry-run (само показва какво ще направи)
    python3 scripts/backfill_promo_grants.py --apply     # реално мести записите
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.gold_grant import GoldGrant
from app.models.promo_grant import PromoGrant
from app.models.promo import PromoCode


def main():
    apply = '--apply' in sys.argv

    app = create_app()
    with app.app_context():
        all_gold = GoldGrant.query.filter(GoldGrant.promo_code.isnot(None)).all()

        to_migrate = []
        for g in all_gold:
            promo = PromoCode.query.filter_by(code=g.promo_code).first()
            if promo and promo.is_custom:
                to_migrate.append((g, promo))

        if not to_migrate:
            print("✓ Няма legacy GoldGrant записи за Custom Promo кодове - нищо за мигриране.")
            return

        print(f"Намерени {len(to_migrate)} legacy GoldGrant записа за Custom Promo кодове:")
        for g, promo in to_migrate:
            print(f"  - GoldGrant #{g.id}, код={g.promo_code}, user_id={g.user_id}, "
                  f"client={promo.client_name}, activated_at={g.activated_at}")

        if not apply:
            print("\n(dry-run - нищо не е променено. Пусни с --apply за реално мигриране.)")
            return

        migrated = 0
        for g, promo in to_migrate:
            new_grant = PromoGrant(
                user_id=g.user_id, department=g.department, level=g.level,
                test_ids=g.test_ids, quota=g.quota, tests_used=g.tests_used,
                activated_at=g.activated_at, expires_at=g.expires_at,
                grace_until=g.grace_until, promo_code=g.promo_code,
                created_at=g.created_at,
            )
            db.session.add(new_grant)
            db.session.delete(g)
            migrated += 1

        db.session.commit()
        print(f"\n✓ Мигрирани {migrated} записа от GoldGrant в PromoGrant.")


if __name__ == '__main__':
    main()
