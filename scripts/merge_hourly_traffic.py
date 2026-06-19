"""Merge 12 DAUZ hourly traffic CSVs into one long-format table (Scheme A)."""

import csv
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "小时交通流量" / "DAUZ_2+0_1h_2023-2026"
LOCATIONS = ROOT / "data" / "A8_A93_MQ_locations.csv"
OUTPUT = ROOT / "data" / "小时交通流量" / "合并表格，小时交通流量.csv"

# dauz_id + direction -> locations site name
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

CORRIDOR_MAP = {
    ("A8", "Sbg"): "A8E_out",
    ("A8", "Mch"): "A8E_in",
    ("A93", "Kff"): "A93S_out",
    ("A93", "Ro"): "A93S_in",
}

FILENAME_RE = re.compile(
    r"^FG1_Lang_(?P<dauz>\d+)_(?P<body>.+?),"
    r"(?P<de>DE[\d,]+)_agg1h_"
)


def load_locations() -> dict[str, dict]:
    sites: dict[str, dict] = {}
    with open(LOCATIONS, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            site = row["site"]
            if site in sites:
                continue
            km = row["BAB-Km"].replace(",", ".")
            sites[site] = {
                "strecke": row["Strecke"],
                "bab_km": km,
                "longitude": row["Longitude_WGS84"],
                "latitude": row["Latitude_WGS84"],
            }
    return sites


def parse_filename(fname: str) -> dict:
    m = FILENAME_RE.match(fname)
    if not m:
        raise ValueError(f"Cannot parse filename: {fname}")

    dauz_id = m.group("dauz")
    body = m.group("body")
    de_channels = m.group("de")

    site_type = "MQDZ" if body.startswith("MQDZ") else "MQ"

    if body.endswith("_Mch_H"):
        direction = "Mch"
        site_name = body
    elif body.endswith("_Sbg_H"):
        direction = "Sbg"
        site_name = body
    elif body.endswith("_Kff"):
        direction = "Kff"
        site_name = body
    elif body.endswith("_Ro"):
        direction = "Ro"
        site_name = body
    else:
        raise ValueError(f"Unknown direction in: {body}")

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


def parse_datetime(datum: str, t_start: str) -> tuple[str, str, int]:
    dt = datetime.strptime(f"{datum} {t_start}", "%d.%m.%Y %H:%M:%S")
    return dt.strftime("%Y-%m-%d %H:%M"), dt.strftime("%Y-%m-%d"), dt.hour


def main() -> None:
    locations = load_locations()
    header = [
        "datetime", "date", "hour", "dauz_id", "site_key", "site_name",
        "site_type", "road", "direction", "corridor_id", "strecke",
        "de_channels", "bab_km", "longitude", "latitude",
        "wochentag", "tagestyp", "kfz_h", "sv_h", "devices_raw",
    ]

    rows_out: list[list] = []
    for csv_path in sorted(DATA_DIR.glob("FG1_Lang_*.csv")):
        meta = parse_filename(csv_path.name)
        loc = locations[meta["loc_site"]]

        with open(csv_path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter=";"):
                dt_str, date_str, hour = parse_datetime(row["datum"], row["t_start"])
                kfz = row["kfz_h"] if row["kfz_h"] != "null" else ""
                sv = row["sv_h"] if row["sv_h"] != "null" else ""

                rows_out.append([
                    dt_str, date_str, hour,
                    meta["dauz_id"], meta["site_key"], meta["site_name"],
                    meta["site_type"], meta["road"], meta["direction"],
                    meta["corridor_id"], loc["strecke"], meta["de_channels"],
                    loc["bab_km"], loc["longitude"], loc["latitude"],
                    row["wochentag"], row["tagestyp"], kfz, sv, row["devices"],
                ])

    rows_out.sort(key=lambda r: (r[0], r[3], r[8]))

    with open(OUTPUT, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(header)
        writer.writerows(rows_out)

    print(f"Saved: {OUTPUT}")
    print(f"Rows: {len(rows_out)}")
    print(f"Sites: {len(set(r[4] for r in rows_out))}")
    print(f"Date range: {rows_out[0][0]} -> {rows_out[-1][0]}")


if __name__ == "__main__":
    main()
