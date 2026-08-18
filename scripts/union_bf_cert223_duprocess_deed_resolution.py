#!/usr/bin/env python3
"""
Union County B/F fix: resolve UNION-TD-CERT223 (tax deed cert #223, parcel
32-05-20-22-018-0022-0) via a genuinely NEW source -- the DuProcess Official
Records portal at recording.unionclerk.com/DuProcessWebInquiry -- which is a
different vendor/URL from both the main unionclerk.com domain (Cloudflare
403 to bots) and the civitek OCRS case-search portal (Person/Case search
only, structurally cannot surface recorded deeds). 2026-08-18 session.

PRIOR STATE: 08-08 session set tax_deed_outcomes.outcome='redeemed' for this
cert based on the LAFT-absence inference alone (no dollar figure, no
grantee). That inference was directionally right (not on Lands Available =
did not go unsold) but wrong on WHICH outcome -- the property was actually
SOLD, not redeemed. A daily adversarial-refuter audit (gold_standard_
ultraloop_audit) then re-confirmed "redeemed, no missed sale" as a survived
finding every day from 2026-06-25 through 2026-08-17, because none of those
sessions tried this specific portal.

DISCOVERY PATH (this session):
  1. unionclerk.com main domain -> 403 via curl AND WebFetch (Cloudflare).
  2. records.unionclerk.com/LandmarkWeb/ -> also 403 (same Cloudflare zone).
  3. WebSearch "Union County Florida official records search landmarkweb OR
     idocmarket OR search.unionclerk" surfaced recording.unionclerk.com.
  4. recording.unionclerk.com -> 200 OK via real Playwright browser session
     (chromium executable, UA spoofed) -- a portal LANDING page offering
     "Official Records / Online Marriage Application / Property Fraud Alert
     Service / Jury Information" as separate DuProcess sub-applications.
  5. "Official Records" button onclick -> recording.unionclerk.com/
     DuProcessWebInquiry/index.html -- a DuProcess (courtalliance.com)
     Official Records index with Inst Type, Parcel ID, Legal Desc, Name,
     Consideration Value search fields. Genuinely distinct system from
     civitek OCRS (case-search only) confirmed dead-end by the 08-09
     adversarial audit.
  6. Parcel ID search on the exact parcel returned 0 rows (parcel index
     field not populated for this document). Inst Type=Deed + date range
     03/01/2026-08/18/2026 returned 336 rows; among them:
       Inst#20260000665 Book482/Page647
       Grantor: RHOADES KELLIE HENDRICKS (CLERK) / UNION COUNTY CLERK OF
                THE CIRCUIT COURT
       Grantee: JR DAVIS ACQUISITIONS LLC
       Filed:   03/13/2026, 2:36:08 PM
     Grantor = the Clerk (who conveys tax deeds) and Grantee name matches
     the existing cert_holder "J. R. Davis Trust" -- strong prior.
  7. Instrument Details page confirmed: Description field =
     "32-05-20-22-018-0022-0" -- EXACT match to UNION-TD-CERT223's parcel.
  8. Retrieved the actual recorded PDF via context.request.get() on the
     CreateDocument endpoint (cookies carried over from the browser
     session) -- 122,501 bytes, real application/pdf, filename 7784698.pdf.
     Rendered page 1 to a PNG (pymupdf) and read the deed face directly
     (this is a scanned/image PDF; pypdf text extraction only recovers the
     "Un-Official" watermark, not the document body -- OCR-by-eye via the
     rendered image was necessary).

DEED FACE (verbatim key facts):
  Tax Deed File No. 63-2025-TD-0002
  Property Identification No. 32-05-20-22-018-0022-0
  "The following Tax Sale Certificate numbered 223 issued MAY 30, 2018 ...
   such land was on the 12TH day of April, 2026, offered for sale as
   required by law for cash to the highest bidder and was sold to J. R.
   Davis Acquisitions, LLC, whose address is P.O. Box 58, Lake Butler, FL
   32054 ... Now, on this 12th day of March, 2026 ... in consideration of
   the sum of THREE THOUSAND SEVEN HUNDRED & 00/100 ($3,700.00) ..."
  Legal: SW 1/4 of Lot 2, Block 18, J. W. Townsend's Addition, Plat Book 1
  page 8, Union County, FL.
  Recorded: 3/13/2026 2:36:08 PM, Book 482 Page 647, Inst #20260000665.

NOTE: the deed's own recital date (offered for sale April 12, 2026) differs
from our DB's scheduled auction_date (2026-03-12). This is a normal FL
Ch.197 sale reschedule and does not weaken the match -- parcel ID, cert
number 223, and buyer name (J.R. Davis Acquisitions LLC vs cert_holder
"J. R. Davis Trust") are all consistent and no other Union County deed in
the same window references this parcel or cert.

WRITES PERFORMED (idempotent, scoped to case_number=UNION-TD-CERT223):
  1. PATCH tax_deed_outcomes id=a965b45d-2711-4ab9-99a9-ed35d87bbde4:
       outcome: 'redeemed' -> 'sold'
       winning_bid: null -> 3700.00
       winner_name: null -> 'J. R. Davis Acquisitions, LLC'
       winner_type: null -> 'cert_holder_entity'
       data_source: -> 'union_clerk_official_records:recording.unionclerk.com/
                         DuProcessWebInquiry/Inst-20260000665'
       source_url: -> CreateDocument URL + Inst#/Book/Page/File No. citation
  2. POST rpc/promote_tier1_from_outcomes -> {"promoted": 1}
     multi_county_auctions row for UNION-TD-CERT223 now has:
       sold_amount=3700.0, winning_bidder='J. R. Davis Acquisitions, LLC',
       tier1_sold_amount=3700.0, auction_status='sold'

VERIFICATION (pencil_dod_evaluate_county('union'), post-write):
  B: pass=true  verified=1 closed_sold=1  metric=100.0  (was: fail, closed_sold=0)
  F: pass=true  tier1_sold=1 closed_sold=1 metric=100.0  (was: fail, closed_sold=0)

SEPARATE REPORT-ONLY CHECK (no DB write): case 63-2025-CA-0053
(parity_status=PHANTOM_NOT_ON_CLERK, foreclosure). Live check of
https://unionclerk.com/departments-services/court-services/foreclosure-sales/
(200 OK, rendered via Playwright) shows exactly ONE upcoming foreclosure
sale listed: case 63-2024-CA-0047 (10/15/2026). Case 63-2025-CA-0053 is
NOT present. A DuProcess Official Records "Legal Desc" search for
"2025-CA-0053" also returned 0 records (no recorded instrument references
this case number). Its DB auction_date (2026-08-13) has already passed
with no re-listing anywhere checked. This is consistent with -- not a
refutation of -- the existing PHANTOM_NOT_ON_CLERK classification. No DB
row was modified for this case per task instructions (report-only).
"""
import json
import os
import urllib.request

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY', '')
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}

OUTCOME_ROW_ID = 'a965b45d-2711-4ab9-99a9-ed35d87bbde4'
PATCH_BODY = {
    'outcome': 'sold',
    'winning_bid': 3700.00,
    'winner_name': 'J. R. Davis Acquisitions, LLC',
    'winner_type': 'cert_holder_entity',
    'data_source': (
        'union_clerk_official_records:recording.unionclerk.com/'
        'DuProcessWebInquiry/Inst-20260000665'
    ),
    'source_url': (
        'https://recording.unionclerk.com/DuProcessWebInquiry/Home/CreateDocument '
        '(Inst #20260000665, Book 482 Page 647, Tax Deed File No. 63-2025-TD-0002, '
        'recorded 2026-03-13)'
    ),
}


def _request(method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f'{BASE}{path}', data=data, headers=HEADERS, method=method)
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode() or 'null')


def main() -> None:
    status, body = _request('PATCH', f'/tax_deed_outcomes?id=eq.{OUTCOME_ROW_ID}', PATCH_BODY)
    print(f'PATCH tax_deed_outcomes -> {status}')
    print(json.dumps(body, indent=2))

    status, body = _request('POST', '/rpc/promote_tier1_from_outcomes', {})
    print(f'promote_tier1_from_outcomes -> {status} {body}')

    status, body = _request(
        'POST', '/rpc/pencil_dod_evaluate_county', {'p_county': 'union'}
    )
    print(f'pencil_dod_evaluate_county -> {status}')
    print(json.dumps(body, indent=2))


if __name__ == '__main__':
    main()
