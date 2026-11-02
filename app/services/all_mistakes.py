"""
app/services/all_mistakes.py
============================
"All Mistakes": всички допуснати грешки по даден тест от активирането на плана му, събрани
в отделен тест.

Кой има функцията (по grant, за тестовете на този grant):
  - Basic/Plus (PlanGrant): ако PLANS[plan]['display']['all_errors'] е включено (Plus);
  - Gold (GoldGrant): ако PLANS['gold']['display']['all_errors'] е включено;
  - Custom Promo (PromoGrant): само ако промо кодът е създаден с включена функция.

Отключва се за тест след ALL_MISTAKES['unlock_tests'] решени Test/Mix/Simulator по него.
Режими на достъп за тест (виж entitlements):
  - 'active'  - абонаментът е активен: преглед + решаване, всяко решаване харчи 1 кредит от квотата;
  - 'review'  - до ALL_MISTAKES['review_days'] след края му: само преглед на грешките (с верните
                отговори); решаването иска платен достъп (виж all_mistakes_pass.py);
  - 'pass'    - платен достъп (ALL_MISTAKES['days'] дни, ALL_MISTAKES['tests_quota'] решавания).
Грешките се трупат до края на абонамента; списъкът се смята на момента от TestResult.answers_json.
"""

import json
from datetime import datetime, timedelta

from app.models.all_mistakes_pass import AllMistakesPass
from app.models.gold_grant import GoldGrant
from app.models.plan_grant import PlanGrant
from app.models.promo_grant import PromoGrant
from app.models.result import TestResult
from app.models.test import Test
from app.services.plans import PLANS, ALL_MISTAKES

TEST_TYPE = 'all_mistakes'

UNLOCK_TEST_TYPES = ('test', 'mix', 'simulator')

# Етикети на типовете решаване - единствено място (ползва се от History, Result review, Dashboard).
TEST_TYPE_LABELS = {
    'test': 'Test', 'mix': 'Mix', 'mistakes': 'Mistakes',
    'all_mistakes': 'All Mistakes', 'simulator': 'Simulator',
}


def grant_test_ids(grant):
    """Тестовете, за които важи даден grant (Gold/Promo - списък, Basic/Plus - избраният)."""
    if hasattr(grant, 'test_id_list'):
        return grant.test_id_list()
    return [grant.library_test_id] if grant.library_test_id else []


def _results(user_id, test_ids, since):
    return TestResult.query.filter(TestResult.user_id == user_id, TestResult.test_id.in_(test_ids),
                                   TestResult.taken_at >= since)


def quota_used(user_id, test_ids, since):
    """Колко кредита от квотата са изразходвани: всички решавания по тези тестове (включително
    All Mistakes - всяко харчи 1). Единственото място, което брои квота - ползва се от картите,
    My Usage и проверката за заключване."""
    if not test_ids:
        return 0
    return _results(user_id, test_ids, since).count()


def unlock_progress(user_id, test_id, start):
    """(решени обикновени теста, нужни) за отключване на All Mistakes по този тест."""
    query = TestResult.query.filter(TestResult.user_id == user_id, TestResult.test_id == test_id,
                                    TestResult.test_type.in_(UNLOCK_TEST_TYPES))
    if start:
        query = query.filter(TestResult.taken_at >= start)
    return query.count(), ALL_MISTAKES['unlock_tests']


def is_unlocked(user_id, test_id, start):
    solved, needed = unlock_progress(user_id, test_id, start)
    return solved >= needed


def plan_has_all_mistakes(plan_key):
    """Функцията е ли включена в плана - единственият източник е PLANS[...]['display']['all_errors']."""
    return bool(PLANS.get(plan_key, {}).get('display', {}).get('all_errors'))


def apply_promo_flags(grant, promo):
    """Копира флага на Custom промо кода в PromoGrant при активация (GoldGrant няма такъв флаг)."""
    if isinstance(grant, PromoGrant):
        grant.all_mistakes = bool(getattr(promo, 'all_mistakes', False))


def _status(grant, now):
    """'active' / 'review' (в рамките на review_days след края) / None за даден grant."""
    if not grant.expires_at:
        return None
    if grant.expires_at > now:
        return 'active'
    if now <= grant.expires_at + timedelta(days=ALL_MISTAKES['review_days']):
        return 'review'
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
    """{test_id: {...}} за тестовете, до които потребителят има достъп до All Mistakes сега.

    Ключове: mode ('active'/'pass'/'review'), grant (активният, иначе най-късно изтеклият), start
    (най-ранното активиране), sub_end (край на абонамента - до него се трупат грешки), ends_at
    (до кога важи режимът), pass_ (активният платен достъп или None).
    Няколко grant-а за един тест: старт = най-ранният, край на абонамента = най-късният.
    """
    now = now or datetime.utcnow()
    per_test = {}
    for grant, test_ids in _grants_with_feature(user.id):
        for tid in test_ids:
            per_test.setdefault(tid, []).append(grant)
    passes = {p.test_id: p for p in AllMistakesPass.query.filter(
        AllMistakesPass.user_id == user.id, AllMistakesPass.expires_at > now).all()}
    result = {}
    for tid, grants in per_test.items():
        statuses = [(g, _status(g, now)) for g in grants]
        active = [g for g, st in statuses if st == 'active']
        review = [g for g, st in statuses if st == 'review']
        starts = [g.activated_at for g in grants if g.activated_at]
        base = {'start': min(starts) if starts else None, 'sub_end': max(g.expires_at for g in grants),
                'pass_': passes.get(tid)}
        if active:
            grant = max(active, key=lambda g: g.expires_at)
            result[tid] = dict(base, mode='active', grant=grant, ends_at=grant.expires_at)
        elif tid in passes:
            grant = max(grants, key=lambda g: g.expires_at)
            result[tid] = dict(base, mode='pass', grant=grant, ends_at=passes[tid].expires_at)
        elif review:
            grant = max(review, key=lambda g: g.expires_at)
            result[tid] = dict(base, mode='review', grant=grant,
                               ends_at=grant.expires_at + timedelta(days=ALL_MISTAKES['review_days']))
    return result


def wrong_question_ids(user_id, test, start=None, until=None):
    """Множество от id (str) на въпроси, отговорени грешно поне веднъж в решение на теста между
    `start` и `until` (края на абонамента - след него нови грешки не се добавят)."""
    questions = {str(q['id']): q for q in test.get_questions()}
    query = TestResult.query.filter_by(user_id=user_id, test_id=test.id)
    if start:
        query = query.filter(TestResult.taken_at >= start)
    if until:
        query = query.filter(TestResult.taken_at <= until)
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


def mistakes_of(user_id, test, ent):
    """Грешките по теста за дадения entitlement (до края на абонамента)."""
    return wrong_question_ids(user_id, test, ent['start'], ent['sub_end'])


def pass_runs_used(user_id, p):
    """Колко решавания на All Mistakes са изразходвани от платения достъп."""
    return TestResult.query.filter(TestResult.user_id == user_id, TestResult.test_id == p.test_id,
                                   TestResult.test_type == TEST_TYPE,
                                   TestResult.taken_at >= p.activated_at).count()


def submit_decision(user, test_id):
    """Може ли да се запише решаване на All Mistakes. Връща (грешка|None, съобщение, skip_quota).

    skip_quota: решаването е по платен достъп - има собствен брояч и не пипа квотата на плана."""
    ent = entitlement_for_test(user, test_id)
    if ent is None or not is_unlocked(user.id, test_id, ent['start']):
        return 'not_allowed', 'All Mistakes is not available for this test yet.', False
    if ent['mode'] == 'review':
        return 'purchase_required', 'Your subscription has ended - buy All Mistakes access to solve.', False
    if ent['mode'] == 'pass':
        if pass_runs_used(user.id, ent['pass_']) >= ent['pass_'].quota:
            return 'quota_exceeded', 'You have used all solves of your All Mistakes access.', False
        return None, '', True
    return None, '', False


def summary(user, now=None):
    """Редове за страницата: по един на тест с достъп (брой грешки, режим, остатък)."""
    ents = entitlements(user, now)
    if not ents:
        return []
    tests = {t.id: t for t in Test.query.filter(Test.id.in_(list(ents))).all()}
    rows = []
    for tid, ent in ents.items():
        test = tests.get(tid)
        if not test:
            continue
        solved, needed = unlock_progress(user.id, tid, ent['start'])
        unlocked = solved >= needed
        p = ent['pass_']
        rows.append({'test': test, 'mode': ent['mode'], 'unlocked': unlocked,
                     'tests_to_go': max(0, needed - solved),
                     'wrong_count': len(mistakes_of(user.id, test, ent)) if unlocked else 0,
                     'ends_at': ent['ends_at'],
                     'pass_left': max(0, p.quota - pass_runs_used(user.id, p)) if p else None,
                     'pass_quota': p.quota if p else None})
    rows.sort(key=lambda r: r['test'].title)
    return rows


def feature_available_to_plan_card():
    """Какви планове включват функцията (за текста на заключената страница)."""
    return [PLANS[k]['name'] for k in ('plus', 'gold') if plan_has_all_mistakes(k)]
