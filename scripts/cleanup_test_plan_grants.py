"""
Еднократен cleanup скрипт: трие всички Basic/Plus PlanGrant записи за
конкретен потребител (по имейл) — за изчистване на тестовите покупки,
натрупани по време на TESTING_MODE checkout тестове.

БЕЗОПАСНО: пипа само PlanGrant таблицата (не Payment история, не Gold
grant-ове, не самия User запис) — само "активния достъп" записите.

Употреба (на Railway, през Railway CLI shell):
    python3 scripts/cleanup_test_plan_grants.py your@email.com

Или за да изтриеш САМО изтеклите (запазвайки активните):
    python3 scripts/cleanup_test_plan_grants.py your@email.com --expired-only
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.plan_grant import PlanGrant
from datetime import datetime


def main():
    if len(sys.argv) < 2:
        print("Употреба: python3 scripts/cleanup_test_plan_grants.py <email> [--expired-only]")
        return

    email = sys.argv[1]
    expired_only = '--expired-only' in sys.argv

    app = create_app()
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"❌ Няма потребител с email {email}")
            return

        query = PlanGrant.query.filter_by(user_id=user.id)
        if expired_only:
            query = query.filter(PlanGrant.expires_at <= datetime.utcnow())

        grants = query.all()
        if not grants:
            print(f"Няма grant-ове за изтриване (потребител {email}, expired_only={expired_only}).")
            return

        print(f"Намерени {len(grants)} PlanGrant записа за {email}:")
        for g in grants:
            status = "АКТИВЕН" if g.expires_at > datetime.utcnow() else "изтекъл"
            print(f"  #{g.id}  {g.plan}  ({status}, изтича {g.expires_at})")

        confirm = input(f"\nИзтрий тези {len(grants)} записа? (yes/no): ")
        if confirm.strip().lower() != 'yes':
            print("Отказано.")
            return

        for g in grants:
            db.session.delete(g)
        db.session.commit()

        from app.utils.grant_cache import invalidate_cached_grants
        invalidate_cached_grants(user.id)

        print(f"✅ Изтрити {len(grants)} PlanGrant записа за {email}.")


if __name__ == '__main__':
    main()
