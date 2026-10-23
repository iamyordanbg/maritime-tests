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


def test_gold_numbers_come_from_plan_config(client, gold_user, monkeypatch):
    from app.services.plans import PLANS
    monkeypatch.setitem(PLANS['gold'], 'promo_codes', 7)
    monkeypatch.setitem(PLANS['gold'], 'valid_days_per_code', 14)
    monkeypatch.setitem(PLANS['gold'], 'code_validity_months', 9)
    _login(client, 'gold@test.bg')
    block = _main_block(client.get('/billing/success?plan=gold').get_data(as_text=True))
    assert '7 promo codes' in block and '14 days of access' in block and '9 months' in block
    assert 'Track my 7 codes' in block
    assert '10 promo codes' not in block and '12 months' not in block


def test_gold_without_code_validity_omits_months(client, gold_user, monkeypatch):
    from app.services.plans import PLANS
    monkeypatch.setitem(PLANS['gold'], 'valid_days_per_code', 1)
    monkeypatch.setitem(PLANS['gold'], 'code_validity_months', None)
    _login(client, 'gold@test.bg')
    block = _main_block(client.get('/billing/success?plan=gold').get_data(as_text=True))
    assert '1 day of access' in block and 'months' not in block


def test_no_bulgarian_labels_left(client, basic_user):
    _login(client, 'basic@test.bg')
    block = _main_block(client.get('/billing/success?plan=basic').get_data(as_text=True))
    for bg in BG_LABELS:
        assert bg not in block, bg
