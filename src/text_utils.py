import calendar
import hashlib
import re
from datetime import datetime, timezone
from html import unescape

from src.config import COINS

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_COIN_PATTERNS = {
    symbol: re.compile(r"\b(" + "|".join(re.escape(k) for k in coin["keywords"]) + r")\b", re.IGNORECASE)
    for symbol, coin in COINS.items()
}


def clean_html(text: str | None) -> str:
    return _SPACE_RE.sub(" ", unescape(_TAG_RE.sub(" ", text or ""))).strip()


def match_coins(text: str) -> list[str]:
    return [symbol for symbol, pattern in _COIN_PATTERNS.items() if pattern.search(text)]


def title_id(title: str) -> str:
    """Stable id from the headline, so the same story from two feeds is stored once."""
    normalized = _SPACE_RE.sub(" ", title.lower()).strip()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def struct_time_to_iso(value) -> str | None:
    if not value:
        return None
    return datetime.fromtimestamp(calendar.timegm(value), tz=timezone.utc).isoformat()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
