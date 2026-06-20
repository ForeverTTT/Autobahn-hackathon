"""Train CatBoost quantile regression (P10/P50/P90) per corridor.

The training-data is processed/features.parquet built by
src/features/build.py. Target is daily_volume.

This module is intentionally minimal — one cat_features list, three
models (one per quantile), saved as .cbm. SHAP via the standard
CatBoost shap_values interface.

Usage::

    python -m src.models.catboost_quantile train      # train 3 quantile models
    python -m src.models.catboost_quantile predict 2026-01-01 2029-12-31
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

# CatBoost is the only heavy dependency; install via `pip install catboost`.
try:
    from catboost import CatBoostRegressor, Pool
except ImportError as exc:
    raise SystemExit(
        "catboost is not installed.  Run:\n"
        "    .venv/bin/pip install catboost\n"
    ) from exc


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED = PROJECT_ROOT / "processed"
MODELS_DIR = PROJECT_ROOT / "models"
MODELS_DIR.mkdir(exist_ok=True)


FEATURE_COLS = [
    # static — corridor identity (always present)
    "road", "direction",
    # calendar
    "dow", "month", "doy", "is_weekend", "is_friday", "is_saturday", "is_sunday",
    "dow_sin", "dow_cos", "month_sin", "month_cos", "doy_sin", "doy_cos", "season",
    # holidays
    "is_school_holiday_DE_BY", "is_school_holiday_AT_SB", "is_school_holiday_AT_TI",
    "is_public_holiday_DE_BY", "is_public_holiday_AT_SB", "is_public_holiday_AT_TI",
    "holiday_overlap_count",
    "days_to_holiday_start_DE_BY", "days_since_holiday_end_DE_BY",
    "is_school_start_day_DE_BY", "is_school_end_day_DE_BY",
    # weather climatology
    "precip_prob_wet", "ice_risk_prob", "low_vis_prob_foggy",
    "t_min_c_mean", "t_max_c_mean",
    # construction
    "is_construction_active", "is_2_plus_0_active",
    # events
    "event_score", "any_event_high_impact",
]

# Optional per-station feature: included only when predicting for all 12 stations
# (i.e. when features.parquet was built from daily_station.parquet).
# When present, the model learns per-station volume differences (e.g. MQQ209 vs MQQ37).
OPT_FEATURE_COLS = ["station_label"]

CAT_FEATURES = ["road", "direction", "season"]
OPT_CAT_FEATURES = ["station_label"]


def get_feature_cols(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Return (feature_cols, cat_features) including optional columns present in df."""
    extra = [c for c in OPT_FEATURE_COLS if c in df.columns]
    extra_cat = [c for c in OPT_CAT_FEATURES if c in df.columns]
    return FEATURE_COLS + extra, CAT_FEATURES + extra_cat
TARGET = "daily_volume"

QUANTILES = [0.1, 0.5, 0.9]
TRAIN_END = "2025-09-30"
VAL_START = "2025-10-01"
VAL_END = "2025-12-31"


def split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df["date"] = pd.to_datetime(df["date"])
    tr = df[df["date"] <= TRAIN_END].copy()
    va = df[(df["date"] >= VAL_START) & (df["date"] <= VAL_END)].copy()
    return tr, va


def _ensure_features(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows missing target/features; cast bools to int (CatBoost-friendly)."""
    out = df.copy()
    out = out.dropna(subset=[TARGET])
    feat_cols, _ = get_feature_cols(out)
    for c in feat_cols:
        if c not in out.columns:
            raise KeyError(f"missing feature column: {c}")
        if out[c].dtype == bool:
            out[c] = out[c].astype(int)
    return out


def train() -> None:
    feat_path = PROCESSED / "features.parquet"
    df = pd.read_parquet(feat_path)
    df = _ensure_features(df)
    feat_cols, cat_cols = get_feature_cols(df)
    train_df, val_df = split(df)
    print(f"train rows: {len(train_df):,}   val rows: {len(val_df):,}")
    print(f"features: {len(feat_cols)} ({feat_cols})")

    metrics = {}
    for q in QUANTILES:
        model = CatBoostRegressor(
            loss_function=f"Quantile:alpha={q}",
            iterations=2000,
            learning_rate=0.05,
            depth=6,
            random_seed=42,
            verbose=200,
            early_stopping_rounds=100,
        )
        tr_pool = Pool(train_df[feat_cols], train_df[TARGET], cat_features=cat_cols)
        va_pool = Pool(val_df[feat_cols], val_df[TARGET], cat_features=cat_cols)
        model.fit(tr_pool, eval_set=va_pool, use_best_model=True)
        preds = model.predict(val_df[feat_cols])
        mae = float(np.mean(np.abs(preds - val_df[TARGET])))
        metrics[f"q{int(q * 100)}"] = {"mae_val": mae, "features": feat_cols}
        out_path = MODELS_DIR / f"catboost_q{int(q * 100)}.cbm"
        model.save_model(str(out_path))
        print(f"  saved {out_path}  val MAE = {mae:,.0f}")

    (MODELS_DIR / "training_metrics.json").write_text(json.dumps(metrics, indent=2))


def predict(start: str, end: str) -> pd.DataFrame:
    """Predict for every (date, road, direction[, station_label]) in the future feature matrix.

    If features.parquet contains a station_label column (built from daily_station.parquet),
    predictions are returned per station. Otherwise, per corridor (road, direction).
    """
    df = pd.read_parquet(PROCESSED / "features.parquet")
    df = _ensure_features(df.assign(daily_volume=df.get("daily_volume", 0).fillna(0)))
    feat_cols, _ = get_feature_cols(df)
    mask = (pd.to_datetime(df["date"]) >= start) & (pd.to_datetime(df["date"]) <= end)
    sub = df[mask].copy()
    for q in QUANTILES:
        model = CatBoostRegressor()
        model.load_model(str(MODELS_DIR / f"catboost_q{int(q * 100)}.cbm"))
        sub[f"volume_p{int(q * 100)}"] = model.predict(sub[feat_cols])
    id_cols = ["date", "road", "direction"]
    if "station_label" in sub.columns:
        id_cols.append("station_label")
    out = sub[id_cols + ["volume_p10", "volume_p50", "volume_p90"]]
    out_path = PROCESSED / f"forecast_{start}_{end}.parquet"
    out.to_parquet(out_path, index=False)
    print(f"wrote {len(out):,} rows -> {out_path}")
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("train")
    pp = sub.add_parser("predict")
    pp.add_argument("start"); pp.add_argument("end")
    a = p.parse_args()
    if a.cmd == "train":
        train()
    else:
        predict(a.start, a.end)


if __name__ == "__main__":
    main()
