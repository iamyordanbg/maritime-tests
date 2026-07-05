"""
Снимки към тестови въпроси.

Две хранилища, преход в движение:
- НОВО (storage='r2'): байтовете живеят в Cloudflare R2, базата пази само
  reference (r2_key). Снимката се сервира с директен redirect към R2
  публичния URL — сървърът дори не пипа байтовете.
- СТАРО (storage='db'): base64 в Postgres TestImage.image_data — както
  преди R2 setup-а. Оставено за обратна съвместимост, докато не се
  мигрират съществуващите записи (виж scripts/migrate_images_to_r2.py).

Ако R2 env variables липсват (R2_ACCOUNT_ID и т.н.), save_test_images()
автоматично пада обратно на 'db' режим — за локална разработка без R2
достъп, без да чупи нищо.
"""
import base64
from app.extensions import db
from app.models.test import TestImage
from app.utils import r2_storage


def inject_images(test_id, questions):
    """Добавя URL към снимката за всеки въпрос, маркиран has_image=True."""
    rows = TestImage.query.filter_by(test_id=test_id).all()
    by_question = {r.question_id: r for r in rows}

    loaded = 0
    r2_loaded = 0
    for q in questions:
        if q.get('has_image'):
            row = by_question.get(q['id'])
            if row:
                if row.storage == 'r2' and row.r2_key:
                    q['image'] = r2_storage.public_url_for(row.r2_key)
                    r2_loaded += 1
                else:
                    q['image'] = f"/qimage/{test_id}/{q['id']}.{row.format or 'jpg'}"
                loaded += 1
    print(f"INJECT: Loaded {loaded} images for test {test_id} ({r2_loaded} от R2, {loaded - r2_loaded} от базата)")
    return questions


def save_test_images(test_id, images):
    """
    Записва/презаписва снимки за даден тест.
    images: списък от (question_id, (raw_bytes, format)) двойки.

    Ако R2 е конфигуриран — качва в R2, базата пази само reference.
    Иначе (локална разработка без R2) — пада обратно на base64 в Postgres.
    """
    use_r2 = r2_storage.is_r2_configured()
    saved = 0
    for q_id, payload in images:
        try:
            img_bytes, fmt = payload
            existing = TestImage.query.filter_by(test_id=test_id, question_id=q_id).first()

            if use_r2:
                r2_storage.upload_image(test_id, q_id, img_bytes, fmt)
                key = r2_storage._key_for(test_id, q_id, fmt)
                if existing:
                    existing.image_data = None
                    existing.format = fmt
                    existing.storage = 'r2'
                    existing.r2_key = key
                else:
                    db.session.add(TestImage(test_id=test_id, question_id=q_id,
                                              image_data=None, format=fmt,
                                              storage='r2', r2_key=key))
            else:
                b64 = base64.b64encode(img_bytes).decode('ascii')
                if existing:
                    existing.image_data = b64
                    existing.format = fmt
                    existing.storage = 'db'
                    existing.r2_key = None
                else:
                    db.session.add(TestImage(test_id=test_id, question_id=q_id,
                                              image_data=b64, format=fmt, storage='db'))
            saved += 1
        except Exception as e:
            print(f"IMAGES: Save error q{q_id}: {e}")
    db.session.commit()
    dest = 'R2' if use_r2 else 'Postgres (R2 не е конфигуриран)'
    print(f"IMAGES: Saved {saved}/{len(images)} images to {dest} for test {test_id}")
    return saved


def get_image_bytes(test_id, question_id):
    """Връща (raw_bytes, format) за конкретна снимка от базата (само за
    storage='db' записи — R2 снимките се сервират чрез redirect, не оттук)."""
    row = TestImage.query.filter_by(test_id=test_id, question_id=question_id).first()
    if not row or row.storage == 'r2' or not row.image_data:
        return None
    return base64.b64decode(row.image_data), (row.format or 'jpg')


def delete_test_images(test_id):
    """Изтрива всички снимки на даден тест (при триене на теста) —
    и от R2 (ако там са), и от базата."""
    rows = TestImage.query.filter_by(test_id=test_id).all()
    r2_items = [(r.question_id, r.format or 'jpg') for r in rows if r.storage == 'r2']
    if r2_items and r2_storage.is_r2_configured():
        try:
            r2_storage.delete_all_for_test(test_id, r2_items)
        except Exception as e:
            print(f"IMAGES: R2 delete error for test {test_id}: {e}")
    TestImage.query.filter_by(test_id=test_id).delete()
    db.session.commit()
