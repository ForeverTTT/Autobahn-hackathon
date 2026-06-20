"""Plot the A8-Ost and A93-Sued measurement-station map.

Reads station coordinates from ``data/A8_A93_MQ_locations.csv`` (semicolon
delimited, comma decimals) and renders a single annotated overview PNG to
``analysis_output/station_map.png``.

The figure is intentionally schematic:

* A8-Ost and A93-Sued are drawn as polylines through manually anchored
  waypoints (Munich -> AD Rosenheim -> Bad Reichenhall -> Salzburg /
  AD Inntal -> Kiefersfelden); they are NOT a precise road geometry.
* Cities and key interchanges are shown as labelled dots.
* Each MQ station group is shown once (we deduplicate the per-detector
  rows in the CSV by ``site``), with the BAB km marker.

Usage::

    python scripts/plot_station_map.py
"""
from __future__ import annotations

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCATIONS_CSV = PROJECT_ROOT / "data" / "A8_A93_MQ_locations.csv"
OUT_DIR = PROJECT_ROOT / "analysis_output"
OUT_FILE = OUT_DIR / "station_map.png"


# Schematic waypoints (lat, lon) used to draw the highway skeletons.
# These are NOT survey-accurate; they are anchored at known interchanges so
# the route shape is recognisable on the map.
A8_WAYPOINTS = [
    (48.060, 11.580),  # München (AK München-Süd, approx.)
    (47.936, 11.705),  # MQB25 / MQQ37 (km 20)
    (47.870, 11.900),  # Bad Aibling
    (47.830, 12.130),  # AD Rosenheim (A8 x A93)
    (47.826, 12.565),  # MQQ209 / MQQ213 (km 94, Übersee)
    (47.831, 12.733),  # MQQ245 (km 106)
    (47.820, 12.880),  # Bad Reichenhall
    (47.810, 13.033),  # Salzburg
]

A93_WAYPOINTS = [
    (47.830, 12.130),  # AD Rosenheim (junction with A8)
    (47.794, 12.090),  # AD Inntal area (km ~2)
    (47.710, 12.151),  # MQ Gletschergarten area (km ~12)
    (47.606, 12.195),  # Kiefersfelden (km ~25)
    (47.583, 12.166),  # Kufstein (AT)
]

CITIES = [
    ("München", 48.137, 11.575, (10, 6)),
    ("Rosenheim", 47.857, 12.123, (10, 8)),
    ("Bad Reichenhall", 47.726, 12.880, (8, -16)),
    ("Salzburg (AT)", 47.811, 13.033, (-90, -22)),
    ("Kufstein (AT)", 47.583, 12.166, (-95, -4)),
]

INTERCHANGES = [
    ("AD Rosenheim", 47.830, 12.130),
]  # AD Inntal is represented by the colocated MQ station label.


# Friendly display names for the A93 LVE-coded sites (the raw site IDs are
# infrastructure codes, not human-readable station names).
A93_NAME_BY_KM = {
    1.882: "AD Inntal",
    12.397: "Gletschergarten",
    12.26: "Gletschergarten",
    25.06: "Kiefersfelden",
}


def load_stations() -> pd.DataFrame:
    """Load the station CSV and deduplicate per site."""
    df = pd.read_csv(LOCATIONS_CSV, sep=";", decimal=",")
    df = df.rename(
        columns={
            "Latitude_WGS84": "lat",
            "Longitude_WGS84": "lon",
            "BAB-Km": "km",
            "Strecke": "route",
        }
    )
    # Deduplicate: many rows are just the same site with different detectors.
    sites = df.drop_duplicates(subset=["site"]).copy()
    sites["road"] = sites["route"].str.split("_").str[0]  # A8-Ost / A93-Sued
    sites["direction_short"] = sites["route"].str.split("_").str[1]  # Mch/Sbg/Ros/Kff
    sites["km_num"] = sites["km"].astype(str).str.replace(",", ".").astype(float)

    def short(row: pd.Series) -> str:
        if row["road"] == "A93-Sued":
            return A93_NAME_BY_KM.get(round(row["km_num"], 3), row["site"].split("_")[0])
        return row["site"].split("_")[0]

    sites["short_name"] = sites.apply(short, axis=1)
    return sites.reset_index(drop=True)


def plot() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sites = load_stations()

    fig, ax = plt.subplots(figsize=(13, 9))

    # --- Highway skeletons -------------------------------------------------
    a8_lat, a8_lon = zip(*A8_WAYPOINTS)
    a93_lat, a93_lon = zip(*A93_WAYPOINTS)
    ax.plot(a8_lon, a8_lat, "-", color="#1f4e96", linewidth=4.5, alpha=0.75, label="A8-Ost (München ↔ Salzburg)")
    ax.plot(a93_lon, a93_lat, "-", color="#b03020", linewidth=4.5, alpha=0.75, label="A93-Süd (Rosenheim ↔ Kufstein)")

    # --- Cities and interchanges ------------------------------------------
    for name, lat, lon, off in CITIES:
        ax.plot(lon, lat, marker="s", color="black", markersize=9)
        ax.annotate(
            name,
            (lon, lat),
            xytext=off,
            textcoords="offset points",
            fontsize=11,
            fontweight="bold",
        )

    for name, lat, lon in INTERCHANGES:
        ax.plot(lon, lat, marker="*", color="#222", markersize=14)
        ax.annotate(
            name,
            (lon, lat),
            xytext=(8, -14),
            textcoords="offset points",
            fontsize=9,
            color="#333",
            style="italic",
        )

    # --- Stations (colour by road, marker by direction) -------------------
    direction_marker = {
        "Mch": "^",  # toward München (inbound on A8)
        "Sbg": "v",  # toward Salzburg (outbound on A8)
        "Ros": "^",  # toward Rosenheim (inbound on A93)
        "Kff": "v",  # toward Kufstein (outbound on A93)
    }
    road_color = {"A8-Ost": "#1f4e96", "A93-Sued": "#b03020"}

    # Offset duplicates at the same coordinate so both direction markers show.
    offsets = {}
    for _, row in sites.iterrows():
        key = (round(row["lat"], 5), round(row["lon"], 5))
        rank = offsets.get(key, 0)
        offsets[key] = rank + 1
        dx = 0.004 * rank
        dy = 0.0015 * rank
        marker = direction_marker.get(row["direction_short"], "o")
        color = road_color.get(row["road"], "grey")
        ax.plot(
            row["lon"] + dx,
            row["lat"] + dy,
            marker=marker,
            color=color,
            markersize=12,
            markeredgecolor="white",
            markeredgewidth=1.2,
        )

    # --- Station labels: group sites by (road, km) so co-located stations
    # (different directions) share a single label like "MQB25 / MQQ37".
    LABEL_OFFSETS = {
        ("A8-Ost", 20.1): (10, -34),
        ("A8-Ost", 93.4): (-95, -28),
        ("A8-Ost", 94.7): (10, 18),
        ("A8-Ost", 106.3): (10, -34),
        ("A93-Sued", 1.9): (14, -6),
        ("A93-Sued", 12.3): (14, -2),
        ("A93-Sued", 12.4): (14, -2),
        ("A93-Sued", 25.1): (14, 6),
    }
    # Cluster stations by ~2 km radius so co-located sites (different
    # directions at the same junction) share one annotation. We bin lat/lon
    # to 0.02° (≈ 2 km at this latitude).
    sites = sites.copy()
    sites["cluster_key"] = list(zip(
        sites["road"],
        (sites["lat"] / 0.02).round().astype(int),
        (sites["lon"] / 0.02).round().astype(int),
    ))
    for cluster_key, group in sites.groupby("cluster_key"):
        road = cluster_key[0]
        km_repr = round(group["km_num"].mean(), 1)
        names = sorted(set(group["short_name"]))
        label = " / ".join(names) + f"\nkm {km_repr:g}"
        xy_off = LABEL_OFFSETS.get((road, km_repr), (12, -22))
        ax.annotate(
            label,
            (group["lon"].mean(), group["lat"].mean()),
            xytext=xy_off,
            textcoords="offset points",
            fontsize=8.5,
            color="#222",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#bbb", alpha=0.85),
        )

    # --- Legend ------------------------------------------------------------
    legend_handles = [
        plt.Line2D([0], [0], color="#1f4e96", linewidth=4, label="A8-Ost"),
        plt.Line2D([0], [0], color="#b03020", linewidth=4, label="A93-Süd"),
        plt.Line2D([0], [0], marker="^", color="grey", markersize=11, linestyle="", label="Direction: München / Rosenheim"),
        plt.Line2D([0], [0], marker="v", color="grey", markersize=11, linestyle="", label="Direction: Salzburg / Kufstein"),
        plt.Line2D([0], [0], marker="s", color="black", markersize=8, linestyle="", label="City"),
        plt.Line2D([0], [0], marker="*", color="#222", markersize=12, linestyle="", label="Autobahnkreuz"),
    ]
    ax.legend(handles=legend_handles, loc="lower left", fontsize=9, framealpha=0.95)

    # --- Axis formatting --------------------------------------------------
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.set_title(
        "Measurement Stations on A8-Ost and A93-Süd\n"
        "(highway lines are schematic, not survey-accurate)",
        fontsize=13,
    )
    ax.set_xlim(11.45, 13.15)
    ax.set_ylim(47.50, 48.20)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.set_aspect(1.4)  # roughly correct for ~48°N (longitude is shorter)

    fig.tight_layout()
    fig.savefig(OUT_FILE, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return OUT_FILE


if __name__ == "__main__":
    path = plot()
    print(f"Wrote {path}")
