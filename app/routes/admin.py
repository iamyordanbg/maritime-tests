from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.user import User
from app.models.test import Test, TestImage, DemoVisit
from app.models.result import TestResult
from app.models.payment import Payment
from app.models.signal import Signal
from app.models.ticket import Ticket, TicketMessage
from app.models.snapshot import MonthlySnapshot
from app.services.stats import get_admin_stats, record_monthly_snapshot
from app.utils.decorators import admin_required
from datetime import datetime, timedelta
import os, json

admin = Blueprint("admin", __name__, url_prefix="/admin")

@admin.route('/results/<int:result_id>')
@admin_required
def admin_result_detail(result_id):
    result = TestResult.query.get_or_404(result_id)
    test = Test.query.get(result.test_id)
    user = User.query.get(result.user_id)
    all_questions = test.get_questions()
    answers = json.loads(result.answers_json)

    # Ако имаме записани ID-та — показвай само тях
    try:
        q_ids = json.loads(result.question_ids_json or '[]')
    except:
        q_ids = []

    if q_ids:
        qid_set = set(str(q) for q in q_ids)
        questions = [q for q in all_questions if str(q['id']) in qid_set]
    else:
        answered_ids = set(answers.keys())
        questions = [q for q in all_questions if str(q['id']) in answered_ids] or all_questions

    # Зареди снимките
    from app.utils.images import inject_images
    questions = inject_images(result.test_id, questions)

    # Форматирай времето
    duration = result.duration or 0
    duration_str = f"{duration // 60:02d}:{duration % 60:02d}"

    # Тип на теста
    type_labels = {'test': 'Обикновен Тест', 'mix': 'Микс', 'simulator': 'Симулатор', 'mistakes': 'Грешки'}
    type_label = type_labels.get(result.test_type or 'test', 'Тест')

    return render_template('admin/result_detail.html',
        result=result, test=test, user=user,
        questions=questions, answers=answers,
        duration_str=duration_str, type_label=type_label)

@admin.route('/results/<int:result_id>/delete', methods=['POST'])
@admin_required
def delete_result(result_id):
    result = TestResult.query.get_or_404(result_id)
    db.session.delete(result)
    db.session.commit()
    return jsonify({'success': True})

@admin.route('/results/cleanup', methods=['POST'])
@admin_required
def cleanup_results():
    """Изтрива резултати по-стари от X дни"""
    days = int(request.json.get('days', 30))
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
    old_results = TestResult.query.filter(TestResult.taken_at < cutoff).all()
    count = len(old_results)
    for r in old_results:
        db.session.delete(r)
    db.session.commit()
    return jsonify({'success': True, 'deleted': count})

@admin.route('/results/cleanup-expired', methods=['POST'])
@admin_required
def cleanup_expired_results():
    """Изтрива резултати, чиито конкретен grant (по това време) вече е изтекъл — не по текущия общ статус на потребителя"""
    from app.models.gold_grant import GoldGrant
    from app.models.plan_grant import PlanGrant
    now = datetime.utcnow()
    all_results = TestResult.query.all()
    to_delete = []

    grants_cache = {}
    for r in all_results:
        if r.user_id not in grants_cache:
            grants_cache[r.user_id] = {
                'gold': GoldGrant.query.filter_by(user_id=r.user_id).all(),
                'plan': PlanGrant.query.filter_by(user_id=r.user_id).all(),
            }
        cache = grants_cache[r.user_id]

        is_active = False
        matched = False
        for g in cache['gold']:
            if r.test_id in g.test_id_list() and g.activated_at and g.activated_at <= r.taken_at:
                is_active = g.expires_at > now
                matched = True
                break
        if not matched:
            for g in cache['plan']:
                if g.library_test_id == r.test_id and g.activated_at and g.activated_at <= r.taken_at:
                    is_active = g.expires_at > now
                    matched = True
                    break

        if not is_active:
            to_delete.append(r)

    count = len(to_delete)
    for r in to_delete:
        db.session.delete(r)
    db.session.commit()
    return jsonify({'success': True, 'deleted': count})


@admin.route('/signals')
@admin_required
def admin_signals():
    signals = Signal.query.order_by(Signal.created_at.desc()).all()
    open_count = Signal.query.filter_by(status='open').count()
    return render_template('admin/signals.html', signals=signals, open_count=open_count)

@admin.route('/signals/<int:signal_id>/resolve', methods=['POST'])
@admin_required
def resolve_signal(signal_id):
    signal = Signal.query.get_or_404(signal_id)
    signal.status = 'resolved'
    db.session.commit()
    return jsonify({'success': True})

# ============================================================
#  ИНИЦИАЛИЗАЦИЯ
# ============================================================

from app.utils.codes import alternating_code, subscription_code, result_public_code, get_or_create_subscription_code, free_code
from app.utils.grants import find_result_grant as _find_result_grant
from app.utils.grants import auto_delete_expired_results as _auto_delete_expired_results


@admin.route('')
@admin_required
def admin_dashboard():
    from app.services.stats import get_admin_stats
    from app.models.result import TestResult
    stats = get_admin_stats()
    admin_user = User.query.filter_by(is_admin=True).first()
    now = datetime.utcnow()

    # Опортюнистично автоматично почистване — 30 дни grace период след изтичане
    auto_deleted = _auto_delete_expired_results()

    # Търсене в историята — по имейл, по заглавие на теста, ИЛИ по РЕАЛНИЯ
    # показван уникален код (напр. "BGS9A2B8...") - НЕ по суровото вътрешно
    # TestResult.id (число в базата, безсмислено за търсене от админ, тъй
    # като никъде не се показва). Кодът е ИЗЧИСЛЕНО Python свойство (зависи
    # от кой grant е покривал теста в момента на решаването), затова не може
    # да се филтрира directly в SQL - правим SQL филтър за имейл/тест, плюс
    # отделен Python pass за кода, върху разумно ограничен по-широк набор.
    search_q = (request.args.get('q') or '').strip()
    from app.models.gold_grant import GoldGrant
    from app.models.plan_grant import PlanGrant
    from app.utils.grants import find_result_grant as _find_result_grant_early

    if search_q:
        # 1) Бърз SQL филтър - имейл на потребителя ИЛИ заглавие на теста.
        sql_matches = (TestResult.query
                       .options(db.joinedload(TestResult.user), db.joinedload(TestResult.test))
                       .join(User, TestResult.user_id == User.id)
                       .join(Test, TestResult.test_id == Test.id)
                       .filter(db.or_(
                           User.email.ilike(f'%{search_q}%'),
                           Test.title.ilike(f'%{search_q}%'),
                       ))
                       .order_by(TestResult.taken_at.desc())
                       .limit(50).all())

        # 2) Ако е ПОХОЖЕ на код (има поне 1 буква + 1 цифра) - допълнително
        #    претърсваме разумно ограничен по-широк набор (последните 3000
        #    резултата) по РЕАЛНИЯ изчислен показван код за всеки от тях.
        code_matches = []
        if any(c.isalpha() for c in search_q) and any(c.isdigit() for c in search_q):
            candidates = (TestResult.query
                          .options(db.joinedload(TestResult.user), db.joinedload(TestResult.test))
                          .order_by(TestResult.taken_at.desc())
                          .limit(3000).all())
            _cand_uids = list({r.user_id for r in candidates})
            _cand_gold = GoldGrant.query.filter(GoldGrant.user_id.in_(_cand_uids)).all() if _cand_uids else []
            from app.models.promo_grant import PromoGrant
            from app.models.free_session import FreeSession
            _cand_promo = PromoGrant.query.filter(PromoGrant.user_id.in_(_cand_uids)).all() if _cand_uids else []
            _cand_plan = PlanGrant.query.filter(PlanGrant.user_id.in_(_cand_uids)).all() if _cand_uids else []
            _cand_free = FreeSession.query.filter(FreeSession.user_id.in_(_cand_uids)).all() if _cand_uids else []
            _cand_gold_c = {uid: [g for g in _cand_gold if g.user_id == uid] for uid in _cand_uids}
            _cand_promo_c = {uid: [g for g in _cand_promo if g.user_id == uid] for uid in _cand_uids}
            _cand_plan_c = {uid: [g for g in _cand_plan if g.user_id == uid] for uid in _cand_uids}
            _cand_free_c = {uid: [g for g in _cand_free if g.user_id == uid] for uid in _cand_uids}
            q_lower = search_q.lower()
            for r in candidates:
                _, _grant = _find_result_grant_early(r, now, _cand_gold_c, _cand_plan_c, _cand_promo_c, _cand_free_c)
                if _grant:
                    _gt = 'gold' if hasattr(_grant, 'test_id_list') else 'plan'
                    _base = _grant.promo_code if _gt == 'gold' else get_or_create_subscription_code('plan', _grant.id)
                    _base = _base or subscription_code(_grant.id, grant_type=_gt)
                    candidate_code = f"{_base}{r.taken_at.strftime('%d%m%y')}-000"[:len(_base) + 6]  # база+дата, без seq за бързо сравнение
                    if q_lower in _base.lower():
                        code_matches.append(r)
                        continue
                if q_lower in (r.display_id or '').lower():
                    code_matches.append(r)

        # Обединяваме (без дубликати), запазваме реда по дата.
        seen_ids = set()
        recent_results = []
        for r in (sql_matches + code_matches):
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                recent_results.append(r)
        recent_results.sort(key=lambda r: r.taken_at, reverse=True)
        recent_results = recent_results[:50]
    else:
        recent_results = (TestResult.query
                           .options(db.joinedload(TestResult.user), db.joinedload(TestResult.test))
                           .order_by(TestResult.taken_at.desc())
                           .limit(10).all())

    # Статус на плана — ПО РЕЗУЛТАТ, не по потребител! Намираме КОНКРЕТНИЯ grant,
    # който е покривал точно ТОЗИ тест по времето на решаването му, и проверяваме
    # дали ИМЕННО ТОЗИ grant все още е активен — не дали потребителят има ДРУГ,
    # несвързан, по-нов план в момента (иначе стар изтекъл резултат лъжливо
    # показва "Active" само защото user-ът е активирал нещо ново оттогава).
    plan_status_by_result_id = {}
    plan_type_by_result_id = {}
    public_code_by_result_id = {}
    from app.models.gold_grant import GoldGrant
    from app.models.promo_grant import PromoGrant
    from app.models.plan_grant import PlanGrant
    from app.models.free_session import FreeSession
    _unique_uids = list({r.user_id for r in recent_results})
    _all_gold = GoldGrant.query.filter(GoldGrant.user_id.in_(_unique_uids)).all() if _unique_uids else []
    _all_promo = PromoGrant.query.filter(PromoGrant.user_id.in_(_unique_uids)).all() if _unique_uids else []
    _all_plan = PlanGrant.query.filter(PlanGrant.user_id.in_(_unique_uids)).all() if _unique_uids else []
    _all_free = FreeSession.query.filter(FreeSession.user_id.in_(_unique_uids)).all() if _unique_uids else []
    gold_cache, promo_cache, plan_cache, free_cache = {}, {}, {}, {}
    for _uid in _unique_uids:
        gold_cache[_uid] = [g for g in _all_gold if g.user_id == _uid]
        promo_cache[_uid] = [g for g in _all_promo if g.user_id == _uid]
        plan_cache[_uid] = [g for g in _all_plan if g.user_id == _uid]
        free_cache[_uid] = [g for g in _all_free if g.user_id == _uid]
    # Преди цикъла: зареждаме ВСИЧКИ резултати на засегнатите потребители в
    # ЕДНА заявка (вместо да удряме базата с отделен COUNT за всеки ред по-долу
    # - това беше N+1 проблем, причиняващ забавяне при зареждане на dashboard-а).
    _all_user_results = (TestResult.query
                          .filter(TestResult.user_id.in_(_unique_uids))
                          .with_entities(TestResult.id, TestResult.user_id, TestResult.test_id, TestResult.taken_at)
                          .all()) if _unique_uids else []
    _results_by_uid = {}
    for _rid, _ruid, _rtest_id, _rtaken_at in _all_user_results:
        _results_by_uid.setdefault(_ruid, []).append((_rtest_id, _rtaken_at))

    for r in recent_results:
        status, grant = _find_result_grant(r, now, gold_cache, plan_cache, promo_cache, free_cache)
        plan_status_by_result_id[r.id] = status

        if grant:
            # БЪГ ФИКС: hasattr(grant,'test_id_list') различава само Gold/
            # Promo от "останалото" - но "останалото" може да е ИЛИ
            # PlanGrant (.plan/.library_test_id) ИЛИ FreeSession (нито едно
            # от двете полета) - старият код третираше FreeSession като
            # PlanGrant и гърмеше с AttributeError на /admin.
            _grant_type_early = (
                'gold' if hasattr(grant, 'test_id_list')
                else 'free' if isinstance(grant, FreeSession)
                else 'plan'
            )
            if _grant_type_early == 'gold':
                from app.utils.grants import grant_plan_label
                plan_type_by_result_id[r.id] = grant_plan_label(grant)
            elif _grant_type_early == 'free':
                plan_type_by_result_id[r.id] = 'Free'
            else:
                plan_type_by_result_id[r.id] = grant.plan.capitalize()
        else:
            plan_type_by_result_id[r.id] = 'Free'

        if grant:
            if hasattr(grant, 'test_id_list'):
                grant_test_ids = set(grant.test_id_list())
            elif isinstance(grant, FreeSession):
                grant_test_ids = {grant.test_id}
            else:
                grant_test_ids = {grant.library_test_id}
            seq = sum(
                1 for _test_id, _taken_at in _results_by_uid.get(r.user_id, [])
                if _test_id in grant_test_ids and grant.activated_at <= _taken_at <= r.taken_at
            )
            _grant_type = (
                'gold' if hasattr(grant, 'test_id_list')
                else 'free' if isinstance(grant, FreeSession)
                else 'plan'
            )
            if _grant_type == 'free':
                # Free сесия няма платен абонамент, но има собствена детерминирана
                # код-схема (free_code() - 3 Букви+3 Цифри групирани, различна
                # scramble математика от subscription_code(), 0% колизия с
                # платени кодове) - СЪЩАТА, вече ползвана от TestResult.display_id
                # /dashboard.py api_history - за консистентност навсякъде.
                _base_code = f"BG{free_code(r.user_id)}"
                public_code_by_result_id[r.id] = f"{_base_code}{r.taken_at.strftime('%d%m%y')}-{seq:03d}"
            else:
                # ПОПРАВКА (същия бъг като user-ската история, вижте
                # dashboard.py): за Gold ползваме РЕАЛНИЯ активиран код
                # (grant.promo_code), не преизчислен нов от grant.id.
                if _grant_type == 'gold':
                    _base_code = grant.promo_code or subscription_code(grant.id, grant_type='gold')
                else:
                    _base_code = get_or_create_subscription_code('plan', grant.id)
                public_code_by_result_id[r.id] = f"{_base_code}{r.taken_at.strftime('%d%m%y')}-{seq:03d}"
        else:
            public_code_by_result_id[r.id] = None

    recent_signals = []
    return render_template('admin/dashboard.html',
        admin_user=admin_user,
        public_code_by_result_id=public_code_by_result_id,
        recent_results=recent_results,
        plan_status_by_result_id=plan_status_by_result_id,
        plan_type_by_result_id=plan_type_by_result_id,
        search_q=search_q,
        auto_deleted=auto_deleted,
        recent_signals=recent_signals,
        **stats)

@admin.route('/tests')
@admin_required
def admin_tests():
    deck_tests = Test.query.filter_by(category='deck').order_by(Test.created_at.desc()).all()
    engine_tests = Test.query.filter_by(category='engine').order_by(Test.created_at.desc()).all()
    admin_user = User.query.filter_by(is_admin=True).first()
    deck_q = sum(t.question_count for t in deck_tests)
    engine_q = sum(t.question_count for t in engine_tests)
    mistakes_ready = False
    demo_sessions = 0
    return render_template('admin/tests.html',
        deck_tests=deck_tests, engine_tests=engine_tests,
        deck_q=deck_q, engine_q=engine_q,
        mistakes_ready=mistakes_ready, admin_user=admin_user)

@admin.route('/demo')
@admin_required
def admin_demo():
    tests = Test.query.filter_by(is_demo=True).order_by(Test.created_at.desc()).all()
    deck_demo = sum(1 for t in tests if t.category == 'deck')
    engine_demo = sum(1 for t in tests if t.category == 'engine')
    demo_count = len(tests)
    admin_user = User.query.filter_by(is_admin=True).first()
    return render_template('admin/demo.html',
        tests=tests, deck_demo=deck_demo,
        engine_demo=engine_demo, demo_count=demo_count,
        admin_user=admin_user)

@admin.route('/demo/toggle/<int:test_id>', methods=['POST'])
@admin_required
def admin_demo_toggle(test_id):
    test = Test.query.get_or_404(test_id)
    test.is_demo = not test.is_demo
    db.session.commit()
    return jsonify({'success': True, 'is_demo': test.is_demo})

@admin.route('/tests/next-title')
@admin_required
def next_title():
    title = request.args.get('title', '').strip()
    if not title:
        return jsonify({'exists': False, 'title': title})
    existing = Test.query.filter_by(title=title).first()
    if not existing:
        return jsonify({'exists': False, 'title': title})
    counter = 2
    while True:
        new_title = f"{title} ({counter})"
        if not Test.query.filter_by(title=new_title).first():
            return jsonify({'exists': True, 'title': new_title})
        counter += 1


# Admin support routes → app/routes/admin_support.py

@admin.route('/api/snapshots/<metric>')
@admin_required
def admin_snapshots(metric):
    from app.services.stats import get_admin_stats
    period = request.args.get('period', '1Y')
    snapshots = MonthlySnapshot.query.order_by(MonthlySnapshot.recorded_at).all()
    labels = [s.recorded_at.strftime('%b %Y') for s in snapshots]
    data = [getattr(s, metric, 0) or 0 for s in snapshots]
    return jsonify({'metric': metric, 'labels': labels, 'data': data})

@admin.route('/api/snapshots/record', methods=['POST'])
@admin_required
def admin_record_snapshot():
    from app.services.stats import record_monthly_snapshot
    record_monthly_snapshot()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Еднократна поправка: акаунти, автоматично ъпгрейднати на Gold от стар бъг
# (webhook-ът задаваше user.plan='gold' директно на купувача, вместо да чака
# той сам да активира код през /activate). Засегнати: plan='gold' И
# gold_test_ids празно (никога не са минали през реалната активация).
# ---------------------------------------------------------------------------

def _find_gold_autobug_users():
    """Връща list от (user, proposed_plan, reason) за преглед преди поправка."""
    affected = User.query.filter(
        User.plan == 'gold',
        User.gold_test_ids.is_(None)
    ).all()

    results = []
    now = datetime.utcnow()
    for u in affected:
        # Търсим последно платено НЕ-gold плащане — то не е пипано от бъга
        last_other = (Payment.query
                      .filter(Payment.user_id == u.id, Payment.plan != 'gold')
                      .order_by(Payment.paid_at.desc())
                      .first())

        if last_other and u.plan_expires_at and u.plan_expires_at > now:
            proposed_plan = last_other.plan
            reason = f"Има валиден {last_other.plan} до {u.plan_expires_at.strftime('%d.%m.%Y')} (плащане от {last_other.paid_at.strftime('%d.%m.%Y')})"
        else:
            proposed_plan = 'free'
            reason = "Няма валидно предишно плащане с неизтекъл достъп — връщаме на free"

        results.append({'user': u, 'proposed_plan': proposed_plan, 'reason': reason})
    return results


@admin.route('/fix-gold-autobug')
@admin_required
def fix_gold_autobug_preview():
    """Dry-run — само показва какво ще се промени, нищо не пипа."""
    rows = _find_gold_autobug_users()
    return render_template('admin/fix_gold_autobug.html', rows=rows)


@admin.route('/fix-gold-autobug/apply', methods=['POST'])
@admin_required
def fix_gold_autobug_apply():
    rows = _find_gold_autobug_users()
    now = datetime.utcnow()
    fixed = 0

    for row in rows:
        u = row['user']
        if row['proposed_plan'] == 'free':
            u.plan = 'free'
            u.is_active = False
            u.plan_activated_at = None
            u.plan_expires_at = None
        else:
            u.plan = row['proposed_plan']
            u.is_active = True
        fixed += 1

    db.session.commit()
    flash(f'Поправени {fixed} акаунта, засегнати от Gold auto-upgrade бъга.', 'success')
    return redirect(url_for('admin.admin_promos'))


# ---------------------------------------------------------------------------
# Реклами (Free план + demo тестове) — показвани на всеки 5-ти въпрос
# ---------------------------------------------------------------------------

@admin.route('/ads')
@admin_required
def admin_ads():
    from app.models.ad import Ad
    ads = Ad.query.order_by(Ad.created_at.desc()).all()
    return render_template('admin/ads.html', ads=ads)


@admin.route('/ads/create', methods=['POST'])
@admin_required
def create_ad():
    from app.models.ad import Ad
    ad = Ad(
        title=request.form.get('title', '').strip(),
        image_url=request.form.get('image_url', '').strip() or None,
        link_url=request.form.get('link_url', '').strip() or None,
        body=request.form.get('body', '').strip() or None,
        is_active=True,
    )
    if not ad.title:
        return jsonify({'success': False, 'message': 'Заглавието е задължително.'}), 400
    db.session.add(ad)
    db.session.commit()
    return jsonify({'success': True, 'id': ad.id})


@admin.route('/ads/<int:ad_id>/toggle', methods=['POST'])
@admin_required
def toggle_ad(ad_id):
    from app.models.ad import Ad
    ad = Ad.query.get_or_404(ad_id)
    ad.is_active = not ad.is_active
    db.session.commit()
    return jsonify({'success': True, 'is_active': ad.is_active})


@admin.route('/ads/<int:ad_id>/delete', methods=['POST'])
@admin_required
def delete_ad(ad_id):
    from app.models.ad import Ad
    ad = Ad.query.get_or_404(ad_id)
    db.session.delete(ad)
    db.session.commit()
    return jsonify({'success': True})


# ── Support Center (от admin_support.py) ──

@admin.route('/support/start/<int:user_id>', methods=['POST'])
@admin_required
def admin_support_start(user_id):
    """
    Admin-ът стартира НОВ разговор с потребител, който още няма никакъв
    ticket - преди тази промяна нямаше начин admin да ИНИЦИИРА съобщение,
    само да отговаря на вече съществуващи, отворени от потребителя tickets.
    """
    from app.models.ticket import TicketMessage
    user = User.query.get_or_404(user_id)
    body = (request.get_json(silent=True) or {}).get('body', '').strip()
    if not body:
        return jsonify({'success': False, 'message': 'Empty message'}), 400

    ticket = Ticket(user_id=user.id, subject='Admin message', type='question', status='in_progress')
    db.session.add(ticket)
    db.session.flush()
    msg = TicketMessage(ticket_id=ticket.id, sender='admin', body=body, is_read=False)
    db.session.add(msg)
    db.session.commit()
    return jsonify({'success': True, 'ticket_id': ticket.id})

@admin.route('/support')
@admin_required
def admin_support_page():
    """
    ВАЖНО: темплейтът очаква {% set t = item.ticket %}{% set u = item.user %}
    и item.unread за всеки ред - преди тази поправка тук се подаваха голи
    Ticket обекти директно (tickets_query.all()), които нямат .ticket/.user
    атрибути -> Jinja UndefinedError -> 500 грешка на ВСЯКА заявка към тази
    страница, щом има поне 1 реален ticket в базата. Точно затова 'Message
    in Support Chat' изглеждаше 'несвързано' - страницата зад него беше
    напълно счупена.
    """
    from types import SimpleNamespace
    from app.models.ticket import TicketMessage

    filter_user_id = request.args.get('user_id', type=int)
    tickets_query = Ticket.query.order_by(Ticket.created_at.desc())
    if filter_user_id:
        tickets_query = tickets_query.filter_by(user_id=filter_user_id)
    raw_tickets = tickets_query.all()

    # Batch-ваме двете заявки, които преди се изпълняваха ПООТДЕЛНО за
    # всеки ticket (N+1 проблем, причиняващ бавно зареждане при много тикети).
    ticket_ids = [t.id for t in raw_tickets]
    unread_by_ticket = {}
    if ticket_ids:
        _unread_counts = (db.session.query(TicketMessage.ticket_id, db.func.count(TicketMessage.id))
                           .filter(TicketMessage.ticket_id.in_(ticket_ids),
                                   TicketMessage.sender == 'user',
                                   TicketMessage.is_read == False)
                           .group_by(TicketMessage.ticket_id).all())
        unread_by_ticket = dict(_unread_counts)

    _ticket_user_ids = list({t.user_id for t in raw_tickets})
    users_by_id = {u.id: u for u in User.query.filter(User.id.in_(_ticket_user_ids)).all()} if _ticket_user_ids else {}

    tickets = []
    for t in raw_tickets:
        unread = unread_by_ticket.get(t.id, 0)
        u = users_by_id.get(t.user_id)
        tickets.append(SimpleNamespace(ticket=t, user=u, unread=unread))

    admin_user = User.query.filter_by(is_admin=True).first()
    filter_user = User.query.get(filter_user_id) if filter_user_id else None
    return render_template('admin/support.html', tickets=tickets, admin_user=admin_user, filter_user=filter_user)

@admin.route('/support/tickets')
@admin_required
def admin_support_tickets():
    from app.models.ticket import TicketMessage
    tickets = Ticket.query.order_by(Ticket.updated_at.desc()).all()
    result = []
    for t in tickets:
        unread = TicketMessage.query.filter_by(ticket_id=t.id, sender='user', is_read=False).count()
        user = User.query.get(t.user_id)
        result.append({
            'id': t.id, 'email': user.email if user else '', 'name': user.name if user else '',
            'type': t.type, 'status': t.status, 'unread': unread,
            'created_at': t.created_at.strftime('%d.%m %H:%M')
        })
    return jsonify(result)

@admin.route('/support/<int:ticket_id>/messages')
@admin_required
def admin_ticket_messages(ticket_id):
    from app.models.ticket import TicketMessage
    ticket = Ticket.query.get_or_404(ticket_id)
    user = User.query.get(ticket.user_id)
    messages = TicketMessage.query.filter_by(ticket_id=ticket_id).order_by(TicketMessage.created_at).all()
    TicketMessage.query.filter_by(ticket_id=ticket_id, sender='user', is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({
        'ticket': {'id': ticket.id, 'type': ticket.type, 'status': ticket.status},
        'user': {'email': user.email if user else '', 'name': user.name if user else ''},
        'messages': [{'id': m.id, 'body': m.body, 'sender': m.sender,
                      'created_at': m.created_at.strftime('%d.%m %H:%M')} for m in messages]
    })

@admin.route('/support/<int:ticket_id>/reply', methods=['POST'])
@admin_required
def admin_ticket_reply(ticket_id):
    from app.models.ticket import TicketMessage
    ticket = Ticket.query.get_or_404(ticket_id)
    body = request.form.get('body', '').strip()
    if not body:
        return jsonify({'success': False})
    msg = TicketMessage(ticket_id=ticket_id, sender='admin', body=body, is_read=False)
    ticket.status = 'in_progress'
    ticket.updated_at = datetime.utcnow()
    db.session.add(msg)
    db.session.commit()
    return jsonify({'success': True})

@admin.route('/support/<int:ticket_id>/close', methods=['POST'])
@admin_required
def admin_ticket_close(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    ticket.status = 'closed'
    ticket.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})

@admin.route('/support/unread')
@admin_required
def admin_support_unread():
    from app.models.ticket import TicketMessage
    count = TicketMessage.query.filter_by(sender='user', is_read=False).count()
    return jsonify({'count': count})

@admin.route('/support/stats')
@admin_required
def admin_support_stats():
    pending = Ticket.query.filter(Ticket.status != 'closed').count()
    total = Ticket.query.count()
    return jsonify({'pending': pending, 'total': total})

