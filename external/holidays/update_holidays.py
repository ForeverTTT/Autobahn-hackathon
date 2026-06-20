#!/usr/bin/env python3
"""Download public and school holidays for Bavaria, Salzburg and Tyrol."""

from __future__ import annotations

import csv
import json
import time
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://openholidaysapi.org"
START_DATE = date(2023, 1, 1)
END_DATE = date(2029, 12, 31)
OUTPUT_DIR = Path(__file__).resolve().parent
AUSTRIAN_SCHOOL_LAW_URL = (
    "https://ris.bka.gv.at/NormDokument.wxe?"
    "Abfrage=Bundesnormen&Gesetzesnummer=10009575&Paragraf=2"
)

TARGET_REGIONS = {
    "DE-BY": {"country_code": "DE", "country_name": "Germany", "region_name": "Bavaria"},
    "AT-SB": {"country_code": "AT", "country_name": "Austria", "region_name": "Salzburg"},
    "AT-TI": {"country_code": "AT", "country_name": "Austria", "region_name": "Tyrol"},
}

TYPE_CLASS = {
    "Public": "public_holiday",
    "Bank": "bank_holiday",
    "Optional": "optional_holiday",
    "School": "school_holiday",
    "BackToSchool": "school_marker",
    "EndOfLessons": "school_marker",
}


def fetch_json(path: str, params: dict[str, str] | None = None) -> Any:
    url = f"{API_BASE}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "Autobahn-Hackathon-Holiday-Importer/2.0"})
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            with urlopen(request, timeout=45) as response:
                return json.load(response)
        except Exception as exc:
            last_error = exc
            if attempt == 3:
                break
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Could not download {url}: {last_error}")


def localized_text(values: list[dict[str, str]] | None) -> str:
    if not values:
        return ""
    for preferred in ("EN", "DE"):
        for item in values:
            if item.get("language", "").upper() == preferred:
                return item.get("text", "")
    return values[0].get("text", "")


def download_holidays(endpoint: str, country_code: str, region_code: str) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for year in range(START_DATE.year, END_DATE.year + 1):
        data = fetch_json(
            f"/{endpoint}",
            {
                "countryIsoCode": country_code,
                "subdivisionCode": region_code,
                "validFrom": f"{year}-01-01",
                "validTo": f"{year}-12-31",
                "languageIsoCode": "EN",
            },
        )
        for item in data:
            subdivision_codes = {
                ref["code"] for ref in (item.get("subdivisions") or [])
            }
            applies_to_whole_region = item.get("nationwide") or region_code in subdivision_codes
            if applies_to_whole_region:
                records[item["id"]] = item
    return list(records.values())


def easter_sunday(year: int) -> date:
    """Return Gregorian Easter Sunday using the Meeus/Jones/Butcher algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month = (h + ell - 7 * m + 114) // 31
    day = (h + ell - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (occurrence - 1))


def first_weekday_on_or_after(day: date, weekday: int) -> date:
    return day + timedelta(days=(weekday - day.weekday()) % 7)


def statutory_austrian_school_holidays(year: int, region_code: str) -> list[dict[str, Any]]:
    """Calculate Austrian school holidays fixed by current statutory rules."""
    easter = easter_sunday(year)
    pentecost = easter + timedelta(days=49)
    semester_start = nth_weekday(year, 2, 0, 2)
    summer_start = first_weekday_on_or_after(date(year, 7, 5), 5)
    next_school_start = nth_weekday(year, 9, 0, 2)

    periods = [
        ("Semester Holidays", semester_start, semester_start + timedelta(days=5)),
        ("Easter Holidays", easter - timedelta(days=8), easter + timedelta(days=1)),
        (
            "Pentecost Holidays",
            pentecost - timedelta(days=1),
            pentecost + timedelta(days=1),
        ),
        ("Summer Holidays", summer_start, next_school_start - timedelta(days=1)),
        ("Autumn Holidays", date(year, 10, 27), date(year, 10, 31)),
        ("All Souls' Day", date(year, 11, 2), date(year, 11, 2)),
        ("Christmas Holidays", date(year, 12, 24), date(year + 1, 1, 6)),
    ]
    if region_code == "AT-SB":
        periods.append(("Saint Rupert's Day", date(year, 9, 24), date(year, 9, 24)))
    if region_code == "AT-TI":
        periods.append(("Saint Joseph's Day", date(year, 3, 19), date(year, 3, 19)))

    result = []
    for name, start, end in periods:
        id_scope = region_code if name in {"Saint Rupert's Day", "Saint Joseph's Day"} else "AT"
        record_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"at-school-law:{id_scope}:{name}:{start.isoformat()}:{end.isoformat()}",
            )
        )
        result.append(
            {
                "id": record_id,
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "type": "School",
                "name": [{"language": "EN", "text": name}],
                "regionalScope": "Regional",
                "temporalScope": "FullDay",
                "nationwide": False,
                "subdivisions": [{"code": region_code, "shortName": region_code[3:]}],
                "_source_provider": "Austrian statutory school-calendar rules",
                "_source_url": AUSTRIAN_SCHOOL_LAW_URL,
                "_verification_status": "calculated_from_current_law",
                "_record_origin": "statutory_calculation",
            }
        )
    return result


def add_missing_austrian_2029(
    holidays: list[dict[str, Any]], region_code: str
) -> list[dict[str, Any]]:
    """Complete 2029 where the published API calendar currently stops in January."""
    by_signature = {
        (item["startDate"], item["endDate"], localized_text(item.get("name")))
        for item in holidays
    }
    result = list(holidays)
    for item in statutory_austrian_school_holidays(2029, region_code):
        signature = (item["startDate"], item["endDate"], localized_text(item.get("name")))
        if signature not in by_signature:
            result.append(item)
    return result


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def wave_window(anchor: date, wave: str) -> tuple[date, date]:
    if wave == "departure":
        if anchor.weekday() == 0:
            return anchor - timedelta(days=3), anchor
        if anchor.weekday() == 5:
            return anchor - timedelta(days=1), anchor + timedelta(days=1)
        return anchor - timedelta(days=1), anchor + timedelta(days=2)
    if anchor.weekday() == 0:
        return anchor - timedelta(days=3), anchor
    if anchor.weekday() == 6:
        return anchor - timedelta(days=2), anchor
    return anchor - timedelta(days=2), anchor


def build_traffic_windows(
    period_rows: list[dict[str, Any]],
    scope_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    scopes_by_record: dict[str, set[str]] = defaultdict(set)
    for row in scope_rows:
        scopes_by_record[row["record_id"]].add(row["region_code"])

    candidates: list[dict[str, Any]] = []
    for row in period_rows:
        if row["holiday_class"] != "school_holiday" or int(row["duration_days"]) < 3:
            continue
        regions = scopes_by_record[row["record_id"]]
        for wave, anchor_text in (
            ("departure", row["start_date"]),
            ("return", row["end_date"]),
        ):
            window_start, window_end = wave_window(date.fromisoformat(anchor_text), wave)
            clipped_start = max(window_start, START_DATE)
            clipped_end = min(window_end, END_DATE)
            if clipped_start > clipped_end:
                continue
            candidates.append(
                {
                    "start": clipped_start,
                    "end": clipped_end,
                    "wave": wave,
                    "regions": set(regions),
                    "holiday_names": {row["name"]},
                    "origins": {row["record_origin"]},
                }
            )

    windows: list[dict[str, Any]] = []
    for wave in ("departure", "return"):
        wave_candidates = sorted(
            (row for row in candidates if row["wave"] == wave),
            key=lambda row: (row["start"], row["end"]),
        )
        merged: list[dict[str, Any]] = []
        for row in wave_candidates:
            if merged and row["start"] <= merged[-1]["end"] + timedelta(days=1):
                merged[-1]["end"] = max(merged[-1]["end"], row["end"])
                merged[-1]["regions"].update(row["regions"])
                merged[-1]["holiday_names"].update(row["holiday_names"])
                merged[-1]["origins"].update(row["origins"])
            else:
                merged.append(
                    {
                        "start": row["start"],
                        "end": row["end"],
                        "wave": wave,
                        "regions": set(row["regions"]),
                        "holiday_names": set(row["holiday_names"]),
                        "origins": set(row["origins"]),
                    }
                )
        windows.extend(merged)

    windows.sort(key=lambda row: (row["start"], row["wave"]))
    output = []
    for index, row in enumerate(windows, start=1):
        region_count = len(row["regions"])
        contains_summer = "Summer Holidays" in row["holiday_names"]
        if contains_summer and region_count == 3:
            risk = "extreme"
        elif contains_summer or region_count == 3:
            risk = "very_high"
        elif region_count == 2:
            risk = "high"
        else:
            risk = "medium"
        direction = "outbound" if row["wave"] == "departure" else "return"
        output.append(
            {
                "window_id": f"TW-{index:03d}",
                "start_date": row["start"].isoformat(),
                "end_date": row["end"].isoformat(),
                "risk_level": risk,
                "expected_direction": direction,
                "a8_direction": "A8 toward Salzburg" if direction == "outbound" else "A8 toward Munich",
                "a93_direction": (
                    "A93 toward Kiefersfelden"
                    if direction == "outbound"
                    else "A93 toward Rosenheim"
                ),
                "regions": "|".join(sorted(row["regions"])),
                "holiday_names": "|".join(sorted(row["holiday_names"])),
                "record_origins": "|".join(sorted(row["origins"])),
                "assessment_status": "rule_derived",
            }
        )
    return output


def main() -> None:
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    records: dict[str, dict[str, Any]] = {}
    record_endpoints: dict[str, str] = {}
    record_regions: dict[str, set[str]] = defaultdict(set)
    coverage_rows: list[dict[str, Any]] = []

    for region_code, region in TARGET_REGIONS.items():
        for endpoint, dataset_type in (
            ("PublicHolidays", "public"),
            ("SchoolHolidays", "school"),
        ):
            holidays = download_holidays(endpoint, region["country_code"], region_code)
            if endpoint == "SchoolHolidays" and region["country_code"] == "AT":
                holidays = add_missing_austrian_2029(holidays, region_code)
            statistics = fetch_json(
                f"/Statistics/{endpoint}",
                {
                    "countryIsoCode": region["country_code"],
                    "subdivisionCode": region_code,
                },
            )
            starts = [item["startDate"] for item in holidays]
            ends = [item["endDate"] for item in holidays]
            years_with_records = {
                year: any(
                    date.fromisoformat(item["startDate"]).year <= year
                    <= date.fromisoformat(item["endDate"]).year
                    for item in holidays
                )
                for year in range(START_DATE.year, END_DATE.year + 1)
            }
            api_record_count = sum(
                item.get("_record_origin", "api") == "api" for item in holidays
            )
            calculated_record_count = len(holidays) - api_record_count
            coverage_rows.append(
                {
                    "region_code": region_code,
                    "region_name": region["region_name"],
                    "country_code": region["country_code"],
                    "country_name": region["country_name"],
                    "dataset_type": dataset_type,
                    "oldest_available_start_date": statistics.get("oldestStartDate", ""),
                    "latest_available_start_date": statistics.get("youngestStartDate", ""),
                    "target_first_record_start": min(starts) if starts else "",
                    "target_last_record_start": max(starts) if starts else "",
                    "target_last_record_end": max(ends) if ends else "",
                    "target_record_count": len(holidays),
                    "api_record_count": api_record_count,
                    "calculated_record_count": calculated_record_count,
                    "coverage_status": (
                        "mixed_api_and_statutory_calculation"
                        if calculated_record_count
                        else "api"
                    ),
                    **{
                        f"has_any_record_overlap_{year}": str(years_with_records[year]).lower()
                        for year in range(START_DATE.year, END_DATE.year + 1)
                    },
                    "retrieved_at": retrieved_at,
                }
            )
            for item in holidays:
                records[item["id"]] = item
                record_endpoints[item["id"]] = endpoint
                record_regions[item["id"]].add(region_code)

    period_rows: list[dict[str, Any]] = []
    scope_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []

    for record_id, item in records.items():
        applicable_regions = sorted(record_regions[record_id])
        first_region = TARGET_REGIONS[applicable_regions[0]]
        api_type = item["type"]
        holiday_class = TYPE_CLASS.get(api_type, api_type.lower())
        start = date.fromisoformat(item["startDate"])
        end = date.fromisoformat(item["endDate"])
        clipped_start = max(start, START_DATE)
        clipped_end = min(end, END_DATE)
        duration = (end - start).days + 1

        period_rows.append(
            {
                "record_id": record_id,
                "holiday_class": holiday_class,
                "api_type": api_type,
                "name": localized_text(item.get("name")),
                "country_code": first_region["country_code"],
                "country_name": first_region["country_name"],
                "start_date": item["startDate"],
                "end_date": item["endDate"],
                "duration_days": duration,
                "nationwide": str(bool(item.get("nationwide"))).lower(),
                "regional_scope": item.get("regionalScope", ""),
                "temporal_scope": item.get("temporalScope", ""),
                "target_region_count": len(applicable_regions),
                "tags": "|".join(item.get("tags") or []),
                "comment": localized_text(item.get("comment")),
                "source_provider": item.get("_source_provider", "OpenHolidays API"),
                "source_url": item.get(
                    "_source_url", f"{API_BASE}/{record_endpoints[record_id]}"
                ),
                "verification_status": item.get(
                    "_verification_status", "aggregated_official_calendar"
                ),
                "record_origin": item.get("_record_origin", "api"),
                "retrieved_at": retrieved_at,
            }
        )

        for region_code in applicable_regions:
            region = TARGET_REGIONS[region_code]
            scope_rows.append(
                {
                    "record_id": record_id,
                    "country_code": region["country_code"],
                    "region_code": region_code,
                    "region_name": region["region_name"],
                }
            )

            current = clipped_start
            while current <= clipped_end:
                daily_rows.append(
                    {
                        "date": current.isoformat(),
                        "record_id": record_id,
                        "region_code": region_code,
                        "region_name": region["region_name"],
                        "country_code": region["country_code"],
                        "country_name": region["country_name"],
                        "holiday_class": holiday_class,
                        "api_type": api_type,
                        "name": localized_text(item.get("name")),
                        "start_date": item["startDate"],
                        "end_date": item["endDate"],
                        "day_index": (current - start).days,
                        "days_to_end": (end - current).days,
                        "duration_days": duration,
                        "weekday_iso": current.isoweekday(),
                        "is_weekend": str(current.isoweekday() >= 6).lower(),
                        "is_start_date": str(current == start).lower(),
                        "is_end_date": str(current == end).lower(),
                    }
                )
                current += timedelta(days=1)

    period_rows.sort(
        key=lambda row: (
            row["start_date"],
            row["country_code"],
            row["holiday_class"],
            row["name"],
            row["record_id"],
        )
    )
    scope_rows.sort(key=lambda row: (row["region_code"], row["record_id"]))
    daily_rows.sort(
        key=lambda row: (
            row["date"],
            row["region_code"],
            row["holiday_class"],
            row["record_id"],
        )
    )
    coverage_rows.sort(key=lambda row: (row["region_code"], row["dataset_type"]))
    traffic_window_rows = build_traffic_windows(period_rows, scope_rows)

    write_csv(
        OUTPUT_DIR / "holiday_periods.csv",
        [
            "record_id",
            "holiday_class",
            "api_type",
            "name",
            "country_code",
            "country_name",
            "start_date",
            "end_date",
            "duration_days",
            "nationwide",
            "regional_scope",
            "temporal_scope",
            "target_region_count",
            "tags",
            "comment",
            "source_provider",
            "source_url",
            "verification_status",
            "record_origin",
            "retrieved_at",
        ],
        period_rows,
    )
    write_csv(
        OUTPUT_DIR / "holiday_scopes.csv",
        ["record_id", "country_code", "region_code", "region_name"],
        scope_rows,
    )
    write_csv(
        OUTPUT_DIR / "holiday_dates.csv",
        [
            "date",
            "record_id",
            "region_code",
            "region_name",
            "country_code",
            "country_name",
            "holiday_class",
            "api_type",
            "name",
            "start_date",
            "end_date",
            "day_index",
            "days_to_end",
            "duration_days",
            "weekday_iso",
            "is_weekend",
            "is_start_date",
            "is_end_date",
        ],
        daily_rows,
    )
    write_csv(
        OUTPUT_DIR / "coverage.csv",
        [
            "region_code",
            "region_name",
            "country_code",
            "country_name",
            "dataset_type",
            "oldest_available_start_date",
            "latest_available_start_date",
            "target_first_record_start",
            "target_last_record_start",
            "target_last_record_end",
            "target_record_count",
            "api_record_count",
            "calculated_record_count",
            "coverage_status",
            "has_any_record_overlap_2023",
            "has_any_record_overlap_2024",
            "has_any_record_overlap_2025",
            "has_any_record_overlap_2026",
            "has_any_record_overlap_2027",
            "has_any_record_overlap_2028",
            "has_any_record_overlap_2029",
            "retrieved_at",
        ],
        coverage_rows,
    )
    write_csv(
        OUTPUT_DIR / "traffic_windows_2023_2029.csv",
        [
            "window_id",
            "start_date",
            "end_date",
            "risk_level",
            "expected_direction",
            "a8_direction",
            "a93_direction",
            "regions",
            "holiday_names",
            "record_origins",
            "assessment_status",
        ],
        traffic_window_rows,
    )

    print(
        f"Wrote {len(period_rows)} periods, {len(scope_rows)} region links, "
        f"{len(daily_rows)} daily rows, {len(coverage_rows)} coverage rows and "
        f"{len(traffic_window_rows)} traffic windows."
    )


if __name__ == "__main__":
    main()
