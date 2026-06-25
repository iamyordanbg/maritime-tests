FEEDS = {
    'maritime': {
        'label': '🚢 Maritime',
        'lang': 'en',
        'urls': [
            'https://gcaptain.com/feed/',
            'https://www.maritime-executive.com/rss',
            'https://splash247.com/feed/',
        ]
    },
    'finance': {
        'label': '💰 Finance',
        'lang': 'en',
        'urls': [
            'https://feeds.reuters.com/reuters/businessNews',
            'https://www.cnbc.com/id/10001147/device/rss/rss.html',
            'https://www.investing.com/rss/news.rss',
        ]
    },
    'sport': {
        'label': '⚽ Sport',
        'lang': 'en',
        'urls': [
            'https://feeds.bbci.co.uk/sport/rss.xml',
            'https://www.espn.com/espn/rss/news',
            'https://www.skysports.com/rss/12040',
        ]
    },
    'world': {
        'label': '🌍 World',
        'lang': 'en',
        'urls': [
            'https://feeds.bbci.co.uk/news/world/rss.xml',
            'https://feeds.reuters.com/reuters/worldNews',
            'https://rss.dw.com/rdf/rss-en-world',
        ]
    },
    'gaming': {
        'label': '🎮 Gaming',
        'lang': 'en',
        'urls': [
            'https://www.ign.com/articles.rss',
            'https://kotaku.com/rss',
            'https://www.eurogamer.net/?format=rss',
        ]
    },
    'music': {
        'label': '🎵 Music',
        'lang': 'en',
        'urls': [
            'https://www.rollingstone.com/music/feed/',
            'https://pitchfork.com/rss/news/',
            'https://www.nme.com/news/music/feed',
        ]
    },
    'crypto': {
        'label': '💎 Crypto',
        'lang': 'en',
        'urls': [
            'https://cointelegraph.com/rss',
            'https://coindesk.com/arc/outboundfeeds/rss/',
            'https://cryptonews.com/news/feed/',
        ]
    },
    'politics': {
        'label': '🗳️ Politics',
        'lang': 'en',
        'urls': [
            'https://feeds.bbci.co.uk/news/politics/rss.xml',
            'https://feeds.reuters.com/Reuters/PoliticsNews',
            'https://rss.politico.com/politics-news.xml',
        ]
    },
    'travel': {
        'label': '✈️ Travel',
        'lang': 'en',
        'urls': [
            'https://www.lonelyplanet.com/news/feed',
            'https://www.travelandleisure.com/rss',
            'https://www.nomadicmatt.com/feed/',
        ]
    },
    'bg_news': {
        'label': '🇧🇬 Bulgaria',
        'lang': 'bg',
        'urls': [
            'https://www.novinite.com/rss.php',
            'https://feeds.feedburner.com/novinibg',
            'https://www.actualno.com/rss.xml',
        ]
    },
}

CATEGORY_ORDER = [
    'maritime', 'world', 'finance', 'crypto',
    'sport', 'politics', 'travel', 'gaming', 'music', 'bg_news'
]
