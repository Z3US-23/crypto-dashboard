"""Streamlit dashboard: crypto news & Reddit sentiment vs. price.

Run locally:  streamlit run app.py
"""

import json
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.config import COINS, META_JSON, POSTS_CSV, PRICES_CSV
from src.sentiment import NEGATIVE_THRESHOLD, POSITIVE_THRESHOLD

st.set_page_config(page_title="Crypto Sentiment Dashboard", page_icon="📈", layout="wide")

LABELS = ["positive", "neutral", "negative"]
SOURCE_TYPES = {"News": "news", "Reddit": "reddit"}
PERIODS = {"7 days": 7, "30 days": 30, "90 days": 90}
MIN_DAYS_FOR_CORRELATION = 10
# A daily average from one or two headlines is noise, not signal.
MIN_ITEMS_PER_DAY = 5
LOW_SAMPLE_OPACITY = 0.3
MIN_ITEMS_FOR_COMPARISON = 20

# Fixed colours: each coin keeps its colour everywhere; sentiment is blue (+) / grey / red (-).
PALETTES = {
    "light": {
        "coins": {"BTC": "#2a78d6", "ETH": "#eb6834", "SOL": "#1baf7a"},
        "labels": {"positive": "#2a78d6", "neutral": "#898781", "negative": "#e34948"},
    },
    "dark": {
        "coins": {"BTC": "#3987e5", "ETH": "#d95926", "SOL": "#199e70"},
        "labels": {"positive": "#3987e5", "neutral": "#898781", "negative": "#e66767"},
    },
}
theme_type = getattr(getattr(st.context, "theme", None), "type", None) or "light"
IS_DARK = theme_type == "dark"
PALETTE = PALETTES["dark" if IS_DARK else "light"]
SURFACE = "#0e1117" if IS_DARK else "#ffffff"


@st.cache_data(ttl=600)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    posts = pd.read_csv(POSTS_CSV)
    posts["published_at"] = pd.to_datetime(posts["published_at"], utc=True, format="ISO8601")
    posts["date"] = posts["published_at"].dt.tz_convert(None).dt.normalize()

    prices = pd.read_csv(PRICES_CSV, parse_dates=["date"]).sort_values(["coin", "date"])
    prices["next_day_return"] = prices.groupby("coin")["close"].transform(lambda s: s.shift(-1) / s - 1)

    meta = json.loads(META_JSON.read_text()) if META_JSON.exists() else {}
    return posts, prices, meta


def daily_sentiment(posts: pd.DataFrame) -> pd.DataFrame:
    daily = (
        posts.groupby(["coin", "date"])
        .agg(mentions=("id", "size"), avg_sentiment=("sentiment", "mean"))
        .reset_index()
    )
    counts = (
        posts.groupby(["coin", "date", "label"]).size()
        .unstack(fill_value=0)
        .reindex(columns=LABELS, fill_value=0)
        .reset_index()
    )
    return daily.merge(counts, on=["coin", "date"])


def time_ago(iso: str | None) -> str:
    if not iso:
        return "unknown"
    minutes = int((datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() // 60)
    if minutes < 60:
        return f"{minutes} min ago"
    if minutes < 48 * 60:
        return f"{minutes // 60} h ago"
    return f"{minutes // (24 * 60)} days ago"


def sentiment_color(value: float) -> str:
    if value >= POSITIVE_THRESHOLD:
        return PALETTE["labels"]["positive"]
    if value <= NEGATIVE_THRESHOLD:
        return PALETTE["labels"]["negative"]
    return PALETTE["labels"]["neutral"]


def spread_labels(values: dict[str, float], min_gap: float) -> dict[str, float]:
    """Nudge end-of-line label positions apart so they never overlap."""
    placed: dict[str, float] = {}
    previous = None
    for key, value in sorted(values.items(), key=lambda item: item[1]):
        position = value if previous is None else max(value, previous + min_gap)
        placed[key] = previous = position
    return placed


def style(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=36, b=8),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text=""),
        bargap=0.25,
    )
    fig.update_xaxes(showgrid=False)
    return fig


posts, prices, meta = load_data()

# ---------- Header ----------
st.title("Crypto Sentiment Dashboard")
st.markdown(
    "What crypto news and Reddit are saying about **Bitcoin, Ethereum and Solana**, "
    "and whether the mood lines up with the price."
)
st.caption(
    f"Collected automatically every 6 hours · last update {time_ago(meta.get('last_run'))} · "
    f"{len(posts):,} headlines and posts scored"
)

# ---------- Filters (one row, scoping everything below) ----------
f1, f2, f3 = st.columns([2, 2, 2])
with f1:
    coin = st.segmented_control(
        "Coin", list(COINS), default="BTC", format_func=lambda s: COINS[s]["name"]
    ) or "BTC"
with f2:
    period_label = st.segmented_control("Period", list(PERIODS), default="30 days") or "30 days"
with f3:
    chosen_sources = st.pills("Sources", list(SOURCE_TYPES), selection_mode="multi", default=list(SOURCE_TYPES))
    chosen_sources = chosen_sources or list(SOURCE_TYPES)

days = PERIODS[period_label]
end = pd.Timestamp.now(tz="UTC").tz_convert(None).normalize()
start = end - pd.Timedelta(days=days - 1)
prev_start = start - pd.Timedelta(days=days)

source_filter = posts["source_type"].isin([SOURCE_TYPES[s] for s in chosen_sources])
in_period = posts[source_filter & posts["date"].between(start, end)]
prev_period = posts[source_filter & posts["date"].between(prev_start, start - pd.Timedelta(days=1))]

coin_posts = in_period[in_period["coin"] == coin]
coin_prev = prev_period[prev_period["coin"] == coin]
coin_prices = prices[(prices["coin"] == coin) & prices["date"].between(start, end)]
daily_all = daily_sentiment(in_period) if not in_period.empty else pd.DataFrame()
coin_daily = daily_all[daily_all["coin"] == coin] if not daily_all.empty else pd.DataFrame()
reliable_all = daily_all[daily_all["mentions"] >= MIN_ITEMS_PER_DAY] if not daily_all.empty else daily_all
bar_opacity = [1.0 if n >= MIN_ITEMS_PER_DAY else LOW_SAMPLE_OPACITY for n in coin_daily.get("mentions", [])]
coin_name = COINS[coin]["name"]
coin_color = PALETTE["coins"][coin]

if coin_posts.empty:
    st.warning("No posts for this coin, period and source selection yet.")
    st.stop()

# ---------- KPI row ----------
k1, k2, k3, k4 = st.columns(4)
avg = coin_posts["sentiment"].mean()
prev_avg = coin_prev["sentiment"].mean() if len(coin_prev) >= MIN_ITEMS_FOR_COMPARISON else None
k1.metric(
    "Average sentiment",
    f"{avg:+.2f}",
    delta=f"{avg - prev_avg:+.2f} vs previous {days} days" if prev_avg is not None else None,
    help="VADER compound score from -1 (very negative) to +1 (very positive), averaged over every headline and post.",
    border=True,
)
k2.metric("Mentions", f"{len(coin_posts):,}", help="Headlines and posts mentioning this coin in the period.", border=True)
shares = coin_posts["label"].value_counts(normalize=True).reindex(LABELS, fill_value=0)
k3.metric(
    "Positive vs negative",
    f"{shares['positive']:.0%} / {shares['negative']:.0%}",
    help=f"Share of items scored positive (≥ {POSITIVE_THRESHOLD}) and negative (≤ {NEGATIVE_THRESHOLD}); "
    f"the remaining {shares['neutral']:.0%} are neutral.",
    border=True,
)
if len(coin_prices) >= 2:
    first, last = coin_prices["close"].iloc[0], coin_prices["close"].iloc[-1]
    k4.metric(
        f"{coin_name} price",
        f"${last:,.2f}",
        delta=f"{last / first - 1:+.1%} over {days} days",
        border=True,
    )

# ---------- Chart: sentiment and price (two panels, one shared date axis) ----------
st.subheader(f"{coin_name}: daily sentiment and price")
fig = make_subplots(
    rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12, row_heights=[0.45, 0.55],
    subplot_titles=("Average sentiment per day", "Closing price (USD)"),
)
fig.add_trace(
    go.Bar(
        x=coin_daily["date"], y=coin_daily["avg_sentiment"],
        marker=dict(color=[sentiment_color(v) for v in coin_daily["avg_sentiment"]], opacity=bar_opacity),
        customdata=coin_daily["mentions"],
        hovertemplate="Sentiment %{y:+.2f} (%{customdata} items)<extra></extra>",
        name="Sentiment",
    ),
    row=1, col=1,
)
fig.add_trace(
    go.Scatter(
        x=coin_prices["date"], y=coin_prices["close"], mode="lines",
        line=dict(color=coin_color, width=2),
        hovertemplate="Price $%{y:,.2f}<extra></extra>", name="Price",
    ),
    row=2, col=1,
)
fig.update_yaxes(tickformat="+.2f", zeroline=True, row=1, col=1)
fig.update_yaxes(tickprefix="$", tickformat=",.0f", row=2, col=1)
fig.update_xaxes(range=[start - pd.Timedelta(hours=12), end + pd.Timedelta(hours=12)])
fig.update_layout(showlegend=False)
st.plotly_chart(style(fig, 520), width="stretch")
st.caption(
    "Blue bars: mostly positive coverage that day. Red: mostly negative. Grey: neutral. "
    f"Faded bars are days with fewer than {MIN_ITEMS_PER_DAY} items, too few to trust."
)

# ---------- Charts: mood mix + coin comparison ----------
left, right = st.columns(2)
with left:
    st.subheader("Mood mix per day")
    mix = go.Figure()
    for lab in LABELS:
        mix.add_trace(
            go.Bar(
                x=coin_daily["date"], y=coin_daily[lab], name=lab.capitalize(),
                marker=dict(color=PALETTE["labels"][lab], opacity=bar_opacity, line=dict(width=2, color=SURFACE)),
                customdata=coin_daily["mentions"],
                hovertemplate=f"{lab.capitalize()}: %{{y}} of %{{customdata}}<extra></extra>",
            )
        )
    mix.update_layout(barmode="stack", barnorm="percent", yaxis=dict(ticksuffix="%", range=[0, 100]))
    st.plotly_chart(style(mix, 360), width="stretch")
    st.caption(
        f"Share of positive, neutral and negative items each day (bars sum to 100%). "
        f"Faded: fewer than {MIN_ITEMS_PER_DAY} items."
    )

with right:
    st.subheader("All three coins compared")
    compare = go.Figure()
    end_points = {}
    for symbol in COINS:
        series = reliable_all[reliable_all["coin"] == symbol] if not reliable_all.empty else pd.DataFrame()
        if series.empty:
            continue
        end_points[symbol] = (series["date"].iloc[-1], series["avg_sentiment"].iloc[-1])
        # Reindex to every day so missing days show as gaps instead of a line bridging them.
        series = series.set_index("date").reindex(pd.date_range(series["date"].min(), end)).rename_axis("date").reset_index()
        compare.add_trace(
            go.Scatter(
                x=series["date"], y=series["avg_sentiment"], name=COINS[symbol]["name"],
                mode="lines+markers", line=dict(color=PALETTE["coins"][symbol], width=2),
                marker=dict(size=8), hovertemplate=f"{COINS[symbol]['name']}: %{{y:+.2f}}<extra></extra>",
            )
        )
    if end_points:
        y_range = reliable_all["avg_sentiment"].max() - reliable_all["avg_sentiment"].min()
        label_y = spread_labels({s: y for s, (_, y) in end_points.items()}, min_gap=max(y_range, 0.1) * 0.09)
        for symbol, (x, _) in end_points.items():
            compare.add_annotation(
                x=x, y=label_y[symbol], text=COINS[symbol]["name"],
                xanchor="left", xshift=10, showarrow=False, font=dict(size=12),
            )
    compare.update_yaxes(tickformat="+.2f", zeroline=True)
    compare.update_layout(margin=dict(r=80))
    st.plotly_chart(style(compare, 360), width="stretch")
    st.caption(
        f"Average daily sentiment per coin, same period and sources. Days with fewer than "
        f"{MIN_ITEMS_PER_DAY} items are left out."
    )

# ---------- Does sentiment lead price? ----------
st.subheader("Does today's mood predict tomorrow's price?")
coin_reliable = coin_daily[coin_daily["mentions"] >= MIN_ITEMS_PER_DAY]
joined = coin_reliable.merge(prices[prices["coin"] == coin][["date", "next_day_return"]], on="date").dropna()
if len(joined) < MIN_DAYS_FOR_CORRELATION:
    st.info(
        f"Not enough history yet: {len(joined)} of {MIN_DAYS_FOR_CORRELATION} days with at least "
        f"{MIN_ITEMS_PER_DAY} items and a next-day price. The collector adds data every 6 hours, "
        "so this test fills in over the next couple of weeks."
    )
else:
    r = joined["avg_sentiment"].corr(joined["next_day_return"])
    scatter = go.Figure(
        go.Scatter(
            x=joined["avg_sentiment"], y=joined["next_day_return"], mode="markers",
            marker=dict(size=10, color=coin_color, line=dict(width=2, color="rgba(255,255,255,0.9)")),
            customdata=joined["date"].dt.strftime("%b %d"),
            hovertemplate="%{customdata}<br>Sentiment %{x:+.2f}<br>Next-day return %{y:+.2%}<extra></extra>",
        )
    )
    scatter.update_xaxes(title="Average sentiment that day", tickformat="+.2f", showgrid=True)
    scatter.update_yaxes(title="Price change the next day", tickformat="+.1%")
    scatter.update_layout(hovermode="closest")
    c1, c2 = st.columns([3, 1])
    c1.plotly_chart(style(scatter, 380).update_layout(hovermode="closest"), width="stretch")
    c2.metric("Correlation (Pearson r)", f"{r:+.2f}", help="-1 to +1. Near 0 means no linear relationship.")
    c2.metric("Days compared", len(joined))
    c2.caption(
        "Correlation is not causation, and with few days the number is noisy. "
        "Treat this as an exploratory signal, not a trading strategy."
    )

# ---------- Headlines ----------
st.subheader("Headlines driving the mood")
headline_cols = {
    "sentiment": st.column_config.NumberColumn("Score", format="%+.2f", width="small"),
    "title": st.column_config.TextColumn("Headline / post", width="large"),
    "source": st.column_config.TextColumn("Source", width="small"),
    "url": st.column_config.LinkColumn("Link", display_text="Open", width="small"),
}
h1, h2 = st.columns(2)
with h1:
    st.markdown("**Most positive**")
    st.dataframe(
        coin_posts.nlargest(5, "sentiment")[list(headline_cols)],
        column_config=headline_cols, hide_index=True, width="stretch",
    )
with h2:
    st.markdown("**Most negative**")
    st.dataframe(
        coin_posts.nsmallest(5, "sentiment")[list(headline_cols)],
        column_config=headline_cols, hide_index=True, width="stretch",
    )

with st.expander(f"All {len(coin_posts):,} {coin_name} items in this period"):
    st.dataframe(
        coin_posts.sort_values("published_at", ascending=False)[["published_at", *headline_cols, "label"]],
        column_config={
            **headline_cols,
            "published_at": st.column_config.DatetimeColumn("Published (UTC)", format="MMM D, HH:mm"),
            "label": st.column_config.TextColumn("Label", width="small"),
        },
        hide_index=True, width="stretch", height=400,
    )

with st.expander("Daily data table"):
    table = coin_daily.merge(
        prices[prices["coin"] == coin][["date", "close", "next_day_return"]], on="date", how="left"
    ).sort_values("date", ascending=False)
    st.dataframe(
        table.drop(columns="coin"),
        column_config={
            "date": st.column_config.DateColumn("Date"),
            "mentions": st.column_config.NumberColumn("Mentions"),
            "avg_sentiment": st.column_config.NumberColumn("Avg. sentiment", format="%+.3f"),
            "positive": st.column_config.NumberColumn("Positive"),
            "neutral": st.column_config.NumberColumn("Neutral"),
            "negative": st.column_config.NumberColumn("Negative"),
            "close": st.column_config.NumberColumn("Close (USD)", format="dollar"),
            "next_day_return": st.column_config.NumberColumn("Next-day return", format="percent"),
        },
        hide_index=True, width="stretch",
    )

with st.expander("How this works"):
    st.markdown(
        f"""
1. **Collect.** Every 6 hours a GitHub Actions job pulls headlines from CoinDesk, Cointelegraph, Decrypt and
   Google News, plus new posts from r/Bitcoin, r/ethereum, r/solana and r/CryptoCurrency (public RSS feeds,
   no API keys). Daily closing prices come from Yahoo Finance.
2. **Tag.** Items from general sources are assigned to a coin when they mention it by name or ticker.
   The same headline from two outlets is stored once.
3. **Score.** Each headline (plus the first 500 characters of the summary or post) is scored with
   [VADER](https://github.com/cjhutto/vaderSentiment), extended with crypto slang such as *bullish*, *rekt*
   and *FUD*. Scores ≥ {POSITIVE_THRESHOLD} count as positive and ≤ {NEGATIVE_THRESHOLD} as negative.
4. **Compare.** Daily average sentiment is lined up with the next day's price change.

**Limitations.** VADER is a word-based model, so it misses sarcasm and context. Mention counts reflect what
the feeds return (Google News caps each query at 100 results), not total market chatter. Reddit sometimes
rate-limits automated readers, so some runs may contain news only.
"""
    )

if meta.get("sources"):
    failed = [name for name, result in meta["sources"].items() if result.startswith("failed")]
    if failed:
        st.caption(f"Sources unavailable in the latest run: {', '.join(failed)}")

st.divider()
st.caption(
    "Built by Ahmad Ammar · [Source code on GitHub](https://github.com/Z3US-23/crypto-sentiment-dashboard) · "
    "[GitHub profile](https://github.com/Z3US-23)"
)
