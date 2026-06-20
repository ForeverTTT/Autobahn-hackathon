#!/bin/bash
# =============================================================================
# Clean all CatBoost model training outputs before re-running model_notebook.ipynb
#
# Usage:
#   bash clean_outputs.sh          # clean everything
#   bash clean_outputs.sh --dry    # preview what would be deleted (no action)
#
# WARNING: This deletes ALL generated model files. Re-run the notebook to regenerate.
# Does NOT touch:
#   - data_autobahn/ (training data)
#   - models/tft/ (teammate's TFT checkpoints)
#   - doc/ (documentation)
# =============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
DRY=false
[[ "${1:-}" == "--dry" ]] && DRY=true

clean() {
    if $DRY; then
        echo "[DRY] would remove: $*"
    else
        rm -rf "$@"
        echo "  removed: $*"
    fi
}

echo "=== Cleaning model outputs in $ROOT ==="
$DRY && echo " (dry run — no files will be deleted)"

# --- processed/ ---
echo ""
echo "processed/:"
clean "$ROOT/processed/conformal.json"
clean "$ROOT/processed/forecast_2026_2029.csv"
clean "$ROOT/processed/forecast_2026_2029.parquet"
clean "$ROOT/processed/forecast_kfz_2026_2029.parquet"
clean "$ROOT/processed/forecast_sv_2026_2029.parquet"
clean "$ROOT/processed/forecast_vkfz_2026_2029.parquet"
clean "$ROOT/processed/profiles.pkl"
clean "$ROOT/processed/site_meta.parquet"

# --- models/ (CatBoost only — NOT tft/) ---
echo ""
echo "models/kfz_h/:"
clean "$ROOT/models/kfz_h/multi.cbm"

echo ""
echo "models/sv_h/:"
clean "$ROOT/models/sv_h/lkw_ratio.cbm"

echo ""
echo "models/v_kfz/:"
clean "$ROOT/models/v_kfz/speed_drop.cbm"

# --- snapshots/ (CatBoost training snapshots — huge, ~140MB) ---
echo ""
echo "models/snapshots/:"
clean "$ROOT/models/snapshots"/*

echo ""
echo "=== Done ==="
if $DRY; then
    echo "Run without --dry to actually delete."
else
    echo "Ready to re-run model_notebook.ipynb (Restart Kernel → Run All)."
fi
