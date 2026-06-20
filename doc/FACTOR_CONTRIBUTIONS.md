# Factor Attribution — Daily CSV Guide for the Agent Layer

> **Audience**: Agent developers AND human reviewers. This doc explains how to read the per-day factor attribution and what each factor means.
> **Design rationale**: See [`doc/FACTOR_GROUPING_REVIEW.md`](FACTOR_GROUPING_REVIEW.md) for why the 7-group split was chosen and how it improves over the previous 6-group scheme.

---

## Quick Start (Agent Code)

```python
import pandas as pd
import re

# Read the daily forecast file — 原因 column has factor attribution
daily = pd.read_csv("data_autobahn/forecast_2026_2029_daily.csv", parse_dates=["date"])
# Columns: site_id, road, direction, site_name, date,
#           kfz_h_p10, kfz_h_p50, kfz_h_p90, sv_h_pred, v_kfz_pred,
#           interval_width, relative_interval_width, 原因

def parse_reasons(reason_str: str) -> dict[str, float]:
    """Convert 'Historical Traffic Baseline: 68.0%；Holiday Effect: 12.3%' -> {...}"""
    if pd.isna(reason_str) or reason_str == '':
        return {}
    result = {}
    for part in re.split(r'[；;]', reason_str):
        part = part.strip()
        if ':' in part:
            key, val = part.split(':', 1)
            result[key.strip()] = float(val.strip().replace('%', ''))
    return result

# Example: explain a prediction
row = daily[daily.date == "2026-08-01"].iloc[0]
parsed = parse_reasons(row['原因'])
# -> {'Historical Traffic Baseline': 60.5, 'Holiday Effect': 15.2,
#     'Road Segment and Detector Attributes': 12.1, 'Date and Time Pattern': 6.8,
#     'Weather and Temperature': 4.3, 'Special Events': 1.1}
```

---

## File Format

**`data_autobahn/forecast_2026_2029_daily.csv`**

This is the primary Agent deliverable — daily traffic forecasts with per-day factor attribution.

| Field | Description |
|-------|-------------|
| `site_id` | Station identifier (e.g. `A8_Sbg_MQQ37_Sbg_H`) |
| `road` | Highway: `A8` or `A93` |
| `direction` | `Mch` (→Munich), `Sbg` (→Salzburg), `Ro` (→Rosenheim), `Kff` (→Kufstein) |
| `site_name` | Short station name (e.g. `MQQ37_Sbg_H`) |
| `date` | `YYYY-MM-DD` |
| `kfz_h_p10` | Daily total vehicles — P10 (lower bound) |
| `kfz_h_p50` | Daily total vehicles — P50 (best estimate) |
| `kfz_h_p90` | Daily total vehicles — P90 (upper bound) |
| `sv_h_pred` | Daily total heavy vehicles |
| `v_kfz_pred` | Daily mean speed (km/h) |
| `interval_width` | `kfz_h_p90 − kfz_h_p10` (absolute uncertainty) |
| `relative_interval_width` | `interval_width / (kfz_h_p50 + 1)` (normalized uncertainty) |
| `原因` | Factor attribution string (see below) |

**`原因` column format**:

```
Historical Traffic Baseline: 68.0%；Date and Time Pattern: 11.6%；Holiday Effect: 7.2%；Weather and Temperature: 7.2%；Road Segment and Detector Attributes: 5.3%；Special Events: 0.7%
```

**Rules**:
- Every station-day has exactly one row. 12 stations × 1,461 days (2026–2029) = **17,532 rows**.
- Display names are full English names (matching the Agent's existing parsing code from `add_daily_forecast_reasons.py`).
- Each percentage has **1 decimal place** with a `%` sign (e.g. `68.0%`).
- Chinese semicolon `；` separates groups.
- Groups are sorted by **descending share**.
- Only groups with a share **≥ 0.1%** are included.
- Shares sum to **~100.0%** per row (may differ by 0.1 due to rounding).

---

## Factor Groups & Meanings (7 Groups)

### Historical Traffic Baseline

> **Display name**: `Historical Traffic Baseline`
> **Human-readable**: Historical traffic patterns
> **What it captures**: Based on 3 years of sensor data (2023–2025), what's the typical traffic volume at this station for this hour, day-of-week, month, and season?

**Features included**: `prof_kfz_shd`, `prof_kfz_sht`, `prof_kfz_shm`, `prof_kfz_p90`, `prof_kfz_shs` — five historical profile features computed from 2023–2025 training data.

**Typical magnitudes**:
- 🟢 **55–70%** on most days — historical data patterns dominate the prediction
- 🟡 **45–55%** on peak travel days — external factors (holidays, weather) take a larger share

**Interpretation**:
- This is the model's "memory" of what traffic normally looks like. High HP means "this day looks like a typical day in the historical record."
- HP is distinct from station location: it answers "what does the DATA say?" while SL answers "WHERE is this road?"
- **HP below 50% signals an unusual day** — holidays, events, or weather are driving the prediction away from historical norms.

---

### Road Segment and Detector Attributes

> **Display name**: `Road Segment and Detector Attributes`
> **Human-readable**: Geographic location & road identity
> **What it captures**: Where the sensor is physically located — kilometer marker, GPS coordinates, which highway (A8/A93), which direction, and the station's unique identity.

**Features included**: `site_id`, `road`, `direction`, `site_name`, `bab_km`, `longitude`, `latitude`.

**Typical magnitudes**:
- 🟢 **10–25%** — the road's geographic identity is a persistent baseline contributor
- 🔴 **Varies by station** — stations near Munich (MQB25) typically show higher SL contribution than remote stations (MQQ245)

**Interpretation**:
- SL answers: "is this road inherently busy because of where it is?"
- A station near Munich on A8 heading to Salzburg has a fundamentally different traffic level than one near Kiefersfelden on A93 — even at the same hour on the same day.
- **SL is the "geographic prior"** — before looking at any data, the model knows MQB25 (Munich end) handles more traffic than MQQ245 (Salzburg border).

---

### Date and Time Pattern

> **Display name**: `Date and Time Pattern`
> **Human-readable**: Calendar timing (hour, day, month, season)
> **What it captures**: Pure time signals — what hour of day, day of week, month, and season it is. Cyclic encodings (sin/cos) help the model understand daily and yearly rhythms.

**Features included**: `hour`, `weekday`, `month`, `doy`, `week_of_year`, `is_weekend`, `is_friday`, `is_saturday`, `is_sunday`, `hour_sin/cos`, `dow_sin/cos`, `month_sin/cos`, `doy_sin/cos`, `season`.

**Note**: `tagestyp` is no longer in this group — it was moved to Holiday Effect (v4 change). This group is now **pure calendar timing** with no holiday information.

**Typical magnitudes**:
- 🟢 **4–8%** on routine workdays — time-of-day pattern is stable
- 🟡 **8–15%** on summer weekends — the calendar timing amplifies the baseline

**Interpretation**:
- CA captures *when* the traffic happens. It answers "is this 8 AM Monday or 11 AM Saturday?"
- **CA is high when the day's timing (e.g., midday on a summer weekend) drives heavier traffic than what even the average profile expects.**

---

### Holiday Effect

> **Display name**: `Holiday Effect`
> **Human-readable**: School/public holiday travel wave
> **What it captures**: School holidays in **Bavaria (DE-BY)**, **Salzburg (AT-SB)**, and **Tyrol (AT-TI)**; public holidays in all three states; holiday start/end days; departure wave days (Saturday before); return wave days (Sunday after); traffic window risk levels; and `tagestyp` (day-type classification: workday/Sunday+holiday/school-holiday).

**Features included**: All `is_school_holiday_*`, `is_public_holiday_*`, `school_holiday_count`, `public_holiday_count`, `is_holiday_start/end`, `in_traffic_window`, `days_to_holiday_start`, `days_since_holiday_end`, `total_holiday_overlap`, `is_departure/return_wave_day`, `window_direction`, `window_risk_level`, `a8_direction`, `a93_direction`, **`tagestyp`** (moved from Calendar in v4).

**Typical magnitudes**:
- 🟢 **< 6%** on routine workdays — no holiday effect
- 🟡 **10–20%** on summer vacation Saturdays (departure wave) and Christmas
- 🔴 **20–35%** if multiple states' holidays overlap on a peak travel Saturday

**Interpretation**:
- **HO is the "holiday bump."** It answers "is today a departure day for school holidays?"
- **The highest HO shares occur on summer Saturdays** — the classic _Stau-Wochenende_ (jam weekend) when all three states are on vacation.
- **HO now includes `tagestyp`** (v4 change), giving a complete picture of holiday effects. Previously, part of the holiday signal leaked into Calendar.

---

### Weather and Temperature

> **Display name**: `Weather and Temperature`
> **Human-readable**: Temperature, precipitation, road conditions
> **What it captures**: Air temperature (daily min/max, hourly mean), road surface temperature, precipitation, snow, low visibility, ice risk. **For future dates (2026–2029), these values are climatological averages** (what's typical for that month and hour), not actual forecasts.

**Features included**: `w_precip`, `w_snow`, `w_lowvis`, `w_tmin`, `w_tmax`, `w_ice`, `weather_source`, `lt_mean` (air temp), `fbt_mean` (road temp), `fbt_min`.

**Typical magnitudes**:
- 🟢 **3–8%** on most days — weather is a mild modifier
- 🟡 **8–15%** in winter (cold/snow/ice) — weather deviates from climatology's neutral state

**Interpretation**:
- In the training data (2023–2025), weather was a real observation. **In the forecast (2026–2029), it's climatology** — so WE captures how this month/hour's average weather differs from the model's unconditional baseline.
- **Don't interpret high WE as "bad weather coming." It means "this month/hour's typical weather matters for traffic."**

---

### Special Events

> **Display name**: `Special Events`
> **Human-readable**: Special event traffic (Oktoberfest, festivals, concerts)
> **What it captures**: Special events in the corridor's catchment cities — München, Salzburg, Rosenheim, Kufstein. Includes event count, max impact level, composite impact score, and whether the event affects A8/A93 corridors.

**Features included**: `has_special_event`, `active_event_count`, `max_impact_level`, `impact_score`, `affects_a8_ost/a93_sued`, `has_munich/salzburg/rosenheim/kufstein_event`, `has_confirmed/estimated_event`.

**Typical magnitudes**:
- 🟢 **< 2%** — most days have no events
- 🟡 **5–15%** — during major festivals (Oktoberfest, Salzburg Festival)

**Interpretation**:
- EV appears when a **known event** is in the future conditions data. For dates without events in the database, all event features are 0, so EV contributes nothing.
- **If EV appears on a date and you know of additional events not in the table, the model may be underestimating traffic.**

---

### Construction Impact

> **Display name**: `Construction Impact`
> **Human-readable**: Roadworks / lane closures
> **What it captures**: Construction activity, 2+0 two-way single-carriageway configurations, closed lanes, and construction counts on A8/A93.

**Features included**: `has_a8/a93_construction`, `a8/a93_construction_count`, `has_2_plus_0`, `two_plus_0_count`, `max_closed_lanes`, `sum_closed_lanes`, `has_target_bbox_construction`.

**Typical magnitudes**:
- 🟢 **Normally absent** (< 0.1%) — CO is usually omitted from the string
- 🟡 **5–15%** — on future dates with documented 2+0 closures

**Interpretation**:
- **CO was ~0% in training** (the Autobahn API had no historical roadwork data). The model learned nothing about how roadworks affect traffic.
- **For known 2+0 days, apply the capacity-override rule** in the Agent layer (`doc/tasks_D_F_G_tutorial.md`) rather than relying on the model's CO contribution.

---

## Volume-Weighted Aggregation

The per-row (hourly) factor contributions are aggregated to one **per-day** string using **feature-group ablation with implicit volume weighting**.

Since the ablation measures `|full_prediction − ablated_prediction|` in vehicles/hour, summing these absolute deltas over 24 hours is naturally volume-weighted — peak hours (2,000+ veh/h) produce much larger absolute deltas than night hours (150 veh/h).

This means:
- **Peak hours (11:00, 15:00, etc.) dominate the daily share** — because those hours carry more vehicles.
- **Nighttime hours (midnight–5 AM) barely affect the daily share** — their traffic is low, so their factor mix doesn't distort the day's story.
- **The daily factor shares reflect when traffic actually happens.** If a holiday bump mostly affects midday hours, HO's daily share is proportionally higher.

---

## Practical Usage Patterns

### 1. Explain why a day is colored red/critical

```python
def explain_day(row):
    parsed = parse_reasons(row['原因'])
    # Find the top non-baseline factor
    non_baseline = {k: v for k, v in parsed.items()
                    if k not in ['Historical Traffic Baseline',
                                 'Road Segment and Detector Attributes']}
    if not non_baseline:
        return f"Traffic follows the normal pattern for this {row['road']} {row['direction']} corridor."

    top_name, top_pct = max(non_baseline.items(), key=lambda kv: kv[1])

    explanations = {
        "Holiday Effect":
            f"School holiday travel in Bavaria/Austria drives {top_pct:.0f}% of today's prediction. "
            "Expect peak departure/return traffic on the A8 Salzburg corridor.",
        "Special Events":
            f"A special event (Oktoberfest / festival) contributes {top_pct:.0f}% to today's traffic. "
            "Check events table for details.",
        "Weather and Temperature":
            f"Weather-related factors explain {top_pct:.0f}% of the prediction. "
            "Expect conditions different from pure historical norm.",
        "Date and Time Pattern":
            f"Calendar timing accounts for {top_pct:.0f}% — "
            "this is an unusual position in the yearly cycle.",
        "Construction Impact":
            f"Construction/roadworks contribute {top_pct:.0f}%. Note: training data had no construction "
            "examples — this reflects the presence of known future closures, not a learned effect.",
    }
    return explanations.get(top_name,
        f"The dominant external factor is {top_name} ({top_pct:.0f}%).")
```

### 2. Compare two days for the same station

```python
# "Why is August 1 (red) so different from August 8 (yellow)?"
aug1 = parse_reasons(row_for('2026-08-01', site))
aug8 = parse_reasons(row_for('2026-08-08', site))

diffs = {c: aug1.get(c, 0) - aug8.get(c, 0) for c in set(aug1) | set(aug8)}
# If Holiday Effect is +12pp on Aug 1, that's the departure wave vs. a week later.
```

### 3. Identify the "surprising" days

Days where baseline factors (HP + SL) are unusually low and external factors (HO + EV) are elevated are candidates for non-routine traffic management:

```python
for _, row in daily.iterrows():
    p = parse_reasons(row['原因'])
    baseline = p.get('Historical Traffic Baseline', 0) + p.get('Road Segment and Detector Attributes', 0)
    external = p.get('Holiday Effect', 0) + p.get('Special Events', 0)
    if baseline < 65 and external > 20:
        print(f"{row['date']} {row['site_id']}: outlier day — "
              f"baseline={baseline:.0f}% external={external:.0f}%")
```

---

## Factor Power Ranking (Completeness Guide)

When presenting factors to an end user, the Agent can summarize like this:

| Dominance | Factor mix pattern | What to tell the user |
|-----------|-------------------|-----------------------|
| HP + SL ≥ 80% | Routine day | "Traffic follows the normal pattern for this corridor. No unusual drivers." |
| HP 50–65% + HO 10–20% | Holiday-affected | "Vacation travel is elevating traffic above normal. Expect holiday patterns." |
| HP 40–55% + HO 20–35% | Peak holiday | "This is a peak travel day — multiple regions' school holidays overlap. Stau risk is elevated." |
| EV ≥ 5% | Event day | "A special event (e.g., Oktoberfest, festival) is driving extra traffic today." |
| CO ≥ 5% | Construction | "Known roadworks may affect capacity. (Note: model has limited training on this — apply the 2+0 override rule.)" |
| WE ≥ 10% | Weather-affected | "Seasonal weather patterns (e.g., winter cold, summer heat) are a meaningful modifier today." |

---

## How It's Calculated (for review)

The attribution uses **feature-group ablation**:

1. Predict `kfz_h_p50` with all 82 features active → **full prediction**.
2. For each of the 7 factor groups, **zero out** that group's features and re-predict → **ablated prediction**.
   - Numerical features → set to `0.0`
   - Categorical features → set to `"__NEUTRAL__"` (CatBoost's unseen-category prior)
3. `|full − ablated|` = that group's raw contribution to this hour's prediction (veh/h).
4. Normalize the 7 contributions to percentages (rows sum to 100).
5. Aggregate to per-day by summing the absolute deltas over 24 hours (implicitly volume-weighted).
6. Format with SHAP-compatible display names, sorted descending, with 1 decimal place.

This runs over all 420,768 forecast rows. The resulting 17,532-row daily table is what the Agent reads.

**Why ablation, not feature importance?** CatBoost feature importance is *global* — the same number for every row. Ablation is **per-row**, so August 1 (departure Saturday) and March 10 (normal Tuesday) get different Holiday shares — which is what explainability needs.

**Why ablation, not SHAP?** SHAP values from `add_daily_forecast_reasons.py` suffer from three issues: (a) simple-sum aggregation without volume weighting, (b) correlation-induced splitting (holiday and weather features co-vary in December, causing attribution dilution), and (c) approximate calculation mode. Ablation's counterfactual semantics ("what if we didn't know about holidays?") also maps more naturally to user-facing explanations. See `doc/FACTOR_GROUPING_REVIEW.md` for the full comparison.

---

## Version Notes

- **v4 (2026-06-20)**: Major revision. Split "Typical Traffic" (TT) into "Historical Traffic Baseline" and "Road Segment and Detector Attributes" (7 groups). Moved `tagestyp` from Calendar to Holiday Effect to capture the complete holiday signal. Changed output format to SHAP-compatible full names with 1 decimal place (e.g. `Historical Traffic Baseline: 68.0%；...`) in the `原因` column. Output file is now `forecast_2026_2029_daily.csv` (replaces both the SHAP script's output and the old `factor_attribution_daily.csv`). See `doc/FACTOR_GROUPING_REVIEW.md` for design rationale.
- **v3 (earlier)**: 6 groups (TT/CA/HO/WE/EV/CO). `factor_attribution_daily.csv` with abbreviated codes (`TT:74;CA:12`).
- **See also**: `doc/MODEL.md` for the full model architecture and feature inventory. `doc/FACTOR_GROUPING_REVIEW.md` for the v4 design rationale and comparison with SHAP.
