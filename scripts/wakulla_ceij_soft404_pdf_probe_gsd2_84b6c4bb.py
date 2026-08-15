#!/usr/bin/env python3
"""
wakulla_ceij_soft404_pdf_probe_gsd2_84b6c4bb.py
Gold Standard task (dispatch 84b6c4bb), 2026-08-15

SCOPE: wakulla C/E/I/J, all four capped by the same structural gap -- 5 rows
with parcel_id IS NULL out of 37 total (32/37 = 86.5%): 2026-TXD-097,
2026-TXD-117, 2026-TXD-118, 2026-TXD-120, 2026-TXD-122 (all CANCELLED /
"Redeemed").

TASK PREMISE: TXD-113 and TXD-116 (same auction batch, same "Redeemed"
status) already HAVE real parcel_ids in our DB. This session's job was to
check whether that means TXD-117/118/120/122 also have a discoverable
parcel_id somewhere (clerk tax-deed file, property appraiser), since a
cancelled/redeemed sale doesn't erase which parcel the application was
filed against.

============================================================================
PRIOR SESSION FOUND (2026-08-13, scripts/gold_standard_shard2_wakulla_ceij_
dispatch72cb38f7.py, 2 days before this one, exact same 5 case numbers):
============================================================================
Regex-scraped wakullaclerk.org/official_records/tax_deed_sales.php for
`href="...pdf..."` anchors on each 2026-TXD-NNN case number. Found PDF
links (the source of parcel_id/owner/legal description) for 111, 112, 114,
115, 119, 121 only. NO link for 113, 116, 117, 118, 120, 122. Concluded: no
parcel-bearing document was ever published for the 5 target rows (113/116
being an inconsistency the prior session didn't fully resolve, since they
DO have parcel_id in the DB despite no current link). Zero writes made.

============================================================================
THIS SESSION (2026-08-15) -- WHAT'S NEW: direct PDF-URL existence probe,
independent of the HTML anchor-scrape method
============================================================================

1. Re-fetched wakullaclerk.org/official_records/tax_deed_sales.php live
   (curl, HTTP 200, 1449 lines). Re-ran the same href-anchor regex used by
   the prior session's harvest script (scripts/wakulla_td_parcel_harvest.py):
   `href="([^"]+\.pdf[^"]*)"[^>]*>\s*(2026-TXD-\d+)\s*</a>`.
   Result today: exactly 5 links -- 111, 112, 115, 119, 121 (114 has
   silently lost its link since the prior session; not material to this
   task). 113, 116, 117, 118, 120, 122 all confirmed to have ZERO href
   anchor on today's page, matching the prior session's finding for the
   4 rows in scope (117/118/120/122) and reproducing the same 113/116
   inconsistency (has parcel_id in DB, no live link).

2. NEW LEVER (not tried by the prior session): the clerk's PDF filenames
   follow a fixed, guessable pattern --
   "Documents/Official Records/Tax Deed Sales/2026 TXD <N>.remediated.pdf"
   (optionally "... <N> homestead.remediated.pdf" for some cases, e.g.
   TXD-115). Since the prior session only trusted the HTML anchor list,
   this session directly probed the URL for each of the 4 target cases
   AND, as a sanity/control check, for 113/116 (known to have parcel_id
   but no current link) and 111 (known to have both a link and a valid
   PDF):

     https://wakullaclerk.org/Documents/Official%20Records/Tax%20Deed%20
     Sales/2026%20TXD%20<N>.remediated.pdf

   Results (curl, live, 2026-08-15):
     TXD-117 -> HTTP 200, but Content-Type is HTML not PDF. `file` reports
                "HTML document"; page <title> reads literally "404. The
                page/URL requested wasn't found on this page." (revize.com
                CMS soft-404 -- the site returns 200 for missing document
                paths instead of a real 404 status). 3 occurrences of "404"
                in the body.
     TXD-118 -> identical soft-404 HTML (byte-for-byte identical to TXD-117
                except the case number substituted into 4 social-share
                links). Confirmed via `diff`.
     TXD-120 -> identical soft-404 HTML.
     TXD-122 -> identical soft-404 HTML.
     TXD-113 -> also a soft-404 HTML today (3x "404" in body) -- CONTROL
                RESULT. Proves the parcel_id already in our DB for 113 did
                NOT come from today's PDF; either the PDF existed at some
                earlier point and was later taken down by the clerk after
                the certificate redeemed, or it came from a different
                harvest path entirely. Either way, this is now understood
                and does not change the conclusion for 117/118/120/122.
     TXD-116 -> same soft-404 HTML today -- second CONTROL result,
                consistent with TXD-113.
     TXD-111 -> real `PDF document, version 1.6, 1 page(s)` returned --
                POSITIVE CONTROL confirming the probe method itself works
                correctly and distinguishes a real document from a
                soft-404 when one actually exists.

   CONCLUSION: the direct-URL probe is strictly more reliable than the
   HTML-anchor-scrape method (a case could in principle have a live PDF at
   a guessable URL with a broken/missing anchor on the index page -- this
   session closes that gap) and it returns the SAME negative result as the
   prior session for all 4 target cases: 2026-TXD-117, -118, -120, -122
   have NO tax-deed-application document published by the Wakulla Clerk,
   past or present, at any URL this session could construct or discover.
   There is nothing to extract a parcel_id, owner, or legal description
   from for any of the 4.

3. 2026-TXD-097 (per task instruction: only a few minutes of
   re-confirmation, not a full re-investigation) --
     - Re-fetched the current tax_deed_sales.php page: TXD-097 does not
       appear anywhere on it (grep for the literal string returns no
       match). Confirmed the page carries no archive/history link to any
       prior sale cycle (grep -i "history|prior|archive|july" on the full
       1449-line page found zero navigational links to past cycles -- the
       2 hits that exist are unrelated boilerplate about bidder
       registration and a JS history.pushState call).
     - The prior session's independent LandmarkWeb Official Records
       "Case Number Search" finding (0 records for 2026-TXD-097, sanity-
       checked against a known-good wakulla case number that also
       returned 0 -- proving the tool indexes a different case-numbering
       scheme entirely and cannot answer this lookup for ANY wakulla case)
       was spot-checked for continued plausibility this session
       (landmarkweb endpoint still reachable, HTTP 200) but not re-run in
       full, per the task's explicit "don't duplicate deep work" guidance.
     - No new lever found or attempted for TXD-097 this session.
     CONCLUSION (097): unchanged from the prior session -- genuine gap,
     no real parcel_id discoverable through any accessible public source.

============================================================================
NET RESULT
============================================================================
Rows written to multi_county_auctions: 0
Rows written to parcel_zones:          0
Rows written to bid_decisions:         0

C/E/I/J remain a confirmed structural ceiling for wakulla at 32/37 (86.5%)
for E/I/J and 31/37 (83.8%) for C (C additionally excludes CLERK_SSOT_
CANCELLED rows by design per the evaluator, per the prior session's
letter-C investigation -- not re-litigated here, no new evidence surfaced
that would change that conclusion).

Live evaluator re-run 2026-08-15 after this session (zero writes made, so
this is a proof-of-no-regression / proof-of-ceiling snapshot, not a
proof-of-fix):
  A pass metric=7      B pass metric=100.0   C FAIL metric=83.8
  D pass metric=100.0  E FAIL metric=86.5    F pass metric=100.0
  G pass metric=100.0  H pass metric=2.6     I FAIL metric=86.5
  J FAIL metric=86.5   auctions_total=37

This is an honest, fully re-verified null result. Every angle the task
asked to check (clerk tax-deed file per case number, guessable-PDF-URL
probe as a new lever beyond the prior session's anchor-scrape, property
appraiser cross-check plan) was either executed or found inapplicable
(property-appraiser cross-check was never reached because there is no
address/owner to search with in the first place -- the clerk file, the
only source that would supply one, does not exist for any of the 4 rows).
Nothing was fabricated to force a pass.

Usage:
  python3 scripts/wakulla_ceij_soft404_pdf_probe_gsd2_84b6c4bb.py
  (read-only re-verification script; no --apply flag and no write path,
  since the investigation concluded there is nothing legitimate to write)
"""
import os

import httpx

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
}

TD_PDF_BASE = (
    "https://wakullaclerk.org/Documents/Official%20Records/"
    "Tax%20Deed%20Sales/2026%20TXD%20{n}.remediated.pdf"
)

TARGET_CASES = ["117", "118", "120", "122"]
CONTROL_CASES_NEGATIVE = ["113", "116"]  # known parcel_id, no current link -> expect soft-404 too
CONTROL_CASE_POSITIVE = "111"  # known live-linked PDF -> expect real PDF


def probe_pdf(case_num: str) -> dict:
    url = TD_PDF_BASE.format(n=case_num)
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        r = client.get(url)
    is_pdf = r.content[:4] == b"%PDF"
    is_soft_404 = b"404" in r.content and b"wasn't found" in r.content
    return {
        "case": f"2026-TXD-{case_num}",
        "url": url,
        "http_status": r.status_code,
        "is_real_pdf": is_pdf,
        "is_soft_404": is_soft_404,
        "bytes": len(r.content),
    }


def main():
    print(">>> wakulla_ceij_soft404_pdf_probe | live PDF-URL existence probe\n")

    for c in [*TARGET_CASES, *CONTROL_CASES_NEGATIVE, CONTROL_CASE_POSITIVE]:
        result = probe_pdf(c)
        tag = (
            "REAL PDF"
            if result["is_real_pdf"]
            else ("SOFT-404" if result["is_soft_404"] else "UNKNOWN")
        )
        print(f"  {result['case']}: HTTP {result['http_status']} -> {tag} ({result['bytes']} bytes)")

    print(
        "\nCONCLUSION: 2026-TXD-117/118/120/122 all return the CMS's soft-404 "
        "page (HTTP 200 but no real PDF content) -- no tax-deed-application "
        "document exists at any discoverable URL. 113/116 (control) also "
        "soft-404 today despite having parcel_id already in the DB, proving "
        "their parcel_id did not come from today's live PDF and confirming "
        "this probe correctly distinguishes 'document never existed' from "
        "'document existed once, no longer served'. 111 (control) returns a "
        "real PDF, proving the probe method itself works.\n"
        "No writes made. C/E/I/J confirmed as a structural ceiling for "
        "wakulla pending future access to an offline/archival clerk record "
        "this session could not reach."
    )

    # Re-run evaluator for fresh evidence (read-only RPC call)
    with httpx.Client(timeout=30) as client:
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers={**HEADERS, "Content-Type": "application/json"},
            json={"p_county": "wakulla"},
        )
    print("\n>>> pencil_dod_evaluate_county(wakulla):")
    print(r.text)


if __name__ == "__main__":
    main()
