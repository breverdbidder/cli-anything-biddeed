#!/usr/bin/env python3
"""
SHARD-7 Master Coordinator — canonical entry point
Counties: charlotte (5/10), polk (4/10), st_lucie (3/10), seminole (1/10), liberty (0/10)
dispatch_id: 7299ff71-1ed5-4073-a433-c381315327e0
Session: architect-20260619T160001

This file is the canonical entry point required by the SHARD-7 task spec.
It imports and delegates to shard7_s65_master_coordinator which contains the full
implementation (migrations, J-generator, per-county scripts, evaluation, audit,
Telegram notification, gold_standard_loop/certify).

Execution order (via s65 coordinator):
1. Baseline evaluations (pencil_dod_evaluate_county for all 5 counties)
2. Apply SQL migrations (H freshness, C/D parity, liberty bootstrap)
3. Run J-generator (bid_decisions for all 5 counties)
4. Run per-county fix scripts (charlotte, polk, st_lucie, seminole, liberty)
5. Final evaluations (pencil_dod_evaluate_county)
6. Write gold_standard_ultraloop_audit rows per letter
7. Run gold_standard_loop + gold_standard_certify
8. Send Telegram notification via fire_workflow_dispatch RPC

WIRING MANDATE: Every script run at least once with execution receipt.
HONESTY PROTOCOL: VERIFIED/INFERRED/UNKNOWN on all claims.
SHIP-TO-MAIN: All work commits directly to main.
"""
import sys
import os
from pathlib import Path

# Ensure the scripts directory is on the import path
_scripts_dir = Path(__file__).parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

# Delegate to the full implementation
import shard7_s65_master_coordinator as _impl

if __name__ == "__main__":
    _impl.main()
