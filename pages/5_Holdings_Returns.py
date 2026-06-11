"""
Holdings Returns – Kite portfolio returns over 1D / 1W / 1M / 3M / 6M.
Reads holdings.json (snapshot exported from Zerodha Kite) and pulls
price history from Yahoo Finance.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="Holdings Returns | NSE Screener",
    page_icon="💼",
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
[data-testid="stSidebar"] .stSelectbox > div > div {
    background-color: #131722 !important; border-color: #2a2e39 !important; color: #d1d4dc !important;
}
#MainMenu { visibility: hidden; } footer { visibility: hidden; }
header[data-testid="stHeader"] {
    background-color: #131722 !important; border-bottom: 1px solid #2a2e39 !important; box-shadow: none !important;
}
[data-testid="stToolbarActions"] { visibility: hidden; }

.hr-banner {
    background: linear-gradient(90deg,#1e222d 0%,#131722 100%);
    border:1px solid #2a2e39; border-left:3px solid #2962ff;
    border-radius:8px; padding:16px 24px; margin-bottom:20px;
}
.hr-banner h1 { color:#d1d4dc; font-size:1.5rem; font-weight:700; margin:0 0 2px 0; }
.hr-banner p  { color:#787b86; font-size:0.8rem; margin:0; }

.summary-strip { display:flex; gap:10px; margin-bottom:18px; flex-wrap:wrap; }
.summary-card {
    background:#1e222d; border:1px solid #2a2e39; border-radius:6px;
    padding:10px 18px; flex:1; min-width:110px; text-align:center;
}
.summary-card .sc-label { color:#787b86; font-size:0.68rem; font-weight:700; text-transform:uppercase; letter-spacing:0.7px; }
.summary-card .sc-val   { color:#d1d4dc; font-size:1.1rem; font-weight:700; margin-top:3px; }
.summary-card .sc-val.bull { color:#26a69a; }
.summary-card .sc-val.bear { color:#ef5350; }

.hr-table-wrap { background:#1e222d; border:1px solid #2a2e39; border-radius:8px; overflow:auto; }
.hr-table-wrap table { width:100%; border-collapse:collapse; font-size:0.82rem; }
.hr-table-wrap th {
    background:#131722; color:#787b86; font-size:0.68rem; font-weight:700;
    text-transform:uppercase; letter-spacing:0.6px; padding:10px 12px;
    border-bottom:1px solid #2a2e39; text-align:right; white-space:nowrap;
    position:sticky; top:0;
}
.hr-table-wrap th:first-child, .hr-table-wrap td:first-child { text-align:left; }
.hr-table-wrap td {
    padding:8px 12px; border-bottom:1px solid #232733;
    color:#d1d4dc; text-align:right; white-space:nowrap;
}
.hr-table-wrap tr:hover td { background:#262b38; }
.sym  { font-weight:700; color:#d1d4dc; }
.muted{ color:#787b86; font-size:0.72rem; }
.pos  { color:#26a69a; font-weight:600; }
.neg  { color:#ef5350; font-weight:600; }
.na   { color:#50535e; }
</style>
""", unsafe_allow_html=True)

# ── Load holdings snapshot ─────────────────────────────────────────
HOLDINGS_FILE = Path(__file__).resolve().parent.parent / "holdings.json"
if HOLDINGS_FILE.exists():
    snapshot = json.loads(HOLDINGS_FILE.read_text())
elif "holdings_snapshot" in st.session_state:
    snapshot = st.session_state["holdings_snapshot"]
else:
    st.info("holdings.json not found (it is kept out of the repo for privacy). "
            "Upload your Kite holdings snapshot to continue.")
    up = st.file_uploader("Upload holdings.json", type="json")
    if up is None:
        st.stop()
    snapshot = json.load(up)
    st.session_state["holdings_snapshot"] = snapshot
    st.rerun()
holdings = snapshot["holdings"]

SERIES_SUFFIXES = ("-BE", "-BZ", "-SM", "-ST", "-BL")
PERIODS = {"1D": 1, "1W": 7, "1M": 30, "3M": 91, "6M": 182}


def yahoo_ticker(symbol: str, exchange: str) -> str:
    base = symbol
    for sfx in SERIES_SUFFIXES:
        if base.endswith(sfx):
            base = base[: -len(sfx)]
            break
    return base + (".NS" if exchange == "NSE" else ".BO")


def alt_ticker(tk: str) -> str:
    return tk[:-3] + (".BO" if tk.endswith(".NS") else ".NS")


@st.cache_data(ttl=600, show_spinner=False)
def fetch_closes(tickers: tuple[str, ...]) -> dict[str, pd.Series]:
    """Batch-download ~9 months of daily closes; fallback to the other
    exchange suffix for anything that came back empty."""
    out: dict[str, pd.Series] = {}
    raw = yf.download(
        list(tickers), period="9mo", interval="1d",
        auto_adjust=True, group_by="ticker", progress=False, threads=True,
    )
    for tk in tickers:
        try:
            s = raw[tk]["Close"].dropna() if len(tickers) > 1 else raw["Close"].dropna()
        except (KeyError, TypeError):
            s = pd.Series(dtype=float)
        out[tk] = s

    missing = [tk for tk, s in out.items() if s.empty]
    for tk in missing:
        try:
            df = yf.download(alt_ticker(tk), period="9mo", interval="1d",
                             auto_adjust=True, progress=False)
            s = df["Close"].dropna()
            if isinstance(s, pd.DataFrame):
                s = s.iloc[:, 0].dropna()
            out[tk] = s
        except Exception:
            pass
    return out


def period_return(closes: pd.Series, days: int) -> float | None:
    if closes.empty or len(closes) < 2:
        return None
    last_date, last = closes.index[-1], float(closes.iloc[-1])
    if days == 1:
        base = float(closes.iloc[-2])
    else:
        prior = closes[closes.index <= last_date - pd.Timedelta(days=days)]
        if prior.empty:
            return None
        base = float(prior.iloc[-1])
    if not base:
        return None
    return (last / base - 1) * 100


# ── Sidebar ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 💼 Holdings Returns")
    sort_by = st.selectbox("Sort by", ["Value", "1D", "1W", "1M", "3M", "6M", "Overall P&L %", "Symbol"])
    ascending = st.checkbox("Ascending", value=False)
    if st.button("🔄 Refresh prices"):
        fetch_closes.clear()
        st.rerun()
    st.caption(f"Snapshot from Kite: {snapshot.get('as_of', '?')}")

# ── Fetch & compute ────────────────────────────────────────────────
tickers = tuple(yahoo_ticker(h["symbol"], h["exchange"]) for h in holdings)
with st.spinner("Fetching price history…"):
    closes_map = fetch_closes(tickers)

rows = []
for h, tk in zip(holdings, tickers):
    closes = closes_map.get(tk, pd.Series(dtype=float))
    ltp = float(closes.iloc[-1]) if not closes.empty else None
    value = ltp * h["qty"] if ltp else None
    invested = h["avg_price"] * h["qty"]
    pnl_pct = (ltp / h["avg_price"] - 1) * 100 if ltp and h["avg_price"] else None
    row = {
        "Symbol": h["symbol"], "Exchange": h["exchange"], "Qty": h["qty"],
        "Avg": h["avg_price"], "LTP": ltp, "Value": value,
        "Invested": invested, "Overall P&L %": pnl_pct,
    }
    for label, days in PERIODS.items():
        row[label] = period_return(closes, days)
    rows.append(row)

df = pd.DataFrame(rows)
df = df.sort_values(sort_by, ascending=ascending, na_position="last",
                    key=(lambda c: c.str.lower()) if sort_by == "Symbol" else None)

# ── Summary strip ──────────────────────────────────────────────────
tot_val = df["Value"].sum(skipna=True)
tot_inv = df["Invested"].sum(skipna=True)
tot_pnl = tot_val - tot_inv


def wavg(col: str) -> float | None:
    sub = df.dropna(subset=[col, "Value"])
    return (sub[col] * sub["Value"]).sum() / sub["Value"].sum() if len(sub) else None


def fmt_inr(x: float) -> str:
    return f"₹{x:,.0f}"


def card(label: str, val: str, cls: str = "") -> str:
    return (f'<div class="summary-card"><div class="sc-label">{label}</div>'
            f'<div class="sc-val {cls}">{val}</div></div>')


cards = [
    card("Invested", fmt_inr(tot_inv)),
    card("Current", fmt_inr(tot_val)),
    card("P&L", f"{fmt_inr(tot_pnl)} ({tot_pnl / tot_inv * 100:+.1f}%)",
         "bull" if tot_pnl >= 0 else "bear"),
]
for label in PERIODS:
    w = wavg(label)
    cards.append(card(f"Portfolio {label}",
                      f"{w:+.2f}%" if w is not None else "—",
                      "" if w is None else ("bull" if w >= 0 else "bear")))

st.markdown(f"""
<div class="hr-banner">
  <h1>💼 Holdings Returns</h1>
  <p>{len(df)} holdings from Zerodha Kite · returns over 1D / 1W / 1M / 3M / 6M (Yahoo Finance, value-weighted portfolio averages)</p>
</div>
<div class="summary-strip">{''.join(cards)}</div>
""", unsafe_allow_html=True)


# ── Table ──────────────────────────────────────────────────────────
def pct_cell(v) -> str:
    if v is None or pd.isna(v):
        return '<td class="na">—</td>'
    cls = "pos" if v >= 0 else "neg"
    return f'<td class="{cls}">{v:+.2f}%</td>'


body = []
for _, r in df.iterrows():
    ltp = f"{r['LTP']:,.2f}" if pd.notna(r["LTP"]) else "—"
    val = f"{r['Value']:,.0f}" if pd.notna(r["Value"]) else "—"
    body.append(
        f"<tr><td><span class='sym'>{r['Symbol']}</span> "
        f"<span class='muted'>{r['Exchange']}</span></td>"
        f"<td>{r['Qty']:,}</td><td>{r['Avg']:,.2f}</td><td>{ltp}</td><td>{val}</td>"
        + pct_cell(r["Overall P&L %"])
        + "".join(pct_cell(r[p]) for p in PERIODS)
        + "</tr>"
    )

st.markdown(f"""
<div class="hr-table-wrap"><table>
<thead><tr>
  <th>Symbol</th><th>Qty</th><th>Avg ₹</th><th>LTP ₹</th><th>Value ₹</th>
  <th>Overall P&amp;L</th><th>1 Day</th><th>1 Week</th><th>1 Month</th><th>3 Months</th><th>6 Months</th>
</tr></thead>
<tbody>{''.join(body)}</tbody>
</table></div>
""", unsafe_allow_html=True)

st.caption("Prices via Yahoo Finance (EOD/delayed). '—' = insufficient history "
           "(recent listing) or symbol not on Yahoo. Refresh holdings.json from "
           "Kite to update quantities.")
