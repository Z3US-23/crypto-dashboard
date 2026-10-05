"""Run one collection cycle: fetch posts and prices, score sentiment, merge into data/.

Usage:  python -m src.pipeline
"""

import json

import pandas as pd

from src.collect_news import collect_news
from src.collect_prices import collect_prices
from src.collect_reddit import collect_reddit
from src.config import DATA_DIR, META_JSON, POSTS_CSV, PRICES_CSV
from src.sentiment import label, score
from src.text_utils import utc_now_iso

POST_COLUMNS = [
    "id", "coin", "source_type", "source", "title", "url",
    "published_at", "collected_at", "sentiment", "label",
]


def update_posts(status: dict, collected_at: str) -> tuple[int, int]:
    new = pd.DataFrame(collect_news(status) + collect_reddit(status))
    existing = pd.read_csv(POSTS_CSV) if POSTS_CSV.exists() else pd.DataFrame(columns=POST_COLUMNS)

    if new.empty:
        return 0, len(existing)

    new["sentiment"] = new["text"].map(score).round(4)
    new["label"] = new["sentiment"].map(label)
    new["collected_at"] = collected_at
    new["published_at"] = new["published_at"].fillna(collected_at)
    new = new[POST_COLUMNS]

    # keep="first" so rows already on disk keep their original collected_at.
    combined = pd.concat([existing, new], ignore_index=True).drop_duplicates(subset=["id", "coin"], keep="first")
    combined = combined.sort_values("published_at", ascending=False)
    combined.to_csv(POSTS_CSV, index=False)
    return len(combined) - len(existing), len(combined)


def update_prices(status: dict) -> None:
    try:
        prices = collect_prices()
    except Exception as exc:
        status["Yahoo Finance"] = f"failed: {exc.__class__.__name__}"
        return
    if prices.empty:
        status["Yahoo Finance"] = "failed: empty response"
        return
    prices["close"] = prices["close"].round(4)
    prices.to_csv(PRICES_CSV, index=False)
    status["Yahoo Finance"] = f"ok ({len(prices)})"


def run() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    collected_at = utc_now_iso()
    status: dict[str, str] = {}

    added, total = update_posts(status, collected_at)
    update_prices(status)

    META_JSON.write_text(
        json.dumps({"last_run": collected_at, "new_rows": added, "total_rows": total, "sources": status}, indent=2)
    )

    print(f"Run at {collected_at}: {added} new rows, {total} total")
    for source, result in status.items():
        print(f"  {source:<22} {result}")


if __name__ == "__main__":
    run()
