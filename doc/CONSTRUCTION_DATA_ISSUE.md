# Construction Data Issue — Root Cause, File Inventory & Fix Guide

> **Status**: 🔴 Known data bug. CSV needs to be replaced with corrected version before re-training.  
> **Discovered**: 2026-06-20  
> **Investigation by**: Claude (data audit)  
> **Target audience**: Whoever rebuilds the construction CSV — teammate, future you, or reviewer.

---

## 1. What's Wrong (Executive Summary)

The merged construction table at `data_autobahn/合并表格，construction日级.csv` — which the CatBoost model reads as training input — was built from a pipeline with **three bugs** and a **fundamental API limitation**. The result:

| Problem | Consequence |
|---------|-------------|
| `is_2_plus_0` decoder too permissive | **91.5% of future days** flagged as 2+0 (should be ~15%) |
| `target_corridor` first-match bbox bug | A93 sites could be mislabeled as A8 |
| `extent` field not parsed (treats string as dict) | All bounding coordinates null |
| Autobahn API has no historical endpoint | Training period (2023–2024) has **zero** usable construction data — this part is correct and unavoidable |

The model currently sees near-zero-variance construction features during training → 0% feature importance. **This is correct behavior given the data**, but the inflated values in 2025 validation and 2026–2029 future periods mean the features are useless even where they shouldn't be.

---

## 2. Complete File Inventory

### 2.1 Primary Data (what the model reads)

| File | Role | Status |
|------|------|--------|
| `Autobahn-hackathon/data_autobahn/合并表格，construction日级.csv` | **The merged daily construction table consumed by the model** | ❌ Buggy — needs replacement |
| `external/construction_daily.parquet` | Corrected daily construction table from `fix_construction_data.py` | ✅ Correct, but different schema (7 cols, per-road rows) |
| `external/construction_sites_clean.csv` | Corrected per-site construction entries (134 rows, raw-ish) | ✅ Correct, useful for cross-validation |

### 2.2 Source Scripts

| File | Status | What it does |
|------|--------|-------------|
| `scripts/fetch_construction_data.py` | ❌ **BUGGY — DO NOT USE** | Original pipeline. Has decoder/corridor/extent bugs. The current merged CSV was built from this. |
| `scripts/fix_construction_data.py` | ✅ **USE THIS** | Corrected pipeline. Run with `--no-fetch` to use cached API data. Outputs `external/construction_daily.parquet` and `external/construction_sites_clean.csv`. |
| `scripts/analyze_construction_lanes.py` | ✅ Reference only | Analysis script. Maps lane configs to stations, builds timeline. Useful for understanding the data, not for pipeline. |

### 2.3 API Cache

| File | Size | Content |
|------|------|---------|
| `external/_autobahn_cache/A8_roadworks.json` | 409 KB | 107 A8 roadworks entries from `verkehr.autobahn.de` |
| `external/_autobahn_cache/A93_roadworks.json` | 106 KB | 27 A93 roadworks entries |
| `external/_autobahn_cache/A8_closures.json` | 2 bytes | Empty (no closures in API) |
| `external/_autobahn_cache/A93_closures.json` | 2 bytes | Empty |
| `external/_autobahn_cache/A8_warnings.json` | 2 bytes | Empty |
| `external/_autobahn_cache/A93_warnings.json` | 2 bytes | Empty |

> The cache was fetched on ~2026-06-19. Re-running `fix_construction_data.py` (without `--no-fetch`) will refresh from the live API. The `--no-fetch` flag reuses these cached files.

### 2.4 Code That References Construction Features

| File | How it uses construction data |
|------|------------------------------|
| `model/model_notebook.ipynb` | **Primary consumer**. Loads the merged CSV via `merge_conditional()`. Uses 9 construction features (see §3). `build_future_grid()` sets all construction to 0 for future prediction. |
| `model/tft.ipynb` | TFT model (teammate). Also loads the merged CSV. |
| `agent/data_loader.py` | Agent data loader. Falls back to `external/construction_sites_clean.csv` if merged CSV missing (line 498). |
| `agent/congestion_score.py` | Congestion scoring logic. References construction features. |
| `model/model_notebook_copy.ipynb` | Backup copy of the notebook. |

### 2.5 Duplicate Files (cross-repo copies)

Both `external/construction_daily.parquet` and `external/construction_sites_clean.csv` exist in **two locations**:

| Root repo copy | Hackathon repo copy | Which is authoritative? |
|---------------|---------------------|------------------------|
| `/autobahn/external/construction_daily.parquet` | `/autobahn/Autobahn-hackathon/external/construction_daily.parquet` | Root copy (output of `fix_construction_data.py`) |
| `/autobahn/external/construction_sites_clean.csv` | `/autobahn/Autobahn-hackathon/external/construction_sites_clean.csv` | Root copy |

> `fix_construction_data.py` writes to the root repo's `external/`. The hackathon repo copies appear to be manual duplicates. When rebuilding, work from the root repo versions.

---

## 3. The Three Bugs in Detail

### Bug 1: `is_2_plus_0` Decoder (PRIMARY — causes the 91.5% inflation)

**File**: `scripts/fetch_construction_data.py`, line 86

**Buggy logic**:
```python
is_2_plus_0 = n_arrow_up > 0 and has_separate
```
Any lane configuration with an opposing-direction arrow + physical separator → flagged as 2+0. This catches ordinary single-lane closures where traffic shifts to the opposite carriageway — these are NOT 2+0 (they're routine lane closures).

**Fixed logic** (`scripts/fix_construction_data.py`, lines 96–101):
```python
is_2_plus_0 = (
    n_arrow_down >= 1
    and n_arrow_up >= 1
    and has_separate
    and n_closed >= 1
)
```
Requires BOTH directions present on the same carriageway + explicit separator + at least one closed lane. This correctly identifies true bidirectional-on-one-carriageway configurations.

**Magnitude**: Future days flagged as 2+0: 91.5% (buggy) vs 15.3% (corrected). ~6× overcount.

### Bug 2: `target_corridor` Assignment

**File**: `scripts/fetch_construction_data.py`, `is_in_target_bbox()` function

**Buggy logic**: Checks A8 bbox first → if match, returns `"A8_Ost"`. A93 sites with coordinates in both bboxes get mislabeled as A8.

**Fixed logic** (`scripts/fix_construction_data.py`): Each site assigned to the road its API endpoint came from, AND verified by that road's bbox. No cross-contamination.

### Bug 3: `extent` Field Parsing

**File**: `scripts/fetch_construction_data.py`, line 254

**Buggy logic**: Treats `extent` as a dict:
```python
extent = entry.get("extent", {})
ext_from_lat = extent.get("lat")  # → None (extent is a string!)
```

**Fixed logic** (`scripts/fix_construction_data.py`, `parse_extent()` function): The API returns `extent` as `"lat1,lon1,lat2,lon2"`. Correctly parses this string format.

---

## 4. The Root Cause: API Has No Historical Data

Even with all three bugs fixed, **training period (2023–2024) has zero construction data**. This is NOT a scraper bug — it's a fundamental API limitation.

| Period | Buggy CSV | Corrected Data | Why |
|--------|-----------|----------------|-----|
| 2023-01 → 2024-11 (703d) | has_construction: **0** | is_construction_active: **0** | API has no historical endpoint |
| 2024-12 (28d) | has_construction: **28** (A8 only, no bbox, no lane closures) | is_construction_active: **0** | API returned 2 A8 far-away entries; bbox filter correctly excludes them |
| 2025 (365d) | has_construction: **365/365 (100%)** ← inflated | is_construction_active: **128/365 (35.1%)** | API returns current+future only; buggy decoder inflated counts |
| 2026–2029 (1461d) | has_2_plus_0: **1337/1461 (91.5%)** ← inflated by decoder bug | is_2_plus_0_active: **224/1461 (15.3%)** | Future plan data; decoder bug caused ~6× overcount |

**Bottom line**: The Autobahn API (`verkehr.autobahn.de`) is a **live/planned roadworks feed**, not a historical archive. It cannot provide 2023–2024 data regardless of how the scraper is written.

---

## 5. Script Usability Assessment

### `fix_construction_data.py` — ✅ Ready to use

```bash
cd /Users/huang/Desktop/codenew/autobahn

# Reuse cached API data (fast, no network):
.venv/bin/python scripts/fix_construction_data.py --no-fetch

# Or re-fetch from live API (if cache is stale):
.venv/bin/python scripts/fix_construction_data.py
```

**Outputs**:
- `external/construction_sites_clean.csv` — 134 per-site entries with lane config details
- `external/construction_daily.parquet` — 5,114 rows (2557 days × 2 roads), ready for model consumption

**What it does correctly**:
- ✅ Strict 2+0 detection
- ✅ Per-road bbox assignment (no cross-contamination)
- ✅ Correct `extent` string parsing
- ✅ Filters to target corridors (A8_Ost, A93_Sued)
- ✅ Date expansion from start/end timestamps → daily rows

**What it does NOT do** (gaps to be aware of):
- ❌ Does not aggregate `n_closed_lanes` to the daily level (only `n_sites_active`, `n_2plus0_active`, and booleans)
- ❌ Does not output in the 30-column merged CSV schema the model expects
- ❌ Does not write to `data_autobahn/` (outputs go to `external/`)

### `fetch_construction_data.py` — ❌ DO NOT USE

All three bugs are in this file. The current merged CSV was built from its output. Retain for reference only.

### `analyze_construction_lanes.py` — ✅ Reference only

Read-only analysis. Maps construction sites to measurement stations and builds timeline views. Not part of any data pipeline.

---

## 6. How to Fix (Step-by-Step Guide for the Next Person)

### Prerequisites

- `.venv` Python with `pandas`, `pyarrow`, `requests`
- Git access to both repos

### Step 1: Get Fresh Construction Data

If you have **newly scraped construction data** (e.g., from a refreshed API fetch or a different data source), replace or supplement the API cache:

```bash
# Option A: Re-fetch from live API
cd /Users/huang/Desktop/codenew/autobahn
.venv/bin/python scripts/fix_construction_data.py

# Option B: Use existing cache (if no new data)
.venv/bin/python scripts/fix_construction_data.py --no-fetch
```

### Step 2: Cross-Validate

Compare the corrected data against any new data source:

```python
import pandas as pd
fixed = pd.read_parquet("external/construction_daily.parquet")
# ... compare against new source
```

Key things to verify:
- Number of 2+0 days per year (expect 0 for 2023–2024, <20% for future)
- Construction site titles match known projects (see `scripts/fetch_construction_data.py` §Known Projects)
- Dates align with publicly announced maintenance schedules

### Step 3: Transform to Merged CSV Schema

The corrected `external/construction_daily.parquet` has a different schema from what the model expects:

| Fixed table (7 cols) | Merged table (30 cols) |
|---------------------|----------------------|
| `date`, `road` (A8_Ost / A93_Sued) | `date` (one row per day, A8+A93 merged) |
| `is_construction_active` (bool) | `has_construction`, `has_a8_construction`, `has_a93_construction` (int 0/1) |
| `n_sites_active` (int) | `construction_count`, `a8_construction_count`, `a93_construction_count` |
| `is_2_plus_0_active` (bool) | `has_2_plus_0` (int 0/1) |
| `n_2plus0_active` (int) | `two_plus_0_count` |
| (not in daily agg) | `max_closed_lanes`, `sum_closed_lanes` → fill with 0 |

You need to write a transformation script that:
1. Reads `external/construction_daily.parquet`
2. Pivots from per-road to per-date (A8_Ost + A93_Sued → single row per date)
3. Maps column names to match the 30-column schema
4. Preserves the 2-row header format (Row 0 = English col names, Row 1 = Chinese description)
5. Overwrites `Autobahn-hackathon/data_autobahn/合并表格，construction日级.csv`

> ⚠️ **Important**: The output format must match the original exactly. Row 0 = `date;weekday_iso;...` (English headers), Row 1 = `日期;星期(1=周一..7=周日);...` (Chinese description, skipped by `skiprows=[1]`). All 30 columns must be present in the original order. Missing columns → KeyError in the notebook's `make_pool()`.

### Step 4: Verify

```python
import pandas as pd
v = pd.read_csv("data_autobahn/合并表格，construction日级.csv", sep=";", skiprows=[1])
v['date'] = pd.to_datetime(v['date'])

# Training should still be 0 (API limitation, correct)
assert v[v['date'] <= '2024-12-31']['has_2_plus_0'].sum() == 0

# 2025 should have reasonable construction coverage (not 100%)
val = v[(v['date'] >= '2025-01-01') & (v['date'] <= '2025-12-31')]
assert val['has_construction'].mean() < 0.5

# Future should have reasonable 2+0 coverage (not 91.5%)
future = v[v['date'] >= '2026-01-01']
assert future['has_2_plus_0'].mean() < 0.3
```

### Step 5: Re-run Model Training

```
Open model/model_notebook.ipynb in VS Code
Select autobahn_venv kernel
Restart Kernel → Run All
```

Expected: metrics unchanged (construction features still near-zero importance during training). But the feature values are now honest, and the pipeline is clean for future work.

---

## 7. Long-Term: Beyond the API

The Autobahn API cannot provide historical construction data. For the model to actually learn 2+0 effects, you need:

1. **Historical construction records** from Autobahn GmbH internal archives (Baustellenarchiv / Verkehrsmanagement-Zentrale)
2. **Future planned closures** — the API provides some, but a comprehensive list from the Autobahn GmbH planning department would be more reliable

Until then, rule-based post-processing (Task D in `tasks_D_F_G_tutorial.md`) remains the only way to express known 2+0 capacity effects on predictions.

---

## 8. Cross-Validation: API vs Wayback Archive (2026-06-20)

### Two Independent Data Sources

| Source | Method | Coverage | Geographic Precision |
|--------|--------|----------|---------------------|
| **API** (`fix_construction_data.py`) | `verkehr.autobahn.de` live roadworks feed | 2025–2027 (near-term + planned) | ✅ Bbox-filtered to target corridors |
| **Wayback** (`construction/` teammate) | Internet Archive CDX + `autobahn.de` Projektübersicht snapshots | 2023–2026 (broader history) | ❌ Entire A8/A93 length across Germany |

### Overlapping Projects Found

Only **one project** appears in both sources within the target corridor:

| Project | API (coordinates) | Wayback (status) | Dates Match? |
|---------|-------------------|------------------|--------------|
| **Rohrdorfer Ache bridge** (Rosenheim–Rohrdorf) | ✅ "A8 \| Rosenheim - Rohrdorf" 2+0, lat=47.806, lon=12.133 | ✅ "A8 Erneuerung der Autobahnbrücke über die Rohrdorfer Ache", "In Umsetzung" | ✅ API: 2026-07-01–2026-11-01. Wayback confirms project exists and is active. |

This single-match cross-validation confirms the API data is directionally correct for the projects it covers.

### Projects Found Only in Wayback (Not Yet in API)

| Project | Road | Status | Location | Why Not in API |
|---------|------|--------|----------|----------------|
| Saalach bridge (Piding) | A8 | "In Planung" | Near Salzburg border, km ~110 | Planning stage — no construction dates yet |
| Oberaudorf bridge (Tiroler Str.) | A93 | "In Planung" | Near Kiefersfelden border | Planning stage — no construction dates yet |

These are **pre-construction planning projects** — they have no timelines, so they can't be included in daily construction features. Monitor the API for when they move to "In Umsetzung."

### Historical Events Assessment

The teammate's 10 curated historical events from 2023 are all geographically **outside the target corridor**:
- A8 events: Neunkirchen, Dillingen, Landertalbrücke (all in Saarland, ~500km away), Mangfallbrücke (closest but still west of Rosenheim), Kirchheim-Ost/Aichelberg (near Stuttgart)
- A93 events: Eichelbachbrücke, Weiden, Schwarzenfeld (all in Nordbayern near Regensburg, ~300km away)

**Conclusion**: The Wayback data confirms what the API tells us — there is **no discoverable historical construction data for the A8 Ost / A93 Süd target corridors in 2023–2024**. This isn't a scraping failure; these corridors simply had no major documented construction during that period, or it was published on pages that weren't archived.

### Verification of API-Only Data Quality

The API found 6 true 2+0 sites in the target corridor (all for 2026):

| Site | Road | Dates | Closed Lanes |
|------|------|-------|-------------|
| Rosenheim → Rohrdorf | A8 | 2026-07-01 – 2026-07-17 | 2 |
| Rohrdorf → Rosenheim | A8 | 2026-07-01 – 2026-07-17 | 2 |
| Übersee → Grabenstätt | A8 | 2026-03-21 – 2026-10-30 | 2 |
| Grabenstätt → Übersee | A8 | 2026-03-21 – 2026-10-30 | 2 |
| Reischenhart → Nicklheim | A93 | 2026-04-18 – 2026-09-14 | 3 |
| Nicklheim → Reischenhart | A93 | 2026-04-18 – 2026-09-14 | 3 |

Each pair represents both directions of the same construction project. The lane configurations (CLOSED + SEPARATE + ARROW_DOWN + ARROW_UP) are textbook 2+0 patterns. The dates align with the summer construction season typical for Alpine corridors.

---

## 9. What Was Done (2026-06-20 Fix)

### Fixed CSV Generated

```bash
.venv/bin/python scripts/rebuild_construction_csv.py
```

**Input**: `external/construction_daily.parquet` (corrected, from `fix_construction_data.py --no-fetch`)  
**Output**: `Autobahn-hackathon/data_autobahn/合并表格，construction日级.csv` (overwritten)

### Key Changes vs Buggy CSV

| Metric | Buggy (old) | Corrected (new) |
|--------|------------|-----------------|
| 2023–2024 construction days | 28 (all A8, wrong bbox) | **0** (correct — API limitation) |
| 2025 construction coverage | 100% | **35.1%** (A8 only) |
| 2026–2029 2+0 coverage | **91.5%** (inflated) | **15.3%** (correct) |
| 2026–2029 construction coverage | ~91% | **37.6%** |

### Model Impact

- **Training**: Unchanged (still 0 construction in 2023–2024). Construction features will remain near-zero importance — this is correct.
- **Validation (2025)**: Now has honest construction values. Previously 100% → now 35.1%.
- **Forecast (2026–2029)**: 2+0 coverage dropped from 91.5% → 15.3%. The model will no longer see near-constant construction flags in future periods.

### Remaining Gaps

1. **No 2023–2024 historical data** — cannot train the model to learn 2+0 effects. Rule-based capacity overrides (Task D) remain the only mitigation.
2. **API coverage drops after 2027** — the API only has near-term plans. 2028–2029 have zero construction entries, which may be optimistic.
3. **A93 2025 has zero construction in API** — but the model's validation set (2025) should ideally contain some construction events to test robustness.
4. **No A93 Süd congestion plots** — ConsystPlots are A8-only, so we can't visually verify A93 construction impacts.

---

## 10. Related Documents

| Document | Relevance |
|----------|-----------|
| `doc/MODEL.md` §6.1 | Model limitation summary (brief version of this doc) |
| `doc/tasks_D_F_G_tutorial.md` §D | Capacity override post-processing code |
| `../CLAUDE.md` §4 (Congestion Plots) | ConsystPlots are A8-only, not machine-readable |
| `../CLAUDE.md` §Key Technical Issues | Construction 0% importance: verified correct |
| `construction/README.md` | Teammate's Wayback collection methodology |
| `../scripts/rebuild_construction_csv.py` | **NEW** — transformation script: parquet → merged CSV |
| `../scripts/fix_construction_data.py` | Corrected API pipeline (fixes 3 bugs from original) |

---

*Written 2026-06-20. CSV replaced with corrected version on 2026-06-20. Cross-validation against Wayback archive completed same day. The fix script and transformation logic are ready — the blocker is the fundamental API historical data gap, not the code.*
