from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.user import User
from app.models.test import Test, TestImage, DemoVisit
from app.models.result import TestResult
from app.models.promo import PromoCode
from app.models.signal import Signal
from app.models.ticket import Ticket, TicketMessage
from app.models.snapshot import MonthlySnapshot
from app.services.stats import get_admin_stats, record_monthly_snapshot
from app.utils.decorators import admin_required
from datetime import datetime, timedelta
import os, json

admin = Blueprint("admin", __name__, url_prefix="/admin")

import tempfile
import xlrd

def parse_xls_colors(filepath):
    """Чете XLS/XLSX и открива верни отговори по цвят на шрифта"""
    OPT_LETTERS = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
    questions = []

    if filepath.endswith('.xlsx'):
        import openpyxl
        wb = openpyxl.load_workbook(filepath)
        ws = wb.active

        # Извличаме снимките — всяка снимка принадлежи на въпроса НАД нея
        image_map = {}
        try:
            all_images = ws._images
            print(f"PARSE: Found {len(all_images)} images in worksheet")
        except Exception as e:
            print(f"PARSE: Cannot access _images: {e}")
            all_images = []
        
        for img in all_images:
            try:
                anchor_row_0idx = img.anchor._from.row
                ws_row_of_image = anchor_row_0idx + 1
                question_ws_row = ws_row_of_image - 1
                # Try different methods to get image data
                try:
                    img_data = img._data()
                except:
                    try:
                        img_data = img.ref.blob
                    except:
                        img_data = bytes(img.ref._data)
                fmt = 'jpg' if img_data[:2] == b'\xff\xd8' else 'png'
                image_map[question_ws_row] = (img_data, fmt)
            except Exception as e:
                print(f"PARSE: Image error: {e}")

        for r_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
            q_cell = row[0]
            if not q_cell.value or str(q_cell.value).strip() == '':
                continue
            q_text = str(q_cell.value).strip()
            options = []
            opt_idx = 0

            for cell in row[1:]:
                if not cell.value or str(cell.value).strip() == '':
                    continue
                text = str(cell.value).strip()
                is_correct = False
                if cell.font and cell.font.color:
                    color = cell.font.color
                    if color.type == 'rgb':
                        rgb = color.rgb
                        if rgb not in ('00000000', 'FF000000', '000000'):
                            is_correct = True
                    elif color.type == 'theme':
                        if color.theme not in (0, 1):
                            is_correct = True
                options.append({
                    'letter': OPT_LETTERS[opt_idx] if opt_idx < len(OPT_LETTERS) else 'x',
                    'text': text,
                    'isCorrect': is_correct
                })
                opt_idx += 1

            if options and not any(o['isCorrect'] for o in options):
                options[0]['isCorrect'] = True

            q_id = len(questions) + 1  # 1, 2, 3... последователно
            q = {'id': q_id, 'question': q_text, 'options': options}
            if r_idx in image_map:
                q['has_image'] = True
                q['_image_data'] = image_map[r_idx]
            questions.append(q)

    else:
        # XLS - използваме xlrd
        BLACK_IDX = 8
        wb = xlrd.open_workbook(filepath, formatting_info=True)
        ws = wb.sheet_by_index(0)

        for r in range(1, ws.nrows):
            q_val = ws.cell(r, 0).value
            if not q_val or str(q_val).strip() == '':
                continue
            q_text = str(q_val).strip()
            options = []
            opt_idx = 0

            for c in range(1, ws.ncols):
                cell = ws.cell(r, c)
                if not cell.value or str(cell.value).strip() == '':
                    continue
                text = str(cell.value).strip()
                xf_idx = ws.cell_xf_index(r, c)
                xf = wb.xf_list[xf_idx]
                font = wb.font_list[xf.font_index]
                is_correct = (font.colour_index != BLACK_IDX)
                options.append({
                    'letter': OPT_LETTERS[opt_idx] if opt_idx < len(OPT_LETTERS) else 'x',
                    'text': text,
                    'isCorrect': is_correct
                })
                opt_idx += 1

            if options and not any(o['isCorrect'] for o in options):
                options[0]['isCorrect'] = True

            questions.append({'id': len(questions) + 1, 'question': q_text, 'options': options})

    return questions

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


@admin.route('/tests/force-upload', methods=['POST'])
@admin_required
def force_upload():
    """Качва тест използвайки вече парснатите данни от сесията"""
    pending_file = session.get('pending_upload_file')
    if pending_file and __import__('os').path.exists(pending_file):
        with open(pending_file) as _pf:
            pending = __import__('json').load(_pf)
    else:
        pending = session.get('pending_upload')
    if not pending:
        return jsonify({'error': 'Няма данни за качване'}), 400
    
    new_title = request.json.get('title', pending['title'])
    
    test = Test(
        title=new_title,
        category=pending['category'],
        level=pending['level'],
        questions_json=pending['questions_json'],
        question_count=pending['question_count'],
        is_demo=False
    )
    db.session.add(test)
    db.session.flush()
    
    # Запази снимките
    if pending.get('images'):
        img_dir = f"/tmp/qimages/{test.id}"
        os.makedirs(img_dir, exist_ok=True)
        for q_id, (img_data, fmt) in pending['images']:
            try:
                with open(f"{img_dir}/{q_id}.{fmt}", 'wb') as f_img:
                    f_img.write(img_data)
            except Exception as e:
                print(f"Image save error: {e}")
    
    db.session.commit()
    session.pop('pending_upload', None)
    return jsonify({'success': True, 'title': new_title, 'total': pending['question_count']})

# toggle_demo route removed - use /admin/demo/toggle/<id>

@admin.route('/tests/upload', methods=['POST'])
@admin_required
def upload_test():
    file = request.files.get('file')
    title = request.form.get('title', '').strip()
    category = request.form.get('category', 'deck')
    level = request.form.get('level', 'Operational Level')

    if not file:
        return jsonify({'error': 'Няма файл'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(tempfile.gettempdir(), filename)
    file.save(filepath)

    try:
        print(f"UPLOAD: Starting parse of {filename}, size={os.path.getsize(filepath)} bytes")
        questions = parse_xls_colors(filepath)
        print(f"UPLOAD: Parsed {len(questions)} questions")
        with_img = sum(1 for q in questions if q.get('has_image'))
        print(f"UPLOAD: Questions with images: {with_img}")
        final_title = title if title else filename.replace('.xls', '').replace('.xlsx', '')
        
        # Провери за дублиращо се заглавие
        existing = Test.query.filter_by(title=final_title).first()
        if existing:
            force = request.form.get('force', 'false')
            if force != 'true':
                # Запази парснатите данни в сесията за по-късно
                import pickle, base64
                # Запазваме в /tmp вместо в сесията (cookie limit)
                _pending_data = {
                    'questions_json': __import__('json').dumps(
                        [{k: v for k, v in q.items() if k != '_image_data'} for q in questions],
                        ensure_ascii=False
                    ),
                    'question_count': len(questions),
                    'category': category,
                    'level': level,
                    'title': final_title,
                    'images': [(q['id'], q['_image_data']) for q in questions if '_image_data' in q]
                }
                _pending_file = f'/tmp/pending_upload_{session.get("user_id","admin")}.json'
                with open(_pending_file, 'w') as _pf:
                    __import__('json').dump({k: v for k, v in _pending_data.items() if k != 'images'}, _pf)
                session['pending_upload_file'] = _pending_file
                session['pending_upload'] = {
                    'title': final_title,
                    'category': category,
                    'level': level,
                    'question_count': len(questions)
                }
                os.remove(filepath)
                return jsonify({'duplicate': True, 'title': final_title})
            else:
                # Намери следващия свободен индекс
                idx = 1
                while Test.query.filter_by(title=f"{final_title} ({idx})").first():
                    idx += 1
                final_title = f"{final_title} ({idx})" 

        # Извади снимките преди да запишем JSON
        images_to_save = []
        for q in questions:
            if '_image_data' in q:
                images_to_save.append((q['id'], q.pop('_image_data')))

        test = Test(
            title=final_title,
            category=category,
            level=level,
            questions_json=json.dumps(questions, ensure_ascii=False),
            question_count=len(questions),
            is_demo=False
        )
        db.session.add(test)
        db.session.flush()
        test_id_for_images = test.id
        db.session.commit()
        os.remove(filepath)

        # Запази снимките директно
        if images_to_save:
            img_dir = f"/tmp/qimages/{test_id_for_images}"
            print(f"IMAGES: Saving {len(images_to_save)} images to {img_dir}")
            try:
                os.makedirs(img_dir, exist_ok=True)
                print(f"IMAGES: Directory created: {img_dir}")
            except Exception as e:
                print(f"IMAGES: Cannot create dir {img_dir}: {e}")
                # Fallback to /tmp
                img_dir = f"/tmp/qimages/{test_id_for_images}"
                os.makedirs(img_dir, exist_ok=True)
                print(f"IMAGES: Using fallback: {img_dir}")
            
            saved_count = 0
            for q_id, (img_data, fmt) in images_to_save:
                try:
                    img_path = f"{img_dir}/{q_id}.{fmt}"
                    with open(img_path, 'wb') as f_img:
                        f_img.write(img_data)
                    saved_count += 1
                except Exception as e:
                    print(f"IMAGES: Save error q{q_id}: {e}")
            print(f"IMAGES: Saved {saved_count}/{len(images_to_save)} images")

        return jsonify({'success': True, 'total': len(questions), 'title': final_title})
    except Exception as e:
        try: os.remove(filepath)
        except: pass
        return jsonify({'error': str(e)}), 500

@admin.route('/tests/<int:test_id>/edit')
@admin_required
def edit_test(test_id):
    test = Test.query.get_or_404(test_id)
    questions = test.get_questions()
    questions = inject_images(test_id, questions)
    return render_template('admin/edit_test.html', test=test, questions=questions)

@admin.route('/tests/<int:test_id>/update-info', methods=['POST'])
@admin_required
def update_test_info(test_id):
    test = Test.query.get_or_404(test_id)
    data = request.json
    test.title = data.get('title', test.title)
    test.level = data.get('level', test.level)
    db.session.commit()
    return jsonify({'success': True})

@admin.route('/tests/<int:test_id>/delete', methods=['POST'])
@admin_required
def delete_test(test_id):
    test = Test.query.get_or_404(test_id)
    # Изтрий резултатите
    TestResult.query.filter_by(test_id=test_id).delete()
    db.session.delete(test)
    # Изтрий снимките от файловата система
    import shutil
    img_dir = f"/tmp/qimages/{test_id}"
    if os.path.exists(img_dir):
        shutil.rmtree(img_dir)
    db.session.commit()
    return jsonify({'success': True})

@admin.route('/tests/<int:test_id>/questions')
@admin_required
def get_test_questions(test_id):
    test = Test.query.get_or_404(test_id)
    return jsonify({'questions': test.get_questions(), 'title': test.title})

@admin.route('/tests/<int:test_id>/questions', methods=['POST'])
@admin_required
def save_test_questions(test_id):
    try:
        test = Test.query.get_or_404(test_id)
        questions = request.json.get('questions', [])

        # Запази has_image флага от оригиналните въпроси
        original = {str(q['id']): q for q in test.get_questions()}
        
        for q in questions:
            # Възстанови has_image от оригинала
            orig = original.get(str(q['id']))
            if orig and orig.get('has_image'):
                q['has_image'] = True

            # Гарантира само ЕДИН верен отговор
            correct_found = False
            for opt in q.get('options', []):
                if opt.get('isCorrect') and not correct_found:
                    correct_found = True
                elif opt.get('isCorrect') and correct_found:
                    opt['isCorrect'] = False
            if not correct_found and q.get('options'):
                q['options'][0]['isCorrect'] = True

        test.questions_json = json.dumps(questions, ensure_ascii=False)
        test.question_count = len(questions)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        import traceback
        print("SAVE QUESTIONS ERROR:", traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@admin.route('/users')
@admin_required
def admin_users():
    users = User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users, now=datetime.utcnow())


@admin.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        return jsonify({'success': False, 'message': 'Cannot delete admin'})
    db.session.delete(user)
    db.session.commit()
    return jsonify({'success': True})

@admin.route('/users/<int:user_id>')
@admin_required
def admin_user_detail(user_id):
    user = User.query.get_or_404(user_id)
    results = TestResult.query.filter_by(user_id=user_id).order_by(TestResult.taken_at.desc()).all()
    return render_template('admin/user_detail.html', user=user, results=results)

@admin.route('/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({'success': True, 'is_active': user.is_active})

@admin.route('/promos')
@admin_required
def admin_promos():
    promos = PromoCode.query.order_by(PromoCode.created_at.desc()).all()
    active = sum(1 for p in promos if p.is_active)
    used = sum(1 for p in promos if p.is_used)
    return render_template('admin/promos.html', promos=promos, active=active, used=used)

@admin.route('/promos/create', methods=['POST'])
@admin_required
def create_promo():
    client = request.form.get('client_name', '').strip()
    access_type = request.form.get('access_type', 'Регулярни тестове')
    price = float(request.form.get('price', 0) or 0)
    code = generate_promo_code()

    promo = PromoCode(code=code, client_name=client, access_type=access_type, price=price)
    db.session.add(promo)
    db.session.commit()
    return jsonify({'success': True, 'code': code})

@admin.route('/promos/<int:promo_id>/delete', methods=['POST'])
@admin_required
def delete_promo(promo_id):
    promo = PromoCode.query.get_or_404(promo_id)
    db.session.delete(promo)
    db.session.commit()
    return jsonify({'success': True})

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

@admin.route('')
@admin_required
def admin_dashboard():
    from app.services.stats import get_admin_stats
    from app.models.result import TestResult
    stats = get_admin_stats()
    admin_user = User.query.filter_by(is_admin=True).first()
    recent_results = TestResult.query.order_by(TestResult.taken_at.desc()).limit(10).all()
    recent_signals = []
    return render_template('admin/dashboard.html',
        admin_user=admin_user,
        recent_results=recent_results,
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

@admin.route('/support')
@admin_required
def admin_support():
    tickets = Ticket.query.order_by(Ticket.created_at.desc()).all()
    admin_user = User.query.filter_by(is_admin=True).first()
    return render_template('admin/support.html', tickets=tickets, admin_user=admin_user)

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
