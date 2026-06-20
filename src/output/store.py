"""Compose the final forecast.parquet that gets served to the UI.

Joins the CatBoost quantile predictions with peak-window templates and a
simple traffic-category mapping (green -> dark_red) computed from the
historical training-distribution percentiles, per corridor.

Output schema (the user-facing deliverable):
    date, road, direction,
    volume_p50, volume_p10, volume_p90,
    category,                  # green / yellow / orange / red / dark_red
    peak_start_hour, peak_end_hour,
    confidence                 # high / medium / low
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED = PROJECT_ROOT / "processed"


def category_thresholds() -> dict:
    """Per-corridor percentiles of historical daily_volume."""
    corridor = pd.read_parquet(PROCESSED / "daily_corridor.parquet")
    out = {}
    for (road, direction), sub in corridor.groupby(["road", "direction"]):
        pct = sub["daily_volume"].quantile([0.40, 0.60, 0.75, 0.90])
        out[(road, direction)] = {
            "yellow": pct[0.40],
            "orange": pct[0.60],
            "red": pct[0.75],
            "dark_red": pct[0.90],
        }
    return out


def map_category(vol: float, thr: dict) -> str:
    if vol < thr["yellow"]:
        return "green"
    if vol < thr["orange"]:
        return "yellow"
    if vol < thr["red"]:
        return "orange"
    if vol < thr["dark_red"]:
        return "red"
    return "dark_red"


def confidence(p10: float, p50: float, p90: float, days_ahead: int) -> str:
    rel_width = (p90 - p10) / max(p50, 1)
    if rel_width < 0.20 and days_ahead < 365:
        return "high"
    if rel_width < 0.35 or days_ahead < 730:
        return "medium"
    return "low"


def compose(forecast_path: Path, peaks_path: Path) -> pd.DataFrame:
    fc = pd.read_parquet(forecast_path)
    peaks = pd.read_parquet(peaks_path)
    thr = category_thresholds()

    # For category we want one threshold per (road, direction)
    fc["category"] = fc.apply(
        lambda r: map_category(r["volume_p50"], thr[(r["road"], r["direction"])]),
        axis=1,
    )

    # Peak window join: we use tagestyp from the features parquet so we need to
    # pull tagestyp in beforehand. Simplification for hackathon: join on a
    # default tagestyp inferred from weekday (w/s/u). u when school holiday.
    # The feature builder already exposes this; for completeness we re-derive
    # a coarse tagestyp here as fallback.
    fc["dow"] = pd.to_datetime(fc["date"]).dt.dayofweek
    fc["tagestyp"] = np.where(fc["dow"] == 6, "s", np.where(fc["dow"] < 5, "w", "w"))
    # We use the most populous peak window per (road, direction, dow) as a
    # safe default — proper join requires matching tagestyp.
    fallback_peak = peaks.groupby(["wochentag"]).agg(
        peak_start_hour=("peak_start_hour", "median"),
        peak_end_hour=("peak_end_hour", "median"),
    ).reset_index().rename(columns={"wochentag": "dow"})
    fc["dow_iso"] = fc["dow"] + 1  # ISO 1=Mon..7=Sun
    fc = fc.merge(fallback_peak.rename(columns={"dow": "dow_iso"}),
                  on="dow_iso", how="left")

    today = pd.Timestamp.today().normalize()
    fc["days_ahead"] = (pd.to_datetime(fc["date"]) - today).dt.days.clip(lower=0)
    fc["confidence"] = fc.apply(
        lambda r: confidence(r["volume_p10"], r["volume_p50"], r["volume_p90"], r["days_ahead"]),
        axis=1,
    )
    keep = [
        "date", "road", "direction",
        "volume_p10", "volume_p50", "volume_p90",
        "category", "peak_start_hour", "peak_end_hour", "confidence",
    ]
    return fc[keep].sort_values(["date", "road", "direction"]).reset_index(drop=True)


def main() -> None:
    # Default: take the most recent forecast file produced by the model.
    forecasts = sorted(PROCESSED.glob("forecast_*.parquet"))
    if not forecasts:
        raise SystemExit("No forecast_*.parquet found — run src.models.catboost_quantile predict first.")
    latest = forecasts[-1]
    out = compose(latest, PROCESSED / "peak_windows.parquet")
    out_path = PROCESSED / "forecast.parquet"
    out.to_parquet(out_path, index=False)
    out.to_csv(out_path.with_suffix(".csv"), index=False)
    print(f"wrote {len(out):,} rows -> {out_path}")
    print(out.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
