"""Validate data hypotheses with code; output reusable artefacts.

Hypotheses tested (decide-by-evidence, not opinion):

H1. v_kfz max ~250 km/h is sensor noise; a sensible cap is ~160 km/h.
H2. DAUZ sv_h (heavy goods) and 1-min q_lkw (Lkw-ähnlich) are different
    classification standards, so they cannot be substituted for each other.
H3. tagestyp == 'u' (Urlaub / vacation-peak day) is more than just school
    holidays; it captures bridge days and shoulder-of-holiday travel.
H4. Intraday hourly profile is too variable within a single
    (corridor, tagestyp, weekday) bucket to use a single template;
    we need a finer grouping (holiday-edge day, season, etc.).

For each hypothesis we either confirm or reject with a number + a chart.

Outputs (all under analysis_output/):
  hypothesis_h1_vkfz.png             - v_kfz CDF + p99/max marker
  hypothesis_h2_lkw_vs_sv.png        - lkw_share vs sv_share scatter
  hypothesis_h3_tagestyp_u.csv       - distribution of 'u' days vs known
                                       school-holiday calendar (DE-BY)
  hypothesis_h4_intraday_cv.png      - coefficient-of-variation of the
                                       normalised 24h profile by group
  hypothesis_h4_intraday_cv.csv      - the same numbers as a table
  hypothesis_summary.md              - one-page conclusion the team reads

Usage::

    python scripts/validate_data_hypotheses.py            # all
    python scripts/validate_data_hypotheses.py --only h4  # specific

Reuses load helpers that other scripts (training pipeline, intraday-template
builder) can import.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DAUZ_DIR = PROJECT_ROOT / "data" / "DAUZ_2+0_1h_2023-2026"
MIN_DIR = PROJECT_ROOT / "data" / "2023-2025_1min_2+0_v"
HOLIDAY_FILE = PROJECT_ROOT / "Autobahn-hackathon" / "holidays" / "holiday_dates.csv"
OUT_DIR = PROJECT_ROOT / "analysis_output"
OUT_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Reusable loaders (imported by other scripts later)
# ---------------------------------------------------------------------------

def load_dauz_hourly(file_path: Path) -> pd.DataFrame:
    """Load one DAUZ hourly CSV into a tidy frame.

    Returns columns: date (datetime64[D]), hour (int), wochentag, tagestyp,
    kfz_h, sv_h, sv_share, station, direction.
    """
    df = pd.read_csv(file_path, sep=";", decimal=".")
    df["date"] = pd.to_datetime(df["datum"], format="%d.%m.%Y")
    df["hour"] = df["t_start"].str.slice(0, 2).astype(int)
    df["sv_share"] = df["sv_h"] / df["kfz_h"]
    # devices column: "9171_MQB25_Mch_H,DE33,34,35,36"
    station_info = df["devices"].iloc[0].split(",")[0]
    parts = station_info.split("_")
    df["station"] = "_".join(parts[1:-1]) if parts[-1] in {"H", "Ro", "Kff"} else "_".join(parts[1:])
    # Direction = last alphabetic chunk before the comma
    df["direction"] = parts[-1] if parts[-1] in {"H"} else parts[-1]
    return df[["date", "hour", "wochentag", "tagestyp", "kfz_h", "sv_h", "sv_share", "station", "direction", "devices"]]


def discover_dauz_files() -> list[Path]:
    return sorted(DAUZ_DIR.glob("*.csv"))


def load_all_dauz() -> pd.DataFrame:
    frames = []
    for f in discover_dauz_files():
        try:
            sub = load_dauz_hourly(f)
        except Exception as exc:
            print(f"  skip {f.name}: {exc}")
            continue
        sub["file"] = f.name
        frames.append(sub)
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# H1: v_kfz cap
# ---------------------------------------------------------------------------

def h1_speed_cap(sample_files: int = 3) -> dict:
    """Empirically derive a sensible v_kfz cap.

    We sample a few 1-min files (the only place v_kfz lives) and look at the
    upper-tail percentiles. Caps the user mentioned: 160 km/h.
    """
    files = sorted(MIN_DIR.glob("*.csv"))[:sample_files]
    print(f"H1: scanning {len(files)} 1-min files for v_kfz tail ...")
    samples = []
    for f in files:
        # Use chunked read to control memory.
        for chunk in pd.read_csv(f, sep=";", usecols=["v_kfz"], chunksize=200_000):
            v = chunk["v_kfz"].dropna()
            samples.append(v.values)
    arr = np.concatenate(samples)
    pct = np.percentile(arr, [50, 90, 95, 99, 99.9, 99.99])
    out = {
        "n": int(arr.size),
        "max": float(arr.max()),
        "p50": float(pct[0]),
        "p90": float(pct[1]),
        "p95": float(pct[2]),
        "p99": float(pct[3]),
        "p99_9": float(pct[4]),
        "p99_99": float(pct[5]),
    }
    # Plot CDF on log-x to expose the long tail.
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bins = np.linspace(0, 260, 200)
    ax.hist(arr, bins=bins, density=True, alpha=0.6)
    for q, val in zip(["p99", "p99.9", "max"], [pct[3], pct[4], arr.max()]):
        ax.axvline(val, linestyle="--", color="black", alpha=0.5)
        ax.text(val, ax.get_ylim()[1] * 0.9, f" {q}={val:.0f}", rotation=90, va="top")
    ax.axvline(160, color="red", linewidth=2, alpha=0.7, label="proposed cap 160 km/h")
    ax.set_xlabel("v_kfz (km/h, 1-min mean)")
    ax.set_ylabel("density")
    ax.set_title(f"H1 — v_kfz distribution (n={arr.size:,}, max={arr.max():.0f})")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "hypothesis_h1_vkfz.png", dpi=140)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# H2: sv_h vs q_lkw classification mismatch
# ---------------------------------------------------------------------------

def h2_sv_vs_lkw(reference_station: str = "MQB25") -> dict:
    """Compare DAUZ sv_h with 1-min q_lkw aggregated to the hour.

    If they tracked the same vehicle class they would be ~identical. We expect
    sv_h < q_lkw (because sv is >3.5t whereas q_lkw includes light goods).
    """
    # Find matching files
    dauz_files = list(DAUZ_DIR.glob(f"*{reference_station}*.csv"))
    min_files = list(MIN_DIR.glob(f"*{reference_station}*.csv"))
    if not dauz_files or not min_files:
        return {"skipped": True, "reason": f"missing files for {reference_station}"}

    dauz = load_dauz_hourly(dauz_files[0])
    # Aggregate 1-min q_lkw to hourly sums.
    min_df = pd.read_csv(
        min_files[0],
        sep=";",
        usecols=["datum", "t_start", "q_lkw"],
        dtype={"datum": str, "t_start": str},
    )
    min_df["date"] = pd.to_datetime(min_df["datum"], format="%d.%m.%Y")
    min_df["hour"] = min_df["t_start"].str.slice(0, 2).astype(int)
    hourly_lkw = min_df.groupby(["date", "hour"])["q_lkw"].sum().reset_index(name="q_lkw_hourly")

    merged = dauz.merge(hourly_lkw, on=["date", "hour"], how="inner")
    merged = merged.dropna(subset=["sv_h", "q_lkw_hourly"])
    merged = merged[(merged["kfz_h"] > 50) & (merged["q_lkw_hourly"] > 5)]  # ignore zeros/near-zero

    # Ratio statistic
    ratio = merged["sv_h"] / merged["q_lkw_hourly"]
    out = {
        "n_hours": int(len(merged)),
        "sv_h_mean": float(merged["sv_h"].mean()),
        "q_lkw_mean": float(merged["q_lkw_hourly"].mean()),
        "ratio_sv_over_lkw_median": float(ratio.median()),
        "ratio_sv_over_lkw_p25": float(ratio.quantile(0.25)),
        "ratio_sv_over_lkw_p75": float(ratio.quantile(0.75)),
        "corr": float(merged[["sv_h", "q_lkw_hourly"]].corr().iloc[0, 1]),
    }
    # Scatter
    fig, ax = plt.subplots(figsize=(6.5, 6.5))
    ax.scatter(merged["q_lkw_hourly"], merged["sv_h"], s=4, alpha=0.15)
    lim = max(merged["q_lkw_hourly"].max(), merged["sv_h"].max())
    ax.plot([0, lim], [0, lim], "k--", alpha=0.5, label="y=x (same classification)")
    ax.set_xlabel("q_lkw_hourly (1-min agg, vehicles/h)")
    ax.set_ylabel("sv_h (DAUZ, vehicles/h)")
    ax.set_title(
        f"H2 — sv_h vs q_lkw_hourly @ {reference_station}\n"
        f"median ratio sv/lkw = {out['ratio_sv_over_lkw_median']:.2f}, corr = {out['corr']:.3f}"
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "hypothesis_h2_lkw_vs_sv.png", dpi=140)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# H3: tagestyp 'u' classification
# ---------------------------------------------------------------------------

def h3_tagestyp_u() -> dict:
    """Cross-tabulate tagestyp=='u' against the DE-BY school-holiday calendar.

    If 'u' == school holiday only, agreement should be near 100%.
    Our hypothesis: 'u' also fires on bridge days / shoulder days; agreement
    will be partial.
    """
    if not HOLIDAY_FILE.exists():
        return {"skipped": True, "reason": "holiday_dates.csv missing"}

    df = pd.read_csv(DAUZ_DIR / discover_dauz_files()[0].name, sep=";")
    df["date"] = pd.to_datetime(df["datum"], format="%d.%m.%Y")
    # Reduce to one row per date (tagestyp is constant across the day).
    by_day = df.drop_duplicates("date").set_index("date")["tagestyp"].sort_index()
    by_day = by_day.loc["2024-01-01":"2025-12-31"]  # use the clean window

    h = pd.read_csv(HOLIDAY_FILE, parse_dates=["date"])
    h = h[h["region_code"] == "DE-BY"]
    sh = set(h.loc[h["holiday_class"] == "school_holiday", "date"].dt.normalize().unique())
    ph = set(h.loc[h["holiday_class"] == "public_holiday", "date"].dt.normalize().unique())

    cm = defaultdict(int)
    for date, t in by_day.items():
        d = pd.Timestamp(date).normalize()
        is_school = d in sh
        is_public = d in ph
        cm[(t, is_school, is_public)] += 1

    rows = []
    for (t, is_school, is_public), n in cm.items():
        rows.append({
            "tagestyp": t, "is_school_holiday": is_school,
            "is_public_holiday": is_public, "n_days": n,
        })
    table = pd.DataFrame(rows).sort_values(["tagestyp", "is_school_holiday", "is_public_holiday"])
    table.to_csv(OUT_DIR / "hypothesis_h3_tagestyp_u.csv", index=False)

    total_u = (by_day == "u").sum()
    u_dates = set(d.normalize() for d, t in by_day.items() if t == "u")
    u_on_school = len(u_dates & sh)
    u_pure = total_u - u_on_school  # how many 'u' days fall OUTSIDE school holidays

    return {
        "n_days_total": int(len(by_day)),
        "n_u_days": int(total_u),
        "n_u_inside_de_by_school_holiday": int(u_on_school),
        "n_u_outside_school_holiday": int(u_pure),
        "share_u_outside_school": round(u_pure / max(total_u, 1), 3),
    }


# ---------------------------------------------------------------------------
# H4: intraday curve variability  — KEY decision: are templates too coarse?
# ---------------------------------------------------------------------------

def normalised_profile(group: pd.DataFrame) -> np.ndarray:
    """Return a 24-vector of hourly_share (sum==1) per date."""
    pivot = group.pivot_table(index="date", columns="hour", values="kfz_h", aggfunc="sum")
    pivot = pivot.dropna(how="any")
    # Normalize each row
    row_sums = pivot.sum(axis=1)
    pivot = pivot.loc[row_sums > 1000]  # ignore near-empty days
    normed = pivot.div(pivot.sum(axis=1), axis=0)
    return normed  # rows=date, cols=hour 0..23


def h4_intraday_variability() -> dict:
    """Compute coefficient-of-variation per hour, for several groupings.

    Comparison:
      G_coarse: (tagestyp, weekday)           — original proposal
      G_fine:   (tagestyp, weekday, month)    — adds seasonality
      G_finer:  (tagestyp, weekday, holiday_edge) — distinguishes start/end days
    """
    # Use one representative station per corridor for speed.
    rep_files = [
        f for f in discover_dauz_files()
        if any(k in f.name for k in ["MQQ37_Sbg", "MQQ245_Mch", "Gletschergarten_Ro", "AD Inntal_(S)_Kff"])
    ]
    print(f"H4: using {len(rep_files)} representative DAUZ files")

    if HOLIDAY_FILE.exists():
        hol = pd.read_csv(HOLIDAY_FILE, parse_dates=["date"])
        hol_by_by = hol[hol["region_code"] == "DE-BY"]
        sh_set = set(hol_by_by.loc[hol_by_by["holiday_class"] == "school_holiday", "date"].dt.normalize())
    else:
        sh_set = set()

    results = []
    plot_curves = []  # (group_name, hour, mean, std)

    for f in rep_files:
        df = load_dauz_hourly(f)
        df = df.dropna(subset=["kfz_h"])
        df = df[(df["date"] >= "2024-02-01") & (df["date"] <= "2025-12-31")]
        df["month"] = df["date"].dt.month
        df["dow"] = df["wochentag"]
        # Holiday-edge flag: is this date the first or last day of a school holiday?
        edge_dates = set()
        if sh_set:
            sh_sorted = sorted(sh_set)
            for d in sh_sorted:
                edge_dates.add(d)
            # Mark start days (no preceding day) and end days (no following day)
            # by scanning consecutive runs.
            starts, ends = set(), set()
            sh_sorted_arr = sorted(sh_set)
            prev = None
            run = []
            runs = []
            for d in sh_sorted_arr:
                if prev is None or (d - prev).days == 1:
                    run.append(d)
                else:
                    runs.append(run)
                    run = [d]
                prev = d
            if run:
                runs.append(run)
            for r in runs:
                starts.add(r[0])
                ends.add(r[-1])
        else:
            starts, ends = set(), set()

        def edge(date):
            d = pd.Timestamp(date).normalize()
            if d in starts:
                return "start"
            if d in ends:
                return "end"
            return "none"

        df["holiday_edge"] = df["date"].apply(edge)

        for grouping_name, group_cols in [
            ("coarse_(tagestyp,dow)", ["tagestyp", "dow"]),
            ("fine_(tagestyp,dow,month)", ["tagestyp", "dow", "month"]),
            ("finer_(tagestyp,dow,edge)", ["tagestyp", "dow", "holiday_edge"]),
        ]:
            cv_per_group = []
            for key, sub in df.groupby(group_cols):
                profile = normalised_profile(sub)
                if len(profile) < 5:
                    continue
                std = profile.std(axis=0)
                mean = profile.mean(axis=0)
                cv = (std / mean.replace(0, np.nan)).mean()  # mean CV across 24 hours
                cv_per_group.append((key, len(profile), float(cv)))
                if grouping_name.startswith("coarse"):
                    # Save a few profile curves for plotting
                    plot_curves.append(
                        (f"{f.name.split('_')[3]}_{key}", mean.values, std.values, len(profile))
                    )
            cvs = [c[2] for c in cv_per_group]
            results.append({
                "station": f.name,
                "grouping": grouping_name,
                "n_groups": len(cv_per_group),
                "cv_mean": float(np.mean(cvs)) if cvs else float("nan"),
                "cv_median": float(np.median(cvs)) if cvs else float("nan"),
            })

    res_df = pd.DataFrame(results)
    res_df.to_csv(OUT_DIR / "hypothesis_h4_intraday_cv.csv", index=False)

    # Plot: for one station, show coarse-group mean profile ± std band for top groups
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharex=True, sharey=True)
    axes = axes.flatten()
    plot_curves_sorted = sorted(plot_curves, key=lambda x: -x[3])[:4]
    hours = np.arange(24)
    for ax, (name, mean, std, n) in zip(axes, plot_curves_sorted):
        ax.fill_between(hours, mean - std, mean + std, alpha=0.25, color="C0")
        ax.plot(hours, mean, "C0-", linewidth=2)
        ax.set_title(f"{name}  (n={n} days)", fontsize=9)
        ax.set_ylabel("hourly share")
        ax.grid(alpha=0.3)
    for ax in axes:
        ax.set_xlabel("hour")
    fig.suptitle(
        "H4 — Intraday profile mean ± std within a coarse group\n"
        "(wide bands → templates are too coarse)",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(OUT_DIR / "hypothesis_h4_intraday_cv.png", dpi=140)
    plt.close(fig)

    # Aggregate decision
    by_grouping = res_df.groupby("grouping")["cv_mean"].mean().to_dict()
    return {
        "cv_mean_by_grouping": {k: round(v, 3) for k, v in by_grouping.items()},
        "interpretation": (
            "Lower CV means the profile is more stable inside the group; "
            "use the finest grouping whose groups still have enough days "
            "(n >= 5)."
        ),
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main(only: list[str] | None = None) -> None:
    only_set = set(only or [])
    results = {}

    if not only_set or "h1" in only_set:
        print("\n[H1] v_kfz speed cap ...")
        results["h1"] = h1_speed_cap()
        print("  ", results["h1"])

    if not only_set or "h2" in only_set:
        print("\n[H2] sv_h vs q_lkw ...")
        results["h2"] = h2_sv_vs_lkw()
        print("  ", results["h2"])

    if not only_set or "h3" in only_set:
        print("\n[H3] tagestyp == 'u' coverage ...")
        results["h3"] = h3_tagestyp_u()
        print("  ", results["h3"])

    if not only_set or "h4" in only_set:
        print("\n[H4] intraday profile variability ...")
        results["h4"] = h4_intraday_variability()
        print("  ", results["h4"])

    # Summary
    md = ["# Data Hypothesis Validation Results", "", f"_Generated {datetime.now():%Y-%m-%d %H:%M}_", ""]
    for k, v in results.items():
        md.append(f"## {k.upper()}")
        md.append("```")
        md.append(repr(v))
        md.append("```")
        md.append("")
    (OUT_DIR / "hypothesis_summary.md").write_text("\n".join(md))
    print(f"\nWrote summary -> {OUT_DIR / 'hypothesis_summary.md'}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--only", nargs="+", help="subset of {h1,h2,h3,h4}")
    args = p.parse_args()
    main(args.only)
