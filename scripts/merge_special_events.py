"""Build daily wide special-event feature table."""

import csv
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_DIR = ROOT / "external"
DAILY_CSV = EXTERNAL_DIR / "special_events_daily.csv"
PERIODS_CSV = EXTERNAL_DIR / "special_events_periods.csv"
OUTPUT = EXTERNAL_DIR / "合并表格，special_events日级.csv"

DATE_START = date(2023, 1, 1)
DATE_END = date(2029, 12, 31)

IMPACT_SCORE = {"low": 1, "med": 2, "high": 3}
IMPACT_BY_SCORE = {v: k for k, v in IMPACT_SCORE.items()}
CITIES = ("Munich", "Salzburg", "Rosenheim", "Kufstein")

HEADER = [
    "date",
    "weekday_iso",
    "is_weekend",
    "has_special_event",
    "active_event_count",
    "max_impact_level",
    "impact_score",
    "low_event_count",
    "med_event_count",
    "high_event_count",
    "affects_a8_ost",
    "affects_a93_sued",
    "a8_event_count",
    "a93_event_count",
    "has_munich_event",
    "has_salzburg_event",
    "has_rosenheim_event",
    "has_kufstein_event",
    "munich_event_count",
    "salzburg_event_count",
    "rosenheim_event_count",
    "kufstein_event_count",
    "has_event_start",
    "has_event_end",
    "start_event_names",
    "end_event_names",
    "active_event_names",
    "active_event_cities",
    "nearest_corridor_nodes",
    "event_statuses",
    "has_confirmed_event",
    "has_estimated_event",
    "event_sources",
]

HEADER_CN = [
    "日期",
    "星期(1=周一..7=周日)",
    "是否周末",
    "是否有特殊活动",
    "当天活动数量",
    "最高影响等级",
    "影响等级数值(无=0/low=1/med=2/high=3)",
    "low活动数量",
    "med活动数量",
    "high活动数量",
    "是否影响A8东段",
    "是否影响A93南段",
    "影响A8东段活动数量",
    "影响A93南段活动数量",
    "是否有慕尼黑活动",
    "是否有萨尔茨堡活动",
    "是否有罗森海姆活动",
    "是否有库夫施泰因活动",
    "慕尼黑活动数量",
    "萨尔茨堡活动数量",
    "罗森海姆活动数量",
    "库夫施泰因活动数量",
    "是否有活动开始",
    "是否有活动结束",
    "当天开始活动名称",
    "当天结束活动名称",
    "当天所有活动名称",
    "当天涉及城市",
    "最近走廊节点",
    "活动状态集合",
    "是否含confirmed活动",
    "是否含estimated活动",
    "活动来源集合",
]


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def as_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def join_values(values) -> str:
    return "|".join(sorted(v for v in values if v))


def load_period_meta() -> dict[tuple[str, str, str], dict[str, str]]:
    meta: dict[tuple[str, str, str], dict[str, str]] = {}
    with open(PERIODS_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if not row:
                continue
            key = (row["event_name"], row["city"], row["year"])
            meta[key] = {
                "nearest_corridor_node": row["nearest_corridor_node"],
                "source": row["source"],
            }
    return meta


def load_daily_events(period_meta: dict[tuple[str, str, str], dict[str, str]]):
    events_by_date: dict[date, list[dict[str, str]]] = defaultdict(list)
    with open(DAILY_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if not row or not row.get("date"):
                continue
            d = date.fromisoformat(row["date"])
            key = (row["event_name"], row["city"], str(d.year))
            meta = period_meta.get(key, {})
            row["nearest_corridor_node"] = meta.get("nearest_corridor_node", "")
            row["source"] = meta.get("source", "")
            events_by_date[d].append(row)
    return events_by_date


def build_row(d: date, events: list[dict[str, str]]) -> list[str]:
    wd = d.isoweekday()
    is_weekend = wd in (6, 7)
    has_event = bool(events)

    impact_counts = Counter(event["impact_level"] for event in events)
    max_score = max((IMPACT_SCORE.get(event["impact_level"], 0) for event in events), default=0)
    max_impact = IMPACT_BY_SCORE.get(max_score, "")

    a8_events = [event for event in events if as_bool(event["affects_a8_ost"])]
    a93_events = [event for event in events if as_bool(event["affects_a93_sued"])]

    city_counts = Counter(event["city"] for event in events)
    start_events = [event["event_name"] for event in events if event["day_position"] == "start"]
    end_events = [event["event_name"] for event in events if event["day_position"] == "end"]
    statuses = {event["status"] for event in events}

    return [
        d.isoformat(),
        str(wd),
        "1" if is_weekend else "0",
        "1" if has_event else "0",
        str(len(events)),
        max_impact,
        str(max_score),
        str(impact_counts.get("low", 0)),
        str(impact_counts.get("med", 0)),
        str(impact_counts.get("high", 0)),
        "1" if a8_events else "0",
        "1" if a93_events else "0",
        str(len(a8_events)),
        str(len(a93_events)),
        "1" if city_counts["Munich"] else "0",
        "1" if city_counts["Salzburg"] else "0",
        "1" if city_counts["Rosenheim"] else "0",
        "1" if city_counts["Kufstein"] else "0",
        str(city_counts["Munich"]),
        str(city_counts["Salzburg"]),
        str(city_counts["Rosenheim"]),
        str(city_counts["Kufstein"]),
        "1" if start_events else "0",
        "1" if end_events else "0",
        join_values(start_events),
        join_values(end_events),
        join_values({event["event_name"] for event in events}),
        join_values({event["city"] for event in events}),
        join_values({event["nearest_corridor_node"] for event in events}),
        join_values(statuses),
        "1" if "confirmed" in statuses else "0",
        "1" if "estimated" in statuses else "0",
        join_values({event["source"] for event in events}),
    ]


def main() -> None:
    period_meta = load_period_meta()
    events_by_date = load_daily_events(period_meta)

    rows = 0
    event_days = 0
    max_events = 0

    with open(OUTPUT, "w", newline="", encoding="utf-8") as out_fh:
        writer = csv.writer(out_fh, delimiter=";")
        writer.writerow(HEADER)
        writer.writerow(HEADER_CN)

        for d in daterange(DATE_START, DATE_END):
            events = events_by_date.get(d, [])
            writer.writerow(build_row(d, events))
            rows += 1
            if events:
                event_days += 1
            max_events = max(max_events, len(events))

    print(f"Saved: {OUTPUT}")
    print(f"Total days: {rows:,}")
    print(f"Days with special events: {event_days:,}")
    print(f"Max events on one day: {max_events}")


if __name__ == "__main__":
    main()
