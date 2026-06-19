"""Merge 12 FG1 Kurz minute traffic CSVs into one long-format table."""

import csv
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "分钟交通流量" / "2023-2025_1min_2+0_v"
LOCATIONS = ROOT / "data" / "A8_A93_MQ_locations.csv"
OUTPUT = ROOT / "data" / "分钟交通流量" / "合并表格，分钟交通流量.csv"

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

CORRIDOR_MAP = {
    ("A8", "Sbg"): "A8E_out",
    ("A8", "Mch"): "A8E_in",
    ("A93", "Kff"): "A93S_out",
    ("A93", "Ro"): "A93S_in",
}

FILENAME_RE = re.compile(
    r"^FG1_Kurz_(?P<body>.+?),(?P<de>DE[\d,]+)_agg1min_"
)

HEADER = [
    "datetime", "date", "hour", "minute", "dauz_id", "site_key", "site_name",
    "site_type", "road", "direction", "corridor_id", "strecke",
    "de_channels", "bab_km", "longitude", "latitude",
    "wochentag", "q_kfz", "q_lkw", "q_pkw", "v_kfz", "devices_raw",
]

HEADER_CN = [
    "分钟起始时刻", "日期", "小时(0-23)", "分钟(0-59)", "永久计数站编号", "站点唯一键",
    "站点名称", "站点类型(MQ/MQDZ)", "道路(A8/A93)", "行驶方向", "建模走廊ID", "所属路段",
    "检测器通道", "公里桩", "经度", "纬度", "星期(1-7)",
    "分钟总车流量(辆)", "分钟货车类流量(辆)", "分钟小客车类流量(辆)",
    "分钟平均车速(km/h)", "原始设备ID",
]


def load_locations() -> dict[str, dict]:
    sites: dict[str, dict] = {}
    with open(LOCATIONS, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            site = row["site"]
            if site in sites:
                continue
            sites[site] = {
                "strecke": row["Strecke"],
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
    de_channels = m.group("de")
    site_type = "MQDZ" if body.startswith("MQDZ") else "MQ"

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

    site_name = body
    dauz_id = SITE_NAME_TO_DAUZ[site_name]
    road = "A8" if direction in ("Mch", "Sbg") else "A93"
    corridor_id = CORRIDOR_MAP[(road, direction)]
    site_key = f"{dauz_id}_{direction}"
    loc_site = LOCATION_SITE_MAP[(dauz_id, direction)]

    return {
        "dauz_id": dauz_id,
        "site_key": site_key,
        "site_name": site_name,
        "site_type": site_type,
        "road": road,
        "direction": direction,
        "corridor_id": corridor_id,
        "de_channels": de_channels,
        "loc_site": loc_site,
    }


def parse_datetime(datum: str, t_start: str) -> tuple[str, str, int, int]:
    dt = datetime.strptime(f"{datum} {t_start}", "%d.%m.%Y %H:%M:%S")
    return (
        dt.strftime("%Y-%m-%d %H:%M"),
        dt.strftime("%Y-%m-%d"),
        dt.hour,
        dt.minute,
    )


def file_sort_key(path: Path) -> tuple[str, str]:
    meta = parse_filename(path.name)
    return meta["dauz_id"], meta["direction"]


def main() -> None:
    locations = load_locations()
    csv_files = sorted(DATA_DIR.glob("FG1_Kurz_*.csv"), key=file_sort_key)

    total_rows = 0
    first_dt = last_dt = ""

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
                    dt_str, date_str, hour, minute = parse_datetime(
                        row["datum"], row["t_start"]
                    )
                    if not first_dt:
                        first_dt = dt_str
                    last_dt = dt_str

                    writer.writerow([
                        dt_str, date_str, hour, minute,
                        meta["dauz_id"], meta["site_key"], meta["site_name"],
                        meta["site_type"], meta["road"], meta["direction"],
                        meta["corridor_id"], loc["strecke"], meta["de_channels"],
                        loc["bab_km"], loc["longitude"], loc["latitude"],
                        row["wochentag"],
                        null_to_empty(row["q_kfz"]),
                        null_to_empty(row["q_lkw"]),
                        null_to_empty(row["q_pkw"]),
                        null_to_empty(row["v_kfz"]),
                        row["devices"],
                    ])
                    file_rows += 1
                    total_rows += 1

            print(f"  {csv_path.name}: {file_rows:,} rows")

    print(f"Saved: {OUTPUT}")
    print(f"Total rows: {total_rows:,}")
    print(f"Sites: {len(csv_files)}")
    print(f"Date range: {first_dt} -> {last_dt}")


if __name__ == "__main__":
    main()
