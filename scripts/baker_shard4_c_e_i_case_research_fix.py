#!/usr/bin/env python3
"""
baker_shard4_c_d_e_i_case_research_fix.py

Gold Standard baker: fix letters C/D/E/I (target >=95%, currently
C/D=20% (3/15), E=33.3% (5/15), I=20% (3/15)).

STEP 0 — Duplicate check (per task instructions)
--------------------------------------------------
Live-queried multi_county_auctions for county=baker, ordered by case_number.
Result: 15 total rows. The apparent "duplicates" the task flagged
(022025CA000117CAAXMX, 022025CA000108CAAXMX, 022026CA000007CAAXMX,
022025CA000124CAAXMX each appearing twice, plus 022025CA000038CAAXMX and
022026CA000018CAAXMX) are NOT duplicate-insert bugs: each pair has the SAME
case_number and auction_date/judgment_amount but a DIFFERENT `id` AND a
DIFFERENT `sale_type` ('foreclosure' vs 'tax_deed'). This is by design in
this pipeline -- calendar_sweep_mca_v3 inserts one row per (case_number,
sale_type) because RealAuction lists the same underlying case under both a
foreclosure auction listing and (separately) a tax-deed listing context.
These are NOT byte-for-byte redundant rows (sale_type differs, and as shown
below the two sibling rows frequently carry DIFFERENT completeness states),
so per the task's own criterion ("you MAY delete an exact duplicate row if
you can prove byte-for-byte redundancy") no delete is performed. This is a
genuine same-case cross-sale_type PAIRING gap, not a dedup bug.

STEP 1 — Live re-verification of the previously-diagnosed gap
-----------------------------------------------------------------
Read scripts/shard8_baker_e_parcel_source_gap_diagnostic.py (prior session,
run 3679) and its 3 follow-on migrations (20260724 purge,
20260724b regression-repurge, 20260725 purge-executed) documenting a real
scraper bug: RealAuction shows the literal anchor text "Property Appraiser"
for cases Baker County hasn't linked a parcel to yet, and an earlier
(pre-fix) version of calendar_sweep_mca_v3 stored that literal string as
parcel_id. Those migrations correctly purged the ghost value back to NULL
for 3 rows (022025CA000108CAAXMX foreclosure, 022025CA000148CAAXMX
tax_deed, 022026CA000018CAAXMX foreclosure) and reset their fabricated
parity_status stamp.

Re-ran the SAME live discovery this session against BOTH
baker.realforeclose.com AND baker.realtaxdeed.com (a second RealAuction
front-end for the same underlying Baker County auction calendar --
previously undocumented in the diagnostic script, discovered this
session). Findings (all VERIFIED live 2026-08-01):

  - baker.realforeclose.com now shows only 2 forward dates (2026-08-13,
    2026-08-20), and 2026-08-13 currently renders 0 AITEM cards on that
    front-end (calendar cache/pagination quirk -- FORECLOSURE auction type
    items are apparently suppressed on the PREVIEW->UPDATE AJAX call for
    that date on this particular front-end).
  - baker.realtaxdeed.com (separate front-end, SAME backend/dates) DOES
    render 2026-08-13's cases: 022025CA000148CAAXMX and 022026CA000007CAAXMX.
    Full card dump:
      022025CA000148CAAXMX: Parcel ID=073S22023800000290,
        Property Address="8696 LAKE GEORGE CIR W", Assessed Value=$273,339.00
      022026CA000007CAAXMX: Parcel ID="Property Appraiser" (empty href,
        genuine source-side placeholder -- Baker has NOT linked a parcel),
        NO Property Address field present at all.
  - 2026-08-20 (both front-ends): 022025CA000038CAAXMX and
    022026CA000018CAAXMX, both WITH real Parcel ID + Property Address +
    Assessed Value, matching what's already in multi_county_auctions for
    their 'foreclosure' sale_type row exactly (same parcel_id, same
    address, same assessed_value -- ruling out a stale/incorrect DB value).
  - 2026-07-16 (both front-ends): 0 cases (past-dated, empty).
  - 022025CA000108CAAXMX, 022025CA000117CAAXMX, 022025CA000124CAAXMX: NOT
    found on ANY visible auction date on EITHER front-end this session.
    These 3 cases have fallen off the live calendar entirely (settled /
    cancelled / removed / rescheduled beyond the currently-published
    window) -- consistent with the prior diagnostic's finding for the same
    3 cases.
  - bakerclerk.com / www.bakerclerk.com: HTTP 403 (Cloudflare WAF),
    re-confirmed this session.
  - civitekflorida.com/ocrs/county/02/ (Baker OCRS): loads (200) but is a
    stateful JSF/PrimeFaces app gated behind an "I Agree" click-through +
    Cloudflare Turnstile human-verification for the actual case search --
    re-confirmed this session, not automatable without CAPTCHA bypass
    (explicitly out of scope).
  - bakerpa.com: HTTP 521 (Cloudflare: origin server unreachable),
    re-confirmed this session (was up 2026-07-29 per a prior session's
    notes, down again now -- intermittent).

CONCLUSION: exactly 2 of the 6 gap case_numbers (022025CA000148CAAXMX,
022026CA000018CAAXMX) have real, source-confirmed parcel_id/address data
available RIGHT NOW -- but only on their 'foreclosure' sale_type row. Their
'tax_deed' sibling row (same case_number, same auction_date, same
judgment_amount/opening_bid, different `id`) is still NULL on
parcel_id/property_address because a scraper run correctly populated the
'foreclosure' row from the live source but the pairing/backfill step that
would copy the same case's parcel data to its 'tax_deed' sibling never
ran (or never existed) for these 2 cases. This is a legitimate same-case
backfill, NOT fabrication: same case_number, same auction_date, same
judgment_amount -- the parcel a case is tied to does not change based on
which sale_type label the row carries.

022026CA000007CAAXMX is genuinely source-blocked (RealAuction's own Parcel
ID anchor literally reads "Property Appraiser" with an empty href --
Baker County has not linked a parcel to this case at bakerpa.com yet).
Per the 20260724b regression-repurge migration's precedent, this string
must NEVER be written to parcel_id. Left NULL on both rows.

022025CA000108CAAXMX, 022025CA000117CAAXMX, 022025CA000124CAAXMX: no
public source reachable this session publishes any address/parcel/owner
for these cases. Left NULL on all 4 rows (2 sale_type rows x these 2 of the
3 -- wait, 3 cases x 2 rows = 6 rows). Reported as still-blocked.

WRITES (this script): for exactly 2 case_numbers
(022025CA000148CAAXMX, 022026CA000018CAAXMX), PATCH the 'tax_deed'
sale_type row's parcel_id, property_address, and assessed_value to match
its 'foreclosure' sibling row (same case, same auction_date, same
judgment_amount -- values independently re-confirmed live against
baker.realtaxdeed.com immediately before writing). latitude/longitude/
city/zip are NOT copied for 148's tax_deed row because the foreclosure
sibling itself has NULL lat/long/city/zip (source doesn't provide them for
that case); for 018 the foreclosure sibling DOES have lat/long, so those
are copied too.

No DDL. No deletes (no proven byte-for-byte duplicate found). No writes
for the 3 unresolved case_numbers or for 022026CA000007CAAXMX.

Env required: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (already in shell env).
"""
import os
import sys

import requests

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# (target tax_deed row id, source foreclosure row id, case_number) for the
# 2 cases with live-reconfirmed real source data on their foreclosure
# sibling but NULL on their tax_deed sibling.
BACKFILL_PAIRS = [
    {
        "case_number": "022025CA000148CAAXMX",
        "target_id": "68f47751-18e4-477f-a88a-068aedfc09c1",  # tax_deed
        "source_id": "a0006bbb-d1fa-425d-8f3b-9329a2072402",  # foreclosure
    },
    {
        "case_number": "022026CA000018CAAXMX",
        "target_id": "ba830663-c3ff-43f4-8c80-1e0825c3e7a6",  # tax_deed
        "source_id": "ed847934-ca00-4dcc-886c-5fa470addb82",  # foreclosure
    },
]

COPY_FIELDS = [
    "parcel_id",
    "property_address",
    "assessed_value",
    "latitude",
    "longitude",
    "city",
    "zip",
    "market_value",
]


def get_row(row_id: str) -> dict:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
        headers=HEADERS,
        params={"select": ",".join(["id", "county"] + COPY_FIELDS), "id": f"eq.{row_id}"},
        timeout=30,
    )
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise RuntimeError(f"row {row_id} not found")
    return rows[0]


def patch_row(row_id: str, payload: dict) -> dict:
    last_exc = None
    for attempt in range(3):
        try:
            r = requests.patch(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                headers=HEADERS,
                params={"id": f"eq.{row_id}", "county": "eq.baker"},
                json=payload,
                timeout=30,
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            last_exc = e
            print(f"  retry {attempt + 1}/3 after error: {e}", file=sys.stderr)
    raise last_exc


def main() -> int:
    total_patched = 0
    for pair in BACKFILL_PAIRS:
        cn = pair["case_number"]
        source = get_row(pair["source_id"])
        target = get_row(pair["target_id"])

        if source.get("county") != "baker" or target.get("county") != "baker":
            print(f"SKIP {cn}: county mismatch, refusing to touch", file=sys.stderr)
            continue

        if not source.get("parcel_id") or not source.get("property_address"):
            print(f"SKIP {cn}: source row missing parcel_id/property_address, nothing to copy", file=sys.stderr)
            continue

        payload = {}
        for field in COPY_FIELDS:
            src_val = source.get(field)
            if src_val is not None and target.get(field) is None:
                payload[field] = src_val

        if not payload:
            print(f"SKIP {cn}: target already populated, no fields to backfill")
            continue

        print(f"PATCH {cn} (tax_deed id={pair['target_id']}): {payload}")
        result = patch_row(pair["target_id"], payload)
        if not result:
            print(f"FAIL {cn}: PATCH returned empty result (0 rows updated) -- RAISE, do not swallow", file=sys.stderr)
            return 1
        total_patched += 1

    print(f"\nTotal rows patched: {total_patched}")

    print("\nStill-blocked case_numbers (no action taken, no public source found):")
    print("  022025CA000108CAAXMX -- not on baker.realforeclose.com or baker.realtaxdeed.com "
          "live calendar (checked 2026-07-16, 2026-08-13, 2026-08-20); bakerclerk.com 403 WAF; "
          "OCRS Turnstile-gated; bakerpa.com HTTP 521 (origin down)")
    print("  022025CA000117CAAXMX -- same as above, not found on either RealAuction front-end")
    print("  022025CA000124CAAXMX -- same as above, not found on either RealAuction front-end")
    print("  022026CA000007CAAXMX -- IS live on baker.realtaxdeed.com 2026-08-13 calendar, but "
          "source's own Parcel ID field is the literal placeholder 'Property Appraiser' with an "
          "empty href and there is NO Property Address field on the card at all -- Baker County "
          "itself has not linked a parcel to this case yet. Writing a value here would repeat the "
          "exact ghost-success pattern purged in migrations 20260724b/20260725. Left NULL.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
