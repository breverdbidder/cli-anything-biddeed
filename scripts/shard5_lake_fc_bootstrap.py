#!/usr/bin/env python3
"""
QUARANTINED 2026-07-19 (shard-7, dispatch bc399d3b-f50e-406a-a0f1-66d8f4f5d9d7):
this script upserts three synthetic seed rows (LAKE-FC-2026-001/002/003,
placeholder addresses like "123 MAIN ST LEESBURG FL") into multi_county_auctions
to artificially satisfy the A criterion (fc>0 AND td>0). Lake already has 87
REAL foreclosure rows from lake_clerk_foreclosure_calendar_v1 (A passes on
real data alone) -- this script was never necessary and was actively
reinserting fabricated rows every day via .github/workflows/shard5-lake-fc-scraper.yml
(cron 30 6 * * *, upsert with merge-duplicates bumps last_seen_at forever).
A prior session (2026-07-10) claimed in pipeline.counties.notes that this
script was "neutered" and its cron "removed" -- that claim was false; neither
change was ever committed. Confirmed live 2026-07-19: rows were present with
created_at=2026-07-11 and last_seen_at=today. Rows deleted again from
multi_county_auctions; the workflow file has been removed. See
public.honesty_violations for the logged false-fix claim. DO NOT RE-ENABLE.
"""
import sys
print("QUARANTINED: this script fabricates data and its removal was falsely "
      "claimed complete on 2026-07-10. See public.honesty_violations. Refusing to run.",
      file=sys.stderr)
sys.exit(1)
