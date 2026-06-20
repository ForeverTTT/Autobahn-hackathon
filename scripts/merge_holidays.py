"""Build daily wide holiday feature table from holidays/ CSVs."""

import csv
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOLIDAYS_DIR = ROOT / "holidays"
DATES_CSV = HOLIDAYS_DIR / "holiday_dates.csv"
PERIODS_CSV = HOLIDAYS_DIR / "holiday_periods.csv"
WINDOWS_CSV = HOLIDAYS_DIR / "traffic_windows_2023_2029.csv"
OUTPUT = HOLIDAYS_DIR / "合并表格，holiday日级.csv"

DATE_START = date(2023, 1, 1)
DATE_END = date(2029, 12, 31)

REGIONS = ("DE-BY", "AT-SB", "AT-TI")
REGION_SUFFIX = {
    "DE-BY": "DE_BY",
    "AT-SB": "AT_SB",
    "AT-TI": "AT_TI",
}

RISK_RANK = {"medium": 1, "high": 2, "very_high": 3}

HEADER = [
    "date",
    "weekday_iso",
    "is_weekend",
    "is_school_holiday_DE_BY",
    "is_school_holiday_AT_SB",
    "is_school_holiday_AT_TI",
    "is_public_holiday_DE_BY",
    "is_public_holiday_AT_SB",
    "is_public_holiday_AT_TI",
    "school_holiday_count",
    "public_holiday_count",
    "school_names_DE_BY",
    "school_names_AT_SB",
    "school_names_AT_TI",
    "public_names_DE_BY",
    "public_names_AT_SB",
    "public_names_AT_TI",
    "is_holiday_start",
    "is_holiday_end",
    "has_calculated_holiday",
    "in_traffic_window",
    "window_direction",
    "window_risk_level",
    "a8_direction",
    "a93_direction",
]

HEADER_CN = [
    "日期",
    "星期(1=周一..7=周日)",
    "是否周末",
    "拜仁州是否学校假",
    "萨尔茨堡州是否学校假",
    "蒂罗尔州是否学校假",
    "拜仁州是否公共假日",
    "萨尔茨堡州是否公共假日",
    "蒂罗尔州是否公共假日",
    "三州学校假数量",
    "三州公共假日数量",
    "拜仁学校假名称",
    "萨尔茨堡学校假名称",
    "蒂罗尔学校假名称",
    "拜仁公共假日名称",
    "萨尔茨堡公共假日名称",
    "蒂罗尔公共假日名称",
    "是否假期首日",
    "是否假期末日",
    "是否含法律推算假期",
    "是否在交通窗口内",
    "交通窗口方向",
    "交通窗口风险等级",
    "A8预期方向",
    "A93预期方向",
]


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def weekday_iso(d: date) -> int:
    return d.isoweekday()


def load_record_origins() -> dict[str, str]:
    origins: dict[str, str] = {}
    with open(PERIODS_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            origins[row["record_id"]] = row["record_origin"]
    return origins


def load_traffic_windows() -> list[dict]:
    windows: list[dict] = []
    with open(WINDOWS_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            windows.append({
                "start": date.fromisoformat(row["start_date"]),
                "end": date.fromisoformat(row["end_date"]),
                "risk_level": row["risk_level"],
                "expected_direction": row["expected_direction"],
                "a8_direction": row["a8_direction"],
                "a93_direction": row["a93_direction"],
            })
    return windows


def pick_window(windows: list[dict], d: date) -> dict | None:
    matches = [w for w in windows if w["start"] <= d <= w["end"]]
    if not matches:
        return None
    return max(matches, key=lambda w: RISK_RANK.get(w["risk_level"], 0))


def empty_day() -> dict:
    return {
        "school": {r: set() for r in REGIONS},
        "public": {r: set() for r in REGIONS},
        "is_holiday_start": False,
        "is_holiday_end": False,
        "has_calculated_holiday": False,
    }


def load_holiday_facts(origins: dict[str, str]) -> dict[date, dict]:
    facts: dict[date, dict] = {}

    with open(DATES_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["holiday_class"] not in ("school_holiday", "public_holiday"):
                continue

            d = date.fromisoformat(row["date"])
            region = row["region_code"]
            if region not in REGIONS:
                continue

            day = facts.setdefault(d, empty_day())
            name = row["name"]
            if row["holiday_class"] == "school_holiday":
                day["school"][region].add(name)
            else:
                day["public"][region].add(name)

            if row["is_start_date"] == "true":
                day["is_holiday_start"] = True
            if row["is_end_date"] == "true":
                day["is_holiday_end"] = True

            origin = origins.get(row["record_id"], "")
            if origin != "api":
                day["has_calculated_holiday"] = True

    return facts


def join_names(names: set[str]) -> str:
    return "|".join(sorted(names))


def build_row(d: date, facts: dict[date, dict], windows: list[dict]) -> list:
    info = facts.get(d, empty_day())
    wd = weekday_iso(d)
    is_weekend = wd in (6, 7)

    school_flags = {
        r: "1" if info["school"][r] else "0" for r in REGIONS
    }
    public_flags = {
        r: "1" if info["public"][r] else "0" for r in REGIONS
    }
    school_count = sum(1 for r in REGIONS if info["school"][r])
    public_count = sum(1 for r in REGIONS if info["public"][r])

    window = pick_window(windows, d)
    if window:
        in_window = "1"
        window_direction = window["expected_direction"]
        window_risk = window["risk_level"]
        a8_dir = window["a8_direction"]
        a93_dir = window["a93_direction"]
    else:
        in_window = "0"
        window_direction = ""
        window_risk = ""
        a8_dir = ""
        a93_dir = ""

    return [
        d.isoformat(),
        str(wd),
        "1" if is_weekend else "0",
        school_flags["DE-BY"],
        school_flags["AT-SB"],
        school_flags["AT-TI"],
        public_flags["DE-BY"],
        public_flags["AT-SB"],
        public_flags["AT-TI"],
        str(school_count),
        str(public_count),
        join_names(info["school"]["DE-BY"]),
        join_names(info["school"]["AT-SB"]),
        join_names(info["school"]["AT-TI"]),
        join_names(info["public"]["DE-BY"]),
        join_names(info["public"]["AT-SB"]),
        join_names(info["public"]["AT-TI"]),
        "1" if info["is_holiday_start"] else "0",
        "1" if info["is_holiday_end"] else "0",
        "1" if info["has_calculated_holiday"] else "0",
        in_window,
        window_direction,
        window_risk,
        a8_dir,
        a93_dir,
    ]


def main() -> None:
    origins = load_record_origins()
    windows = load_traffic_windows()
    facts = load_holiday_facts(origins)

    rows = 0
    holiday_days = 0
    window_days = 0

    with open(OUTPUT, "w", newline="", encoding="utf-8") as out_fh:
        writer = csv.writer(out_fh, delimiter=";")
        writer.writerow(HEADER)
        writer.writerow(HEADER_CN)

        for d in daterange(DATE_START, DATE_END):
            row = build_row(d, facts, windows)
            writer.writerow(row)
            rows += 1
            if d in facts:
                holiday_days += 1
            if row[20] == "1":
                window_days += 1

    print(f"Saved: {OUTPUT}")
    print(f"Total days: {rows:,}")
    print(f"Days with any holiday: {holiday_days:,}")
    print(f"Days in traffic window: {window_days:,}")


if __name__ == "__main__":
    main()
