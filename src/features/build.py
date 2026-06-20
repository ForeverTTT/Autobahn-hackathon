"""Assemble the training feature matrix.

Joins the daily corridor table with calendar, holiday, weather,
construction, and event features. Output:
``processed/features.parquet`` keyed by (date, road, direction).

Run after the upstream tables exist:
    processed/daily_corridor.parquet           (src/data/load_dauz.py)
    Autobahn-hackathon/holidays/holiday_dates.csv (teammate)
    external/weather_daily.parquet             (scripts/fetch_weather.py)
    external/weather_climatology.parquet
    external/construction_daily.parquet        (scripts/fix_construction_data.py)
    external/special_events_daily.csv          (scripts/build_special_events.py)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED = PROJECT_ROOT / "processed"
EXTERNAL = PROJECT_ROOT / "external"
HOLIDAYS = PROJECT_ROOT / "Autobahn-hackathon" / "holidays" / "holiday_dates.csv"


def calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    d = pd.to_datetime(out["date"])
    out["dow"] = d.dt.dayofweek            # 0=Mon
    out["month"] = d.dt.month
    out["doy"] = d.dt.dayofyear
    out["is_weekend"] = out["dow"] >= 5
    out["is_friday"] = out["dow"] == 4
    out["is_saturday"] = out["dow"] == 5
    out["is_sunday"] = out["dow"] == 6
    out["dow_sin"] = np.sin(2 * np.pi * out["dow"] / 7)
    out["dow_cos"] = np.cos(2 * np.pi * out["dow"] / 7)
    out["month_sin"] = np.sin(2 * np.pi * out["month"] / 12)
    out["month_cos"] = np.cos(2 * np.pi * out["month"] / 12)
    out["doy_sin"] = np.sin(2 * np.pi * out["doy"] / 365.25)
    out["doy_cos"] = np.cos(2 * np.pi * out["doy"] / 365.25)
    # Season: 12-2 winter, 3-5 spring, 6-8 summer, 9-11 autumn
    out["season"] = pd.cut(
        out["month"], bins=[0, 2, 5, 8, 11, 12],
        labels=["winter", "spring", "summer", "autumn", "winter"],
        ordered=False,
    )
    return out


def holiday_features(df: pd.DataFrame) -> pd.DataFrame:
    """Project the holidays CSV into the strong features only.

    Per hypothesis H3 we know tagestyp=='u' == DE-BY school holiday, so
    the school-holiday flag is the single strongest holiday feature.
    Keep:
      - school holidays in DE-BY (local population) + DE-BW (upstream)
        + AT-SB/AT-TI (downstream / destination)
      - public holidays in DE-BY + AT-SB/AT-TI
      - days_to_holiday_start / days_since_holiday_end across DE-BY
      - is_school_start_day / is_school_end_day
    Drop: NL/IT/HR/CZ — too speculative for a 2-day build.
    """
    if not HOLIDAYS.exists():
        # leave columns empty so the join still works
        for col in [
            "is_school_holiday_DE_BY", "is_school_holiday_AT_SB", "is_school_holiday_AT_TI",
            "is_public_holiday_DE_BY", "is_public_holiday_AT_SB", "is_public_holiday_AT_TI",
            "days_to_holiday_start_DE_BY", "days_since_holiday_end_DE_BY",
            "is_school_start_day_DE_BY", "is_school_end_day_DE_BY",
            "holiday_overlap_count",
        ]:
            df[col] = 0
        return df

    h = pd.read_csv(HOLIDAYS, parse_dates=["date"])
    h["date"] = h["date"].dt.normalize()

    def flag(region: str, klass: str) -> pd.DataFrame:
        sub = h[(h["region_code"] == region) & (h["holiday_class"] == klass)]
        return sub[["date"]].drop_duplicates().assign(flag=1)

    base = df.copy()
    base["date"] = pd.to_datetime(base["date"]).dt.normalize()

    for region in ["DE-BY", "AT-SB", "AT-TI"]:
        for klass in ["school_holiday", "public_holiday"]:
            f = flag(region, klass)
            col = f"is_{klass[:6]}_holiday_{region.replace('-', '_')}"
            base = base.merge(f.rename(columns={"flag": col}), on="date", how="left")
            base[col] = base[col].fillna(0).astype(int)
    # NOTE: rename above produces e.g. 'is_school_holiday_DE_BY' / 'is_public_holiday_DE_BY'

    base["holiday_overlap_count"] = (
        base["is_school_holiday_DE_BY"]
        + base["is_school_holiday_AT_SB"]
        + base["is_school_holiday_AT_TI"]
        + base["is_public_holiday_DE_BY"]
        + base["is_public_holiday_AT_SB"]
        + base["is_public_holiday_AT_TI"]
    )

    # Distance-to-edge features (DE-BY only; that's the strong one)
    by_school = h[(h["region_code"] == "DE-BY") & (h["holiday_class"] == "school_holiday")]
    by_school_dates = set(by_school["date"].unique())
    # Build per-period start/end day sets.
    starts, ends = set(), set()
    if by_school_dates:
        ordered = sorted(by_school_dates)
        prev = None
        run = []
        for d in ordered:
            if prev is not None and (d - prev).days > 1:
                if run:
                    starts.add(run[0]); ends.add(run[-1])
                run = []
            run.append(d); prev = d
        if run:
            starts.add(run[0]); ends.add(run[-1])

    starts_arr = np.array(sorted(starts), dtype="datetime64[ns]")
    ends_arr = np.array(sorted(ends), dtype="datetime64[ns]")

    def days_to_next(d):
        diffs = (starts_arr - np.datetime64(d, "ns")).astype("timedelta64[D]").astype(int)
        future = diffs[diffs >= 0]
        return int(future.min()) if len(future) else 365

    def days_since_prev(d):
        diffs = (np.datetime64(d, "ns") - ends_arr).astype("timedelta64[D]").astype(int)
        past = diffs[diffs >= 0]
        return int(past.min()) if len(past) else 365

    base["days_to_holiday_start_DE_BY"] = base["date"].apply(days_to_next).clip(upper=60)
    base["days_since_holiday_end_DE_BY"] = base["date"].apply(days_since_prev).clip(upper=60)
    base["is_school_start_day_DE_BY"] = base["date"].isin(starts).astype(int)
    base["is_school_end_day_DE_BY"] = base["date"].isin(ends).astype(int)
    return base


def weather_features(df: pd.DataFrame) -> pd.DataFrame:
    """Join climatological weather. We never use observed future weather."""
    climo_path = EXTERNAL / "weather_climatology.parquet"
    if not climo_path.exists():
        for col in ["precip_prob_wet", "ice_risk_prob", "low_vis_prob_foggy",
                    "t_min_c_mean", "t_max_c_mean"]:
            df[col] = 0.0
        return df
    climo = pd.read_parquet(climo_path)
    df = df.copy()
    df["doy"] = pd.to_datetime(df["date"]).dt.dayofyear
    df = df.merge(
        climo[["doy", "precip_prob_wet", "ice_risk_prob",
               "low_vis_prob_foggy", "t_min_c_mean", "t_max_c_mean"]],
        on="doy", how="left",
    )
    return df


def construction_features(df: pd.DataFrame) -> pd.DataFrame:
    path = EXTERNAL / "construction_daily.parquet"
    if not path.exists():
        df["is_construction_active"] = False
        df["is_2_plus_0_active"] = False
        return df
    cons = pd.read_parquet(path)
    cons["date"] = pd.to_datetime(cons["date"])
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.merge(
        cons[["date", "road", "is_construction_active", "is_2_plus_0_active"]],
        on=["date", "road"], how="left",
    )
    df["is_construction_active"] = df["is_construction_active"].fillna(False).astype(bool)
    df["is_2_plus_0_active"] = df["is_2_plus_0_active"].fillna(False).astype(bool)
    return df


def event_features(df: pd.DataFrame) -> pd.DataFrame:
    path = EXTERNAL / "special_events_daily.csv"
    if not path.exists():
        df["any_event_high_impact"] = False
        df["event_impact_score"] = 0
        return df
    ev = pd.read_csv(path, parse_dates=["date"])
    impact_map = {"high": 3, "med": 2, "low": 1}
    ev["score"] = ev["impact_level"].map(impact_map)
    # Aggregate per (date, road)
    a8 = ev[ev["affects_a8_ost"]].groupby("date").agg(
        a8_score=("score", "sum"),
        a8_high=("impact_level", lambda x: (x == "high").any()),
    )
    a93 = ev[ev["affects_a93_sued"]].groupby("date").agg(
        a93_score=("score", "sum"),
        a93_high=("impact_level", lambda x: (x == "high").any()),
    )
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.merge(a8.rename(columns={
        "a8_score": "event_score_a8", "a8_high": "event_high_a8"}),
                  on="date", how="left")
    df = df.merge(a93.rename(columns={
        "a93_score": "event_score_a93", "a93_high": "event_high_a93"}),
                  on="date", how="left")
    df["event_score"] = np.where(df["road"] == "A8_Ost",
                                 df["event_score_a8"], df["event_score_a93"]).astype(float)
    df["event_score"] = df["event_score"].fillna(0)
    df["any_event_high_impact"] = np.where(
        df["road"] == "A8_Ost", df["event_high_a8"], df["event_high_a93"]
    )
    df["any_event_high_impact"] = df["any_event_high_impact"].fillna(False).astype(bool)
    return df.drop(columns=["event_score_a8", "event_score_a93",
                            "event_high_a8", "event_high_a93"])


def build_features(corridor_path: Path | None = None) -> pd.DataFrame:
    corridor_path = corridor_path or (PROCESSED / "daily_corridor.parquet")
    df = pd.read_parquet(corridor_path)
    df = calendar_features(df)
    df = holiday_features(df)
    df = weather_features(df)
    df = construction_features(df)
    df = event_features(df)
    return df


def main() -> None:
    out = build_features()
    out_path = PROCESSED / "features.parquet"
    out.to_parquet(out_path, index=False)
    print(f"wrote {len(out):,} rows -> {out_path}")
    print(f"columns ({len(out.columns)}): {list(out.columns)}")


if __name__ == "__main__":
    main()
