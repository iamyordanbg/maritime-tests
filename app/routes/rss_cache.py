import feedparser, threading, re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from .rss_feeds import FEEDS

_cache = {}
_last_update = {}
UPDATE_HOURS = {8, 13, 20}
MAX_FEEDS_PER_CAT = 3
MAX_ITEMS_PER_FEED = 5

def _time_ago(dt):
    if not dt: return ''
    diff = (datetime.utcnow() - dt).total_seconds()
    if diff < 3600: return f'{int(diff//60)}m ago'
    if diff < 86400: return f'{int(diff//3600)}h ago'
    if diff < 604800: return f'{int(diff//86400)}d ago'
    return dt.strftime('%d.%m.%Y')

def _fetch_one(url, category):
    try:
        d = feedparser.parse(url, request_headers={'User-Agent': 'Mozilla/5.0'})
        items = []
        for e in d.entries[:MAX_ITEMS_PER_FEED]:
            pub = None
            if hasattr(e, 'published_parsed') and e.published_parsed:
                try: pub = datetime(*e.published_parsed[:6])
                except: pass
            title = e.get('title', '').strip()[:200]
            if not title: continue
            summary = re.sub('<[^>]+>', '', e.get('summary', '')).strip()[:300]
            items.append({
                'title': title,
                'summary': summary,
                'link': e.get('link', ''),
                'source': d.feed.get('title', '')[:60],
                'category': category,
                'cat_label': FEEDS.get(category, {}).get('label', ''),
                'lang': FEEDS.get(category, {}).get('lang', 'en'),
                'published': pub,
                'time_ago': _time_ago(pub),
                'type': 'rss'
            })
        return items
    except: return []

def _should_update(cat):
    if cat not in _last_update: return True
    last = _last_update[cat]
    now = datetime.utcnow()
    for h in UPDATE_HOURS:
        t = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if last < t <= now: return True
    return False

def _refresh(categories):
    tasks = [(url, cat) for cat in categories
             for url in FEEDS.get(cat, {}).get('urls', [])[:MAX_FEEDS_PER_CAT]]
    cat_items = {cat: [] for cat in categories}
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(_fetch_one, url, cat): cat for url, cat in tasks}
        for future in as_completed(futures, timeout=20):
            try:
                items = future.result(timeout=8)
                if items: cat_items[items[0]['category']].extend(items)
            except: pass
    for cat in categories:
        _cache[cat] = cat_items[cat]
        _last_update[cat] = datetime.utcnow()

def get_cached(categories, language='both'):
    cats_to_refresh = [c for c in categories if _should_update(c)]
    if cats_to_refresh: _refresh(cats_to_refresh)
    result = []
    for cat in categories:
        for item in _cache.get(cat, []):
            if language == 'both': result.append(item)
            elif language == 'bg' and item.get('lang') == 'bg': result.append(item)
            elif language == 'en' and item.get('lang') == 'en': result.append(item)
    result.sort(key=lambda x: x['published'] or datetime(2000,1,1), reverse=True)
    # refresh time_ago
    for i in result:
        if i.get('published'): i['time_ago'] = _time_ago(i['published'])
    return result
