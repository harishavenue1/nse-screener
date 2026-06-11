"""
Deep Tech – curated universe of interesting NSE/BSE deep-tech businesses
with fundamentals (growth, profitability, valuation) from Yahoo Finance.
Themes: Defense & Space · Semis & Electronics · EV & Energy · AI, Software & Robotics
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="Deep Tech | NSE Screener",
    page_icon="🚀",
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

.dt-banner {
    background: linear-gradient(90deg,#1e222d 0%,#131722 100%);
    border:1px solid #2a2e39; border-left:3px solid #a855f7;
    border-radius:8px; padding:16px 24px; margin-bottom:20px;
}
.dt-banner h1 { color:#d1d4dc; font-size:1.5rem; font-weight:700; margin:0 0 2px 0; }
.dt-banner p  { color:#787b86; font-size:0.8rem; margin:0; }

.theme-chip {
    display:inline-block; padding:2px 8px; border-radius:10px;
    font-size:0.62rem; font-weight:700; letter-spacing:0.4px; text-transform:uppercase;
}
.chip-def  { background:#2d1f1f; color:#f87171; border:1px solid #7f1d1d; }
.chip-semi { background:#1f2937; color:#60a5fa; border:1px solid #1e40af; }
.chip-ev   { background:#1a2e1a; color:#4ade80; border:1px solid #166534; }
.chip-ai   { background:#2a1f33; color:#c084fc; border:1px solid #6b21a8; }

.dt-table-wrap { background:#1e222d; border:1px solid #2a2e39; border-radius:8px; overflow:auto; }
.dt-table-wrap table { width:100%; border-collapse:collapse; font-size:0.8rem; }
.dt-table-wrap th {
    background:#131722; color:#787b86; font-size:0.66rem; font-weight:700;
    text-transform:uppercase; letter-spacing:0.6px; padding:10px 10px;
    border-bottom:1px solid #2a2e39; text-align:right; white-space:nowrap;
    position:sticky; top:0;
}
.dt-table-wrap th:nth-child(-n+2), .dt-table-wrap td:nth-child(-n+2) { text-align:left; }
.dt-table-wrap td {
    padding:8px 10px; border-bottom:1px solid #232733;
    color:#d1d4dc; text-align:right; white-space:nowrap;
}
.dt-table-wrap td.desc { white-space:normal; min-width:260px; max-width:420px;
    color:#9aa0ae; font-size:0.74rem; line-height:1.35; }
.dt-table-wrap tr:hover td { background:#262b38; }
.sym  { font-weight:700; color:#d1d4dc; }
.held { color:#f59e0b; }
.pos  { color:#26a69a; font-weight:600; }
.neg  { color:#ef5350; font-weight:600; }
.na   { color:#50535e; }
</style>
""", unsafe_allow_html=True)

# ── Curated deep-tech universe ─────────────────────────────────────
# (symbol, name, one-liner on why the business is interesting)
UNIVERSE = {
    "Defense & Space": [
        ("HAL", "Hindustan Aeronautics", "Fighter jets (Tejas), helicopters & aero-engines; decade-long order book from Indian defense indigenisation."),
        ("BEL", "Bharat Electronics", "Defense electronics monopoly — radars, EW systems, avionics; consistent 20%+ ROE PSU."),
        ("SOLARINDS", "Solar Industries", "Industrial explosives leader pivoting into ammunition, warheads & Pinaka rockets; drone (Nagastra) supplier."),
        ("DATAPATTNS", "Data Patterns", "Vertically-integrated defense electronics — designs its own radar, avionics & satellite subsystems IP."),
        ("MTARTECH", "MTAR Technologies", "Precision machining for nuclear reactors, space (Vikas engines for ISRO) & clean energy (Bloom fuel cells)."),
        ("PARAS", "Paras Defence", "Optics & optronics for space imaging and defense; anti-drone systems; rare niche with high entry barriers."),
        ("ASTRAMICRO", "Astra Microwave", "RF & microwave subsystems for radars, missiles and satellites; key DRDO/ISRO supplier."),
        ("AZAD", "Azad Engineering", "Airfoils & turbine components for Rolls-Royce, GE, Boeing; only Indian qualified vendor for several parts."),
        ("IDEAFORGE", "ideaForge", "India's largest military drone maker — surveillance UAVs for army & homeland security."),
        ("ZENTEC", "Zen Technologies", "Combat training simulators & anti-drone systems with strong IP; recurring annuity revenues."),
        ("DCXINDIA", "DCX Systems", "Cable harnesses & system integration for Israeli defense majors (IAI, ELTA); offset beneficiary."),
        ("DYNAMATECH", "Dynamatic Tech", "Aerostructures for Airbus (flap-track beams) & Boeing; hydraulic pumps; deep aerospace moat."),
    ],
    "Semis & Electronics": [
        ("KAYNES", "Kaynes Technology", "End-to-end electronics manufacturing + entering OSAT (chip packaging) with own fab in Sanand."),
        ("SYRMA", "Syrma SGS", "High-mix EMS across auto, medical, industrial; growing exports and design-led (ODM) share."),
        ("DIXON", "Dixon Technologies", "India's largest EMS — phones, IT hardware via PLI; operating-leverage compounder."),
        ("CGPOWER", "CG Power", "Murugappa-backed motors & transformers leader; building India's first OSAT chip plant with Renesas."),
        ("NETWEB", "Netweb Technologies", "Indigenous AI servers, HPC clusters & private-cloud appliances; NVIDIA partner riding AI capex."),
        ("TATAELXSI", "Tata Elxsi", "Embedded software & design for auto (SDV), medical devices and media; high-margin ER&D."),
        ("MOSCHIP", "MosChip Technologies", "India's only listed fabless semiconductor design house — ASICs, mixed-signal IP."),
        ("IZMO", "izmo Ltd", "Auto dealer software + FrogData AI; pivoting into semiconductor SiP packaging incl. silicon photonics (izmoMicro)."),
        ("AVALON", "Avalon Technologies", "Box-build EMS with large US revenue share — clean rooms, rail, aerospace verticals."),
        ("CYIENTDLM", "Cyient DLM", "Build-to-spec electronics for aerospace & medical — long-cycle, high-reliability niches."),
        ("TEJASNET", "Tejas Networks", "Tata-owned telecom equipment — optical, 4G/5G RAN (BSNL rollout), wireless backhaul R&D."),
        ("AMBER", "Amber Enterprises", "AC components king diversifying into electronics (PCBA) & railway subsystems."),
    ],
    "EV & Energy": [
        ("SEDEMAC", "Sedemac Mechatronics", "Control algorithms IP — world-first sensorless ISG, EFI ECUs & EV motor controllers; Tier-1 to TVS/Bajaj/Kirloskar."),
        ("ATHERENERG", "Ather Energy", "Premium electric scooters with own software stack (Atherstack) & fast-charging grid."),
        ("OLAELEC", "Ola Electric", "Largest e-2W maker; vertically integrating into own 4680 battery cells (gigafactory)."),
        ("EXICOM", "Exicom Tele-Systems", "EV chargers (home + DC fast) & telecom power; acquired Tritium for global DC fast-charging."),
        ("TATATECH", "Tata Technologies", "ER&D services focused on EV/SDV engineering for OEMs incl. VinFast, JLR."),
        ("HBLENGINE", "HBL Engineering", "Train collision-avoidance (KAVACH) leader + specialty defense batteries; electronics-led rerating."),
        ("EXIDEIND", "Exide Industries", "Lead-acid leader building 12 GWh lithium-cell plant with SVOLT tech; Hyundai/Kia tie-up."),
        ("ARE&M", "Amara Raja", "Batteries major investing in giga corridor for Li-ion cells & chargers."),
        ("WAAREEENER", "Waaree Energies", "India's largest solar module maker (13+ GW), expanding into cells, ingots & US fab."),
        ("SERVOTECH", "Servotech Renewable", "Fast-growing EV charger & solar EPC small-cap; DC fast-charger manufacturing."),
        ("POWERINDIA", "Hitachi Energy India", "HVDC & grid-automation tech for India's renewables build-out; scarce pure-play grid tech."),
    ],
    "AI, Software & Robotics": [
        ("AFFLE", "Affle 3i", "Ad-tech with consumer-intelligence platform; proprietary AI for conversion-based mobile ads."),
        ("KPITTECH", "KPIT Technologies", "Pure-play software-defined-vehicle engineering; partnerships with global OEM majors."),
        ("LTTS", "L&T Technology Services", "Diversified ER&D — digital twins, autonomous transport, med-tech engineering."),
        ("CYIENT", "Cyient", "Geospatial, aerospace engineering & semiconductor design services (Cyient Semiconductors)."),
        ("NEWGEN", "Newgen Software", "Low-code enterprise automation platform with GenAI (LumYn) layer; sticky BFSI clients."),
        ("E2E", "E2E Networks", "GPU cloud for AI training/inference — NVIDIA H200/GB200 clusters; L&T-backed sovereign AI play."),
        ("RTNINDIA", "RattanIndia Enterprises", "Drones (NeoSky), e-commerce & fintech incubator; Revolt EV motorcycles."),
        ("HONAUT", "Honeywell Automation", "Industrial automation & building tech MNC arm — process control, warehouse robotics."),
        ("ABB", "ABB India", "Factory electrification, motion & robotics portfolio riding India capex/automation cycle."),
    ],
}

CHIP_CLASS = {
    "Defense & Space": "chip-def",
    "Semis & Electronics": "chip-semi",
    "EV & Energy": "chip-ev",
    "AI, Software & Robotics": "chip-ai",
}

# Portfolio overlap badge
HOLDINGS_FILE = Path(__file__).resolve().parent.parent / "holdings.json"
held_symbols: set[str] = set()
if HOLDINGS_FILE.exists():
    try:
        for h in json.loads(HOLDINGS_FILE.read_text())["holdings"]:
            base = h["symbol"]
            for sfx in ("-BE", "-BZ", "-SM", "-ST", "-BL"):
                if base.endswith(sfx):
                    base = base[: -len(sfx)]
            held_symbols.add(base)
    except Exception:
        pass


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fundamentals(symbols: tuple[str, ...]) -> dict[str, dict]:
    """Pull key .info fundamentals for each symbol (NSE, fallback BSE)."""
    def one(sym: str) -> tuple[str, dict]:
        for suffix in (".NS", ".BO"):
            try:
                info = yf.Ticker(sym + suffix).info or {}
                if info.get("marketCap"):
                    return sym, info
            except Exception:
                continue
        return sym, {}

    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(one, s) for s in symbols]
        for f in as_completed(futures):
            sym, info = f.result()
            out[sym] = info
    return out


def g(info: dict, key: str, mult: float = 1.0):
    v = info.get(key)
    return v * mult if isinstance(v, (int, float)) else None


# ── Sidebar ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🚀 Deep Tech")
    themes = st.multiselect("Themes", list(UNIVERSE), default=list(UNIVERSE))
    sort_by = st.selectbox("Sort by", [
        "MCap ₹Cr", "Rev YoY %", "Earnings YoY %", "ROE %", "OPM %",
        "P/E", "P/S", "1Y %", "Symbol",
    ])
    ascending = st.checkbox("Ascending", value=False)
    only_held = st.checkbox("Only my holdings", value=False)
    if st.button("🔄 Refresh data"):
        fetch_fundamentals.clear()
        st.rerun()

# ── Fetch ──────────────────────────────────────────────────────────
selected = [(t, s, n, d) for t in themes for (s, n, d) in UNIVERSE[t]]
symbols = tuple(s for _, s, _, _ in selected)
with st.spinner(f"Fetching fundamentals for {len(symbols)} companies…"):
    infos = fetch_fundamentals(symbols)

rows = []
for theme, sym, name, desc in selected:
    info = infos.get(sym, {})
    rows.append({
        "Theme": theme, "Symbol": sym, "Name": name, "Desc": desc,
        "Held": sym in held_symbols,
        "MCap ₹Cr": g(info, "marketCap", 1e-7),
        "P/E": g(info, "trailingPE"),
        "P/S": g(info, "priceToSalesTrailing12Months"),
        "Rev YoY %": g(info, "revenueGrowth", 100),
        "Earnings YoY %": g(info, "earningsGrowth", 100),
        "ROE %": g(info, "returnOnEquity", 100),
        "OPM %": g(info, "operatingMargins", 100),
        "D/E": g(info, "debtToEquity"),
        "1Y %": g(info, "52WeekChange", 100),
    })

df = pd.DataFrame(rows)
if only_held:
    df = df[df["Held"]]
df = df.sort_values(sort_by, ascending=ascending, na_position="last",
                    key=(lambda c: c.str.lower()) if sort_by == "Symbol" else None)

held_count = int(df["Held"].sum())
st.markdown(f"""
<div class="dt-banner">
  <h1>🚀 Deep Tech — Interesting Businesses</h1>
  <p>{len(df)} curated NSE/BSE companies across Defense &amp; Space, Semiconductors &amp; Electronics,
  EV &amp; Energy, and AI/Software/Robotics · ★ = in your portfolio ({held_count}) ·
  fundamentals via Yahoo Finance (TTM)</p>
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
for _, r in df.iterrows():
    star = ' <span class="held">★</span>' if r["Held"] else ""
    chip = f'<span class="theme-chip {CHIP_CLASS[r["Theme"]]}">{r["Theme"]}</span>'
    body.append(
        f"<tr><td><span class='sym'>{r['Symbol']}</span>{star}<br>"
        f"<span style='color:#787b86;font-size:0.7rem'>{r['Name']}</span><br>{chip}</td>"
        f"<td class='desc'>{r['Desc']}</td>"
        + num(r["MCap ₹Cr"], "{:,.0f}")
        + num(r["P/E"])
        + num(r["P/S"])
        + num(r["Rev YoY %"], signed=True, color=True)
        + num(r["Earnings YoY %"], signed=True, color=True)
        + num(r["ROE %"])
        + num(r["OPM %"])
        + num(r["D/E"], "{:,.0f}")
        + num(r["1Y %"], signed=True, color=True)
        + "</tr>"
    )

st.markdown(f"""
<div class="dt-table-wrap"><table>
<thead><tr>
  <th>Company</th><th>Why interesting</th><th>MCap ₹Cr</th><th>P/E</th><th>P/S</th>
  <th>Rev YoY</th><th>Earn YoY</th><th>ROE</th><th>OPM</th><th>D/E %</th><th>1Y Ret</th>
</tr></thead>
<tbody>{''.join(body)}</tbody>
</table></div>
""", unsafe_allow_html=True)

st.caption("Curated list, not investment advice. Growth = latest quarter YoY (Yahoo TTM "
           "fields); '—' = not reported. Data cached 1 hour — use Refresh in the sidebar.")
