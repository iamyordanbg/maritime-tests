from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.models.user import User
from app.models.test import Test
from app.models.result import TestResult
from app.models.signal import Signal
from app.models.ticket import Ticket, TicketMessage
from app.utils.decorators import admin_required, login_required, admin_required
from datetime import datetime

dashboard = Blueprint("dashboard", __name__)


@dashboard.route('/dashboard')
@login_required
def user_dashboard():
    user = User.query.get(session['user_id'])
    if user and user.is_admin:
        return redirect(url_for('admin.admin_dashboard'))
    results = TestResult.query.filter_by(user_id=user.id).order_by(TestResult.taken_at.desc()).limit(5).all()
    total_tests = TestResult.query.filter_by(user_id=user.id).count()
    passed_tests = TestResult.query.filter_by(user_id=user.id, passed=True).count()
    tests = Test.query.order_by(Test.created_at.desc()).all()
    return render_template('user/dashboard.html', user=user, results=results,
                           total_tests=total_tests, passed_tests=passed_tests, tests=tests)

def inject_images(test_id, questions):
    """Добавя снимките към въпросите — URL вместо base64"""
    img_dir = f"/tmp/qimages/{test_id}"
    if not os.path.exists(img_dir):
        print(f"INJECT: No image dir found for test {test_id}")
        return questions
    
    loaded = 0
    for q in questions:
        if q.get('has_image'):
            for fmt in ['jpg', 'png']:
                img_path = f"{img_dir}/{q['id']}.{fmt}"
                if os.path.exists(img_path):
                    # URL вместо base64 — браузърът зарежда при нужда
                    q['image'] = f"/qimage/{test_id}/{q['id']}.{fmt}"
                    loaded += 1
                    break
    print(f"INJECT: Loaded {loaded} images for test {test_id}")
    return questions

@dashboard.route('/test/<int:test_id>')
@login_required
def take_test(test_id):
    import random as rnd
    user = User.query.get(session['user_id'])
    if user and user.is_admin:
        return redirect(url_for('admin.admin_dashboard'))
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
    return render_template('take_test.html', test=test, questions=questions, shuffle=shuffle)

@dashboard.route('/test/<int:test_id>/mistakes')
@login_required
def test_mistakes(test_id):
    # Admin redirect
    from app.models.user import User as _U
    _u = _U.query.get(session['user_id'])
    if _u and _u.is_admin:
        return redirect(url_for('admin.admin_dashboard'))
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
    
    return render_template('take_test.html', test=test, questions=wrong_questions, 
                         shuffle=True, test_type='mistakes')

@dashboard.route('/test/<int:test_id>/simulator')
@login_required
def simulator(test_id):
    # Admin redirect
    from app.models.user import User as _U
    _u = _U.query.get(session['user_id'])
    if _u and _u.is_admin:
        return redirect(url_for('admin.admin_dashboard'))
    import random as rnd
    test = Test.query.get_or_404(test_id)
    questions = test.get_questions()
    questions = inject_images(test_id, questions)
    rnd.shuffle(questions)
    questions = questions[:60]
    return render_template('simulator.html', test=test, questions=questions)

@dashboard.route('/test/<int:test_id>/submit', methods=['POST'])
@login_required
def submit_test(test_id):
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
    db.session.commit()

    return jsonify({'score': score, 'total': total, 'percent': percent, 'passed': passed})

@dashboard.route('/history')
@login_required
def history():
    user = User.query.get(session['user_id'])
    if user and user.is_admin:
        return redirect(url_for('admin.admin_dashboard'))
    results = TestResult.query.filter_by(user_id=user.id).order_by(TestResult.taken_at.desc()).all()
    return render_template('user/history.html', user=user, results=results)

@dashboard.route('/signal', methods=['POST'])
@login_required
def submit_signal():
    from app.services.email import send_signal_notification
    msg = request.form.get('message', '').strip()[:500]
    sig_type = request.form.get('type', 'bug')
    user = User.query.get(session['user_id'])
    if msg:
        signal = Signal(
            user_id=user.id,
            user_name=user.name,
            user_email=user.email,
            type=sig_type,
            message=msg
        )
        db.session.add(signal)
        db.session.commit()
        # Изпращаме имейл до admin
        send_signal_notification(user.name, user.email, sig_type, msg)
    return jsonify({'success': True})

@dashboard.route('/signals/unread')
@login_required
def unread_signals():
    user_id = session['user_id']
    count = Signal.query.filter_by(user_id=user_id, is_read=False).filter(Signal.reply != None).count()
    return jsonify({'count': count})

@dashboard.route('/signals/read/<int:signal_id>', methods=['POST'])
@login_required
def mark_signal_read(signal_id):
    signal = Signal.query.filter_by(id=signal_id, user_id=session['user_id']).first()
    if signal:
        signal.is_read = True
        db.session.commit()
    return jsonify({'success': True})

@dashboard.route('/signals/my')
@login_required
def my_signals():
    signals = Signal.query.filter_by(user_id=session['user_id']).order_by(Signal.created_at.desc()).all()
    return jsonify([{
        'id': s.id,
        'type': s.type,
        'message': s.message,
        'reply': s.reply,
        'replied_at': s.replied_at.strftime('%d.%m.%Y %H:%M') if s.replied_at else None,
        'is_read': s.is_read,
        'created_at': s.created_at.strftime('%d.%m.%Y %H:%M')
    } for s in signals])


# ============================================================
#  SUPPORT CENTER ROUTES
# ============================================================

@dashboard.route('/support/tickets')
@login_required
def get_tickets():
    """Всички tickets на потребителя"""
    user_id = session['user_id']
    tickets = Ticket.query.filter_by(user_id=user_id).order_by(Ticket.updated_at.desc()).all()
    result = []
    for t in tickets:
        unread = TicketMessage.query.filter_by(
            ticket_id=t.id, sender='admin', is_read=False).count()
        last_msg = TicketMessage.query.filter_by(
            ticket_id=t.id).order_by(TicketMessage.created_at.desc()).first()
        result.append({
            'id': t.id,
            'subject': t.subject,
            'type': t.type,
            'status': t.status,
            'unread': unread,
            'last_message': last_msg.body[:80] + '...' if last_msg and len(last_msg.body) > 80 else (last_msg.body if last_msg else ''),
            'updated_at': t.updated_at.strftime('%d.%m.%Y %H:%M')
        })
    return jsonify(result)

@dashboard.route('/support/tickets/<int:ticket_id>/messages')
@login_required
def get_ticket_messages(ticket_id):
    """Съобщенията в ticket"""
    ticket = Ticket.query.filter_by(id=ticket_id, user_id=session['user_id']).first_or_404()
    # Маркираме admin съобщенията като прочетени
    TicketMessage.query.filter_by(
        ticket_id=ticket_id, sender='admin', is_read=False).update({'is_read': True})
    db.session.commit()
    msgs = TicketMessage.query.filter_by(ticket_id=ticket_id).order_by(TicketMessage.created_at).all()
    return jsonify({
        'ticket': {
            'id': ticket.id,
            'subject': ticket.subject,
            'type': ticket.type,
            'status': ticket.status
        },
        'messages': [{
            'id': m.id,
            'sender': m.sender,
            'body': m.body,
            'created_at': m.created_at.strftime('%d.%m.%Y %H:%M')
        } for m in msgs]
    })

@dashboard.route('/support/tickets', methods=['POST'])
@login_required
def create_ticket():
    """Нов ticket"""
    from app.services.email import send_new_ticket_notification
    user_id = session['user_id']
    user = User.query.get(user_id)
    subject = request.form.get('subject', '').strip()[:200]
    body = request.form.get('body', '').replace('<', '&lt;').strip()[:500]
    ticket_type = request.form.get('type', 'question')
    if not subject or not body:
        return jsonify({'success': False, 'message': 'Попълнете всички полета'})
    ticket = Ticket(user_id=user_id, subject=subject, type=ticket_type)
    db.session.add(ticket)
    db.session.flush()
    msg = TicketMessage(ticket_id=ticket.id, sender='user', body=body)
    db.session.add(msg)
    db.session.commit()
    send_new_ticket_notification(user.name, user.email, subject, body, ticket.id)
    return jsonify({'success': True, 'ticket_id': ticket.id})

@dashboard.route('/support/tickets/<int:ticket_id>/reply', methods=['POST'])
@login_required
def reply_ticket(ticket_id):
    """Потребителят отговаря на ticket"""
    from app.services.email import send_user_reply_notification
    ticket = Ticket.query.filter_by(id=ticket_id, user_id=session['user_id']).first_or_404()
    user = User.query.get(session['user_id'])
    body = request.form.get('body', '').replace('<', '&lt;').strip()[:500]
    if not body:
        return jsonify({'success': False, 'message': 'Празно съобщение'})
    ticket.status = 'open'
    ticket.updated_at = datetime.utcnow()
    msg = TicketMessage(ticket_id=ticket_id, sender='user', body=body)
    db.session.add(msg)
    db.session.commit()
    send_user_reply_notification(user.name, user.email, ticket.subject, body, ticket_id)
    return jsonify({'success': True})

@dashboard.route('/support/unread')
@login_required
def support_unread():
    """Брой непрочетени отговори"""
    user_id = session['user_id']
    tickets = Ticket.query.filter_by(user_id=user_id).all()
    count = 0
    for t in tickets:
        count += TicketMessage.query.filter_by(
            ticket_id=t.id, sender='admin', is_read=False).count()
    return jsonify({'count': count})

# ============================================================
#  ADMIN ROUTES
# ============================================================


@dashboard.route('/settings')
@login_required
def settings():
    user = User.query.get(session['user_id'])
    if user and user.is_admin:
        return redirect(url_for('admin.admin_dashboard'))
    return render_template('user/settings.html', user=user)

@dashboard.route('/settings/profile', methods=['POST'])
@login_required
def settings_profile():
    try:
        user = User.query.get(session['user_id'])
        user.nick = request.form.get('nick', '').strip()
        user.firstname = request.form.get('firstname', '').strip()
        user.lastname = request.form.get('lastname', '').strip()
        db.session.commit()
        return jsonify({'success': True, 'message': '✓ Профилът е запазен'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})



@dashboard.route('/settings/check-password', methods=['POST'])
@login_required
def check_password():
    from werkzeug.security import check_password_hash
    user = User.query.get(session['user_id'])
    cur = request.form.get('current_password', '')
    valid = check_password_hash(user.password, cur)
    return jsonify({'valid': valid})

@dashboard.route('/settings/notifications', methods=['POST'])
@login_required
def settings_notifications():
    user = User.query.get(session['user_id'])
    data = request.get_json()
    user.notif_subscription = data.get('notif_subscription', True)
    db.session.commit()
    return jsonify({'success': True})

@dashboard.route('/logout-all', methods=['POST'])
@login_required
def logout_all():
    session.clear()
    return jsonify({'success': True})

@dashboard.route('/settings/password', methods=['POST'])
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

@dashboard.route('/admin/api/snapshots/<metric>')
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

@dashboard.route('/admin/api/snapshots/record', methods=['POST'])
@admin_required
def admin_record_snapshot():
    """Ръчно записване на snapshot"""
    snap = record_monthly_snapshot()
    return jsonify({'success': True, 'message': f'Snapshot {snap.year}-{snap.month:02d} записан'})
