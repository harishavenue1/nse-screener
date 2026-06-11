"""
Sector Performance – every NSE sector (Nifty 500 industry groups) with
returns over 1D / 1W / 1M / 3M / 6M / 1Y, plus per-sector drill-down.

Sector return = median (or mean) of constituent stock returns, equal-weighted.
Per-stock returns cached to sector_cache.csv; use "Rescan" to refresh.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="Sectors | NSE Screener",
    page_icon="🏭",
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

.sec-banner {
    background: linear-gradient(90deg,#1e222d 0%,#131722 100%);
    border:1px solid #2a2e39; border-left:3px solid #f59e0b;
    border-radius:8px; padding:16px 24px; margin-bottom:20px;
}
.sec-banner h1 { color:#d1d4dc; font-size:1.5rem; font-weight:700; margin:0 0 2px 0; }
.sec-banner p  { color:#787b86; font-size:0.8rem; margin:0; }

.sec-table-wrap { background:#1e222d; border:1px solid #2a2e39; border-radius:8px; overflow:auto; margin-bottom:18px; }
.sec-table-wrap table { width:100%; border-collapse:collapse; font-size:0.84rem; }
.sec-table-wrap th {
    background:#131722; color:#787b86; font-size:0.66rem; font-weight:700;
    text-transform:uppercase; letter-spacing:0.6px; padding:10px 12px;
    border-bottom:1px solid #2a2e39; text-align:right; white-space:nowrap;
    position:sticky; top:0;
}
.sec-table-wrap th:first-child, .sec-table-wrap td:first-child { text-align:left; }
.sec-table-wrap td {
    padding:9px 12px; border-bottom:1px solid #232733;
    color:#d1d4dc; text-align:right; white-space:nowrap; font-weight:600;
}
.sec-table-wrap tr:hover td { background:#262b38 !important; }
.sec-table-wrap th a { color:#787b86; text-decoration:none; }
.sec-table-wrap th a:hover { color:#d1d4dc; }
.sec-table-wrap th a.active { color:#2962ff; }
.secname { font-weight:700; color:#d1d4dc; }
.count   { color:#787b86; font-size:0.72rem; font-weight:400; }
.pos { color:#26a69a; } .neg { color:#ef5350; } .na { color:#50535e; font-weight:400; }
.sym { font-weight:700; } .held { color:#f59e0b; }
</style>
""", unsafe_allow_html=True)

APP_DIR    = Path(__file__).resolve().parent.parent
CACHE_FILE = APP_DIR / "sector_cache.csv"
PERIODS    = {"1D": 1, "1W": 7, "1M": 30, "3M": 91, "6M": 182, "1Y": 365}


@st.cache_data(ttl=86400, show_spinner=False)
def get_universe() -> pd.DataFrame:
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/csv,*/*"}
    r = requests.get(
        "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
        headers=headers, timeout=15,
    )
    r.raise_for_status()
    df = pd.read_csv(StringIO(r.text))
    return df[["Symbol", "Company Name", "Industry"]].rename(
        columns={"Company Name": "Name"})


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


def run_scan(symbols: list[str]) -> pd.DataFrame:
    """Batch-download 13 months of closes in chunks; compute per-stock returns."""
    rows = []
    chunks = [symbols[i:i + 100] for i in range(0, len(symbols), 100)]
    bar = st.progress(0.0, text="Downloading price history…")
    for ci, chunk in enumerate(chunks):
        tickers = [s + ".NS" for s in chunk]
        try:
            raw = yf.download(tickers, period="13mo", interval="1d",
                              auto_adjust=True, group_by="ticker",
                              progress=False, threads=True)
        except Exception:
            continue
        for sym, tk in zip(chunk, tickers):
            try:
                closes = raw[tk]["Close"].dropna()
            except (KeyError, TypeError):
                continue
            if closes.empty:
                continue
            row = {"Symbol": sym}
            for label, days in PERIODS.items():
                row[label] = period_return(closes, days)
            rows.append(row)
        bar.progress((ci + 1) / len(chunks),
                     text=f"Downloaded {min((ci + 1) * 100, len(symbols))} / {len(symbols)} stocks…")
    bar.empty()
    df = pd.DataFrame(rows)
    df["as_of"] = date.today().isoformat()
    df.to_csv(CACHE_FILE, index=False)
    return df


# ── Sidebar ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏭 Sector Performance")
    agg_name = st.selectbox("Aggregation", ["Median", "Mean"])
    rescan = st.button("🔄 Rescan (~1–2 min)")

universe = get_universe()

cached = None
if CACHE_FILE.exists() and not rescan:
    try:
        cached = pd.read_csv(CACHE_FILE)
    except Exception:
        cached = None

if cached is not None and not cached.empty:
    stock_df, as_of = cached, cached["as_of"].iloc[0]
else:
    st.info(f"Downloading 13 months of prices for {len(universe)} stocks…")
    stock_df, as_of = run_scan(universe["Symbol"].tolist()), date.today().isoformat()

stock_df = stock_df.merge(universe, on="Symbol", how="left").dropna(subset=["Industry"])
agg = "median" if agg_name == "Median" else "mean"

sec = stock_df.groupby("Industry").agg(
    **{"Stocks": ("Symbol", "count")},
    **{p: (p, agg) for p in PERIODS},
).reset_index()

# ── Sorting via clickable headers ──────────────────────────────────
SORTABLE = {"Sector": "Industry", "Stocks": "Stocks", **{p: p for p in PERIODS}}
qp = st.query_params
sort_label = qp.get("sort", "1D")
sort_dir = qp.get("dir", "desc")
if sort_label in SORTABLE:
    col = SORTABLE[sort_label]
    sec = sec.sort_values(
        col, ascending=(sort_dir == "asc"), na_position="last",
        key=(lambda c: c.str.lower()) if col == "Industry" else None,
    ).reset_index(drop=True)


def th(label: str) -> str:
    active = label == sort_label
    arrow = (" ▲" if sort_dir == "asc" else " ▼") if active else ""
    next_dir = "asc" if (active and sort_dir == "desc") else "desc"
    cls = ' class="active"' if active else ""
    return (f'<th><a{cls} href="?sort={label.replace(" ", "%20")}&dir={next_dir}" '
            f'target="_self">{label}{arrow}</a></th>')


def heat_cell(v) -> str:
    """Colored cell with intensity-scaled background."""
    if v is None or pd.isna(v):
        return '<td class="na">—</td>'
    alpha = min(abs(v) / 25, 0.45)
    bg = f"rgba({'38,166,154' if v >= 0 else '239,83,80'},{alpha:.2f})"
    cls = "pos" if v >= 0 else "neg"
    return f'<td class="{cls}" style="background:{bg}">{v:+.1f}%</td>'


st.markdown(f"""
<div class="sec-banner">
  <h1>🏭 Sector Performance</h1>
  <p>{len(sec)} sectors · {agg_name.lower()} of Nifty 500 constituent returns (equal-weighted) ·
  1D / 1W / 1M / 3M / 6M / 1Y · data as of {as_of} · click a column to sort</p>
</div>
""", unsafe_allow_html=True)

body = []
for _, r in sec.iterrows():
    body.append(
        f"<tr><td><span class='secname'>{r['Industry']}</span> "
        f"<span class='count'>({r['Stocks']})</span></td>"
        f"<td class='count'>{r['Stocks']}</td>"
        + "".join(heat_cell(r[p]) for p in PERIODS)
        + "</tr>"
    )

st.markdown(f"""
<div class="sec-table-wrap"><table>
<thead><tr>{th("Sector")}{th("Stocks")}{''.join(th(p) for p in PERIODS)}</tr></thead>
<tbody>{''.join(body)}</tbody>
</table></div>
""", unsafe_allow_html=True)

# ── Drill-down ─────────────────────────────────────────────────────
st.markdown("#### 🔍 Drill into a sector")
c1, c2 = st.columns([2, 1])
with c1:
    pick = st.selectbox("Sector", sorted(sec["Industry"]), label_visibility="collapsed")
with c2:
    pick_period = st.selectbox("Rank by", list(PERIODS), index=3, label_visibility="collapsed")

sub = (stock_df[stock_df["Industry"] == pick]
       .sort_values(pick_period, ascending=False, na_position="last")
       .reset_index(drop=True))

# holdings badge
held = set()
hf = APP_DIR / "holdings.json"
if hf.exists():
    try:
        import json
        for h in json.loads(hf.read_text())["holdings"]:
            base = h["symbol"]
            for sfx in ("-BE", "-BZ", "-SM", "-ST", "-BL"):
                if base.endswith(sfx):
                    base = base[: -len(sfx)]
            held.add(base)
    except Exception:
        pass

body2 = []
for _, r in sub.iterrows():
    star = ' <span class="held">★</span>' if r["Symbol"] in held else ""
    body2.append(
        f"<tr><td><span class='sym'>{r['Symbol']}</span>{star}<br>"
        f"<span class='count'>{r['Name']}</span></td><td></td>"
        + "".join(heat_cell(r[p]) for p in PERIODS)
        + "</tr>"
    )

st.markdown(f"""
<div class="sec-table-wrap"><table>
<thead><tr><th>Stock</th><th></th>{''.join(f'<th>{p}</th>' for p in PERIODS)}</tr></thead>
<tbody>{''.join(body2)}</tbody>
</table></div>
""", unsafe_allow_html=True)

st.caption("Sector = NSE industry classification of Nifty 500 constituents. Returns are "
           "price-only (no dividends), equal-weighted per stock. ★ = in your portfolio. "
           "Cached daily — Rescan in the sidebar for fresh prices.")
