"""
RSS Cache — обновява се 3 пъти на ден: 08:00, 13:00, 20:00
"""
import feedparser
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from .rss_feeds import FEEDS

_cache = {}        # {'cat': [items...]}
_last_update = {}  # {'cat': datetime}

UPDATE_HOURS = {8, 13, 20}  # часовете на обновяване
MAX_FEEDS_PER_CAT = 3       # max RSS URLs на категория
MAX_ITEMS_PER_FEED = 5      # max статии на RSS
TIMEOUT = 5                 # секунди timeout

def _fetch_one(url, category):
    try:
        d = feedparser.parse(url, request_headers={
            'User-Agent': 'Mozilla/5.0',
        })
        items = []
        for e in d.entries[:MAX_ITEMS_PER_FEED]:
            pub = None
            if hasattr(e, 'published_parsed') and e.published_parsed:
                try: pub = datetime(*e.published_parsed[:6])
                except: pass
            title = e.get('title', '').strip()[:200]
            if not title: continue
            summary = ''
            if hasattr(e, 'summary'):
                import re
                summary = re.sub('<[^>]+>', '', e.summary).strip()[:300]
            items.append({
                'title': title,
                'summary': summary,
                'link': e.get('link', ''),
                'source': d.feed.get('title', '')[:60],
                'category': category,
                'cat_label': FEEDS.get(category, {}).get('label', ''),
                'published': pub,
                'time_ago': _time_ago(pub),
                'type': 'rss'
            })
        return items
    except Exception:
        return []

def _time_ago(dt):
    if not dt: return ''
    diff = (datetime.utcnow() - dt).total_seconds()
    if diff < 3600: return f'Преди {int(diff//60)} мин'
    if diff < 86400: return f'Преди {int(diff//3600)} ч'
    if diff < 604800: return f'Преди {int(diff//86400)} дни'
    return dt.strftime('%d.%m.%Y')

def _should_update(cat):
    if cat not in _last_update:
        return True
    last = _last_update[cat]
    now = datetime.utcnow()
    # Проверяваме дали сме минали някой от часовете за обновяване след последното
    for h in UPDATE_HOURS:
        update_time = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if last < update_time <= now:
            return True
    return False

def get_cached(categories):
    """Връща кешираните новини за избраните категории"""
    result = []
    cats_to_refresh = [c for c in categories if _should_update(c)]

    if cats_to_refresh:
        _refresh(cats_to_refresh)

    for cat in categories:
        result.extend(_cache.get(cat, []))

    result.sort(key=lambda x: x['published'] or datetime(2000,1,1), reverse=True)
    return result

def _refresh(categories):
    """Обновява кеша паралелно за дадените категории"""
    tasks = []
    for cat in categories:
        urls = FEEDS.get(cat, {}).get('urls', [])[:MAX_FEEDS_PER_CAT]
        for url in urls:
            tasks.append((url, cat))

    cat_items = {cat: [] for cat in categories}

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(_fetch_one, url, cat): (url, cat) for url, cat in tasks}
        for future in as_completed(futures, timeout=TIMEOUT*2):
            try:
                items = future.result(timeout=TIMEOUT)
                if items:
                    cat_items[items[0]['category']].extend(items)
            except Exception:
                pass

    for cat in categories:
        _cache[cat] = cat_items[cat]
        _last_update[cat] = datetime.utcnow()
