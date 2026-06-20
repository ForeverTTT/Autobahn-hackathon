# Factor Attribution — Daily CSV Guide for the Agent Layer

> **Audience**: Agent developers AND human reviewers. This doc explains how to read the per-day factor attribution file and what each factor means. Keep it accessible to both.

---

## Quick Start (Agent Code)

```python
import pandas as pd

factors = pd.read_csv("data_autobahn/factor_attribution_daily.csv", parse_dates=["date"])
# Columns: site_id, road, direction, date, factors
# factors looks like: "TT:76;CA:12;HO:10;WE:2"

def parse_factors(factors_str: str) -> dict[str, int]:
    """Convert 'TT:76;CA:12;HO:10;WE:2' -> {'TT':76, 'CA':12, 'HO':10, 'WE':2}"""
    return {p.split(":")[0]: int(p.split(":")[1])
            for p in factors_str.split(";") if p}

# Example: explain a prediction
row = factors[factors.date == "2026-08-01"].iloc[0]
parsed = parse_factors(row.factors)
# -> {'TT':67, 'CA':10, 'WE':10, 'HO':9, 'EV':5}
```

---

## File Format

**`data_autobahn/factor_attribution_daily.csv`**

| Field | Description |
|-------|-------------|
| `site_id` | Station identifier (e.g. `A8_Sbg_MQQ37_Sbg_H`) |
| `road` | Highway: `A8` or `A93` |
| `direction` | `Mch` (→Munich), `Sbg` (→Salzburg), `Ro` (→Rosenheim), `Kff` (→Kufstein) |
| `date` | `YYYY-MM-DD` |
| `factors` | Semicolon-separated `CODE:percentage` pairs, sorted by descending share |

**Rules**:
- Every station-day has exactly one row. 12 stations × 1,461 days (2026–2029) = **17,532 rows**.
- The `factors` string uses **abbreviated codes** to keep the file small (~1.2 MB, under GitHub limits).
- Each code's percentage is an **integer** (rounded to nearest percent).
- Only codes with a rounded share **≥ 1%** are written. Missing codes contributed < 1%.
- Shares sum to **≈100%** per row (may differ by a point due to rounding).
- If the string is empty, the model's P50 prediction for that whole station-day was near zero (should never happen in practice).

---

## Factor Codes & Meanings

### TT — Typical Traffic

> **Abbreviation**: Typical Traffic  
> **Human-readable**: Baseline flow level  
> **What it captures**: This station's normal volume for this hour, day-type, month, and season — *plus* the station's geographic position (km marker, coordinates, road/direction identity). It is the model's default expectation before any external adjustments.

**Features included**: Historical flow/truck/speed profiles (`prof_*`), plus all static station attributes (`site_id`, `road`, `direction`, `site_name`, `bab_km`, `longitude`, `latitude`).

**Typical magnitudes**:
- 🟢 **70–95%** on routine workdays — "this is a normal Tuesday at this location"
- 🟡 **55–70%** on holiday Saturdays or peak travel days — baseline still dominant, but external factors meaningfully shift the prediction

**Interpretation**:
- **High TT** means the station's innate traffic pattern (its "personality") explains most of the prediction. Low prediction uncertainty.
- **TT rarely drops below 50%** — even on the wildest day, the station's fundamental character still matters.

---

### CA — Calendar

> **Abbreviation**: Calendar  
> **Human-readable**: Time-of-day / day-of-week / seasonal pattern  
> **What it captures**: Hour of day, day of week, month, season, whether it's a Friday/Saturday/Sunday/holiday-type day, and sin/cos cyclic encodings that help the model understand time-of-day and day-of-year rhythms.

**Features included**: `hour`, `weekday`, `month`, `doy`, `week_of_year`, `is_weekend/friday/saturday/sunday`, `hour_sin/cos`, `dow_sin/cos`, `month_sin/cos`, `doy_sin/cos`, `tagestyp`, `season`.

**Typical magnitudes**:
- 🟢 **5–15%** on routine workdays — time-of-day pattern is stable
- 🟡 **15–25%** on summer Saturdays and peak travel days — the calendar timing amplifies the baseline

**Interpretation**:
- CA captures *when* the traffic happens. It answers "is this 8 AM Monday or 11 AM Saturday?"
- **CA is high when the day's timing (e.g., midday on a summer weekend) drives heavier traffic than what even the average profile expects.**

---

### HO — Holiday

> **Abbreviation**: Holiday  
> **Human-readable**: School/public holiday travel wave  
> **What it captures**: School holidays in **Bavaria (DE-BY)**, **Salzburg (AT-SB)**, and **Tyrol (AT-TI)**; public holidays in all three states; holiday start/end days; departure wave days (Saturday before); return wave days (Sunday after); traffic window risk levels; and how many state holidays overlap.

**Features included**: `is_school_holiday_DE_BY/AT_SB/AT_TI`, `is_public_holiday_DE_BY/AT_SB/AT_TI`, `school_holiday_count`, `public_holiday_count`, `is_holiday_start/end`, `in_traffic_window`, `days_to_holiday_start`, `days_since_holiday_end`, `total_holiday_overlap`, `is_departure/return_wave_day`, `window_direction`, `window_risk_level`, `a8_direction`, `a93_direction`.

**Typical magnitudes**:
- 🟢 **< 5%** on routine workdays — no holiday effect
- 🟡 **10–20%** on summer vacation Saturdays (departure wave) and Christmas
- 🔴 **20–35%** if multiple states' holidays overlap on a peak travel Saturday

**Interpretation**:
- **HO is the "holiday bump."** It answers "is today a departure day for school holidays?"
- **The highest HO shares occur on summer Saturdays** — the classic _Stau-Wochenende_ (jam weekend) when all three states are on vacation.
- **HO can spike even when TT is high**, because the baseline already captures some of the pattern — HO is the *extra* holiday-specific push.

---

### WE — Weather

> **Abbreviation**: Weather  
> **Human-readable**: Temperature, precipitation, road conditions  
> **What it captures**: Air temperature (daily min/max, hourly mean), road surface temperature, precipitation, snow, low visibility, ice risk. **For future dates (2026–2029), these values are climatological averages** (what's typical for that month and hour), not actual forecasts.

**Features included**: `w_precip`, `w_snow`, `w_lowvis`, `w_tmin`, `w_tmax`, `w_ice`, `weather_source`, `lt_mean` (air temp), `fbt_mean` (road temp), `fbt_min`.

**Typical magnitudes**:
- 🟢 **2–7%** on most days — weather is a mild modifier
- 🟡 **8–15%** in winter (cold/snow/ice) — weather deviates from climatology's neutral state

**Interpretation**:
- In the training data (2023–2025), weather was a real observation. **In the forecast (2026–2029), it's climatology** — so WE captures how this month/hour's average weather differs from the model's unconditional baseline.
- **WE % is more informative for the *present* than for the *future***, because it reflects historical weather effects that are baked into the climatology.
- **Don't interpret high WE as "bad weather coming." It means "this month/hour's typical weather (good or bad) matters for traffic."**

---

### EV — Events

> **Abbreviation**: Events  
> **Human-readable**: Special event traffic (Oktoberfest, festivals, concerts)  
> **What it captures**: Special events in the corridor's catchment cities — München, Salzburg, Rosenheim, Kufstein. Includes event count, max impact level, composite impact score, whether the event affects A8/A93 corridors, and whether the event is confirmed or estimated.

**Features included**: `has_special_event`, `active_event_count`, `max_impact_level`, `impact_score`, `affects_a8_ost/a93_sued`, `has_munich/salzburg/rosenheim/kufstein_event`, `has_confirmed/estimated_event`.

**Typical magnitudes**:
- 🟢 **< 5%** — most days have no events
- 🟡 **5–15%** — during major festivals (Oktoberfest, Salzburg Festival)
- 🔴 **EV is often absent** from the string (< 1%) because events are sparse

**Interpretation**:
- EV appears when a **known event** is in the future conditions data. For dates without events in the database, all event features are 0, so EV contributes nothing.
- **If EV appears on a date and you know of additional events not in the table, the model may be underestimating traffic.**

---

### CO — Construction

> **Abbreviation**: Construction  
> **Human-readable**: Roadworks / lane closures  
> **What it captures**: Construction activity, 2+0 two-way single-carriageway configurations, closed lanes, and construction counts on A8/A93.

**Features included**: `has_a8/a93_construction`, `a8/a93_construction_count`, `has_2_plus_0`, `two_plus_0_count`, `max_closed_lanes`, `sum_closed_lanes`, `has_target_bbox_construction`.

**Typical magnitudes**:
- 🟢 **Normally absent** (< 1%) — CO is usually omitted
- 🟡 **5–15%** — on future dates with documented 2+0 closures

**Interpretation**:
- **CO was ~0% in training** (the Autobahn API had no historical roadwork data). The model learned nothing about how roadworks affect traffic.
- **For future dates where 2+0 closures are in the construction table, CO will appear because the features change from their training-time default.** Treat CO values with caution — they reflect a feature perturbation, not a learned effect.
- **For known 2+0 days, apply the capacity-override rule** in the Agent layer (code in `doc/tasks_D_F_G_tutorial.md`) rather than relying on the model's CO contribution.

---

## Volume-Weighted Aggregation

The per-row (hourly) factor contributions are aggregated to one **per-day** string by **weighting each hour's share by that hour's predicted traffic volume (`kfz_h_p50`)**.

This means:
- **Peak hours (11:00, 15:00, etc.) dominate the daily share** — because those hours carry more vehicles.
- **Nighttime hours (midnight–5 AM) barely affect the daily share** — their traffic is low, so their factor mix doesn't distort the day's story.
- **The daily TT percentage reflects when traffic actually happens.** If holiday bump mostly affects midday hours, HO's daily share is proportionally higher.

Mathematically:
```
daily_contribution[factor] = Σ_hour ( kfz_h_p50[hour] × factor_share[hour] ) / Σ_hour kfz_h_p50[hour]
```

---

## Practical Usage Patterns

### 1. Explain why a day is colored red/critical

```python
def explain_day(row):
    parsed = parse_factors(row.factors)
    top_code, top_pct = max(parsed.items(), key=lambda kv: kv[1])

    explanations = {
        "TT": f"This is a {row.direction} direction day near {row.site_id.split('_')[-1]}. "
              f"Traffic here follows its typical high-volume pattern ({top_pct}% of prediction).",
        "HO": f"School holiday travel in Bavaria/Austria drives {top_pct}% of today's prediction. "
              "Expect peak departure/return traffic on the A8 Salzburg corridor.",
        "EV": f"A special event (Oktoberfest / festival) contributes {top_pct}% to today's traffic. "
              "Check events table for details.",
        "WE": f"Weather-related factors (temperature, precipitation patterns) explain {top_pct}% "
              "of the prediction. Expect conditions different from pure historical norm.",
        "CA": f"Calendar timing (month/day-of-week/season) accounts for {top_pct}% — "
              "this is an unusual position in the yearly cycle.",
        "CO": f"Construction/roadworks contribute {top_pct}%. Note: training data had no construction "
              "examples — this reflects the presence of known future closures, not a learned effect.",
    }
    return explanations.get(top_code,
        f"The dominant factor is {top_code} ({top_pct}%).")
```

### 2. Compare two days for the same station

```python
# "Why is August 1 (red) so different from August 8 (yellow)?"
aug1 = parse_factors(factors_row_for('2026-08-01', site))
aug8 = parse_factors(factors_row_for('2026-08-08', site))

diffs = {c: aug1.get(c,0) - aug8.get(c,0) for c in set(aug1)|set(aug8)}
# If HO is +12pp on Aug 1, that's the departure wave vs. a week later.
```

### 3. Identify the "surprising" days

Days where TT is unusually low (< 60%) and HO or EV is elevated are candidates for non-routine traffic management:

```python
for _, row in factors.iterrows():
    p = parse_factors(row.factors)
    if p.get("TT", 100) < 60 and p.get("HO", 0) + p.get("EV", 0) > 20:
        print(f"{row.date} {row.site_id}: outlier day — TT={p['TT']}% HO+EV={p.get('HO',0)+p.get('EV',0)}%")
```

---

## Factor Power Ranking (Completeness Guide)

When presenting factors to an end user, the Agent can summarize like this:

| Dominance | Factor mix pattern | What to tell the user |
|-----------|-------------------|-----------------------|
| TT ≥ 80% | Routine day | "Traffic follows the normal pattern for this corridor. No unusual drivers." |
| TT 60–80% + HO 10–20% | Holiday-affected | "Vacation travel is elevating traffic above normal. Expect holiday patterns." |
| TT 50–70% + HO 15–30% | Peak holiday | "This is a peak travel day — multiple regions' school holidays overlap. Stau risk is elevated." |
| EV ≥ 5% | Event day | "A special event (e.g., Oktoberfest, festival) is driving extra traffic today." |
| CO ≥ 5% | Construction | "Known roadworks may affect capacity. (Note: model has limited training on this — apply the 2+0 override rule.)" |
| WE ≥ 10% | Weather-affected | "Seasonal weather patterns (e.g., winter cold, summer heat) are a meaningful modifier today." |

---

## How It's Calculated (for review)

The attribution uses **feature-group ablation**:

1. Predict `kfz_h_p50` with all 82 features active → **full prediction**.
2. For each of the 6 factor groups (TT/CA/HO/WE/EV/CO), **zero out** that group's features and re-predict → **ablated prediction**.
3. `|full − ablated|` = that group's raw contribution to this hour's prediction.
4. Normalize the 6 contributions to percentages (rows sum to 100).
5. Aggregate to per-day by volume-weighting each hour.

This runs over all 420,768 forecast rows. The resulting 17,532-row daily table is what you read.

**Why ablation, not feature importance?** CatBoost feature importance is *global* — the same number for every row. Ablation is **per-row**, so August 1 (departure Saturday) and March 10 (normal Tuesday) get different Holiday shares — which is what explainability needs.

---

## Version Notes

- **v3 (2026-06-20)**: Removed per-row `factor_contributions` column from `forecast_2026_2029.csv` (file was 107 MB, exceeded GitHub limit). Factor attribution now lives in the compact per-day `factor_attribution_daily.csv` (~1.2 MB). Reduced from 7 groups to 6 by merging "Site Location" into "Typical Traffic" (station identity is population-level constant per station; daily attribution is per-station, so a separate "which station" factor added no per-day insight).
- **v2 (earlier)**: Per-row factor string in the forecast CSV, 7 groups.
- **See also**: `doc/MODEL.md` for the full model architecture and feature inventory.
