"""
tests/integration/test_reading_prefs.py
=======================================
Настройките за четене (тема, яркост, тегло на шрифта...) са в акаунта и важат еднакво за
Test / Mix / Mistakes / All Mistakes / Simulator / преглед на резултат.
"""
import pytest
from app.models.user import User

AJAX = {'X-Requested-With': 'XMLHttpRequest'}


@pytest.fixture
def env_test(db):
    import json
    from app.models.test import Test
    t = Test(title='RP', level='Operational Level', category='deck', is_demo=True,
             questions_json=json.dumps([{'id': 1, 'question': 'Q', 'options': [{'text': 'a', 'isCorrect': True}]}]))
    db.session.add(t)
    db.session.commit()
    yield t.id
    db.session.delete(t)
    db.session.commit()


@pytest.fixture
def logged(client, db, free_user):
    client.post('/login', data={'email': 'free@test.bg', 'password': 'Test123'}, headers=AJAX)
    yield free_user
    u = User.query.get(free_user.id)
    u.pref_theme, u.pref_bg_brightness, u.pref_font_weight = 'dark', 5, 5
    db.session.commit()


def _set(client, **kw):
    assert client.post('/api/test-preferences', json=kw).get_json()['success']


def test_defaults(client, logged):
    data = client.get('/api/test-preferences').get_json()
    assert data['theme'] == 'dark' and data['bg_brightness'] == 5 and data['font_weight'] == 5


def test_brightness_weight_and_theme_persist(client, logged):
    _set(client, theme='sepia', bg_brightness=8, font_weight=2)
    data = client.get('/api/test-preferences').get_json()
    assert (data['theme'], data['bg_brightness'], data['font_weight']) == ('sepia', 8, 2)


def test_invalid_values_ignored(client, logged):
    _set(client, bg_brightness=8, theme='light')
    _set(client, bg_brightness=99, font_weight='x', theme='neon')
    data = client.get('/api/test-preferences').get_json()
    assert (data['theme'], data['bg_brightness'], data['font_weight']) == ('light', 8, 5)


def test_reset_restores_all(client, logged):
    _set(client, theme='ink', bg_brightness=1, font_weight=9)
    client.post('/api/test-preferences', json={'reset': True})
    data = client.get('/api/test-preferences').get_json()
    assert (data['theme'], data['bg_brightness'], data['font_weight']) == ('dark', 5, 5)


def test_theme_is_rendered_server_side_on_every_mode(client, db, logged, env_test):
    _set(client, theme='light')
    for path in (f'/test/{env_test}', f'/test/{env_test}/simulator'):
        html = client.get(path).get_data(as_text=True)
        assert 'data-theme="light"' in html, path
