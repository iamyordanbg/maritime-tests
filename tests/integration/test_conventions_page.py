"""tests/integration/test_conventions_page.py - Conventions е 'Under construction'."""
AJAX = {'X-Requested-With': 'XMLHttpRequest'}


def test_conventions_shows_under_construction(client, db, basic_user):
    client.post('/login', data={'email': basic_user.email, 'password': 'Test123'}, headers=AJAX)
    resp = client.get('/conventions')
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200 and 'Under construction' in html
    assert 'href="/conventions"' in html   # линкът в страничното меню води към страницата


def test_conventions_requires_login(client):
    assert client.get('/conventions').status_code == 302
