"""Merge 12 DAUZ hourly traffic CSVs into one long-format table."""

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "小时交通流量" / "DAUZ_2+0_1h_2023-2026"
LOCATIONS = ROOT / "data" / "A8_A93_MQ_locations.csv"
OUTPUT = ROOT / "data" / "小时交通流量" / "合并表格，小时交通流量.csv"

LOCATION_SITE_MAP = {
    ("9171", "Mch"): "MQB25_Mch_H",
    ("9171", "Sbg"): "MQQ37_Sbg_H",
    ("9192", "Mch"): "MQQ209_Mch_H",
    ("9192", "Sbg"): "MQQ213_Sbg_H",
    ("9194", "Mch"): "MQQ245_Mch_H",
    ("9194", "Sbg"): "MQQ245_Sbg_H",
    ("9190", "Kff"): "LVE_81389190_33_34",
    ("9190", "Ro"): "LVE_81389190_1_2",
    ("9629", "Kff"): "LVE_82389192_33_34",
    ("9629", "Ro"): "LVE_82389192_1_2",
    ("9191", "Kff"): "LVE_83399191_33_34",
    ("9191", "Ro"): "LVE_83399191_1_2",
}

FILENAME_RE = re.compile(
    r"^FG1_Lang_(?P<dauz>\d+)_(?P<body>.+?),"
    r"(?P<de>DE[\d,]+)_agg1h_"
)

HEADER = [
    "road", "direction", "site_name", "bab_km", "longitude", "latitude",
    "devices", "datum", "t_start", "wochentag", "tagestyp", "kfz_h", "sv_h",
]

HEADER_CN = [
    "高速路编号", "方向代码", "站点名称", "公里桩", "经度", "纬度",
    "原始设备ID", "原始日期", "原始时刻", "星期(1-7)",
    "日类型(w=工作日/s=周日及公共假日/u=学校假期等)",
    "小时总车流量(辆)", "小时重型车流量(辆)",
]


def load_locations() -> dict[str, dict]:
    sites: dict[str, dict] = {}
    with open(LOCATIONS, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            site = row["site"]
            if site in sites:
                continue
            sites[site] = {
                "bab_km": row["BAB-Km"].replace(",", "."),
                "longitude": row["Longitude_WGS84"],
                "latitude": row["Latitude_WGS84"],
            }
    return sites


def null_to_empty(value: str) -> str:
    return "" if value == "null" else value


def parse_filename(fname: str) -> dict:
    m = FILENAME_RE.match(fname)
    if not m:
        raise ValueError(f"Cannot parse filename: {fname}")

    dauz_id = m.group("dauz")
    body = m.group("body")

    if body.endswith("_Mch_H"):
        direction = "Mch"
    elif body.endswith("_Sbg_H"):
        direction = "Sbg"
    elif body.endswith("_Kff"):
        direction = "Kff"
    elif body.endswith("_Ro"):
        direction = "Ro"
    else:
        raise ValueError(f"Unknown direction in: {body}")

    road = "A8" if direction in ("Mch", "Sbg") else "A93"
    loc_site = LOCATION_SITE_MAP[(dauz_id, direction)]

    return {
        "road": road,
        "direction": direction,
        "site_name": body,
        "loc_site": loc_site,
    }


def file_sort_key(path: Path) -> tuple[str, str]:
    meta = parse_filename(path.name)
    return meta["road"], meta["direction"], meta["site_name"]


def main() -> None:
    locations = load_locations()
    rows_out: list[list] = []

    for csv_path in sorted(DATA_DIR.glob("FG1_Lang_*.csv"), key=file_sort_key):
        meta = parse_filename(csv_path.name)
        loc = locations[meta["loc_site"]]

        with open(csv_path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter=";"):
                rows_out.append([
                    meta["road"],
                    meta["direction"],
                    meta["site_name"],
                    loc["bab_km"],
                    loc["longitude"],
                    loc["latitude"],
                    row["devices"],
                    row["datum"],
                    row["t_start"],
                    row["wochentag"],
                    row["tagestyp"],
                    null_to_empty(row["kfz_h"]),
                    null_to_empty(row["sv_h"]),
                ])

    rows_out.sort(key=lambda r: (r[7], r[8], r[0], r[1], r[2]))

    with open(OUTPUT, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(HEADER)
        writer.writerow(HEADER_CN)
        writer.writerows(rows_out)

    print(f"Saved: {OUTPUT}")
    print(f"Rows: {len(rows_out):,}")
    print(f"Sites: {len(set(r[2] for r in rows_out))}")
    print(f"Date range: {rows_out[0][7]} {rows_out[0][8]} -> {rows_out[-1][7]} {rows_out[-1][8]}")


if __name__ == "__main__":
    main()
