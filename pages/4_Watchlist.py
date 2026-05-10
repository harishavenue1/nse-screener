import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf

st.set_page_config(
    page_title="Watchlist | NSE Screener",
    page_icon="⭐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── TradingView dark theme ─────────────────────────────────────────
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] {
    background-color: #131722 !important; color: #d1d4dc;
    font-family: -apple-system, "Trebuchet MS", sans-serif;
}
[data-testid="stMain"]          { background-color: #131722 !important; }
[data-testid="block-container"] { padding-top: 1rem !important; }
[data-testid="stSidebar"]       { background-color: #1e222d !important; border-right: 1px solid #2a2e39 !important; }
[data-testid="stSidebar"] *     { color: #d1d4dc !important; }
[data-testid="stSidebar"] label { color: #787b86 !important; font-size:0.78rem !important; }
[data-testid="stSidebar"] .stTextInput input,
[data-testid="stSidebar"] .stSelectbox > div > div {
    background-color: #131722 !important; border-color: #2a2e39 !important; color: #d1d4dc !important;
}
#MainMenu { visibility: hidden; } footer { visibility: hidden; }
header[data-testid="stHeader"] {
    background-color: #131722 !important; border-bottom: 1px solid #2a2e39 !important; box-shadow: none !important;
}
[data-testid="stToolbarActions"] { visibility: hidden; }

/* Banner */
.wl-banner {
    background: linear-gradient(90deg,#1e222d 0%,#131722 100%);
    border:1px solid #2a2e39; border-left:3px solid #f59e0b;
    border-radius:8px; padding:16px 24px; margin-bottom:20px;
    display:flex; align-items:center; gap:16px;
}
.wl-banner h1 { color:#d1d4dc; font-size:1.5rem; font-weight:700; margin:0 0 2px 0; }
.wl-banner p  { color:#787b86; font-size:0.8rem; margin:0; }

/* Summary strip */
.summary-strip {
    display:flex; gap:10px; margin-bottom:18px; flex-wrap:wrap;
}
.summary-card {
    background:#1e222d; border:1px solid #2a2e39; border-radius:6px;
    padding:10px 18px; flex:1; min-width:110px; text-align:center;
}
.summary-card .sc-label { color:#787b86; font-size:0.68rem; font-weight:700; text-transform:uppercase; letter-spacing:0.7px; }
.summary-card .sc-val   { color:#d1d4dc; font-size:1.15rem; font-weight:700; margin-top:3px; }
.summary-card .sc-val.bull { color:#26a69a; }
.summary-card .sc-val.bear { color:#ef5350; }
.summary-card .sc-val.gold { color:#f59e0b; }

/* Watchlist table */
.wl-table-wrap {
    background:#1e222d; border:1px solid #2a2e39; border-radius:8px; overflow:hidden;
}
.wl-table-wrap table {
    width:100%; border-collapse:collapse; font-size:0.82rem;
}
.wl-table-wrap th {
    background:#131722; color:#787b86; font-size:0.68rem; font-weight:700;
    text-transform:uppercase; letter-spacing:0.6px; padding:10px 12px;
    border-bottom:1px solid #2a2e39; text-align:right; white-space:nowrap;
}
.wl-table-wrap th:first-child { text-align:left; }
.wl-table-wrap td {
    padding:10px 12px; border-bottom:1px solid #181c27;
    color:#d1d4dc; text-align:right; white-space:nowrap;
}
.wl-table-wrap td:first-child { text-align:left; }
.wl-table-wrap tr:last-child td { border-bottom:none; }
.wl-table-wrap tr:hover td { background:#242836; }
.bull  { color:#26a69a !important; }
.bear  { color:#ef5350 !important; }
.gold  { color:#f59e0b !important; }
.muted { color:#787b86 !important; }

/* Tag badges */
.tag {
    display:inline-block; padding:2px 7px; border-radius:3px;
    font-size:0.65rem; font-weight:700; letter-spacing:0.4px;
}
.tag-bull { background:#0d2e2b; color:#26a69a; }
.tag-bear { background:#2e1515; color:#ef5350; }
.tag-gold { background:#2e2410; color:#f59e0b; }
.tag-muted{ background:#1e222d; color:#787b86; border:1px solid #2a2e39; }

/* RSI pill */
.rsi-pill {
    display:inline-block; padding:2px 8px; border-radius:10px;
    font-size:0.75rem; font-weight:700;
}
.rsi-ob  { background:#2e1515; color:#ef5350; }
.rsi-os  { background:#0d2e2b; color:#26a69a; }
.rsi-neu { background:#1e222d; color:#d1d4dc; border:1px solid #2a2e39; }

/* Section label */
.section-label {
    color:#787b86; font-size:0.68rem; font-weight:700; text-transform:uppercase;
    letter-spacing:1px; border-bottom:1px solid #2a2e39; padding-bottom:6px; margin:18px 0 12px 0;
}

/* Remove button */
button[data-testid="baseButton-secondary"] {
    background:#1e222d !important; border:1px solid #2a2e39 !important;
    color:#787b86 !important; font-size:0.75rem !important;
}
button[data-testid="baseButton-secondary"]:hover {
    border-color:#ef5350 !important; color:#ef5350 !important;
}

/* Empty state */
.empty-state {
    text-align:center; padding:60px 20px;
    color:#787b86; font-size:0.9rem;
}
.empty-state .es-icon { font-size:2.5rem; margin-bottom:12px; }
.empty-state .es-title { color:#d1d4dc; font-size:1.1rem; font-weight:700; margin-bottom:6px; }

/* Tab styling */
.stTabs [data-baseweb="tab-list"]  { gap:4px; border-bottom:1px solid #2a2e39; }
.stTabs [data-baseweb="tab"]       { background:#1e222d; border-radius:6px 6px 0 0; color:#787b86; padding:6px 18px; font-size:0.8rem; }
.stTabs [aria-selected="true"]     { background:#131722 !important; color:#d1d4dc !important; border-bottom:2px solid #f59e0b !important; }
.stTabs [data-baseweb="tab-panel"] { padding-top:16px; }

::-webkit-scrollbar { width:6px; height:6px; }
::-webkit-scrollbar-track { background:#131722; }
::-webkit-scrollbar-thumb { background:#2a2e39; border-radius:3px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
WATCHLIST_FILE = str(Path(__file__).resolve().parent.parent / "watchlist.json")
YF_SEARCH_URL  = "https://query1.finance.yahoo.com/v1/finance/search?q={q}&quotesCount=8&newsCount=0"
YF_SEARCH_HDRS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept":     "application/json",
}
_INDIA_EXCHANGES = {"NSI", "NMS", "BSE", "NSE", "NS", "BO", "NSE_EQ"}

PLOTLY_DARK = dict(
    paper_bgcolor="#131722", plot_bgcolor="#1e222d",
    font=dict(color="#d1d4dc", size=11),
    xaxis=dict(gridcolor="#2a2e39", zerolinecolor="#2a2e39", showgrid=True),
    yaxis=dict(gridcolor="#2a2e39", zerolinecolor="#2a2e39", showgrid=True),
    legend=dict(bgcolor="#1e222d", bordercolor="#2a2e39", borderwidth=1),
    margin=dict(l=0, r=0, t=30, b=0),
)

# ─────────────────────────────────────────────────────────────────────────────
# Watchlist persistence
# ─────────────────────────────────────────────────────────────────────────────
def load_watchlist() -> list[dict]:
    """Load watchlist from JSON file. Returns list of {ticker, name, added_at}."""
    try:
        with open(WATCHLIST_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_watchlist(wl: list[dict]):
    try:
        Path(WATCHLIST_FILE).parent.mkdir(parents=True, exist_ok=True)
        with open(WATCHLIST_FILE, "w") as f:
            json.dump(wl, f, indent=2)
    except OSError:
        pass   # read-only filesystem (some cloud deployments) — silently skip

def add_ticker(ticker: str, name: str):
    wl = load_watchlist()
    if not any(w["ticker"] == ticker for w in wl):
        wl.append({"ticker": ticker, "name": name, "added_at": datetime.now().isoformat()})
        save_watchlist(wl)
    return wl

def remove_ticker(ticker: str):
    wl = [w for w in load_watchlist() if w["ticker"] != ticker]
    save_watchlist(wl)

# ─────────────────────────────────────────────────────────────────────────────
# Symbol search helpers (same as Company Analysis)
# ─────────────────────────────────────────────────────────────────────────────
def _yf_ticker_from_yahoo(raw_sym: str) -> str:
    """Convert a raw Yahoo Finance symbol to a yfinance-compatible ticker.
    Keeps -SM / -ST / -BE etc. suffixes because some SME stocks ONLY work with them
    (e.g. SUNLITE-SM.NS, not SUNLITE.NS which is a different delisted company).
    """
    upper = raw_sym.upper()
    # Strip only the exchange dot-suffix (.NS / .BO), preserve everything else
    base = raw_sym
    for sfx in (".NS", ".ns", ".BO", ".bo"):
        base = base.replace(sfx, "")
    if ".BO" in upper:
        return base + ".BO"
    return base + ".NS"

def _ticker_display_sym(ticker: str) -> str:
    """Return a clean display symbol: SUNLITE-SM.NS → SUNLITE, YASHHV.BO → YASHHV."""
    return ticker.split(".")[0].split("-")[0].upper()

def _yahoo_search(query: str) -> list[dict]:
    try:
        url = YF_SEARCH_URL.format(q=requests.utils.quote(query))
        r   = requests.get(url, headers=YF_SEARCH_HDRS, timeout=6)
        quotes = r.json().get("quotes", [])
        results = []
        for qt in quotes:
            exch = qt.get("exchange", "")
            if any(x in exch for x in _INDIA_EXCHANGES):
                raw  = qt.get("symbol", "")
                name = qt.get("longname") or qt.get("shortname", "")
                if raw and name:
                    results.append({"ticker": _yf_ticker_from_yahoo(raw), "name": name})
        return results
    except Exception:
        return []

@st.cache_data(ttl=86400, show_spinner=False)
def get_nse_symbols() -> pd.DataFrame:
    """Load NSE equity list (main board + SME)."""
    dfs = []
    # Main board
    try:
        url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
        r   = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        df  = pd.read_csv(StringIO(r.text))
        df.columns = df.columns.str.strip()
        df = df.rename(columns={"NAME OF COMPANY": "Company Name", "SYMBOL": "Symbol"})
        df["Symbol"] = df["Symbol"].str.strip()
        df["Company Name"] = df["Company Name"].str.strip()
        df["Exchange"] = "NSE"
        dfs.append(df[["Symbol", "Company Name", "Exchange"]])
    except Exception:
        pass
    # SME
    try:
        url2 = "https://nsearchives.nseindia.com/content/equities/sec_list.csv"
        r2   = requests.get(url2, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        df2  = pd.read_csv(StringIO(r2.text))
        df2.columns = df2.columns.str.strip()
        sme  = df2[df2["Series"].str.strip().isin(["SM","ST"])].copy()
        sme["Exchange"] = "NSE"
        sme = sme.rename(columns={"Company Name": "Company Name"})
        dfs.append(sme[["Symbol","Company Name","Exchange"]])
    except Exception:
        pass
    return pd.concat(dfs, ignore_index=True).drop_duplicates("Symbol") if dfs else pd.DataFrame(columns=["Symbol","Company Name","Exchange"])

def find_symbol(query: str) -> list[dict]:
    """Search for a stock. Returns list of {ticker, name}."""
    q = query.strip().upper()
    nse = get_nse_symbols()
    results = []

    # 1. Exact symbol match
    exact = nse[nse["Symbol"] == q]
    if not exact.empty:
        row = exact.iloc[0]
        results.append({"ticker": f"{row['Symbol']}.NS", "name": row["Company Name"]})
        return results

    # 2. Name contains query
    name_match = nse[nse["Company Name"].str.upper().str.contains(q, na=False)]
    for _, row in name_match.head(5).iterrows():
        results.append({"ticker": f"{row['Symbol']}.NS", "name": row["Company Name"]})
    if results:
        return results

    # 3. Yahoo Finance search (handles NSE SME + BSE)
    yf_res = _yahoo_search(query)
    if yf_res:
        return yf_res[:5]

    # 4. Direct yfinance probe
    for suffix in [".NS", ".BO"]:
        try:
            tk = yf.Ticker(q + suffix)
            info = tk.fast_info
            if getattr(info, "last_price", None):
                name = tk.info.get("longName") or tk.info.get("shortName") or q
                return [{"ticker": q + suffix, "name": name}]
        except Exception:
            pass
    return []

# ─────────────────────────────────────────────────────────────────────────────
# Data fetching
# ─────────────────────────────────────────────────────────────────────────────
def _calc_rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff().dropna()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_g = gain.rolling(period).mean().iloc[-1]
    avg_l = loss.rolling(period).mean().iloc[-1]
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return round(100 - (100 / (1 + rs)), 1)

@st.cache_data(ttl=300, show_spinner=False)   # 5-min cache
def fetch_ticker_data(ticker: str) -> dict:
    """Fetch price + fundamental data for one ticker.

    Two isolated stages so a slow/broken info fetch never blocks price data:
      Stage 1 — history()  : price, OHLCV, 52W, RSI, MAs, sparkline
      Stage 2 — info dict  : name, fundamentals (PE, PB, ROE …)

    For NSE SME stocks (exchange=NSI) info.regularMarketPrice is stale;
    history is always authoritative. Falls back to -SM ticker if needed.
    """
    result = {
        "ticker": ticker,
        "name":   _ticker_display_sym(ticker),
        "error":  None,
        "price": None, "chg_pct": None,
        "open": None, "high": None, "low": None,
        "volume": None, "avg_volume": None,
        "w52_high": None, "w52_low": None,
        "rsi": None,
        "ma20": None, "ma50": None, "ma200": None,
        "market_cap": None, "pe": None, "pb": None,
        "ev_ebitda": None, "eps": None,
        "rev_ttm": None, "rev_growth": None,
        "debt_equity": None, "roe": None,
        "dividend_yield": None,
        "sector": None, "exchange": None,
        "sparkline": [],
        "resolved_ticker": ticker,
    }

    # ── Stage 1: History (isolated — never let info failure kill this) ────────
    _active_ticker = ticker
    try:
        hist = yf.Ticker(ticker).history(period="1y", interval="1d")

        # -SM fallback for NSE SME stocks like SUNLITE
        if hist.empty and ticker.endswith(".NS") and "-" not in ticker:
            sm = ticker.replace(".NS", "-SM.NS")
            hist_sm = yf.Ticker(sm).history(period="1y", interval="1d")
            if not hist_sm.empty:
                hist = hist_sm
                _active_ticker = sm
                result["resolved_ticker"] = sm

        if not hist.empty:
            closes = hist["Close"]
            last   = float(closes.iloc[-1])
            result["price"]      = round(last, 2)
            result["high"]       = round(float(hist["High"].iloc[-1]), 2)
            result["low"]        = round(float(hist["Low"].iloc[-1]), 2)
            result["open"]       = round(float(hist["Open"].iloc[-1]), 2)
            result["volume"]     = int(hist["Volume"].iloc[-1])
            result["avg_volume"] = int(hist["Volume"].mean())
            result["w52_high"]   = round(float(hist["High"].max()), 2)
            result["w52_low"]    = round(float(hist["Low"].min()), 2)
            if len(closes) >= 2:
                prev = float(closes.iloc[-2])
                result["chg_pct"] = round((last - prev) / prev * 100, 2) if prev else 0
            if len(closes) >= 15:
                result["rsi"]  = _calc_rsi(closes)
            if len(closes) >= 20:
                result["ma20"] = round(float(closes.tail(20).mean()), 2)
            if len(closes) >= 50:
                result["ma50"] = round(float(closes.tail(50).mean()), 2)
            if len(closes) >= 200:
                result["ma200"]= round(float(closes.tail(200).mean()), 2)
            result["sparkline"] = closes.tail(30).round(2).tolist()
        else:
            result["error"] = "No price history"
    except Exception as e:
        result["error"] = str(e)

    # ── Stage 2: info dict for name + fundamentals (best-effort) ─────────────
    try:
        info = yf.Ticker(_active_ticker).info or {}

        # Name
        raw_short = (info.get("shortName") or "").split(",")[0].strip()
        result["name"] = (
            info.get("longName")
            or (raw_short if raw_short and "." not in raw_short and len(raw_short) > 2 else None)
            or _ticker_display_sym(ticker)
        )

        result["market_cap"]    = info.get("marketCap")
        result["pe"]            = info.get("trailingPE") or info.get("forwardPE")
        result["pb"]            = info.get("priceToBook")
        result["ev_ebitda"]     = info.get("enterpriseToEbitda")
        result["eps"]           = info.get("trailingEps")
        result["debt_equity"]   = info.get("debtToEquity")
        result["roe"]           = info.get("returnOnEquity")
        result["dividend_yield"]= info.get("dividendYield")
        result["sector"]        = info.get("sector") or info.get("industry") or "—"
        result["exchange"]      = info.get("exchange") or ("BSE" if ticker.endswith(".BO") else "NSE")

        # Recalculate market cap when info value is stale (NSE SME)
        shares = info.get("sharesOutstanding")
        if shares and result["price"]:
            calc_mcap = shares * result["price"]
            if result["market_cap"] and abs(calc_mcap - result["market_cap"]) / result["market_cap"] > 0.30:
                result["market_cap"] = calc_mcap
            elif not result["market_cap"]:
                result["market_cap"] = calc_mcap

        # Price fallback if history was empty
        if not result["price"]:
            result["price"]   = info.get("currentPrice") or info.get("regularMarketPrice")
            result["chg_pct"] = info.get("regularMarketChangePercent") or 0
            if result["price"]:
                result["error"] = None

        # Revenue TTM
        try:
            fin = yf.Ticker(_active_ticker).quarterly_financials
            if not fin.empty:
                for lbl in ["Total Revenue", "Revenue"]:
                    if lbl in fin.index:
                        rev_row = fin.loc[lbl]
                        result["rev_ttm"] = float(rev_row.iloc[:4].sum())
                        if len(rev_row) >= 5:
                            cq = float(rev_row.iloc[0])
                            pq = float(rev_row.iloc[4])
                            if pq:
                                result["rev_growth"] = round((cq - pq) / abs(pq) * 100, 1)
                        break
        except Exception:
            pass
    except Exception:
        pass   # fundamentals unavailable — price data still shown

    return result

# ─────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────────────────────
def fmt_price(v):
    if v is None: return "—"
    return f"₹{v:,.2f}"

def fmt_pct(v, decimals=2):
    if v is None: return "—"
    sign = "+" if v > 0 else ""
    cls  = "bull" if v > 0 else ("bear" if v < 0 else "muted")
    return f'<span class="{cls}">{sign}{v:.{decimals}f}%</span>'

def fmt_mcap(v):
    if v is None: return "—"
    cr = v / 1e7
    if cr >= 10000: return f"₹{cr/100:.0f}K Cr"
    if cr >= 1000:  return f"₹{cr:.0f} Cr"
    return f"₹{cr:.1f} Cr"

def fmt_num(v, decimals=2):
    if v is None: return "—"
    return f"{v:.{decimals}f}"

def fmt_ratio(v, decimals=1):
    if v is None: return "—"
    return f"{v:.{decimals}f}x"

def rsi_pill(v):
    if v is None: return "—"
    if v >= 70:   cls, lbl = "rsi-ob", "&nbsp;OB"
    elif v <= 30: cls, lbl = "rsi-os", "&nbsp;OS"
    else:         cls, lbl = "rsi-neu", ""
    return f'<span class="rsi-pill {cls}">{v:.0f}{lbl}</span>'

def ma_signal_html(price, ma20, ma50, ma200):
    if price is None: return "—"
    above = sum([
        1 if (ma20  and price > ma20)  else 0,
        1 if (ma50  and price > ma50)  else 0,
        1 if (ma200 and price > ma200) else 0,
    ])
    total = sum([1 if v else 0 for v in [ma20, ma50, ma200]])
    if total == 0: return "—"
    if above == total: return '<span class="tag tag-bull">▲ ABOVE ALL MAs</span>'
    if above == 0:     return '<span class="tag tag-bear">▼ BELOW ALL MAs</span>'
    return f'<span class="tag tag-gold">~ {above}/{total} MAs</span>'

def pct_from_high(price, w52_high):
    if price is None or w52_high is None or w52_high == 0: return "—"
    pct = (price - w52_high) / w52_high * 100
    cls = "bull" if pct >= -5 else ("gold" if pct >= -20 else "bear")
    return f'<span class="{cls}">{pct:+.1f}%</span>'

def vol_vs_avg(vol, avg_vol):
    if vol is None or avg_vol is None or avg_vol == 0: return "—"
    ratio = vol / avg_vol
    cls = "bull" if ratio > 1.5 else ("gold" if ratio > 0.75 else "bear")
    return f'<span class="{cls}">{ratio:.1f}x</span>'

def sparkline_html(values: list) -> str:
    """Tiny inline SVG sparkline."""
    if len(values) < 2:
        return ""
    mn, mx = min(values), max(values)
    rng = mx - mn or 1
    w, h = 80, 24
    pts = []
    for i, v in enumerate(values):
        x = int(i / (len(values) - 1) * w)
        y = int(h - (v - mn) / rng * h)
        pts.append(f"{x},{y}")
    color = "#26a69a" if values[-1] >= values[0] else "#ef5350"
    path  = " ".join(pts)
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">'
        f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="1.5"/>'
        f'</svg>'
    )

_TABLE_CSS = """
<style>
* { box-sizing: border-box; }
body { margin:0; padding:0; background:#131722; color:#d1d4dc;
       font-family:-apple-system,"Trebuchet MS",sans-serif; }
.wl-table-wrap { background:#1e222d; border:1px solid #2a2e39; border-radius:8px; overflow:hidden; }
.wl-table-wrap table { width:100%; border-collapse:collapse; font-size:0.82rem; }
.wl-table-wrap th {
    background:#131722; color:#787b86; font-size:0.68rem; font-weight:700;
    text-transform:uppercase; letter-spacing:0.6px; padding:10px 12px;
    border-bottom:1px solid #2a2e39; text-align:right; white-space:nowrap;
    cursor:pointer; user-select:none; position:relative; }
.wl-table-wrap th:first-child { text-align:left; }
.wl-table-wrap th:hover { color:#d1d4dc; background:#1a1e2d; }
.wl-table-wrap th.sort-asc  { color:#f59e0b; }
.wl-table-wrap th.sort-desc { color:#f59e0b; }
.wl-table-wrap th .sort-arrow {
    display:inline-block; margin-left:4px; font-size:0.6rem;
    opacity:0.4; vertical-align:middle; }
.wl-table-wrap th.sort-asc  .sort-arrow,
.wl-table-wrap th.sort-desc .sort-arrow { opacity:1; color:#f59e0b; }
.wl-table-wrap td { padding:10px 12px; border-bottom:1px solid #181c27;
    color:#d1d4dc; text-align:right; white-space:nowrap; }
.wl-table-wrap td:first-child { text-align:left; }
.wl-table-wrap tr:last-child td { border-bottom:none; }
.wl-table-wrap tr:hover td { background:#242836; }
.bull  { color:#26a69a !important; }
.bear  { color:#ef5350 !important; }
.gold  { color:#f59e0b !important; }
.muted { color:#787b86 !important; }
.tag { display:inline-block; padding:2px 7px; border-radius:3px;
       font-size:0.65rem; font-weight:700; letter-spacing:0.4px; }
.tag-bull { background:#0d2e2b; color:#26a69a; }
.tag-bear { background:#2e1515; color:#ef5350; }
.tag-gold { background:#2e2410; color:#f59e0b; }
.rsi-pill { display:inline-block; padding:2px 8px; border-radius:10px;
             font-size:0.75rem; font-weight:700; }
.rsi-ob  { background:#2e1515; color:#ef5350; }
.rsi-os  { background:#0d2e2b; color:#26a69a; }
.rsi-neu { background:#1e222d; color:#d1d4dc; border:1px solid #2a2e39; }
::-webkit-scrollbar { width:6px; height:6px; }
::-webkit-scrollbar-track { background:#131722; }
::-webkit-scrollbar-thumb { background:#2a2e39; border-radius:3px; }
</style>
"""

_SORT_JS = """
<script>
(function () {
  // Parse a cell's text to a sortable value (numeric where possible)
  function parseVal(cell) {
    var raw = cell.innerText.trim();
    if (!raw || raw === '—') return -Infinity;
    // strip currency, sign, commas, whitespace, unit badges
    var s = raw.replace(/[₹+,\\s]/g, '');
    // market-cap shorthand: "184K Cr" -> 184e9, "1,234 Cr" -> 1234e7, "12.3L" -> 12.3e5
    if (/KCr$/i.test(s))  return parseFloat(s) * 1e9;
    if (/Cr$/i.test(s))   return parseFloat(s) * 1e7;
    if (/L$/i.test(s))    return parseFloat(s) * 1e5;
    // strip trailing x or %
    s = s.replace(/[x%]$/, '');
    // strip OB / OS labels from RSI pills
    s = s.replace(/(OB|OS)$/i, '').trim();
    var n = parseFloat(s);
    return isNaN(n) ? raw.toLowerCase() : n;
  }

  function initTable(table) {
    var sortCol = -1, sortAsc = true;
    var ths = Array.from(table.querySelectorAll('thead th'));

    // Inject arrow spans
    ths.forEach(function (th) {
      var arrow = document.createElement('span');
      arrow.className = 'sort-arrow';
      arrow.textContent = '⬍';
      th.appendChild(arrow);
    });

    ths.forEach(function (th, i) {
      th.addEventListener('click', function () {
        if (sortCol === i) { sortAsc = !sortAsc; }
        else               { sortCol = i; sortAsc = true; }

        // Update header styles + arrows
        ths.forEach(function (h, j) {
          h.classList.remove('sort-asc', 'sort-desc');
          h.querySelector('.sort-arrow').textContent = '⬍';
          if (j === i) {
            h.classList.add(sortAsc ? 'sort-asc' : 'sort-desc');
            h.querySelector('.sort-arrow').textContent = sortAsc ? '▲' : '▼';
          }
        });

        // Sort rows
        var tbody = table.querySelector('tbody');
        var rows  = Array.from(tbody.rows);
        rows.sort(function (a, b) {
          var va = parseVal(a.cells[i]), vb = parseVal(b.cells[i]);
          if (typeof va === 'number' && typeof vb === 'number') {
            return sortAsc ? va - vb : vb - va;
          }
          if (va < vb) return sortAsc ? -1 :  1;
          if (va > vb) return sortAsc ?  1 : -1;
          return 0;
        });
        rows.forEach(function (r) { tbody.appendChild(r); });
      });
    });
  }

  document.querySelectorAll('.wl-table-wrap table').forEach(initTable);
})();
</script>
"""

def render_table(html: str, height: int = 420):
    """Render a sortable HTML table via components.html (avoids Streamlit markdown stripping)."""
    components.html(_TABLE_CSS + html + _SORT_JS, height=height, scrolling=True)

# ─────────────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────────────
if "wl_search_results" not in st.session_state:
    st.session_state["wl_search_results"] = []
if "wl_refresh_ts" not in st.session_state:
    st.session_state["wl_refresh_ts"] = 0

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — Add / Manage
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⭐ Watchlist")
    st.markdown('<p style="color:#787b86;font-size:0.76rem;">Search and add any NSE / BSE stock</p>', unsafe_allow_html=True)
    st.divider()

    # Search input
    query = st.text_input("🔍 Search stock", placeholder="Name or symbol…", key="wl_query", label_visibility="collapsed")

    if query and len(query) >= 2:
        with st.spinner("Searching…"):
            results = find_symbol(query)
        if results:
            st.session_state["wl_search_results"] = results
        else:
            st.warning("No results found")
            st.session_state["wl_search_results"] = []

    if st.session_state["wl_search_results"]:
        st.markdown('<div class="section-label" style="margin-top:10px;">Search Results</div>', unsafe_allow_html=True)
        current_tickers = {w["ticker"] for w in load_watchlist()}
        for r in st.session_state["wl_search_results"]:
            col1, col2 = st.columns([3, 1])
            with col1:
                exch_tag = "BSE" if r["ticker"].endswith(".BO") else "NSE"
                st.markdown(
                    f'<div style="font-size:0.8rem;font-weight:600;color:#d1d4dc;">{r["name"]}</div>'
                    f'<div style="font-size:0.7rem;color:#787b86;">{r["ticker"]} · {exch_tag}</div>',
                    unsafe_allow_html=True
                )
            with col2:
                if r["ticker"] in current_tickers:
                    st.markdown('<span style="color:#26a69a;font-size:0.75rem;">✓ Added</span>', unsafe_allow_html=True)
                else:
                    if st.button("＋", key=f"add_{r['ticker']}"):
                        add_ticker(r["ticker"], r["name"])
                        st.rerun()

    st.divider()

    # Manage / Remove
    wl_meta = load_watchlist()
    if wl_meta:
        st.markdown('<div class="section-label">Manage Watchlist</div>', unsafe_allow_html=True)
        for item in wl_meta:
            c1, c2 = st.columns([4, 1])
            with c1:
                sym = item["ticker"].split(".")[0]
                exch = "BSE" if item["ticker"].endswith(".BO") else "NSE"
                st.markdown(
                    f'<div style="font-size:0.78rem;color:#d1d4dc;font-weight:600;">{sym}</div>'
                    f'<div style="font-size:0.68rem;color:#787b86;">{exch}</div>',
                    unsafe_allow_html=True
                )
            with c2:
                if st.button("✕", key=f"rm_{item['ticker']}"):
                    remove_ticker(item["ticker"])
                    st.rerun()

    st.divider()

    # Refresh
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.session_state["wl_refresh_ts"] = time.time()
        st.rerun()

    st.markdown(
        '<p style="color:#787b86;font-size:0.7rem;text-align:center;margin-top:8px;">Data cached 5 min</p>',
        unsafe_allow_html=True
    )

# ─────────────────────────────────────────────────────────────────────────────
# Main area
# ─────────────────────────────────────────────────────────────────────────────
wl_meta = load_watchlist()

# Banner
st.markdown(
    '<div class="wl-banner">'
    '<div style="font-size:2rem;">⭐</div>'
    '<div><h1>My Watchlist</h1>'
    f'<p>{len(wl_meta)} stocks · Last updated {datetime.now().strftime("%d %b %Y, %H:%M")}</p></div>'
    '</div>',
    unsafe_allow_html=True
)

# Empty state
if not wl_meta:
    st.markdown(
        '<div class="empty-state">'
        '<div class="es-icon">📋</div>'
        '<div class="es-title">Your watchlist is empty</div>'
        '<p>Search for a stock in the sidebar and click ＋ to add it here.</p>'
        '</div>',
        unsafe_allow_html=True
    )
    st.stop()

# ── Fetch data for all tickers (parallel) ─────────────────────────
progress_bar = st.progress(0, text="Loading watchlist data…")
all_data      = [None] * len(wl_meta)
_completed    = [0]
_watchlist_healed = False

def _fetch_one(idx_item):
    idx, item = idx_item
    return idx, fetch_ticker_data(item["ticker"])

with ThreadPoolExecutor(max_workers=8) as pool:
    futures = {pool.submit(_fetch_one, (i, item)): i for i, item in enumerate(wl_meta)}
    for fut in as_completed(futures):
        idx, d = fut.result()
        item   = wl_meta[idx]
        # Fallback name from watchlist.json when yfinance gave nothing
        if d["name"] == _ticker_display_sym(item["ticker"]) and item.get("name"):
            d["name"] = item["name"]
        # Auto-heal: ticker resolved to -SM variant
        if d["resolved_ticker"] != item["ticker"]:
            item["ticker"] = d["resolved_ticker"]
            _watchlist_healed = True
        all_data[idx] = d
        _completed[0] += 1
        progress_bar.progress(_completed[0] / len(wl_meta),
                               text=f"Loaded {_completed[0]}/{len(wl_meta)}…")

if _watchlist_healed:
    save_watchlist(wl_meta)
progress_bar.empty()

# ── Summary strip ─────────────────────────────────────────────────
valid   = [d for d in all_data if d["price"]]
gainers = sum(1 for d in valid if (d["chg_pct"] or 0) > 0)
losers  = sum(1 for d in valid if (d["chg_pct"] or 0) < 0)
overbought = sum(1 for d in valid if d["rsi"] and d["rsi"] >= 70)
oversold   = sum(1 for d in valid if d["rsi"] and d["rsi"] <= 30)
above_200  = sum(1 for d in valid if d["price"] and d["ma200"] and d["price"] > d["ma200"])

g_cls  = "bull" if gainers > losers else ("bear" if losers > gainers else "")
ob_cls = "bear" if overbought > 0 else "muted"
os_cls = "bull" if oversold > 0 else "muted"
am_cls = "bull" if above_200 > len(valid) // 2 else "bear"

st.markdown(f"""
<div class="summary-strip">
  <div class="summary-card">
    <div class="sc-label">Total Stocks</div>
    <div class="sc-val gold">{len(wl_meta)}</div>
  </div>
  <div class="summary-card">
    <div class="sc-label">Gainers / Losers</div>
    <div class="sc-val {g_cls}">{gainers} / {losers}</div>
  </div>
  <div class="summary-card">
    <div class="sc-label">RSI Overbought</div>
    <div class="sc-val {ob_cls}">{overbought}</div>
  </div>
  <div class="summary-card">
    <div class="sc-label">RSI Oversold</div>
    <div class="sc-val {os_cls}">{oversold}</div>
  </div>
  <div class="summary-card">
    <div class="sc-label">Above 200 DMA</div>
    <div class="sc-val {am_cls}">{above_200} / {len(valid)}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Tabs: Overview | Technical | Fundamentals
# ─────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Overview", "⚡ Technical", "📋 Fundamentals"])

# ── TAB 1: OVERVIEW ───────────────────────────────────────────────
with tab1:
    rows_html = ""
    for d in all_data:
        sym  = _ticker_display_sym(d["ticker"])
        exch = "BSE" if d["ticker"].endswith(".BO") else "NSE"
        exch_color = "#ef5350" if exch == "BSE" else "#26a69a"
        spark = sparkline_html(d["sparkline"])
        price_html = fmt_price(d["price"])
        chg_html   = fmt_pct(d["chg_pct"])
        high52     = fmt_price(d["w52_high"])
        low52      = fmt_price(d["w52_low"])
        from_high  = pct_from_high(d["price"], d["w52_high"])
        mcap_s     = fmt_mcap(d["market_cap"])
        pe_s       = fmt_num(d["pe"], 1) if d["pe"] else "—"
        rsi_s      = rsi_pill(d["rsi"])
        sector_s   = (d["sector"] or "—")[:22]

        rows_html += f"""
        <tr>
          <td>
            <div style="font-size:0.85rem;font-weight:700;color:#d1d4dc;">{sym}</div>
            <div style="font-size:0.7rem;color:#787b86;max-width:160px;overflow:hidden;text-overflow:ellipsis;">{d['name']}</div>
            <div style="font-size:0.65rem;margin-top:2px;"><span style="background:#1e222d;border:1px solid {exch_color};color:{exch_color};padding:1px 5px;border-radius:3px;font-size:0.62rem;">{exch}</span> <span style="color:#787b86;">{sector_s}</span></div>
          </td>
          <td>{spark}</td>
          <td style="font-weight:700;color:#d1d4dc;">{price_html}</td>
          <td>{chg_html}</td>
          <td class="muted">{high52}</td>
          <td class="muted">{low52}</td>
          <td>{from_high}</td>
          <td class="muted">{mcap_s}</td>
          <td class="muted">{pe_s}</td>
          <td>{rsi_s}</td>
        </tr>"""

    n_rows = len(all_data)
    render_table(f"""
    <div class="wl-table-wrap">
      <table>
        <thead>
          <tr>
            <th>Stock</th>
            <th>30D Chart</th>
            <th>Price</th>
            <th>Day Chg%</th>
            <th>52W High</th>
            <th>52W Low</th>
            <th>From High</th>
            <th>Mkt Cap</th>
            <th>P/E</th>
            <th>RSI (14)</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
    """, height=min(80 + n_rows * 68, 800))

# ── TAB 2: TECHNICAL ──────────────────────────────────────────────
with tab2:
    rows_html = ""
    for d in all_data:
        sym   = _ticker_display_sym(d["ticker"])
        price = d["price"]
        ma20  = d["ma20"]
        ma50  = d["ma50"]
        ma200 = d["ma200"]

        def ma_vs_price(p, ma):
            if p is None or ma is None or ma == 0: return "—"
            pct = (p - ma) / ma * 100
            cls = "bull" if pct > 0 else "bear"
            return f'<span class="{cls}">{pct:+.1f}%</span>'

        ma_sig = ma_signal_html(price, ma20, ma50, ma200)
        v_str  = vol_vs_avg(d["volume"], d["avg_volume"])
        vol_s  = f"{d['volume']/1e5:.1f}L" if d["volume"] else "—"

        def price_tag(p, ma, lbl):
            if p is None or ma is None: return f"<span class='muted'>—</span>"
            cls = "bull" if p > ma else "bear"
            return f'<span class="{cls}">₹{ma:,.0f}</span>'

        rows_html += f"""
        <tr>
          <td>
            <div style="font-size:0.85rem;font-weight:700;color:#d1d4dc;">{sym}</div>
            <div style="font-size:0.7rem;color:#787b86;">{d['name']}</div>
          </td>
          <td style="font-weight:700;color:#d1d4dc;">{fmt_price(price)}</td>
          <td>{fmt_pct(d['chg_pct'])}</td>
          <td>{rsi_pill(d['rsi'])}</td>
          <td>{ma_sig}</td>
          <td>{price_tag(price, ma20,  "20")}<br><span class='muted' style='font-size:0.68rem;'>20 DMA · {ma_vs_price(price,ma20)}</span></td>
          <td>{price_tag(price, ma50,  "50")}<br><span class='muted' style='font-size:0.68rem;'>50 DMA · {ma_vs_price(price,ma50)}</span></td>
          <td>{price_tag(price, ma200, "200")}<br><span class='muted' style='font-size:0.68rem;'>200 DMA · {ma_vs_price(price,ma200)}</span></td>
          <td>{vol_s} <span class='muted' style='font-size:0.7rem;'>({v_str})</span></td>
          <td>{pct_from_high(price, d['w52_high'])}</td>
        </tr>"""

    render_table(f"""
    <div class="wl-table-wrap">
      <table>
        <thead>
          <tr>
            <th>Stock</th>
            <th>Price</th>
            <th>Day Chg%</th>
            <th>RSI (14)</th>
            <th>MA Signal</th>
            <th>20 DMA</th>
            <th>50 DMA</th>
            <th>200 DMA</th>
            <th>Volume</th>
            <th>vs 52W High</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
    """, height=min(80 + len(all_data) * 78, 800))

    # RSI chart
    rsi_data = [(_ticker_display_sym(d["ticker"]), d["rsi"]) for d in all_data if d["rsi"] is not None]
    if rsi_data:
        st.markdown('<div class="section-label" style="margin-top:24px;">RSI Distribution</div>', unsafe_allow_html=True)
        syms_rsi  = [r[0] for r in rsi_data]
        vals_rsi  = [r[1] for r in rsi_data]
        bar_colors = ["#ef5350" if v >= 70 else ("#26a69a" if v <= 30 else "#2962ff") for v in vals_rsi]

        fig_rsi = go.Figure(go.Bar(
            x=syms_rsi, y=vals_rsi,
            marker_color=bar_colors,
            text=[f"{v:.0f}" for v in vals_rsi],
            textposition="outside",
        ))
        fig_rsi.add_hline(y=70, line_dash="dash", line_color="#ef5350", annotation_text="Overbought 70",
                          annotation_font_color="#ef5350", annotation_font_size=10)
        fig_rsi.add_hline(y=30, line_dash="dash", line_color="#26a69a", annotation_text="Oversold 30",
                          annotation_font_color="#26a69a", annotation_font_size=10)
        fig_rsi.add_hrect(y0=70, y1=100, fillcolor="#ef5350", opacity=0.04, line_width=0)
        fig_rsi.add_hrect(y0=0,  y1=30,  fillcolor="#26a69a", opacity=0.04, line_width=0)
        fig_rsi.update_layout(
            height=300, title="RSI (14) — All Watchlist Stocks",
            **{k: v for k, v in PLOTLY_DARK.items() if k != "yaxis"}
        )
        fig_rsi.update_yaxes(range=[0, 110], **PLOTLY_DARK["yaxis"])
        st.plotly_chart(fig_rsi, use_container_width=True)

# ── TAB 3: FUNDAMENTALS ───────────────────────────────────────────
with tab3:
    rows_html = ""
    for d in all_data:
        sym   = _ticker_display_sym(d["ticker"])
        de    = d["debt_equity"]
        roe   = d["roe"]
        rev_g = d["rev_growth"]

        def de_html(v):
            if v is None: return "—"
            cls = "bull" if v < 1 else ("gold" if v < 2 else "bear")
            return f'<span class="{cls}">{v:.2f}x</span>'

        def roe_html(v):
            if v is None: return "—"
            pct = v * 100 if abs(v) < 10 else v
            cls = "bull" if pct >= 15 else ("gold" if pct >= 10 else "bear")
            return f'<span class="{cls}">{pct:.1f}%</span>'

        div_yield = d["dividend_yield"]
        div_s = f"{div_yield*100:.2f}%" if div_yield else "—"

        pe_html = "—"
        if d["pe"]:
            cls = "bull" if d["pe"] < 20 else ("gold" if d["pe"] < 40 else "bear")
            pe_html = f'<span class="{cls}">{d["pe"]:.1f}x</span>'

        pb_html = "—"
        if d["pb"]:
            cls = "bull" if d["pb"] < 3 else ("gold" if d["pb"] < 6 else "bear")
            pb_html = f'<span class="{cls}">{d["pb"]:.1f}x</span>'

        ev_s = fmt_ratio(d["ev_ebitda"]) if d["ev_ebitda"] else "—"
        eps_s = f"₹{d['eps']:.2f}" if d["eps"] else "—"
        rev_ttm_s = fmt_mcap(d["rev_ttm"]) if d["rev_ttm"] else "—"

        rows_html += f"""
        <tr>
          <td>
            <div style="font-size:0.85rem;font-weight:700;color:#d1d4dc;">{sym}</div>
            <div style="font-size:0.7rem;color:#787b86;">{d['name']}</div>
          </td>
          <td class="muted">{fmt_mcap(d['market_cap'])}</td>
          <td>{pe_html}</td>
          <td>{pb_html}</td>
          <td class="muted">{ev_s}</td>
          <td style="font-weight:600;color:#d1d4dc;">{eps_s}</td>
          <td class="muted">{rev_ttm_s}</td>
          <td>{fmt_pct(rev_g, 1) if rev_g is not None else "—"}</td>
          <td>{de_html(de)}</td>
          <td>{roe_html(roe)}</td>
          <td class="{'bull' if div_yield and div_yield > 0.02 else 'muted'}">{div_s}</td>
        </tr>"""

    render_table(f"""
    <div class="wl-table-wrap">
      <table>
        <thead>
          <tr>
            <th>Stock</th>
            <th>Mkt Cap</th>
            <th>P/E</th>
            <th>P/B</th>
            <th>EV/EBITDA</th>
            <th>EPS TTM</th>
            <th>Revenue TTM</th>
            <th>Rev Growth</th>
            <th>D/E Ratio</th>
            <th>ROE</th>
            <th>Div Yield</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
    """, height=min(80 + len(all_data) * 68, 800))

    # Scatter: P/E vs ROE
    plot_data = [
        d for d in all_data
        if d["pe"] and d["roe"] and d["market_cap"]
        and 0 < d["pe"] < 200
    ]
    if len(plot_data) >= 2:
        st.markdown('<div class="section-label" style="margin-top:24px;">P/E vs ROE Scatter</div>', unsafe_allow_html=True)
        pes   = [d["pe"]  for d in plot_data]
        roes  = [(d["roe"]*100 if abs(d["roe"]) < 10 else d["roe"]) for d in plot_data]
        caps  = [max(d["market_cap"] / 1e10, 5) for d in plot_data]
        names = [_ticker_display_sym(d["ticker"]) for d in plot_data]

        fig_sc = go.Figure(go.Scatter(
            x=roes, y=pes,
            mode="markers+text",
            text=names, textposition="top center",
            marker=dict(
                size=[min(max(c, 8), 40) for c in caps],
                color=roes,
                colorscale=[[0,"#ef5350"],[0.5,"#f59e0b"],[1,"#26a69a"]],
                showscale=True,
                colorbar=dict(title="ROE%", tickfont=dict(color="#787b86")),
                line=dict(width=1, color="#2a2e39"),
            ),
            textfont=dict(color="#d1d4dc", size=10),
            hovertemplate="<b>%{text}</b><br>ROE: %{x:.1f}%<br>P/E: %{y:.1f}x<extra></extra>",
        ))
        fig_sc.update_layout(
            height=380,
            title="P/E vs ROE — bubble size = market cap",
            xaxis_title="ROE (%)",
            yaxis_title="P/E Ratio",
            **{k: v for k, v in PLOTLY_DARK.items() if k != "yaxis"}
        )
        fig_sc.update_yaxes(**PLOTLY_DARK["yaxis"])
        st.plotly_chart(fig_sc, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# Per-stock detail expanders
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label" style="margin-top:28px;">Stock Details</div>', unsafe_allow_html=True)

for d in all_data:
    sym   = _ticker_display_sym(d["ticker"])
    exch  = "BSE" if d["ticker"].endswith(".BO") else "NSE"
    price = d["price"]
    chg   = d["chg_pct"] or 0
    chg_color = "#26a69a" if chg >= 0 else "#ef5350"

    with st.expander(f"{'🟢' if chg >= 0 else '🔴'}  {sym}  ·  {fmt_price(price)}  ({chg:+.2f}%)  ·  {d['name']}", expanded=False):
        left, mid, right = st.columns(3)

        with left:
            st.markdown('<div class="section-label">Price Info</div>', unsafe_allow_html=True)
            metrics = [
                ("Price",       fmt_price(price)),
                ("Day Change",  f"{chg:+.2f}%"),
                ("Open",        fmt_price(d["open"])),
                ("Day High",    fmt_price(d["high"])),
                ("Day Low",     fmt_price(d["low"])),
                ("52W High",    fmt_price(d["w52_high"])),
                ("52W Low",     fmt_price(d["w52_low"])),
                ("Volume",      f"{d['volume']/1e5:.1f}L" if d["volume"] else "—"),
                ("Avg Volume",  f"{d['avg_volume']/1e5:.1f}L" if d["avg_volume"] else "—"),
            ]
            for lbl, val in metrics:
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #2a2e39;">'
                    f'<span style="color:#787b86;font-size:0.78rem;">{lbl}</span>'
                    f'<span style="color:#d1d4dc;font-size:0.78rem;font-weight:600;">{val}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

        with mid:
            st.markdown('<div class="section-label">Technical</div>', unsafe_allow_html=True)
            rsi_v = d["rsi"]
            rsi_lbl = "Overbought" if rsi_v and rsi_v >= 70 else ("Oversold" if rsi_v and rsi_v <= 30 else "Neutral")
            ma_vals = [
                ("RSI (14)",   f"{rsi_v:.1f} — {rsi_lbl}" if rsi_v else "—"),
                ("20 DMA",     fmt_price(d["ma20"])),
                ("50 DMA",     fmt_price(d["ma50"])),
                ("200 DMA",    fmt_price(d["ma200"])),
                ("vs 20 DMA",  f"{(price-d['ma20'])/d['ma20']*100:+.1f}%" if price and d['ma20'] else "—"),
                ("vs 50 DMA",  f"{(price-d['ma50'])/d['ma50']*100:+.1f}%" if price and d['ma50'] else "—"),
                ("vs 200 DMA", f"{(price-d['ma200'])/d['ma200']*100:+.1f}%" if price and d['ma200'] else "—"),
                ("vs 52W High", f"{(price-d['w52_high'])/d['w52_high']*100:+.1f}%" if price and d['w52_high'] else "—"),
            ]
            for lbl, val in ma_vals:
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #2a2e39;">'
                    f'<span style="color:#787b86;font-size:0.78rem;">{lbl}</span>'
                    f'<span style="color:#d1d4dc;font-size:0.78rem;font-weight:600;">{val}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

        with right:
            st.markdown('<div class="section-label">Fundamentals</div>', unsafe_allow_html=True)
            roe_pct = None
            if d["roe"]:
                roe_pct = d["roe"] * 100 if abs(d["roe"]) < 10 else d["roe"]
            fund_vals = [
                ("Market Cap",    fmt_mcap(d["market_cap"])),
                ("P/E Ratio",     f"{d['pe']:.1f}x"   if d["pe"]     else "—"),
                ("P/B Ratio",     f"{d['pb']:.2f}x"   if d["pb"]     else "—"),
                ("EV/EBITDA",     f"{d['ev_ebitda']:.1f}x" if d["ev_ebitda"] else "—"),
                ("EPS (TTM)",     f"₹{d['eps']:.2f}"  if d["eps"]    else "—"),
                ("Revenue (TTM)", fmt_mcap(d["rev_ttm"]) if d["rev_ttm"] else "—"),
                ("Rev Growth YoY",f"{d['rev_growth']:+.1f}%" if d["rev_growth"] is not None else "—"),
                ("Debt / Equity", f"{d['debt_equity']:.2f}x" if d["debt_equity"] else "—"),
                ("ROE",           f"{roe_pct:.1f}%"   if roe_pct     else "—"),
                ("Dividend Yield",f"{d['dividend_yield']*100:.2f}%" if d["dividend_yield"] else "—"),
            ]
            for lbl, val in fund_vals:
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #2a2e39;">'
                    f'<span style="color:#787b86;font-size:0.78rem;">{lbl}</span>'
                    f'<span style="color:#d1d4dc;font-size:0.78rem;font-weight:600;">{val}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

        # Mini price chart
        if d["sparkline"] and len(d["sparkline"]) >= 5:
            st.markdown('<div class="section-label" style="margin-top:10px;">30-Day Price Chart</div>', unsafe_allow_html=True)
            fill_color = "rgba(38,166,154,0.08)" if chg >= 0 else "rgba(239,83,80,0.08)"
            fig_mini = go.Figure(go.Scatter(
                y=d["sparkline"],
                mode="lines",
                line=dict(color=chg_color, width=2),
                fill="tozeroy",
                fillcolor=fill_color,
            ))
            fig_mini.update_layout(
                height=160, showlegend=False,
                **{k: v for k, v in PLOTLY_DARK.items() if k != "yaxis"}
            )
            fig_mini.update_yaxes(**PLOTLY_DARK["yaxis"])
            fig_mini.update_xaxes(showgrid=False)
            st.plotly_chart(fig_mini, use_container_width=True)

        # Open in Company Analysis
        if st.button(f"🔍 Open Full Analysis → {sym}", key=f"goto_{d['ticker']}"):
            st.session_state["ca_ticker"] = d["ticker"]
            st.session_state["ca_name"]   = d["name"]
            st.switch_page("pages/3_Company_Analysis.py")
