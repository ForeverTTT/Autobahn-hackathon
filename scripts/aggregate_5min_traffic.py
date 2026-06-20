"""Aggregate 12 FG1 Kurz 1-min CSVs into one 5-min merged table."""

import csv
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "分钟交通流量" / "2023-2025_1min_2+0_v"
LOCATIONS = ROOT / "data" / "A8_A93_MQ_locations.csv"
OUTPUT = ROOT / "data" / "分钟交通流量" / "合并表格，5分钟交通流量.csv"

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
    "devices", "datum", "t_start", "wochentag",
    "q_kfz", "q_lkw", "q_pkw", "v_kfz", "n_q_observed", "is_complete",
]

HEADER_CN = [
    "高速路编号", "方向代码", "站点名称", "公里桩", "经度", "纬度",
    "原始设备ID", "原始日期", "5分钟桶起始时刻", "星期(1-7)",
    "5分钟总车流量(辆)", "5分钟货车类流量(辆)", "5分钟小客车类流量(辆)",
    "5分钟加权平均车速(km/h)", "有效q分钟数(0-5)", "是否5分钟完整(1/0)",
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


def bucket_key(datum: str, t_start: str) -> tuple[str, str]:
    dt = datetime.strptime(f"{datum} {t_start}", "%d.%m.%Y %H:%M:%S")
    floored = dt.replace(minute=(dt.minute // 5) * 5, second=0)
    return floored.strftime("%d.%m.%Y"), floored.strftime("%H:%M:%S")


def parse_optional_float(value: str) -> float | None:
    if value in ("", "null"):
        return None
    return float(value)


def fmt_number(value: float) -> str:
    rounded = round(value)
    if abs(value - rounded) < 1e-9:
        return str(int(rounded))
    return f"{value:.1f}"


def aggregate_q(values: list[float | None]) -> str:
    observed = [v for v in values if v is not None]
    if not observed:
        return ""
    return fmt_number(sum(observed) / len(observed) * 5)


def new_bucket(devices: str, wochentag: str) -> dict:
    return {
        "devices": devices,
        "wochentag": wochentag,
        "q_kfz": [],
        "q_lkw": [],
        "q_pkw": [],
        "v_num": 0.0,
        "v_den": 0.0,
    }


def add_minute(bucket: dict, row: dict[str, str]) -> None:
    q_kfz = parse_optional_float(row["q_kfz"])
    q_lkw = parse_optional_float(row["q_lkw"])
    q_pkw = parse_optional_float(row["q_pkw"])
    v_kfz = parse_optional_float(row["v_kfz"])

    bucket["q_kfz"].append(q_kfz)
    bucket["q_lkw"].append(q_lkw)
    bucket["q_pkw"].append(q_pkw)

    if q_kfz is not None and q_kfz > 0 and v_kfz is not None:
        bucket["v_num"] += v_kfz * q_kfz
        bucket["v_den"] += q_kfz


def flush_bucket(
    writer: csv.writer,
    meta: dict,
    loc: dict,
    datum: str,
    t_start: str,
    bucket: dict,
) -> None:
    q_kfz = aggregate_q(bucket["q_kfz"])
    q_lkw = aggregate_q(bucket["q_lkw"])
    q_pkw = aggregate_q(bucket["q_pkw"])
    n_q_observed = sum(v is not None for v in bucket["q_kfz"])
    is_complete = "1" if n_q_observed == 5 else "0"

    if q_kfz == "":
        v_kfz = ""
    elif bucket["v_den"] > 0:
        v_kfz = fmt_number(bucket["v_num"] / bucket["v_den"])
    else:
        v_kfz = ""

    writer.writerow([
        meta["road"],
        meta["direction"],
        meta["site_name"],
        loc["bab_km"],
        loc["longitude"],
        loc["latitude"],
        bucket["devices"],
        datum,
        t_start,
        bucket["wochentag"],
        q_kfz,
        q_lkw,
        q_pkw,
        v_kfz,
        str(n_q_observed),
        is_complete,
    ])


def process_file(
    csv_path: Path,
    meta: dict,
    loc: dict,
    writer: csv.writer,
) -> tuple[int, dict | None, dict | None]:
    file_rows = 0
    first_row = last_row = None
    current_key: tuple[str, str] | None = None
    current_bucket: dict | None = None

    with open(csv_path, newline="", encoding="utf-8") as in_fh:
        for row in csv.DictReader(in_fh, delimiter=";"):
            key = bucket_key(row["datum"], row["t_start"])

            if current_key is None:
                current_key = key
                current_bucket = new_bucket(row["devices"], row["wochentag"])

            elif key != current_key:
                flush_bucket(writer, meta, loc, current_key[0], current_key[1], current_bucket)
                file_rows += 1
                if first_row is None:
                    first_row = (current_key[0], current_key[1])
                last_row = (current_key[0], current_key[1])
                current_key = key
                current_bucket = new_bucket(row["devices"], row["wochentag"])

            add_minute(current_bucket, row)

    if current_key is not None and current_bucket is not None:
        flush_bucket(writer, meta, loc, current_key[0], current_key[1], current_bucket)
        file_rows += 1
        if first_row is None:
            first_row = (current_key[0], current_key[1])
        last_row = (current_key[0], current_key[1])

    return file_rows, first_row, last_row


def main() -> None:
    locations = load_locations()
    csv_files = sorted(DATA_DIR.glob("FG1_Kurz_*.csv"), key=file_sort_key)

    total_rows = 0
    global_first = global_last = None

    with open(OUTPUT, "w", newline="", encoding="utf-8") as out_fh:
        writer = csv.writer(out_fh, delimiter=";")
        writer.writerow(HEADER)
        writer.writerow(HEADER_CN)

        for csv_path in csv_files:
            meta = parse_filename(csv_path.name)
            loc = locations[meta["loc_site"]]
            file_rows, first_row, last_row = process_file(csv_path, meta, loc, writer)
            total_rows += file_rows
            if global_first is None and first_row:
                global_first = first_row
            if last_row:
                global_last = last_row
            print(f"  {csv_path.name}: {file_rows:,} rows")

    size_mb = OUTPUT.stat().st_size / 1024 / 1024
    print(f"Saved: {OUTPUT}")
    print(f"Total rows: {total_rows:,}")
    print(f"Sites: {len(csv_files)}")
    print(f"File size: {size_mb:.1f} MB")
    if global_first and global_last:
        print(
            f"Date range: {global_first[0]} {global_first[1]} -> "
            f"{global_last[0]} {global_last[1]}"
        )


if __name__ == "__main__":
    main()
