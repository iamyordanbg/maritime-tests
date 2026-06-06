from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.user import User
from app.models.test import Test, TestImage, DemoVisit
from app.models.result import TestResult
from app.models.promo import PromoCode
from app.models.signal import Signal
from app.models.snapshot import MonthlySnapshot
from app.services.stats import get_admin_stats, record_monthly_snapshot
from app.utils.decorators import admin_required
from datetime import datetime, timedelta
import os, json

admin = Blueprint("admin", __name__, url_prefix="/admin")


@admin.route('/api/snapshots/<metric>')
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

@admin.route('/api/snapshots/record', methods=['POST'])
@admin_required
def admin_record_snapshot():
    """Ръчно записване на snapshot"""
    snap = record_monthly_snapshot()
    return jsonify({'success': True, 'message': f'Snapshot {snap.year}-{snap.month:02d} записан'})



@admin.route('')
@admin_required
def admin_dashboard():
    admin_user = User.query.get(session['user_id'])
    total_users = User.query.filter_by(is_admin=False).count()
    active_users = User.query.filter_by(is_admin=False, is_active=True).count()
    promo_all = PromoCode.query.count()
    active_promos = PromoCode.query.filter_by(is_active=True, is_used=False).count()
    promo_standby = PromoCode.query.filter_by(is_active=False, is_used=False).count()
    used_promos = PromoCode.query.filter_by(is_used=True).count()
    demo_sessions = DemoVisit.query.count()
    income_all = 0
    income_month = 0
    active_promos = PromoCode.query.filter_by(is_active=True).count()
    total_tests = Test.query.count()
    total_results = TestResult.query.count()
    open_signals = Signal.query.filter_by(status='open').count()
    recent_results = TestResult.query.order_by(TestResult.taken_at.desc()).limit(8).all()
    deck_q = db.session.query(db.func.sum(Test.question_count)).filter_by(category='deck').scalar() or 0
    engine_q = db.session.query(db.func.sum(Test.question_count)).filter_by(category='engine').scalar() or 0

    recent_signals = Signal.query.order_by(Signal.created_at.desc()).limit(4).all()

    # Demo visit stats
    from datetime import timedelta
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    demo_today = DemoVisit.query.filter(DemoVisit.visited_at >= today_start).count()
    demo_week = DemoVisit.query.filter(DemoVisit.visited_at >= week_start).count()
    demo_month = DemoVisit.query.filter(DemoVisit.visited_at >= month_start).count()
    demo_total = DemoVisit.query.count()

    # Unique visitors (by ip_hash)
    demo_unique_today = db.session.query(DemoVisit.ip_hash).filter(
        DemoVisit.visited_at >= today_start).distinct().count()
    demo_unique_week = db.session.query(DemoVisit.ip_hash).filter(
        DemoVisit.visited_at >= week_start).distinct().count()
    demo_unique_month = db.session.query(DemoVisit.ip_hash).filter(
        DemoVisit.visited_at >= month_start).distinct().count()
    demo_unique_total = db.session.query(DemoVisit.ip_hash).distinct().count()

    # Recent demo visits with order number
    recent_demo = DemoVisit.query.order_by(DemoVisit.visited_at.desc()).limit(10).all()

    return render_template('admin/dashboard.html',
        admin_user=admin_user,
        total_users=total_users, active_users=active_users, active_promos=active_promos,
        promo_all=promo_all, promo_standby=promo_standby, used_promos=used_promos,
        demo_sessions=demo_sessions,
        income_all=income_all, income_month=income_month,
        total_tests=total_tests, total_results=total_results,
        open_signals=open_signals, recent_results=recent_results,
        recent_signals=recent_signals,
        deck_q=deck_q, engine_q=engine_q,
        demo_today=demo_today,
        demo_week=demo_week,
        demo_month=demo_month,
        demo_total=demo_total,
        demo_unique_today=demo_unique_today,
        demo_unique_week=demo_unique_week,
        demo_unique_month=demo_unique_month,
        demo_unique_total=demo_unique_total,
        recent_demo=recent_demo
    )

@admin.route('/tests')
@admin_required
def admin_tests():
    deck_tests = Test.query.filter_by(category='deck').order_by(Test.created_at.desc()).all()
    engine_tests = Test.query.filter_by(category='engine').order_by(Test.created_at.desc()).all()
    
    # За всеки тест провери дали има 2+ резултата
    mistakes_ready = {}
    for t in deck_tests + engine_tests:
        count = TestResult.query.filter_by(
            user_id=session['user_id'], test_id=t.id
        ).filter(TestResult.test_type.in_(['test', 'mix'])).count()
        mistakes_ready[t.id] = count >= 2
    
    return render_template('admin/tests.html', deck_tests=deck_tests, engine_tests=engine_tests, mistakes_ready=mistakes_ready)

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
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
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
                session['pending_upload'] = {
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


@admin.route('/demo')
@admin_required
def admin_demo():
    tests = Test.query.filter_by(is_demo=True).order_by(Test.category, Test.level, Test.title).all()
    demo_count = Test.query.filter_by(is_demo=True).count()
    deck_demo = Test.query.filter_by(is_demo=True, category='deck').count()
    engine_demo = Test.query.filter_by(is_demo=True, category='engine').count()
    return render_template('admin/demo.html',
        active='demo',
        tests=tests,
        demo_count=demo_count,
        deck_demo=deck_demo,
        engine_demo=engine_demo
    )

@admin.route('/demo/toggle/<int:test_id>', methods=['POST'])
@admin_required
def admin_demo_toggle(test_id):
    # Extra security: verify request is AJAX from same origin
    if not request.is_json and request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        # Accept both JSON and same-origin fetch
        pass
    
    # Validate test_id is positive integer (already done by Flask route)
    test = Test.query.get_or_404(test_id)
    
    # Toggle demo status
    test.is_demo = not test.is_demo
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_demo': test.is_demo,
        'test_id': test.id
    })


@admin.route('/demo/reset-all', methods=['POST'])
@admin_required  
def admin_demo_reset_all():
    """Reset ALL tests to is_demo=False - emergency fix"""
    Test.query.update({Test.is_demo: False})
    db.session.commit()
    count = Test.query.count()
    return jsonify({'success': True, 'message': f'Reset {count} tests to is_demo=False'})




def get_google_redirect_uri():
    return os.environ.get('BASE_URL', 'https://web-production-ca6b6.up.railway.app') + '/auth/google/callback'
