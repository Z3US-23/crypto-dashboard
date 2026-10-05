"""VADER sentiment scoring, tuned with crypto-market slang."""

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# VADER is trained on general social media; these terms carry strong market meaning
# in crypto that the default lexicon misses or underweights. Scale: -4 to +4.
CRYPTO_LEXICON = {
    "bullish": 2.5, "bearish": -2.5,
    "moon": 2.0, "mooning": 2.5,
    "pump": 1.5, "pumping": 1.5,
    "dump": -2.0, "dumping": -2.0, "dumped": -2.0,
    "rekt": -3.0, "hodl": 1.5, "fud": -2.0,
    "rally": 2.0, "rallies": 2.0, "rallied": 2.0,
    "surge": 2.0, "surges": 2.0, "surged": 2.0,
    "soar": 2.5, "soars": 2.5, "soared": 2.5,
    "plunge": -2.5, "plunges": -2.5, "plunged": -2.5,
    "crash": -3.0, "crashes": -3.0, "crashed": -3.0,
    "slump": -2.0, "slumps": -2.0, "tumbles": -2.0,
    "selloff": -2.0, "sell-off": -2.0,
    "liquidated": -2.0, "liquidations": -1.5,
    "hack": -2.5, "hacked": -3.0, "exploit": -2.5, "exploited": -2.5,
    "scam": -3.0, "rug": -2.5, "rugpull": -3.0,
    "ath": 2.0, "breakout": 1.5,
    "inflows": 1.0, "outflows": -1.0,
}

_analyzer = SentimentIntensityAnalyzer()
_analyzer.lexicon.update(CRYPTO_LEXICON)

POSITIVE_THRESHOLD = 0.05
NEGATIVE_THRESHOLD = -0.05


def score(text: str) -> float:
    """Compound sentiment from -1 (most negative) to +1 (most positive)."""
    return _analyzer.polarity_scores(text)["compound"]


def label(compound: float) -> str:
    if compound >= POSITIVE_THRESHOLD:
        return "positive"
    if compound <= NEGATIVE_THRESHOLD:
        return "negative"
    return "neutral"
