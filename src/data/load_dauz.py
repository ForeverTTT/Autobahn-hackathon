"""Load DAUZ hourly tables and aggregate to per-station daily volume.

Why this module exists
----------------------
The DAUZ (Dauerzählstelle) CSVs are the cleanest source of vehicle counts.
Each file is one (station, direction). We:

1. parse with the right dtypes (devices column is a string, datum is
   German DD.MM.YYYY).
2. drop the unreliable window: Gletschergarten was offline all of 2023,
   Kiefersfelden_Kff DE33,34 was dead 2023-07..2023-12. We use only
   2024-02-01..2025-12-31 by default (the "clean window" per
   docs/station_reliability_report.md).
3. aggregate kfz_h to daily_volume per (date, station, direction).

Public functions
----------------
- load_dauz_hourly(file): one tidy DataFrame, hour-level
- build_station_daily(): per-station daily volume, all clean stations
- build_corridor_daily(): four-corridor representation
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DAUZ_DIR = PROJECT_ROOT / "data" / "DAUZ_2+0_1h_2023-2026"
PROCESSED_DIR = PROJECT_ROOT / "processed"

# The clean window across all 12 stations per the reliability report.
CLEAN_START = "2024-02-01"
CLEAN_END = "2025-12-31"

# One representative station per (road, direction). Picked for completeness
# in the clean window. See docs/final_plan.md §2.
CORRIDOR_REP = {
    ("A8_Ost", "outbound"): "MQQ37_Sbg_H",
    ("A8_Ost", "inbound"):  "MQQ209_Mch_H",
    ("A93_Sued", "outbound"): "MQDZ_AD_Inntal_Kff",
    ("A93_Sued", "inbound"):  "MQDZ_AD_Inntal_Ro",
}


def parse_station_meta(filename: str) -> dict:
    """Filename -> {station, direction_short, lanes, road}.

    Examples:
        FG1_Lang_9171_MQB25_Mch_H,DE33,34,35,36_agg1h_..._bis_....csv
        FG1_Lang_9190_MQDZ_AD Inntal_(S)_Kff,DE33,34_agg1h_..._bis_....csv
    """
    base = filename.replace(".csv", "")
    rest = base.split("FG1_Lang_", 1)[1]
    # rest example: 9171_MQB25_Mch_H,DE33,34,35,36_agg1h_2023-01-01_bis_2026-01-01
    station_chunk, lane_chunk = rest.split(",", 1)
    # station_chunk: 9171_MQB25_Mch_H
    parts = station_chunk.split("_")
    dauz_id = parts[0]
    direction = parts[-1] if parts[-1] in {"H"} else parts[-1]  # may be H, Ro, Kff
    # Reconstruct station (everything between dauz_id and direction)
    station_parts = parts[1:-1] if parts[-1] in {"H"} and parts[-2] in {"Mch", "Sbg"} else parts[1:]
    if parts[-1] in {"H"} and parts[-2] in {"Mch", "Sbg"}:
        station_parts = parts[1:-2]
        direction = "_".join(parts[-2:])  # Mch_H or Sbg_H
    elif parts[-1] in {"Ro", "Kff", "Ros"}:
        station_parts = parts[1:-1]
        direction = parts[-1]
    station = "_".join(station_parts)
    # lane_chunk example: DE33,34,35,36_agg1h_2023-01-01_bis_2026-01-01
    lanes = lane_chunk.split("_agg1h")[0]
    # Road
    if station.startswith("MQDZ_AD Inntal") or station.startswith("MQDZ_Kiefersfelden") or station.startswith("MQ_Gletschergarten"):
        road = "A93_Sued"
    else:
        road = "A8_Ost"
    return {
        "dauz_id": dauz_id, "station": station, "direction_short": direction,
        "lanes": lanes, "road": road,
        "label": f"{station}_{direction}",
    }


def load_dauz_hourly(file_path: Path) -> pd.DataFrame:
    """Load one DAUZ hourly CSV with proper types."""
    df = pd.read_csv(file_path, sep=";", decimal=".")
    df["date"] = pd.to_datetime(df["datum"], format="%d.%m.%Y")
    df["hour"] = df["t_start"].str.slice(0, 2).astype(int)
    df["sv_share"] = df["sv_h"] / df["kfz_h"]
    meta = parse_station_meta(file_path.name)
    for k, v in meta.items():
        df[k] = v
    return df


def build_station_daily(clean_window: bool = True) -> pd.DataFrame:
    """Aggregate every DAUZ file to daily totals per station/direction.

    Returns a DataFrame with one row per (date, label) and columns:
    daily_volume, sv_daily, sv_share, n_hours_observed,
    road, station, direction_short, direction (outbound/inbound),
    tagestyp, wochentag, label.

    Pass this DataFrame directly to build_features() via the corridor_path
    argument to train or predict for all 12 stations instead of the 4
    representative corridor nodes.
    """
    frames = []
    for f in sorted(DAUZ_DIR.glob("*.csv")):
        df = load_dauz_hourly(f)
        if clean_window:
            df = df[(df["date"] >= CLEAN_START) & (df["date"] <= CLEAN_END)]
        # Drop hours with missing kfz_h before summing — keep the count so
        # we can flag near-empty days.
        df = df.dropna(subset=["kfz_h"])
        agg = (
            df.groupby(["date", "label", "station", "direction_short", "road"], as_index=False)
              .agg(
                  daily_volume=("kfz_h", "sum"),
                  sv_daily=("sv_h", "sum"),
                  n_hours_observed=("kfz_h", "size"),
                  tagestyp=("tagestyp", "first"),
                  wochentag=("wochentag", "first"),
              )
        )
        # Days with <20 observed hours are unreliable.
        agg = agg[agg["n_hours_observed"] >= 20]
        agg["sv_share"] = agg["sv_daily"] / agg["daily_volume"]
        agg["direction"] = agg.apply(
            lambda r: map_direction(r["road"], r["direction_short"]), axis=1
        )
        # Expose station_label as a column so models can use it as a
        # categorical feature when predicting for all stations.
        agg = agg.rename(columns={"label": "station_label"})
        frames.append(agg)
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(["date", "station_label"]).reset_index(drop=True)


def map_direction(road: str, direction_short: str) -> str:
    """Return outbound/inbound for the corridor."""
    if road == "A8_Ost":
        if direction_short == "Sbg_H":
            return "outbound"   # to Salzburg (alps)
        if direction_short == "Mch_H":
            return "inbound"    # to München
    if road == "A93_Sued":
        if direction_short == "Kff":
            return "outbound"   # to Kufstein (alps/border)
        if direction_short == "Ro":
            return "inbound"    # to Rosenheim
    return "unknown"


def build_corridor_daily() -> pd.DataFrame:
    """Daily series keyed by (date, road, direction).

    Uses the representative station per corridor (see CORRIDOR_REP). For
    A93 inbound we currently fall back to AD Inntal because Gletschergarten
    only became reliable in 2024-02.

    To train/predict for all 12 stations instead, use build_station_daily()
    directly and pass its output to src.features.build.build_features().
    """
    station_daily = build_station_daily()
    station_daily["corridor"] = station_daily["road"] + "_" + station_daily["direction"]

    # Pick representative rows.
    rep_labels = set()
    for (road, direction), station in CORRIDOR_REP.items():
        sub = station_daily[(station_daily["road"] == road) & (station_daily["direction"] == direction)]
        match = sub[sub["station"] == station.replace("_Sbg_H", "").replace("_Mch_H", "").replace("_Ro", "").replace("_Kff", "")]
        if match.empty:
            best = sub.groupby("station_label")["date"].count().idxmax()
            rep_labels.add(best)
        else:
            rep_labels.add(match["station_label"].iloc[0])

    rep_df = station_daily[station_daily["station_label"].isin(rep_labels)].copy()
    out = rep_df.groupby(["date", "road", "direction"], as_index=False).agg(
        daily_volume=("daily_volume", "sum"),
        sv_share=("sv_share", "mean"),
        tagestyp=("tagestyp", "first"),
        wochentag=("wochentag", "first"),
    )
    return out


def main() -> None:
    """CLI: write processed/daily_*.parquet.

    daily_station.parquet  — all 12 stations, with station_label column
    daily_corridor.parquet — 4 representative corridor nodes (default for training)
    """
    PROCESSED_DIR.mkdir(exist_ok=True)
    station = build_station_daily()
    station.to_parquet(PROCESSED_DIR / "daily_station.parquet", index=False)
    print(f"wrote {len(station):,} rows -> processed/daily_station.parquet")
    print(f"  stations: {sorted(station['station_label'].unique())}")
    corridor = build_corridor_daily()
    corridor.to_parquet(PROCESSED_DIR / "daily_corridor.parquet", index=False)
    print(f"wrote {len(corridor):,} rows -> processed/daily_corridor.parquet")
    print("\nCorridor coverage:")
    print(corridor.groupby(["road", "direction"])["date"].agg(["min", "max", "count"]))


if __name__ == "__main__":
    main()
