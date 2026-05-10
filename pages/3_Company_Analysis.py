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
NSE_EQUITIES_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"

# ── Symbol map (all NSE-listed equities) ─────────────────────────
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

def find_symbol(query: str, sym_map: pd.DataFrame):
    """Return (symbol, name) or (matches_df, None) for ambiguous queries."""
    q = query.strip()
    # Exact symbol match
    exact = sym_map[sym_map["Symbol"].str.upper() == q.upper()]
    if not exact.empty:
        return exact.iloc[0]["Symbol"], exact.iloc[0]["Company Name"]
    # Partial company name match
    mask = sym_map["Company Name"].str.contains(q, case=False, na=False, regex=False)
    hits = sym_map[mask].reset_index(drop=True)
    if len(hits) == 1:
        return hits.iloc[0]["Symbol"], hits.iloc[0]["Company Name"]
    if len(hits) > 1:
        return hits, None
    # Fallback: direct yfinance lookup
    try:
        tk = yf.Ticker(f"{q.upper()}.NS")
        name = (tk.info or {}).get("longName", "")
        if name:
            return q.upper(), name
    except Exception:
        pass
    return None, None

# ── Data fetching ──────────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_company(symbol: str):
    tk = yf.Ticker(f"{symbol}.NS")
    info  = tk.info or {}
    q_inc = tk.quarterly_income_stmt
    a_inc = tk.income_stmt
    news  = tk.news or []
    return info, q_inc, a_inc, news

@st.cache_data(ttl=3600, show_spinner=False)
def get_nse_announcements(symbol: str, max_items: int = 10):
    try:
        s = requests.Session()
        hdrs = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://www.nseindia.com/",
        }
        s.get("https://www.nseindia.com/", headers=hdrs, timeout=8)
        url = f"https://www.nseindia.com/api/corp-announcements?index=equities&symbol={symbol}"
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
        "Company", placeholder="e.g. Dynacons Systems, Piccadily Agro, RELIANCE",
        label_visibility="collapsed",
    ).strip()
with c2:
    go_btn = st.button("🔍 Analyse", type="primary", use_container_width=True)

if not query:
    st.markdown("""
    <div style="text-align:center;padding:60px 0;color:#475569;">
      <div style="font-size:2.5rem;margin-bottom:12px;">🏢</div>
      <div style="font-size:1rem;font-weight:600;color:#64748b;">Enter a company name or NSE symbol above</div>
      <div style="font-size:0.82rem;color:#475569;margin-top:6px;">e.g. Dynacons Systems, Piccadily Agro, RELIANCE, HDFCBANK</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Symbol resolution ──────────────────────────────────────────────
if go_btn or st.session_state.get("ca_query") != query:
    st.session_state["ca_query"] = query
    st.session_state.pop("ca_symbol", None)
    st.session_state.pop("ca_matches", None)

with st.spinner("Looking up symbol…"):
    sym_map = load_symbol_map()

if "ca_symbol" not in st.session_state:
    result, name = find_symbol(query, sym_map)
    if result is None:
        st.error(f"No NSE-listed company found for **{query}**. Try the NSE symbol directly.")
        st.stop()
    if isinstance(result, pd.DataFrame):
        st.session_state["ca_matches"] = result
    else:
        st.session_state["ca_symbol"] = result
        st.session_state["ca_name"]   = name

if "ca_matches" in st.session_state:
    matches = st.session_state["ca_matches"]
    st.warning(f"Found {len(matches)} companies matching **{query}**. Select one:")
    sel = st.selectbox(
        "Choose company", matches["Company Name"].tolist(), label_visibility="collapsed"
    )
    if st.button("Confirm", type="primary"):
        row = matches[matches["Company Name"] == sel].iloc[0]
        st.session_state["ca_symbol"] = row["Symbol"]
        st.session_state["ca_name"]   = row["Company Name"]
        del st.session_state["ca_matches"]
        st.rerun()
    st.stop()

symbol = st.session_state["ca_symbol"]

# ── Fetch data ─────────────────────────────────────────────────────
with st.spinner(f"Fetching data for {symbol}…"):
    info, q_inc, a_inc, news = fetch_company(symbol)
    announcements = get_nse_announcements(symbol)

if not info or not info.get("longName"):
    st.error(f"Could not fetch data for **{symbol}**. Verify the symbol is correct.")
    st.stop()

company_name = info.get("longName", symbol)
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
  <span style="color:#787b86;font-size:0.8rem;">52W: ₹{w52_low:,.0f} – ₹{w52_high:,.0f}</span>
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
q_bal = yf.Ticker(f"{symbol}.NS").quarterly_balance_sheet if symbol else None

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

if rev_s is not None and len(rev_s) >= 3 and a_inc is not None and not a_inc.empty:
    rev_row_a = next((r for r in ["Total Revenue", "Net Interest Income"] if r in a_inc.index), None)
    col_p1, col_p2 = st.columns([1, 2])

    with col_p1:
        # CAGR metrics
        ann_rev = None
        cagr1, cagr3 = None, None
        if rev_row_a:
            ann_rev = a_inc.loc[rev_row_a].dropna().sort_index(ascending=True)
            if len(ann_rev) >= 2:
                cagr1 = ((float(ann_rev.iloc[-1]) / float(ann_rev.iloc[-2])) - 1) * 100
            if len(ann_rev) >= 4:
                n = min(3, len(ann_rev) - 1)
                cagr3 = ((float(ann_rev.iloc[-1]) / float(ann_rev.iloc[-n-1])) ** (1/n) - 1) * 100

        # Avg quarterly growth rate (last 4 quarters)
        avg_qoq = None
        if rev_s is not None and len(rev_s) >= 4:
            pct_changes = [(float(rev_s.iloc[i]) / float(rev_s.iloc[i-1]) - 1)
                           for i in range(max(1, len(rev_s)-4), len(rev_s))
                           if float(rev_s.iloc[i-1]) != 0]
            avg_qoq = sum(pct_changes) / len(pct_changes) if pct_changes else None

        c1h = "#26a69a" if cagr1 and cagr1 >= 0 else "#ef5350"
        c3h = "#26a69a" if cagr3 and cagr3 >= 0 else "#ef5350"
        cqh = "#26a69a" if avg_qoq and avg_qoq >= 0 else "#ef5350"

        st.markdown(f"""
        <div style="display:flex;flex-direction:column;gap:10px;padding-top:6px">
          <div class="order-box">
            <div class="ob-label">1-Year Revenue Growth</div>
            <div class="ob-val" style="color:{c1h}">{'▲' if cagr1 and cagr1>=0 else '▼'} {abs(cagr1):.1f}%</div>
            <div class="ob-note">Latest FY vs prior FY</div>
          </div>
          <div class="order-box">
            <div class="ob-label">{min(3,len(ann_rev)-1) if ann_rev is not None and len(ann_rev)>=2 else '—'}-Year CAGR</div>
            <div class="ob-val" style="color:{c3h}">{'▲' if cagr3 and cagr3>=0 else ('—' if cagr3 is None else '▼')} {f'{abs(cagr3):.1f}%' if cagr3 else '—'}</div>
            <div class="ob-note">Compound annual growth</div>
          </div>
          <div class="order-box">
            <div class="ob-label">Avg Qtrly Growth Rate</div>
            <div class="ob-val" style="color:{cqh}">{'▲' if avg_qoq and avg_qoq>=0 else '—'} {f'{abs(avg_qoq*100):.1f}%' if avg_qoq else '—'}</div>
            <div class="ob-note">Used for forward projection</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with col_p2:
        # Project next 4 quarters using avg QoQ rate
        if avg_qoq is not None and rev_s is not None and len(rev_s) > 0:
            base = float(rev_s.iloc[-1]) / 1e7
            last_qtr = rev_s.index[-1]   # e.g. "Q4 FY26"
            # Generate next quarter labels
            def next_qtr(label):
                try:
                    q = int(label[1]); fy = int("20" + label[5:])
                    q += 1
                    if q > 4: q, fy = 1, fy + 1
                    return f"Q{q} FY{str(fy)[2:]}"
                except Exception:
                    return label + "+"

            proj_qtrs = [last_qtr]
            proj_vals = [base]
            lbl = last_qtr
            for _ in range(4):
                lbl = next_qtr(lbl)
                base = round(base * (1 + avg_qoq), 1)
                proj_qtrs.append(lbl)
                proj_vals.append(base)

            hist_vals = [(float(v) / 1e7) for v in rev_s.values]
            hist_qtrs = list(rev_s.index)

            fig_proj = go.Figure()
            fig_proj.add_trace(go.Bar(
                x=hist_qtrs, y=hist_vals, name="Historical Revenue",
                marker_color="#26a69a",
                text=[f"₹{v:,.0f}" for v in hist_vals],
                textposition="outside", textfont=dict(size=9, color="#787b86"),
            ))
            fig_proj.add_trace(go.Bar(
                x=proj_qtrs[1:], y=proj_vals[1:], name="Projected Revenue",
                marker_color="#7e57c2", opacity=0.75,
                text=[f"₹{v:,.0f}" for v in proj_vals[1:]],
                textposition="outside", textfont=dict(size=9, color="#d1d4dc"),
            ))
            # Projection boundary line
            fig_proj.add_vline(
                x=proj_qtrs[0], line_color="#2a2e39", line_dash="dash", line_width=1.5,
            )
            fig_proj.add_annotation(
                text="◀ Actual   Projected ▶",
                x=proj_qtrs[0], y=max(max(hist_vals), max(proj_vals)) * 1.05,
                font=dict(size=10, color="#787b86"), showarrow=False,
            )
            fig_proj.update_layout(
                title=dict(text=f"Revenue Projection — based on {avg_qoq*100:.1f}% avg QoQ growth",
                           font=dict(size=12, color="#787b86")),
                height=320, margin=dict(t=50, b=10, l=10, r=10),
                barmode="group",
                legend=dict(orientation="h", y=-0.25, font=dict(size=10, color="#787b86"), bgcolor="rgba(0,0,0,0)"),
                **PLOTLY_DARK,
            )
            fig_proj.update_xaxes(tickfont=dict(size=9, color="#787b86"), tickangle=-30)
            fig_proj.update_yaxes(tickfont=dict(size=9, color="#787b86"), title_text="₹ Cr")
            st.plotly_chart(fig_proj, use_container_width=True)

# ── Quick links ────────────────────────────────────────────────────
st.markdown(f"""
<div style="margin-top:24px;padding:14px 18px;background:#1e222d;border:1px solid #2a2e39;border-radius:6px;font-size:0.82rem;">
  <span style="color:#787b86;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">Quick Links &nbsp;·&nbsp;</span>
  <a href="https://www.nseindia.com/get-quotes/equity?symbol={symbol}" target="_blank" style="color:#26a69a;margin-right:16px;">NSE Filings ↗</a>
  <a href="https://www.screener.in/company/{symbol}/" target="_blank" style="color:#26a69a;margin-right:16px;">Screener.in ↗</a>
  <a href="https://www.moneycontrol.com/stocks/cptmarket/compsearchnew.php?search_data={company_name.replace(' ','+')}" target="_blank" style="color:#26a69a;margin-right:16px;">Moneycontrol ↗</a>
  <a href="https://finance.yahoo.com/quote/{symbol}.NS" target="_blank" style="color:#26a69a;">Yahoo Finance ↗</a>
</div>
""", unsafe_allow_html=True)
