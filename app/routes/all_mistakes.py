"""
app/routes/all_mistakes.py
==========================
Страница "All Mistakes", преглед на грешките, решаване и платен достъп след изтичане на абонамента.
Само HTTP - правилата са в app/services/all_mistakes.py и all_mistakes_pass.py.
"""
import random

from flask import Blueprint, render_template, session, redirect, url_for, flash, request, current_app
from app.extensions import db
from app.models.user import User
from app.models.test import Test
from app.utils.decorators import login_required
from app.utils.images import inject_images
from app.utils.grants import test_access_lock
from app.services import all_mistakes as svc
from app.services import all_mistakes_pass as passes
from app.services.plans import ALL_MISTAKES

all_mistakes_bp = Blueprint("all_mistakes", __name__)

PAGE = 'all_mistakes.all_mistakes_page'


def _unlocked_entitlement(user, test_id):
    """(entitlement, redirect) - redirect е готов отговор, когато няма достъп или още е заключен."""
    ent = svc.entitlement_for_test(user, test_id)
    if ent is None:
        flash('All Mistakes is not included in your plan for this test.', 'warning')
        return None, redirect(url_for(PAGE))
    if ent['mode'] == 'offer':  # планът няма функцията - заключена, достъп само срещу допълнително плащане
        return None, redirect(url_for('all_mistakes.unlock_page', test_id=test_id))
    solved, needed = svc.unlock_progress(user.id, test_id, ent['start'])
    if not svc.is_open(user.id, test_id, ent):
        flash(f'Solve {needed - solved} more Test, Mix or Simulator run(s) of this test to unlock All Mistakes.', 'warning')
        return None, redirect(url_for(PAGE))
    return ent, None


@all_mistakes_bp.route('/all-mistakes')
@login_required
def all_mistakes_page():
    user = User.query.get(session['user_id'])
    rows = svc.summary(user)
    return render_template('user/all_mistakes.html', user=user, rows=rows, locked=not rows,
                           plan_names=svc.feature_available_to_plan_card(), cfg=ALL_MISTAKES)


@all_mistakes_bp.route('/all-mistakes/<int:test_id>/review')
@login_required
def review_all_mistakes(test_id):
    """Само преглед: въпросите, сгрешени по теста, с верните отговори. Достъпен във всички режими."""
    user = User.query.get(session['user_id'])
    test = Test.query.get_or_404(test_id)
    ent, redirect_resp = _unlocked_entitlement(user, test_id)
    if redirect_resp:
        return redirect_resp
    wrong_ids = svc.mistakes_of(user.id, test, ent)
    questions = inject_images(test_id, [q for q in test.get_questions() if str(q['id']) in wrong_ids])
    return render_template('user/all_mistakes_review.html', user=user, test=test, questions=questions,
                           mode=ent['mode'], ends_at=ent['ends_at'])


@all_mistakes_bp.route('/test/<int:test_id>/all-mistakes')
@login_required
def start_all_mistakes(test_id):
    user = User.query.get(session['user_id'])
    test = Test.query.get_or_404(test_id)
    ent, redirect_resp = _unlocked_entitlement(user, test_id)
    if redirect_resp:
        return redirect_resp
    if ent['mode'] == 'review':  # абонаментът е изтекъл - решаването иска платен достъп
        return redirect(url_for('all_mistakes.unlock_page', test_id=test_id))
    if ent['mode'] == 'pass':
        if svc.pass_runs_used(user.id, ent['pass_']) >= ent['pass_'].quota:
            flash('You have used all solves of your All Mistakes access.', 'warning')
            return redirect(url_for(PAGE))
    else:  # активен абонамент: всяко решаване харчи 1 кредит
        locked, _grant = test_access_lock(user, test_id)
        db.session.commit()  # test_access_lock може да обвърже чакащ grant
        if locked:
            return redirect(url_for('dashboard.user_dashboard', quota_exceeded=1))

    wrong_ids = svc.mistakes_of(user.id, test, ent)
    if not wrong_ids:
        flash('No mistakes yet - questions you answer wrongly will appear here.', 'success')
        return redirect(url_for(PAGE))
    questions = inject_images(test_id, [q for q in test.get_questions() if str(q['id']) in wrong_ids])
    random.shuffle(questions)
    return render_template('user/test.html', test=test, questions=questions, shuffle=True,
                           test_type=svc.TEST_TYPE, is_demo=False)


@all_mistakes_bp.route('/all-mistakes/<int:test_id>/unlock')
@login_required
def unlock_page(test_id):
    """Оферта за платения достъп (планът няма функцията, или абонаментът е изтекъл и тя е била включена)."""
    user = User.query.get(session['user_id'])
    test = Test.query.get_or_404(test_id)
    if not passes.can_buy(user, test_id):
        return redirect(url_for(PAGE))
    ent = svc.entitlement_for_test(user, test_id)
    return render_template('user/all_mistakes_unlock.html', user=user, test=test, cfg=ALL_MISTAKES,
                           not_in_plan=ent['mode'] == 'offer')


@all_mistakes_bp.route('/all-mistakes/<int:test_id>/checkout', methods=['POST'])
@login_required
def checkout(test_id):
    user = User.query.get(session['user_id'])
    if not passes.can_buy(user, test_id):
        return redirect(url_for(PAGE))
    base = request.host_url.rstrip('/')  # реалният домейн (production или PR preview)
    success = f"{base}{url_for('all_mistakes.purchased')}?session_id={{CHECKOUT_SESSION_ID}}"
    url = passes.create_checkout(user, test_id, success, f"{base}{url_for(PAGE)}")
    if not url:
        flash('Could not connect to Stripe. Please try again.', 'error')
        return redirect(url_for('all_mistakes.unlock_page', test_id=test_id))
    return redirect(url)


@all_mistakes_bp.route('/all-mistakes/purchased')
@login_required
def purchased():
    """Stripe пренасочва тук след плащане; проверяваме сесията (идемпотентно, както /billing/success)."""
    session_id = request.args.get('session_id', '')
    if session_id:
        from app.services.stripe import verify_and_grant_checkout_session
        ok, message = verify_and_grant_checkout_session(session_id)
        if ok:
            flash('Payment received - your All Mistakes access is active.', 'success')
        else:
            current_app.logger.warning(f"all-mistakes purchase verify failed: {message}")
            flash('We could not confirm the payment yet. If you were charged, contact support.', 'error')
    return redirect(url_for(PAGE))
