"""
Еднократен migration скрипт: прехвърля съществуващите снимки от Postgres
(TestImage.image_data, base64, storage='db') към Cloudflare R2.

Пуска се РЪЧНО на Railway (или локално с реалния DATABASE_URL), след като
R2 env variables вече са настроени. Безопасен за повторно пускане —
прескача записите, вече мигрирани (storage='r2').

Употреба:
    python3 scripts/migrate_images_to_r2.py
"""
import sys, os, base64
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.test import TestImage
from app.utils import r2_storage


def main():
    if not r2_storage.is_r2_configured():
        print("❌ R2 is not configured (env variables are missing). Stopping.")
        return

    app = create_app()
    with app.app_context():
        rows = TestImage.query.filter_by(storage='db').all()
        total = len(rows)
        print(f"Found {total} images to migrate from Postgres to R2...")

        migrated, failed = 0, 0
        for i, row in enumerate(rows, 1):
            if not row.image_data:
                continue
            try:
                img_bytes = base64.b64decode(row.image_data)
                fmt = row.format or 'jpg'
                r2_storage.upload_image(row.test_id, row.question_id, img_bytes, fmt)
                row.r2_key = r2_storage._key_for(row.test_id, row.question_id, fmt)
                row.storage = 'r2'
                row.image_data = None  # освобождава мястото в Postgres
                migrated += 1
            except Exception as e:
                failed += 1
                print(f"  ❌ Error at test {row.test_id} / q {row.question_id}: {e}")

            if i % 50 == 0:
                db.session.commit()
                print(f"  ... {i}/{total} processed")

        db.session.commit()
        print(f"✅ Done: {migrated} migrated successfully, {failed} errors.")


if __name__ == '__main__':
    main()
