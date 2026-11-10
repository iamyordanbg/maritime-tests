"""
tests/integration/test_review_prompt_choices.py
===============================================
Прозорецът за отзив: Not now (имейл след седмица) / No thanks (никога повече) / Submit review
(задължително описание). Напомнянето по имейл и страницата "No thanks".
"""
from datetime import datetime, timedelta

import pytest

from app.models.review import Review
from app.models.review_prompt import ReviewPrompt
from app.models.plan_grant import PlanGrant
from app.services import review_reminders
from app.services.reviews import REVIEW_REMINDER_DAYS

AJAX = {'X-Requested-With': 'XMLHttpRequest'}


@pytest.fixture(autouse=True)
def _clean(db):
    for model in (Review, ReviewPrompt):
        model.query.delete()
    db.session.commit()
    yield
    for model in (Review, ReviewPrompt):
        model.query.delete()
    db.session.commit()


@pytest.fixture
def near_expiry_user(db, basic_user):
    PlanGrant.query.filter_by(user_id=basic_user.id).update({'expires_at': datetime.utcnow() + timedelta(days=1)})
    db.session.commit()
    return basic_user


def _login(client, email='basic@test.bg'):
    client.post('/login', data={'email': email, 'password': 'Test123'}, headers=AJAX)


def _prompt(client):
    return client.get('/api/review/should-prompt').get_json()


def test_initial_prompt_shown_near_expiry(client, near_expiry_user):
    _login(client)
    data = _prompt(client)
    assert data['should_prompt'] is True and data['variant'] == 'initial'


def test_not_now_hides_prompt_and_schedules_reminder(client, db, near_expiry_user):
    _login(client)
    assert client.post('/api/review/postpone').get_json() == {'success': True}
    data = _prompt(client)
    assert data['should_prompt'] is False and data['variant'] is None
    state = ReviewPrompt.query.filter_by(user_id=near_expiry_user.id).one()
    delta = state.remind_at - datetime.utcnow()
    assert timedelta(days=REVIEW_REMINDER_DAYS) - timedelta(minutes=1) < delta <= timedelta(days=REVIEW_REMINDER_DAYS)
    assert state.declined is False and state.reminder_sent_at is None


def test_no_thanks_never_shows_again_and_blocks_reminder(client, db, near_expiry_user):
    _login(client)
    client.post('/api/review/postpone')
    client.post('/api/review/decline')
    assert _prompt(client)['should_prompt'] is False
    state = ReviewPrompt.query.filter_by(user_id=near_expiry_user.id).one()
    state.reminder_sent_at = datetime.utcnow()  # дори и след изпратено напомняне
    db.session.commit()
    assert _prompt(client)['should_prompt'] is False
    state.remind_at = datetime.utcnow() - timedelta(days=1)
    state.reminder_sent_at = None
    db.session.commit()
    assert review_reminders.send_due_reminders() == 0


def test_decline_without_prior_state_creates_one(client, db, near_expiry_user):
    _login(client)
    client.post('/api/review/decline')
    assert ReviewPrompt.query.filter_by(user_id=near_expiry_user.id).one().declined is True


def test_reminder_variant_after_email_sent(client, db, near_expiry_user):
    _login(client)
    client.post('/api/review/postpone')
    ReviewPrompt.query.filter_by(user_id=near_expiry_user.id).update({'reminder_sent_at': datetime.utcnow()})
    db.session.commit()
    data = _prompt(client)
    assert data['should_prompt'] is True and data['variant'] == 'reminder'


def test_reminder_variant_even_if_plan_no_longer_near_expiry(client, db, basic_user):
    PlanGrant.query.filter_by(user_id=basic_user.id).update({'expires_at': datetime.utcnow() + timedelta(days=20)})
    db.session.add(ReviewPrompt(user_id=basic_user.id, declined=False,
                                remind_at=datetime.utcnow() - timedelta(days=1), reminder_sent_at=datetime.utcnow()))
    db.session.commit()
    _login(client)
    assert _prompt(client)['variant'] == 'reminder'


def test_no_prompt_after_review_submitted(client, near_expiry_user):
    _login(client)
    assert client.post('/api/review/submit', data={'stars': 5, 'text': 'Great', 'visibility': 'anonymous'}).get_json()['success']
    assert _prompt(client)['should_prompt'] is False


@pytest.mark.parametrize('form,message', [
    ({'stars': 5, 'text': '   '}, 'Please write a short review.'),
    ({'stars': 0, 'text': 'x'}, 'Please choose a rating from 1 to 5 stars.'),
])
def test_submit_requires_description_and_stars(client, db, near_expiry_user, form, message):
    _login(client)
    res = client.post('/api/review/submit', data={**form, 'visibility': 'anonymous'})
    assert res.status_code == 400 and res.get_json()['message'] == message
    assert Review.query.count() == 0


def test_submit_twice_message_in_english(client, near_expiry_user):
    _login(client)
    client.post('/api/review/submit', data={'stars': 5, 'text': 'a', 'visibility': 'anonymous'})
    res = client.post('/api/review/submit', data={'stars': 5, 'text': 'b', 'visibility': 'anonymous'})
    assert res.get_json()['message'] == 'You have already left a review.'


def test_admin_gets_no_prompt(client, admin_user):
    client.post('/login', data={'email': 'admin@test.bg', 'password': 'Admin123'}, headers=AJAX)
    assert _prompt(client)['should_prompt'] is False


# ---------- напомняне по имейл ----------

class _Mail:
    def __init__(self, ok=True):
        self.ok, self.calls = ok, []

    def base_url(self):
        return 'https://site.test'

    def send_review_reminder_email(self, to_email, decline_url, dashboard_url):
        self.calls.append((to_email, decline_url, dashboard_url))
        return self.ok


def _due(db, user, days_ago=1):
    db.session.add(ReviewPrompt(user_id=user.id, declined=False, remind_at=datetime.utcnow() - timedelta(days=days_ago)))
    db.session.commit()


def test_due_reminder_sent_once(db, basic_user, monkeypatch):
    mail = _Mail()
    monkeypatch.setattr(review_reminders, 'mailer', mail)
    _due(db, basic_user)
    assert review_reminders.send_due_reminders() == 1
    assert review_reminders.send_due_reminders() == 0  # не се праща втори път
    to, decline_url, dashboard_url = mail.calls[0]
    assert to == 'basic@test.bg' and dashboard_url == 'https://site.test/review/open'
    token = decline_url.rsplit('/', 1)[1]
    assert review_reminders.read_decline_token(token) == basic_user.id


def test_not_yet_due_is_not_sent(db, basic_user, monkeypatch):
    mail = _Mail()
    monkeypatch.setattr(review_reminders, 'mailer', mail)
    db.session.add(ReviewPrompt(user_id=basic_user.id, declined=False, remind_at=datetime.utcnow() + timedelta(days=2)))
    db.session.commit()
    assert review_reminders.send_due_reminders() == 0 and mail.calls == []


def test_failed_send_is_retried(db, basic_user, monkeypatch):
    mail = _Mail(ok=False)
    monkeypatch.setattr(review_reminders, 'mailer', mail)
    _due(db, basic_user)
    assert review_reminders.send_due_reminders() == 0
    assert ReviewPrompt.query.filter_by(user_id=basic_user.id).one().reminder_sent_at is None
    mail.ok = True
    assert review_reminders.send_due_reminders() == 1


def test_no_email_if_user_already_reviewed(db, basic_user, monkeypatch):
    mail = _Mail()
    monkeypatch.setattr(review_reminders, 'mailer', mail)
    db.session.add(Review(user_id=basic_user.id, stars=5, text='x', visibility='anonymous', status='pending'))
    _due(db, basic_user)
    assert review_reminders.send_due_reminders() == 0 and mail.calls == []


def test_reminder_email_has_two_choices_in_english():
    from app.services import email as mailer
    sent = {}
    orig = mailer._brevo_send
    mailer._brevo_send = lambda to, subject, text, html=None: sent.update(to=to, subject=subject, text=text, html=html) or True
    try:
        assert mailer.send_review_reminder_email('a@b.c', 'https://x/decline', 'https://x/dashboard')
    finally:
        mailer._brevo_send = orig
    html = sent['html']
    assert 'NO THANKS' in html and 'SUBMIT REVIEW' in html
    assert html.count('<a href=') == 2  # точно два избора
    assert 'https://x/decline' in html and 'https://x/dashboard' in html and 'MARADTEST.COM' in html
    assert 'Your opinion matters to us' in html


# ---------- страница "No thanks" ----------

def test_decline_page_get_only_confirms(client, db, basic_user):
    token = _token(basic_user)
    html = client.get(f'/review/decline/{token}').get_data(as_text=True)
    assert 'No more review requests?' in html and 'Yes, no thanks' in html
    assert ReviewPrompt.query.filter_by(user_id=basic_user.id).first() is None  # GET не записва


def test_decline_page_post_declines(client, db, basic_user):
    token = _token(basic_user)
    html = client.post(f'/review/decline/{token}').get_data(as_text=True)
    assert 'We will not ask you for a review again' in html
    assert ReviewPrompt.query.filter_by(user_id=basic_user.id).one().declined is True


def test_decline_page_invalid_token(client, db):
    res = client.get('/review/decline/not-a-token')
    assert res.status_code == 400 and 'invalid or has expired' in res.get_data(as_text=True)


def _token(user):
    from flask import current_app
    with current_app.test_request_context():
        return review_reminders.make_decline_token(user.id)


def test_open_link_logged_out_goes_to_login_then_dashboard(client, db, basic_user):
    res = client.get('/review/open')
    assert res.status_code == 302 and res.headers['Location'].endswith('/?login=1')
    res = client.post('/login', data={'email': basic_user.email, 'password': 'Test123'},
                      headers={'X-Requested-With': 'XMLHttpRequest'})
    assert res.get_json()['redirect'].endswith('/dashboard')


def test_open_link_logged_in_goes_to_dashboard(client, db, basic_user):
    client.post('/login', data={'email': basic_user.email, 'password': 'Test123'},
                headers={'X-Requested-With': 'XMLHttpRequest'})
    res = client.get('/review/open')
    assert res.status_code == 302 and res.headers['Location'].endswith('/dashboard')


def test_decline_page_confirm_loads_autosubmit_and_done_text(client, db, basic_user):
    from app.services.review_reminders import make_decline_token
    url = f'/review/decline/{make_decline_token(basic_user.id)}'
    assert b'review-decline.js' in client.get(url).data
    assert b'Request accepted' in client.post(url).data
