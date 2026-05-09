import os
import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from io import StringIO
from datetime import datetime, date

st.set_page_config(page_title="NSE Stock Screener", layout="wide")
st.title("NSE Stock Screener")
st.markdown("Price Change %, Sector, Weekly / Monthly / Yearly Gains & RSI(14)")

INDEX_URLS = {
    "Nifty 500":    "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
    "Midcap 150":   "https://nsearchives.nseindia.com/content/indices/ind_niftymidcap150list.csv",
    "Smallcap 250": "https://nsearchives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
    "Microcap 250": "https://nsearchives.nseindia.com/content/indices/ind_niftymicrocap250_list.csv",
}

SYMBOL_MAP = {"ZOMATO": "ETERNAL"}
CACHE_FILE = "/tmp/screener_cache.csv"
BATCH_SIZE = 100


def get_index_stocks(index_name):
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/xhtml+xml"}
        r = requests.get(INDEX_URLS[index_name], headers=headers, timeout=10)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text))
        cols = [c for c in ["Symbol", "Company Name", "Industry"] if c in df.columns]
        return df[cols].rename(columns={"Industry": "Sector"})
    except Exception as e:
        st.error(f"Could not fetch {index_name}: {e}")
        return None


def wilder_rsi(series, length=14):
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.iloc[1:length + 1].mean()
    avg_loss = loss.iloc[1:length + 1].mean()
    for g, l in zip(gain.iloc[length + 1:], loss.iloc[length + 1:]):
        avg_gain = (avg_gain * (length - 1) + g) / length
        avg_loss = (avg_loss * (length - 1) + l) / length
    if avg_loss == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_gain / avg_loss), 2)


def batch_download(tickers, period, interval):
    """Download a batch of tickers; returns (close_df, adj_df) or (None, None)."""
    try:
        raw = yf.download(tickers, period=period, interval=interval,
                          progress=False, auto_adjust=False)
        if raw is None or raw.empty:
            return None, None
        return raw["Close"], raw["Adj Close"]
    except Exception:
        return None, None


def scan_symbols(symbols, progress_bar, status_text):
    results = []
    total   = len(symbols)
    chunks  = [symbols[i:i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
    done    = 0

    for chunk in chunks:
        tickers = [f"{SYMBOL_MAP.get(s, s)}.NS" for s in chunk]

        # Three independent downloads per batch — one per interval
        status_text.text(f"Downloading daily data ({done + 1}–{done + len(chunk)})…")
        close_d, adj_d = batch_download(tickers, "2y", "1d")

        status_text.text(f"Downloading weekly data ({done + 1}–{done + len(chunk)})…")
        close_w, adj_w = batch_download(tickers, "2y", "1wk")

        status_text.text(f"Downloading monthly data ({done + 1}–{done + len(chunk)})…")
        close_m, adj_m = batch_download(tickers, "5y", "1mo")

        for symbol, ticker in zip(chunk, tickers):
            try:
                r = build_row(symbol, ticker,
                              close_d, adj_d,
                              close_w, adj_w,
                              close_m, adj_m)
                if r:
                    results.append(r)
            except Exception:
                pass

        done += len(chunk)
        progress_bar.progress(done / total)

    return results


def build_row(symbol, ticker, close_d, adj_d, close_w, adj_w, close_m, adj_m):
    # ── Daily ──────────────────────────────────────────────────────
    if close_d is None or ticker not in close_d.columns:
        return None
    cd = close_d[ticker].dropna()
    if len(cd) < 20:
        return None

    last_date = cd.index[-1].date()
    if (date.today() - last_date).days > 5:
        return None

    current      = float(cd.iloc[-1])
    current_date = cd.index[-1]

    def pct(idx):
        if len(cd) > abs(idx):
            old = float(cd.iloc[idx])
            return round((current - old) / old * 100, 2) if old else None
        return None

    def pct_since(offset):
        """Return % change vs the last available close on or before (current_date - offset)."""
        target = current_date - offset
        past   = cd[cd.index <= target]
        if past.empty:
            return None
        old = float(past.iloc[-1])
        return round((current - old) / old * 100, 2) if old else None

    ad = adj_d[ticker].dropna() if adj_d is not None and ticker in adj_d.columns else cd

    # ── Weekly RSI + 3 green weekly bars ──────────────────────────
    rsi_w    = None
    green_3w = False
    if close_w is not None and ticker in close_w.columns:
        cw = close_w[ticker].dropna()
        if len(cw) >= 20:
            rsi_w = wilder_rsi(cw)
        if len(cw) >= 4:
            # Each of the last 3 weeks must close higher than the prior week
            green_3w = all(
                float(cw.iloc[i]) > float(cw.iloc[i - 1])
                for i in [-3, -2, -1]
            )

    # ── Monthly RSI ────────────────────────────────────────────────
    rsi_m = None
    if close_m is not None and ticker in close_m.columns:
        cm = close_m[ticker].dropna()
        if len(cm) >= 15:
            rsi_m = wilder_rsi(cm)

    return {
        "Symbol":   symbol,
        "Price":    round(current, 2),
        "Change%":  pct(-2),
        "Weekly%":  pct(-6),
        "Monthly%": pct_since(pd.DateOffset(months=1)),
        "Yearly%":  pct_since(pd.DateOffset(years=1)),
        "RSI(D)":   wilder_rsi(ad) if len(ad) >= 30 else None,
        "RSI(W)":   rsi_w,
        "RSI(M)":   rsi_m,
        "3W Green": green_3w,
    }


def load_cache():
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        cached = pd.read_csv(CACHE_FILE)
        if pd.to_datetime(cached["_date"].iloc[0]).date() == date.today():
            return cached.drop(columns=["_date"])
    except Exception:
        pass
    return None


def save_cache(df):
    out = df.copy()
    out["_date"] = date.today().isoformat()
    out.to_csv(CACHE_FILE, index=False)


def color_pct(val):
    if pd.isna(val):
        return ""
    return f"color: {'#16a34a' if val >= 0 else '#dc2626'}; font-weight: 600"


def rsi_color(val):
    if pd.isna(val):
        return ""
    if val >= 70:
        return "color: #dc2626; font-weight: 600"
    if val <= 30:
        return "color: #16a34a; font-weight: 600"
    return ""


# ── Sidebar ────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    selected = st.multiselect(
        "Index",
        options=list(INDEX_URLS.keys()),
        default=["Midcap 150", "Smallcap 250"],
    )
    rsi_min, rsi_max = st.slider("Daily RSI range", 0, 100, (0, 100))
    change_min, change_max = st.slider("Change% range", -30, 30, (-30, 30))
    search      = st.text_input("Search symbol / company").strip().lower()
    only_3w     = st.checkbox("3 consecutive green weekly bars only")
    sort_col    = st.selectbox(
        "Sort by",
        ["Change%", "Weekly%", "Monthly%", "Yearly%", "RSI(D)", "RSI(W)", "RSI(M)"],
    )
    sort_asc = st.checkbox("Ascending", value=False)

run = st.button("Run Scan", type="primary", use_container_width=True)

# ── Scan ──────────────────────────────────────────────────────────
if run:
    if not selected:
        st.warning("Select at least one index.")
        st.stop()

    with st.spinner("Fetching index lists…"):
        frames = [get_index_stocks(idx) for idx in selected]
        frames = [f for f in frames if f is not None]
        if not frames:
            st.stop()
        info_df = pd.concat(frames).drop_duplicates("Symbol").reset_index(drop=True)

    cached = load_cache()
    if cached is not None:
        st.success(f"Loaded from today's cache — {len(cached)} stocks.")
        st.session_state["data"] = cached
        st.session_state["info"] = info_df
    else:
        symbols = info_df["Symbol"].tolist()
        st.info(f"Scanning {len(symbols)} stocks in batches of {BATCH_SIZE}…")
        progress = st.progress(0)
        status   = st.empty()

        results = scan_symbols(symbols, progress, status)

        status.empty()
        progress.empty()

        if not results:
            st.warning("No results. Check connection and try again.")
            st.stop()

        data_df = pd.DataFrame(results)
        save_cache(data_df)
        st.session_state["data"] = data_df
        st.session_state["info"] = info_df

# ── Display ───────────────────────────────────────────────────────
if "data" not in st.session_state:
    st.info("Configure filters on the left and click **Run Scan**.")
    st.stop()

raw  = st.session_state["data"]
info = st.session_state["info"]

df = raw.merge(info, on="Symbol", how="left")

df = df[df["RSI(D)"].isna()  | df["RSI(D)"].between(rsi_min, rsi_max)]
df = df[df["Change%"].isna() | df["Change%"].between(change_min, change_max)]
if only_3w and "3W Green" in df.columns:
    df = df[df["3W Green"] == True]

if search:
    mask = (
        df["Symbol"].str.lower().str.contains(search, na=False)
        | df["Company Name"].str.lower().str.contains(search, na=False)
    )
    df = df[mask]

df = df.sort_values(sort_col, ascending=sort_asc, na_position="last").reset_index(drop=True)

col_order = ["Company Name", "Symbol", "Sector", "Price",
             "Change%", "Weekly%", "Monthly%", "Yearly%",
             "RSI(D)", "RSI(W)", "RSI(M)", "3W Green"]
df = df[[c for c in col_order if c in df.columns]]

st.success(f"{len(df)} stocks matched")

pct_cols = ["Change%", "Weekly%", "Monthly%", "Yearly%"]
rsi_cols = ["RSI(D)", "RSI(W)", "RSI(M)"]

styled = (
    df.style
    .map(color_pct, subset=[c for c in pct_cols if c in df.columns])
    .map(rsi_color, subset=[c for c in rsi_cols if c in df.columns])
    .format(
        {c: "{:+.2f}%" for c in pct_cols if c in df.columns}
        | {c: "{:.1f}"  for c in rsi_cols if c in df.columns}
        | {"Price": "₹{:.2f}"}
    )
)

st.dataframe(styled, use_container_width=True, height=700)

csv = df.to_csv(index=False).encode()
st.download_button(
    "Download CSV",
    csv,
    f"screener_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
    "text/csv",
)

st.caption("Data: Yahoo Finance (native 1d/1wk/1mo intervals) + NSE index CSVs • Cached daily")
