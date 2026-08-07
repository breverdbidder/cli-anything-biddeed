#!/usr/bin/env bash
# GOLD STANDARD SHARD-3 — Main orchestration script
# dispatch_id: 85a4f86f-993f-40c0-9095-47ac8d01a6e5
# session: architect-20260807T080000
# Counties: collier, hamilton, clay, escambia, putnam
#
# Execution order (priority by leverage):
#   1. clay G zone_standards migration (most likely to pass with known fix)
#   2. escambia I+J backfill (new rows since 07-24)
#   3. escambia C/D re-probe (08/05 past — convergence window)
#   4. putnam I+J backfill (large gap: 73.2%)
#   5. putnam C/D clerk certification
#   6. collier I backfill (91.4% -> 95%)
#   7. Verify all counties
#   8. Session close-out migration

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
cd "$REPO_DIR"

echo "======================================================================"
echo "GOLD STANDARD SHARD-3 — 2026-08-07 session"
echo "dispatch_id: 85a4f86f-993f-40c0-9095-47ac8d01a6e5"
echo "======================================================================"
echo ""

# ── Step 1: clay G zone_standards ─────────────────────────────────────────────
echo "STEP 1: clay G zone_standards migration..."
python3 mgmt_sql.py -f migrations/20260807_shard3_clay_g_zone_standards.sql
echo "clay G migration applied."
echo ""

# ── Step 2: escambia I+J backfill ─────────────────────────────────────────────
echo "STEP 2: escambia I+J backfill (new rows since 07-24)..."
python3 scripts/shard3_escambia_ij_backfill_20260807.py
echo ""

# ── Step 3: escambia C/D re-probe ─────────────────────────────────────────────
echo "STEP 3: escambia C/D re-probe (08/05 convergence)..."
python3 scripts/shard3_escambia_cd_reprobe_20260807.py
echo ""

# ── Step 4: putnam I+J backfill ───────────────────────────────────────────────
echo "STEP 4: putnam I+J backfill..."
python3 scripts/shard3_putnam_ij_backfill_20260807.py
echo ""

# ── Step 5: putnam C/D clerk certification ────────────────────────────────────
echo "STEP 5: putnam C/D clerk certification..."
python3 scripts/shard3_putnam_cd_clerk_20260807.py
echo ""

# ── Step 6: collier I backfill ────────────────────────────────────────────────
echo "STEP 6: collier I backfill..."
python3 scripts/shard3_collier_i_backfill_20260807.py
echo ""

# ── Step 7: Verification (per VERIFICATION PROTOCOL) ─────────────────────────
echo "STEP 7: Verification — pencil_dod_evaluate_county for all 5 counties..."
echo ""

for county in collier hamilton clay escambia putnam; do
    echo "--- $county ---"
    python3 mgmt_sql.py "SELECT public.pencil_dod_evaluate_county('$county');"
    echo ""
done

# ── Step 8: Session close-out migration ───────────────────────────────────────
echo "STEP 8: Session close-out migration..."
python3 mgmt_sql.py -f migrations/20260807_shard3_session_closeout.sql
echo "Close-out migration applied."
echo ""

echo "======================================================================"
echo "SHARD-3 SESSION COMPLETE"
echo "dispatch_id: 85a4f86f-993f-40c0-9095-47ac8d01a6e5"
echo "======================================================================"
