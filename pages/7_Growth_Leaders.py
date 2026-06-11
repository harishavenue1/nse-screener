"""
Growth Leaders – businesses with the highest sales growth, margin expansion
and profit growth (latest quarter YoY), market cap ≥ ₹500 Cr.

Universe: NSE Nifty Total Market index (~750 companies; falls back to Nifty 500).
Data: Yahoo Finance quarterly income statements. Results cached to
growth_cache.csv so subsequent loads are instant; use "Rescan" to refresh.
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
    page_title="Growth Leaders | NSE Screener",
    page_icon="📈",
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
#MainMenu { visibility: hidden; } footer { visibility: hidden; }
header[data-testid="stHeader"] {
    background-color: #131722 !important; border-bottom: 1px solid #2a2e39 !important; box-shadow: none !important;
}
[data-testid="stToolbarActions"] { visibility: hidden; }

.gl-banner {
    background: linear-gradient(90deg,#1e222d 0%,#131722 100%);
    border:1px solid #2a2e39; border-left:3px solid #26a69a;
    border-radius:8px; padding:16px 24px; margin-bottom:20px;
}
.gl-banner h1 { color:#d1d4dc; font-size:1.5rem; font-weight:700; margin:0 0 2px 0; }
.gl-banner p  { color:#787b86; font-size:0.8rem; margin:0; }

.gl-table-wrap { background:#1e222d; border:1px solid #2a2e39; border-radius:8px; overflow:auto; }
.gl-table-wrap table { width:100%; border-collapse:collapse; font-size:0.82rem; }
.gl-table-wrap th {
    background:#131722; color:#787b86; font-size:0.66rem; font-weight:700;
    text-transform:uppercase; letter-spacing:0.6px; padding:10px 12px;
    border-bottom:1px solid #2a2e39; text-align:right; white-space:nowrap;
    position:sticky; top:0;
}
.gl-table-wrap th:nth-child(-n+2), .gl-table-wrap td:nth-child(-n+2) { text-align:left; }
.gl-table-wrap td {
    padding:8px 12px; border-bottom:1px solid #232733;
    color:#d1d4dc; text-align:right; white-space:nowrap;
}
.gl-table-wrap tr:hover td { background:#262b38; }
.gl-table-wrap th a { color:#787b86; text-decoration:none; }
.gl-table-wrap th a:hover { color:#d1d4dc; }
.gl-table-wrap th a.active { color:#2962ff; }
.rank { color:#787b86; font-weight:700; }
.sym  { font-weight:700; }
.held { color:#f59e0b; }
.pos  { color:#26a69a; font-weight:600; }
.neg  { color:#ef5350; font-weight:600; }
.na   { color:#50535e; }
.score{ color:#2962ff; font-weight:700; }
</style>
""", unsafe_allow_html=True)

APP_DIR    = Path(__file__).resolve().parent.parent
CACHE_FILE = APP_DIR / "growth_cache.csv"

# ── Universe ───────────────────────────────────────────────────────
@st.cache_data(ttl=86400, show_spinner=False)
def get_universe() -> pd.DataFrame:
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/csv,*/*"}
    for fname in ("ind_niftytotalmarket_list.csv", "ind_nifty500list.csv"):
        try:
            r = requests.get(
                f"https://nsearchives.nseindia.com/content/indices/{fname}",
                headers=headers, timeout=15,
            )
            r.raise_for_status()
            df = pd.read_csv(StringIO(r.text))
            return df[["Symbol", "Company Name"]].rename(
                columns={"Symbol": "Symbol", "Company Name": "Name"})
        except Exception:
            continue
    return pd.DataFrame(columns=["Symbol", "Name"])


# ── Per-stock scan ─────────────────────────────────────────────────
def _yoy_pair(series: pd.Series):
    """latest value + same-quarter-prior-year value (within 60 days)."""
    s = series.dropna().sort_index()
    s.index = pd.to_datetime(s.index)
    if len(s) < 2:
        return None, None
    latest_dt, latest = s.index[-1], float(s.iloc[-1])
    target = latest_dt - pd.DateOffset(years=1)
    diffs = (s.index[:-1] - target).to_series().abs()
    if diffs.empty or diffs.min().days > 60:
        return latest, None
    return latest, float(s.iloc[diffs.argmin()])


def scan_one(sym: str) -> dict | None:
    try:
        tk = yf.Ticker(sym + ".NS")
        q = tk.quarterly_income_stmt
        if q is None or q.empty:
            return None
        try:
            mcap = tk.fast_info["marketCap"]
        except Exception:
            mcap = (tk.info or {}).get("marketCap")
        if not mcap:
            return None

        rev_row = next((r for r in ("Total Revenue", "Net Interest Income") if r in q.index), None)
        if rev_row is None:
            return None
        rev_now, rev_then = _yoy_pair(q.loc[rev_row])
        ni_now, ni_then = _yoy_pair(q.loc["Net Income"]) if "Net Income" in q.index else (None, None)
        oi_now, oi_then = _yoy_pair(q.loc["Operating Income"]) if "Operating Income" in q.index else (None, None)

        rev_yoy = ((rev_now - rev_then) / abs(rev_then) * 100) if rev_now is not None and rev_then else None
        np_yoy  = ((ni_now - ni_then) / abs(ni_then) * 100) if ni_now is not None and ni_then else None

        opm_now = opm_exp = None
        if oi_now is not None and rev_now:
            opm_now = oi_now / rev_now * 100
            if oi_then is not None and rev_then:
                opm_exp = opm_now - (oi_then / rev_then * 100)

        return {
            "Symbol": sym, "MCap ₹Cr": mcap / 1e7,
            "Rev YoY %": rev_yoy, "PAT YoY %": np_yoy,
            "OPM %": opm_now, "OPM Δ pps": opm_exp,
        }
    except Exception:
        return None


def run_scan(symbols: list[str]) -> pd.DataFrame:
    rows, done = [], 0
    bar = st.progress(0.0, text=f"Scanning 0 / {len(symbols)}…")
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(scan_one, s) for s in symbols]
        for f in as_completed(futures):
            res = f.result()
            if res:
                rows.append(res)
            done += 1
            if done % 10 == 0 or done == len(symbols):
                bar.progress(done / len(symbols), text=f"Scanning {done} / {len(symbols)}…")
    bar.empty()
    df = pd.DataFrame(rows)
    df["as_of"] = date.today().isoformat()
    df.to_csv(CACHE_FILE, index=False)
    return df


# ── Sidebar ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📈 Growth Leaders")
    min_mcap = st.number_input("Min market cap (₹ Cr)", value=500, step=100, min_value=0)
    min_rev = st.number_input("Min sales growth %", value=0, step=5)
    require_all = st.checkbox("Require all 3 positive (sales ↑, margin ↑, profit ↑)", value=True)
    top_n = st.slider("Show top N", 10, 200, 50, step=10)
    rescan = st.button("🔄 Rescan universe (~2–4 min)")

# ── Load / scan ────────────────────────────────────────────────────
universe = get_universe()
if universe.empty:
    st.error("Could not fetch NSE index constituents.")
    st.stop()

cached = None
if CACHE_FILE.exists() and not rescan:
    try:
        cached = pd.read_csv(CACHE_FILE)
    except Exception:
        cached = None

if cached is not None and not cached.empty:
    df, as_of = cached, cached["as_of"].iloc[0]
else:
    st.info(f"Scanning {len(universe)} companies — first run takes a few minutes…")
    df, as_of = run_scan(universe["Symbol"].tolist()), date.today().isoformat()

df = df.merge(universe, on="Symbol", how="left")

# Holdings badge
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

# ── Filter & rank ──────────────────────────────────────────────────
f = df[df["MCap ₹Cr"] >= min_mcap].copy()
f = f[f["Rev YoY %"] >= min_rev]
if require_all:
    f = f[(f["Rev YoY %"] > 0) & (f["PAT YoY %"] > 0) & (f["OPM Δ pps"] > 0)]

# Composite score: average percentile rank across the three growth metrics
for col in ("Rev YoY %", "PAT YoY %", "OPM Δ pps"):
    f[f"_r_{col}"] = f[col].rank(pct=True)
f["Score"] = (f[[c for c in f.columns if c.startswith("_r_")]].mean(axis=1) * 100).round(1)
f = f.sort_values("Score", ascending=False).head(top_n).reset_index(drop=True)

# ── Column sorting via clickable headers (?sort=<col>&dir=asc|desc) ─
SORTABLE = {
    "Company": "Symbol", "MCap ₹Cr": "MCap ₹Cr", "Sales YoY": "Rev YoY %",
    "Profit YoY": "PAT YoY %", "OPM": "OPM %", "Margin Δ (pps)": "OPM Δ pps",
    "Score": "Score",
}
qp = st.query_params
sort_label = qp.get("sort", "Score")
sort_dir = qp.get("dir", "desc")
if sort_label in SORTABLE:
    col = SORTABLE[sort_label]
    f = f.sort_values(
        col, ascending=(sort_dir == "asc"), na_position="last",
        key=(lambda c: c.str.lower()) if col == "Symbol" else None,
    ).reset_index(drop=True)


def th(label: str) -> str:
    if label not in SORTABLE:
        return f"<th>{label}</th>"
    active = label == sort_label
    arrow = (" ▲" if sort_dir == "asc" else " ▼") if active else ""
    next_dir = "asc" if (active and sort_dir == "desc") else "desc"
    cls = ' class="active"' if active else ""
    return (f'<th><a{cls} href="?sort={label.replace(" ", "%20")}&dir={next_dir}" '
            f'target="_self">{label}{arrow}</a></th>')

st.markdown(f"""
<div class="gl-banner">
  <h1>📈 Growth Leaders</h1>
  <p>Highest sales growth + margin expansion + profit growth (latest quarter YoY) ·
  mcap ≥ ₹{min_mcap:,.0f} Cr · {len(f)} of {len(df)} scanned companies ·
  data as of {as_of} · ★ = in your portfolio</p>
</div>
""", unsafe_allow_html=True)


# ── Table ──────────────────────────────────────────────────────────
def num(v, fmt="{:,.1f}", signed=False, color=False):
    if v is None or pd.isna(v):
        return '<td class="na">—</td>'
    txt = ("{:+,.1f}" if signed else fmt).format(v)
    cls = ("pos" if v >= 0 else "neg") if color else ""
    return f'<td class="{cls}">{txt}</td>'


body = []
for i, r in f.iterrows():
    star = ' <span class="held">★</span>' if r["Symbol"] in held else ""
    name = r["Name"] if pd.notna(r.get("Name")) else ""
    body.append(
        f"<tr><td class='rank'>{i + 1}</td>"
        f"<td><span class='sym'>{r['Symbol']}</span>{star}<br>"
        f"<span style='color:#787b86;font-size:0.7rem'>{name}</span></td>"
        + num(r["MCap ₹Cr"], "{:,.0f}")
        + num(r["Rev YoY %"], signed=True, color=True)
        + num(r["PAT YoY %"], signed=True, color=True)
        + num(r["OPM %"])
        + num(r["OPM Δ pps"], signed=True, color=True)
        + f"<td class='score'>{r['Score']:.1f}</td></tr>"
    )

st.markdown(f"""
<div class="gl-table-wrap"><table>
<thead><tr>
  <th>#</th>{th("Company")}{th("MCap ₹Cr")}{th("Sales YoY")}{th("Profit YoY")}{th("OPM")}{th("Margin Δ (pps)")}{th("Score")}
</tr></thead>
<tbody>{''.join(body)}</tbody>
</table></div>
""", unsafe_allow_html=True)

st.caption("Score = average percentile rank across sales growth, profit growth and margin "
           "expansion. Latest reported quarter vs same quarter last year (Yahoo Finance). "
           "Banks/NBFCs use Net Interest Income as sales; margin metrics may be blank for "
           "financials. Not investment advice.")
