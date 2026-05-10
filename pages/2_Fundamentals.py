import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import os
import threading

_yf_lock = threading.Lock()

st.set_page_config(
    page_title="Fundamentals | NSE Screener",
    page_icon="📊",
    layout="wide",
)

# ── Same TradingView theme ─────────────────────────────────────────
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] {
    background-color: #131722 !important;
    color: #d1d4dc;
    font-family: -apple-system, "Trebuchet MS", sans-serif;
}
[data-testid="stMain"] { background-color: #131722 !important; }
[data-testid="block-container"] { padding-top: 1rem !important; }
[data-testid="stSidebar"] {
    background-color: #1e222d !important;
    border-right: 1px solid #2a2e39 !important;
}
[data-testid="stSidebar"] * { color: #d1d4dc !important; }
[data-testid="stSidebar"] label { color: #787b86 !important; font-size: 0.78rem !important; }
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
header[data-testid="stHeader"] {
    background-color: #131722 !important;
    border-bottom: 1px solid #2a2e39 !important;
    box-shadow: none !important;
}
[data-testid="stToolbarActions"] { visibility: hidden; }
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: #1e222d !important;
    border-radius: 8px;
    padding: 4px;
    gap: 4px;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    background: transparent !important;
    color: #787b86 !important;
    border-radius: 6px !important;
    font-weight: 800 !important;
    font-size: 0.9rem !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
    background: transparent !important;
    color: #d1d4dc !important;
    font-weight: 900 !important;
}
.tv-banner {
    background: linear-gradient(90deg, #1e222d 0%, #131722 100%);
    border: 1px solid #2a2e39;
    border-left: 3px solid #7e57c2;
    border-radius: 8px;
    padding: 18px 28px;
    margin-bottom: 20px;
}
.tv-banner h1 { color: #d1d4dc; font-size: 1.65rem; font-weight: 700; margin: 0 0 3px 0; }
.tv-banner p  { color: #787b86; font-size: 0.82rem; margin: 0; }
.metric-row { display: flex; gap: 10px; margin-bottom: 18px; flex-wrap: wrap; }
.metric-card {
    background: #1e222d; border: 1px solid #2a2e39; border-radius: 6px;
    padding: 12px 18px; flex: 1; min-width: 110px; position: relative; overflow: hidden;
}
.metric-card::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: #2a2e39;
}
.metric-card.bull::before   { background: #26a69a; }
.metric-card.bear::before   { background: #ef5350; }
.metric-card .label {
    color: #787b86; font-size: 0.7rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 6px;
}
.metric-card .val { color: #d1d4dc; font-size: 1.3rem; font-weight: 700; line-height: 1; }
.metric-card .val.bull   { color: #26a69a; }
.metric-card .val.bear   { color: #ef5350; }
.section-label {
    color: #787b86; font-size: 0.7rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 1px;
    border-bottom: 1px solid #2a2e39; padding-bottom: 6px; margin: 20px 0 12px 0;
}
[data-testid="stDataFrame"] { border: 1px solid #2a2e39 !important; border-radius: 6px !important; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #131722; }
::-webkit-scrollbar-thumb { background: #2a2e39; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

# ── Constants ──────────────────────────────────────────────────────
SYMBOL_MAP = {"ZOMATO": "ETERNAL"}
INDEX_URLS = {
    "Nifty 500":    "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
    "Midcap 150":   "https://nsearchives.nseindia.com/content/indices/ind_niftymidcap150list.csv",
    "Smallcap 250": "https://nsearchives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
    "Microcap 250": "https://nsearchives.nseindia.com/content/indices/ind_niftymicrocap250_list.csv",
}
FUND_CACHE  = "/tmp/fund_screener_cache.csv"
PLOTLY_DARK = dict(
    plot_bgcolor  = "#131722",
    paper_bgcolor = "#131722",
    font_color    = "#d1d4dc",
    xaxis = dict(gridcolor="#2a2e39", zerolinecolor="#2a2e39"),
    yaxis = dict(gridcolor="#2a2e39", zerolinecolor="#2a2e39"),
)

# ── Helpers ────────────────────────────────────────────────────────
def cr(val):
    """Format raw value to ₹ Crores string."""
    if pd.isna(val) or val is None:
        return "—"
    c = val / 1e7
    return f"₹{c/100:.1f}K Cr" if c >= 100_000 else f"₹{c:,.0f} Cr"

def pct_str(val, decimals=1):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "—"
    arrow = "▲" if val >= 0 else "▼"
    color = "#26a69a" if val >= 0 else "#ef5350"
    return f'<span style="color:{color};font-weight:700">{arrow} {abs(val):.{decimals}f}%</span>'

def growth(new, old):
    if old and old != 0 and not pd.isna(new) and not pd.isna(old):
        return round((new - old) / abs(old) * 100, 1)
    return None

def get_index_stocks(name):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(INDEX_URLS[name], headers=headers, timeout=10)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text))
        cols = [c for c in ["Symbol", "Company Name", "Industry"] if c in df.columns]
        return df[cols].rename(columns={"Industry": "Sector"})
    except Exception:
        return None

def _qtr_label(dt):
    ts = pd.Timestamp(dt)
    m, y = ts.month, ts.year
    if ts.day <= 5 and m in [1, 4, 7, 10]:
        ts = ts - pd.DateOffset(months=1); m, y = ts.month, ts.year
    if m in [1,2,3]:   q, fy = 4, y
    elif m in [4,5,6]: q, fy = 1, y+1
    elif m in [7,8,9]: q, fy = 2, y+1
    else:               q, fy = 3, y+1
    return f"Q{q} FY{str(fy)[2:]}"

def fetch_info(symbol):
    """Fetch key fundamentals — quarterly revenue + info-based margins/EPS."""
    try:
        ticker = SYMBOL_MAP.get(symbol, symbol)
        with _yf_lock:
            tk    = yf.Ticker(f"{ticker}.NS")
            info  = tk.info
            q_inc = tk.quarterly_income_stmt
            a_inc = tk.income_stmt

        if not info or not info.get("trailingEps"):
            return None

        # Quarterly revenue: latest quarter value + QoQ% + YoY%
        # YoY: try same-quarter comparison (needs 5 quarters); fall back to annual FY vs FY.
        rev_cr = rev_yoy = rev_qoq = latest_qtr = None
        try:
            if q_inc is not None and not q_inc.empty:
                rev_row = next(
                    (r for r in ["Total Revenue", "Net Interest Income"] if r in q_inc.index),
                    None
                )
                if rev_row:
                    rev_q = q_inc.loc[rev_row].dropna().sort_index(ascending=True)
                    rev_q.index = pd.to_datetime(rev_q.index)
                    if len(rev_q) >= 1:
                        latest_val = float(rev_q.iloc[-1])
                        rev_cr     = round(latest_val / 1e7, 0)
                        latest_qtr = _qtr_label(rev_q.index[-1])
                    if len(rev_q) >= 2:
                        prev_val = float(rev_q.iloc[-2])
                        if prev_val != 0:
                            rev_qoq = round((latest_val - prev_val) / abs(prev_val) * 100, 1)
                    # YoY — same quarter prior year (needs 5 quarters)
                    if len(rev_q) >= 5:
                        target_dt = rev_q.index[-1] - pd.DateOffset(years=1)
                        diffs     = (rev_q.index[:-1] - target_dt).abs()
                        ci        = diffs.argmin()
                        if diffs[ci].days <= 60:
                            denom = float(rev_q.iloc[ci])
                            if denom != 0:
                                rev_yoy = round((latest_val - denom) / abs(denom) * 100, 1)
        except Exception:
            pass

        # YoY fallback: annual FY vs FY when quarterly history is too short
        if rev_yoy is None and a_inc is not None and not a_inc.empty:
            try:
                rev_row_a = next(
                    (r for r in ["Total Revenue", "Net Interest Income"] if r in a_inc.index),
                    None
                )
                if rev_row_a:
                    rev_a = a_inc.loc[rev_row_a].dropna().sort_index(ascending=True)
                    if len(rev_a) >= 2:
                        curr, prev = float(rev_a.iloc[-1]), float(rev_a.iloc[-2])
                        if prev != 0:
                            rev_yoy = round((curr - prev) / abs(prev) * 100, 1)
            except Exception:
                pass

        earn_g = info.get("earningsGrowth")
        return {
            "Symbol":       symbol,
            "Market Cap":   info.get("marketCap"),
            "Quarter":      latest_qtr,
            "Rev (Cr)":     rev_cr,
            "Rev YoY%":     rev_yoy,
            "Rev QoQ%":     rev_qoq,
            "EPS Growth%":  round(earn_g * 100, 1) if earn_g is not None else None,
            "Gross Margin": round(info.get("grossMargins", 0) * 100, 1)     if info.get("grossMargins")     else None,
            "Op Margin":    round(info.get("operatingMargins", 0) * 100, 1) if info.get("operatingMargins") else None,
            "Net Margin":   round(info.get("profitMargins", 0) * 100, 1)    if info.get("profitMargins")    else None,
            "EPS (TTM)":    info.get("trailingEps"),
            "PE":           round(info.get("trailingPE"), 1) if info.get("trailingPE") else None,
            "ROE%":         round(info.get("returnOnEquity", 0) * 100, 1)   if info.get("returnOnEquity")   else None,
            "D/E":          round(info.get("debtToEquity"), 1)              if info.get("debtToEquity")     else None,
        }
    except Exception:
        return None

def load_fund_cache():
    if not os.path.exists(FUND_CACHE):
        return None
    try:
        cached = pd.read_csv(FUND_CACHE)
        from datetime import date
        if pd.to_datetime(cached["_date"].iloc[0]).date() == date.today():
            return cached.drop(columns=["_date"])
    except Exception:
        pass
    return None

def save_fund_cache(df):
    from datetime import date
    out = df.copy()
    out["_date"] = date.today().isoformat()
    out.to_csv(FUND_CACHE, index=False)

def get_quarterly(symbol):
    """Return cleaned quarterly income statement DataFrame."""
    try:
        ticker = SYMBOL_MAP.get(symbol, symbol)
        tk     = yf.Ticker(f"{ticker}.NS")
        inc    = tk.quarterly_income_stmt
        if inc is None or inc.empty:
            return None
        inc = inc.sort_index(axis=1, ascending=True)   # oldest → newest
        want = {
            "Total Revenue":    "Revenue",
            "Gross Profit":     "Gross Profit",
            "Operating Income": "Op Income",
            "EBITDA":           "EBITDA",
            "Net Income":       "Net Income",
            "Basic EPS":        "EPS",
        }
        rows = {}
        for src, dst in want.items():
            if src in inc.index:
                rows[dst] = inc.loc[src]
        if "Revenue" not in rows:
            return None
        df = pd.DataFrame(rows)
        def to_quarter(dt):
            ts = pd.Timestamp(dt)
            m, y = ts.month, ts.year
            # yfinance sometimes returns Oct 1 instead of Sep 30, etc.
            # If within first 5 days of a quarter-start month, snap back to prior quarter
            if ts.day <= 5 and m in [1, 4, 7, 10]:
                ts = ts - pd.DateOffset(months=1)
                m, y = ts.month, ts.year
            if m in [1, 2, 3]:    q, fy = 4, y
            elif m in [4, 5, 6]:  q, fy = 1, y + 1
            elif m in [7, 8, 9]:  q, fy = 2, y + 1
            else:                  q, fy = 3, y + 1
            return f"Q{q} FY{str(fy)[2:]}"
        df.index = [to_quarter(c) for c in pd.to_datetime(df.index)]
        return df
    except Exception:
        return None

# ── Banner ─────────────────────────────────────────────────────────
st.markdown("""
<div class="tv-banner">
  <h1>📊 Fundamentals</h1>
  <p>Quarterly Results &nbsp;·&nbsp; Revenue Growth &nbsp;·&nbsp; Margins &nbsp;·&nbsp; EPS Growth</p>
</div>
""", unsafe_allow_html=True)

tab_screen, tab_dive = st.tabs(["Fundamental Screener", "Stock Deep Dive"])

# ══════════════════════════════════════════════════════════════════
# TAB 1 — Fundamental Screener
# ══════════════════════════════════════════════════════════════════
with tab_screen:
    with st.sidebar:
        st.markdown("## 📊 Filters")
        idx_sel  = st.multiselect("Index", list(INDEX_URLS.keys()), default=["Midcap 150"])
        sort_f   = st.selectbox("Sort by", ["Rev YoY%", "Rev QoQ%", "Rev (Cr)", "EPS Growth%", "Net Margin", "Op Margin", "PE", "ROE%"])
        sort_asc = st.radio("Order", ["Descending ↓", "Ascending ↑"], horizontal=True) == "Ascending ↑"
        min_pe, max_pe = st.slider("PE range", 0, 200, (0, 100))
        scan_btn  = st.button("🚀 Scan Fundamentals", type="primary", use_container_width=True)
        clear_btn = st.button("🔄 Clear Cache", use_container_width=True)

    if clear_btn:
        if os.path.exists(FUND_CACHE):
            os.remove(FUND_CACHE)
        st.session_state.pop("fund_data", None)
        st.rerun()

    if scan_btn:
        if not idx_sel:
            st.warning("Select at least one index.")
            st.stop()

        frames = [get_index_stocks(i) for i in idx_sel]
        frames = [f for f in frames if f is not None]
        if not frames:
            st.stop()
        info_df  = pd.concat(frames).drop_duplicates("Symbol").reset_index(drop=True)
        symbols  = info_df["Symbol"].tolist()

        cached = load_fund_cache()
        if cached is not None:
            st.toast(f"Loaded from cache — {len(cached)} stocks.", icon="✅")
            st.session_state["fund_data"] = cached
            st.session_state["fund_info"] = info_df
        else:
            st.info(f"Fetching fundamentals for {len(symbols)} stocks — may take 2–4 min…")
            prog   = st.progress(0)
            status = st.empty()
            results = []

            with ThreadPoolExecutor(max_workers=8) as ex:
                futs = {ex.submit(fetch_info, s): s for s in symbols}
                for i, fut in enumerate(as_completed(futs)):
                    r = fut.result()
                    if r:
                        results.append(r)
                    prog.progress((i + 1) / len(symbols))
                    status.text(f"Fetched {i + 1} / {len(symbols)}…")

            status.empty()
            prog.empty()
            if not results:
                st.error("No data returned.")
                st.stop()

            fdf = pd.DataFrame(results)
            save_fund_cache(fdf)
            st.session_state["fund_data"] = fdf
            st.session_state["fund_info"]  = info_df
            st.toast(f"Done — {len(fdf)} stocks.", icon="✅")

    if "fund_data" not in st.session_state:
        st.markdown("""
        <div style="text-align:center;padding:60px 0;color:#475569;">
          <div style="font-size:2.5rem;margin-bottom:12px;">📊</div>
          <div style="font-size:1rem;font-weight:600;color:#64748b;">Select an index and click Scan Fundamentals</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        raw  = st.session_state["fund_data"]
        info = st.session_state["fund_info"]
        df   = raw.merge(info[["Symbol","Company Name","Sector"]], on="Symbol", how="left")

        # PE filter
        df = df[df["PE"].isna() | df["PE"].between(min_pe, max_pe)]
        df = df.sort_values(sort_f, ascending=sort_asc, na_position="last").reset_index(drop=True)

        # Summary cards
        pos_yoy = int((df["Rev YoY%"] > 0).sum()) if "Rev YoY%" in df.columns else 0
        pos_eps = int((df["EPS Growth%"] > 0).sum())
        avg_nem = df["Net Margin"].mean()
        avg_yoy = df["Rev YoY%"].mean() if "Rev YoY%" in df.columns else None
        # Show which quarter the data is from (most common quarter label)
        qtr_label = df["Quarter"].mode().iloc[0] if "Quarter" in df.columns and df["Quarter"].notna().any() else ""

        def delta_html(val, suffix="%"):
            if val is None or pd.isna(val): return '<span style="color:#787b86">—</span>'
            c = "#26a69a" if val >= 0 else "#ef5350"
            a = "▲" if val >= 0 else "▼"
            return f'<span style="color:{c};font-weight:700">{a} {abs(val):.1f}{suffix}</span>'

        st.markdown(f"""
        <div style="color:#787b86;font-size:0.75rem;margin-bottom:8px;letter-spacing:0.5px;">
          QUARTERLY DATA &nbsp;·&nbsp; Latest Quarter: <strong style="color:#d1d4dc">{qtr_label}</strong>
          &nbsp;·&nbsp; Rev YoY% &amp; QoQ% = same quarter vs prior year / prior quarter
        </div>
        <div class="metric-row">
          <div class="metric-card">
            <div class="label">Stocks</div>
            <div class="val">{len(df)}</div>
          </div>
          <div class="metric-card bull">
            <div class="label">Rev YoY +ve</div>
            <div class="val bull">{pos_yoy}</div>
          </div>
          <div class="metric-card bull">
            <div class="label">EPS Growth +ve</div>
            <div class="val bull">{pos_eps}</div>
          </div>
          <div class="metric-card {'bull' if avg_yoy and avg_yoy>=0 else 'bear'}">
            <div class="label">Avg Rev YoY</div>
            <div class="val" style="font-size:1rem;padding-top:4px;">{delta_html(avg_yoy)}</div>
          </div>
          <div class="metric-card {'bull' if avg_nem and avg_nem>=0 else 'bear'}">
            <div class="label">Avg Net Margin</div>
            <div class="val" style="font-size:1rem;padding-top:4px;">{delta_html(avg_nem)}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        col_order = ["Company Name", "Symbol", "Sector", "Quarter", "Market Cap",
                     "Rev (Cr)", "Rev YoY%", "Rev QoQ%", "EPS Growth%",
                     "Gross Margin", "Op Margin", "Net Margin", "EPS (TTM)", "PE", "ROE%", "D/E"]
        df_disp = df[[c for c in col_order if c in df.columns]]

        def _is_null(v):
            return v is None or (isinstance(v, float) and pd.isna(v))

        def color_growth(val):
            if _is_null(val): return "color: #787b86"
            return f"color: {'#26a69a' if val >= 0 else '#ef5350'}; font-weight:600"

        def color_pe(val):
            if _is_null(val): return "color: #787b86"
            if val < 15:  return "color: #26a69a; font-weight:600"
            if val > 60:  return "color: #ef5350; font-weight:600"
            return "color: #d1d4dc"

        def fmt_pct(v):
            return "—" if _is_null(v) else f"{v:+.1f}%"

        def fmt_1f(v):
            return "—" if _is_null(v) else f"{v:.1f}"

        def fmt_2f(v):
            return "—" if _is_null(v) else f"{v:.2f}"

        def fmt_rev(v):
            return "—" if _is_null(v) else f"₹{v:,.0f} Cr"

        def fmt_mcap(val):
            if _is_null(val): return "—"
            c = val / 1e7
            if c >= 100_000: return f"₹{c/100_000:.1f}L Cr"
            if c >= 1_000:   return f"₹{c/1000:.0f}K Cr"
            return f"₹{c:.0f} Cr"

        pct_cols   = ["Rev YoY%","Rev QoQ%","EPS Growth%","Gross Margin","Op Margin","Net Margin","ROE%"]
        color_cols = ["Rev YoY%","Rev QoQ%","EPS Growth%","Gross Margin","Op Margin","Net Margin","ROE%"]
        fmt_map = {c: fmt_pct for c in pct_cols if c in df_disp.columns}
        fmt_map |= {"PE": fmt_1f, "D/E": fmt_1f, "EPS (TTM)": fmt_2f,
                    "Market Cap": fmt_mcap, "Rev (Cr)": fmt_rev}
        styled = (
            df_disp.style
            .map(color_growth, subset=[c for c in color_cols if c in df_disp.columns])
            .map(color_pe, subset=["PE"] if "PE" in df_disp.columns else [])
            .format({k: v for k, v in fmt_map.items() if k in df_disp.columns})
            .set_properties(**{"background-color":"#1e222d","color":"#d1d4dc","border-color":"#2a2e39"})
        )
        st.dataframe(styled, use_container_width=True, height=620)

        csv = df_disp.to_csv(index=False).encode()
        st.download_button("⬇️ Export CSV", csv,
                           f"fundamentals_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                           "text/csv")

# ══════════════════════════════════════════════════════════════════
# TAB 2 — Stock Deep Dive
# ══════════════════════════════════════════════════════════════════
with tab_dive:
    c1, c2 = st.columns([2, 1])
    with c1:
        symbol_input = st.text_input("Symbol", placeholder="e.g. RELIANCE, HDFCBANK, INFY",
                                     label_visibility="collapsed").strip().upper()
    with c2:
        fetch_btn = st.button("Fetch Quarterly Data", type="primary", use_container_width=True)

    if not symbol_input:
        st.markdown("""
        <div style="text-align:center;padding:60px 0;color:#475569;">
          <div style="font-size:2.5rem;margin-bottom:12px;">🔍</div>
          <div style="font-size:1rem;font-weight:600;color:#64748b;">Enter a symbol above to see quarterly results</div>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    # Fetch only when button pressed or symbol changed
    if fetch_btn or st.session_state.get("dive_symbol") != symbol_input:
        with st.spinner(f"Fetching quarterly data for {symbol_input}…"):
            qdf_raw = get_quarterly(symbol_input)
            ticker_key = SYMBOL_MAP.get(symbol_input, symbol_input)
            try:
                info_raw = yf.Ticker(f"{ticker_key}.NS").info or {}
            except Exception:
                info_raw = {}
        st.session_state["dive_symbol"] = symbol_input
        st.session_state["dive_qdf"]    = qdf_raw
        st.session_state["dive_info"]   = info_raw

    qdf  = st.session_state.get("dive_qdf")
    info = st.session_state.get("dive_info", {})

    if qdf is None or qdf.empty:
        st.error(f"No quarterly data found for **{symbol_input}**. Check the symbol and try again.")
        st.stop()

    # Use last 8 quarters
    qdf = qdf.tail(8)
    quarters = qdf.index.tolist()

    # ── Summary cards ──────────────────────────────────────────
    def safe_val(series, pos):
        try:
            v = series.iloc[pos]
            return None if pd.isna(v) else float(v)
        except Exception:
            return None

    rev  = safe_val(qdf["Revenue"],    -1) if "Revenue"    in qdf.columns else None
    rev1 = safe_val(qdf["Revenue"],    -2) if "Revenue"    in qdf.columns else None
    rev4 = safe_val(qdf["Revenue"],    -5) if len(qdf) >= 5 and "Revenue" in qdf.columns else None
    nim  = safe_val(qdf["Net Income"], -1) if "Net Income" in qdf.columns else None
    eps  = safe_val(qdf["EPS"],        -1) if "EPS"        in qdf.columns else None
    eps1 = safe_val(qdf["EPS"],        -2) if "EPS"        in qdf.columns else None
    eps4 = safe_val(qdf["EPS"],        -5) if len(qdf) >= 5 and "EPS" in qdf.columns else None

    net_margin = round(nim / rev * 100, 1) if rev and nim and rev != 0 else None
    qoq_rev    = growth(rev, rev1)
    yoy_rev    = growth(rev, rev4)
    qoq_eps    = growth(eps, eps1)
    yoy_eps    = growth(eps, eps4)

    def card_delta(val):
        if val is None: return "—"
        c = "#26a69a" if val >= 0 else "#ef5350"
        a = "▲" if val >= 0 else "▼"
        return f'<span style="color:{c};font-weight:700">{a} {abs(val):.1f}%</span>'

    eps_str = f"₹{eps:.2f}" if eps is not None else "—"
    nm_color = "#26a69a" if net_margin and net_margin >= 0 else "#ef5350"
    nm_str   = f"{net_margin:.1f}%" if net_margin is not None else "—"
    company_name = info.get("longName", symbol_input)

    st.markdown(f"""
    <div style="color:#787b86;font-size:0.78rem;margin-bottom:6px;">{company_name}</div>
    <div class="metric-row">
      <div class="metric-card">
        <div class="label">Latest Revenue</div>
        <div class="val" style="font-size:1.05rem;">{cr(rev)}</div>
      </div>
      <div class="metric-card {'bull' if qoq_rev and qoq_rev>=0 else 'bear'}">
        <div class="label">QoQ Revenue</div>
        <div class="val" style="font-size:1rem;padding-top:4px;">{card_delta(qoq_rev)}</div>
      </div>
      <div class="metric-card {'bull' if yoy_rev and yoy_rev>=0 else 'bear'}">
        <div class="label">YoY Revenue</div>
        <div class="val" style="font-size:1rem;padding-top:4px;">{card_delta(yoy_rev)}</div>
      </div>
      <div class="metric-card {'bull' if net_margin and net_margin>=0 else 'bear'}">
        <div class="label">Net Margin</div>
        <div class="val" style="font-size:1rem;padding-top:4px;">
          <span style="color:{nm_color};font-weight:700">{nm_str}</span>
        </div>
      </div>
      <div class="metric-card {'bull' if qoq_eps and qoq_eps>=0 else 'bear'}">
        <div class="label">EPS (latest)</div>
        <div class="val" style="font-size:1rem;padding-top:4px;">
          <span style="color:#d1d4dc;font-weight:700">{eps_str}</span>
        </div>
      </div>
      <div class="metric-card {'bull' if yoy_eps and yoy_eps>=0 else 'bear'}">
        <div class="label">YoY EPS Growth</div>
        <div class="val" style="font-size:1rem;padding-top:4px;">{card_delta(yoy_eps)}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Charts ─────────────────────────────────────────────────
    st.markdown('<div class="section-label">Quarterly Performance</div>', unsafe_allow_html=True)

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=["Revenue (₹ Cr)", "Net Income (₹ Cr)", "EPS (₹)", "Margins (%)"],
        vertical_spacing=0.18, horizontal_spacing=0.1,
    )

    rev_cr = (qdf["Revenue"]    / 1e7).round(0) if "Revenue"    in qdf.columns else None
    ni_cr  = (qdf["Net Income"] / 1e7).round(0) if "Net Income" in qdf.columns else None

    if rev_cr is not None:
        colors = ["#26a69a" if v >= (rev_cr.iloc[i-1] if i > 0 else 0) else "#ef5350"
                  for i, v in enumerate(rev_cr)]
        fig.add_trace(go.Bar(
            x=quarters, y=rev_cr,
            marker_color=colors, name="Revenue",
            text=[f"₹{v:,.0f}" for v in rev_cr],
            textposition="outside", textfont=dict(size=9, color="#787b86"),
        ), row=1, col=1)

    if ni_cr is not None:
        ni_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in ni_cr]
        fig.add_trace(go.Bar(
            x=quarters, y=ni_cr,
            marker_color=ni_colors, name="Net Income",
            text=[f"₹{v:,.0f}" for v in ni_cr],
            textposition="outside", textfont=dict(size=9, color="#787b86"),
        ), row=1, col=2)

    if "EPS" in qdf.columns:
        eps_col = qdf["EPS"].fillna(0)
        eps_colors = ["#26a69a" if v >= (eps_col.iloc[i-1] if i > 0 else 0) else "#ef5350"
                      for i, v in enumerate(eps_col)]
        fig.add_trace(go.Bar(
            x=quarters, y=eps_col,
            marker_color=eps_colors, name="EPS",
            text=[f"₹{v:.2f}" for v in eps_col],
            textposition="outside", textfont=dict(size=9, color="#787b86"),
        ), row=2, col=1)

    if "Revenue" in qdf.columns:
        rev_s = qdf["Revenue"].replace(0, float("nan"))
        if "Gross Profit" in qdf.columns:
            gm = (qdf["Gross Profit"] / rev_s * 100).round(1)
            fig.add_trace(go.Scatter(x=quarters, y=gm, name="Gross Margin",
                line=dict(color="#26a69a", width=2), mode="lines+markers"), row=2, col=2)
        if "Op Income" in qdf.columns:
            om = (qdf["Op Income"] / rev_s * 100).round(1)
            fig.add_trace(go.Scatter(x=quarters, y=om, name="Op Margin",
                line=dict(color="#f7931a", width=2), mode="lines+markers"), row=2, col=2)
        if "Net Income" in qdf.columns:
            nm = (qdf["Net Income"] / rev_s * 100).round(1)
            fig.add_trace(go.Scatter(x=quarters, y=nm, name="Net Margin",
                line=dict(color="#26a69a", width=2), mode="lines+markers"), row=2, col=2)

    fig.update_layout(
        height=560, showlegend=True,
        legend=dict(orientation="h", y=-0.1, font=dict(size=11, color="#787b86"),
                    bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=40, b=20, l=10, r=10),
        **PLOTLY_DARK,
    )
    for ann in fig.layout.annotations:
        ann.font.color = "#787b86"
        ann.font.size  = 12
    fig.update_xaxes(tickfont=dict(size=9, color="#787b86"), tickangle=-30)
    fig.update_yaxes(tickfont=dict(size=10, color="#787b86"))
    st.plotly_chart(fig, use_container_width=True)

    # ── Quarterly table ────────────────────────────────────────
    st.markdown('<div class="section-label">Quarterly Results Table (₹ Crores)</div>',
                unsafe_allow_html=True)

    tbl = qdf.copy()
    for col in ["Revenue", "Gross Profit", "Op Income", "EBITDA", "Net Income"]:
        if col in tbl.columns:
            tbl[col] = (tbl[col] / 1e7).round(0)

    growth_rows = {}
    for col in ["Revenue", "Net Income", "EPS"]:
        if col in tbl.columns:
            growth_rows[f"{col} QoQ%"] = tbl[col].pct_change().mul(100).round(1)
            growth_rows[f"{col} YoY%"] = tbl[col].pct_change(4).mul(100).round(1)

    tbl_T = tbl.T
    if growth_rows:
        extra = pd.DataFrame(growth_rows).T
        extra.columns = tbl.index
        tbl_T = pd.concat([tbl_T, extra])

    growth_idx = [i for i in tbl_T.index if "%" in str(i)]
    plain_idx  = [i for i in tbl_T.index if "%" not in str(i)]

    def color_tbl(val):
        try:
            v = float(val)
            if not pd.isna(v):
                if v > 0: return "color: #26a69a; font-weight:600"
                if v < 0: return "color: #ef5350; font-weight:600"
        except Exception:
            pass
        return "color: #d1d4dc"

    def fmt_growth(val):
        try:
            v = float(val)
            return f"{v:+.1f}%" if not pd.isna(v) else "—"
        except Exception:
            return "—"

    def fmt_plain(val):
        try:
            v = float(val)
            return f"{v:,.0f}" if not pd.isna(v) else "—"
        except Exception:
            return str(val) if val is not None else "—"

    styled_tbl = tbl_T.style.set_properties(
        **{"background-color": "#1e222d", "color": "#d1d4dc", "border-color": "#2a2e39"}
    )
    if growth_idx:
        styled_tbl = (
            styled_tbl
            .map(color_tbl, subset=pd.IndexSlice[growth_idx, :])
            .format(fmt_growth, subset=pd.IndexSlice[growth_idx, :])
        )
    if plain_idx:
        styled_tbl = styled_tbl.format(fmt_plain, subset=pd.IndexSlice[plain_idx, :])

    st.dataframe(styled_tbl, use_container_width=True)
