"""
tests/integration/test_mobile_header_size.py
============================================
Телефонен хедър: височината остава (64px), аватарът е по-малък (40px; бутонът около него си остава 56px за пръста),
името на сайта е 16px. Браузърният тест (320-430px, library / dashboard / history) е пуснат ръчно с Playwright.
"""
import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[2] / 'app' / 'static' / 'css' / 'mobile-header.css').read_text(encoding='utf-8')


def _rule(selector):
    m = re.search(r'^\s*' + re.escape(selector) + r'\s*\{([^}]*)\}', CSS, re.M)
    assert m, selector
    return m.group(1)


def test_header_keeps_its_height():
    assert 'height: 64px; min-height: 64px' in _rule('.mhdr')


def test_avatar_is_smaller_but_the_tap_target_is_not():
    assert 'width: 40px; height: 40px' in _rule('.mhdr-avatar')
    user = _rule('.mhdr-user')
    assert 'width: 56px; height: 56px' in user


def test_site_name_is_16px():
    assert 'font-size: 16px' in _rule('.mhdr-brand')
