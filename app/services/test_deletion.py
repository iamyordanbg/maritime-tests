"""
app/services/test_deletion.py
=============================
Пълно изтриване на тест заедно с всичко, което сочи към него.

Postgres налага FK ограничения (SQLite в dev/тестовете - не), затова всички
записи, свързани с теста, се махат ПРЕДИ самия Test. Всичко е в една
транзакция: при грешка нищо не се губи (rollback), а снимките от R2 се
трият чак след успешния commit.

Какво се прави със свързаните записи:
- резултати, безплатни сесии (free_session), All Mistakes изключения,
  снимки -> изтриват се;
- user.library_test_id и plan_grant.library_test_id (избран тест в акаунта /
  в покупка) -> зачистват се (клиентът избира друг тест); самите плащания и
  планове остават непокътнати.
"""
from app.extensions import db
from app.models.test import Test
from app.models.result import TestResult
from app.models.user import User
from app.models.free_session import FreeSession
from app.models.plan_grant import PlanGrant
from app.models.all_mistakes_exclusion import AllMistakesExclusion
from app.utils.images import remove_test_image_rows, delete_r2_images


def delete_test_completely(test):
    """Изтрива теста и всички свързани записи. При грешка прави rollback и
    повдига изключението нагоре."""
    test_id = test.id
    try:
        TestResult.query.filter_by(test_id=test_id).delete()
        FreeSession.query.filter_by(test_id=test_id).delete()
        AllMistakesExclusion.query.filter_by(test_id=test_id).delete()
        User.query.filter_by(library_test_id=test_id).update(
            {'library_test_id': None, 'library_selected_at': None})
        PlanGrant.query.filter_by(library_test_id=test_id).update(
            {'library_test_id': None, 'library_selected_at': None})
        r2_items = remove_test_image_rows(test_id)
        db.session.delete(test)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    delete_r2_images(test_id, r2_items)
