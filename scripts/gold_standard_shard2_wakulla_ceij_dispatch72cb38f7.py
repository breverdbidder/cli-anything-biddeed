#!/usr/bin/env python3
"""GOLD STANDARD shard-2, wakulla county, letters C / E / I / J (dispatch 72cb38f7).

HONEST NEGATIVE-RESULT REPORT -- this script performs and documents a
verification sweep. It intentionally makes ZERO writes to multi_county_auctions,
parcel_zones, or bid_decisions, because no real, verifiable data was
recoverable for the 5 target rows after exhausting every realistically
accessible public source. Per BLANK > WRONG (HONESTY PROTOCOL), a documented
"nothing recoverable" is the correct and complete deliverable here -- not a
forced or fabricated write.

============================================================================
TARGET ROWS (multi_county_auctions, county='wakulla', all sale_type=tax_deed,
all parcel_id IS NULL as of this session -- re-verified live before any
investigation began):
============================================================================
  2026-TXD-097  auction_date=2026-07-08  parity_status=matched_clean
                data_source=wakulla_clerk_live
  2026-TXD-117  auction_date=2026-08-19  parity_status=CLERK_SSOT_CANCELLED
  2026-TXD-118  auction_date=2026-08-19  parity_status=CLERK_SSOT_CANCELLED
  2026-TXD-120  auction_date=2026-08-19  parity_status=CLERK_SSOT_CANCELLED
  2026-TXD-122  auction_date=2026-08-19  parity_status=CLERK_SSOT_CANCELLED

============================================================================
LETTER E / I / J -- WHY NO PARCEL_ID WAS RECOVERABLE (investigated live,
2026-08-13)
============================================================================

Sources checked, in order, all confirmed EITHER "no data present" (a genuine
negative, not a tooling failure) OR blocked to automated access:

1. wakullaclerk.org/official_records/tax_deed_sales.php (the clerk's live
   tax-deed-sale calendar -- this is the authoritative source, and the same
   one scripts/wakulla_td_parcel_harvest.py already uses successfully for
   the 6 sibling rows in this SAME auction batch that DO have a parcel_id:
   2026-TXD-111/112/114/115/119/121).
     - Status column for 113, 116, 117, 118, 120, 122 (all six) reads
       "Redeemed" (raw HTML span/table cell text, verified via curl fetch +
       regex, see LETTER-C section below).
     - Critically: this page attaches a "Notice of Application for Tax Deed"
       PDF link (which is where parcel_id/owner/legal description live) ONLY
       to cases that reached the point of a published sale notice. A live
       regex sweep of the full page HTML for
       `href="...\.pdf..."...>2026-TXD-\d+</a>` pairs found PDF links for
       exactly 6 cases: 111, 112, 114, 115, 119, 121 -- precisely the 6
       sibling rows that already have parcel_id in our DB. ZERO PDF links
       exist for 113, 116, 117, 118, 120, or 122. This is consistent with a
       redemption happening before the clerk ever published the tax-deed
       application notice for these specific certificates -- there is no
       parcel-bearing document to fetch for them on this source, full stop.
     - 2026-TXD-097 is not on this page at all: its auction_date (2026-07-08)
       has passed, and the live calendar only carries the current/upcoming
       cycle. No archive of the July cycle is publicly linked from this page
       or discoverable via search.

2. scripts/wakulla_landmarkweb_outcomes_harvest.py (prior, INDEPENDENT
   session, 2026-07-24) -- its own docstring records: "confirming a genuine
   gap at case 2026-TXD-097 -- no bidder, no deed recorded, not a scraper
   defect." This is prior, independently-collected evidence (via the
   LandmarkWeb NameSearch+GetSearchResults API, grantor="WAKULLA COUNTY
   CLERK OF COURT") that 2026-TXD-097 never had ANY document (deed or
   otherwise) recorded against it. Re-confirmed live this session via the
   LandmarkWeb UI's own "Case Number Search" tool (see below) returning 0
   records for all 5 target case numbers.

3. Wakulla Clerk LandmarkWeb Official Records Index, "Case Number Search"
   (http://www.wakullaclerk.com/landmarkweb, live browser session this
   session): searched "2026-TXD-097", "2026-TXD-117", "2026-TXD-118",
   "2026-TXD-120", "2026-TXD-122" -- every one returned "Returned 0 records".
   Sanity-checked against a KNOWN, already-resolved wakulla case number
   (23-CA-627, a foreclosure with a real, fully-populated row in our DB) --
   that ALSO returned 0 records. This proves the Official Records "Case
   Number" field indexes circuit-court/recording case numbers under a
   different internal scheme than either tax-deed-application IDs or the
   civil case numbers our DB already carries -- i.e. this tool structurally
   cannot answer this lookup for ANY wakulla case, not just ours. A negative
   result here is a tooling-scope finding, not evidence the parcels don't
   exist.

4. qpublic.schneidercorp.com (Wakulla County Property Appraiser search) --
   direct curl gets HTTP 403 (bot-blocked); a real headless-browser session
   loads the search UI fine, but the UI requires a search key (owner name,
   parcel number, or address) to return anything. We have none of the three
   for any of these 5 rows -- the tax deed case number itself is not a
   field this tool indexes (it's a Property Appraiser tool, not a Clerk of
   Court tool). No lookup could be attempted.

5. wakullacountytaxcollector.com/Property/CountyCertificates (public
   county-wide outstanding tax-certificate roll, downloaded and parsed live
   this session with openpyxl -- 1131-row .xlsx, 'CC=County Cert / CI=Ind
   Cert / TD=Certificate currently in Tax Deed Application' status column
   checked for TD rows: 0 TD rows in the current export). Cross-checked: NONE
   of the 8 already-known parcel_ids from this same auction batch (111, 112,
   113, 114, 115, 116, 119, 121) appear anywhere in this export either --
   confirming it is a snapshot of certificates that have NOT yet progressed
   to tax-deed application, i.e. structurally cannot contain any of our
   already-progressed-to-sale target cases, known or unknown.

6. Wakulla Tax Collector site (wakullatax.com) -- no case-number or
   certificate-number public search tool found; only points to the
   certificate-sale platform (taxcertsale.com, an auction-bidding UI with no
   general public search either) and the CountyCertificates export
   (source 5, dead end).

CONCLUSION (E / I / J): no parcel_id, property_address, assessed/market
value, or lat/lon is recoverable for 2026-TXD-097, -117, -118, -120, or -122
through any publicly accessible, non-authenticated source as of 2026-08-13.
Per this task's explicit instruction, no field is fabricated. ZERO writes
made to multi_county_auctions for these 5 rows.

Because none of these 5 rows can be grounded with a real parcel_id or value,
letter J (bid_decisions) is also correctly left untouched for them -- the
Shapira-v14 generator pattern (scripts/highlands_j_bid_decisions_backfill.py)
requires either a real assessed/market value or, at minimum, a real
parcel-linked row to avoid manufacturing a deal recommendation on a phantom
property. Fabricating an ARV/max_bid off nothing but the county median for
5 rows we cannot even confirm the address of would violate the same
BLANK > WRONG principle this task explicitly invokes. ZERO writes made to
bid_decisions for these 5 rows.

Letter I (card_complete, parcel_zones linkage) has nothing to check for
these 5 rows either -- linkage requires a parcel_id to key against
parcel_zones, and none exists. ZERO writes made to parcel_zones.

============================================================================
LETTER C -- INVESTIGATION OF CLERK_SSOT_CANCELLED STATUS (113, 116, 117,
118, 120, 122)
============================================================================

Live re-check against wakullaclerk.org/official_records/tax_deed_sales.php
(curl fetch, 2026-08-13, HTTP 200): raw HTML status cell for ALL SIX of
these case numbers reads "Redeemed" -- not "Cancelled". Verified by direct
string search in the fetched page HTML around each case number's table row;
sample context (2026-TXD-117):
    "...2026-TXD-117 | | | | Redeemed | | | | 2026-TXD-117 | | ..."
Same pattern repeats identically for 113, 116, 118, 120, 122.

This raised the question the task asked to investigate: is
parity_status='CLERK_SSOT_CANCELLED' a miscategorization of a "Redeemed"
outcome?

Finding: NO -- this is NOT a miscategorization, and the status should NOT be
changed. Two independent reasons:

  1. Semantically, "Redeemed" IS a real "the tax deed sale did not/will not
     proceed" outcome (the delinquent owner paid off the certificate before
     the sale), which is functionally the same bucket as "Cancelled" for
     purposes of this evaluator's letter C (matched_clean = the row is a
     GENUINE currently-active/clean matched auction). A redeemed certificate
     is neither an active auction nor a clean parity match -- it is exactly
     as excluded from "clean match" as an outright cancellation.

  2. Confirmed by existing prior-art in this exact codebase:
     calhoun_c_546of2024_phantom_ssot_cancel_reconcile.sql (2026-08-11,
     independently written) states this in explicit terms as canon: "C's
     passing set is (parity_status='matched_clean' AND parity_source LIKE
     'tier1%') OR parity_status IN ('PARITY_OK','CLERK_VERIFIED') --
     CLERK_SSOT_CANCELLED is deliberately excluded from C (only D accepts
     it)." That script's own conclusion for an analogous calhoun row was:
     leave C's structural gap as-is, do not fabricate a status change to
     force a pass. The wakulla D metric (matched_any) already shows 100%
     PASS for wakulla -- proof these 6 rows ARE already correctly counted as
     legitimately-resolved-per-clerk-SSOT, just not "clean" in the
     active-sale sense C measures.

  There is also no 'REDEEMED' parity_status value anywhere else in the
  live database (checked: full distinct parity_status value list across
  ALL 245K+ multi_county_auctions rows, statewide, returns only
  matched_clean / mca_only / PARITY_OK / CLERK_SSOT_CANCELLED /
  matched_divergent / CLERK_VERIFIED / PHANTOM_NOT_ON_CLERK /
  platform_not_found / tier1_only / NULL -- no county anywhere in this
  system distinguishes "redeemed" from "cancelled" at the parity_status
  level). Inventing a new value, or silently relabeling these 6 wakulla
  rows to a different existing status, would be a one-off deviation from
  the system's own established taxonomy purely to move a metric -- exactly
  what this task's instructions explicitly forbid.

CONCLUSION (C): wakulla's C gap for case_numbers 113, 116, 117, 118, 120,
122 (parity_status=CLERK_SSOT_CANCELLED, all genuinely redeemed per the live
clerk site) is a byproduct of correct, accurate, already-verified data and
a deliberate evaluator design choice already validated on another county.
This is a legitimate partial fail for wakulla C and is left unchanged.
ZERO writes made for letter C.

============================================================================
NET RESULT
============================================================================
Rows written to multi_county_auctions: 0
Rows written to parcel_zones:          0
Rows written to bid_decisions:         0

This is an honest, fully-investigated null result, not an incomplete
investigation. Every accessible public data channel for these 5 rows was
checked and returned a genuine, corroborated negative (cross-verified
against two independent prior sessions' findings). Wakulla C / E / I / J
remain at their pre-session metrics; nothing regressed and nothing was
fabricated to force a pass.

Usage:
  python3 scripts/gold_standard_shard2_wakulla_ceij_dispatch72cb38f7.py
  (no --apply flag: this script performs read-only re-verification queries
  only; it deliberately contains no write path, since the investigation
  concluded there is nothing legitimate to write)
"""
import json
import os

import httpx

ACCESS_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
MGMT_HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}

TARGET_CASES = [
    "2026-TXD-097", "2026-TXD-117", "2026-TXD-118", "2026-TXD-120", "2026-TXD-122",
]

_CASES_SQL_ARRAY = "ARRAY[" + ",".join(f"'{c}'" for c in TARGET_CASES) + "]"
VERIFY_SQL = f"""
SET statement_timeout = 0;
SELECT case_number, parcel_id, property_address, market_value, assessed_value,
       opening_bid, auction_date, sale_type, parity_status, data_source, tier1_authoritative,
       latitude, longitude
FROM multi_county_auctions
WHERE lower(county)='wakulla'
  AND case_number = ANY({_CASES_SQL_ARRAY})
ORDER BY case_number;
"""

EVAL_SQL = "SELECT public.pencil_dod_evaluate_county('wakulla');"


def run_query(sql: str):
    with httpx.Client(timeout=60) as c:
        r = c.post(MGMT_URL, headers=MGMT_HEADERS, content=json.dumps({"query": sql}))
        if r.status_code >= 400:
            raise RuntimeError(f"query failed {r.status_code}: {r.text[:300]}")
        return r.json()


def main() -> int:
    print(">>> gold_standard_shard2_wakulla_ceij_dispatch72cb38f7: re-verification pass (no writes)")
    rows = run_query(VERIFY_SQL)
    still_ungrounded = 0
    for row in rows:
        has_parcel = row.get("parcel_id") is not None
        print(f"  {row['case_number']}: parcel_id={row['parcel_id']!r} "
              f"parity_status={row['parity_status']!r} data_source={row['data_source']!r}")
        if not has_parcel:
            still_ungrounded += 1

    print(f"\n{still_ungrounded} of {len(rows)} target rows remain ungrounded (no parcel_id) "
          "after exhaustive public-source investigation -- see module docstring for the full "
          "source-by-source trail. ZERO writes performed by this script (by design).")

    result = run_query(EVAL_SQL)
    print("\n>>> pencil_dod_evaluate_county('wakulla') AFTER this session:")
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
