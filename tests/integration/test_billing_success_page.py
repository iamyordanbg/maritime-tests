"""
tests/integration/test_billing_success_page.py
==============================================
Страницата след плащане (/billing/success) е на английски (Basic/Plus и Gold).
"""

import re

CYR = re.compile(r'[Ѐ-ӿ]')
BG_LABELS = ['Достъп', 'Тестове', 'Теми', 'Всички грешки', 'Валидност', 'Реклами', 'Избери тест',
             'Провери имейла', 'Изпратихме', 'Към Dashboard']


def _login(client, email):
    client.post('/login', data={'email': email, 'password': 'Test123'},
                headers={'X-Requested-With': 'XMLHttpRequest'})


def _main_block(html):
    """Само картата на страницата - base.html има собствени (правни) текстове."""
    start = html.index('Payment successful</h2>')
    end = html.find('id="loginModal"', start)
    block = html[start:end if end != -1 else start + 6000]
    return re.sub(r'<!--.*?-->', '', block, flags=re.S)  # коментарите не се виждат


def test_basic_success_page_is_english(client, basic_user):
    _login(client, 'basic@test.bg')
    html = client.get('/billing/success?plan=basic').get_data(as_text=True)
    block = _main_block(html)
    for label in ('Access', 'Tests', 'Topics', 'Mistakes', 'All mistakes', 'Validity', 'Ads', 'Subscription',
                  'Choose a test'):
        assert label in block, label
    assert not CYR.search(block)
    assert 'MARADTEST.COM' in html


def test_gold_success_page_is_english(client, gold_user):
    _login(client, 'gold@test.bg')
    html = client.get('/billing/success?plan=gold').get_data(as_text=True)
    block = _main_block(html)
    assert 'Check your email' in block and 'Go to Dashboard' in block
    assert not CYR.search(block)


def test_no_bulgarian_labels_left(client, basic_user):
    _login(client, 'basic@test.bg')
    block = _main_block(client.get('/billing/success?plan=basic').get_data(as_text=True))
    for bg in BG_LABELS:
        assert bg not in block, bg
