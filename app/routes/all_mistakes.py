"""
app/routes/all_mistakes.py
==========================
Страница "All Mistakes" и стартиране на теста с всички допуснати грешки.
Само HTTP - правилата за достъп и изчисленията са в app/services/all_mistakes.py.
"""
import random

from flask import Blueprint, render_template, session, redirect, url_for, flash
from app.extensions import db
from app.models.user import User
from app.models.test import Test
from app.utils.decorators import login_required
from app.utils.images import inject_images
from app.utils.grants import test_access_lock
from app.services import all_mistakes as svc

all_mistakes_bp = Blueprint("all_mistakes", __name__)


@all_mistakes_bp.route('/all-mistakes')
@login_required
def all_mistakes_page():
    user = User.query.get(session['user_id'])
    rows = svc.summary(user)
    return render_template('user/all_mistakes.html', user=user, rows=rows,
                           locked=not rows, plan_names=svc.feature_available_to_plan_card(),
                           min_tests=svc.MIN_TESTS_TO_UNLOCK, free_runs=svc.FREE_RUNS_PER_CREDIT)


@all_mistakes_bp.route('/test/<int:test_id>/all-mistakes')
@login_required
def start_all_mistakes(test_id):
    user = User.query.get(session['user_id'])
    test = Test.query.get_or_404(test_id)
    ent = svc.entitlement_for_test(user, test_id)
    if ent is None:
        flash('All Mistakes is not included in your plan for this test.', 'warning')
        return redirect(url_for('all_mistakes.all_mistakes_page'))
    solved, needed = svc.unlock_progress(user.id, test_id, ent['start'])
    if solved < needed:
        flash(f'Solve {needed - solved} more Test or Mix run(s) of this test to unlock All Mistakes.', 'warning')
        return redirect(url_for('all_mistakes.all_mistakes_page'))
    # Всяко FREE_RUNS_PER_CREDIT-о решаване струва кредит -> тогава важи и заключването при изчерпана квота.
    if not ent['in_grace'] and svc.next_run_is_charged(user.id, ent['grant']):
        locked, _grant = test_access_lock(user, test_id)
        db.session.commit()  # test_access_lock може да обвърже чакащ grant
        if locked:
            return redirect(url_for('dashboard.user_dashboard', quota_exceeded=1))

    wrong_ids = svc.wrong_question_ids(user.id, test, ent['start'])
    if not wrong_ids:
        flash('No mistakes yet - questions you answer wrongly will appear here.', 'success')
        return redirect(url_for('all_mistakes.all_mistakes_page'))

    questions = inject_images(test_id, [q for q in test.get_questions() if str(q['id']) in wrong_ids])
    random.shuffle(questions)
    return render_template('user/test.html', test=test, questions=questions, shuffle=True,
                           test_type=svc.TEST_TYPE, is_demo=False)
