"""
app/routes/admin_users_mgmt.py
================================
Admin: Users CRUD + billing history + debug — extraction-нат от admin.py
(Group A audit, File Limits).
"""
from flask import Blueprint, render_template, request, jsonify
from app.extensions import db
from app.models.user import User
from app.models.result import TestResult
from app.utils.decorators import admin_required
from datetime import datetime

admin_users_mgmt = Blueprint("admin_users_mgmt", __name__, url_prefix="/admin")


@admin_users_mgmt.route('/users')
@admin_required
def admin_users():
    from app.models.gold_grant import GoldGrant
    now = datetime.utcnow()
    search_q = (request.args.get('q') or '').strip()
    users_query = User.query.filter_by(is_admin=False)
    if search_q:
        users_query = users_query.filter(
            db.or_(
                User.email.ilike(f'%{search_q}%'),
                db.cast(User.id, db.String).ilike(f'%{search_q}%'),
            )
        )
    users = users_query.order_by(User.created_at.desc()).all()

    user_ids = [u.id for u in users]
    grants_by_user = {}
    if user_ids:
        for g in GoldGrant.query.filter(GoldGrant.user_id.in_(user_ids), GoldGrant.expires_at > now).all():
            grants_by_user.setdefault(g.user_id, []).append(g)

    # Всеки текущо ВАЛИДЕН план/grant за потребителя — не user.plan (единично поле,
    # което не отразява, че може да има няколко активни Gold grant-а едновременно).
    plan_labels = {}
    for u in users:
        labels = []
        if u.plan in ('basic', 'plus') and u.plan_expires_at and u.plan_expires_at > now:
            labels.append(u.plan.upper())
        for g in grants_by_user.get(u.id, []):
            dept_short = (g.department or '?')[:4].capitalize()
            level_short = (g.level or '').split()[0][:3].upper() if g.level else ''
            labels.append(f"GOLD·{dept_short}{'/' + level_short if level_short else ''}")
        plan_labels[u.id] = labels or ['FREE']

    return render_template('admin/users.html', users=users, now=now, plan_labels=plan_labels, search_q=search_q)


@admin_users_mgmt.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        return jsonify({'success': False, 'message': 'Cannot delete admin'})
    db.session.delete(user)
    db.session.commit()
    return jsonify({'success': True})

@admin_users_mgmt.route('/debug/plan-status')
@admin_required
def debug_plan_status():
    """
    Суровата истина за акаунт — без изчисления, без предположения.
    Използване: /admin/debug/plan-status?email=bumnazaloga3@abv.bg
    """
    from app.models.gold_grant import GoldGrant
    email = (request.args.get('email') or '').strip().lower()
    if not email:
        return jsonify({'error': 'Добави ?email=... в URL-a'}), 400

    user = User.query.filter(db.func.lower(User.email) == email).first()
    if not user:
        return jsonify({'error': f'Няма потребител с имейл {email}'}), 404

    now = datetime.utcnow()
    all_grants = GoldGrant.query.filter_by(user_id=user.id).order_by(GoldGrant.activated_at.desc()).all()

    return jsonify({
        'user_id': user.id,
        'email': user.email,
        'server_time_now': now.isoformat(),
        'RAW_DB_FIELDS': {
            'plan': user.plan,
            'is_active': user.is_active,
            'plan_activated_at': user.plan_activated_at.isoformat() if user.plan_activated_at else None,
            'plan_expires_at': user.plan_expires_at.isoformat() if user.plan_expires_at else None,
            'library_test_id': user.library_test_id,
            'tests_used': user.tests_used,
        },
        'COMPUTED_REAL_STATUS': {
            'has_active_plan': user.has_active_plan(),
            'effective_plan_label': user.effective_plan_label(),
            'effective_days_left': user.effective_days_left(),
        },
        'ALL_GOLD_GRANTS_IN_DB': [
            {
                'id': g.id,
                'promo_code': g.promo_code,
                'department': g.department,
                'level': g.level,
                'test_ids': g.test_id_list(),
                'quota': g.quota,
                'tests_used': g.tests_used,
                'activated_at': g.activated_at.isoformat() if g.activated_at else None,
                'expires_at': g.expires_at.isoformat() if g.expires_at else None,
                'IS_CURRENTLY_ACTIVE': g.expires_at > now if g.expires_at else False,
            }
            for g in all_grants
        ],
    })


@admin_users_mgmt.route('/users/<int:user_id>')
@admin_required
def admin_user_detail(user_id):
    user = User.query.get_or_404(user_id)
    results = TestResult.query.filter_by(user_id=user_id).order_by(TestResult.taken_at.desc()).all()
    return render_template('admin/user_detail.html', user=user, results=results)

@admin_users_mgmt.route('/users/<int:user_id>/billing')
@admin_required
def admin_user_billing(user_id):
    """
    Пълната billing история на потребителя (всички Basic/Plus/Gold покупки
    - активни И вече изтекли/използвани), за попъпа "Account" в admin/users.
    Същите данни, каквито потребителят вижда в собствения си Billing/Usage
    таб (grant.plan, кодa, activated_at/expires_at), но БЕЗ филтъра "само
    активните" - тук админът трябва да види ЦЯЛАТА история, включително
    колко пъти е ползвал платени абонаменти по-рано.
    """
    from app.models.plan_grant import PlanGrant
    from app.models.gold_grant import GoldGrant
    from app.models.promo_grant import PromoGrant
    from app.utils.codes import get_or_create_subscription_code
    user = User.query.get_or_404(user_id)
    now = datetime.utcnow()

    cards = []
    all_plan_grants = PlanGrant.query.filter_by(user_id=user_id).order_by(PlanGrant.activated_at.asc()).all()
    for g in all_plan_grants:
        cards.append({
            'plan': g.plan.capitalize(),
            'code': get_or_create_subscription_code('plan', g.id),
            'activated_at': g.activated_at.strftime('%d.%m.%Y %H:%M') if g.activated_at else '—',
            'expires_at': g.expires_at.strftime('%d.%m.%Y %H:%M') if g.expires_at else '—',
            'status': 'Active' if g.expires_at and g.expires_at > now else 'Expired',
            '_sort_key': g.activated_at or datetime.min,
        })

    all_gold_grants = GoldGrant.query.filter_by(user_id=user_id).order_by(GoldGrant.activated_at.asc()).all()
    for g in all_gold_grants:
        cards.append({
            'plan': 'Gold',
            'code': g.promo_code or get_or_create_subscription_code('gold', g.id),
            'activated_at': g.activated_at.strftime('%d.%m.%Y %H:%M') if g.activated_at else '—',
            'expires_at': g.expires_at.strftime('%d.%m.%Y %H:%M') if g.expires_at else '—',
            'status': 'Active' if g.expires_at and g.expires_at > now else 'Expired',
            '_sort_key': g.activated_at or datetime.min,
        })

    # БЪГ ФИКС: тук липсваше изцяло заявка към PromoGrant - Custom Promo
    # активации (is_custom=True кодове) създават PromoGrant, НЕ GoldGrant
    # (виж activate.py:321), затова не се появяваха изобщо в тази справка.
    all_promo_grants = PromoGrant.query.filter_by(user_id=user_id).order_by(PromoGrant.activated_at.asc()).all()
    for g in all_promo_grants:
        cards.append({
            'plan': 'Custom',
            'code': g.promo_code or get_or_create_subscription_code('promo', g.id),
            'activated_at': g.activated_at.strftime('%d.%m.%Y %H:%M') if g.activated_at else '—',
            'expires_at': g.expires_at.strftime('%d.%m.%Y %H:%M') if g.expires_at else '—',
            'status': 'Active' if g.expires_at and g.expires_at > now else 'Expired',
            '_sort_key': g.activated_at or datetime.min,
        })

    # Free-план сесии (library избор) - от FreeSession историята, СЪЩИЯ
    # формат като Basic/Plus/Gold картите по-горе, за да се вижда Free в
    # Usage/Billing попъпа на админа по абсолютно същия начин.
    from app.models.free_session import FreeSession
    free_cards = []
    all_free_sessions = FreeSession.query.filter_by(user_id=user_id).order_by(FreeSession.activated_at.asc()).all()
    for s in all_free_sessions:
        free_cards.append({
            'plan': 'Free',
            'code': f"{s.test.title[:22]}" if s.test else '—',
            'activated_at': s.activated_at.strftime('%d.%m.%Y %H:%M') if s.activated_at else '—',
            'expires_at': s.expires_at.strftime('%d.%m.%Y %H:%M') if s.expires_at else '—',
            'status': 'Active' if s.expires_at and s.expires_at > now else 'Expired',
            '_sort_key': s.activated_at or datetime.min,
        })

    all_cards_merged = cards + free_cards
    all_cards_merged.sort(key=lambda c: c['_sort_key'], reverse=True)
    for c in all_cards_merged:
        del c['_sort_key']

    return jsonify({
        'email': user.email,
        'server_time_utc': now.strftime('%Y-%m-%d %H:%M:%S'),
        'total_purchases': len(all_cards_merged),
        'cards': all_cards_merged,
    })

@admin_users_mgmt.route('/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    user.email_verified = not user.email_verified
    db.session.commit()
    return jsonify({'success': True, 'email_verified': user.email_verified})
