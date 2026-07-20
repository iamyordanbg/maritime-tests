"""
app/routes/test_taking.py
==========================
Test/Mix/Mistakes/Simulator/Demo/Image serving — extraction-нат от
dashboard.py (Group A audit, File Limits).
"""
import json
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from app.extensions import db
from app.models.user import User
from app.models.test import Test
from app.models.result import TestResult
from app.utils.decorators import login_required
from app.utils.images import inject_images
from app.permissions.roles import user_can_access_test

test_taking = Blueprint("test_taking", __name__)


@test_taking.route('/test/<int:test_id>')
@login_required
def take_test(test_id):
    import random as rnd
    from app.utils.grants import test_access_lock
    user = User.query.get(session['user_id'])
    test = Test.query.get_or_404(test_id)
    if not user_can_access_test(user, test):
        flash('Този тест не е достъпен в твоя план. Избери го от Library или направи ъпгрейд.', 'warning')
        return redirect(url_for('dashboard.library'))
    # user_can_access_test() може да е задействала library_refresh_if_expired()
    # (изтичане на library прозорец + триене на стари TestResult редове) -
    # тя не commit-ва сама, за разлика от предишната локална версия тук.
    db.session.commit()
    locked, _owning_grant = test_access_lock(user, test_id)
    if locked:
        return redirect(url_for('dashboard.user_dashboard', quota_exceeded=1))
    questions = test.get_questions()
    questions = inject_images(test_id, questions)
    shuffle = request.args.get('shuffle') == 'true'
    if shuffle:
        questions = list(questions)
        rnd.shuffle(questions)
    is_free_plan = not user.is_admin and not user.has_active_plan()
    test_type = 'mix' if shuffle else 'test'
    return render_template('user/test.html', test=test, questions=questions, shuffle=shuffle, test_type=test_type, is_free_plan=is_free_plan, is_demo=False)


@test_taking.route('/test/<int:test_id>/mistakes')
@login_required
def test_mistakes(test_id):

    import random as rnd
    from app.permissions.roles import user_can_access_mistakes
    from app.utils.grants import test_access_lock
    user = User.query.get(session['user_id'])
    test = Test.query.get_or_404(test_id)
    if not user_can_access_mistakes(user, test):
        flash('Този тест не е достъпен в твоя план. Избери го от Library или направи ъпгрейд.', 'warning')
        return redirect(url_for('dashboard.library'))
    # user_can_access_mistakes()->user_can_access_test() може да е задействала
    # library_refresh_if_expired() (изтичане на прозорец + триене на стари
    # TestResult редове) - тя не commit-ва сама.
    db.session.commit()
    locked, _owning_grant = test_access_lock(user, test_id)
    if locked:
        return redirect(url_for('dashboard.user_dashboard', quota_exceeded=1))

    # Намери grant-а, който притежава ТОЗИ тест — резултатите преди неговата
    # активация не се броят (иначе стар план на същия test_id лъжливо отключва).
    grant_activated_at = None
    for g in user.active_gold_grants():
        if test_id in g.test_id_list():
            grant_activated_at = g.activated_at
            break
    if grant_activated_at is None:
        for g in user.active_plan_grants():
            if g.library_test_id == test_id:
                grant_activated_at = g.activated_at
                break

    # Вземи последните 2 резултата от обикновен тест или микс, СЛЕД активацията на grant-а
    results_query = TestResult.query.filter_by(
        user_id=session['user_id'],
        test_id=test_id
    ).filter(
        TestResult.test_type.in_(['test', 'mix'])
    )
    if grant_activated_at:
        results_query = results_query.filter(TestResult.taken_at >= grant_activated_at)
    last_results = results_query.order_by(TestResult.taken_at.desc()).limit(2).all()

    if len(last_results) < 2:
        flash('Трябват поне 2 решени теста (Тест или Микс) за тази функция', 'error')
        return redirect(url_for('dashboard.user_dashboard'))

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
        return redirect(url_for('dashboard.user_dashboard'))

    # Вземи въпросите с грешки
    wrong_questions = [q for q in all_questions if str(q['id']) in wrong_ids]
    wrong_questions = inject_images(test_id, wrong_questions)
    rnd.shuffle(wrong_questions)

    return render_template('user/test.html', test=test, questions=wrong_questions,
                         shuffle=True, test_type='mistakes', is_demo=False)


@test_taking.route('/test/<int:test_id>/simulator')
@login_required
def simulator(test_id):

    import random as rnd
    from app.utils.grants import test_access_lock
    user = User.query.get(session['user_id'])
    test = Test.query.get_or_404(test_id)

    # БЪГ ФИКС: демо тестовете (test.is_demo) трябва да са ВИНАГИ свободно
    # достъпни за Simulator, без да минават през изискването "първо избери
    # този тест в Library" - точно както вече работи за Test/Mix/Mistakes
    # (виж user_can_access_test(), която изрично bypass-ва is_demo).
    # Преди тази поправка симулаторът НЯМАШЕ този bypass и връщаше всеки
    # опит за демо симулатор обратно към /library с грешка "не е твоят
    # избран тест" - демото трябваше да е достъпно за всеки, без избор.
    if user.is_admin or test.is_demo:
        pass
    elif not user.has_active_plan():
        if user.library_refresh_if_expired():
            db.session.commit()
        if not (user.library_window_active() and user.library_test_id == test_id):
            flash('Този тест не е твоят активно избран тест в Library. Отвори картата му и натисни бутона за избор, за да отключиш Simulator за него.', 'warning')
            return redirect(url_for('dashboard.library'))
        if not user.library_simulator_available():
            # Free план: 1 симулатор на ден. Тих redirect към dashboard,
            # без popup/toast (потвърдено предпочитание от предишна сесия) -
            # клиентът просто остава на dashboard-а, вижда картата си там.
            return redirect(url_for('dashboard.user_dashboard'))
        # ВАЖНО (бъг поправка): library_last_simulator_at СЕ ЗАПИСВА едва при
        # реален SUBMIT (виж submit_test в app/routes/tests.py), НЕ тук при
        # обикновено зареждане на страницата. Преди тази поправка
        # потребител, който само отваря симулатора и НЕ отговори на нито
        # един въпрос (после затваря страницата/акаунта), губеше дневния си
        # лимит без резултат в историята - сериозен бъг, докладван от
        # потребител. Сега лимитът се "изразходва" само при действително
        # завършен и предаден тест.
    else:
        locked, _owning_grant = test_access_lock(user, test_id)
        if locked:
            return redirect(url_for('dashboard.user_dashboard', quota_exceeded=1))

    questions = test.get_questions()
    questions = inject_images(test_id, questions)
    rnd.shuffle(questions)
    questions = questions[:45]  # Max 45 въпроса за 60 мин
    is_free_plan = not user.is_admin and not user.has_active_plan()
    return render_template('user/simulator.html', test=test, questions=questions, time_limit=60, is_free_plan=is_free_plan)


@test_taking.route('/demo/test/<int:test_id>')
def demo_test(test_id):
    """Демо тест - без регистрация"""
    import random as rnd
    test = Test.query.get_or_404(test_id)
    if not test.is_demo:
        flash('Този тест вече не е достъпен като демо. Избери друг тест от списъка.', 'warning')
        return redirect(url_for('dashboard.demo'))
    mode = request.args.get('mode', 'test')
    questions = test.get_questions()
    questions = inject_images(test_id, questions)

    # Маркетингово решение: демото (публичната /demo секция, зареждана от
    # landing страницата) показва САМО Simulator - НЕ Test/Mix/Mistakes.
    # Заключено и тук на сървъра (не само скрито от UI-то), за да не може
    # някой просто да редактира ?mode= в адреса и да заобиколи ограничението.
    rnd.shuffle(questions)
    questions = questions[:45]
    return render_template('user/simulator.html', test=test, questions=questions, time_limit=60, is_demo=True, is_free_plan=True)


@test_taking.route('/demo/test/<int:test_id>/submit', methods=['POST'])
def demo_submit(test_id):
    """Оценяване на демо тест - без регистрация"""
    test = Test.query.get_or_404(test_id)
    all_questions = test.get_questions()
    answers = request.json.get('answers', {})
    answers_norm = {str(k): int(v) for k, v in answers.items()}
    score = 0
    for q in all_questions:
        selected = answers_norm.get(str(q['id']))
        if selected is not None:
            try:
                if q['options'][int(selected)]['isCorrect']:
                    score += 1
            except (IndexError, KeyError):
                pass
    total = len(all_questions)
    percent = round((score / total) * 100, 1) if total > 0 else 0
    passed = percent >= 90
    return jsonify({'score': score, 'total': total, 'percent': percent, 'passed': passed})


@test_taking.route('/qimage/<int:test_id>/<path:filename>')
def serve_qimage(test_id, filename):
    """Legacy route — все още активен за снимки, останали в Postgres
    (storage='db'), и като fallback за стари линкове/кеш в браузъра.
    Новите снимки (storage='r2') вече идват директно от R2 URL, инжектиран
    от inject_images() — този route не се удря за тях в нормалния поток."""
    from flask import abort, Response, redirect
    from app.utils.images import get_image_bytes
    from app.models.test import TestImage
    from app.utils import r2_storage
    try:
        question_id = int(filename.rsplit('.', 1)[0])
    except (ValueError, IndexError):
        abort(404)

    row = TestImage.query.filter_by(test_id=test_id, question_id=question_id).first()
    if row and row.storage == 'r2' and row.r2_key:
        return redirect(r2_storage.public_url_for(row.r2_key), code=301)

    result = get_image_bytes(test_id, question_id)
    if not result:
        abort(404)
    img_bytes, fmt = result
    mimetype = 'image/png' if fmt == 'png' else 'image/jpeg'
    resp = Response(img_bytes, mimetype=mimetype)
    resp.headers['Cache-Control'] = 'public, max-age=2592000'  # 30 дни, снимките не се менят
    return resp
