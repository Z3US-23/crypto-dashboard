"""Collect recent Reddit posts via Reddit's public RSS feeds (no API key needed)."""

import re
import time

import feedparser
import requests

from src.config import COINS, GENERAL_SUBREDDITS, REQUEST_TIMEOUT, USER_AGENT
from src.text_utils import clean_html, match_coins, struct_time_to_iso

FEED_URL = "https://www.reddit.com/r/{sub}/new/.rss?limit=100"
MAX_RETRIES = 2
MAX_WAIT_SECONDS = 90
# Reddit appends "submitted by /u/name [link] [comments]" to every post body.
_FOOTER_RE = re.compile(r"\s*submitted by\s+/u/.*$", re.IGNORECASE | re.DOTALL)


def _fetch_entries(subreddit: str) -> list:
    # Anonymous RSS is limited to roughly one request per minute; on HTTP 429 Reddit
    # says how many seconds until the window resets, so wait that long and retry.
    for attempt in range(MAX_RETRIES + 1):
        response = requests.get(
            FEED_URL.format(sub=subreddit), headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
        )
        if response.status_code != 429 or attempt == MAX_RETRIES:
            break
        wait = float(response.headers.get("x-ratelimit-reset") or response.headers.get("retry-after") or 60)
        time.sleep(min(wait + 1, MAX_WAIT_SECONDS))
    response.raise_for_status()
    return feedparser.parse(response.content).entries


def _record(coin: str, subreddit: str, entry, title: str, body: str) -> dict:
    post_id = entry.get("id", "").removeprefix("t3_") or entry.get("link", "")
    return {
        "id": f"reddit_{post_id}",
        "coin": coin,
        "source_type": "reddit",
        "source": f"r/{subreddit}",
        "title": title,
        "url": entry.get("link", ""),
        "published_at": struct_time_to_iso(entry.get("published_parsed") or entry.get("updated_parsed")),
        "text": f"{title}. {body}",
    }


def collect_reddit(status: dict) -> list[dict]:
    # Coin subreddits: every post counts for that coin. General subreddits: tag by keyword.
    targets = [(sub, symbol) for symbol, coin in COINS.items() for sub in coin["subreddits"]]
    targets += [(sub, None) for sub in GENERAL_SUBREDDITS]

    records = []
    for subreddit, symbol in targets:
        try:
            entries = _fetch_entries(subreddit)
        except Exception as exc:
            status[f"r/{subreddit}"] = f"failed: {exc.__class__.__name__}"
            continue
        count = 0
        for entry in entries:
            title = clean_html(entry.get("title"))
            if not title:
                continue
            content = entry.get("content") or [{}]
            body = _FOOTER_RE.sub("", clean_html(content[0].get("value")))[:500]
            coins = [symbol] if symbol else match_coins(f"{title} {body}")
            for coin in coins:
                records.append(_record(coin, subreddit, entry, title, body))
                count += 1
        status[f"r/{subreddit}"] = f"ok ({count})"
    return records
