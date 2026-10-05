from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
POSTS_CSV = DATA_DIR / "posts.csv"
PRICES_CSV = DATA_DIR / "prices.csv"
META_JSON = DATA_DIR / "meta.json"

COINS = {
    "BTC": {
        "name": "Bitcoin",
        "ticker": "BTC-USD",
        "keywords": ["bitcoin", "btc"],
        "subreddits": ["Bitcoin"],
    },
    "ETH": {
        "name": "Ethereum",
        "ticker": "ETH-USD",
        "keywords": ["ethereum", "eth", "ether"],
        "subreddits": ["ethereum"],
    },
    "SOL": {
        "name": "Solana",
        "ticker": "SOL-USD",
        "keywords": ["solana", "sol"],
        "subreddits": ["solana"],
    },
}

# General feeds: each item is tagged with whichever coins its text mentions.
NEWS_FEEDS = {
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Cointelegraph": "https://cointelegraph.com/rss",
    "Decrypt": "https://decrypt.co/feed",
}
GENERAL_SUBREDDITS = ["CryptoCurrency"]

GOOGLE_NEWS_URL = "https://news.google.com/rss/search?q={query}+when:7d&hl=en-US&gl=US&ceid=US:en"

USER_AGENT = "crypto-sentiment-dashboard/1.0 (portfolio project; github.com/Z3US-23)"
REQUEST_TIMEOUT = 20
PRICE_HISTORY_DAYS = 180
