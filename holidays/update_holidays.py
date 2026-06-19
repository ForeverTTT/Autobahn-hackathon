#!/usr/bin/env python3
"""Download and normalize public/school holidays relevant to A8 East and A93 South."""

from __future__ import annotations

import csv
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://openholidaysapi.org"
START_DATE = date(2026, 1, 1)
END_DATE = date(2029, 12, 31)
OUTPUT_DIR = Path(__file__).resolve().parent

COUNTRIES = {
    "DE": ("Germany", 1, "core"),
    "AT": ("Austria", 1, "core"),
    "IT": ("Italy", 2, "high"),
    "SI": ("Slovenia", 2, "high"),
    "HR": ("Croatia", 2, "high"),
    "NL": ("Netherlands", 3, "medium"),
    "BE": ("Belgium", 3, "medium"),
    "CZ": ("Czechia", 3, "medium"),
    "PL": ("Poland", 3, "medium"),
    "HU": ("Hungary", 3, "medium"),
    "SK": ("Slovakia", 3, "medium"),
    "CH": ("Switzerland", 3, "medium"),
    "RS": ("Serbia", 4, "secondary"),
    "RO": ("Romania", 4, "secondary"),
    "BG": ("Bulgaria", 4, "secondary"),
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
    request = Request(url, headers={"User-Agent": "Autobahn-Hackathon-Holiday-Importer/1.0"})
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            with urlopen(request, timeout=45) as response:
                return json.load(response)
        except Exception as exc:  # network retries are intentionally broad
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


def flatten_regional_items(items: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}

    def visit(item: dict[str, Any]) -> None:
        result[item["code"]] = localized_text(item.get("name")) or item.get("shortName", "")
        for child in item.get("children") or []:
            visit(child)

    for item in items:
        visit(item)
    return result


def download_holidays(endpoint: str, country_code: str) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for year in range(START_DATE.year, END_DATE.year + 1):
        data = fetch_json(
            f"/{endpoint}",
            {
                "countryIsoCode": country_code,
                "validFrom": f"{year}-01-01",
                "validTo": f"{year}-12-31",
                "languageIsoCode": "EN",
            },
        )
        for item in data:
            records[item["id"]] = item
    return list(records.values())


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    period_rows: list[dict[str, Any]] = []
    scope_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []

    for country_code, (country_name, priority, priority_label) in COUNTRIES.items():
        subdivisions = flatten_regional_items(
            fetch_json(
                "/Subdivisions",
                {"countryIsoCode": country_code, "languageIsoCode": "EN"},
            )
        )
        groups = flatten_regional_items(
            fetch_json(
                "/Groups",
                {"countryIsoCode": country_code, "languageIsoCode": "EN"},
            )
        )

        endpoints = (
            ("PublicHolidays", "public"),
            ("SchoolHolidays", "school"),
        )
        for endpoint, dataset_type in endpoints:
            holidays = download_holidays(endpoint, country_code)
            statistics = fetch_json(
                f"/Statistics/{endpoint}",
                {"countryIsoCode": country_code},
            )

            target_starts = [item["startDate"] for item in holidays]
            target_ends = [item["endDate"] for item in holidays]
            years_with_records = {
                year: any(
                    date.fromisoformat(item["startDate"]).year <= year
                    <= date.fromisoformat(item["endDate"]).year
                    for item in holidays
                )
                for year in range(START_DATE.year, END_DATE.year + 1)
            }
            coverage_rows.append(
                {
                    "country_code": country_code,
                    "country_name": country_name,
                    "dataset_type": dataset_type,
                    "oldest_available_start_date": statistics.get("oldestStartDate", ""),
                    "latest_available_start_date": statistics.get("youngestStartDate", ""),
                    "target_first_record_start": min(target_starts) if target_starts else "",
                    "target_last_record_start": max(target_starts) if target_starts else "",
                    "target_last_record_end": max(target_ends) if target_ends else "",
                    "target_record_count": len(holidays),
                    **{
                        f"has_any_record_overlap_{year}": str(years_with_records[year]).lower()
                        for year in range(START_DATE.year, END_DATE.year + 1)
                    },
                    "retrieved_at": retrieved_at,
                }
            )

            for item in holidays:
                api_type = item["type"]
                holiday_class = TYPE_CLASS.get(api_type, api_type.lower())
                start = date.fromisoformat(item["startDate"])
                end = date.fromisoformat(item["endDate"])
                clipped_start = max(start, START_DATE)
                clipped_end = min(end, END_DATE)
                duration = (end - start).days + 1
                subdivision_refs = item.get("subdivisions") or []
                group_refs = item.get("groups") or []

                period_rows.append(
                    {
                        "record_id": item["id"],
                        "holiday_class": holiday_class,
                        "api_type": api_type,
                        "name": localized_text(item.get("name")),
                        "country_code": country_code,
                        "country_name": country_name,
                        "traffic_priority": priority,
                        "traffic_priority_label": priority_label,
                        "start_date": item["startDate"],
                        "end_date": item["endDate"],
                        "duration_days": duration,
                        "nationwide": str(bool(item.get("nationwide"))).lower(),
                        "regional_scope": item.get("regionalScope", ""),
                        "temporal_scope": item.get("temporalScope", ""),
                        "subdivision_count": len(subdivision_refs),
                        "group_count": len(group_refs),
                        "tags": "|".join(item.get("tags") or []),
                        "comment": localized_text(item.get("comment")),
                        "source_provider": "OpenHolidays API",
                        "source_url": f"{API_BASE}/{endpoint}",
                        "verification_status": "aggregated_official_calendar",
                        "retrieved_at": retrieved_at,
                    }
                )

                scopes: set[tuple[str, str, str]] = set()
                if item.get("nationwide"):
                    scopes.add(("national", country_code, country_name))
                for ref in subdivision_refs:
                    code = ref["code"]
                    scopes.add(("subdivision", code, subdivisions.get(code, ref.get("shortName", ""))))
                for ref in group_refs:
                    code = ref["code"]
                    scopes.add(("group", code, groups.get(code, ref.get("shortName", ""))))
                if not scopes:
                    scopes.add(("unspecified", country_code, country_name))

                for scope_kind, scope_code, scope_name in sorted(scopes):
                    scope_rows.append(
                        {
                            "record_id": item["id"],
                            "country_code": country_code,
                            "scope_kind": scope_kind,
                            "scope_code": scope_code,
                            "scope_name": scope_name,
                        }
                    )

                current = clipped_start
                while current <= clipped_end:
                    day_index = (current - start).days
                    daily_rows.append(
                        {
                            "date": current.isoformat(),
                            "record_id": item["id"],
                            "holiday_class": holiday_class,
                            "api_type": api_type,
                            "name": localized_text(item.get("name")),
                            "country_code": country_code,
                            "country_name": country_name,
                            "traffic_priority": priority,
                            "start_date": item["startDate"],
                            "end_date": item["endDate"],
                            "day_index": day_index,
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
    scope_rows.sort(
        key=lambda row: (
            row["record_id"],
            row["scope_kind"],
            row["scope_code"],
        )
    )
    daily_rows.sort(
        key=lambda row: (
            row["date"],
            row["country_code"],
            row["holiday_class"],
            row["record_id"],
        )
    )
    coverage_rows.sort(key=lambda row: (row["country_code"], row["dataset_type"]))

    write_csv(
        OUTPUT_DIR / "holiday_periods.csv",
        [
            "record_id",
            "holiday_class",
            "api_type",
            "name",
            "country_code",
            "country_name",
            "traffic_priority",
            "traffic_priority_label",
            "start_date",
            "end_date",
            "duration_days",
            "nationwide",
            "regional_scope",
            "temporal_scope",
            "subdivision_count",
            "group_count",
            "tags",
            "comment",
            "source_provider",
            "source_url",
            "verification_status",
            "retrieved_at",
        ],
        period_rows,
    )
    write_csv(
        OUTPUT_DIR / "holiday_scopes.csv",
        ["record_id", "country_code", "scope_kind", "scope_code", "scope_name"],
        scope_rows,
    )
    write_csv(
        OUTPUT_DIR / "holiday_dates.csv",
        [
            "date",
            "record_id",
            "holiday_class",
            "api_type",
            "name",
            "country_code",
            "country_name",
            "traffic_priority",
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
            "country_code",
            "country_name",
            "dataset_type",
            "oldest_available_start_date",
            "latest_available_start_date",
            "target_first_record_start",
            "target_last_record_start",
            "target_last_record_end",
            "target_record_count",
            "has_any_record_overlap_2026",
            "has_any_record_overlap_2027",
            "has_any_record_overlap_2028",
            "has_any_record_overlap_2029",
            "retrieved_at",
        ],
        coverage_rows,
    )

    print(
        f"Wrote {len(period_rows)} periods, {len(scope_rows)} scopes, "
        f"{len(daily_rows)} daily rows and {len(coverage_rows)} coverage rows."
    )


if __name__ == "__main__":
    main()
