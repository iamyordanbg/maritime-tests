from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from app.extensions import db
from app.models.user import User
from app.models.test import Test
from app.models.result import TestResult
from app.utils.decorators import admin_required, login_required
import random as rnd
from datetime import datetime

tests = Blueprint("tests", __name__)


@tests.route('/test/<int:test_id>')
@login_required
def take_test(test_id):
    import random as rnd
    user = User.query.get(session['user_id'])
    if not user.is_active:
        flash('Необходим е активен абонамент за достъп до тестовете.', 'warning')
        return redirect(url_for('dashboard.user_dashboard'))
    test = Test.query.get_or_404(test_id)
    questions = test.get_questions()
    questions = inject_images(test_id, questions)
    shuffle = request.args.get('shuffle') == 'true'
    if shuffle:
        questions = list(questions)
        rnd.shuffle(questions)
    return render_template('user/test.html', test=test, questions=questions, shuffle=shuffle, is_demo=False)

@tests.route('/test/<int:test_id>/mistakes')
@login_required
def test_mistakes(test_id):
    import random as rnd
    test = Test.query.get_or_404(test_id)
    
    # Вземи последните 2 резултата от обикновен тест или микс
    last_results = TestResult.query.filter_by(
        user_id=session['user_id'],
        test_id=test_id
    ).filter(
        TestResult.test_type.in_(['test', 'mix'])
    ).order_by(TestResult.taken_at.desc()).limit(2).all()
    
    if len(last_results) < 2:
        flash('Трябват поне 2 решени теста (Тест или Микс) за тази функция', 'error')
        return redirect(url_for('admin.admin_tests'))
    
    # Събери грешно отговорените въпроси
    all_questions = test.get_questions()
    q_map = {str(q['id']): q for q in all_questions}
    
    # Въпрос се включва в грешките ако е грешен в ПОНЕ ЕДИН от последните 2 теста
    # Въпрос се премахва само ако е верен И В ДВАТА последни теста
    
    # Намери всички въпроси отговорени в двата теста
    answered_in = [{}, {}]  # {q_id: is_correct} за всеки тест
    for i, result in enumerate(last_results):
        answers = json.loads(result.answers_json)
        for q_id_str, o_idx in answers.items():
            q = q_map.get(str(q_id_str))
            if q:
                try:
                    is_correct = q['options'][int(o_idx)]['isCorrect']
                    answered_in[i][str(q_id_str)] = is_correct
                except (IndexError, KeyError):
                    answered_in[i][str(q_id_str)] = False
    
    wrong_ids = set()
    all_answered = set(answered_in[0].keys()) | set(answered_in[1].keys())
    
    for q_id_str in all_answered:
        correct_in_0 = answered_in[0].get(q_id_str, None)
        correct_in_1 = answered_in[1].get(q_id_str, None)
        
        # Грешен ако е грешен в поне един тест
        # Верен само ако е верен в ДВАТА теста
        if correct_in_0 is False or correct_in_1 is False:
            wrong_ids.add(q_id_str)
        elif correct_in_0 is None or correct_in_1 is None:
            # Отговорен само в един тест — включи ако е грешен
            val = correct_in_0 if correct_in_0 is not None else correct_in_1
            if not val:
                wrong_ids.add(q_id_str)
    
    if not wrong_ids:
        flash('Нямаш грешки от последните 2 теста!', 'success')
        return redirect(url_for('admin.admin_tests'))
    
    # Вземи въпросите с грешки
    wrong_questions = [q for q in all_questions if str(q['id']) in wrong_ids]
    wrong_questions = inject_images(test_id, wrong_questions)
    rnd.shuffle(wrong_questions)
    
    return render_template('user/test.html', test=test, questions=wrong_questions, 
                         shuffle=True, test_type='mistakes', is_demo=False)

@tests.route('/test/<int:test_id>/simulator')
@login_required
def simulator(test_id):
    import random as rnd
    test = Test.query.get_or_404(test_id)
    questions = test.get_questions()
    questions = inject_images(test_id, questions)
    rnd.shuffle(questions)
    questions = questions[:60]
    return render_template('user/simulator.html', test=test, questions=questions)

@tests.route('/test/<int:test_id>/submit', methods=['POST'])
@login_required
def submit_test(test_id):
    print(f"DEBUG submit_test ENTRY: test_id={test_id}, session_user_id={session.get('user_id')}", flush=True)
    test = Test.query.get_or_404(test_id)
    all_questions = test.get_questions()
    answers = request.json.get('answers', {})
    test_type = request.json.get('test_type', 'test')
    # ID-тата на въпросите пратени от frontend
    question_ids = request.json.get('question_ids', [])

    # Нормализирай ключовете към стрингове
    answers_normalized = {str(k): int(v) for k, v in answers.items()}

    # Ако симулаторът е пратил конкретни ID-та — ползвай само тях
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
    answered = len(answers_normalized)
    percent = round((score / total) * 100, 1) if total > 0 else 0
    # Взет тест:
    # - Симулатор: грешни <= 10% от total (т.е. <= 6 от 60)
    # - Всички останали: >= 90% верни
    wrong = total - score
    if test_type == 'simulator':
        # Взет ако: грешни <= 10% от total ИЛИ верни >= 90%
        passed = (wrong <= round(total * 0.10)) or (percent >= 90)
    else:
        passed = percent >= 90

    answers_normalized_final = answers_normalized

    duration = request.json.get('duration', 0)

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

    # Намаляваме брояча на тестовете
    user = User.query.get(session['user_id'])
    debug_info = f"active={user.is_active if user else 'NOUSER'},used_before={user.tests_used if user else 'N/A'}"
    if user and user.is_active:
        if user.tests_used is None:
            user.tests_used = 0
        user.tests_used += 1
        debug_info += f",used_after={user.tests_used}"
    else:
        debug_info += ",SKIPPED"

    db.session.commit()

    return jsonify({'score': score, 'total': total, 'percent': percent, 'passed': passed, '_debug': debug_info})

@tests.route('/history')
@login_required
def history():
    user = User.query.get(session['user_id'])
    results = TestResult.query.filter_by(user_id=user.id).order_by(TestResult.taken_at.desc()).all()
    return render_template('history.html', user=user, results=results)

@tests.route('/signal', methods=['POST'])
@login_required
def submit_signal():
    msg = request.form.get('message', '').strip()
    sig_type = request.form.get('type', 'bug')
    user = User.query.get(session['user_id'])
    if msg:
        signal = Signal(user_id=user.id, user_name=user.name, type=sig_type, message=msg)
        db.session.add(signal)
        db.session.commit()
    return redirect(url_for('dashboard.user_dashboard'))

# ============================================================
#  ADMIN ROUTES
# ============================================================


@tests.route('/settings')
@login_required
def settings():
    with app.app_context():
        user = User.query.get(session['user_id'])
    if user and user.is_admin:
        return redirect(url_for('admin.admin_dashboard'))
    return render_template('settings.html', user=user)

@tests.route('/settings/profile', methods=['POST'])
@login_required
def settings_profile():
    user = User.query.get(session['user_id'])
    user.nick = request.form.get('rank', '').strip()
    user.fullname = request.form.get('company', '').strip()
    db.session.commit()
    return jsonify({'success': True, 'message': '✓ Профилът е запазен'})



@tests.route('/settings/notifications', methods=['POST'])
@login_required
def settings_notifications():
    user = User.query.get(session['user_id'])
    data = request.get_json()
    user.notif_subscription = data.get('notif_subscription', True)
    db.session.commit()
    return jsonify({'success': True})

@tests.route('/logout-all', methods=['POST'])
@login_required
def logout_all():
    session.clear()
    return jsonify({'success': True})

@tests.route('/settings/password', methods=['POST'])
@login_required
def settings_password():
    user = User.query.get(session['user_id'])
    cur = request.form.get('current_password', '')
    new_pass = request.form.get('new_password', '')
    if not check_password_hash(user.password, cur):
        return jsonify({'success': False, 'message': 'Грешна текуща парола'})
    if len(new_pass) < 6:
        return jsonify({'success': False, 'message': 'Паролата е прекалено кратка'})
    user.password = generate_password_hash(new_pass)
    db.session.commit()
    return jsonify({'success': True, 'message': '✓ Паролата е сменена'})

@tests.route('/admin/api/snapshots/<metric>')
@admin_required
def admin_snapshots(metric):
    """Връща данни за графика по метрика и период"""
    period = request.args.get('period', '1Y')  # 6M, 1Y, 2Y, 3Y, 5Y, ALL
    
    now = datetime.utcnow()
    
    if period == '6M':
        from_date = datetime(now.year, now.month, 1) - timedelta(days=180)
    elif period == '1Y':
        from_date = datetime(now.year - 1, now.month, 1)
    elif period == '2Y':
        from_date = datetime(now.year - 2, now.month, 1)
    elif period == '3Y':
        from_date = datetime(now.year - 3, now.month, 1)
    elif period == '5Y':
        from_date = datetime(now.year - 5, now.month, 1)
    else:  # ALL
        from_date = datetime(2020, 1, 1)
    
    snapshots = MonthlySnapshot.query.filter(
        MonthlySnapshot.year > from_date.year,
        db.or_(
            MonthlySnapshot.year > from_date.year,
            db.and_(MonthlySnapshot.year == from_date.year, MonthlySnapshot.month >= from_date.month)
        )
    ).order_by(MonthlySnapshot.year, MonthlySnapshot.month).all()
    
    valid = ['total_users', 'active_users', 'passive_users', 'demo_users']
    if metric not in valid:
        return jsonify({'error': 'Invalid metric'}), 400
    
    return jsonify({
        'metric': metric,
        'period': period,
        'labels': [s.label for s in snapshots],
        'data': [getattr(s, metric) for s in snapshots],
    })

@tests.route('/admin/api/snapshots/record', methods=['POST'])
@admin_required
def admin_record_snapshot():
    """Ръчно записване на snapshot"""
    snap = record_monthly_snapshot()
    return jsonify({'success': True, 'message': f'Snapshot {snap.year}-{snap.month:02d} записан'})
