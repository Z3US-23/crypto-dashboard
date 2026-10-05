"""Daily closing prices from Yahoo Finance."""

import pandas as pd
import yfinance as yf

from src.config import COINS, PRICE_HISTORY_DAYS


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
        return pd.DataFrame(columns=["date", "coin", "close"])

    close = raw["Close"].rename(columns=ticker_to_symbol)
    close.index = pd.to_datetime(close.index).date
    prices = close.rename_axis("date").reset_index().melt(id_vars="date", var_name="coin", value_name="close")
    return prices.dropna().sort_values(["coin", "date"]).reset_index(drop=True)
