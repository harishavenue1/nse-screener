"""
Demand Zone Scanner – Nifty 500 Weekly
Translates BigBeluga's Supply and Demand Zones (Pine Script v6) to Python.

Logic:
  Demand zone triggered when:
    • 3 consecutive bullish candles (close > open)
    • Volume at bar[-1] above rolling average
    • 15-bar cooldown between signals
    • Look back up to 5 bars for first bearish candle → zone anchor
    • Zone: top = anchor_high, bottom = anchor_high − ATR(200)×2
  Zone invalidated when close < zone bottom.
  Stock flagged when current price is inside an active zone.
"""

import pandas as pd
import numpy as np
import requests
import yfinance as yf
from io import StringIO
from datetime import datetime
import time
import sys

# ─── CONFIG ──────────────────────────────────────────────────────────────────
ATR_PERIOD  = 200
COOLDOWN    = 15   # bars between demand zone signals
MAX_ZONES   = 5
VOL_WINDOW  = 1000
WEEKS_BACK  = 300  # need >200 weeks for ATR(200) to warm up
# ─────────────────────────────────────────────────────────────────────────────


def get_nifty500_symbols() -> list[str]:
    url = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/csv,*/*"}
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    df = pd.read_csv(StringIO(r.text))
    return df["Symbol"].str.strip().tolist()


def fetch_weekly(symbol: str) -> pd.DataFrame | None:
    ticker = symbol + ".NS"
    try:
        df = yf.download(
            ticker,
            period=f"{WEEKS_BACK}wk",
            interval="1wk",
            auto_adjust=True,
            progress=False,
            timeout=20,
        )
    except Exception:
        return None

    if df is None or len(df) < ATR_PERIOD + 10:
        return None

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df = df.dropna(subset=["open", "close"])
    df.index = pd.to_datetime(df.index)
    return df


def _atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """Wilder's ATR (RMA) × 2, matching Pine Script ta.atr(200)*2."""
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    # RMA = EWM with alpha=1/period, adjust=False
    return tr.ewm(alpha=1 / period, adjust=False).mean() * 2


def detect_demand_zones(df: pd.DataFrame):
    """
    Bar-by-bar simulation of the Pine Script demand zone logic.
    Returns (active_zones, zones_containing_price, current_price).
    """
    df = df.copy()
    df["bull"] = (df["close"] > df["open"]).astype(bool)
    df["bear"] = (df["close"] < df["open"]).astype(bool)

    n = min(VOL_WINDOW, len(df))
    df["vol_avg"] = df["volume"].rolling(window=n, min_periods=20).mean()
    df["extra_vol"] = df["volume"] > df["vol_avg"]
    df["atr2"] = _atr(df)

    # Pre-extract numpy arrays for speed
    bull      = df["bull"].values
    bear      = df["bear"].values
    extra_vol = df["extra_vol"].values
    atr2      = df["atr2"].values
    high      = df["high"].values
    close     = df["close"].values
    dates     = df.index

    demand_zones: list[dict] = []
    count_bull = 0

    for idx in range(2, len(df)):
        cur_close = close[idx]

        # Remove zones invalidated by price closing below zone bottom
        demand_zones = [z for z in demand_zones if cur_close >= z["bottom"]]

        three_bull = bool(bull[idx]) and bool(bull[idx - 1]) and bool(bull[idx - 2])
        ev         = bool(extra_vol[idx - 1])  # extra_vol[1] in Pine = prev bar
        atr_val    = float(atr2[idx])

        if three_bull and ev and count_bull == 0 and not np.isnan(atr_val):
            for i in range(6):  # i=0..5
                if idx - i < 0:
                    break
                if bear[idx - i]:
                    top    = float(high[idx - i])
                    bottom = top - atr_val
                    demand_zones.append(
                        {
                            "top":         top,
                            "bottom":      bottom,
                            "anchor_date": dates[idx - i].date(),
                        }
                    )
                    count_bull = 1
                    break

        if count_bull >= 1:
            count_bull += 1
        if count_bull >= COOLDOWN:
            count_bull = 0

        # Keep only most recent MAX_ZONES zones
        if len(demand_zones) > MAX_ZONES:
            demand_zones = demand_zones[-MAX_ZONES:]

    current_price = float(close[-1])
    in_zone = [z for z in demand_zones if z["bottom"] <= current_price <= z["top"]]
    return demand_zones, in_zone, current_price


def scan():
    print("=" * 65)
    print("  Demand Zone Scanner  –  Nifty 500  –  Weekly")
    print(f"  {datetime.today().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 65)

    print("\n[1/3] Fetching Nifty 500 symbol list from NSE…")
    try:
        symbols = get_nifty500_symbols()
    except Exception as e:
        print(f"  ERROR: {e}")
        sys.exit(1)
    print(f"  → {len(symbols)} symbols loaded")

    print(f"\n[2/3] Scanning {len(symbols)} stocks for demand zones…\n")

    results = []
    total   = len(symbols)

    for i, sym in enumerate(symbols, 1):
        label = f"[{i:3d}/{total}] {sym:<12}"
        df = fetch_weekly(sym)

        if df is None:
            print(f"{label}  skip (no data)")
            continue

        try:
            all_zones, in_zone, price = detect_demand_zones(df)
        except Exception as e:
            print(f"{label}  ERROR: {e}")
            continue

        if in_zone:
            z = in_zone[0]  # closest / most relevant zone
            depth_pct = (price - z["bottom"]) / (z["top"] - z["bottom"]) * 100
            print(
                f"{label}  ✅ IN ZONE  "
                f"price={price:>9.2f}  "
                f"zone=[{z['bottom']:.2f} – {z['top']:.2f}]  "
                f"depth={depth_pct:.0f}%  "
                f"anchor={z['anchor_date']}"
            )
            for z in in_zone:
                results.append(
                    {
                        "Symbol":       sym,
                        "Price":        round(price, 2),
                        "Zone Bottom":  round(z["bottom"], 2),
                        "Zone Top":     round(z["top"], 2),
                        "Depth %":      round(
                            (price - z["bottom"]) / (z["top"] - z["bottom"]) * 100, 1
                        ),
                        "Zone Anchor":  z["anchor_date"],
                        "Active Zones": len(all_zones),
                    }
                )
        else:
            print(f"{label}  – {len(all_zones)} zone(s), price={price:.2f}")

        # yfinance is polite but avoid hammering
        time.sleep(0.1)

    print("\n" + "=" * 65)
    print("[3/3] Results")
    print("=" * 65)

    if results:
        out = (
            pd.DataFrame(results)
            .sort_values("Depth %")
            .reset_index(drop=True)
        )
        print(out.to_string(index=False))
        out_path = "/Users/harishkp/demand_zone_results.csv"
        out.to_csv(out_path, index=False)
        print(f"\n  Saved → {out_path}")
        print(f"  Total stocks in demand zone: {len(results)}")
    else:
        print("  No stocks found in demand zones.")

    return results


if __name__ == "__main__":
    scan()