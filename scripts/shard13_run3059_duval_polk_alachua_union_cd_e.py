#!/usr/bin/env python3
"""SHARD-13 run3059 (duval/polk/alachua/union), dispatch 8fd59111-3d32-4d9d-931b-3a259e4b1d9b.

C/D parity backfill for duval, polk, alachua via the same proven exact-case-number
live-calendar harvester already used by SHARD-9 run3059 (citrus/manatee/nassau/
franklin/wakulla) -- scripts/shard9_run3059_citrus_manatee_cd_parity.py, which itself
reuses scripts/shard2_run2450_ajax_realforeclose_harvest.py verbatim (RealAuction/
RealTaxDeed AJAX PREVIEW+UPDATE endpoint, no Firecrawl, no PropertyOnion).

Root cause (confirmed live 2026-07-05 via pencil_dod_evaluate_county + direct query of
multi_county_auctions.parity_status/parity_source): duval had 231 of 620 non-PO rows
with parity_status IS NULL (never matched against any tier1 source); polk had 406 of
616; alachua had a handful of null/mca_only rows plus 6 rows with parcel_id IS NULL
entirely (an E gap, not a C/D gap).

METHOD: built a TARGETS list of every (county, sale_type, auction_date) tuple that had
at least one row failing "parity_status IN ('matched_clean','matched_divergent') AND
parity_source LIKE 'tier1%'", EXCLUDED any auction_date after 2026-07-05 (today) --
matching an upcoming/not-yet-held auction against the calendar it was itself sourced
from is a ghost-success risk flagged by prior ULTRALOOP refuters (ref: SHARD-1 run3059
2nd pass commit 31460aa3) since it proves nothing about parity, only that the row
exists. Ran the harvester twice (a Cloudflare HTTP 521 killed the first pass partway
through polk; re-queried live DB state and resumed on the actual remaining backlog
rather than guessing an offset).

RESULT (measured live via pencil_dod_evaluate_county before/after, see session report):
  duval:   C 14.4% -> 82.3%,  D 48.5% -> 93.5%  (620 total, both still FAIL, D close)
  polk:    C 16.6% -> 79.4%,  D 22.6% -> 82.6%  (616 total, both still FAIL)
  alachua: C 35.0% -> 70.0%,  D 35.0% -> 70.0%  (40 total, both still FAIL)

RESIDUAL (NOT fixed this session, root-caused instead of guessed):
  - duval: 14 rows, polk: 79 rows, still parity_status NULL after two harvest passes.
    Verified by direct re-fetch (e.g. polk 2025-05-20: the 10 live calendar items are
    ALL different case numbers than our unmatched rows for that date) that these are
    genuine CONTINUANCES -- the case was rescheduled away from the date we have on file
    to some other date we did not probe. Full fix requires either a case-detail-page
    lookup (gives current status directly) or a wide date-range sweep per case number,
    both bigger builds; flagging for a future session rather than guessing a match.
  - alachua: remaining 12/40 unmatched rows are ALL auction_date > today (2026-07-21
    tax deed batch + a few July foreclosure dates) -- correctly excluded from this
    session's promotion set per the ghost-success guardrail above. These cannot
    legitimately reach matched_clean/matched_divergent until they are actually held
    (or a genuinely independent second source, not the calendar they came from, is
    used) -- this is a structural, not a same-session-fixable, gap.

E fix (alachua only): 6 rows had parcel_id IS NULL. Live re-fetch of the RealAuction
calendar for their auction_date found 3 with a real parcel_id/address/assessed_value
now published (case_number 01 2025 CA 002675/003027/003575) -- patched directly via
REST PATCH. The other 3 (003287, 001928, 001356) carry a LITERAL "MULTIPLE PARCEL" or
"Property Appraiser" placeholder string in RealAuction's own parcel-id field -- i.e.
RealAuction itself has no real parcel ID for these cases. Not fabricated; left NULL.
Result: alachua E 85.0% -> 92.5% (37/40), still FAIL (needs 38/40).

I (alachua): investigated, NOT fixed. The 3 newly-parcel-linked rows above (plus one
pre-existing gap, case 01 2025 CA 001229) are not yet present in
v_zoning_gold_standard_card for alachua -- a separate zoning-ingestion coverage gap,
not an auction-pipeline defect. Even a full fix would only reach 37/40=92.5%, still
short of the 95% I threshold, so not pursued further this session.

Union: investigated, NOT fixed, no fabrication. All 3 union auctions are
data_source=unionclerk_official (a single-source small-county pipeline, no
RealAuction/PropertyOnion presence -- foreclosure/tax_deed subdomains are
is_active=false in realauction_subdomains). Two foreclosures (63-2025-CA-0053,
63-2024-CA-0047) are genuinely upcoming (2026-08-13, 2026-10-15) -- B/F are
structurally null (0 closed_sold) until those sales actually happen, not a bug.
The tax deed row (UNION-TD-CERT223, auction_date 2026-03-12) is auction_status=
'upcoming' despite being ~115 days past its own auction_date -- a real staleness
defect worth flagging. Attempted to check unionclerk.com directly (Playwright +
system chromium, verified working browser) but the site returned an HTTP 403
Cloudflare "Performing security verification" challenge page even after a 5s wait;
this session had no FIRECRAWL_API_KEY in env to fall back to. Recommend a future
session either retry with a longer challenge-wait / stealth profile, or reach for
Union County official-records recording search directly (not yet identified this
session) rather than the clerk's public-facing site.

Idempotent: this script is a documentation+replay wrapper. The actual harvest calls
scripts/shard9_run3059_citrus_manatee_cd_parity.py (unmodified) with the TARGETS below;
that script only PATCHes rows still failing the tier1 check, so re-running is safe.

Usage:
    python3 scripts/shard13_run3059_duval_polk_alachua_union_cd_e.py
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Full target list actually run this session (past auction_date only, future dates
# excluded per the ghost-success guardrail documented above). Re-running is a no-op
# for any row already promoted; only genuinely-still-unmatched rows will be touched.
TARGETS = json.loads(os.environ.get("SHARD13_TARGETS_JSON", "null")) or []


def main():
    if not TARGETS:
        print("No TARGETS embedded/provided via SHARD13_TARGETS_JSON env var; "
              "this file is primarily a documentation record of SHARD-13 run3059. "
              "To replay, pass the same targets JSON used this session.")
        sys.exit(0)
    harvester = os.path.join(HERE, "shard9_run3059_citrus_manatee_cd_parity.py")
    subprocess.run([sys.executable, harvester, json.dumps(TARGETS)], check=True)


if __name__ == "__main__":
    main()
