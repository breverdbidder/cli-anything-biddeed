"""investigate+fix: suwannee C/D/E/I/J stuck at 35/56 (62.5%) -- clerk_ssot
case_number-format duplicate rows, 2026-08-11 session.

ROOT CAUSE (VERIFIED live via PostgREST queries against multi_county_auctions,
2026-08-11): NOT one shared blocker across 21 rows -- two DISJOINT 21-row
groups (union = all 56, intersection = 14 clean rows) each failing a
different half of the letters:

  Group A (21 rows, parity_status='PARITY_OK', parity_source=
  'suwannee_clerk_tax_deed', data_source=NULL, created_at ~2026-08-10T14:37-38
  UTC): case_number in the FULL clerk PDF format e.g. "4680/2019-2108".
  parcel_id/property_address/lat/long/assessed_value all NULL.
  -> passes C/D (matched_clean/matched_any, parity_status='PARITY_OK' is
     evaluator-recognized per 20260810_gold_standard_shard3_lake_clerk_ssot_
     cd_recognition.sql), but FAILS E (no parcel_id), I (no card fields),
     J (bid_decisions.case_number lookup never matches the long format).

  Group B (21 rows, parity_status='PHANTOM_NOT_ON_CLERK', parity_source=
  'tier1:suwannee_shard4_c40bb245_realtaxdeed_ajax_all_dates', data_source=
  'calendar_sweep_mca_v3', created_at 2026-08-01T06:13 UTC): case_number in
  the SHORT format e.g. "4680" (matches realtaxdeed's own numbering).
  parcel_id/geo/assessed_value all populated; bid_decisions already has a
  complete row (arv, max_bid, ml_score, all 5 factors keys) keyed on the
  SAME short case_number.
  -> passes E/I/J but FAILS C/D because clerk_ssot flagged it PHANTOM_NOT_ON_
     CLERK (correctly, from the parity script's point of view: it never
     found a case_number match for the short form in the clerk PDF's
     case list, because the clerk PDF's format is long).

MECHANISM (confirmed by reading scripts/clerk_ssot/run_parity.py lines
148-213): diff_and_reconcile() keys `ours_by_case` on the raw case_number
string already in the DB, and looks up ssot_row['case_number'] (long format,
per scripts/clerk_ssot/parsers/suwannee.py's own docstring/regex CASE_RE)
against it with an EXACT match. Because the pre-existing suwannee tax_deed
rows were seeded in the short format by an earlier realtaxdeed AJAX sweep
(calendar_sweep_mca_v3, 2026-08-01), every one of the 21 long-format clerk
case numbers misses `ours_by_case` and is treated as `missing_from_ours` ->
a brand-new sparse row gets INSERTed (case_number, sale_type, auction_date,
auction_status, parity_status, parity_source only -- see INSERT at line
180-181). The pre-existing short-format row for the same real-world auction
is never touched by that INSERT, and simultaneously gets swept into
`phantom_in_ours` (it's not a key in ssot_by_case either) and flagged
PHANTOM_NOT_ON_CLERK. Net effect: every matched auction on the 2026-09-03
suwannee sale date got split into 2 DB rows, 21 of 21 in this window.

VERIFIED PAIRING: all 21 Group-A case numbers, stripped of their
"/YYYY-NNNN" clerk suffix, exactly match 21 Group-B case numbers 1:1 (zero
collisions, zero leftovers -- see /tmp/pairs.json built this session).

FIX APPLIED THIS SESSION (PostgREST only, no Management API / raw SQL used):
  1. PATCH the 21 Group-B (enriched) rows: parity_status='PARITY_OK',
     parity_source='suwannee_clerk_tax_deed' -- i.e. recognize that the
     clerk PDF DOES list this case (just under its long case_number), so
     the short-format enriched row is in fact clerk-confirmed clean, not a
     phantom. Zero data mutation to parcel_id/geo/bid_decisions linkage
     (case_number left untouched on purpose -- bid_decisions and
     v_zoning_gold_standard_card both key on the short format; renaming
     would have broken J and I again).
  2. DELETE the 21 Group-A (orphan) rows by verified `id` (see
     /tmp/orphan_ids.txt built this session) -- each one is a confirmed
     duplicate shell of a Group-B row that already carries every real field
     the orphan lacks. No FK references multi_county_auctions.id in any
     migration (grepped supabase/migrations/*.sql); clerk_ssot_sale_rows /
     clerk_parity_results key on (county_slug, case_number, sale_type), not
     on multi_county_auctions.id, so deleting these ids is safe.

RESULT (VERIFIED live via pencil_dod_evaluate_county('suwannee'), run
immediately after each step this session):
  before:  auctions_total=56  C=62.5 D=62.5 E=62.5 I=62.5(35/56) J=62.5
  after PATCH only (orphans still present): auctions_total=56
           C=100.0(56) D=100.0(56) E=62.5(35/56, unchanged) I=62.5 J=62.5
  after DELETE (final): auctions_total=35
           C=100.0(35/35) D=100.0 E=100.0(35/35) I=100.0(35/35) J=100.0(35/35)
  All 10 letters (A-J) PASS for suwannee as of this session.

RECURRENCE RISK -- NOT CLOSED, FLAGGED HONESTLY:
.github/workflows/clerk-ssot-parity.yml runs scripts/clerk_ssot/run_parity.py
daily at 09:00 UTC (cron "0 9 * * *") against suwannee (and 8 other clerk_
ssot counties: brevard, gadsden, highlands, okeechobee, st_johns, union,
wakulla, lake). The underlying bug -- exact-string case_number matching in
diff_and_reconcile() with no short/long-format normalization -- is NOT fixed
by this script. It only cleaned up the data this bug already produced. On
its next scheduled run, run_parity.py will re-diff suwannee's tax_deed PDF
against the now-clean 35 rows, find the same 21 long-format case numbers
missing again (because the DB still stores them in short format), and
RE-INSERT the same 21 orphan rows, regressing C/D/E/I/J back to 62.5%
within ~24h of this fix.

Fixing the root cause in run_parity.py (e.g. normalizing case_number to a
canonical form before the dict-key comparison, or teaching the suwannee
parser to also emit/accept the short numeric prefix) is OUT OF SCOPE for
this session: it touches shared matching logic used by 8 other counties'
parity runs and needs a per-county format survey before a generic fix can
be applied safely -- that is "complex" scope per CLAUDE.md (6+ files /
cross-cutting change), not a bounded single-session fix. Logged here as the
concrete next-session priority for the suwannee/clerk_ssot lane.

Zero destructive SQL beyond the verified 21-id DELETE above (each id
individually confirmed as a duplicate before deletion, per /tmp/pairs.json
built and printed in-session). No Management API / SUPABASE_ACCESS_TOKEN
used for the fix itself (only PostgREST with SUPABASE_SERVICE_ROLE_KEY).
This file is investigation documentation + a reproducible pairing query;
it does not re-run the fix (already applied and verified live) and is safe
to execute read-only for future audits.
"""
import json
import os
import subprocess


def fetch_suwannee_rows():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    fields = (
        "id,case_number,parcel_id,sale_type,auction_date,auction_status,"
        "parity_status,parity_source,bcpao_enriched,property_address,"
        "latitude,longitude,assessed_value,data_source,created_at"
    )
    r = subprocess.run(
        [
            "curl", "-s",
            f"{url}/rest/v1/multi_county_auctions?county=eq.suwannee&select={fields}",
            "-H", f"apikey: {key}",
            "-H", f"Authorization: Bearer {key}",
        ],
        capture_output=True, text=True, check=True,
    )
    return json.loads(r.stdout)


def find_duplicate_pairs(rows):
    """Read-only reproduction of this session's pairing logic, for future
    audits. Returns [] once the dedup has been applied (expected state)."""
    missing = {r["case_number"]: r for r in rows if not r.get("parcel_id")}
    present = {
        r["case_number"]: r
        for r in rows
        if r.get("parcel_id") and r.get("auction_date") == "2026-09-03"
    }

    def short(cn):
        return cn.split("/")[0]

    pairs = []
    for cn_long, r_long in missing.items():
        s = short(cn_long)
        if s in present:
            pairs.append(
                {
                    "orphan_id": r_long["id"],
                    "enriched_id": present[s]["id"],
                    "short_case": s,
                    "long_case": cn_long,
                }
            )
    return pairs


if __name__ == "__main__":
    rows = fetch_suwannee_rows()
    print(f"suwannee rows: {len(rows)}")
    pairs = find_duplicate_pairs(rows)
    if pairs:
        print(f"WARNING: {len(pairs)} duplicate pairs detected (regression -- "
              f"run_parity.py has likely re-run since the 2026-08-11 fix). "
              f"See docstring RECURRENCE RISK section for the real fix.")
        for p in pairs:
            print(p)
    else:
        print("No duplicate pairs found -- dedup fix from 2026-08-11 is holding.")
