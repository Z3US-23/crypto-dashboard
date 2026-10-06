"""Daily OHLC prices (open, high, low, close) from Yahoo Finance."""

import pandas as pd
import yfinance as yf

from src.config import COINS, PRICE_HISTORY_DAYS

FIELDS = {"Open": "open", "High": "high", "Low": "low", "Close": "close"}


def collect_prices() -> pd.DataFrame:
    ticker_to_symbol = {coin["ticker"]: symbol for symbol, coin in COINS.items()}
    raw = yf.download(
        list(ticker_to_symbol),
        period=f"{PRICE_HISTORY_DAYS}d",
        interval="1d",
        auto_adjust=False,
        progress=False,
    )
    if raw.empty:
        return pd.DataFrame(columns=["date", "coin", *FIELDS.values()])

    frames = []
    for field, column in FIELDS.items():
        wide = raw[field].rename(columns=ticker_to_symbol)
        wide.index = pd.to_datetime(wide.index).date
        frames.append(wide.rename_axis("date").reset_index().melt(id_vars="date", var_name="coin", value_name=column))
    prices = frames[0]
    for frame in frames[1:]:
        prices = prices.merge(frame, on=["date", "coin"])

    # Today's candle is still forming, and Yahoo sometimes reports a high below the latest close.
    prices["high"] = prices[["high", "open", "close"]].max(axis=1)
    prices["low"] = prices[["low", "open", "close"]].min(axis=1)
    return prices.dropna().sort_values(["coin", "date"]).reset_index(drop=True)
