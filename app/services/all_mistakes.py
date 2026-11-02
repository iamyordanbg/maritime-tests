"""
app/services/all_mistakes.py
============================
"All Mistakes": всички допуснати грешки по даден тест от активирането на плана му, събрани
в отделен тест.

Кой има достъп (по grant, за тестовете на този grant):
  - Basic/Plus (PlanGrant): ако PLANS[plan]['display']['all_errors'] е включено (Plus);
  - Gold (GoldGrant): ако PLANS['gold']['display']['all_errors'] е включено;
  - Custom Promo (PromoGrant): само ако промо кодът е създаден с включена функция.
Достъпът трае до края на grant-а; Gold/Promo имат и grace период (grace_until). В grace
въпросите вече не се добавят (няма нови решени тестове), но старите могат да се решават.

Списъкът с грешки се смята на момента от запазените отговори (TestResult.answers_json) -
не се пази отделно, затова нови грешки се появяват автоматично до края на абонамента.
"""
import json
from datetime import datetime

from app.models.gold_grant import GoldGrant
from app.models.plan_grant import PlanGrant
from app.models.promo_grant import PromoGrant
from app.models.result import TestResult
from app.models.test import Test
from app.services.plans import PLANS

TEST_TYPE = 'all_mistakes'

# Решаването на All Mistakes не изразходва тест от квотата и не се блокира от изчерпана квота
# (засега безплатно). Едно място за промяна, ако това се смени.
CONSUMES_QUOTA = False

# Етикети на типовете решаване - единствено място (ползва се от History, Result review, Dashboard).
TEST_TYPE_LABELS = {
    'test': 'Test', 'mix': 'Mix', 'mistakes': 'Mistakes',
    'all_mistakes': 'All Mistakes', 'simulator': 'Simulator',
}


def plan_has_all_mistakes(plan_key):
    """Функцията е ли включена в плана - единственият източник е PLANS[...]['display']['all_errors']."""
    return bool(PLANS.get(plan_key, {}).get('display', {}).get('all_errors'))


def apply_promo_flags(grant, promo):
    """Копира флага на Custom промо кода в PromoGrant при активация (GoldGrant няма такъв флаг)."""
    if isinstance(grant, PromoGrant):
        grant.all_mistakes = bool(getattr(promo, 'all_mistakes', False))


def _status(grant, now):
    """'active' / 'grace' / None за даден grant."""
    if grant.expires_at and grant.expires_at > now:
        return 'active'
    grace_until = getattr(grant, 'grace_until', None)
    if grace_until and grant.expires_at and grant.expires_at <= now <= grace_until:
        return 'grace'
    return None


def _grants_with_feature(user_id):
    """(grant, [test_id, ...]) за всеки grant на потребителя, който включва функцията."""
    out = []
    for g in PlanGrant.query.filter_by(user_id=user_id).all():
        if plan_has_all_mistakes(g.plan) and g.library_test_id:
            out.append((g, [g.library_test_id]))
    if plan_has_all_mistakes('gold'):
        for g in GoldGrant.query.filter_by(user_id=user_id).all():
            out.append((g, g.test_id_list()))
    for g in PromoGrant.query.filter_by(user_id=user_id, all_mistakes=True).all():
        out.append((g, g.test_id_list()))
    return out


def entitlements(user, now=None):
    """{test_id: {'grant', 'start', 'ends_at', 'in_grace'}} за тестове с достъп до функцията.

    Няколко grant-а за един тест: старт = най-ранното активиране, активен grant бие grace,
    краят е най-късният измежду grant-овете от същия вид.
    """
    now = now or datetime.utcnow()
    per_test = {}
    for grant, test_ids in _grants_with_feature(user.id):
        status = _status(grant, now)
        if not status:
            continue
        ends_at = grant.grace_until if status == 'grace' else grant.expires_at
        for tid in test_ids:
            per_test.setdefault(tid, []).append((grant, status, ends_at))
    result = {}
    for tid, items in per_test.items():
        pool = [i for i in items if i[1] == 'active'] or items
        grant, status, _ = max(pool, key=lambda i: i[2])
        starts = [i[0].activated_at for i in items if i[0].activated_at]
        result[tid] = {'grant': grant, 'start': min(starts) if starts else None,
                       'ends_at': max(i[2] for i in pool), 'in_grace': status == 'grace'}
    return result


def wrong_question_ids(user_id, test, start=None):
    """Множество от id (str) на въпроси, отговорени грешно поне веднъж в решение на теста след `start`."""
    questions = {str(q['id']): q for q in test.get_questions()}
    query = TestResult.query.filter_by(user_id=user_id, test_id=test.id)
    if start:
        query = query.filter(TestResult.taken_at >= start)
    wrong = set()
    for res in query.all():
        try:
            answers = json.loads(res.answers_json or '{}')
        except ValueError:
            continue
        for qid, idx in answers.items():
            q = questions.get(str(qid))
            if not q:
                continue
            try:
                correct = q['options'][int(idx)]['isCorrect']
            except (IndexError, KeyError, ValueError, TypeError):
                correct = False
            if not correct:
                wrong.add(str(qid))
    return wrong


def entitlement_for_test(user, test_id, now=None):
    """Entitlement dict за теста или None (няма достъп до функцията за него)."""
    return entitlements(user, now).get(test_id)


def user_has_feature(user, now=None):
    return bool(entitlements(user, now))


def summary(user, now=None):
    """Редове за страницата: по един на тест с достъп (брой грешки, до кога е достъпно)."""
    ents = entitlements(user, now)
    if not ents:
        return []
    tests = {t.id: t for t in Test.query.filter(Test.id.in_(list(ents))).all()}
    rows = []
    for tid, ent in ents.items():
        test = tests.get(tid)
        if not test:
            continue
        rows.append({'test': test, 'wrong_count': len(wrong_question_ids(user.id, test, ent['start'])),
                     'ends_at': ent['ends_at'], 'in_grace': ent['in_grace']})
    rows.sort(key=lambda r: r['test'].title)
    return rows


def feature_available_to_plan_card():
    """Какви планове включват функцията (за текста на заключената страница)."""
    return [PLANS[k]['name'] for k in ('plus', 'gold') if plan_has_all_mistakes(k)]
