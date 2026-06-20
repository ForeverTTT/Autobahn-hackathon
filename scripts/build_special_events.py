"""Build a special-events table for the A8-Ost / A93-Sued corridor.

Hand-curated list of recurring large events around Munich, Salzburg,
Rosenheim and Kufstein that pull significant leisure / tourism traffic
onto the corridor. Source of dates: official websites (verified for
2023-2026; later years are calendar-rule extrapolations and marked as
``status='estimated'``).

Each event row gets expanded to one row per day so that downstream
feature construction is a simple ``date`` join.

Outputs:
  external/special_events_periods.csv  - one row per event instance
  external/special_events_daily.csv    - one row per (date, event)

The "impact_level" column is a coarse traffic-impact prior, NOT a
measured effect:
  high   - city-wide festival pulling 200k+ visitors over the period
           (Oktoberfest, Festspiele, Herbstfest)
  med    - regional festival, weekend draw
  low    - smaller event, baseline local impact

Add new events by editing ``EVENTS`` below and re-running the script.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "external"
OUT_DIR.mkdir(exist_ok=True)


# Each entry: (event_name, city, impact_level, [(year, start, end, status, source), ...])
# Dates are inclusive on both ends. Status: 'confirmed' if published, 'estimated' if extrapolated.
EVENTS = [
    # ---- Munich ---------------------------------------------------------
    ("Oktoberfest", "Munich", "high", [
        (2023, "2023-09-16", "2023-10-03", "confirmed", "oktoberfest.de"),
        (2024, "2024-09-21", "2024-10-06", "confirmed", "oktoberfest.de"),
        (2025, "2025-09-20", "2025-10-05", "confirmed", "oktoberfest.de"),
        (2026, "2026-09-19", "2026-10-04", "confirmed", "oktoberfest.de"),
        (2027, "2027-09-18", "2027-10-03", "estimated", "rule:Sat-before-Oct1 +16d"),
        (2028, "2028-09-16", "2028-10-03", "estimated", "rule:Sat-before-Oct1 +16d"),
        (2029, "2029-09-15", "2029-10-07", "estimated", "rule:Sat-before-Oct1 +16d; possible centenary extension"),
    ]),
    ("Frühlingsfest", "Munich", "med", [
        (2023, "2023-04-21", "2023-05-07", "confirmed", "fruehlingsfest-muenchen.de"),
        (2024, "2024-04-19", "2024-05-05", "confirmed", "fruehlingsfest-muenchen.de"),
        (2025, "2025-04-25", "2025-05-11", "confirmed", "fruehlingsfest-muenchen.de"),
        (2026, "2026-04-24", "2026-05-10", "estimated", "rule:late-April +17d"),
        (2027, "2027-04-23", "2027-05-09", "estimated", "rule:late-April +17d"),
        (2028, "2028-04-21", "2028-05-07", "estimated", "rule:late-April +17d"),
        (2029, "2029-04-27", "2029-05-13", "estimated", "rule:late-April +17d"),
    ]),
    ("Tollwood Sommer", "Munich", "med", [
        (2023, "2023-06-21", "2023-07-23", "confirmed", "tollwood.de"),
        (2024, "2024-06-26", "2024-07-21", "confirmed", "tollwood.de"),
        (2025, "2025-06-25", "2025-07-20", "confirmed", "tollwood.de"),
        (2026, "2026-06-24", "2026-07-19", "estimated", "rule:late-June + ~4w"),
        (2027, "2027-06-23", "2027-07-18", "estimated", "rule:late-June + ~4w"),
        (2028, "2028-06-21", "2028-07-16", "estimated", "rule:late-June + ~4w"),
        (2029, "2029-06-20", "2029-07-15", "estimated", "rule:late-June + ~4w"),
    ]),
    ("Tollwood Winter & Christkindlmarkt", "Munich", "med", [
        # Spans Tollwood Winter (late Nov - Dec 31) which overlaps
        # the Munich Christkindlmarkt. Bundled because the traffic
        # signal is the same: weekend leisure inflow into city center.
        (2023, "2023-11-27", "2023-12-31", "confirmed", "tollwood.de"),
        (2024, "2024-11-25", "2024-12-31", "confirmed", "tollwood.de"),
        (2025, "2025-11-24", "2025-12-31", "confirmed", "tollwood.de"),
        (2026, "2026-11-23", "2026-12-31", "estimated", "rule:Mon-of-1st-Advent-week"),
        (2027, "2027-11-22", "2027-12-31", "estimated", "rule:Mon-of-1st-Advent-week"),
        (2028, "2028-11-20", "2028-12-31", "estimated", "rule:Mon-of-1st-Advent-week"),
        (2029, "2029-11-19", "2029-12-31", "estimated", "rule:Mon-of-1st-Advent-week"),
    ]),

    # ---- Salzburg -------------------------------------------------------
    ("Salzburger Festspiele", "Salzburg", "high", [
        # The Festspiele runs ~6 weeks each summer; this is the single
        # most important event for A8-Ost inbound traffic to Salzburg.
        (2023, "2023-07-18", "2023-08-31", "confirmed", "salzburgerfestspiele.at"),
        (2024, "2024-07-19", "2024-08-31", "confirmed", "salzburgerfestspiele.at"),
        (2025, "2025-07-18", "2025-08-30", "confirmed", "salzburgerfestspiele.at"),
        (2026, "2026-07-17", "2026-08-30", "estimated", "rule:Fri-before-Jul21 +~44d"),
        (2027, "2027-07-16", "2027-08-29", "estimated", "rule:Fri-before-Jul21 +~44d"),
        (2028, "2028-07-21", "2028-09-03", "estimated", "rule:Fri-before-Jul21 +~44d"),
        (2029, "2029-07-20", "2029-09-02", "estimated", "rule:Fri-before-Jul21 +~44d"),
    ]),
    ("Mozartwoche", "Salzburg", "low", [
        (2023, "2023-01-26", "2023-02-05", "confirmed", "mozarteum.at"),
        (2024, "2024-01-25", "2024-02-04", "confirmed", "mozarteum.at"),
        (2025, "2025-01-23", "2025-02-02", "confirmed", "mozarteum.at"),
        (2026, "2026-01-22", "2026-02-01", "estimated", "rule:around-Mozart-Jan27"),
        (2027, "2027-01-21", "2027-01-31", "estimated", "rule:around-Mozart-Jan27"),
        (2028, "2028-01-20", "2028-01-30", "estimated", "rule:around-Mozart-Jan27"),
        (2029, "2029-01-25", "2029-02-04", "estimated", "rule:around-Mozart-Jan27"),
    ]),
    ("Salzburger Christkindlmarkt", "Salzburg", "med", [
        (2023, "2023-11-23", "2023-12-26", "confirmed", "christkindlmarkt.co.at"),
        (2024, "2024-11-21", "2024-12-26", "confirmed", "christkindlmarkt.co.at"),
        (2025, "2025-11-20", "2025-12-26", "confirmed", "christkindlmarkt.co.at"),
        (2026, "2026-11-19", "2026-12-26", "estimated", "rule:Thu-before-Advent"),
        (2027, "2027-11-18", "2027-12-26", "estimated", "rule:Thu-before-Advent"),
        (2028, "2028-11-23", "2028-12-26", "estimated", "rule:Thu-before-Advent"),
        (2029, "2029-11-22", "2029-12-26", "estimated", "rule:Thu-before-Advent"),
    ]),

    # ---- Rosenheim ------------------------------------------------------
    ("Rosenheimer Herbstfest", "Rosenheim", "high", [
        # Largest folk festival in Oberbayern after the Oktoberfest;
        # heavy regional weekend inflow over both A8 and A93.
        (2023, "2023-09-02", "2023-09-17", "confirmed", "rosenheimer-herbstfest.de"),
        (2024, "2024-08-31", "2024-09-15", "confirmed", "rosenheimer-herbstfest.de"),
        (2025, "2025-08-30", "2025-09-14", "confirmed", "rosenheimer-herbstfest.de"),
        (2026, "2026-08-29", "2026-09-13", "estimated", "rule:Sat-of-last-Aug-week +15d"),
        (2027, "2027-08-28", "2027-09-12", "estimated", "rule:Sat-of-last-Aug-week +15d"),
        (2028, "2028-09-02", "2028-09-17", "estimated", "rule:Sat-of-last-Aug-week +15d"),
        (2029, "2029-09-01", "2029-09-16", "estimated", "rule:Sat-of-last-Aug-week +15d"),
    ]),
    ("Rosenheimer Sommerfestival", "Rosenheim", "low", [
        (2023, "2023-07-21", "2023-08-13", "confirmed", "rosenheimer-sommerfestival.de"),
        (2024, "2024-07-19", "2024-08-11", "confirmed", "rosenheimer-sommerfestival.de"),
        (2025, "2025-07-18", "2025-08-10", "confirmed", "rosenheimer-sommerfestival.de"),
        (2026, "2026-07-17", "2026-08-09", "estimated", "rule:Fri-of-3rd-Jul-week +24d"),
        (2027, "2027-07-16", "2027-08-08", "estimated", "rule:Fri-of-3rd-Jul-week +24d"),
        (2028, "2028-07-21", "2028-08-13", "estimated", "rule:Fri-of-3rd-Jul-week +24d"),
        (2029, "2029-07-20", "2029-08-12", "estimated", "rule:Fri-of-3rd-Jul-week +24d"),
    ]),

    # ---- Kufstein (A93 south end) --------------------------------------
    ("Kufsteiner Operettensommer", "Kufstein", "low", [
        (2023, "2023-07-06", "2023-08-12", "confirmed", "operettensommer.com"),
        (2024, "2024-07-04", "2024-08-10", "confirmed", "operettensommer.com"),
        (2025, "2025-07-10", "2025-08-09", "confirmed", "operettensommer.com"),
        (2026, "2026-07-09", "2026-08-08", "estimated", "rule:1st-Thu-Jul +~5w"),
        (2027, "2027-07-08", "2027-08-07", "estimated", "rule:1st-Thu-Jul +~5w"),
        (2028, "2028-07-06", "2028-08-05", "estimated", "rule:1st-Thu-Jul +~5w"),
        (2029, "2029-07-05", "2029-08-04", "estimated", "rule:1st-Thu-Jul +~5w"),
    ]),
]


# Which corridors does each city primarily affect.
CITY_CORRIDOR = {
    "Munich":    {"a8_ost": True,  "a93_sued": False, "node": "AK_München"},
    "Salzburg":  {"a8_ost": True,  "a93_sued": False, "node": "Salzburg_border"},
    "Rosenheim": {"a8_ost": True,  "a93_sued": True,  "node": "AD_Rosenheim"},
    "Kufstein":  {"a8_ost": False, "a93_sued": True,  "node": "Kufstein_border"},
}


def expand() -> tuple[pd.DataFrame, pd.DataFrame]:
    periods, daily = [], []
    for event_name, city, impact, instances in EVENTS:
        corridor = CITY_CORRIDOR[city]
        for year, start, end, status, source in instances:
            s = pd.Timestamp(start)
            e = pd.Timestamp(end)
            periods.append({
                "event_name": event_name,
                "city": city,
                "year": year,
                "start_date": s.date(),
                "end_date": e.date(),
                "duration_days": (e - s).days + 1,
                "impact_level": impact,
                "affects_a8_ost": corridor["a8_ost"],
                "affects_a93_sued": corridor["a93_sued"],
                "nearest_corridor_node": corridor["node"],
                "status": status,
                "source": source,
            })
            # daily expansion
            for d in pd.date_range(s, e, freq="D"):
                day_index = (d - s).days
                duration = (e - s).days
                edge = (
                    "start" if day_index == 0
                    else "end" if day_index == duration
                    else "mid"
                )
                daily.append({
                    "date": d.date(),
                    "event_name": event_name,
                    "city": city,
                    "impact_level": impact,
                    "affects_a8_ost": corridor["a8_ost"],
                    "affects_a93_sued": corridor["a93_sued"],
                    "day_position": edge,
                    "is_weekend": d.weekday() >= 5,
                    "status": status,
                })

    periods_df = pd.DataFrame(periods).sort_values(["start_date", "event_name"]).reset_index(drop=True)
    daily_df = pd.DataFrame(daily).sort_values(["date", "city", "event_name"]).reset_index(drop=True)
    return periods_df, daily_df


def main() -> None:
    periods_df, daily_df = expand()
    p_path = OUT_DIR / "special_events_periods.csv"
    d_path = OUT_DIR / "special_events_daily.csv"
    periods_df.to_csv(p_path, index=False)
    daily_df.to_csv(d_path, index=False)
    print(f"Wrote {p_path}  ({len(periods_df)} event instances)")
    print(f"Wrote {d_path}  ({len(daily_df):,} day-rows)")

    # Sanity: top-3 highest-traffic days of 2026 by impact density
    df26 = daily_df[pd.to_datetime(daily_df["date"]).dt.year == 2026].copy()
    df26["impact_score"] = df26["impact_level"].map({"high": 3, "med": 2, "low": 1})
    top = (df26.groupby("date")["impact_score"].sum().sort_values(ascending=False).head(8))
    print("\n2026 days with highest event-overlap impact score:")
    for d, score in top.items():
        events = ", ".join(df26.loc[df26["date"] == d, "event_name"].unique())
        print(f"  {d}  score={int(score)}  events: {events}")


if __name__ == "__main__":
    main()
