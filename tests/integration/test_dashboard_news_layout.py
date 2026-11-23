"""
tests/integration/test_dashboard_news_layout.py
===============================================
Регресия: на телефон новинарският блок на dashboard трябва да е с ФИКСИРАНО поле за снимката,
което заема цялата свободна височина - така лентата с гледания/коментари/харесвания е винаги на
едно и също място над картите Tests Completed / Passed / Success Rate, независимо от пропорциите
на снимката (преди това широка снимка оставяше до 300px празно място под лентата).
Пълният браузърен тест (320/360/390/393/412/430px, снимки квадратна/широка/висока/без снимка)
е пуснат ръчно с Playwright.
"""
import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[2] / 'app' / 'static' / 'css' / 'dashboard-mobile.css').read_text(encoding='utf-8')


def _rule(selector_start):
    m = re.search(r'^\s*' + re.escape(selector_start) + r'\s*\{([^}]*)\}', CSS, re.M)
    assert m, f'rule {selector_start!r} not found'
    return m.group(1)


def test_news_block_fills_free_height_and_stats_follow_directly():
    news = _rule('#newsWidget:has(.dash-news-item)')
    assert 'flex: 1 1 auto' in news and 'min-height:' in news
    assert 'margin-top: auto' not in _rule('#newsWidget + .dash-stats')


def test_picture_is_laid_over_a_fixed_field_and_never_cropped():
    img = _rule('.dash-news-item-img')
    assert 'position: absolute' in img and 'inset: 0' in img
    assert 'grid-area: 2 / 1 / 3 / 2' in img           # изрични краища - иначе полето се разтяга и върху лентата
    assert 'object-fit: contain' in img
    assert 'max-height' not in img


def test_no_magic_screen_height_reserve_left():
    assert 'nimg-reserve' not in CSS


def test_phone_news_title_is_two_lines_with_the_padding_on_the_head_row():
    """Заглавието е най-много 2 реда с многоточие; padding е на реда с аватара, не на clamp-натия <p> (иначе излиза края на 3-ия ред)."""
    title = _rule('.dash-news-item-title')
    assert '-webkit-line-clamp: 2' in title and 'overflow: hidden' in title and 'padding' not in title
    head = _rule('.dash-news-item-head')
    assert 'grid-area: 1 / 1' in head and 'padding' in head


def test_phone_opened_post_is_full_screen_with_a_square_edge_to_edge_picture():
    """Отворена новина на телефон: снимка от ръб до ръб, без заоблени ъгли и без рамка; търсачката е скрита, докато се чете."""
    feed = (Path(__file__).resolve().parents[2] / 'app' / 'static' / 'css' / 'news-feed.css').read_text(encoding='utf-8')
    phone = feed[feed.index('@media (max-width: 767px)'):]
    assert re.search(r'#newsPostImage \{ order: 3; padding: 0 0 12px; \}', phone)
    assert re.search(r'#newsPostImage img \{[^}]*border-radius: 0 !important', phone)
    assert 'border-radius: 10px !important' not in feed
    assert '.nc-search-wrap { display: none; }' in phone and '#newsDetailView[style*="block"]' in phone
