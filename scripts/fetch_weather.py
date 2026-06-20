"""Fetch daily weather for the A8-Ost / A93-Sued corridor.

The model only needs three quantities (per the team's call):

* precipitation_mm — daily total rainfall
* low_vis_hours    — daily count of hours with cloud_cover_low >= 85%
                     (Open-Meteo Archive does NOT publish visibility for
                     this region, so we use low-cloud cover as a proxy:
                     dense low cloud at low temperature ≈ fog).
* has_ice_risk     — boolean: any hour with snowfall > 0 OR
                     temperature_2m < 0

Single weather point: the AD Rosenheim interchange (47.83 N, 12.13 E) —
this matches the existing LT/FBT sensor location at A8 km 54.6 and is the
central node where A8-Ost meets A93-Sued. The corridor is short enough
(~100 km on A8-Ost, ~25 km on A93-Sued) that one weather point is fine
for daily forecasting; we are not running a meso-scale model.

Source: Open-Meteo Archive API (free, no key needed). It blends
ECMWF ERA5 + ICON reanalysis; daily aggregates from hourly fields.

Outputs (under external/):
  weather_daily.parquet           - one row per date, raw aggregates
                                    Schema: date, precip_mm, vis_min_km,
                                    has_ice_risk, t_min_c, t_max_c, snowfall_mm
  weather_climatology.parquet     - per (day_of_year) climatological stats
                                    over 2018-2025, used for forecasting
                                    2026-2029 (since future weather is unknown).

Usage::

    python scripts/fetch_weather.py                     # default 2018-2025
    python scripts/fetch_weather.py --start 2020-01-01  # custom range
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib import request, error

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "external"
OUT_DIR.mkdir(exist_ok=True)

# AD Rosenheim interchange (A8 x A93). Matches the existing LT/FBT sensor at
# A8 km 54.6 documented in CLAUDE.md.
LAT, LON = 47.83, 12.13
LOCATION_NAME = "AD_Rosenheim"

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_year(year: int) -> pd.DataFrame:
    """Fetch one year of hourly data from Open-Meteo Archive and return raw."""
    params = {
        "latitude": LAT,
        "longitude": LON,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "hourly": "temperature_2m,precipitation,snowfall,cloud_cover_low",
        "timezone": "Europe/Berlin",
    }
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{ARCHIVE_URL}?{qs}"
    print(f"  fetching {year} ...")
    try:
        with request.urlopen(url, timeout=60) as r:
            payload = json.load(r)
    except error.URLError as exc:
        print(f"    network error: {exc}", file=sys.stderr)
        raise

    hourly = payload["hourly"]
    df = pd.DataFrame({
        "time": pd.to_datetime(hourly["time"]),
        "t_2m": hourly["temperature_2m"],
        "precip": hourly["precipitation"],
        "snowfall": hourly["snowfall"],
        "low_cloud_pct": hourly["cloud_cover_low"],
    })
    return df


def aggregate_to_daily(hourly: pd.DataFrame) -> pd.DataFrame:
    hourly = hourly.copy()
    hourly["date"] = hourly["time"].dt.date
    # Ice risk: any hour with snowfall > 0 mm or t < 0 °C
    hourly["ice_hour"] = (hourly["snowfall"].fillna(0) > 0) | (hourly["t_2m"] < 0)
    hourly["low_vis_hour"] = hourly["low_cloud_pct"] >= 85
    daily = hourly.groupby("date").agg(
        precip_mm=("precip", "sum"),
        snowfall_mm=("snowfall", "sum"),
        low_vis_hours=("low_vis_hour", "sum"),
        t_min_c=("t_2m", "min"),
        t_max_c=("t_2m", "max"),
        has_ice_risk=("ice_hour", "any"),
    ).reset_index()
    daily["date"] = pd.to_datetime(daily["date"])
    return daily


def compute_climatology(daily: pd.DataFrame) -> pd.DataFrame:
    """For each day-of-year (1..366), aggregate across all years."""
    d = daily.copy()
    d["doy"] = d["date"].dt.dayofyear
    grouped = d.groupby("doy").agg(
        precip_mm_mean=("precip_mm", "mean"),
        precip_mm_p90=("precip_mm", lambda s: s.quantile(0.90)),
        precip_prob_wet=("precip_mm", lambda s: float((s > 1.0).mean())),
        low_vis_hours_mean=("low_vis_hours", "mean"),
        low_vis_prob_foggy=("low_vis_hours", lambda s: float((s >= 6).mean())),
        ice_risk_prob=("has_ice_risk", "mean"),
        t_min_c_mean=("t_min_c", "mean"),
        t_max_c_mean=("t_max_c", "mean"),
        n_years=("date", "nunique"),
    ).reset_index()
    return grouped


def main(start_year: int, end_year: int, force: bool = False) -> None:
    daily_path = OUT_DIR / "weather_daily.parquet"
    climo_path = OUT_DIR / "weather_climatology.parquet"

    if daily_path.exists() and not force:
        existing = pd.read_parquet(daily_path)
        have_years = sorted(existing["date"].dt.year.unique())
        print(f"Existing weather_daily.parquet covers years {have_years}.")
    else:
        existing = pd.DataFrame()
        have_years = []

    new_frames = []
    for year in range(start_year, end_year + 1):
        if year in have_years and not force:
            continue
        try:
            hourly = fetch_year(year)
        except Exception as exc:
            print(f"  giving up on {year}: {exc}", file=sys.stderr)
            continue
        new_frames.append(aggregate_to_daily(hourly))
        time.sleep(1)  # be polite to the public API

    if new_frames:
        new_daily = pd.concat(new_frames, ignore_index=True)
        if not existing.empty:
            full = pd.concat([existing, new_daily], ignore_index=True)
            full = full.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
        else:
            full = new_daily.sort_values("date").reset_index(drop=True)
        full.to_parquet(daily_path, index=False)
        print(f"Wrote {daily_path}  ({len(full):,} rows)")
    else:
        full = existing

    if not full.empty:
        climo = compute_climatology(full)
        climo.to_parquet(climo_path, index=False)
        print(f"Wrote {climo_path}  ({len(climo):,} rows, one per doy)")
        # Quick sanity summary
        print("\nClimatology summary (representative rows):")
        for doy in [15, 105, 196, 288]:  # mid-Jan, mid-Apr, mid-Jul, mid-Oct
            row = climo[climo["doy"] == doy].iloc[0]
            label = pd.Timestamp("2024-01-01") + pd.Timedelta(days=doy - 1)
            print(
                f"  doy {doy:3d} ({label:%b %d}):"
                f"  precip_prob_wet={row['precip_prob_wet']:.2f}"
                f"  ice_risk={row['ice_risk_prob']:.2f}"
                f"  fog_prob={row['low_vis_prob_foggy']:.2f}"
                f"  t[{row['t_min_c_mean']:+.1f},{row['t_max_c_mean']:+.1f}]°C"
            )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--end", default="2025-12-31")
    p.add_argument("--force", action="store_true", help="re-download even if cached")
    a = p.parse_args()
    main(int(a.start[:4]), int(a.end[:4]), force=a.force)
