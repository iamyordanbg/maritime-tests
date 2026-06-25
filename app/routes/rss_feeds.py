# RSS Feed конфигурация по категории
FEEDS = {
    'maritime': {
        'label': '🚢 Морски',
        'lang': 'en',
        'urls': [
            'https://gcaptain.com/feed/',
            'https://www.maritime-executive.com/rss',
            'https://splash247.com/feed/',
            'https://www.seatrade-maritime.com/rss.xml',
            'https://www.lloydslist.com/rss',
        ]
    },
    'finance': {
        'label': '💰 Финанси',
        'lang': 'en',
        'urls': [
            'https://feeds.reuters.com/reuters/businessNews',
            'https://www.ft.com/?format=rss',
            'https://feeds.bloomberg.com/markets/news.rss',
            'https://www.investing.com/rss/news.rss',
            'https://www.cnbc.com/id/10001147/device/rss/rss.html',
        ]
    },
    'sport': {
        'label': '⚽ Спорт',
        'lang': 'en',
        'urls': [
            'https://feeds.bbci.co.uk/sport/rss.xml',
            'https://www.espn.com/espn/rss/news',
            'https://www.skysports.com/rss/12040',
            'https://www.goal.com/feeds/en/news',
            'https://sportstar.thehindu.com/feeder/default.rss',
        ]
    },
    'world': {
        'label': '🌍 Световни',
        'lang': 'en',
        'urls': [
            'https://feeds.bbci.co.uk/news/world/rss.xml',
            'https://feeds.reuters.com/reuters/worldNews',
            'https://rss.dw.com/rdf/rss-en-world',
            'https://www.aljazeera.com/xml/rss/all.xml',
            'https://feeds.skynews.com/feeds/rss/world.xml',
        ]
    },
    'gaming': {
        'label': '🎮 Gaming',
        'lang': 'en',
        'urls': [
            'https://www.reddit.com/r/gaming/.rss',
            'https://www.ign.com/articles.rss',
            'https://kotaku.com/rss',
            'https://www.gamespot.com/feeds/mashup/',
            'https://www.eurogamer.net/?format=rss',
        ]
    },
    'music': {
        'label': '🎵 Музика',
        'lang': 'en',
        'urls': [
            'https://www.rollingstone.com/music/feed/',
            'https://pitchfork.com/rss/news/',
            'https://www.nme.com/news/music/feed',
            'https://consequence.net/feed/',
            'https://www.stereogum.com/feed/',
        ]
    },
    'crypto': {
        'label': '💎 Крипто',
        'lang': 'en',
        'urls': [
            'https://cointelegraph.com/rss',
            'https://coindesk.com/arc/outboundfeeds/rss/',
            'https://cryptonews.com/news/feed/',
            'https://bitcoinmagazine.com/.rss/full/',
            'https://www.newsbtc.com/feed/',
        ]
    },
    'politics': {
        'label': '🗳️ Политика',
        'lang': 'en',
        'urls': [
            'https://feeds.bbci.co.uk/news/politics/rss.xml',
            'https://feeds.reuters.com/Reuters/PoliticsNews',
            'https://rss.politico.com/politics-news.xml',
            'https://thehill.com/feed/',
            'https://www.politico.eu/feed/',
        ]
    },
    'travel': {
        'label': '✈️ Почивки',
        'lang': 'en',
        'urls': [
            'https://www.lonelyplanet.com/news/feed',
            'https://www.travelandleisure.com/rss',
            'https://www.cntraveler.com/feed/rss',
            'https://www.nomadicmatt.com/feed/',
            'https://www.roughguides.com/feed/',
        ]
    },
    'bg_news': {
        'label': '🇧🇬 България',
        'lang': 'bg',
        'urls': [
            'https://www.dnes.bg/rss.php',
            'https://bnr.bg/sites/all/modules/bnr_rss/rss.php?cat=5',
            'https://www.novinite.com/rss.php',
            'https://www.investor.bg/rss/',
            'https://treegment.com/feed',
        ]
    },
}

CATEGORY_ORDER = [
    'maritime', 'world', 'finance', 'crypto',
    'sport', 'politics', 'travel', 'gaming', 'music', 'bg_news'
]
