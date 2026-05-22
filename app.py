from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import xlrd, os, json, random, string

app = Flask(__name__)
app.config['SECRET_KEY'] = 'maritime-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///maritime.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
os.makedirs('/tmp/uploads', exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

db = SQLAlchemy(app)

# ============================================================
#  МОДЕЛИ (Таблици в базата данни)
# ============================================================

class User(db.Model):
    """Моряци / потребители"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    rank = db.Column(db.String(100), default='')          # Длъжност/ранг
    company = db.Column(db.String(100), default='')       # Компания
    category = db.Column(db.String(20), default='deck')   # deck / engine
    level = db.Column(db.String(30), default='Operational Level')
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    promo_code = db.Column(db.String(50), default='')     # Кода с който се е регистрирал
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    results = db.relationship('TestResult', backref='user', lazy=True)

class Test(db.Model):
    """Тестове (качени от admin)"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(20), nullable=False)   # deck / engine
    level = db.Column(db.String(50), default='Operational Level')
    questions_json = db.Column(db.Text, nullable=False)   # JSON с въпросите
    question_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    results = db.relationship('TestResult', backref='test', lazy=True)

    def get_questions(self):
        return json.loads(self.questions_json)

class TestResult(db.Model):
    """Резултати от тестове"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    score = db.Column(db.Integer, default=0)
    total = db.Column(db.Integer, default=0)
    percent = db.Column(db.Float, default=0)
    passed = db.Column(db.Boolean, default=False)
    answers_json = db.Column(db.Text, default='{}')       # Запазени отговори
    taken_at = db.Column(db.DateTime, default=datetime.utcnow)

class PromoCode(db.Model):
    """Промокодове"""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    client_name = db.Column(db.String(200), default='')
    access_type = db.Column(db.String(100), default='Регулярни тестове')
    price = db.Column(db.Float, default=0)
    is_active = db.Column(db.Boolean, default=True)
    is_used = db.Column(db.Boolean, default=False)
    used_by = db.Column(db.String(120), default='')
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Signal(db.Model):
    """Сигнали / бъгове от потребители"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user_name = db.Column(db.String(100), default='Анонимен')
    type = db.Column(db.String(50), default='bug')        # bug / suggestion / question
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='open')     # open / resolved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ============================================================
#  ПОМОЩНИ ФУНКЦИИ
# ============================================================

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            return redirect(url_for('user_dashboard'))
        return f(*args, **kwargs)
    return decorated

def parse_xls_colors(filepath):
    """Чете XLS/XLSX и открива верни отговори по цвят на шрифта"""
    OPT_LETTERS = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
    questions = []

    if filepath.endswith('.xlsx'):
        # XLSX - използваме openpyxl
        import openpyxl
        wb = openpyxl.load_workbook(filepath)
        ws = wb.active

        for r_idx, row in enumerate(ws.iter_rows(min_row=2), start=1):
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
                        # Всичко различно от черно (000000 или FF000000)
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

            questions.append({'id': r_idx, 'question': q_text, 'options': options})

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

            questions.append({'id': r, 'question': q_text, 'options': options})

    return questions

def generate_promo_code(prefix='MAR'):
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{suffix}"

# ============================================================
#  AUTH ROUTES
# ============================================================

@app.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user and user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('user_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['is_admin'] = user.is_admin
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('user_dashboard'))
        flash('Грешен имейл или парола', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        promo = request.form.get('promo_code', '').strip()
        rank = request.form.get('rank', '').strip()

        # Проверка на промокода
        promo_obj = PromoCode.query.filter_by(code=promo, is_active=True, is_used=False).first()
        if not promo_obj:
            flash('Невалиден или вече използван промокод', 'error')
            return render_template('register.html')

        if User.query.filter_by(email=email).first():
            flash('Имейлът вече е регистриран', 'error')
            return render_template('register.html')

        user = User(
            name=name, email=email,
            password=generate_password_hash(password),
            rank=rank, promo_code=promo
        )
        db.session.add(user)

        promo_obj.is_used = True
        promo_obj.used_by = email
        promo_obj.used_at = datetime.utcnow()
        promo_obj.is_active = False

        db.session.commit()
        flash('Регистрацията е успешна! Влезте в профила си.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ============================================================
#  USER ROUTES
# ============================================================

@app.route('/dashboard')
@login_required
def user_dashboard():
    user = User.query.get(session['user_id'])
    results = TestResult.query.filter_by(user_id=user.id).order_by(TestResult.taken_at.desc()).limit(5).all()
    total_tests = TestResult.query.filter_by(user_id=user.id).count()
    passed_tests = TestResult.query.filter_by(user_id=user.id, passed=True).count()
    tests = Test.query.order_by(Test.created_at.desc()).all()
    return render_template('dashboard_user.html', user=user, results=results,
                           total_tests=total_tests, passed_tests=passed_tests, tests=tests)

@app.route('/test/<int:test_id>')
@login_required
def take_test(test_id):
    import random as rnd
    test = Test.query.get_or_404(test_id)
    questions = test.get_questions()
    shuffle = request.args.get('shuffle') == 'true'
    if shuffle:
        questions = list(questions)
        rnd.shuffle(questions)
    return render_template('take_test.html', test=test, questions=questions, shuffle=shuffle)

@app.route('/test/<int:test_id>/submit', methods=['POST'])
@login_required
def submit_test(test_id):
    test = Test.query.get_or_404(test_id)
    questions = test.get_questions()
    answers = request.json.get('answers', {})

    score = 0
    for q in questions:
        q_id = str(q['id'])
        selected = answers.get(q_id)
        if selected is not None:
            try:
                if q['options'][int(selected)]['isCorrect']:
                    score += 1
            except (IndexError, KeyError):
                pass

    total = len(questions)
    percent = round((score / total) * 100, 1) if total > 0 else 0
    passed = percent >= 70

    result = TestResult(
        user_id=session['user_id'],
        test_id=test_id,
        score=score, total=total,
        percent=percent, passed=passed,
        answers_json=json.dumps(answers)
    )
    db.session.add(result)
    db.session.commit()

    return jsonify({'score': score, 'total': total, 'percent': percent, 'passed': passed})

@app.route('/history')
@login_required
def history():
    user = User.query.get(session['user_id'])
    results = TestResult.query.filter_by(user_id=user.id).order_by(TestResult.taken_at.desc()).all()
    return render_template('history.html', user=user, results=results)

@app.route('/signal', methods=['POST'])
@login_required
def submit_signal():
    msg = request.form.get('message', '').strip()
    sig_type = request.form.get('type', 'bug')
    user = User.query.get(session['user_id'])
    if msg:
        signal = Signal(user_id=user.id, user_name=user.name, type=sig_type, message=msg)
        db.session.add(signal)
        db.session.commit()
    return redirect(url_for('user_dashboard'))

# ============================================================
#  ADMIN ROUTES
# ============================================================

@app.route('/admin')
@admin_required
def admin_dashboard():
    total_users = User.query.filter_by(is_admin=False).count()
    active_promos = PromoCode.query.filter_by(is_active=True).count()
    total_tests = Test.query.count()
    total_results = TestResult.query.count()
    open_signals = Signal.query.filter_by(status='open').count()
    recent_results = TestResult.query.order_by(TestResult.taken_at.desc()).limit(8).all()
    deck_q = db.session.query(db.func.sum(Test.question_count)).filter_by(category='deck').scalar() or 0
    engine_q = db.session.query(db.func.sum(Test.question_count)).filter_by(category='engine').scalar() or 0

    recent_signals = Signal.query.order_by(Signal.created_at.desc()).limit(4).all()

    return render_template('admin_dashboard.html',
        total_users=total_users, active_promos=active_promos,
        total_tests=total_tests, total_results=total_results,
        open_signals=open_signals, recent_results=recent_results,
        recent_signals=recent_signals,
        deck_q=deck_q, engine_q=engine_q)

@app.route('/admin/tests')
@admin_required
def admin_tests():
    deck_tests = Test.query.filter_by(category='deck').order_by(Test.created_at.desc()).all()
    engine_tests = Test.query.filter_by(category='engine').order_by(Test.created_at.desc()).all()
    return render_template('admin_tests.html', deck_tests=deck_tests, engine_tests=engine_tests)

@app.route('/admin/tests/upload', methods=['POST'])
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
        questions = parse_xls_colors(filepath)
        final_title = title if title else filename.replace('.xls', '').replace('.xlsx', '')

        test = Test(
            title=final_title,
            category=category,
            level=level,
            questions_json=json.dumps(questions, ensure_ascii=False),
            question_count=len(questions)
        )
        db.session.add(test)
        db.session.commit()
        os.remove(filepath)
        return jsonify({'success': True, 'total': len(questions), 'title': final_title})
    except Exception as e:
        try: os.remove(filepath)
        except: pass
        return jsonify({'error': str(e)}), 500

@app.route('/admin/tests/<int:test_id>/edit')
@admin_required
def edit_test(test_id):
    test = Test.query.get_or_404(test_id)
    questions = test.get_questions()
    return render_template('edit_test.html', test=test, questions=questions)

@app.route('/admin/tests/<int:test_id>/update-info', methods=['POST'])
@admin_required
def update_test_info(test_id):
    test = Test.query.get_or_404(test_id)
    data = request.json
    test.title = data.get('title', test.title)
    test.level = data.get('level', test.level)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/tests/<int:test_id>/delete', methods=['POST'])
@admin_required
def delete_test(test_id):
    test = Test.query.get_or_404(test_id)
    db.session.delete(test)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/tests/<int:test_id>/questions')
@admin_required
def get_test_questions(test_id):
    test = Test.query.get_or_404(test_id)
    return jsonify({'questions': test.get_questions(), 'title': test.title})

@app.route('/admin/tests/<int:test_id>/questions', methods=['POST'])
@admin_required
def save_test_questions(test_id):
    test = Test.query.get_or_404(test_id)
    questions = request.json.get('questions', [])

    # Гарантира само ЕДИН верен отговор на въпрос
    for q in questions:
        correct_found = False
        for opt in q.get('options', []):
            if opt.get('isCorrect') and not correct_found:
                correct_found = True
            elif opt.get('isCorrect') and correct_found:
                opt['isCorrect'] = False  # Премахва дублиращи се верни
        # Ако няма верен — маркира първия
        if not correct_found and q.get('options'):
            q['options'][0]['isCorrect'] = True

    test.questions_json = json.dumps(questions, ensure_ascii=False)
    test.question_count = len(questions)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/<int:user_id>')
@admin_required
def admin_user_detail(user_id):
    user = User.query.get_or_404(user_id)
    results = TestResult.query.filter_by(user_id=user_id).order_by(TestResult.taken_at.desc()).all()
    return render_template('admin_user_detail.html', user=user, results=results)

@app.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({'success': True, 'is_active': user.is_active})

@app.route('/admin/promos')
@admin_required
def admin_promos():
    promos = PromoCode.query.order_by(PromoCode.created_at.desc()).all()
    active = sum(1 for p in promos if p.is_active)
    used = sum(1 for p in promos if p.is_used)
    return render_template('admin_promos.html', promos=promos, active=active, used=used)

@app.route('/admin/promos/create', methods=['POST'])
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

@app.route('/admin/promos/<int:promo_id>/delete', methods=['POST'])
@admin_required
def delete_promo(promo_id):
    promo = PromoCode.query.get_or_404(promo_id)
    db.session.delete(promo)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/signals')
@admin_required
def admin_signals():
    signals = Signal.query.order_by(Signal.created_at.desc()).all()
    open_count = Signal.query.filter_by(status='open').count()
    return render_template('admin_signals.html', signals=signals, open_count=open_count)

@app.route('/admin/signals/<int:signal_id>/resolve', methods=['POST'])
@admin_required
def resolve_signal(signal_id):
    signal = Signal.query.get_or_404(signal_id)
    signal.status = 'resolved'
    db.session.commit()
    return jsonify({'success': True})

# ============================================================
#  ИНИЦИАЛИЗАЦИЯ
# ============================================================

def create_admin():
    """Създава администратор при първо стартиране"""
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(is_admin=True).first():
            admin = User(
                name='Администратор',
                email='admin@maritime.bg',
                password=generate_password_hash('admin123'),
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✓ Администратор създаден: admin@maritime.bg / admin123")

# Инициализация на базата - работи и на Railway и локално
create_admin()

if __name__ == '__main__':
    print("=" * 50)
    print("  Морски Тестове - Стартира...")
    print("  http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)
