"""Build hourly profile templates and derive peak windows for forecasts.

Per the H4 hypothesis-validation result, grouping by
(tagestyp, weekday, season) gives intraday-profile CV ~10% — fine
enough that one template per group is usable. Finer groupings need
more data per cell than we have in 2024-2025 alone.

Two outputs:

1. ``processed/intraday_templates.parquet``
   Schema: corridor, tagestyp, dow, season, hour, share_mean
   (one row per (group, hour); each group's 24 shares sum to 1).

2. ``processed/peak_windows.parquet``
   Schema: corridor, tagestyp, dow, season, peak_start_hour, peak_end_hour
   Defined as the contiguous hours containing the central 50% of daily
   traffic (i.e. cumulative share from 25% to 75%).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DAUZ_DIR = PROJECT_ROOT / "data" / "DAUZ_2+0_1h_2023-2026"
PROCESSED = PROJECT_ROOT / "processed"


def season_of(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def parse_label(filename: str) -> str:
    base = filename.replace(".csv", "")
    rest = base.split("FG1_Lang_", 1)[1]
    station_chunk = rest.split(",", 1)[0]
    return station_chunk.split("_", 1)[1]  # drop DAUZ id


def build_templates() -> pd.DataFrame:
    frames = []
    for f in sorted(DAUZ_DIR.glob("*.csv")):
        df = pd.read_csv(f, sep=";", decimal=".")
        df["date"] = pd.to_datetime(df["datum"], format="%d.%m.%Y")
        df = df[(df["date"] >= "2024-02-01") & (df["date"] <= "2025-12-31")]
        df = df.dropna(subset=["kfz_h"])
        df["hour"] = df["t_start"].str.slice(0, 2).astype(int)
        df["month"] = df["date"].dt.month
        df["season"] = df["month"].map(season_of)
        # Days sum to compute hourly share per day
        daily = df.groupby(["date", "tagestyp", "wochentag", "season"], as_index=False).agg(
            day_total=("kfz_h", "sum")
        )
        df = df.merge(daily, on=["date", "tagestyp", "wochentag", "season"], how="left")
        df = df[df["day_total"] > 1000]
        df["share"] = df["kfz_h"] / df["day_total"]
        df["station_label"] = parse_label(f.name)
        # Group: corridor proxy by file name + (tagestyp, weekday, season).
        agg = df.groupby(
            ["station_label", "tagestyp", "wochentag", "season", "hour"], as_index=False
        ).agg(share_mean=("share", "mean"), n_days=("date", "nunique"))
        frames.append(agg)
    out = pd.concat(frames, ignore_index=True)
    return out


def derive_peak_windows(templates: pd.DataFrame) -> pd.DataFrame:
    rows = []
    keys = ["station_label", "tagestyp", "wochentag", "season"]
    for key, g in templates.groupby(keys):
        g = g.sort_values("hour")
        cum = g["share_mean"].cumsum()
        # Peak window = central 50% of cumulative share, i.e. p25..p75
        lo = g[cum >= 0.25]["hour"].iloc[0] if (cum >= 0.25).any() else 0
        hi = g[cum >= 0.75]["hour"].iloc[0] if (cum >= 0.75).any() else 23
        rows.append({
            **dict(zip(keys, key)),
            "peak_start_hour": int(lo),
            "peak_end_hour": int(hi),
            "n_days_used": int(g["n_days"].max()),
        })
    return pd.DataFrame(rows)


def main() -> None:
    PROCESSED.mkdir(exist_ok=True)
    templates = build_templates()
    templates.to_parquet(PROCESSED / "intraday_templates.parquet", index=False)
    print(f"wrote {len(templates):,} rows -> processed/intraday_templates.parquet")

    peaks = derive_peak_windows(templates)
    peaks.to_parquet(PROCESSED / "peak_windows.parquet", index=False)
    print(f"wrote {len(peaks):,} rows -> processed/peak_windows.parquet")
    print("\nSample peak windows:")
    print(peaks.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
