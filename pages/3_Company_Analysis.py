import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from datetime import datetime

st.set_page_config(
    page_title="Company Analysis | NSE Screener",
    page_icon="🏢",
    layout="wide",
)

# ── TradingView theme ──────────────────────────────────────────────
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
#MainMenu { visibility: hidden; } footer { visibility: hidden; }
header[data-testid="stHeader"] {
    background-color: #131722 !important;
    border-bottom: 1px solid #2a2e39 !important; box-shadow: none !important;
}
[data-testid="stToolbarActions"] { visibility: hidden; }
.tv-banner {
    background: linear-gradient(90deg, #1e222d 0%, #131722 100%);
    border: 1px solid #2a2e39; border-left: 3px solid #26a69a;
    border-radius: 8px; padding: 18px 28px; margin-bottom: 20px;
}
.tv-banner h1 { color: #d1d4dc; font-size: 1.65rem; font-weight: 700; margin: 0 0 3px 0; }
.tv-banner p  { color: #787b86; font-size: 0.82rem; margin: 0; }
.metric-row   { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.metric-card  {
    background: #1e222d; border: 1px solid #2a2e39; border-radius: 6px;
    padding: 12px 18px; flex: 1; min-width: 100px; position: relative; overflow: hidden;
}
.metric-card::before { content:""; position:absolute; top:0; left:0; right:0; height:2px; background:#2a2e39; }
.metric-card.bull::before { background: #26a69a; }
.metric-card.bear::before { background: #ef5350; }
.metric-card.gold::before { background: #f59e0b; }
.metric-card .label { color:#787b86; font-size:0.7rem; font-weight:600; text-transform:uppercase; letter-spacing:0.6px; margin-bottom:5px; }
.metric-card .val   { color:#d1d4dc; font-size:1.2rem; font-weight:700; line-height:1.1; }
.metric-card .val.bull { color:#26a69a; }
.metric-card .val.bear { color:#ef5350; }
.metric-card .val.gold { color:#f59e0b; }
.section-label {
    color:#787b86; font-size:0.7rem; font-weight:700; text-transform:uppercase; letter-spacing:1px;
    border-bottom: 1px solid #2a2e39; padding-bottom:6px; margin:22px 0 14px 0;
}
.ann-card {
    background:#1e222d; border:1px solid #2a2e39; border-left:3px solid #26a69a;
    border-radius:6px; padding:12px 16px; margin-bottom:8px;
}
.ann-card .ann-title { color:#d1d4dc; font-size:0.88rem; font-weight:600; margin-bottom:4px; }
.ann-card .ann-meta  { color:#787b86; font-size:0.75rem; }
.ann-card.order      { border-left-color:#f59e0b; }
.ann-card.guidance   { border-left-color:#7e57c2; }
.order-row { display:flex; gap:10px; margin-bottom:16px; flex-wrap:wrap; }
.order-box {
    background:#1e222d; border:1px solid #2a2e39; border-radius:6px;
    padding:14px 18px; flex:1; min-width:130px;
}
.order-box .ob-label { color:#787b86; font-size:0.7rem; font-weight:700; text-transform:uppercase; letter-spacing:0.6px; margin-bottom:6px; }
.order-box .ob-val   { color:#d1d4dc; font-size:1.1rem; font-weight:700; }
.order-box .ob-note  { color:#787b86; font-size:0.7rem; margin-top:3px; }
[data-testid="stDataFrame"] { border:1px solid #2a2e39 !important; border-radius:6px !important; }
::-webkit-scrollbar { width:6px; height:6px; }
::-webkit-scrollbar-track { background:#131722; }
::-webkit-scrollbar-thumb { background:#2a2e39; border-radius:3px; }
</style>
""", unsafe_allow_html=True)

PLOTLY_DARK = dict(
    plot_bgcolor="#131722", paper_bgcolor="#131722", font_color="#d1d4dc",
    xaxis=dict(gridcolor="#2a2e39", zerolinecolor="#2a2e39"),
    yaxis=dict(gridcolor="#2a2e39", zerolinecolor="#2a2e39"),
)
NSE_EQUITIES_URL  = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
NSE_SME_INDEX_URL = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY+SME+EMERGE"
YF_SEARCH_URL     = "https://query1.finance.yahoo.com/v1/finance/search?q={q}&quotesCount=8&newsCount=0"
YF_SEARCH_HDRS    = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
# Indian exchange codes returned by Yahoo Finance search
_INDIA_EXCHANGES  = {"NSI", "NMS", "BSE", "NSE", "NS", "BO", "NSE_EQ"}

# ── Symbol map (NSE main board) ───────────────────────────────────
@st.cache_data(ttl=86400, show_spinner=False)
def load_symbol_map():
    try:
        r = requests.get(NSE_EQUITIES_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text))
        df.columns = df.columns.str.strip()
        return df[["SYMBOL", "NAME OF COMPANY"]].rename(
            columns={"SYMBOL": "Symbol", "NAME OF COMPANY": "Company Name"}
        )
    except Exception:
        return pd.DataFrame(columns=["Symbol", "Company Name"])

def _yf_ticker_from_yahoo(raw_sym: str) -> str:
    """Convert Yahoo Finance search symbol to a yfinance-compatible ticker.
    'AIMTRON-SM.NS' → 'AIMTRON.NS'
    'YASHHV.BO'     → 'YASHHV.BO'
    'CNCRD.BO'      → 'CNCRD.BO'
    'DSSL.NS'       → 'DSSL.NS'
    """
    upper = raw_sym.upper()
    # Strip exchange suffix first, then clean sub-type (e.g. -SM)
    base = raw_sym.replace(".BO","").replace(".NS","").replace(".ns","").replace(".bo","")
    base = base.split("-")[0]   # remove -SM, -BE, -ST etc.
    if ".BO" in upper:
        return base + ".BO"
    return base + ".NS"

def _yahoo_search(query: str):
    """Search Yahoo Finance for Indian exchange companies.
    Returns list of {ticker, name} dicts or empty list.
    """
    try:
        url = YF_SEARCH_URL.format(q=requests.utils.quote(query))
        r = requests.get(url, headers=YF_SEARCH_HDRS, timeout=6)
        quotes = r.json().get("quotes", [])
        results = []
        for qt in quotes:
            exch = qt.get("exchange", "")
            if any(x in exch for x in _INDIA_EXCHANGES):
                raw = qt.get("symbol", "")
                name = qt.get("longname") or qt.get("shortname", "")
                if raw and name:
                    results.append({"ticker": _yf_ticker_from_yahoo(raw), "name": name})
        return results
    except Exception:
        return []

def find_symbol(query: str, sym_map: pd.DataFrame):
    """Return (ticker, name) or (matches_df, None) for ambiguous results.
    ticker includes exchange suffix: 'DSSL.NS' or 'YASHHV.BO'
    """
    q = query.strip()

    # 1 ── Exact symbol match in NSE main board CSV
    exact = sym_map[sym_map["Symbol"].str.upper() == q.upper()]
    if not exact.empty:
        return exact.iloc[0]["Symbol"] + ".NS", exact.iloc[0]["Company Name"]

    # 2 ── Partial company name match in NSE main board CSV
    mask = sym_map["Company Name"].str.contains(q, case=False, na=False, regex=False)
    hits = sym_map[mask].reset_index(drop=True)
    if len(hits) == 1:
        return hits.iloc[0]["Symbol"] + ".NS", hits.iloc[0]["Company Name"]
    if len(hits) > 1:
        df = hits[["Symbol", "Company Name"]].copy()
        df["Symbol"] = df["Symbol"] + ".NS"
        return df, None

    # 3 ── Yahoo Finance search (NSE SME + BSE + anything missed above)
    yf_results = _yahoo_search(q)
    if len(yf_results) == 1:
        return yf_results[0]["ticker"], yf_results[0]["name"]
    if len(yf_results) > 1:
        df = pd.DataFrame(yf_results).rename(columns={"ticker": "Symbol", "name": "Company Name"})
        return df, None

    # 4 ── Direct yfinance probe (.NS then .BO)
    for suffix in [".NS", ".BO"]:
        try:
            tk = yf.Ticker(f"{q.upper()}{suffix}")
            name = (tk.info or {}).get("longName", "")
            if name:
                return f"{q.upper()}{suffix}", name
        except Exception:
            pass

    return None, None

# ── Data fetching ──────────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_company(ticker: str):
    """ticker is the full yfinance ticker e.g. 'DSSL.NS' or 'YASHHV.BO'."""
    tk = yf.Ticker(ticker)
    info  = tk.info or {}
    q_inc = tk.quarterly_income_stmt
    a_inc = tk.income_stmt
    news  = tk.news or []
    return info, q_inc, a_inc, news

@st.cache_data(ttl=3600, show_spinner=False)
def get_nse_announcements(base_symbol: str, max_items: int = 10):
    """base_symbol = symbol without exchange suffix, e.g. 'DSSL'."""
    try:
        s = requests.Session()
        hdrs = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://www.nseindia.com/",
        }
        s.get("https://www.nseindia.com/", headers=hdrs, timeout=8)
        url = f"https://www.nseindia.com/api/corp-announcements?index=equities&symbol={base_symbol}"
        r = s.get(url, headers=hdrs, timeout=8)
        data = r.json()
        return data[:max_items] if isinstance(data, list) else []
    except Exception:
        return []

# ── Helpers ────────────────────────────────────────────────────────
def cr(val):
    if val is None or (isinstance(val, float) and pd.isna(val)): return "—"
    c = val / 1e7
    if c >= 100_000: return f"₹{c/100_000:.1f}L Cr"
    if c >= 1_000:   return f"₹{c/1000:.1f}K Cr"
    return f"₹{c:,.0f} Cr"

def to_qtr(dt):
    ts = pd.Timestamp(dt); m, y = ts.month, ts.year
    if ts.day <= 5 and m in [1, 4, 7, 10]:
        ts -= pd.DateOffset(months=1); m, y = ts.month, ts.year
    if m in [1,2,3]:    q, fy = 4, y
    elif m in [4,5,6]:  q, fy = 1, y + 1
    elif m in [7,8,9]:  q, fy = 2, y + 1
    else:                q, fy = 3, y + 1
    return f"Q{q} FY{str(fy)[2:]}"

ORDER_KEYWORDS    = ["order", "contract", "award", "win", "l1", "bid", "bagged", "secured", "letter of intent"]
GUIDANCE_KEYWORDS = ["guidance", "outlook", "target", "capacity", "expansion", "growth plan",
                     "commissioning", "revenue target", "fy2", "guidance"]

def classify_ann(text: str):
    t = text.lower()
    if any(k in t for k in ORDER_KEYWORDS):    return "order"
    if any(k in t for k in GUIDANCE_KEYWORDS): return "guidance"
    return "general"

# ── Banner ─────────────────────────────────────────────────────────
st.markdown("""
<div class="tv-banner">
  <h1>🏢 Company Analysis</h1>
  <p>Order Book &nbsp;·&nbsp; Revenue Trend &nbsp;·&nbsp; Capacity &nbsp;·&nbsp; Management Guidance</p>
</div>
""", unsafe_allow_html=True)

# ── Search ─────────────────────────────────────────────────────────
c1, c2 = st.columns([4, 1])
with c1:
    query = st.text_input(
        "Company", placeholder="e.g. Dynacons Systems, Yash Highvoltage, AIMTRON, SUPREMEPWR",
        label_visibility="collapsed",
    ).strip()
with c2:
    go_btn = st.button("🔍 Analyse", type="primary", use_container_width=True)

if not query:
    st.markdown("""
    <div style="text-align:center;padding:60px 0;color:#475569;">
      <div style="font-size:2.5rem;margin-bottom:12px;">🏢</div>
      <div style="font-size:1rem;font-weight:600;color:#64748b;">Enter a company name or NSE symbol above</div>
      <div style="font-size:0.82rem;color:#475569;margin-top:6px;">NSE main board, NSE SME Emerge &amp; BSE — e.g. DSSL, YASHHV, AIMTRON, SUPREMEPWR</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Symbol resolution ──────────────────────────────────────────────
if go_btn or st.session_state.get("ca_query") != query:
    st.session_state["ca_query"] = query
    st.session_state.pop("ca_ticker", None)
    st.session_state.pop("ca_matches", None)

with st.spinner("Looking up symbol…"):
    sym_map = load_symbol_map()

if "ca_ticker" not in st.session_state:
    result, name = find_symbol(query, sym_map)
    if result is None:
        st.error(
            f"Could not find **{query}** on NSE or BSE. "
            "Try the exact symbol (e.g. YASHHV, SUPREMEPWR, AIMTRON)."
        )
        st.stop()
    if isinstance(result, pd.DataFrame):
        st.session_state["ca_matches"] = result
    else:
        st.session_state["ca_ticker"] = result       # full ticker e.g. 'DSSL.NS' / 'YASHHV.BO'
        st.session_state["ca_name"]   = name

if "ca_matches" in st.session_state:
    matches = st.session_state["ca_matches"]
    st.warning(f"Found {len(matches)} companies matching **{query}**. Select one:")
    sel = st.selectbox(
        "Choose company", matches["Company Name"].tolist(), label_visibility="collapsed"
    )
    if st.button("Confirm", type="primary"):
        row = matches[matches["Company Name"] == sel].iloc[0]
        st.session_state["ca_ticker"] = row["Symbol"]   # already has suffix
        st.session_state["ca_name"]   = row["Company Name"]
        del st.session_state["ca_matches"]
        st.rerun()
    st.stop()

ticker = st.session_state["ca_ticker"]                  # full yfinance ticker
symbol = ticker.split(".")[0]                           # base symbol for display / NSE API

# ── Fetch data ─────────────────────────────────────────────────────
with st.spinner(f"Fetching data for {symbol}…"):
    info, q_inc, a_inc, news = fetch_company(ticker)
    announcements = get_nse_announcements(symbol)

if not info or not (info.get("regularMarketPrice") or info.get("currentPrice")):
    st.error(f"Could not fetch data for **{symbol}**. Verify the symbol is correct.")
    st.stop()

# longName is None for some NSE SME stocks — fall back through shortName → symbol
_raw_short = info.get("shortName", "") or ""
_short_clean = _raw_short.split(",")[0].strip()          # strip garbage like "AIMTRON.NS,0P0001..."
company_name = info.get("longName") or (_short_clean if _short_clean and "." not in _short_clean else None) or symbol
sector       = info.get("sector", "—")
industry     = info.get("industry", "—")
price        = info.get("currentPrice") or info.get("regularMarketPrice")
chg_pct      = info.get("regularMarketChangePercent", 0) or 0
mcap         = info.get("marketCap")
w52_high     = info.get("fiftyTwoWeekHigh")
w52_low      = info.get("fiftyTwoWeekLow")

# ── Company header ─────────────────────────────────────────────────
chg_color = "#26a69a" if chg_pct >= 0 else "#ef5350"
chg_arrow = "▲" if chg_pct >= 0 else "▼"
price_str = f"₹{price:,.2f}" if price else "—"
chg_str   = f"{chg_arrow} {abs(chg_pct):.2f}%"

st.markdown(f"""
<div style="display:flex;align-items:baseline;gap:16px;margin-bottom:4px;flex-wrap:wrap;">
  <span style="color:#d1d4dc;font-size:1.5rem;font-weight:800;">{company_name}</span>
  <span style="color:#787b86;font-size:0.85rem;background:#1e222d;padding:2px 10px;border-radius:12px;border:1px solid #2a2e39;">{symbol} · NSE</span>
  <span style="color:#787b86;font-size:0.82rem;">{sector} — {industry}</span>
</div>
<div style="display:flex;align-items:baseline;gap:14px;margin-bottom:18px;flex-wrap:wrap;">
  <span style="color:#d1d4dc;font-size:1.8rem;font-weight:700;">{price_str}</span>
  <span style="color:{chg_color};font-size:1rem;font-weight:700;">{chg_str}</span>
  <span style="color:#787b86;font-size:0.8rem;">52W: {'₹{:,.0f} – ₹{:,.0f}'.format(w52_low, w52_high) if w52_low and w52_high else '—'}</span>
</div>
""", unsafe_allow_html=True)

# ── Snapshot metric cards ──────────────────────────────────────────
pe    = info.get("trailingPE")
pb    = info.get("priceToBook")
roe   = info.get("returnOnEquity")
de    = info.get("debtToEquity")
eps   = info.get("trailingEps")
div_y = info.get("dividendYield")

def _f(v, fmt=".1f", suffix=""):
    return f"{v:{fmt}}{suffix}" if v is not None and not (isinstance(v, float) and pd.isna(v)) else "—"

st.markdown(f"""
<div class="metric-row">
  <div class="metric-card">
    <div class="label">Market Cap</div>
    <div class="val">{cr(mcap)}</div>
  </div>
  <div class="metric-card {'bull' if pe and pe < 30 else 'bear' if pe and pe > 60 else ''}">
    <div class="label">P/E (TTM)</div>
    <div class="val">{_f(pe)}</div>
  </div>
  <div class="metric-card">
    <div class="label">P/B</div>
    <div class="val">{_f(pb)}</div>
  </div>
  <div class="metric-card {'bull' if roe and roe*100 >= 15 else ''}">
    <div class="label">ROE</div>
    <div class="val {'bull' if roe and roe*100 >= 15 else ''}">{_f(roe*100 if roe else None)}{'%' if roe else ''}</div>
  </div>
  <div class="metric-card {'bear' if de and de > 1 else 'bull' if de is not None else ''}">
    <div class="label">Debt / Equity</div>
    <div class="val {'bear' if de and de > 1 else 'bull' if de is not None else ''}">{_f(de)}</div>
  </div>
  <div class="metric-card">
    <div class="label">EPS (TTM)</div>
    <div class="val">₹{_f(eps, '.2f')}</div>
  </div>
  <div class="metric-card {'bull' if div_y else ''}">
    <div class="label">Div Yield</div>
    <div class="val">{_f(div_y*100 if div_y else None, '.2f')}{'%' if div_y else '—' if div_y is None else ''}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Quarterly financial chart ─────────────────────────────────────
st.markdown('<div class="section-label">Quarterly Financial Performance</div>', unsafe_allow_html=True)

if q_inc is not None and not q_inc.empty:
    rev_row = next((r for r in ["Total Revenue", "Net Interest Income"] if r in q_inc.index), None)
    q_sorted = q_inc.sort_index(axis=1, ascending=True)

    def qseries(row_name):
        if row_name in q_sorted.index:
            s = q_sorted.loc[row_name].dropna()
            s.index = [to_qtr(c) for c in pd.to_datetime(s.index)]
            return s.tail(8)
        return None

    rev_s  = qseries(rev_row) if rev_row else None
    ni_s   = qseries("Net Income")
    eps_s  = qseries("Basic EPS")
    gp_s   = qseries("Gross Profit")
    oi_s   = qseries("Operating Income")

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=["Revenue (₹ Cr)", "Net Income (₹ Cr)", "EPS (₹)", "Margins (%)"],
        vertical_spacing=0.18, horizontal_spacing=0.12,
    )

    def bar_colors(s):
        return ["#26a69a" if v >= (list(s)[i-1] if i > 0 else 0) else "#ef5350"
                for i, v in enumerate(s)]

    if rev_s is not None:
        rev_cr = (rev_s / 1e7).round(1)
        fig.add_trace(go.Bar(x=rev_cr.index, y=rev_cr, name="Revenue",
            marker_color=bar_colors(rev_cr),
            text=[f"₹{v:,.0f}" for v in rev_cr],
            textposition="outside", textfont=dict(size=9, color="#787b86"),
        ), row=1, col=1)

    if ni_s is not None:
        ni_cr = (ni_s / 1e7).round(1)
        fig.add_trace(go.Bar(x=ni_cr.index, y=ni_cr, name="Net Income",
            marker_color=["#26a69a" if v >= 0 else "#ef5350" for v in ni_cr],
            text=[f"₹{v:,.0f}" for v in ni_cr],
            textposition="outside", textfont=dict(size=9, color="#787b86"),
        ), row=1, col=2)

    if eps_s is not None:
        fig.add_trace(go.Bar(x=eps_s.index, y=eps_s, name="EPS",
            marker_color=bar_colors(eps_s),
            text=[f"₹{v:.2f}" for v in eps_s],
            textposition="outside", textfont=dict(size=9, color="#787b86"),
        ), row=2, col=1)

    if rev_s is not None:
        rev_nz = rev_s.replace(0, float("nan"))
        if gp_s is not None:
            gm = (gp_s / rev_nz * 100).round(1)
            fig.add_trace(go.Scatter(x=gm.index, y=gm, name="Gross Margin",
                line=dict(color="#26a69a", width=2), mode="lines+markers"), row=2, col=2)
        if oi_s is not None:
            om = (oi_s / rev_nz * 100).round(1)
            fig.add_trace(go.Scatter(x=om.index, y=om, name="Op Margin",
                line=dict(color="#f59e0b", width=2), mode="lines+markers"), row=2, col=2)
        if ni_s is not None:
            nm = (ni_s / rev_nz * 100).round(1)
            fig.add_trace(go.Scatter(x=nm.index, y=nm, name="Net Margin",
                line=dict(color="#7e57c2", width=2), mode="lines+markers"), row=2, col=2)

    fig.update_layout(
        height=520, showlegend=True,
        legend=dict(orientation="h", y=-0.12, font=dict(size=11, color="#787b86"), bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=40, b=20, l=10, r=10), **PLOTLY_DARK,
    )
    for ann in fig.layout.annotations:
        ann.font.color = "#787b86"; ann.font.size = 12
    fig.update_xaxes(tickfont=dict(size=9, color="#787b86"), tickangle=-30)
    fig.update_yaxes(tickfont=dict(size=10, color="#787b86"))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No quarterly income data available for this company.")

# ── Revenue growth summary ─────────────────────────────────────────
if rev_s is not None and len(rev_s) >= 2:
    rev_cr = (rev_s / 1e7).round(1)
    latest_q   = rev_cr.index[-1]
    latest_rev = rev_cr.iloc[-1]
    qoq = ((rev_cr.iloc[-1] - rev_cr.iloc[-2]) / abs(rev_cr.iloc[-2]) * 100) if rev_cr.iloc[-2] != 0 else None
    yoy = None
    if len(rev_cr) >= 5:
        # Same quarter 4 quarters ago (positional)
        denom = float(rev_cr.iloc[-5])
        if denom != 0:
            yoy = round((float(rev_cr.iloc[-1]) - denom) / abs(denom) * 100, 1)

    cqoq = "#26a69a" if qoq and qoq >= 0 else "#ef5350"
    cyoy = "#26a69a" if yoy and yoy >= 0 else "#ef5350"
    st.markdown(f"""
    <div class="order-row">
      <div class="order-box">
        <div class="ob-label">Latest Quarter</div>
        <div class="ob-val">{latest_q}</div>
        <div class="ob-note">Most recent reporting period</div>
      </div>
      <div class="order-box">
        <div class="ob-label">Revenue ({latest_q})</div>
        <div class="ob-val">₹{latest_rev:,.0f} Cr</div>
        <div class="ob-note">Quarterly revenue</div>
      </div>
      <div class="order-box">
        <div class="ob-label">QoQ Growth</div>
        <div class="ob-val" style="color:{cqoq}">{'▲' if qoq and qoq>=0 else '▼'} {abs(qoq):.1f}%</div>
        <div class="ob-note">vs previous quarter</div>
      </div>
      <div class="order-box">
        <div class="ob-label">YoY Growth</div>
        <div class="ob-val" style="color:{cyoy if yoy is not None else '#787b86'}">
          {'▲' if yoy and yoy>=0 else ('▼' if yoy else '—')}{f' {abs(yoy):.1f}%' if yoy else ''}</div>
        <div class="ob-note">vs same quarter last year</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── Fetch balance sheet for order book & capacity metrics ─────────
q_bal = yf.Ticker(ticker).quarterly_balance_sheet if ticker else None

def bs_val(bs, row):
    """Safely get latest quarter value from balance sheet."""
    try:
        if bs is not None and row in bs.index:
            v = bs.sort_index(axis=1, ascending=True).loc[row].dropna()
            return float(v.iloc[-1]) if len(v) else None
    except Exception:
        return None
    return None

ar        = bs_val(q_bal, "Accounts Receivable")
inventory = bs_val(q_bal, "Inventory")
total_assets = bs_val(q_bal, "Total Assets")
net_ppe   = bs_val(q_bal, "Net PPE")
total_debt = bs_val(q_bal, "Total Debt")

# TTM revenue (sum of last 4 quarters)
ttm_rev = None
if rev_s is not None and len(rev_s) >= 4:
    ttm_rev = float(rev_s.iloc[-4:].sum())
elif rev_s is not None and len(rev_s) > 0:
    ttm_rev = float(rev_s.sum())

latest_q_rev = float(rev_s.iloc[-1]) if rev_s is not None and len(rev_s) > 0 else None

# ── Order Book Summary ────────────────────────────────────────────
st.markdown('<div class="section-label">Order Book Summary</div>', unsafe_allow_html=True)

# Billed Pipeline = Accounts Receivable (work done, awaiting payment)
# WIP / Stock     = Inventory (goods in production / finished stock)
# Pipeline Proxy  = AR + Inventory (total active order value on books)
pipeline = (ar or 0) + (inventory or 0)
# Completed %     = Revenue delivered vs total pipeline
# (what % of the pipeline has been converted to revenue this quarter)
completed_pct = (latest_q_rev / pipeline * 100) if pipeline and latest_q_rev else None
pending_cr    = pipeline / 1e7 if pipeline else None
ar_cr         = ar / 1e7 if ar else None
inv_cr        = inventory / 1e7 if inventory else None
dso           = (ar / (ttm_rev / 4) * 90) if ar and ttm_rev else None   # Days Sales Outstanding
ttm_cr        = ttm_rev / 1e7 if ttm_rev else None

col1, col2, col3, col4 = st.columns(4)

def ob_box(col, label, val_html, note="", color="#d1d4dc"):
    col.markdown(f"""
    <div class="order-box">
      <div class="ob-label">{label}</div>
      <div class="ob-val" style="color:{color}">{val_html}</div>
      <div class="ob-note">{note}</div>
    </div>""", unsafe_allow_html=True)

with col1:
    ob_box(col1, "Billed Pipeline (AR)",
           f"₹{ar_cr:,.0f} Cr" if ar_cr else "—",
           "Work delivered, payment pending", "#f59e0b")
with col2:
    ob_box(col2, "WIP / Stock (Inventory)",
           f"₹{inv_cr:,.0f} Cr" if inv_cr else "—",
           "Goods in production / finished stock", "#26a69a")
with col3:
    ob_box(col3, "Total Active Pipeline",
           f"₹{pending_cr:,.0f} Cr" if pending_cr else "—",
           "AR + Inventory on books", "#d1d4dc")
with col4:
    ob_box(col4, "Qtr Completion %",
           f"{completed_pct:.1f}%" if completed_pct else "—",
           "Revenue booked vs pipeline", "#26a69a" if completed_pct and completed_pct > 30 else "#f59e0b")

# Order execution bar chart  (quarterly revenue as order completion proxy)
if rev_s is not None and len(rev_s) >= 2:
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    rev_cr_s = (rev_s / 1e7).round(1)
    max_rev  = float(rev_cr_s.max())
    fig_ob = go.Figure()
    completed_vals = rev_cr_s.values
    pending_vals   = [max(0, max_rev * 1.15 - v) for v in completed_vals]  # target headroom
    fig_ob.add_trace(go.Bar(
        x=rev_cr_s.index, y=completed_vals, name="Completed (Revenue)",
        marker_color="#26a69a",
        text=[f"₹{v:,.0f}" for v in completed_vals],
        textposition="inside", textfont=dict(size=9, color="#ffffff"),
    ))
    fig_ob.add_trace(go.Bar(
        x=rev_cr_s.index, y=pending_vals, name="Headroom to Peak",
        marker_color="#2a2e39", opacity=0.6,
    ))
    if dso:
        fig_ob.add_annotation(
            text=f"DSO: {dso:.0f} days", xref="paper", yref="paper",
            x=0.01, y=0.97, showarrow=False,
            font=dict(size=11, color="#f59e0b"), bgcolor="#1e222d",
            bordercolor="#2a2e39", borderwidth=1,
        )
    fig_ob.update_layout(
        barmode="stack", height=260,
        title=dict(text="Quarterly Order Completion (Revenue Booked)", font=dict(size=12, color="#787b86")),
        legend=dict(orientation="h", y=-0.25, font=dict(size=10, color="#787b86"), bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=40, b=10, l=10, r=10), **PLOTLY_DARK,
    )
    fig_ob.update_xaxes(tickfont=dict(size=9, color="#787b86"), tickangle=-30)
    fig_ob.update_yaxes(tickfont=dict(size=9, color="#787b86"), title_text="₹ Cr")
    st.plotly_chart(fig_ob, use_container_width=True)

# ── Capacity Utilisation ──────────────────────────────────────────
st.markdown('<div class="section-label">Capacity Utilisation</div>', unsafe_allow_html=True)

col_a, col_b = st.columns([1, 2])

with col_a:
    # Derived utilisation metrics
    asset_turn  = (ttm_rev / total_assets) if ttm_rev and total_assets else None
    fa_turn     = (ttm_rev / net_ppe)      if ttm_rev and net_ppe and net_ppe > 0 else None
    # Revenue ramp: latest Q vs 8Q max = % of peak capacity being used
    rev_ramp    = (float(rev_s.iloc[-1]) / float(rev_s.max()) * 100) if rev_s is not None and len(rev_s) > 0 else None
    # EBITDA margin = operational efficiency
    ebitda_latest = None
    if q_inc is not None and not q_inc.empty and "EBITDA" in q_inc.index:
        eb = q_inc.sort_index(axis=1, ascending=True).loc["EBITDA"].dropna()
        if len(eb) > 0 and latest_q_rev and latest_q_rev > 0:
            ebitda_latest = float(eb.iloc[-1]) / latest_q_rev * 100

    metrics_html = ""
    def gauge_bar(label, pct, color="#26a69a", note=""):
        if pct is None: return ""
        filled = min(100, max(0, pct))
        return f"""
        <div style="margin-bottom:14px">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px">
            <span style="color:#787b86;font-size:0.72rem;font-weight:700;text-transform:uppercase">{label}</span>
            <span style="color:{color};font-size:0.82rem;font-weight:700">{pct:.1f}%</span>
          </div>
          <div style="background:#2a2e39;border-radius:4px;height:8px;overflow:hidden">
            <div style="background:{color};width:{filled}%;height:8px;border-radius:4px;transition:width 0.5s"></div>
          </div>
          <div style="color:#475569;font-size:0.7rem;margin-top:2px">{note}</div>
        </div>"""

    bars = ""
    if rev_ramp is not None:
        bars += gauge_bar("Revenue Ramp", rev_ramp, "#26a69a", "Latest quarter vs 8Q peak")
    if ebitda_latest is not None:
        bars += gauge_bar("EBITDA Margin", ebitda_latest, "#f59e0b", "Operational efficiency")
    if asset_turn is not None:
        norm_at = min(100, asset_turn * 50)   # 2x turns → 100%
        bars += gauge_bar("Asset Utilisation", norm_at, "#7e57c2",
                          f"Asset turnover {asset_turn:.2f}x (Revenue / Total Assets)")
    if fa_turn is not None:
        norm_fa = min(100, fa_turn * 20)      # 5x fixed asset turns → 100%
        bars += gauge_bar("Fixed Asset Efficiency", norm_fa, "#26a69a",
                          f"Fixed asset turnover {fa_turn:.1f}x (Revenue / Net PPE)")

    if bars:
        st.markdown(f'<div style="padding:4px 0">{bars}</div>', unsafe_allow_html=True)
    else:
        st.info("Insufficient data for capacity metrics.")

with col_b:
    # EBITDA trend with margin overlay
    if q_inc is not None and not q_inc.empty:
        q_sorted2 = q_inc.sort_index(axis=1, ascending=True)
        def get_qs(row):
            if row in q_sorted2.index:
                s = q_sorted2.loc[row].dropna()
                s.index = [to_qtr(c) for c in pd.to_datetime(s.index)]
                return s.tail(8)
            return None
        ebitda_s2 = get_qs("EBITDA")
        rev_s2    = get_qs(rev_row) if rev_row else None

        if ebitda_s2 is not None and len(ebitda_s2) > 0:
            eb_cr = (ebitda_s2 / 1e7).round(1)
            eb_mg = (ebitda_s2 / rev_s2.reindex(ebitda_s2.index).replace(0, float("nan")) * 100).round(1) \
                    if rev_s2 is not None else None
            fig_cap = go.Figure()
            fig_cap.add_trace(go.Bar(
                x=eb_cr.index, y=eb_cr, name="EBITDA (₹ Cr)",
                marker_color="#26a69a", opacity=0.85,
                text=[f"₹{v:,.0f}" for v in eb_cr],
                textposition="inside", textfont=dict(size=9, color="#ffffff"),
            ))
            if eb_mg is not None:
                fig_cap.add_trace(go.Scatter(
                    x=eb_mg.index, y=eb_mg, name="EBITDA Margin %",
                    line=dict(color="#f59e0b", width=2, dash="dot"),
                    mode="lines+markers+text",
                    text=[f"{v:.1f}%" for v in eb_mg],
                    textposition="top center", textfont=dict(size=8, color="#f59e0b"),
                    yaxis="y2",
                ))
            fig_cap.update_layout(
                title=dict(text="EBITDA Trend & Margin", font=dict(size=12, color="#787b86")),
                height=300, margin=dict(t=40, b=10, l=10, r=10),
                yaxis2=dict(overlaying="y", side="right", showgrid=False,
                            tickfont=dict(size=9, color="#f59e0b"), ticksuffix="%"),
                legend=dict(orientation="h", y=-0.28, font=dict(size=10, color="#787b86"), bgcolor="rgba(0,0,0,0)"),
                **PLOTLY_DARK,
            )
            fig_cap.update_xaxes(tickfont=dict(size=9, color="#787b86"), tickangle=-30)
            fig_cap.update_yaxes(tickfont=dict(size=9, color="#787b86"))
            st.plotly_chart(fig_cap, use_container_width=True)

# ── Future Growth Projections ─────────────────────────────────────
st.markdown('<div class="section-label">Future Growth Projections</div>', unsafe_allow_html=True)
st.markdown(
    '<p style="color:#787b86;font-size:0.78rem;margin:-8px 0 14px 0;">'
    'Enter management guidance from the latest concall / investor presentation. '
    'Historical CAGR & analyst consensus are shown for reference.</p>',
    unsafe_allow_html=True,
)

if rev_s is not None and len(rev_s) >= 2:
    rev_row_a = next((r for r in ["Total Revenue", "Net Interest Income"] if r in (a_inc.index if a_inc is not None and not a_inc.empty else [])), None)

    # ── Historical CAGR ──
    ann_rev = None
    cagr1, cagr3 = None, None
    if rev_row_a and a_inc is not None and not a_inc.empty:
        ann_rev = a_inc.loc[rev_row_a].dropna().sort_index(ascending=True)
        if len(ann_rev) >= 2:
            cagr1 = ((float(ann_rev.iloc[-1]) / float(ann_rev.iloc[-2])) - 1) * 100
        if len(ann_rev) >= 3:
            n = min(3, len(ann_rev) - 1)
            cagr3 = ((float(ann_rev.iloc[-1]) / float(ann_rev.iloc[-n-1])) ** (1/n) - 1) * 100

    # ── Analyst revenue estimates (yfinance) ──
    has_analyst   = False
    analyst_rev_1y = None
    analyst_growth = None
    analyst_n      = 0
    try:
        rev_est = yf.Ticker(ticker).revenue_estimate
        if rev_est is not None and not rev_est.empty and "+1y" in rev_est.index:
            avg_1y = float(rev_est.loc["+1y", "avg"])
            n_ana  = int(rev_est.loc["+1y", "numberOfAnalysts"])
            if avg_1y > 0 and n_ana > 0:
                has_analyst    = True
                analyst_rev_1y = avg_1y / 1e7
                analyst_growth = float(rev_est.loc["+1y", "growth"]) * 100
                analyst_n      = n_ana
    except Exception:
        pass

    # ── Quarter label helper ──
    def next_qtr(label):
        try:
            q = int(label[1]); fy = int("20" + label[5:])
            q += 1
            if q > 4: q, fy = 1, fy + 1
            return f"Q{q} FY{str(fy)[2:]}"
        except Exception:
            return label + "+"

    last_qtr  = rev_s.index[-1]
    base_rev  = float(rev_s.iloc[-1]) / 1e7   # latest quarter ₹ Cr
    fwd_qtrs  = []
    lbl = last_qtr
    for _ in range(5):
        lbl = next_qtr(lbl)
        fwd_qtrs.append(lbl)
    proj_qtrs_full = [last_qtr] + fwd_qtrs

    def project(base_val, annual_pct, n=5):
        q_rate = (1 + annual_pct / 100) ** 0.25 - 1
        vals = [base_val]
        for _ in range(n):
            vals.append(round(vals[-1] * (1 + q_rate), 1))
        return vals

    # Scenario rates (annual %)
    bear_annual = max(0.0, (cagr1 or 0) * 0.4)
    base_annual = cagr1 or 10.0
    bull_annual = max(base_annual * 1.5, cagr3 or base_annual * 1.5)

    col_p1, col_p2 = st.columns([1, 2])

    with col_p1:
        # ── Management guidance input ──
        st.markdown(
            '<div style="color:#787b86;font-size:0.72rem;font-weight:700;'
            'text-transform:uppercase;letter-spacing:0.6px;margin-bottom:6px">'
            'Enter Management Guidance</div>',
            unsafe_allow_html=True,
        )
        guidance_yoy = st.number_input(
            "Annual Revenue Growth %",
            min_value=-50.0, max_value=500.0,
            value=None,
            placeholder="e.g. 25 for 25% growth",
            key=f"mgmt_guidance_{symbol}",
            help="Type the revenue growth % target from the company's latest earnings call or investor presentation.",
            label_visibility="collapsed",
        )

        if guidance_yoy is not None:
            gc = "#26a69a" if guidance_yoy >= 0 else "#ef5350"
            ga = "▲" if guidance_yoy >= 0 else "▼"
            st.markdown(f"""
            <div class="order-box" style="border-left:3px solid #7e57c2;margin-bottom:10px">
              <div class="ob-label">Mgmt Guidance (entered)</div>
              <div class="ob-val" style="color:#7e57c2">{ga} {abs(guidance_yoy):.1f}% YoY</div>
              <div class="ob-note">Annual revenue growth target</div>
            </div>""", unsafe_allow_html=True)

        # ── Analyst consensus ──
        if has_analyst:
            ac = "#26a69a" if analyst_growth >= 0 else "#ef5350"
            aa = "▲" if analyst_growth >= 0 else "▼"
            st.markdown(f"""
            <div class="order-box" style="margin-bottom:10px">
              <div class="ob-label">Analyst Consensus (+1 Yr)</div>
              <div class="ob-val" style="color:{ac}">{aa} {abs(analyst_growth):.1f}%</div>
              <div class="ob-note">{analyst_n} analyst{'s' if analyst_n != 1 else ''} · ₹{analyst_rev_1y:,.0f} Cr est.</div>
            </div>""", unsafe_allow_html=True)

        # ── Historical reference ──
        cagr_n = min(3, len(ann_rev) - 1) if ann_rev is not None and len(ann_rev) >= 2 else None
        c1c = "#26a69a" if cagr1 and cagr1 >= 0 else "#ef5350"
        c3c = "#26a69a" if cagr3 and cagr3 >= 0 else "#ef5350"
        st.markdown(f"""
        <div style="color:#787b86;font-size:0.7rem;font-weight:700;text-transform:uppercase;
             letter-spacing:0.6px;margin:4px 0 6px 0">Historical Reference</div>
        <div class="order-box" style="margin-bottom:6px">
          <div class="ob-label">1-Yr Revenue Growth</div>
          <div class="ob-val" style="color:{c1c}">
            {'▲' if cagr1 and cagr1 >= 0 else ('▼' if cagr1 else '—')}
            {f' {abs(cagr1):.1f}%' if cagr1 else ''}</div>
          <div class="ob-note">Latest FY vs prior FY</div>
        </div>
        <div class="order-box">
          <div class="ob-label">{cagr_n or '—'}-Yr CAGR</div>
          <div class="ob-val" style="color:{c3c}">
            {'▲' if cagr3 and cagr3 >= 0 else ('▼' if cagr3 else '—')}
            {f' {abs(cagr3):.1f}%' if cagr3 else ''}</div>
          <div class="ob-note">Compound annual growth rate</div>
        </div>""", unsafe_allow_html=True)

        # ── NSE guidance announcements ──
        guid_anns = [
            a for a in announcements
            if any(k in (a.get("subject", "") + " " + a.get("desc", "")).lower()
                   for k in GUIDANCE_KEYWORDS)
        ]
        if guid_anns:
            st.markdown(
                '<div style="color:#787b86;font-size:0.7rem;font-weight:700;text-transform:uppercase;'
                'letter-spacing:0.6px;margin:12px 0 6px 0">Guidance Announcements</div>',
                unsafe_allow_html=True,
            )
            for ann in guid_anns[:3]:
                subj = (ann.get("subject") or ann.get("desc") or "")[:80]
                dt   = (ann.get("exchdisstime") or "")[:10]
                st.markdown(f"""
                <div style="background:#1e222d;border-left:3px solid #7e57c2;border-radius:4px;
                     padding:8px 12px;margin-bottom:5px">
                  <div style="color:#d1d4dc;font-size:0.78rem">{subj}</div>
                  <div style="color:#787b86;font-size:0.72rem;margin-top:2px">{dt}</div>
                </div>""", unsafe_allow_html=True)

    with col_p2:
        hist_vals = [float(v) / 1e7 for v in rev_s.values]
        hist_qtrs = list(rev_s.index)

        bear_proj = project(base_rev, bear_annual)
        base_proj = project(base_rev, base_annual)
        bull_proj = project(base_rev, bull_annual)
        guid_proj = project(base_rev, guidance_yoy) if guidance_yoy is not None else None
        anal_proj = project(base_rev, analyst_growth) if has_analyst else None

        y_max = max(
            max(hist_vals),
            max(bull_proj),
            max(guid_proj) if guid_proj else 0,
            max(anal_proj) if anal_proj else 0,
        ) * 1.12

        fig_proj = go.Figure()

        # Historical bars
        fig_proj.add_trace(go.Bar(
            x=hist_qtrs, y=hist_vals, name="Historical",
            marker_color="#26a69a",
            text=[f"₹{v:,.0f}" for v in hist_vals],
            textposition="outside", textfont=dict(size=9, color="#787b86"),
        ))

        # Bull–Bear shaded band
        fig_proj.add_trace(go.Scatter(
            x=proj_qtrs_full, y=bull_proj,
            name=f"Bull  {bull_annual:.0f}% pa",
            line=dict(color="#26a69a", width=1, dash="dot"),
            mode="lines",
        ))
        fig_proj.add_trace(go.Scatter(
            x=proj_qtrs_full, y=bear_proj,
            name=f"Bear  {bear_annual:.0f}% pa",
            line=dict(color="#ef5350", width=1, dash="dot"),
            fill="tonexty", fillcolor="rgba(38,166,154,0.07)",
            mode="lines",
        ))

        # Base (historical CAGR) — dashed grey reference
        fig_proj.add_trace(go.Scatter(
            x=proj_qtrs_full, y=base_proj,
            name=f"Base  {base_annual:.0f}% pa (hist. CAGR)",
            line=dict(color="#787b86", width=1.5, dash="dash"),
            mode="lines+markers",
        ))

        # Analyst consensus — amber
        if anal_proj:
            fig_proj.add_trace(go.Scatter(
                x=proj_qtrs_full, y=anal_proj,
                name=f"Analyst  {analyst_growth:.0f}% pa ({analyst_n} est.)",
                line=dict(color="#f59e0b", width=2),
                mode="lines+markers+text",
                text=[""] + [f"₹{v:,.0f}" for v in anal_proj[1:]],
                textposition="top center",
                textfont=dict(size=8, color="#f59e0b"),
            ))

        # Management guidance — purple, most prominent
        if guid_proj:
            fig_proj.add_trace(go.Scatter(
                x=proj_qtrs_full, y=guid_proj,
                name=f"Mgmt Guidance  {guidance_yoy:.0f}% pa",
                line=dict(color="#7e57c2", width=2.5),
                mode="lines+markers+text",
                text=[""] + [f"₹{v:,.0f}" for v in guid_proj[1:]],
                textposition="top center",
                textfont=dict(size=9, color="#c5b4e3"),
            ))

        # Divider line between actual and projected
        fig_proj.add_vline(
            x=last_qtr, line_color="#2a2e39", line_dash="dash", line_width=1.5,
        )
        fig_proj.add_annotation(
            text="◀ Actual   Projected ▶",
            x=last_qtr, y=y_max * 0.97,
            font=dict(size=10, color="#787b86"), showarrow=False,
            bgcolor="#131722", borderpad=3,
        )

        primary_source = (
            "Mgmt Guidance" if guid_proj else
            f"Analyst Consensus ({analyst_n} est.)" if anal_proj else
            "Historical CAGR (no guidance entered)"
        )
        fig_proj.update_layout(
            title=dict(
                text=f"Revenue Outlook — {primary_source}   |   "
                     f"Bear {bear_annual:.0f}%  /  Base {base_annual:.0f}%  /  Bull {bull_annual:.0f}% pa",
                font=dict(size=11, color="#787b86"),
            ),
            height=370,
            margin=dict(t=55, b=10, l=10, r=10),
            barmode="group",
            legend=dict(
                orientation="h", y=-0.22,
                font=dict(size=10, color="#787b86"),
                bgcolor="rgba(0,0,0,0)",
            ),
            **PLOTLY_DARK,
        )
        fig_proj.update_xaxes(tickfont=dict(size=9, color="#787b86"), tickangle=-30)
        fig_proj.update_yaxes(tickfont=dict(size=9, color="#787b86"), title_text="₹ Cr", range=[0, y_max])
        st.plotly_chart(fig_proj, use_container_width=True)

# ── Quick links ────────────────────────────────────────────────────
_is_bse    = ticker.endswith(".BO")
_exch_link = (
    f'<a href="https://www.bseindia.com/stock-share-price/{symbol.lower()}/A/" target="_blank" style="color:#26a69a;margin-right:16px;">BSE Filings ↗</a>'
    if _is_bse else
    f'<a href="https://www.nseindia.com/get-quotes/equity?symbol={symbol}" target="_blank" style="color:#26a69a;margin-right:16px;">NSE Filings ↗</a>'
)
st.markdown(f"""
<div style="margin-top:24px;padding:14px 18px;background:#1e222d;border:1px solid #2a2e39;border-radius:6px;font-size:0.82rem;">
  <span style="color:#787b86;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">Quick Links &nbsp;·&nbsp;</span>
  {_exch_link}
  <a href="https://www.screener.in/company/{symbol}/" target="_blank" style="color:#26a69a;margin-right:16px;">Screener.in ↗</a>
  <a href="https://www.moneycontrol.com/stocks/cptmarket/compsearchnew.php?search_data={company_name.replace(' ','+')}" target="_blank" style="color:#26a69a;margin-right:16px;">Moneycontrol ↗</a>
  <a href="https://finance.yahoo.com/quote/{ticker}" target="_blank" style="color:#26a69a;">Yahoo Finance ↗</a>
</div>
""", unsafe_allow_html=True)
