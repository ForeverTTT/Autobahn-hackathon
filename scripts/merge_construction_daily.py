"""Build daily construction feature table from cleaned construction sites."""

import csv
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_DIR = ROOT / "external"
SITES_CSV = EXTERNAL_DIR / "construction_sites_clean.csv"
OUTPUT = EXTERNAL_DIR / "合并表格，construction日级.csv"

DATE_START = date(2023, 1, 1)
DATE_END = date(2029, 12, 31)

HEADER = [
    "date",
    "weekday_iso",
    "is_weekend",
    "has_construction",
    "construction_count",
    "has_target_bbox_construction",
    "target_bbox_construction_count",
    "outside_bbox_construction_count",
    "has_a8_construction",
    "has_a93_construction",
    "a8_construction_count",
    "a93_construction_count",
    "has_roadworks",
    "has_short_term_roadworks",
    "roadworks_count",
    "short_term_roadworks_count",
    "has_2_plus_0",
    "two_plus_0_count",
    "max_closed_lanes",
    "sum_closed_lanes",
    "active_roads",
    "active_corridors",
    "active_services",
    "display_types",
    "config_types",
    "construction_ids",
    "construction_titles",
    "has_missing_time_range",
    "missing_time_range_count",
    "source_row_count",
]

HEADER_CN = [
    "日期",
    "星期(1=周一..7=周日)",
    "是否周末",
    "是否有施工",
    "当天施工记录数量",
    "是否有目标区域内施工",
    "目标区域内施工数量",
    "目标区域外施工数量",
    "是否有A8施工",
    "是否有A93施工",
    "A8施工数量",
    "A93施工数量",
    "是否有普通施工ROADWORKS",
    "是否有短期施工SHORT_TERM_ROADWORKS",
    "普通施工数量",
    "短期施工数量",
    "是否有2+0交通组织",
    "2+0施工数量",
    "最大关闭车道数",
    "关闭车道数合计",
    "涉及道路集合",
    "涉及走廊集合",
    "服务类型集合",
    "展示类型集合",
    "交通组织类型集合",
    "施工ID集合",
    "施工标题集合",
    "是否存在无法展开日期的施工记录",
    "无法展开日期的施工记录数量",
    "原始明细行数量",
]


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def parse_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def parse_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def join_values(values) -> str:
    return "|".join(sorted(str(v) for v in values if v))


def empty_bucket() -> dict:
    return {
        "rows": [],
        "ids": set(),
        "roads": set(),
        "corridors": set(),
        "services": set(),
        "display_types": set(),
        "config_types": set(),
        "titles": set(),
    }


def load_sites() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    dated_rows: list[dict[str, str]] = []
    missing_rows: list[dict[str, str]] = []
    with open(SITES_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            start = parse_date(row.get("start_text_parsed", "")) or parse_date(row.get("start_iso", ""))
            end = parse_date(row.get("end_text_parsed", "")) or parse_date(row.get("end_iso", ""))
            if start is None or end is None:
                missing_rows.append(row)
                continue
            if end < DATE_START or start > DATE_END:
                continue
            row["_start_date"] = max(start, DATE_START).isoformat()
            row["_end_date"] = min(end, DATE_END).isoformat()
            dated_rows.append(row)
    return dated_rows, missing_rows


def build_daily_index(rows: list[dict[str, str]]) -> dict[date, dict]:
    by_day: dict[date, dict] = defaultdict(empty_bucket)
    seen: set[tuple[date, str]] = set()

    for row in rows:
        start = date.fromisoformat(row["_start_date"])
        end = date.fromisoformat(row["_end_date"])
        for d in daterange(start, end):
            identifier = row["identifier"]
            key = (d, identifier)
            if key in seen:
                continue
            seen.add(key)

            bucket = by_day[d]
            bucket["rows"].append(row)
            bucket["ids"].add(identifier)
            bucket["roads"].add(row["road"])
            bucket["corridors"].add(row["corridor"])
            bucket["services"].add(row["service"])
            bucket["display_types"].add(row["display_type"])
            bucket["config_types"].add(row["config_type"])
            bucket["titles"].add(row["title"])

    return by_day


def build_row(d: date, bucket: dict | None, missing_count: int) -> list[str]:
    rows = bucket["rows"] if bucket else []
    construction_count = len(rows)
    target_rows = [row for row in rows if parse_bool(row["in_target_bbox"])]
    outside_rows = [row for row in rows if not parse_bool(row["in_target_bbox"])]
    a8_rows = [row for row in rows if row["road"] == "A8"]
    a93_rows = [row for row in rows if row["road"] == "A93"]
    roadworks_rows = [row for row in rows if row["display_type"] == "ROADWORKS"]
    short_rows = [row for row in rows if row["display_type"] == "SHORT_TERM_ROADWORKS"]
    two_plus_rows = [row for row in rows if parse_bool(row["is_2_plus_0"])]
    closed_lanes = [parse_int(row["n_closed_lanes"]) for row in rows]

    return [
        d.isoformat(),
        str(d.isoweekday()),
        "1" if d.isoweekday() in (6, 7) else "0",
        "1" if rows else "0",
        str(construction_count),
        "1" if target_rows else "0",
        str(len(target_rows)),
        str(len(outside_rows)),
        "1" if a8_rows else "0",
        "1" if a93_rows else "0",
        str(len(a8_rows)),
        str(len(a93_rows)),
        "1" if roadworks_rows else "0",
        "1" if short_rows else "0",
        str(len(roadworks_rows)),
        str(len(short_rows)),
        "1" if two_plus_rows else "0",
        str(len(two_plus_rows)),
        str(max(closed_lanes, default=0)),
        str(sum(closed_lanes)),
        join_values(bucket["roads"] if bucket else []),
        join_values(bucket["corridors"] if bucket else []),
        join_values(bucket["services"] if bucket else []),
        join_values(bucket["display_types"] if bucket else []),
        join_values(bucket["config_types"] if bucket else []),
        join_values(bucket["ids"] if bucket else []),
        join_values(bucket["titles"] if bucket else []),
        "1" if missing_count else "0",
        str(missing_count),
        str(construction_count),
    ]


def main() -> None:
    dated_rows, missing_rows = load_sites()
    by_day = build_daily_index(dated_rows)
    missing_count = len(missing_rows)

    rows_written = 0
    construction_days = 0
    target_days = 0

    with open(OUTPUT, "w", newline="", encoding="utf-8") as out_fh:
        writer = csv.writer(out_fh, delimiter=";")
        writer.writerow(HEADER)
        writer.writerow(HEADER_CN)

        for d in daterange(DATE_START, DATE_END):
            bucket = by_day.get(d)
            row = build_row(d, bucket, missing_count)
            writer.writerow(row)
            rows_written += 1
            if row[3] == "1":
                construction_days += 1
            if row[5] == "1":
                target_days += 1

    print(f"Saved: {OUTPUT}")
    print(f"Total days: {rows_written:,}")
    print(f"Construction days: {construction_days:,}")
    print(f"Target-bbox construction days: {target_days:,}")
    print(f"Dated source rows: {len(dated_rows):,}")
    print(f"Rows with missing/unexpanded time range: {missing_count:,}")


if __name__ == "__main__":
    main()
