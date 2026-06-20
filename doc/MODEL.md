# Model Documentation — CatBoost v2 Traffic Forecasting

> **Notebook**: `model/model_notebook.ipynb`  
> **Status**: ✅ Training complete, forecasts generated for 2026–2029  
> **Last run**: 2026-06-20  
> **Replaces**: `model_v2_review.md`, `model_v2_next_steps.md`, `hyperparameter_guide.md`, `final_plan.md` (those are now obsolete)

---

## 1. What the Model Does

Predicts **hourly traffic for 12 measurement stations** on the A8 East and A93 South autobahn corridors, **2026-01-01 → 2029-12-31** (420,768 rows = 12 sites × 1,461 days × 24 hours).

### Three Targets

| Target | Unit | Method | Model |
|--------|------|--------|-------|
| `kfz_h` (total flow) | veh/h | P10/P50/P90 quantile regression | CatBoost `MultiQuantile:alpha=0.1,0.5,0.9` — single model, shared trees |
| `sv_h` (truck volume) | veh/h | Ratio method: `lkw_ratio × kfz_h_p50` | CatBoost RMSE on `lkw_ratio = sv_h / kfz_h` |
| `v_kfz` (avg speed) | km/h | Two-step: `prof_v_p85 − speed_drop` | CatBoost RMSE on `speed_drop` (G3: includes `kfz_p50_pred`) |

### Core Idea

Historical **profile features** (median traffic by site×hour×weekday, site×hour×tagestyp, etc.) provide the baseline prediction (~64% of feature importance). External **conditional features** (holidays, weather climatology, construction, events) provide marginal adjustments on top. **No lag features, no recursive forecasting** — the model predicts any future date directly from calendar-anchored features.

---

## 2. Feature Engineering Overview

### Feature Groups (82–86 features depending on target)

| Group | Count | Examples | Purpose |
|-------|-------|----------|---------|
| **CALENDAR** | 17 | `hour`, `weekday`, `month`, `doy`, `hour_sin/cos`, `dow_sin/cos`, `month_sin/cos`, `doy_sin/cos`, `is_weekend/friday/saturday/sunday` | Temporal position encoding |
| **STATIC_NUM** | 3 | `bab_km`, `longitude`, `latitude` | Site geographic position |
| **STATIC_CAT** | 6 | `site_id`, `road`, `direction`, `site_name`, `tagestyp`, `season` | Site identity + day type |
| **PROF_KFZ** | 5 | `prof_kfz_shd` (site×h×wkday), `prof_kfz_sht` (site×h×tagestyp), `prof_kfz_shm` (site×h×month), `prof_kfz_p90` (P90), `prof_kfz_shs` (site×h×season) | Historical flow profiles — **primary signal (64% importance)** |
| **PROF_LKW** | 2 | `prof_lkw_shd`, `prof_lkw_sht` | Historical truck ratio profiles |
| **PROF_V** | 3 | `prof_v_shd`, `prof_v_p85` (free-flow baseline), `prof_v_sht` | Historical speed profiles |
| **HOLIDAY** | 17 | `is_school/public_holiday_DE_BY/AT_SB/AT_TI`, `school/public_holiday_count`, `is_holiday_start/end`, `days_to_holiday_start`, `days_since_holiday_end`, `total_holiday_overlap`, `is_departure/return_wave_day`, `in_traffic_window` | Holiday impact + departure/return wave detection |
| **HOLIDAY_CAT** | 4 | `window_direction`, `window_risk_level`, `a8_direction`, `a93_direction` | Categorical holiday modifiers |
| **WEATHER** | 6 | `w_precip`, `w_snow`, `w_lowvis`, `w_tmin`, `w_tmax`, `w_ice` | Daily weather (observed for past, climatology for future) |
| **WEATHER_CAT** | 1 | `weather_source` | Data source indicator |
| **TEMP** | 3 | `lt_mean` (air temp), `fbt_mean` (road temp), `fbt_min` | Hourly temperature (observed or climatology) |
| **CONSTRUCTION** | 9 | `has_a8/a93_construction`, `has_2_plus_0`, `two_plus_0_count`, `max_closed_lanes`, `sum_closed_lanes`, `has_target_bbox_construction` | Construction/closure indicators |
| **EVENTS** | 12 | `has_special_event`, `active_event_count`, `max_impact_level`, `impact_score`, `affects_a8_ost/a93_sued`, `has_munich/salzburg/rosenheim/kufstein_event`, `has_confirmed/estimated_event` | Special event impact scores |
| **G3 (speed only)** | 1 | `kfz_p50_pred` | Flow prediction fed into speed model (flow→speed coupling) |

### Profile Features — The Core Signal

Profiles are built **only from training data** (2023–2024), preventing data leakage:

```python
profiles = build_profiles(train_df)  # train_df ends at 2024-12-31
train_df = apply_profiles(train_df, profiles)
val_df   = apply_profiles(val_df, profiles)    # val = 2025, profiles still from train only
```

Each profile is a groupby-median (or quantile) lookup: e.g., `prof_kfz_sht = median(kfz_h) by (site_id, hour, tagestyp)`. Missing keys fall back to a global median.

Profile keys:
- `shd` = site × hour × weekday
- `sht` = site × hour × tagestyp (w/s/u)
- `shm` = site × hour × month
- `shs` = site × hour × season (v2 new)
- `p90` / `p85` = upper quantiles for peak detection / free-flow speed

---

## 3. Model Architecture

### 3.1 kfz_h: MultiQuantile CatBoost

```
CatBoostRegressor(
    loss_function="MultiQuantile:alpha=0.1,0.5,0.9",
    iterations=2000, learning_rate=0.02, depth=8,
    l2_leaf_reg=3.0, min_data_in_leaf=50,
    subsample=0.85, rsm=0.8,
    early_stopping_rounds=200
)
```

Single model outputs P10, P50, P90 simultaneously. Shared tree structure prevents quantile crossing. `rsm=0.8` adds column subsampling for minor diversity between quantiles.

Post-processing: monotonicity constraint (`P90 ≥ P50 ≥ P10`) + conformal calibration (`±conf_quantile` applied to P10/P90).

### 3.2 sv_h: Ratio Method

```
lkw_ratio = sv_h / kfz_h  →  CatBoostRegressor(loss_function="RMSE", ...)
sv_h_pred = lkw_ratio_pred × kfz_h_p50
```

Trained on rows where `sv_h > 0`. Ratio prediction is more stable than direct SV regression (ratios are bounded and less volatile).

### 3.3 v_kfz: Two-Step Speed Drop (G3)

```
speed_drop = prof_v_p85 − v_kfz      # positive = congestion
v_kfz_pred = prof_v_p85 − speed_drop_pred
```

Training target clipped to `[-20, 60]` to reduce outlier influence. Validation target kept raw for honest evaluation.

**G3 enhancement**: `kfz_p50_pred` added as a feature so the speed model sees the predicted flow level, capturing the flow→speed relationship directly. This requires two-stage training: kfz model first → predict kfz_p50 on train/val → speed model uses it as input.

```
CatBoostRegressor(
    loss_function="RMSE", eval_metric="RMSE",
    iterations=1200, learning_rate=0.02, depth=5,
    l2_leaf_reg=15.0, min_data_in_leaf=200,
    early_stopping_rounds=100, random_strength=1.0, rsm=0.85
)
```

More conservative than the flow model (shallower trees, stronger regularization) because the speed-flow relationship is simpler but noisier.

---

## 4. Key Milestones & Fixes Applied

### Timeline

| Milestone | Status | Description |
|-----------|--------|-------------|
| **v1 baseline** | ✅ | 3 independent CatBoost models (P10/P50/P90). PICP=69.5%, MAPE=16.4%. MPIW baseline corrected (was 585, real 365). |
| **v2 MultiQuantile** | ✅ | Single model for all 3 quantiles. Shared trees, no quantile crossing, 3× faster training. |
| **A: tagestyp rebuild** | ✅ | `derive_tagestyp()` reconstructs tagestyp (w/s/u) from holiday flags for future grid. 99.91% accuracy validated on 2023–2025. Prevents summer holidays being treated as workdays (was causing systematic underestimation of peak days). |
| **B: Split conformal** | ✅ | 2025 validation split by time: first half calibrates `conf_quantile`, second half reports honest PICP. `conf_quantile` saved to `conformal.json` and applied to forecast P10/P90. Result: raw PICP 71.4% → calibrated 81.5% (held-out). |
| **E: Honest baselines** | ✅ | V1_BASELINE MPIW corrected 585→365. Both raw and calibrated PICP reported. Peak Recall label fixed to top10%. Comparison table no longer misleading. |
| **G3: Speed model + flow** | ✅ | `kfz_p50_pred` added as feature to speed model. v_kfz MAE improved from 5.9→5.7 km/h. Requires two-stage pipeline. |
| **Confidence metrics** | ✅ | `interval_width` and `relative_interval_width` added to forecast output for Agent layer consumption. |
| **Chinese→English labels** | ✅ | All chart titles, axis labels, DataFrame columns, and print output translated to English for consistent rendering. |

### What Was NOT a Real Improvement (Corrected)

- **PICP "69.5→80.0%" in early v2**: Was in-sample self-deception (calibrated and evaluated on the same data). Fixed by split conformal. The real improvement is 69.5% → 81.5% (honest).
- **MPIW "585→393"**: Used a wrong v1 baseline (585). Real v1 MPIW = 365. The real change is 365→393 (interval slightly wider, which is the price of honest 80% coverage).
- **rsm boosting PICP**: The `hyperparameter_guide.md` previously claimed `rsm=0.8` could push PICP from 69% to 75-80%. Actual data: rsm contribution ~2pt (69.5%→71.4%). The main PICP lever is conformal calibration.

---

## 5. Final Metrics (2025 Hold-Out, Split-Conformal Evaluation)

| Metric | v1 (model.ipynb) | v2 (model_notebook.ipynb) | Δ | Verdict |
|--------|-------------------|---------------------------|---|---------|
| kfz_h MAE | 137.1 veh/h | **135.4** | ▼ 1.7 | ✅ Small real improvement |
| kfz_h RMSE | 238.7 | **235.4** | ▼ 3.3 | ✅ |
| kfz_h MAPE | 16.4% | **16.1%** | ▼ 0.26pt | ✅ |
| kfz_h WMAPE | — | **10.7%** | new | Reference |
| sv_h MAE | 24.5 veh/h | **23.7** | ▼ 0.8 | ✅ |
| sv_h RMSE | 41.9 | **40.5** | ▼ 1.4 | ✅ |
| sv_h MAPE | 20.9% | **19.9%** | ▼ 0.99pt | ✅ |
| v_kfz MAE | 5.9 km/h | **5.7** | ▼ 0.19 | ✅ G3 improvement |
| v_kfz RMSE | 9.6 | **9.5** | ▼ 0.14 | ✅ |
| v_kfz MAPE | 7.5% | **7.3%** | ▼ 0.21pt | ✅ |
| **PICP (raw)** | 69.5% | **71.4%** | ▲ 1.9pt | Small (rsm), not the main lever |
| **PICP (calibrated)** | — | **81.5%** | — | ✅ Split-conformal, honest, held-out |
| **MPIW (calibrated)** | 365 veh/h | **393** | ▲ 28 | Price of honest 80% coverage |
| **Peak Recall (top10%)** | 88.1% | **88.1%** | 0 | Stable |
| **Improved / Total** | — | **11 / 12** | — | MPIW is the only "regression" (expected) |

### Feature Importance (kfz_h P50)

| Group | Share |
|-------|-------|
| ① Historical Profile | 63.9% |
| ② Calendar | 18.5% |
| ⑦ Site Static | 6.7% |
| ④ Weather/Temp | 6.1% |
| ③ Holiday | 3.7% |
| ⑥ Events | 1.1% |
| ⑤ Construction | **0.0%** (verified correct — see §6.1) |

---

## 6. Known Limitations & Issues

### 6.1 🔴 Train/Test Split: Construction Features Dead (0% Importance)

**What**: All construction features have 0.0% importance in the model.

**Why (verified correct)**: The training window (2023–2024, 731 days) contains **zero** days with meaningful construction data. The Autobahn API has no historical endpoint. Additionally, the merged construction table was built from a buggy pipeline with an over-permissive `is_2_plus_0` decoder. A corrected pipeline exists (`scripts/fix_construction_data.py`) but its output was never wired into the merged table. **Full investigation**: see [`doc/CONSTRUCTION_DATA_ISSUE.md`](CONSTRUCTION_DATA_ISSUE.md).

**Impact**: The model **cannot represent "2+0" capacity halving** during road maintenance. This is a data limitation, not a code bug.

**Mitigation**: Known future 2+0 closures should be handled via rule-based post-processing (`apply_capacity_override()` in `doc/tasks_D_F_G_tutorial.md`). The training set limitation must be documented when presenting results.

### 6.2 🟠 Delivery Model Uses 2023–2024 Only (2025 Not Used for Final Training)

**What**: The final forecast (`forecast_2026_2029.parquet`) was generated using profiles and models trained only on 2023–2024. The 2025 data was used for validation but **not incorporated** into the final model.

**Impact**: ~105,000 additional training rows (2025) are thrown away. Using them would likely improve generalization, especially for stations that were installed late (Gletschergarten: 0% data in 2023).

**Why not done (Task C deferred)**: The model v2 pipeline was built around the train/val split for honest evaluation. Full-data retraining requires a separate "deploy mode" switch (`DEPLOY_FULL_REFIT`). Team decided to defer this — the 2025 hold-out metrics are already good and the priority is delivery.

### 6.3 🟡 Gletschergarten Station: No 2023 Data

Gletschergarten (both directions) was not installed until January 2024. All of 2023 = 0% data. Profile features for this station are built from 2024 only, making them noisier. Since February 2024, reliability is >95% — this is a deployment timeline issue, not ongoing.

### 6.4 🟡 Kiefersfelden DE33,34: 6-Month Outage in 2023

The DE33,34 sensor on the Kufstein direction was dead July–December 2023. The co-located DE1,2 sensor (Rosenheim direction) worked throughout. Since 2024, reliability >96%. The model handles this via the global `site_id` categorical — the Kiefersfelden_Kff site gets less reliable profile estimates for 2023 periods.

### 6.5 🟢 Weather: Single-Point Measurement

All weather data comes from one station at AD Rosenheim (km 54.6, A8 Salzburg direction). No spatial variation captured. For 4-year forecasting, weather enters as climatology (month×hour averages), so this limitation is acceptable.

---

## 7. Unfinished / Experimental Tasks

These are documented with implementation code in `doc/tasks_D_F_G_tutorial.md`.

| Task | Priority | Description | Effort |
|------|----------|-------------|--------|
| **C** | 🟠 Deferred | Full-data refit (2023–2025) for final forecast | 1 switch + rerun |
| **D** | 🟠 Pending data | Capacity override rules for known 2+0 closures | Fill real closure data |
| **F** | 🟢 Delegated | Daily aggregation + color grading → Agent layer | Agent-side |
| **G1** | 🟢 Experimental | Peak-hour weighted training (2× weight for kfz_h > P90) | 15 min |
| **G2** | 🟢 Experimental | sv_h direct regression vs ratio method comparison | 15 min |
| **G4** | 🟢 Experimental | Grouped conformal calibration (per-site or per-tagestyp) | 15 min |

---

## 8. Forecast Output Schema

### `processed/forecast_2026_2029.csv` (primary for Agent) / `.parquet`

420,768 rows × 13 columns:

| Column | Type | Description |
|--------|------|-------------|
| `site_id` | str | Unique site identifier (e.g., `A8_Mch_MQB25_Mch_H`) |
| `road` | str | Highway: A8 or A93 |
| `direction` | str | Direction: Mch (→Munich), Sbg (→Salzburg), Ro (→Rosenheim), Kff (→Kufstein) |
| `site_name` | str | Station name |
| `date` | datetime | Date (2026-01-01 to 2029-12-31) |
| `hour` | int | Hour (0–23) |
| `kfz_h_p10` | float | Total flow P10 (lower bound, veh/h) |
| `kfz_h_p50` | float | Total flow P50 (median prediction, veh/h) |
| `kfz_h_p90` | float | Total flow P90 (upper bound, veh/h) |
| `sv_h_pred` | float | Truck volume prediction (veh/h) |
| `v_kfz_pred` | float | Average speed prediction (km/h) |
| `interval_width` | float | Absolute uncertainty: `p90 − p10` (veh/h) |
| `relative_interval_width` | float | Normalized uncertainty: `width / (p50 + 1)` (median ~0.34) |

### Confidence Interpretation (for Agent)

The Agent can derive confidence from `relative_interval_width`:

| relative_interval_width | Confidence | Interpretation |
|--------------------------|------------|----------------|
| < 0.3 | High | Tight interval, routine conditions |
| 0.3 – 0.6 | Medium | Moderate uncertainty |
| > 0.6 | Low | Wide interval, unusual conditions (holidays, extreme weather) |

The conformal calibration ensures ~80% of true values fall within `[p10, p90]` across all predictions.

---

## 9. How to Run

### Prerequisites

```bash
cd Autobahn-hackathon
.venv/bin/python -m ipykernel install --user --name=autobahn_venv
```

### Execute

Open `model/model_notebook.ipynb` in VS Code, select the `autobahn_venv` kernel, then **Restart Kernel → Run All**.

**Expected runtime**: ~8–12 minutes (CatBoost training dominates). The notebook auto-creates `.venv` if missing, installs dependencies, and registers the kernel.

### Cell Order

| § | Content | Notes |
|---|---------|-------|
| §0 | Environment setup (venv + deps) | Skip if venv exists |
| §1 | Imports + hyperparameters | All config in one cell |
| §2 | Data loading | Reads 6 merged CSVs from `data_autobahn/` |
| §3 | Feature engineering | Calendar + profiles + conditional merge |
| §4.0 | (Optional) Load saved models | Skip training, go straight to eval/inference |
| §4.1 | kfz_h training | MultiQuantile CatBoost (~5 min) |
| §4.2 | Loss curves | |
| §4.3 | sv_h training | Ratio regression (~1 min) |
| §4.4 | v_kfz training | Speed drop with G3 (~1 min) |
| §5 | Validation evaluation | Split-conformal, metrics, comparison table |
| §6 | Full 2026–2029 inference | Saves forecast CSV + parquet |
| §7 | Explainability | Feature importance + SHAP |

### Generated Files

```
processed/
├── forecast_2026_2029.csv           ← Primary for Agent consumption
├── forecast_2026_2029.parquet
├── forecast_kfz_2026_2029.parquet
├── forecast_sv_2026_2029.parquet
├── forecast_vkfz_2026_2029.parquet
├── conformal.json                   ← {conf_quantile: 26.3, coverage: 0.80}
├── profiles.pkl
└── site_meta.parquet

models/
├── kfz_h/multi.cbm                  ← MultiQuantile P10/P50/P90
├── sv_h/lkw_ratio.cbm
└── v_kfz/speed_drop.cbm
```

---

## 10. Hyperparameter Reference

| Parameter | kfz_h | sv_h (ratio) | v_kfz (speed) | Notes |
|-----------|-------|-------------|---------------|-------|
| `iterations` | 2000 | 2000 | 1200 | Early stopping usually triggers earlier |
| `learning_rate` | 0.02 | 0.02 | 0.02 | |
| `depth` | 8 | 8 | 5 | Speed model: shallower (simpler relationship) |
| `l2_leaf_reg` | 3.0 | 3.0 | 15.0 | Speed model: stronger regularization |
| `min_data_in_leaf` | 50 | 50 | 200 | Speed model: larger (sparser signal) |
| `subsample` | 0.85 | 0.85 | 0.85 | |
| `rsm` | 0.8 | — | 0.85 | Column subsampling (minor PICP boost) |
| `early_stopping_rounds` | 200 | 200 | 100 | |
| `loss_function` | MultiQuantile | RMSE | RMSE | |
| `random_strength` | — | — | 1.0 | Speed only |

### Key Tuning Insights

- **PICP improvement**: Conformal calibration is the main lever (raw 71% → cal 82%). `rsm` tuning contributes only ~2pt — don't expect it to fix PICP.
- **Overfitting**: If train MAPE ≪ val MAPE, increase `l2_leaf_reg` (kfz: 3→5→8) or decrease `depth` (8→7).
- **Underfitting**: If both train and val MAPE are high, increase `iterations` (2000→3000) or decrease `learning_rate` (0.02→0.01 with more iterations).
- **Peak Recall**: Currently 88.1%. For improvement, try peak-weighted training (G1).

---

## 11. Related Documents

| Document | Relevance |
|----------|-----------|
| `../CLAUDE.md` | Complete data dictionary, station mapping, project context |
| `station_reliability_report.md` | Per-station sensor reliability analysis |
| `DATA.md` | Merged data table schema reference |
| `CONSTRUCTION_DATA_ISSUE.md` | Full investigation of construction data bug — root cause, fix guide, script inventory |
| `tasks_D_F_G_tutorial.md` | Implementation code for unfinished tasks (D, F, G1–G4) |
| `SOLUTION.md` | Original system architecture vision (pre-implementation) |
| `product.md` / `product_func.md` | Product requirements and user stories |
| `../agent/README.md` | Agent layer architecture (LangGraph multi-agent system) |

---

*Document generated 2026-06-20. Replaces `model_v2_review.md`, `model_v2_next_steps.md`, `hyperparameter_guide.md`, and `final_plan.md` which are superseded by this combined document and the executed notebook outputs.*
