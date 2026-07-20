"""
app/routes/admin_promos_mgmt.py
=================================
Admin: Promo codes (Gold/Custom) + Payments management — extraction-нат
от admin.py (Group A audit, File Limits).
"""
from flask import Blueprint, render_template, request, jsonify
from app.extensions import db
from app.models.user import User
from app.models.promo import PromoCode
from app.models.payment import Payment
from app.utils.decorators import admin_required
from datetime import datetime, timedelta

admin_promos_mgmt = Blueprint("admin_promos_mgmt", __name__, url_prefix="/admin")


@admin_promos_mgmt.route('/promos')
@admin_required
def admin_promos():
    from app.models.payment import Payment
    from app.services.plans import PLANS, TESTING_MODE, TESTING_ACTIVATION_DAYS
    now = datetime.utcnow()
    from app.models.gold_grant import GoldGrant
    from app.models.promo_grant import PromoGrant
    promos = PromoCode.query.order_by(PromoCode.created_at.desc()).all()

    # payment date по stripe_payment_intent (за Gold кодове); fallback = created_at (ръчно създадени кодове)
    intents = [p.stripe_payment_intent for p in promos if p.stripe_payment_intent]
    payments_by_intent = {}
    if intents:
        for pay in Payment.query.filter(Payment.stripe_payment_intent.in_(intents)).all():
            payments_by_intent[pay.stripe_payment_intent] = pay

    # Grant-ове по promo код — реалният срок (спазва TESTING_MODE), не хардкоднати 30 дни.
    # Custom Promo кодове (p.is_custom=True) активират PromoGrant, НЕ GoldGrant (отделни
    # таблици по изрично искане, виж activate.py: GrantModel = PromoGrant if promo.is_custom
    # else GoldGrant) — затова тук трябва да проверим И двете таблици, иначе lookup-ът за
    # Custom кодовете винаги връща None и погрешно пада в legacy fallback клона по-долу.
    grants_by_code = {}
    used_codes = [p.code for p in promos if p.is_used]
    if used_codes:
        for g in GoldGrant.query.filter(GoldGrant.promo_code.in_(used_codes)).all():
            grants_by_code[g.promo_code] = g
        for g in PromoGrant.query.filter(PromoGrant.promo_code.in_(used_codes)).all():
            grants_by_code[g.promo_code] = g

    rows = []
    for p in promos:
        payment = payments_by_intent.get(p.stripe_payment_intent)
        payment_date = payment.paid_at if payment else p.created_at

        # Legacy fallback дни (когато няма никакъв grant запис за кода) — за Custom
        # промо кодове ползваме собствения им duration_days (зададен при създаването
        # през generator формата), НЕ PLANS['gold'], защото Custom кодовете имат
        # индивидуален срок, различен от стандартния Gold 10-пакет.
        def _legacy_days():
            if p.is_custom:
                return p.duration_days or 30
            from app.services.plans import PLANS as _PLANS
            return _PLANS['gold'].get('valid_days_per_code', 30)

        if not p.is_used:
            status = 'expired' if (p.expires_at and p.expires_at < now) else 'stand-by'
        else:
            grant = grants_by_code.get(p.code)
            if grant:
                status = 'active' if grant.expires_at > now else 'used'
            else:
                # легаси код, активиран преди GoldGrant/PromoGrant модела - няма грант запис.
                legacy_days = _legacy_days()
                status = 'active' if (p.activated_at and (now - p.activated_at).days < legacy_days) else 'used'

        if p.is_used and not grants_by_code.get(p.code) and p.activated_at:
            legacy_valid_until = p.activated_at + timedelta(days=_legacy_days())
        else:
            legacy_valid_until = None

        grant = grants_by_code.get(p.code)
        # Единствен източник на истина за СТАНДАРТНИ (не-Custom) планове е
        # app/services/plans.py::PLANS - реалният Gold код няма собствена
        # "конфигурация", той просто Е стандартния Gold план. Custom кодовете
        # (is_custom=True) ИМАТ собствени, ИЗРИЧНО зададени при създаването
        # duration_days/tests_quota_override - тези си остават source of
        # truth ЗА ТЯХ (умишлено различни от стандартния план).
        std_duration = None if p.is_custom else PLANS['gold']['days']
        std_quota = None if p.is_custom else PLANS['gold']['tests_quota']
        # Topics allowed - реален еквивалент съществува в PLANS[..]['display']['themes']
        # за ВСЕКИ стандартен план (Basic:1, Plus:1, Gold:2) - не е N/A.
        std_topics = None if p.is_custom else int(PLANS['gold']['display']['themes'])
        # Activation period (stand-by) - за реален Gold код ИМА реален
        # еквивалент (validity_months -> дни, компресиран от TESTING_MODE
        # до TESTING_ACTIVATION_DAYS) - клиентът наистина има прозорец,
        # в който да активира получения код. За Basic/Plus (директно
        # плащане = директна активация) тази концепция ДЕЙСТВИТЕЛНО не
        # съществува - остава N/A само за тях, не защото сме мързеливи да
        # я намерим, а защото физически няма какво да покажем.
        std_activation_window = None if p.is_custom else (TESTING_ACTIVATION_DAYS if TESTING_MODE else 365)
        rows.append({
            'kind': 'custom' if p.is_custom else 'gold', 'promo': p, 'code': p.code,
            'client_name': p.client_name, 'used_by': p.used_by,
            'plan_label': 'Custom' if p.is_custom else 'Gold',
            'payment_date': payment_date, 'status': status,
            'valid_until': (grant.expires_at if p.is_used and grant else (legacy_valid_until or p.expires_at)),
            'seq_number': grant.id if grant else None,
            'std_duration_days': std_duration, 'std_tests_quota': std_quota,
            'std_topics_allowed': std_topics, 'std_activation_window_days': std_activation_window,
        })

    # Basic/Plus плащания — нямат промокод (директна активация), обединяваме в същия списък.
    # Всяко плащане е свой собствен, автономен период на достъп — статусът му се смята
    # от собствения му прозорец (paid_at + план дни), а НЕ от това какъв е user.plan сега.
    from app.services.plans import get_plan_config
    from app.models.plan_grant import PlanGrant
    basic_plus_payments = Payment.query.filter(Payment.plan.in_(['basic', 'plus'])).all()

    # БЪГ ФИКС (перформанс): преди тук User.query.get() и
    # PlanGrant.query.filter_by() се изпълняваха ВЪТРЕ в цикъла - веднъж
    # на ВСЯКО Payment, вместо batch-fetch-нати веднъж (същия N+1 паттерн,
    # какъвто вече поправихме за FreeSession в grants.py). При натрупване
    # на тестови плащания страницата ставаше все по-бавна с всяко ново
    # плащане. Сега: 2 batch заявки общо, независимо от броя редове.
    _bp_user_ids = list({pay.user_id for pay in basic_plus_payments})
    _bp_payment_ids = [pay.id for pay in basic_plus_payments]
    _bp_users = {u.id: u for u in User.query.filter(User.id.in_(_bp_user_ids)).all()} if _bp_user_ids else {}
    _bp_grants = {g.payment_id: g for g in PlanGrant.query.filter(PlanGrant.payment_id.in_(_bp_payment_ids)).all()} if _bp_payment_ids else {}

    for pay in basic_plus_payments:
        u = _bp_users.get(pay.user_id)
        if not u:
            continue
        cfg = get_plan_config(pay.plan) or {}
        days = cfg.get('days', 0)
        pay_expires = pay.paid_at + timedelta(days=days) if pay.paid_at and days else None
        bp_status = 'active' if (pay_expires and pay_expires > now) else 'used'

        grant = _bp_grants.get(pay.id)
        from app.utils.codes import get_or_create_subscription_code
        # Същият читаем BG код, ползван вече в Billing/Usage - не суровия
        # PlanGrant.id (само вътрешен database номер, безсмислен за админа
        # без контекст, а и лесен за объркване с GoldGrant.id при съвпадащ номер).
        unique_ref = get_or_create_subscription_code('plan', grant.id) if grant else None

        rows.append({
            'kind': pay.plan, 'promo': None, 'code': unique_ref,
            'client_name': u.email, 'used_by': u.email, 'plan_label': pay.plan.capitalize(),
            'payment_date': pay.paid_at, 'status': bp_status,
            'valid_until': pay_expires,
            'seq_number': grant.id if grant else None,
            'payment_id': pay.id,
            'payment_amount': pay.amount,
            'grant_quota': grant.quota if grant else None,
            'grant_tests_used': grant.tests_used if grant else None,
            'std_duration_days': cfg.get('days'), 'std_tests_quota': cfg.get('tests_quota'),
            'std_topics_allowed': int(cfg.get('display', {}).get('themes', 1)),
            # Activation period (stand-by) ДЕЙСТВИТЕЛНО не съществува за
            # Basic/Plus - директно плащане = директна активация, няма
            # чакащ код с прозорец за активиране (за разлика от Gold).
            'std_activation_window_days': None,
        })

    rows.sort(key=lambda r: r['payment_date'] or datetime.min, reverse=True)

    # Статистиките (Active/Used/Total) отразяват ВИНАГИ пълния набор от
    # данни, независимо от търсенето - търсенето филтрира само редовете в
    # самата таблица, не обобщените бройки горе.
    active = sum(1 for r in rows if r['status'] == 'active')
    used = sum(1 for r in rows if r['status'] in ('used', 'expired'))
    total_count = len(rows)

    # Търсене по email на клиента, по BG кода, или по суровия пореден номер
    # (seq_number) - същия UX паттерн като в admin/users.html (закръглена
    # кутийка с лупа вдясно).
    search_q = (request.args.get('q') or '').strip()
    if search_q:
        q_lower = search_q.lower()
        rows = [
            r for r in rows
            if q_lower in (r['client_name'] or '').lower()
            or q_lower in (r.get('used_by') or '').lower()
            or q_lower in (r['code'] or '').lower()
            or (r['seq_number'] is not None and q_lower in str(r['seq_number']))
        ]

    return render_template('admin/promos.html', rows=rows, promos=promos, active=active, used=used, total_count=total_count, search_q=search_q)

@admin_promos_mgmt.route('/promos/create', methods=['POST'])
@admin_required
def create_promo():
    from app.utils.codes import subscription_code
    from datetime import timedelta

    client = request.form.get('client_name', '').strip()
    access_type = request.form.get('access_type', 'Регулярни тестове')
    price = float(request.form.get('price', 0) or 0)

    promo_name = request.form.get('promo_name', '').strip() or None
    internal_note = request.form.get('internal_note', '').strip() or None
    department_restriction = (request.form.get('department_restriction') or '').strip().lower() or None
    if department_restriction not in ('deck', 'engine'):
        department_restriction = None  # "всички" (без ограничение) - празно/невалидно = свободен избор при активация
    duration_days = int(request.form.get('duration_days') or 30)
    activation_window_days = int(request.form.get('activation_window_days') or 30)
    topics_allowed = int(request.form.get('topics_allowed') or 1)
    tests_quota_override = int(request.form.get('tests_quota_override') or 50)
    restricted_email = (request.form.get('restricted_email') or '').strip().lower() or None
    usage_limit_type = request.form.get('usage_limit_type', 'single')
    if usage_limit_type not in ('single', 'custom', 'multiple'):
        usage_limit_type = 'single'
    usage_limit_count = None
    if usage_limit_type == 'custom':
        usage_limit_count = int(request.form.get('usage_limit_count') or 1)
    auto_email = request.form.get('auto_email') in ('1', 'true', 'on')

    expires_at = datetime.utcnow() + timedelta(days=activation_window_days)

    promo = PromoCode(
        code='__pending__', client_name=client, access_type=access_type, price=price,
        promo_name=promo_name, internal_note=internal_note,
        department_restriction=department_restriction,
        duration_days=duration_days, activation_window_days=activation_window_days,
        topics_allowed=topics_allowed, tests_quota_override=tests_quota_override,
        restricted_email=restricted_email, usage_limit_type=usage_limit_type,
        usage_limit_count=usage_limit_count, used_count=0,
        expires_at=expires_at, is_custom=True,
    )
    db.session.add(promo)
    db.session.flush()  # присвоява реално ID, преди пълния commit
    code = subscription_code(promo.id, grant_type='promo')
    promo.code = code
    db.session.commit()

    email_sent = False
    if auto_email and restricted_email:
        from app.services.email import send_shared_promo_code
        try:
            email_sent = send_shared_promo_code(restricted_email, 'Maritime Tests', code, promo.expires_at)
            if email_sent:
                promo.shared_to = restricted_email
                promo.shared_at = datetime.utcnow()
                promo.shared_count = (promo.shared_count or 0) + 1
                db.session.commit()
        except Exception:
            email_sent = False

    return jsonify({'success': True, 'code': code, 'email_sent': email_sent})

@admin_promos_mgmt.route('/payments/<int:payment_id>/delete', methods=['POST'])
@admin_required
def delete_payment(payment_id):
    """Изтрива Basic/Plus плащане (Payment + свързания PlanGrant) - реално
    отнема достъпа, не само трие реда от историята. Огледален на
    delete_promo() по-долу, но за Basic/Plus вместо Custom/Gold кодове."""
    from app.models.payment import Payment
    from app.models.plan_grant import PlanGrant
    payment = Payment.query.get_or_404(payment_id)

    affected_user = User.query.get(payment.user_id)

    PlanGrant.query.filter_by(payment_id=payment.id).delete(synchronize_session=False)
    db.session.delete(payment)
    db.session.commit()

    if affected_user:
        _sync_user_plan_after_revoke(affected_user)

    return jsonify({'success': True})


@admin_promos_mgmt.route('/promos/<int:promo_id>/delete', methods=['POST'])
@admin_required
def delete_promo(promo_id):
    from app.models.gold_grant import GoldGrant
    promo = PromoCode.query.get_or_404(promo_id)

    # Изтриването на кода трябва реално да отнеме достъпа — иначе GoldGrant остава
    # жив в отделна таблица, независимо от промокода.
    affected_user = None
    if promo.used_by:
        affected_user = User.query.filter_by(email=promo.used_by).first()

    GoldGrant.query.filter_by(promo_code=promo.code).delete(synchronize_session=False)
    db.session.delete(promo)
    db.session.commit()

    # Синхронизираме плана на потребителя ВЕДНАГА — не да чака следваща проверка
    if affected_user:
        _sync_user_plan_after_revoke(affected_user)

    return jsonify({'success': True})

@admin_promos_mgmt.route('/promos/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_promos():
    from app.models.gold_grant import GoldGrant
    data = request.get_json(silent=True) or {}
    ids = data.get('ids', [])
    ids = [int(i) for i in ids if str(i).isdigit()]
    if not ids:
        return jsonify({'success': False, 'message': 'No codes selected'}), 400

    promos = PromoCode.query.filter(PromoCode.id.in_(ids)).all()
    codes = [p.code for p in promos]
    affected_emails = {p.used_by for p in promos if p.used_by}

    if codes:
        GoldGrant.query.filter(GoldGrant.promo_code.in_(codes)).delete(synchronize_session=False)

    deleted = PromoCode.query.filter(PromoCode.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()

    # Синхронизираме плановете на всички засегнати потребители веднага
    for email in affected_emails:
        u = User.query.filter_by(email=email).first()
        if u:
            _sync_user_plan_after_revoke(u)

    return jsonify({'success': True, 'deleted': deleted})


def _sync_user_plan_after_revoke(user):
    """
    След премахване на GoldGrant — веднага обновява legacy полетата на потребителя
    (user.plan / is_active / plan_expires_at), ако вече няма никакъв валиден план.
    Иначе стар код, четящ директно тези полета, ще показва грешни данни до следваща
    случайна проверка.
    """
    if not user.has_active_plan():
        if user.plan == 'gold':
            user.plan = 'free'
            user.is_active = False
            user.plan_expires_at = None
            user.plan_activated_at = None
        db.session.commit()

