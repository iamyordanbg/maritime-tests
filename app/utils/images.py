"""
Снимки към тестови въпроси — trайно съхранение в PostgreSQL (TestImage
таблица), НЕ на диска на Railway контейнера. Причина: /tmp (и всяко друго
локално файлово хранилище на контейнера) е ephemeral — изтрива се напълно
при всеки redeploy. Тъй като базата вече е доказано trайна (persistent
Postgres инстанция), снимките живеят там, като всичко останало.
"""
import base64
from app.extensions import db
from app.models.test import TestImage


def inject_images(test_id, questions):
    """Добавя URL към снимката за всеки въпрос, маркиран has_image=True,
    ако реално съществува съответен TestImage запис в базата."""
    rows = TestImage.query.filter_by(test_id=test_id).all()
    by_question = {r.question_id: r for r in rows}

    loaded = 0
    for q in questions:
        if q.get('has_image'):
            row = by_question.get(q['id'])
            if row:
                q['image'] = f"/qimage/{test_id}/{q['id']}.{row.format or 'jpg'}"
                loaded += 1
    print(f"INJECT: Loaded {loaded} images for test {test_id} (от базата)")
    return questions


def save_test_images(test_id, images):
    """
    Записва/презаписва снимки за даден тест в базата.
    images: списък от (question_id, (raw_bytes, format)) двойки — същия
    формат, който parse_xls_colors() вече извлича от Excel файла.
    """
    saved = 0
    for q_id, payload in images:
        try:
            img_bytes, fmt = payload
            b64 = base64.b64encode(img_bytes).decode('ascii')
            existing = TestImage.query.filter_by(test_id=test_id, question_id=q_id).first()
            if existing:
                existing.image_data = b64
                existing.format = fmt
            else:
                db.session.add(TestImage(test_id=test_id, question_id=q_id,
                                          image_data=b64, format=fmt))
            saved += 1
        except Exception as e:
            print(f"IMAGES: Save error q{q_id}: {e}")
    db.session.commit()
    print(f"IMAGES: Saved {saved}/{len(images)} images to DB for test {test_id}")
    return saved


def get_image_bytes(test_id, question_id):
    """Връща (raw_bytes, format) за конкретна снимка, или None ако липсва."""
    row = TestImage.query.filter_by(test_id=test_id, question_id=question_id).first()
    if not row:
        return None
    return base64.b64decode(row.image_data), (row.format or 'jpg')


def delete_test_images(test_id):
    """Изтрива всички снимки на даден тест (при триене на теста)."""
    TestImage.query.filter_by(test_id=test_id).delete()
    db.session.commit()
