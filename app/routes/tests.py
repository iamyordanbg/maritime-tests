"""
app/routes/tests.py
====================
Само route-овете, които са РЕАЛНО уникални (не дублирани в dashboard.py):
преглед на резултат (/result/<id>) и оценяване на тест (/test/<id>/submit).

ВАЖНО: take_test, test_mistakes, simulator, history, submit_signal, settings*,
logout_all, admin_snapshots* бяха ТОЧНИ дубликати на route-ове в dashboard.py
(същия URL, регистриран от друг blueprint) — премахнати, защото създаваха
недетерминирано route-ване (Werkzeug решава кой да изпълни без гаранция) и
част от тях бяха счупени (undefined имена: app, Signal, MonthlySnapshot,
check_password_hash — биха гръмнали с NameError, ако някога се изпълнят).
"""

from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from app.extensions import db
from app.models.user import User
from app.models.test import Test
from app.models.result import TestResult
from app.utils.decorators import login_required
import json
from datetime import datetime

tests = Blueprint("tests", __name__)


@tests.route('/result/<int:result_id>')
@login_required
def view_result(result_id):
    """Преглед на решен тест — само за справка, без възможност за промяна"""
    from app import inject_images
    result = TestResult.query.get_or_404(result_id)
    if result.user_id != session['user_id']:
        flash('Нямаш достъп до този резултат.', 'error')
        return redirect(url_for('dashboard.user_dashboard'))

    test = Test.query.get_or_404(result.test_id)
    all_questions = test.get_questions()
    q_map = {str(q['id']): q for q in all_questions}

    saved_answers = json.loads(result.answers_json)
    question_ids = json.loads(result.question_ids_json) if result.question_ids_json else []

    if question_ids:
        ordered_ids = [str(qid) for qid in question_ids]
    else:
        ordered_ids = list(q_map.keys())

    review_questions = []
    for qid_str in ordered_ids:
        q = q_map.get(qid_str)
        if not q:
            continue
        selected_idx = saved_answers.get(qid_str)
        review_questions.append({
            'id': q['id'],
            'question': q['question'],
            'options': q['options'],
            'selected_idx': selected_idx,
            'has_image': q.get('has_image', False)
        })

    review_questions_with_img = inject_images(result.test_id, [
        {'id': q['id'], 'has_image': q['has_image']} for q in review_questions
    ])
    img_map = {str(q['id']): q.get('image') for q in review_questions_with_img if q.get('image')}
    for q in review_questions:
        if str(q['id']) in img_map:
            q['image'] = img_map[str(q['id'])]

    type_labels = {'test': 'Test', 'mix': 'Mix', 'mistakes': 'Mistakes', 'simulator': 'Simulator'}

    return render_template('user/result_review.html',
                           test=test, result=result,
                           questions=review_questions,
                           test_type_label=type_labels.get(result.test_type, 'Test'))


@tests.route('/test/<int:test_id>/submit', methods=['POST'])
@login_required
def submit_test(test_id):
    test = Test.query.get_or_404(test_id)
    all_questions = test.get_questions()
    answers = request.json.get('answers', {})
    test_type = request.json.get('test_type', 'test')
    question_ids = request.json.get('question_ids', [])

    answers_normalized = {str(k): int(v) for k, v in answers.items()}

    if question_ids:
        qid_set = set(str(qid) for qid in question_ids)
        questions = [q for q in all_questions if str(q['id']) in qid_set]
    else:
        questions = all_questions

    score = 0
    for q in questions:
        q_id = str(q['id'])
        selected = answers_normalized.get(q_id)
        if selected is not None:
            try:
                if q['options'][int(selected)]['isCorrect']:
                    score += 1
            except (IndexError, KeyError):
                pass

    total = len(questions)
    percent = round((score / total) * 100, 1) if total > 0 else 0
    wrong = total - score
    if test_type == 'simulator':
        passed = (wrong <= round(total * 0.10)) or (percent >= 90)
    else:
        passed = percent >= 90

    duration = request.json.get('duration', 0)

    # Defense-in-depth: дори ако UI-то е позволило зареждане (напр. директно
    # API извикване, заобикалящо /test/<id>), не позволяваме submit ако
    # достъпът е ЗАКЛЮЧЕН (изтекло време ИЛИ изчерпан лимит от тестове).
    user = User.query.get(session['user_id'])
    owning_grant = None
    if user and not user.is_admin:
        from app.utils.grants import test_access_lock
        locked, owning_grant = test_access_lock(user, test_id)
        if locked:
            return jsonify({
                'error': 'quota_exceeded',
                'message': 'You have reached the question-solving limit for this plan. If you want to continue preparing, please activate a new subscription!'
            }), 403

    result = TestResult(
        user_id=session['user_id'],
        test_id=test_id,
        score=score, total=total,
        percent=percent, passed=passed,
        answers_json=json.dumps(answers_normalized),
        test_type=test_type,
        duration=duration,
        question_ids_json=json.dumps(question_ids)
    )
    db.session.add(result)

    # Намаляваме брояча на тестовете — от правилния grant (Gold/PlanGrant), не глобално
    if user and user.is_active:
        if user.is_admin:
            pass
        elif owning_grant:
            owning_grant.tests_used = (owning_grant.tests_used or 0) + 1
        else:
            if user.tests_used is None:
                user.tests_used = 0
            user.tests_used += 1

    db.session.commit()

    return jsonify({'score': score, 'total': total, 'percent': percent, 'passed': passed})
