"""Collect crypto headlines from news RSS feeds and Google News."""

from urllib.parse import quote_plus

import feedparser
import requests

from src.config import COINS, GOOGLE_NEWS_URL, NEWS_FEEDS, REQUEST_TIMEOUT, USER_AGENT
from src.text_utils import clean_html, match_coins, struct_time_to_iso, title_id


def _fetch_feed(url: str) -> list:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return feedparser.parse(response.content).entries


def _record(coin: str, source: str, title: str, url: str, published_at: str | None, text: str) -> dict:
    return {
        "id": title_id(title),
        "coin": coin,
        "source_type": "news",
        "source": source,
        "title": title,
        "url": url,
        "published_at": published_at,
        "text": text,
    }


def collect_feeds(status: dict) -> list[dict]:
    records = []
    for source, url in NEWS_FEEDS.items():
        try:
            entries = _fetch_feed(url)
        except Exception as exc:
            status[source] = f"failed: {exc.__class__.__name__}"
            continue
        count = 0
        for entry in entries:
            title = clean_html(entry.get("title"))
            summary = clean_html(entry.get("summary"))[:500]
            if not title:
                continue
            published = struct_time_to_iso(entry.get("published_parsed") or entry.get("updated_parsed"))
            for coin in match_coins(f"{title} {summary}"):
                records.append(_record(coin, source, title, entry.get("link", ""), published, f"{title}. {summary}"))
                count += 1
        status[source] = f"ok ({count})"
    return records


def collect_google_news(status: dict) -> list[dict]:
    records = []
    for symbol, coin in COINS.items():
        query = quote_plus(f'"{coin["name"]}" crypto')
        try:
            entries = _fetch_feed(GOOGLE_NEWS_URL.format(query=query))
        except Exception as exc:
            status[f"Google News {symbol}"] = f"failed: {exc.__class__.__name__}"
            continue
        for entry in entries:
            raw_title = clean_html(entry.get("title"))
            publisher = clean_html(entry.get("source", {}).get("title")) or "Google News"
            # Google News appends " - Publisher" to every headline.
            title = raw_title.removesuffix(f" - {publisher}").strip()
            if not title:
                continue
            published = struct_time_to_iso(entry.get("published_parsed"))
            records.append(_record(symbol, publisher, title, entry.get("link", ""), published, title))
        status[f"Google News {symbol}"] = f"ok ({len(entries)})"
    return records


def collect_news(status: dict) -> list[dict]:
    return collect_feeds(status) + collect_google_news(status)
