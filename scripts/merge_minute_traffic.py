"""Merge 12 FG1 Kurz minute traffic CSVs into one long-format table."""

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "分钟交通流量" / "2023-2025_1min_2+0_v"
LOCATIONS = ROOT / "data" / "A8_A93_MQ_locations.csv"
OUTPUT = ROOT / "data" / "分钟交通流量" / "合并表格，分钟交通流量.csv"

SITE_NAME_TO_DAUZ = {
    "MQB25_Mch_H": "9171",
    "MQQ37_Sbg_H": "9171",
    "MQQ209_Mch_H": "9192",
    "MQQ213_Sbg_H": "9192",
    "MQQ245_Mch_H": "9194",
    "MQQ245_Sbg_H": "9194",
    "MQDZ_AD Inntal_(S)_Kff": "9190",
    "MQDZ_AD Inntal_(S)_Ro": "9190",
    "MQ_Gletschergarten_Kff": "9629",
    "MQ_Gletschergarten_Ro": "9629",
    "MQDZ_Kiefersfelden_(S)_Kff": "9191",
    "MQDZ_Kiefersfelden_(S)_Ro": "9191",
}

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
    r"^FG1_Kurz_(?P<body>.+?),(?P<de>DE[\d,]+)_agg1min_"
)

HEADER = [
    "road", "direction", "site_name", "bab_km", "longitude", "latitude",
    "devices", "datum", "t_start", "wochentag", "q_kfz", "q_lkw", "q_pkw", "v_kfz",
]

HEADER_CN = [
    "高速路编号", "方向代码", "站点名称", "公里桩", "经度", "纬度",
    "原始设备ID", "原始日期", "原始时刻", "星期(1-7)",
    "分钟总车流量(辆)", "分钟货车类流量(辆)", "分钟小客车类流量(辆)",
    "分钟平均车速(km/h)",
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

    dauz_id = SITE_NAME_TO_DAUZ[body]
    road = "A8" if direction in ("Mch", "Sbg") else "A93"
    loc_site = LOCATION_SITE_MAP[(dauz_id, direction)]

    return {
        "road": road,
        "direction": direction,
        "site_name": body,
        "loc_site": loc_site,
    }


def file_sort_key(path: Path) -> tuple[str, str, str]:
    meta = parse_filename(path.name)
    return meta["road"], meta["direction"], meta["site_name"]


def main() -> None:
    locations = load_locations()
    csv_files = sorted(DATA_DIR.glob("FG1_Kurz_*.csv"), key=file_sort_key)

    total_rows = 0
    first_row = last_row = None

    with open(OUTPUT, "w", newline="", encoding="utf-8") as out_fh:
        writer = csv.writer(out_fh, delimiter=";")
        writer.writerow(HEADER)
        writer.writerow(HEADER_CN)

        for csv_path in csv_files:
            meta = parse_filename(csv_path.name)
            loc = locations[meta["loc_site"]]
            file_rows = 0

            with open(csv_path, newline="", encoding="utf-8") as in_fh:
                for row in csv.DictReader(in_fh, delimiter=";"):
                    out_row = [
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
                        null_to_empty(row["q_kfz"]),
                        null_to_empty(row["q_lkw"]),
                        null_to_empty(row["q_pkw"]),
                        null_to_empty(row["v_kfz"]),
                    ]
                    writer.writerow(out_row)
                    if first_row is None:
                        first_row = out_row
                    last_row = out_row
                    file_rows += 1
                    total_rows += 1

            print(f"  {csv_path.name}: {file_rows:,} rows")

    print(f"Saved: {OUTPUT}")
    print(f"Total rows: {total_rows:,}")
    print(f"Sites: {len(csv_files)}")
    if first_row and last_row:
        print(f"Date range: {first_row[7]} {first_row[8]} -> {last_row[7]} {last_row[8]}")


if __name__ == "__main__":
    main()
