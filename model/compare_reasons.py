"""
Compare old SHAP 原因 vs new ablation 原因 in forecast_2026_2029_daily.csv.

Usage (after running the notebook to generate new daily file):
    python compare_reasons.py
"""
import re
import pandas as pd
import numpy as np

ROOT = "../data_autobahn"
OLD = f"{ROOT}/forecast_2026_2029_daily_SHAP_BACKUP.csv"
NEW = f"{ROOT}/forecast_2026_2029_daily.csv"


def parse_reasons(s: str) -> dict:
    """Parse 'Name: XX.X%；Name: YY.Y%' -> {name: float}"""
    out = {}
    for part in re.split(r"[；;]", str(s)):
        part = part.strip()
        if not part or ":" not in part:
            continue
        name, pct = part.rsplit(":", 1)
        out[name.strip()] = float(pct.strip().replace("%", ""))
    return out


def main():
    old = pd.read_csv(OLD, parse_dates=["date"])
    new = pd.read_csv(NEW, parse_dates=["date"])

    print(f"Old (SHAP): {len(old)} rows, columns: {old.columns.tolist()}")
    print(f"New (ablation): {len(new)} rows, columns: {new.columns.tolist()}")

    # Check column match
    assert old.columns.tolist() == new.columns.tolist(), "COLUMN MISMATCH!"
    print("✅ Column names match")

    # Check 原因 format compatibility
    old_sample = old["原因"].iloc[0]
    new_sample = new["原因"].iloc[0]
    print(f"\nOld sample: {old_sample[:120]}...")
    print(f"New sample: {new_sample[:120]}...")

    # Parse all
    old_parsed = old["原因"].apply(parse_reasons)
    new_parsed = new["原因"].apply(parse_reasons)

    # Find all group names
    old_groups = set()
    new_groups = set()
    for d in old_parsed:
        old_groups.update(d.keys())
    for d in new_parsed:
        new_groups.update(d.keys())

    print(f"\nOld group names: {sorted(old_groups)}")
    print(f"New group names: {sorted(new_groups)}")

    # Check group name overlap
    common = old_groups & new_groups
    only_old = old_groups - new_groups
    only_new = new_groups - old_groups
    if only_old:
        print(f"⚠️  Only in old: {only_old}")
    if only_new:
        print(f"⚠️  Only in new: {only_new}")
    if not only_old and not only_new:
        print("✅ All group names match between old and new")

    # For common groups, compare mean percentages
    print("\n--- Mean percentage comparison ---")
    print(f"{'Group':<45} {'SHAP':>8} {'Ablation':>8} {'Diff':>8}")
    print("-" * 70)
    for g in sorted(common):
        old_mean = np.mean([d.get(g, 0) for d in old_parsed])
        new_mean = np.mean([d.get(g, 0) for d in new_parsed])
        print(f"{g:<45} {old_mean:>7.1f}% {new_mean:>7.1f}% {new_mean-old_mean:>+7.1f}%")

    # Correlation per group
    print("\n--- Pearson correlation (SHAP vs Ablation) ---")
    old_df = pd.DataFrame([{g: d.get(g, 0) for g in common} for d in old_parsed])
    new_df = pd.DataFrame([{g: d.get(g, 0) for g in common} for d in new_parsed])
    for g in sorted(common):
        r = old_df[g].corr(new_df[g])
        print(f"  {g:<45} r={r:+.4f}")

    # Check: do sums match ~100%?
    old_sums = old_df.sum(axis=1)
    new_sums = new_df.sum(axis=1)
    print(f"\nOld sum range: {old_sums.min():.1f}% – {old_sums.max():.1f}%")
    print(f"New sum range: {new_sums.min():.1f}% – {new_sums.max():.1f}%")

    # Spot-check: peak holiday dates
    print("\n--- Spot-check: peak dates ---")
    holiday_dates = ["2026-08-01", "2026-12-24", "2026-07-25", "2026-03-04"]
    for d in holiday_dates:
        old_row = old[old["date"] == d]
        new_row = new[new["date"] == d]
        if len(old_row) == 0 or len(new_row) == 0:
            continue
        # Average across all sites
        old_avg = parse_reasons(old_row["原因"].iloc[0])
        new_avg = parse_reasons(new_row["原因"].iloc[0])
        print(f"\n  {d}:")
        for g in sorted(common):
            ov = old_avg.get(g, 0)
            nv = new_avg.get(g, 0)
            if abs(ov - nv) > 1:
                print(f"    {g:<40} SHAP={ov:5.1f}%  Ablation={nv:5.1f}%  Δ={nv-ov:+.1f}%")

    print("\n✅ Comparison complete.")


if __name__ == "__main__":
    main()
