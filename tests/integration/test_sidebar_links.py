"""tests/integration/test_sidebar_links.py - the user sidebar must not contain dead/duplicate links."""
import re

AJAX = {'X-Requested-With': 'XMLHttpRequest'}


def _sidebar_links(html):
    nav = re.search(r'<nav class="sidebar-nav">(.*?)</nav>', html, re.S).group(1)
    return re.findall(r'<a href="([^"]*)"[^>]*?title="([^"]*)"', nav, re.S)


def test_sidebar_has_no_tests_link_and_no_duplicate_destinations(client, db, basic_user):
    client.post('/login', data={'email': basic_user.email, 'password': 'Test123'}, headers=AJAX)
    html = client.get('/dashboard').get_data(as_text=True)
    links = _sidebar_links(html)
    titles = [t for _, t in links]
    assert 'Tests' not in titles
    assert titles[:3] == ['Home', 'All Mistakes', 'History']
    hrefs = [h for h, _ in links]
    assert len(hrefs) == len(set(hrefs)), f'two sidebar buttons lead to the same page: {links}'
