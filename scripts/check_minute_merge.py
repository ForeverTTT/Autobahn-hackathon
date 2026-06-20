"""Stream-check merged minute traffic CSV against 12 source files."""

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "分钟交通流量" / "2023-2025_1min_2+0_v"
MERGED = ROOT / "data" / "分钟交通流量" / "合并表格，分钟交通流量.csv"

EXPECTED_HEADER = [
    "road", "direction", "site_name", "bab_km", "longitude", "latitude",
    "devices", "datum", "t_start", "wochentag", "q_kfz", "q_lkw", "q_pkw", "v_kfz",
]


def count_source_files() -> tuple[int, dict[str, int]]:
    by_file: dict[str, int] = {}
    total = 0
    for path in sorted(DATA_DIR.glob("FG1_Kurz_*.csv")):
        with open(path, encoding="utf-8", newline="") as fh:
            rows = sum(1 for _ in fh) - 1
        by_file[path.name] = rows
        total += rows
    return total, by_file


def check_merged(src_total: int, src_by_file: dict[str, int]) -> int:
    if not MERGED.exists():
        print("MERGED FILE NOT FOUND")
        return 1

    size_mb = MERGED.stat().st_size / 1024 / 1024
    print(f"\n=== MERGED: {MERGED.name} ===")
    print(f"Size: {size_mb:.1f} MB")

    site_counts: Counter[str] = Counter()
    road_counts: Counter[str] = Counter()
    dir_counts: Counter[str] = Counter()
    rows = bad_len = missing_loc = empty_q = empty_v = 0
    date_min = date_max = t_min = t_max = None

    with open(MERGED, encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh, delimiter=";")
        header = next(reader)
        cn = next(reader)

        print(f"Columns ({len(header)}): {header}")
        print(f"Header OK: {header == EXPECTED_HEADER}")

        for row in reader:
            rows += 1
            if len(row) != len(header):
                bad_len += 1
                if bad_len <= 3:
                    print(f"  BAD ROW len={len(row)}: {row[:4]}")
                continue

            if not row[3] or not row[4] or not row[5]:
                missing_loc += 1

            site_counts[row[2]] += 1
            road_counts[row[0]] += 1
            dir_counts[row[1]] += 1
            if row[10] == "":
                empty_q += 1
            if row[13] == "":
                empty_v += 1

            d = datetime.strptime(row[7], "%d.%m.%Y")
            ts = datetime.strptime(f"{row[7]} {row[8]}", "%d.%m.%Y %H:%M:%S")
            date_min = d if date_min is None or d < date_min else date_min
            date_max = d if date_max is None or d > date_max else date_max
            t_min = ts if t_min is None or ts < t_min else t_min
            t_max = ts if t_max is None or ts > t_max else t_max

            if rows % 3_000_000 == 0:
                print(f"  ... processed {rows:,} rows")

    print(f"\nData rows: {rows:,}")
    print(f"Expected:  {src_total:,}")
    print(f"Diff:      {rows - src_total:+,}")
    print(f"Complete:  {'YES' if rows == src_total else 'NO'}")
    print(f"Bad row length: {bad_len:,}")
    print(f"Missing location (bab_km/lon/lat): {missing_loc:,}")
    print(f"Date range: {date_min.date() if date_min else None} -> {date_max.date() if date_max else None}")
    print(f"Time range: {t_min} -> {t_max}")
    print(f"Empty q_kfz: {empty_q:,} ({100 * empty_q / rows:.2f}%)")
    print(f"Empty v_kfz: {empty_v:,} ({100 * empty_v / rows:.2f}%)")
    print(f"Roads: {dict(road_counts)}")
    print(f"Directions: {dict(dir_counts)}")

    print(f"\nSites ({len(site_counts)}):")
    per_site_ok = True
    expected_per_site = next(iter(src_by_file.values())) if src_by_file else 0
    for site, count in sorted(site_counts.items()):
        ok = count == expected_per_site
        if not ok:
            per_site_ok = False
        mark = "OK" if ok else "MISMATCH"
        print(f"  {count:>10,}  {site}  [{mark}]")

    all_sites_match = per_site_ok and len(site_counts) == len(src_by_file)
    print(f"\nAll 12 sites row count match: {'YES' if all_sites_match else 'NO'}")
    print(f"\n=== FINAL: {'PASS - merge is complete' if rows == src_total and bad_len == 0 and missing_loc == 0 else 'FAIL - see issues above'} ===")
    return 0 if rows == src_total and bad_len == 0 else 1


def main() -> None:
    print("=== SOURCE FILES ===")
    src_total, src_by_file = count_source_files()
    print(f"Files: {len(src_by_file)}")
    for name, n in src_by_file.items():
        print(f"  {n:>10,}  {name}")
    print(f"SOURCE TOTAL: {src_total:,}")

    raise SystemExit(check_merged(src_total, src_by_file))


if __name__ == "__main__":
    main()
