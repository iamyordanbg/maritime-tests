"""
app/utils/grants.py
=====================
Споделена логика за намиране на КОНКРЕТНИЯ grant (Gold или Basic/Plus),
покривал точно даден тест по времето на решаването му. Ползва се и от
admin.py (Last Results таблица), и от dashboard.py (собствена история
на потребителя) — за да няма дублиране и разминаване на логиката.
"""


def find_result_grant(r, now, gold_cache=None, plan_cache=None):
    """
    Връща (is_active: bool, grant или None).
    gold_cache/plan_cache — по избор, {user_id: [grants]} за преизползване
    между много резултати на един и същ потребител (избягва повторни заявки).

    ПОПРАВКА: ако ДВА (или повече) активни Gold/Plan grant-а покриват СЪЩИЯ
    test_id (напр. потребител активира 2 Gold кода, и вторият код по
    съвпадение включва същия тест като първия) - предпочитаме НАЙ-СКОРО
    АКТИВИРАНИЯ grant, не първия по ред в базата (който е бил произволно
    най-старият/вече изчерпан). Иначе нови резултати продължават да се
    трупат към изчерпан grant, докато по-свеж, с останала квота, стои
    неизползван - объркващо в историята (виждано реално от потребител).
    """
    from app.models.gold_grant import GoldGrant
    from app.models.plan_grant import PlanGrant
    from app.models.free_session import FreeSession

    if gold_cache is not None:
        if r.user_id not in gold_cache:
            gold_cache[r.user_id] = GoldGrant.query.filter_by(user_id=r.user_id).all()
        gold_grants = gold_cache[r.user_id]
    else:
        gold_grants = GoldGrant.query.filter_by(user_id=r.user_id).all()

    matching_gold = [g for g in gold_grants
                      if r.test_id in g.test_id_list() and g.activated_at and g.activated_at <= r.taken_at]
    if matching_gold:
        best = max(matching_gold, key=lambda g: g.activated_at)
        return best.expires_at > now, best

    if plan_cache is not None:
        if r.user_id not in plan_cache:
            plan_cache[r.user_id] = PlanGrant.query.filter_by(user_id=r.user_id).all()
        plan_grants = plan_cache[r.user_id]
    else:
        plan_grants = PlanGrant.query.filter_by(user_id=r.user_id, library_test_id=r.test_id).all()

    matching_plan = [g for g in plan_grants
                      if g.library_test_id == r.test_id and g.activated_at and g.activated_at <= r.taken_at]
    if matching_plan:
        best = max(matching_plan, key=lambda g: g.activated_at)
        return best.expires_at > now, best

    # Free план - преди тази поправка НЕ се проверяваше тук изобщо, вместо
    # това result_visible() имаше СПЕЦИАЛЕН клон за Free (броене direct от
    # taken_at, не от истинско изтичане на достъпа) - неконсистентно с
    # Basic/Plus/Gold/Promo, които ВСИЧКИ ползват "30 дни СЛЕД изтичане на
    # КОНКРЕТНИЯ план" правилото. FreeSession си има собствен expires_at
    # (виж модела) - вече се третира по СЪЩИЯ унифициран начин.
    free_sessions = FreeSession.query.filter_by(user_id=r.user_id, test_id=r.test_id).all()
    matching_free = [g for g in free_sessions if g.activated_at and g.activated_at <= r.taken_at]
    if matching_free:
        best = max(matching_free, key=lambda g: g.activated_at)
        return best.expires_at > now, best

    return False, None


# Колко дни след изтичане на конкретния grant резултатът остава видим в
# историята на потребителя, преди да бъде окончателно скрит/изтрит.
HISTORY_GRACE_DAYS = 30


def result_visible(r, is_active, grant, now):
    """
    Дали даден резултат трябва да се показва в историята в момента.
    - Активен grant (Basic/Plus/Gold/Promo/Free - ВСИЧКИ еднакво) → винаги видим.
    - Изтекъл grant → видим само до HISTORY_GRACE_DAYS след expires_at.
      Важи ЕДНАКВО за всички типове план, без изключение (виж
      find_result_grant() - Free вече минава през FreeSession.expires_at,
      не отделен special-case тук).
    - Няма никакъв grant изобщо (стари/несигурни данни, отпреди тази
      логика е съществувала) → не пипаме, винаги видим.
    """
    if is_active:
        return True
    if grant:
        return (now - grant.expires_at).days < HISTORY_GRACE_DAYS

    return True


def auto_delete_expired_results(grace_days=HISTORY_GRACE_DAYS):
    """
    Автоматично трие резултати, чийто конкретен grant е изтекъл преди
    ПОВЕЧЕ ОТ grace_days дни. Вика се опортюнистично при зареждане на
    admin dashboard-а И на потребителска история/dashboard (няма отделен
    cron в тази среда).
    """
    from datetime import datetime, timedelta
    from app.extensions import db
    from app.models.result import TestResult

    now = datetime.utcnow()
    cutoff_candidates = now - timedelta(days=grace_days)
    # Само резултати, взети достатъчно отдавна, за да е изобщо възможно
    # техният grace период вече да е минал — пести ненужна работа.
    candidates = TestResult.query.filter(TestResult.taken_at < cutoff_candidates).all()

    gold_cache, plan_cache = {}, {}
    deleted = 0
    for r in candidates:
        is_active, grant = find_result_grant(r, now, gold_cache, plan_cache)
        if is_active:
            continue
        if grant:
            if (now - grant.expires_at).days >= grace_days:
                db.session.delete(r)
                deleted += 1
            continue
        # Няма НИКАКЪВ grant (нито Gold/Plan/Promo, нито FreeSession) -
        # стари/несигурни данни отпреди тази логика е съществувала. Не
        # трием - винаги пазим, за да не изгубим нещо неволно.

    if deleted:
        db.session.commit()
    return deleted


def grant_real_used(grant, user_id):
    """
    Реален брой решени тестове за дадения grant — броени ДИРЕКТНО от
    TestResult записите (същия начин, по който dashboard.py изчислява
    показания на картата брояч "X/Y"), НЕ от съхраненото grant.tests_used
    поле. Полето може да се разсинхронизира с реалността (пропуснат
    increment, стар код, ръчна admin промяна и т.н.) — затова единственият
    надежден източник на истина е самата TestResult таблица, същата, която
    вижда потребителят на екрана си.

    GoldGrant: брои само тестовете от собствения test_ids списък (Gold
    дава достъп до КУРИРАН набор тестове по департамент/ниво, избрани при
    активация на кода).

    PlanGrant (Basic/Plus): брои само решенията на КОНКРЕТНО избрания
    library_test_id тест (клиентът избира 1 тест от цялата библиотека
    през Library, но лимитът важи само за него — не за всички тестове
    едновременно). Ако все още няма избран тест (library_test_id=None),
    връща 0 (нищо не е решено под този grant все още).
    """
    from app.models.result import TestResult

    if hasattr(grant, 'test_id_list'):  # GoldGrant
        test_ids = grant.test_id_list()
        if not test_ids:
            return 0
        return (TestResult.query
                .filter(TestResult.user_id == user_id,
                        TestResult.test_id.in_(test_ids),
                        TestResult.taken_at >= grant.activated_at)
                .count())
    else:  # PlanGrant — само избрания тест
        if not grant.library_test_id:
            return 0
        return (TestResult.query
                .filter(TestResult.user_id == user_id,
                        TestResult.test_id == grant.library_test_id,
                        TestResult.taken_at >= grant.activated_at)
                .count())


def find_active_grant_for_test(user, test_id, now=None):
    """
    Намира АКТИВНИЯ Gold/PlanGrant, който в момента покрива test_id за дадения
    потребител (за разлика от find_result_grant, който гледа кой grant е
    покривал резултат В МИНАЛОТО по taken_at). Ползва се за проверка дали
    потребителят все още има оставащ лимит ПРЕДИ да зареди/реши тест.

    ВАЖНО: търси ЕДНОВРЕМЕННО в GoldGrant И PlanGrant, независимо от
    user.plan полето — потребител може да държи Gold И Basic И Plus grants
    ИСТОВРЕМЕННО (всяка покупка е автономна карта, виж app/services/plans.py),
    user.plan е само легаси поле (отразява последно-изтичащия grant, НЕ
    списъка от активни grants). Клонове по user.plan тук биха пропуснали
    grant-а, който реално покрива test_id, ако той е от "другия" тип спрямо
    каквото user.plan случайно казва в момента.

    GoldGrant покрива само test_id-та от собствения си списък. PlanGrant
    (Basic/Plus) покрива САМО конкретния library_test_id, избран от
    клиента през Library — 1 тест наведнъж на grant, не цялата библиотека
    едновременно (клиентът може да избере КОЙ ДА Е тест от библиотеката,
    но само 1 активен избор наведнъж; вижте claim_waiting_grant_for_test
    за преизбиране, когато лимитът е изчерпан).

    Ако НЯКОЛКО активни grant-а покриват същия test_id — връща ПЪРВИЯ С
    ОСТАВАЩ КАПАЦИТЕТ (по РЕАЛНО преброени резултати, виж grant_real_used),
    не просто първия по ред от заявката. Само ако ВСИЧКИ покриващи grant-ове
    са изчерпани, връща (произволен) от тях — за коректно съобщение
    "лимитът е изчерпан".

    Връща grant обект или None (напр. free план, demo тест, или тест извън
    всеки grant).
    """
    from datetime import datetime
    now = now or datetime.utcnow()

    from app.models.gold_grant import GoldGrant
    from app.models.plan_grant import PlanGrant
    from app.models.test import Test

    test = Test.query.get(test_id)
    if test and test.is_demo:
        return None  # demo — извън grant системата изцяло, винаги свободен

    gold_grants = (GoldGrant.query
                   .filter(GoldGrant.user_id == user.id, GoldGrant.expires_at > now)
                   .all())
    plan_grants = (PlanGrant.query
                   .filter(PlanGrant.user_id == user.id, PlanGrant.expires_at > now)
                   .all())

    matches = [g for g in gold_grants if test_id in g.test_id_list()]
    matches += [g for g in plan_grants if g.library_test_id == test_id]

    if not matches:
        return None

    for g in matches:
        if grant_real_used(g, user.id) < g.quota:
            return g
    return matches[0]


def grant_quota_exceeded(grant, user_id):
    """
    Дали дадения grant е изчерпал напълно лимита си от тестове — ползва
    РЕАЛНО преброени TestResult записи (grant_real_used), не съхраненото
    tests_used поле, за да съвпада на 100% с брояча, който потребителят
    вижда на картата в dashboard-а.
    """
    if not grant:
        return False
    return grant_real_used(grant, user_id) >= grant.quota


def find_any_grant_ever_for_test(user, test_id):
    """
    Намира КОЙТО И ДА Е Gold/PlanGrant на потребителя, покривал test_id -
    БЕЗ филтър по expires_at (за разлика от find_active_grant_for_test).
    Търси в ОБЕ таблици. GoldGrant — само ако test_id е в собствения му
    списък. PlanGrant — само ако library_test_id съвпада с test_id.
    Ползва се само за да различим "имало е покриващ grant, но е ИЗТЕКЪЛ по
    време" от "този тест никога не е бил в обхвата на никой негов план"
    (последното се управлява от друга логика — user_can_access_test).
    """
    from app.models.gold_grant import GoldGrant
    from app.models.plan_grant import PlanGrant
    from app.models.test import Test

    test = Test.query.get(test_id)
    if test and test.is_demo:
        return None

    gold_grants = GoldGrant.query.filter_by(user_id=user.id).all()
    plan_grants = PlanGrant.query.filter_by(user_id=user.id, library_test_id=test_id).all()

    matches = [g for g in gold_grants if test_id in g.test_id_list()]
    matches += plan_grants
    return matches[0] if matches else None


# ---------------------------------------------------------------------------
# ЗАКОНЪТ: два брояча контролират достъпа до решаване на тест — ОСТАВАЩИ
# ТЕСТОВЕ и ОСТАВАЩО ВРЕМЕ. Ако КОЙТО И ДА Е от двата стигне 0 — СТОП.
# Кодът никога не позволява зареждане на нов тест, независимо от функцията
# (TEST/MIX/MISTAKES/SIM) и независимо от плана (Basic/Plus/Gold), докато
# абонаментът не бъде подновен или ъпгрейднат. Тази функция е ЕДИНСТВЕНАТА
# точка, която прилага закона — всеки route/каунтър го вика оттук, не
# преизобретява собствена версия на проверката.
# ---------------------------------------------------------------------------

def claim_waiting_grant_for_test(user, test_id, now=None):
    """
    Ако потребителят има свободен (чакащ избор на тест) PlanGrant — активен,
    неизтекъл, с library_test_id все още None (напр. току-що закупен нов
    Basic/Plus план) — обвързва го с test_id и връща grant-а. Иначе None.

    Само за PlanGrant (Basic/Plus) — Gold работи различно (test_ids се
    задават наведнъж при активация на кода, няма аналогично "чакащо" поле).

    Ползва се от test_access_lock(), за да не блокира достъпа до тест, който
    вече е бил избран от СТАР (изчерпан/изтекъл) grant, докато потребителят
    има съвсем свободен нов grant, който просто никога не е бил обвързан —
    UI-то показва такъв тест като "вече избран" (dropdown "Open"), затова
    никога не минава през /library/select, за да завърже новия grant.
    """
    from datetime import datetime
    from app.extensions import db
    from app.models.plan_grant import PlanGrant

    now = now or datetime.utcnow()
    waiting_grant = (PlanGrant.query
                      .filter(PlanGrant.user_id == user.id,
                              PlanGrant.expires_at > now,
                              PlanGrant.library_test_id.is_(None))
                      .order_by(PlanGrant.activated_at.asc())
                      .first())
    if not waiting_grant:
        return None
    if grant_real_used(waiting_grant, user.id) >= waiting_grant.quota:
        return None  # изчерпан е — не го "claim-вай", остави да падне към LOCKED

    waiting_grant.library_test_id = test_id
    waiting_grant.library_selected_at = now
    db.session.commit()
    return waiting_grant


def test_access_lock(user, test_id, now=None):
    """
    Единна проверка дали достъпът до test_id трябва да е ЗАКЛЮЧЕН:
    - Оставащо ВРЕМЕ = 0 (всички grant-ове, покривали този тест, вече са
      изтекли по expires_at) → LOCKED.
    - Оставащи ТЕСТОВЕ = 0 (активният, неизтекъл grant е изчерпал реалния
      си лимит) → LOCKED.
    - ИЗКЛЮЧЕНИЕ: ако няма покриващ grant с капацитет, но потребителят има
      СЪВСЕМ СВОБОДЕН (чакащ избор) PlanGrant — автоматично се обвързва с
      този test_id (виж claim_waiting_grant_for_test) и достъпът НЕ се
      заключва. Това пресъздава очакваното поведение: с наличен нов/платен
      план потребителят може да зареди кой да е тест (освен demo), дори
      ако UI-то вече го показва като "избран" от друг, изчерпан grant.

    Прилага се еднакво за Gold/Basic/Plus — НЕ гейтва по user.plan полето
    (доказано ненадеждно/легаси, виж find_active_grant_for_test), а по
    реалното наличие на GoldGrant/PlanGrant записи, покриващи ИМЕННО този
    test_id. Admin винаги минава с LOCKED=False. Потребител без НИКАКЪВ
    grant (нито активен, нито изтекъл) за този test_id — чист free план
    сценарий, управляван от отделната library-window логика, не тук.

    Връща (locked: bool, active_grant или None). active_grant е неизтеклия
    grant (ако има такъв) — ползва се после за increment на legacy tests_used
    полето при submit.
    """
    from datetime import datetime
    if not user or getattr(user, 'is_admin', False):
        return False, None

    now = now or datetime.utcnow()
    active_grant = find_active_grant_for_test(user, test_id, now)
    if active_grant and not grant_quota_exceeded(active_grant, user.id):
        return False, active_grant  # има покриващ grant С капацитет — директен достъп

    # Или няма никакъв покриващ grant, или намереният е ИЗЧЕРПАН — преди да
    # заключим, провери дали има СЪВСЕМ СВОБОДЕН нов grant, който просто
    # чака да бъде обвързан с този тест.
    claimed = claim_waiting_grant_for_test(user, test_id, now)
    if claimed:
        return False, claimed

    if active_grant:
        return True, active_grant  # изчерпан е и няма свободен grant да го спаси

    # test_id не съвпада с НИТО ЕДИН от активните (неизтекли) grant-ове на
    # потребителя в момента. Две причини за това:
    # (1) Потребителят ИМА активен grant, но той сочи КЪМ ДРУГ тест (или е
    #     преизбрал нанякъде другаде) — този test_id просто не е текущият
    #     му избор -> LOCKED, трябва да го избере през Library, ако иска.
    # (2) Потребителят НЯМА никакъв активен grant в момента — или защото
    #     никога не е имал (чист free план — не пипаме, друга логика), или
    #     защото ВСИЧКИ негови grant-ове са изтекли по ВРЕМЕ -> LOCKED.
    from app.models.gold_grant import GoldGrant
    from app.models.plan_grant import PlanGrant

    has_any_active_grant = (
        GoldGrant.query.filter(GoldGrant.user_id == user.id, GoldGrant.expires_at > now).count() > 0
        or PlanGrant.query.filter(PlanGrant.user_id == user.id, PlanGrant.expires_at > now).count() > 0
    )
    if has_any_active_grant:
        return True, None  # има активен план, но не за ТОЗИ тест — LOCKED

    has_ever_had_any_grant = (
        GoldGrant.query.filter_by(user_id=user.id).count() > 0
        or PlanGrant.query.filter_by(user_id=user.id).count() > 0
    )
    return has_ever_had_any_grant, None
