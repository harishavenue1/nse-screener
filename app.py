import os
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
    total  = len(symbols)
    chunks = [symbols[i:i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
    done   = 0

    for chunk in chunks:
        tickers = [f"{SYMBOL_MAP.get(s, s)}.NS" for s in chunk]

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
        options=list(INDEX_URLS.keys()),
        default=["Midcap 150", "Smallcap 250"],
        label_visibility="collapsed",
    )

    st.markdown('<div class="section-label">Filters</div>', unsafe_allow_html=True)
    rsi_min, rsi_max = st.slider("Daily RSI", 0, 100, (0, 100))
    change_min, change_max = st.slider("Day Change %", -30, 30, (-30, 30))
    only_3w = st.checkbox("3 consecutive green weekly bars")

    st.markdown('<div class="section-label">Search</div>', unsafe_allow_html=True)
    search = st.text_input("Symbol or company", placeholder="e.g. RELIANCE", label_visibility="collapsed").strip().lower()

    st.markdown('<div class="section-label">Sort</div>', unsafe_allow_html=True)
    sort_col = st.selectbox(
        "Sort by", label_visibility="collapsed",
        options=["Monthly%", "Yearly%", "Weekly%", "Change%", "RSI(D)", "RSI(W)", "RSI(M)"],
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
        st.toast(f"Loaded from today's cache — {len(cached)} stocks.", icon="✅")
        st.session_state["data"] = cached
        st.session_state["info"] = info_df
    else:
        symbols = info_df["Symbol"].tolist()
        progress = st.progress(0, text=f"Scanning {len(symbols)} stocks…")
        status   = st.empty()

        results = scan_symbols(symbols, progress, status)

        status.empty()
        progress.empty()

        if not results:
            st.error("No results returned. Check your connection and try again.")
            st.stop()

        data_df = pd.DataFrame(results)
        save_cache(data_df)
        st.session_state["data"] = data_df
        st.session_state["info"] = info_df
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
             "Change%", "Weekly%", "Monthly%", "Yearly%",
             "RSI(D)", "RSI(W)", "RSI(M)", "3W Green"]
df = df[[c for c in col_order if c in df.columns]]

# ── Summary metric cards ──────────────────────────────────────────
gainers    = int((df["Change%"] > 0).sum()) if "Change%" in df.columns else 0
losers     = int((df["Change%"] < 0).sum()) if "Change%" in df.columns else 0
green3w    = int(df["3W Green"].sum())       if "3W Green" in df.columns else 0
overbought = int((df["RSI(D)"] >= 70).sum()) if "RSI(D)" in df.columns else 0
oversold   = int((df["RSI(D)"] <= 30).sum()) if "RSI(D)" in df.columns else 0

avg_chg    = df["Change%"].mean()  if "Change%" in df.columns else None
avg_mo     = df["Monthly%"].mean() if "Monthly%" in df.columns else None

def delta_html(val, size="1rem"):
    """Return a coloured ▲/▼ percentage string."""
    if val is None or pd.isna(val):
        return '<span style="color:#787b86">—</span>'
    arrow = "▲" if val >= 0 else "▼"
    color = "#26a69a" if val >= 0 else "#ef5350"
    return f'<span style="color:{color};font-size:{size};font-weight:700">{arrow} {abs(val):.2f}%</span>'

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

# ── Table ─────────────────────────────────────────────────────────
pct_cols = ["Change%", "Weekly%", "Monthly%", "Yearly%"]
rsi_cols = ["RSI(D)", "RSI(W)", "RSI(M)"]

styled = (
    df.style
    .map(color_pct, subset=[c for c in pct_cols if c in df.columns])
    .map(rsi_color, subset=[c for c in rsi_cols if c in df.columns])
    .format(
        {c: lambda v: f"▲ {v:.2f}%" if not pd.isna(v) and v >= 0 else (f"▼ {abs(v):.2f}%" if not pd.isna(v) else "—")
         for c in pct_cols if c in df.columns}
        | {c: "{:.1f}" for c in rsi_cols if c in df.columns}
        | {"Price": "₹{:.2f}"}
    )
    .set_properties(**{"background-color": "#1e222d", "color": "#d1d4dc", "border-color": "#2a2e39"})
)

st.dataframe(styled, use_container_width=True, height=640)

# ── Footer ────────────────────────────────────────────────────────
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown(
        '<div style="color:#2a2e39;font-size:0.75rem;padding-top:8px;">'
        'Data: Yahoo Finance (1d / 1wk / 1mo) + NSE index CSVs &nbsp;·&nbsp; Cached daily'
        '</div>',
        unsafe_allow_html=True,
    )
with col2:
    csv = df.to_csv(index=False).encode()
    st.download_button(
        "⬇️ Export CSV",
        csv,
        f"nse_screener_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        "text/csv",
        use_container_width=True,
    )
