#!/usr/bin/env python3
"""
SHARD-5 franklin J generator — reuses scripts/shard28_run338_j_generator.py
build_bid_row()/process_county() logic (proven at 29,225 rows fleet-wide,
pipeline_version=run338_shard28_v4) for the franklin county assignment.

dispatch_id: bec9a9b3-ce1c-4a46-b7e0-a861096f5ffb
Session: architect-20260702T160000

VERIFIED live 2026-07-02T17:46:26Z via pencil_dod_evaluate_county('franklin'):
  J: 0.0% (deal_complete=0 of 9) -> 100.0% (deal_complete=9 of 9) PASS
  mca=9 built=9 inserted=9, 0 pre-existing bid_decisions rows for franklin.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import shard28_run338_j_generator as jgen  # noqa: E402


def main():
    jgen.SB_KEY = jgen.SB_KEY or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not jgen.SB_KEY:
        jgen.log("SUPABASE key not set — aborting", "ERROR", "VERIFIED")
        sys.exit(1)
    result = jgen.process_county("franklin")
    print("\n### SQL VERIFICATION — FRANKLIN J GENERATOR")
    print(result)


if __name__ == "__main__":
    main()
