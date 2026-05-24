import os
import json
import concurrent.futures
import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from io import StringIO
from datetime import datetime, date

st.set_page_config(
    page_title="NSE Stock Screener",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── TradingView-inspired palette ───────────────────────────────────
# bg: #131722  panel: #1e222d  border: #2a2e39
# text: #d1d4dc  muted: #787b86
# bull/green: #26a69a  bear/red: #ef5350  accent: #2962ff
# ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ---- Base ---- */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #131722 !important;
    color: #d1d4dc;
    font-family: -apple-system, "Trebuchet MS", sans-serif;
}
[data-testid="stMain"] { background-color: #131722 !important; }
[data-testid="block-container"] { padding-top: 1rem !important; }

/* ---- Sidebar ---- */
[data-testid="stSidebar"] {
    background-color: #1e222d !important;
    border-right: 1px solid #2a2e39 !important;
}
[data-testid="stSidebar"] * { color: #d1d4dc !important; }
[data-testid="stSidebar"] label { color: #787b86 !important; font-size: 0.78rem !important; }
[data-testid="stSidebar"] .stSelectbox > div > div,
[data-testid="stSidebar"] .stMultiSelect > div > div {
    background-color: #131722 !important;
    border-color: #2a2e39 !important;
    color: #d1d4dc !important;
}
[data-testid="stSidebar"] .stSlider [data-baseweb="slider"] { color: #2962ff; }
[data-testid="stSidebar"] section[data-testid="stSidebarContent"] { padding-top: 1.2rem; }

/* ---- Hide chrome, keep sidebar toggle visible ---- */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
/* Style header to match theme without hiding it (hiding it breaks the sidebar toggle) */
header[data-testid="stHeader"] {
    background-color: #131722 !important;
    border-bottom: 1px solid #2a2e39 !important;
    box-shadow: none !important;
}
/* Hide the deploy/share toolbar but not the sidebar arrow */
[data-testid="stToolbarActions"] { visibility: hidden; }

/* ---- Banner ---- */
.tv-banner {
    background: linear-gradient(90deg, #1e222d 0%, #131722 100%);
    border: 1px solid #2a2e39;
    border-left: 3px solid #2962ff;
    border-radius: 8px;
    padding: 18px 28px;
    margin-bottom: 20px;
}
.tv-banner h1 {
    color: #d1d4dc;
    font-size: 1.65rem;
    font-weight: 700;
    margin: 0 0 3px 0;
    letter-spacing: -0.3px;
}
.tv-banner p { color: #787b86; font-size: 0.82rem; margin: 0; }
.tv-banner .badge {
    display: inline-block;
    background: #2962ff22;
    color: #2962ff;
    border: 1px solid #2962ff55;
    border-radius: 4px;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.5px;
    padding: 2px 7px;
    margin-right: 6px;
    text-transform: uppercase;
}

/* ---- Section label ---- */
.section-label {
    color: #2a2e39;
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin: 16px 0 6px 0;
    border-bottom: 1px solid #2a2e39;
    padding-bottom: 4px;
}

/* ---- Metric cards ---- */
.metric-row {
    display: flex;
    gap: 10px;
    margin-bottom: 18px;
    flex-wrap: wrap;
}
.metric-card {
    background: #1e222d;
    border: 1px solid #2a2e39;
    border-radius: 6px;
    padding: 12px 18px;
    flex: 1;
    min-width: 100px;
    position: relative;
    overflow: hidden;
}
.metric-card::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: #2a2e39;
}
.metric-card.bull::before { background: #26a69a; }
.metric-card.bear::before { background: #ef5350; }
.metric-card.blue::before { background: #2962ff; }
.metric-card.purple::before { background: #7e57c2; }
.metric-card .label {
    color: #787b86;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin-bottom: 6px;
}
.metric-card .value {
    color: #d1d4dc;
    font-size: 1.45rem;
    font-weight: 700;
    line-height: 1;
    font-variant-numeric: tabular-nums;
}
.metric-card .value.bull { color: #26a69a; }
.metric-card .value.bear { color: #ef5350; }
.metric-card .value.blue { color: #2962ff; }
.metric-card .value.purple { color: #7e57c2; }

/* ---- Buttons ---- */
[data-testid="stSidebar"] .stButton > button {
    background-color: #2962ff !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 5px !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    letter-spacing: 0.2px !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background-color: #1e53e5 !important;
}
[data-testid="stSidebar"] .stButton:last-of-type > button {
    background-color: #1e222d !important;
    color: #787b86 !important;
    border: 1px solid #2a2e39 !important;
}
[data-testid="stSidebar"] .stButton:last-of-type > button:hover {
    border-color: #2962ff !important;
    color: #2962ff !important;
}

/* ---- Download button ---- */
[data-testid="stDownloadButton"] > button {
    background-color: #1e222d !important;
    color: #d1d4dc !important;
    border: 1px solid #2a2e39 !important;
    border-radius: 5px !important;
    font-size: 0.82rem !important;
}
[data-testid="stDownloadButton"] > button:hover {
    border-color: #2962ff !important;
    color: #2962ff !important;
}

/* ---- Dataframe ---- */
[data-testid="stDataFrame"] iframe {
    border-radius: 6px;
}
[data-testid="stDataFrame"] {
    border: 1px solid #2a2e39 !important;
    border-radius: 6px !important;
}

/* ---- Checkbox ---- */
[data-testid="stSidebar"] .stCheckbox span { color: #d1d4dc !important; }

/* ---- Scrollbar ---- */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #131722; }
::-webkit-scrollbar-thumb { background: #2a2e39; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #2962ff; }

/* ---- Toast ---- */
[data-testid="stToast"] { background: #1e222d !important; border: 1px solid #2a2e39 !important; }
</style>
""", unsafe_allow_html=True)

INDEX_URLS = {
    "Nifty 500":    "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
    "Midcap 150":   "https://nsearchives.nseindia.com/content/indices/ind_niftymidcap150list.csv",
    "Smallcap 250": "https://nsearchives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
    "Microcap 250": "https://nsearchives.nseindia.com/content/indices/ind_niftymicrocap250_list.csv",
}

# NSE sec_list has ALL NSE equities including SME (SM/ST series) — ~545 SME stocks
NSE_SEC_LIST_URL = "https://nsearchives.nseindia.com/content/equities/sec_list.csv"

SYMBOL_MAP = {"ZOMATO": "ETERNAL"}
CACHE_FILE      = "/tmp/screener_cache.csv"
FUND_CACHE_FILE = "/tmp/screener_fund_cache.json"
BATCH_SIZE = 100


@st.cache_data(ttl=86400, show_spinner=False)
def get_nse_sme_stocks():
    """Fetch NSE SME companies from NSE sec_list (SM + ST series). ~545 stocks."""
    try:
        r = requests.get(NSE_SEC_LIST_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text))
        df.columns = df.columns.str.strip()
        sme = df[df["Series"].str.strip().isin(["SM", "ST"])].copy()
        sme = sme.rename(columns={"Security Name": "Company Name"})
        sme["Symbol"]       = sme["Symbol"].str.strip()
        sme["Company Name"] = sme["Company Name"].str.strip()
        sme["Sector"]       = "NSE SME"
        sme["Exchange"]     = "NSE"
        return sme[["Symbol", "Company Name", "Sector", "Exchange"]].reset_index(drop=True)
    except Exception as e:
        st.error(f"Could not fetch NSE SME list: {e}")
        return None


def parse_bse_custom(raw: str) -> pd.DataFrame:
    """Parse comma/newline-separated BSE symbols into a stock DataFrame."""
    syms = [s.strip().upper() for s in raw.replace("\n", ",").split(",") if s.strip()]
    rows = [{"Symbol": s, "Company Name": s, "Sector": "BSE SME", "Exchange": "BSE"}
            for s in syms]
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["Symbol", "Company Name", "Sector", "Exchange"])


def get_index_stocks(index_name):
    """Returns DataFrame with Symbol, Company Name, Sector, Exchange columns."""
    if index_name == "NSE SME Emerge":
        return get_nse_sme_stocks()
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/xhtml+xml"}
        r = requests.get(INDEX_URLS[index_name], headers=headers, timeout=10)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text))
        cols = [c for c in ["Symbol", "Company Name", "Industry"] if c in df.columns]
        df = df[cols].rename(columns={"Industry": "Sector"})
        df["Exchange"] = "NSE"
        return df
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
    try:
        raw = yf.download(tickers, period=period, interval=interval,
                          progress=False, auto_adjust=False)
        if raw is None or raw.empty:
            return None, None
        return raw["Close"], raw["Adj Close"]
    except Exception:
        return None, None


def scan_symbols(symbols, progress_bar, status_text, exchange_map=None):
    """exchange_map: dict of {symbol: 'NSE'|'BSE'}, defaults to NSE for all."""
    results = []
    total  = len(symbols)
    chunks = [symbols[i:i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
    done   = 0
    if exchange_map is None:
        exchange_map = {}

    for chunk in chunks:
        tickers = [
            f"{SYMBOL_MAP.get(s, s)}.{'BO' if exchange_map.get(s) == 'BSE' else 'NS'}"
            for s in chunk
        ]

        status_text.markdown(f"⬇️ Fetching **daily** data — stocks {done + 1}–{done + len(chunk)}…")
        close_d, adj_d = batch_download(tickers, "2y", "1d")

        status_text.markdown(f"⬇️ Fetching **weekly** data — stocks {done + 1}–{done + len(chunk)}…")
        close_w, adj_w = batch_download(tickers, "2y", "1wk")

        status_text.markdown(f"⬇️ Fetching **monthly** data — stocks {done + 1}–{done + len(chunk)}…")
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
        target = current_date - offset
        past   = cd[cd.index <= target]
        if past.empty:
            return None
        old = float(past.iloc[-1])
        return round((current - old) / old * 100, 2) if old else None

    ad = adj_d[ticker].dropna() if adj_d is not None and ticker in adj_d.columns else cd

    rsi_w    = None
    green_3w = False
    if close_w is not None and ticker in close_w.columns:
        cw = close_w[ticker].dropna()
        if len(cw) >= 20:
            rsi_w = wilder_rsi(cw)
        if len(cw) >= 4:
            green_3w = all(float(cw.iloc[i]) > float(cw.iloc[i - 1]) for i in [-3, -2, -1])

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
        "3Month%":  pct_since(pd.DateOffset(months=3)),
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


def load_fund_cache():
    try:
        if os.path.exists(FUND_CACHE_FILE):
            with open(FUND_CACHE_FILE) as f:
                data = json.load(f)
            if data.get("_date") == date.today().isoformat():
                return data.get("data", {})
    except Exception:
        pass
    return {}


def save_fund_cache(data):
    try:
        with open(FUND_CACHE_FILE, "w") as f:
            json.dump({"_date": date.today().isoformat(), "data": data}, f)
    except Exception:
        pass


def _fetch_one_fund(args):
    sym, exchange_map = args
    suffix = ".BO" if exchange_map.get(sym) == "BSE" else ".NS"
    ticker_sym = SYMBOL_MAP.get(sym, sym) + suffix
    try:
        t = yf.Ticker(ticker_sym)
        q = t.quarterly_income_stmt  # cols = dates newest-first, rows = metrics
        if q is None or q.empty:
            return sym, {}

        def get_row(names):
            for n in names:
                if n in q.index:
                    row = q.loc[n].dropna()
                    return row if not row.empty else None
            return None

        rev_row = get_row(["Total Revenue", "Revenue"])
        gp_row  = get_row(["Gross Profit"])
        eps_row = get_row(["Basic EPS", "Diluted EPS"])

        result = {}

        if rev_row is not None and len(rev_row) >= 1:
            result["Revenue (Cr)"] = round(float(rev_row.iloc[0]) / 1e7, 1)

        if rev_row is not None and len(rev_row) >= 2:
            curr, prev = float(rev_row.iloc[0]), float(rev_row.iloc[1])
            if prev != 0:
                result["QoQ Rev%"] = round((curr - prev) / abs(prev) * 100, 1)

        if rev_row is not None and len(rev_row) >= 5:
            curr, yr = float(rev_row.iloc[0]), float(rev_row.iloc[4])
            if yr != 0:
                result["YoY Rev%"] = round((curr - yr) / abs(yr) * 100, 1)

        if gp_row is not None and rev_row is not None and len(rev_row) >= 1:
            gp, rev = float(gp_row.iloc[0]), float(rev_row.iloc[0])
            if rev != 0:
                result["Gross Margin%"] = round(gp / rev * 100, 1)

        if eps_row is not None and len(eps_row) >= 5:
            curr_e, yr_e = float(eps_row.iloc[0]), float(eps_row.iloc[4])
            if yr_e != 0:
                result["YoY EPS%"] = round((curr_e - yr_e) / abs(yr_e) * 100, 1)

        return sym, result
    except Exception:
        return sym, {}


def fetch_fundamentals(symbols, exchange_map, progress_bar=None):
    cached = load_fund_cache()
    to_fetch = [s for s in symbols if s not in cached]
    if to_fetch:
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(_fetch_one_fund, (s, exchange_map)): s for s in to_fetch}
            done = 0
            for fut in concurrent.futures.as_completed(futures):
                sym, data = fut.result()
                results[sym] = data
                done += 1
                if progress_bar is not None:
                    progress_bar.progress(done / len(to_fetch))
        cached.update(results)
        save_fund_cache(cached)
    return {s: cached.get(s, {}) for s in symbols}



def color_pct(val):
    if pd.isna(val):
        return "color: #787b86"
    return f"color: {'#26a69a' if val >= 0 else '#ef5350'}; font-weight: 600"


def rsi_color(val):
    if pd.isna(val):
        return "color: #787b86"
    if val >= 70:
        return "color: #ef5350; font-weight: 700"
    if val <= 30:
        return "color: #26a69a; font-weight: 700"
    return "color: #d1d4dc"


# ── Sidebar ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 NSE Screener")
    st.markdown('<div class="section-label">Universe</div>', unsafe_allow_html=True)
    selected = st.multiselect(
        "Indices",
        options=list(INDEX_URLS.keys()) + ["NSE SME Emerge"],
        default=["Midcap 150", "Smallcap 250"],
        label_visibility="collapsed",
    )
    st.markdown(
        '<div class="section-label" style="margin-top:10px">BSE SME Symbols</div>',
        unsafe_allow_html=True,
    )
    bse_input = st.text_area(
        "BSE symbols",
        placeholder="YASHHV, CNCRD, SUPREMEPWR\n(comma or newline separated)",
        height=80, label_visibility="collapsed",
        help="Enter BSE-listed SME stock symbols. These are fetched with .BO suffix from yfinance.",
    ).strip()

    st.markdown('<div class="section-label">Filters</div>', unsafe_allow_html=True)
    rsi_min, rsi_max = st.slider("Daily RSI", 0, 100, (0, 100))
    change_min, change_max = st.slider("Day Change %", -30, 30, (-30, 30))
    only_3w = st.checkbox("3 consecutive green weekly bars")

    st.markdown('<div class="section-label">Search</div>', unsafe_allow_html=True)
    search = st.text_input("Symbol or company", placeholder="e.g. RELIANCE", label_visibility="collapsed").strip().lower()

    st.markdown('<div class="section-label">Sort</div>', unsafe_allow_html=True)
    sort_col = st.selectbox(
        "Sort by", label_visibility="collapsed",
        options=["Monthly%", "3Month%", "Yearly%", "Weekly%", "Change%", "RSI(D)", "RSI(W)", "RSI(M)"],
    )
    sort_dir = st.radio("Order", ["Descending ↓", "Ascending ↑"], horizontal=True, label_visibility="collapsed")
    sort_asc = sort_dir == "Ascending ↑"

    st.markdown("---")
    run   = st.button("🚀 Run Scan", type="primary", use_container_width=True)
    clear = st.button("🔄 Clear Cache & Rescan", use_container_width=True)
    st.markdown(
        f'<div style="color:#475569;font-size:0.72rem;text-align:center;margin-top:8px;">'
        f'Data as of {datetime.now().strftime("%d %b %Y")}</div>',
        unsafe_allow_html=True,
    )

# ── Header ────────────────────────────────────────────────────────
st.markdown(f"""
<div class="tv-banner">
  <h1>NSE Stock Screener</h1>
  <p style="margin-top:8px;">
    <span class="badge">NSE</span>
    <span class="badge" style="color:#26a69a;border-color:#26a69a55;background:#26a69a22;">Live Data</span>
    <span style="color:#787b86;">
      Price &nbsp;·&nbsp; Sector &nbsp;·&nbsp; Weekly / Monthly / Yearly Returns
      &nbsp;·&nbsp; RSI(14) Daily / Weekly / Monthly &nbsp;·&nbsp; 3-Week Green Streak
    </span>
  </p>
</div>
""", unsafe_allow_html=True)

# ── Cache clear ───────────────────────────────────────────────────
if clear:
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
    st.session_state.pop("data", None)
    st.session_state.pop("info", None)
    st.rerun()

# ── Scan ──────────────────────────────────────────────────────────
if run:
    if not selected and not bse_input:
        st.warning("Select at least one index or enter BSE symbols.")
        st.stop()

    with st.spinner("Fetching index lists…"):
        frames = [get_index_stocks(idx) for idx in selected] if selected else []
        frames = [f for f in frames if f is not None]

        # Append BSE custom symbols
        if bse_input:
            bse_df = parse_bse_custom(bse_input)
            if not bse_df.empty:
                frames.append(bse_df)

        if not frames:
            st.stop()
        info_df = pd.concat(frames).drop_duplicates("Symbol").reset_index(drop=True)

    # Build exchange map: symbol → 'NSE' or 'BSE'
    exchange_map = {}
    if "Exchange" in info_df.columns:
        exchange_map = dict(zip(info_df["Symbol"], info_df["Exchange"]))

    cached = load_cache()
    if cached is not None:
        st.toast(f"Loaded from today's cache — {len(cached)} stocks.", icon="✅")
        st.session_state["data"]         = cached
        st.session_state["info"]         = info_df
        st.session_state["exchange_map"] = exchange_map
    else:
        symbols = info_df["Symbol"].tolist()
        progress = st.progress(0, text=f"Scanning {len(symbols)} stocks…")
        status   = st.empty()

        results = scan_symbols(symbols, progress, status, exchange_map)

        status.empty()
        progress.empty()

        if not results:
            st.error("No results returned. Check your connection and try again.")
            st.stop()

        data_df = pd.DataFrame(results)
        save_cache(data_df)
        st.session_state["data"]         = data_df
        st.session_state["info"]         = info_df
        st.session_state["exchange_map"] = exchange_map
        st.toast(f"Scan complete — {len(data_df)} stocks loaded.", icon="✅")

# ── Empty state ───────────────────────────────────────────────────
if "data" not in st.session_state:
    st.markdown("""
    <div style="text-align:center;padding:80px 0;color:#475569;">
      <div style="font-size:3rem;margin-bottom:16px;">📊</div>
      <div style="font-size:1.1rem;font-weight:600;color:#64748b;margin-bottom:8px;">No data yet</div>
      <div style="font-size:0.875rem;">Select indices in the sidebar and click <strong>Run Scan</strong></div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Filter & sort ─────────────────────────────────────────────────
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
             "Change%", "Weekly%", "Monthly%", "3Month%", "Yearly%",
             "RSI(D)", "RSI(W)", "RSI(M)", "3W Green"]
df = df[[c for c in col_order if c in df.columns]]

# ── Shared helpers ────────────────────────────────────────────────
def delta_html(val, size="1rem"):
    if val is None or pd.isna(val):
        return '<span style="color:#787b86">—</span>'
    arrow = "▲" if val >= 0 else "▼"
    color = "#26a69a" if val >= 0 else "#ef5350"
    return f'<span style="color:{color};font-size:{size};font-weight:700">{arrow} {abs(val):.2f}%</span>'

SCREENER_PCT_COLS = ["Change%", "Weekly%", "Monthly%", "3Month%", "Yearly%"]
RSI_COLS          = ["RSI(D)", "RSI(W)", "RSI(M)"]
FUND_METRICS   = ["Revenue (Cr)", "QoQ Rev%", "YoY Rev%", "Gross Margin%", "YoY EPS%"]
FUND_PCT_COLS  = ["QoQ Rev%", "YoY Rev%", "YoY EPS%"]
FUND_VIEW_COLS = ["Symbol", "Company Name"] + FUND_METRICS

def fmt_pct(v):
    if pd.isna(v):
        return "—"
    return f"▲ {v:.1f}%" if v >= 0 else f"▼ {abs(v):.1f}%"

def fmt_rev(v):
    if pd.isna(v):
        return "—"
    return f"₹{v:,.0f} Cr"

def fmt_margin(v):
    if pd.isna(v):
        return "—"
    return f"{v:.1f}%"

def style_fund_df(frame):
    pct_sub = [c for c in FUND_PCT_COLS + SCREENER_PCT_COLS if c in frame.columns]
    rsi_sub = [c for c in RSI_COLS if c in frame.columns]
    fmt = {c: fmt_pct for c in pct_sub}
    if "Revenue (Cr)" in frame.columns:
        fmt["Revenue (Cr)"] = fmt_rev
    if "Gross Margin%" in frame.columns:
        fmt["Gross Margin%"] = fmt_margin
    if "Price" in frame.columns:
        fmt["Price"] = "₹{:.2f}".format
    if rsi_sub:
        fmt.update({c: "{:.1f}".format for c in rsi_sub})
    styled = (
        frame.style
        .map(color_pct, subset=pct_sub)
        .map(rsi_color, subset=rsi_sub)
        .format(fmt)
        .set_properties(**{"background-color": "#1e222d", "color": "#d1d4dc", "border-color": "#2a2e39"})
    )
    return styled

def merge_fundamentals(frame, fund_dict):
    frame = frame.copy()
    for col in FUND_METRICS:
        frame[col] = frame["Symbol"].map(lambda s, c=col: fund_dict.get(s, {}).get(c))
    return frame

# ── Tabs ──────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📈 Screener", "📊 Fundamental", "⭐ Watchlist"])

# ── Tab 1: Screener ───────────────────────────────────────────────
with tab1:
    gainers    = int((df["Change%"] > 0).sum()) if "Change%" in df.columns else 0
    losers     = int((df["Change%"] < 0).sum()) if "Change%" in df.columns else 0
    green3w    = int(df["3W Green"].sum())       if "3W Green" in df.columns else 0
    overbought = int((df["RSI(D)"] >= 70).sum()) if "RSI(D)" in df.columns else 0
    oversold   = int((df["RSI(D)"] <= 30).sum()) if "RSI(D)" in df.columns else 0
    avg_chg    = df["Change%"].mean()  if "Change%" in df.columns else None
    avg_mo     = df["Monthly%"].mean() if "Monthly%" in df.columns else None

    st.markdown(f"""
<div class="metric-row">
  <div class="metric-card blue">
    <div class="label">Stocks shown</div>
    <div class="value blue">{len(df)}</div>
  </div>
  <div class="metric-card bull">
    <div class="label">Gainers today</div>
    <div class="value bull">{gainers}</div>
  </div>
  <div class="metric-card bear">
    <div class="label">Losers today</div>
    <div class="value bear">{losers}</div>
  </div>
  <div class="metric-card {'bull' if avg_chg and avg_chg >= 0 else 'bear'}">
    <div class="label">Avg day change</div>
    <div class="value" style="font-size:1.1rem;padding-top:4px;">{delta_html(avg_chg, "1.1rem")}</div>
  </div>
  <div class="metric-card {'bull' if avg_mo and avg_mo >= 0 else 'bear'}">
    <div class="label">Avg monthly</div>
    <div class="value" style="font-size:1.1rem;padding-top:4px;">{delta_html(avg_mo, "1.1rem")}</div>
  </div>
  <div class="metric-card bull">
    <div class="label">3W Green streak</div>
    <div class="value bull">{green3w}</div>
  </div>
  <div class="metric-card bear">
    <div class="label">RSI ≥ 70</div>
    <div class="value bear">{overbought}</div>
  </div>
  <div class="metric-card purple">
    <div class="label">RSI ≤ 30</div>
    <div class="value purple">{oversold}</div>
  </div>
</div>
""", unsafe_allow_html=True)

    styled1 = (
        df.style
        .map(color_pct, subset=[c for c in SCREENER_PCT_COLS if c in df.columns])
        .map(rsi_color, subset=[c for c in RSI_COLS if c in df.columns])
        .format(
            {c: fmt_pct for c in SCREENER_PCT_COLS if c in df.columns}
            | {c: "{:.1f}".format for c in RSI_COLS if c in df.columns}
            | ({"Price": "₹{:.2f}".format} if "Price" in df.columns else {})
        )
        .set_properties(**{"background-color": "#1e222d", "color": "#d1d4dc", "border-color": "#2a2e39"})
    )
    st.dataframe(styled1, use_container_width=True, height=620)

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(
            '<div style="color:#2a2e39;font-size:0.75rem;padding-top:8px;">'
            'Data: Yahoo Finance (1d / 1wk / 1mo) + NSE index CSVs &nbsp;·&nbsp; Cached daily'
            '</div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.download_button(
            "⬇️ Export CSV",
            df.to_csv(index=False).encode(),
            f"nse_screener_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv",
            use_container_width=True,
        )

# ── Tab 2: Fundamental ────────────────────────────────────────────
with tab2:
    exmap = st.session_state.get("exchange_map", {})
    syms  = df["Symbol"].tolist()

    if "fund_data" not in st.session_state:
        # Check if cache already has all symbols
        cached_fund = load_fund_cache()
        if all(s in cached_fund for s in syms):
            st.session_state["fund_data"] = cached_fund
        else:
            missing = len([s for s in syms if s not in cached_fund])
            st.info(f"Fundamental data not loaded. {missing} stocks need fetching (Sales & Profit growth from Yahoo Finance).")
            if st.button("Load Fundamental Data", type="primary", key="load_fund"):
                pb  = st.progress(0, text="Fetching fundamentals…")
                st.session_state["fund_data"] = fetch_fundamentals(syms, exmap, pb)
                pb.empty()
                st.rerun()

    if "fund_data" in st.session_state:
        fund_dict = st.session_state["fund_data"]
        base_df   = df[["Symbol", "Company Name"]].copy()
        fund_df   = merge_fundamentals(base_df, fund_dict)
        fund_df   = fund_df[[c for c in FUND_VIEW_COLS if c in fund_df.columns]]

        st.dataframe(style_fund_df(fund_df), use_container_width=True, height=640)
        st.download_button(
            "⬇️ Export CSV",
            fund_df.to_csv(index=False).encode(),
            f"nse_fundamental_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv",
        )

# ── Tab 3: Watchlist ──────────────────────────────────────────────
with tab3:
    st.markdown(
        '<div style="text-align:center;padding:60px 0;">'
        '<div style="font-size:3rem;margin-bottom:16px;">⭐</div>'
        '<div style="font-size:1.1rem;font-weight:600;color:#d1d4dc;margin-bottom:8px;">Your Watchlist is managed on the Watchlist page</div>'
        '<div style="color:#787b86;font-size:0.85rem;margin-bottom:24px;">Add stocks, view charts, technicals and fundamentals — all in one place.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/4_Watchlist.py", label="Go to Watchlist →", icon="⭐")
