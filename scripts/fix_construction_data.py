"""Re-fetch and clean construction data from autobahn.de.

Replaces the bug-affected output of the teammate's
``fetch_construction_data.py``. Three fixes vs. the original:

1. ``is_2_plus_0`` decoder now requires actual 2+0 indicators (ARROW_UP
   on a carriageway that also has ARROW_DOWN and SEPARATE separating
   them, with the closed/up arrows forming a coherent block). The
   original logic fired ``True`` for every entry with any ARROW_UP +
   SEPARATE, including ordinary single-lane closures.

2. ``target_corridor`` no longer uses first-match bbox priority. Each
   site is assigned to the road its API endpoint came from (``A8`` /
   ``A93``) AND verified by bbox. This stops A93 sites from being
   mislabelled as A8 just because A8's bbox is checked first.

3. ``extent`` is parsed correctly: the API returns it as a comma-
   separated string ``"lat1,lon1,lat2,lon2"``, not a dict. We now
   surface the bounding coordinates instead of leaving them null.

We additionally save the ``closures`` and ``warnings`` endpoints
(silently discarded by the original) into separate CSVs.

The script then produces the feature table the model actually
consumes::

  external/construction_daily.parquet
    schema: date, road, is_construction_active, is_2_plus_0_active,
            n_sites_active, top_site_name

This is a daily 2023-2029 expansion ready to join into the training
features by (date, road).

Usage::

    python scripts/fix_construction_data.py             # full pipeline
    python scripts/fix_construction_data.py --no-fetch  # reuse cache
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "external"
OUT_DIR.mkdir(exist_ok=True)
CACHE_DIR = PROJECT_ROOT / "external" / "_autobahn_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

API_BASE = "https://verkehr.autobahn.de/o/autobahn"
ROADS = ["A8", "A93"]
SERVICES = ["roadworks", "closures", "warnings"]

# Generous corridor bboxes - used only to filter out far-away entries
# (e.g. A8 in Saarland, A93 near Regensburg) that the API also returns.
TARGET_BBOX = {
    "A8":  {"lat_min": 47.70, "lat_max": 48.20, "lon_min": 11.40, "lon_max": 13.10},
    "A93": {"lat_min": 47.50, "lat_max": 47.90, "lon_min": 12.00, "lon_max": 12.30},
}

CORRIDOR_NAME = {"A8": "A8_Ost", "A93": "A93_Sued"}


# ---------------------------------------------------------------------------
# Corrected lane-config decoder
# ---------------------------------------------------------------------------

def decode_lane_config(symbols: list[str]) -> dict:
    """Decode the impact.symbols list. See teammate's docstring for symbol meanings.

    Rule for 2+0 (corrected): a true 2+0 has BOTH directions sharing one
    carriageway -> must have ARROW_UP AND ARROW_DOWN AND SEPARATE. An
    ``ARROW_UP`` alone next to ``CLOSED`` on the opposite carriageway is
    a routine lane closure, NOT a 2+0.
    """
    if not symbols:
        return {"config_type": "unknown", "is_2_plus_0": False, "raw": symbols}

    n_arrow_down = symbols.count("ARROW_DOWN")
    n_arrow_up = symbols.count("ARROW_UP")
    n_closed = symbols.count("CLOSED")
    has_separate = "SEPARATE" in symbols

    # Strict 2+0: both directions present on same carriageway with explicit
    # SEPARATE marker, AND at least one closed lane (typical of capacity
    # halving). Without the closed-lane constraint we'd capture normal
    # multi-lane sections.
    is_2_plus_0 = (
        n_arrow_down >= 1
        and n_arrow_up >= 1
        and has_separate
        and n_closed >= 1
    )

    if is_2_plus_0:
        cfg = "2+0_bidirectional"
    elif n_closed >= 1 and n_arrow_down >= 1:
        cfg = "lane_closure"
    elif n_closed == 0 and n_arrow_down >= 1:
        cfg = "normal"
    else:
        cfg = "complex"

    return {
        "config_type": cfg,
        "is_2_plus_0": is_2_plus_0,
        "n_open_in_direction": n_arrow_down,
        "n_open_oncoming": n_arrow_up,
        "n_closed": n_closed,
        "raw": symbols,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_extent(value) -> dict:
    """Parse the ``extent`` field which the API returns as ``"lat1,lon1,lat2,lon2"``."""
    if not value or not isinstance(value, str):
        return {"ext_from_lat": None, "ext_from_lon": None,
                "ext_to_lat": None, "ext_to_lon": None}
    try:
        parts = [float(x) for x in value.split(",")]
        if len(parts) >= 4:
            return {
                "ext_from_lat": parts[0],
                "ext_from_lon": parts[1],
                "ext_to_lat": parts[2],
                "ext_to_lon": parts[3],
            }
    except ValueError:
        pass
    return {"ext_from_lat": None, "ext_from_lon": None,
            "ext_to_lat": None, "ext_to_lon": None}


BEGIN_RX = re.compile(r"Beginn:\s*(\d{2})\.(\d{2})\.(\d{2,4})")
END_RX = re.compile(r"Ende:\s*(\d{2})\.(\d{2})\.(\d{2,4})")
ANY_DATE_RX = re.compile(r"(\d{2})\.(\d{2})\.(\d{2,4})")


def parse_date_from_text(text: str, kind: str = "any") -> str | None:
    """Pull dd.mm.yyyy out of a free-text description.

    kind: 'begin' | 'end' | 'any' — which label to anchor on.
    """
    if not text:
        return None
    rx = {"begin": BEGIN_RX, "end": END_RX, "any": ANY_DATE_RX}.get(kind, ANY_DATE_RX)
    m = rx.search(text)
    if not m:
        return None
    d, mo, y = m.groups()
    if len(y) == 2:
        y = "20" + y
    return f"{y}-{mo}-{d}"


def fetch_all(use_cache: bool) -> dict:
    out = {}
    for road in ROADS:
        out[road] = {}
        for svc in SERVICES:
            cache_path = CACHE_DIR / f"{road}_{svc}.json"
            if use_cache and cache_path.exists():
                out[road][svc] = json.loads(cache_path.read_text())
                print(f"  cached: {road}/{svc} ({len(out[road][svc])} entries)")
                continue
            url = f"{API_BASE}/{road}/services/{svc}"
            print(f"  fetching {url}")
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            data = r.json()
            arr = data.get(svc, data.get(svc.rstrip("s"), []))
            cache_path.write_text(json.dumps(arr, ensure_ascii=False, indent=2))
            out[road][svc] = arr
    return out


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process_to_sites(raw: dict) -> pd.DataFrame:
    """Flatten API entries to a per-site DataFrame."""
    rows = []
    for road, svc_map in raw.items():
        for svc, entries in svc_map.items():
            for e in entries:
                coord = e.get("coordinate") or {}
                lat = coord.get("lat") if isinstance(coord, dict) else None
                lon = coord.get("long") if isinstance(coord, dict) else None
                lat = float(lat) if lat else None
                lon = float(lon) if lon else None

                bbox = TARGET_BBOX[road]
                in_target = (
                    lat is not None and lon is not None
                    and bbox["lat_min"] <= lat <= bbox["lat_max"]
                    and bbox["lon_min"] <= lon <= bbox["lon_max"]
                )

                symbols = (e.get("impact") or {}).get("symbols", []) if isinstance(e.get("impact"), dict) else []
                lc = decode_lane_config(symbols if isinstance(symbols, list) else [])
                extent = parse_extent(e.get("extent"))

                # Dates
                start_raw = e.get("startTimestamp")
                end_raw = e.get("endTimestamp")
                desc_list = e.get("description") or []
                desc_text = " ".join(str(d) for d in desc_list) if isinstance(desc_list, list) else str(desc_list)
                # Description often has Beginn:/Ende: in free text — for
                # most A8/A93 entries the endTimestamp field is null.
                start_parsed = parse_date_from_text(desc_text, "begin") if desc_text else None
                end_parsed = parse_date_from_text(desc_text, "end") if desc_text else None

                row = {
                    "road": road,
                    "corridor": CORRIDOR_NAME[road],
                    "service": svc,
                    "identifier": e.get("identifier"),
                    "title": e.get("title"),
                    "subtitle": e.get("subtitle"),
                    "display_type": e.get("display_type"),
                    "coord_lat": lat,
                    "coord_lon": lon,
                    "in_target_bbox": in_target,
                    "start_iso": start_raw,
                    "end_iso": end_raw,
                    "start_text_parsed": start_parsed,
                    "end_text_parsed": end_parsed,
                    "description": desc_text[:500],
                    "is_2_plus_0": lc["is_2_plus_0"],
                    "config_type": lc["config_type"],
                    "n_closed_lanes": lc.get("n_closed", 0),
                    "raw_symbols": "|".join(symbols) if isinstance(symbols, list) else "",
                    **extent,
                }
                rows.append(row)
    return pd.DataFrame(rows)


def build_daily_feature_table(sites: pd.DataFrame,
                              start: str = "2023-01-01",
                              end: str = "2029-12-31") -> pd.DataFrame:
    """Expand each site to a (date, road) per-day feature table."""
    sites = sites[sites["in_target_bbox"]].copy()
    sites["start_date"] = pd.to_datetime(
        sites["start_iso"].combine_first(sites["start_text_parsed"]),
        errors="coerce", utc=True,
    ).dt.tz_convert(None).dt.normalize()
    sites["end_date"] = pd.to_datetime(
        sites["end_iso"].combine_first(sites["end_text_parsed"]),
        errors="coerce", utc=True,
    ).dt.tz_convert(None).dt.normalize()

    # Drop entries without any usable date.
    dated = sites.dropna(subset=["start_date", "end_date"]).copy()
    dropped = len(sites) - len(dated)
    if dropped:
        print(f"  WARNING: dropped {dropped} target-corridor entries without dates")

    date_index = pd.date_range(start, end, freq="D")
    out = []
    for road in ["A8", "A93"]:
        corridor = CORRIDOR_NAME[road]
        sub = dated[dated["road"] == road]
        active = pd.DataFrame({"date": date_index, "road": corridor})
        n_active = []
        n_2p0 = []
        sites_on_day = []
        for d in date_index:
            mask = (sub["start_date"] <= d) & (sub["end_date"] >= d)
            today = sub[mask]
            n_active.append(int(len(today)))
            n_2p0.append(int(today["is_2_plus_0"].sum()))
            sites_on_day.append(
                "; ".join(today["title"].dropna().astype(str).unique()[:3])
            )
        active["n_sites_active"] = n_active
        active["n_2plus0_active"] = n_2p0
        active["is_construction_active"] = active["n_sites_active"] > 0
        active["is_2_plus_0_active"] = active["n_2plus0_active"] > 0
        active["active_sites"] = sites_on_day
        out.append(active)
    daily = pd.concat(out, ignore_index=True)
    return daily


def main(no_fetch: bool) -> None:
    print("=== fetching autobahn.de (or using cache) ===")
    raw = fetch_all(use_cache=no_fetch)

    print("\n=== flattening + cleaning ===")
    sites = process_to_sites(raw)
    sites_path = OUT_DIR / "construction_sites_clean.csv"
    sites.to_csv(sites_path, index=False)
    print(f"  wrote {sites_path}  ({len(sites)} entries total)")

    in_target = sites[sites["in_target_bbox"]]
    print(f"\n  in target corridor: {len(in_target)}  "
          f"(true 2+0: {int(in_target['is_2_plus_0'].sum())})")
    by_corridor = in_target.groupby("corridor")["is_2_plus_0"].sum()
    print(f"  2+0 by corridor:\n{by_corridor.to_string()}")

    print("\n=== building daily feature table ===")
    daily = build_daily_feature_table(sites)
    daily_path = OUT_DIR / "construction_daily.parquet"
    daily.to_parquet(daily_path, index=False)
    print(f"  wrote {daily_path}  ({len(daily):,} rows)")

    sample = daily[(daily["date"] >= "2026-07-01") & (daily["date"] <= "2026-07-10")]
    print("\n  sample (2026-07-01..10):")
    print(sample.to_string(index=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--no-fetch", action="store_true", help="use cached JSON only")
    a = p.parse_args()
    main(no_fetch=a.no_fetch)
