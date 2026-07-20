# Gold Standard shard-11 gadsden — dispatch 52bf028c, loop run 5361, item gadsden_E_901CA

## Result: 8/10 unchanged — E stays FAIL 91.3%, genuinely blocked with NEW evidence found and documented

| Letter | Before | After | Notes |
|---|---|---|---|
| A | PASS fc=16 td=7 | PASS fc=16 td=7 | Unchanged |
| B | PASS 100.0 | PASS 100.0 | Unchanged |
| C | PASS 95.7 | PASS 95.7 | Unchanged |
| D | PASS 95.7 | PASS 95.7 | Unchanged |
| **E** | **FAIL 91.3 (21/23)** | **FAIL 91.3 (21/23)** | **Unchanged — new real evidence found, still genuinely ambiguous, no write made** |
| F | PASS 100.0 | PASS 100.0 | Unchanged |
| G | PASS 100.0 | PASS 100.0 | Unchanged |
| H | PASS (SLA 48h) | PASS (SLA 48h) | Wall-clock drift only (0.1h vs prior session's 28.9h), no writes |
| I | FAIL 56.5 (13/23) | FAIL 56.5 (13/23) | Unchanged — capped by E per prior sessions' analysis |
| J | PASS 100.0 | PASS 100.0 | Unchanged |

No metric moved this session. This is an honest, evidence-backed non-result, not a failure to try.

## What was tried (genuinely new angles, not repeats of prior sessions' dead ends)

### 1. CourtScribePublicInquiry — a real, previously-undiscovered docket search portal
`gadsdenclerk.com/CourtScribePublicInquiry/` is a **separate system from the sale-sheet**
(`Foreclosures_files/sheet001.htm`) that all 4+ prior sessions used, and separate from
qpublic/gadsdencountyfl.gov (both confirmed WAF-blocked, not re-tried per instructions). It
returns HTTP 200 with a standard browser User-Agent and exposes a working AJAX search API:

- `GET .../CourtScribe/SearchClerk?input=CASE_NUMBER=25000901CA` → returns case metadata
  including internal `CaseDataID=726040` and UCN `202025CA000901AXXXCX`.
- `GET .../CourtScribe/GetCaseDetailsPI?CaseDataID=726040` → returns the full 32-entry docket
  as a semicolon-delimited payload, including an HTML fragment (`DocketHTML`) with `ShowDocument(ID)`
  links to individual filed PDFs.
- `GET .../CourtScribe/GetDocumentPDF?DocketID=<id>` → serves the actual scanned PDF, publicly,
  no auth required.

This is a genuinely new, live, working source no prior gadsden session (4+) had found or used.

### 2. Fetched and read the actual court documents (not just docket titles)
Three independent filings were pulled and OCR'd via page-render + visual read (pymupdf, no
tesseract available in sandbox — used direct visual reading of rendered PNG pages instead):

- **Notice of Lis Pendens** (filed 11/21/2025, DocketID 12604730, 2 pages) — full metes-and-bounds
  legal description: "PARCEL 3: A parcel of land lying in the Southeast Quarter of Section 26,
  Township 2 North, Range 5 West, Gadsden County, Florida, as described in Official Record Book
  317, Page 772... commence at the SW corner of the SW 1/4 of the SE 1/4 of Section 26... [full
  traverse to a 200ft x 217.8ft POB rectangle]."
- **Final Judgment of Foreclosure** (recorded OR Bk 984 Pg 974-977, 06/11/2026, DocketID 12703263,
  4 pages) — repeats the identical PARCEL 3 legal description verbatim; independently confirms
  judgment total **$56,245.27** (exact match to `multi_county_auctions.judgment_amount`) and sale
  date **September 10, 2026** (exact match to `auction_date`), which cross-validates this is
  unambiguously the correct case/parties, just not the correct one-of-two parcel.
  Interest rate 8.44%, Judge David Frank, plaintiff attorney James C. Thompson — all consistent.
- **Verified Complaint + recorded Mortgage (Exhibit A)** (OR Bk 949 Pg 572-585, DocketID 12604724,
  21 pages) — the *mortgage instrument's own* Exhibit A (page 14 of 14 of the mortgage) repeats
  the identical PARCEL 3 legal description a third time. No parcel ID, tax account number, or
  street address appears anywhere in the mortgage, complaint, lis pendens, or judgment.

### 3. Closed-traverse verification (new analytical method, not tried by prior sessions)
Computed the metes-and-bounds traverse programmatically: N 217.8 ft, S89°40'E 200.00 ft,
S 217.8 ft, N89°40'W 200.00 ft. Closure error = 0.0000 ft (mathematically valid closed parcel).
Shoelace-formula area = 43,559.26 sq ft = **1.0000 acre exactly** — which matches
`fl_parcels.lnd_sqfoot = 43560` for **both** candidate parcels
(`3-26-2N-5W-0000-00424-0500` and `...-1000`) exactly. This confirms the legal description is
internally consistent and real, but does **not** disambiguate between the two candidates, since
both are identically-sized adjacent lots.

Additionally computed the haversine distance between the two candidates' centroids: **203.3 ft**
— consistent with them being adjacent same-subdivision lots off the same OR Book 317 Page 772
plat (the traverse's own east-west leg is 200.00 ft), reinforcing that this is a genuine
same-plat ambiguity, not a data error.

### 4. Firecrawl credits re-checked (per item instruction #2)
`GET https://api.firecrawl.dev/v1/team/credit-usage` → `remaining_credits: 0` (VERIFIED,
re-checked live this session, unchanged from the 2026-07-19 session's finding — credits have not
refilled).

### 5. Alternate appraiser vendor path (per item instruction #3)
- `gadsdenpa.com` (the real official appraiser domain per web search) → **HTTP 403**, still
  WAF-blocked, same as qpublic/gadsdencountyfl.gov.
- `gadsdencountypropertyappraiser.org` → HTTP 200, but on inspection is confirmed to be an
  **unofficial WordPress ad/lead-gen imitation site** (google-adsense-account meta tag present,
  "Property Search Pro" WP plugin, generic templated content) — not a real data source. Not used.

### 6. Official Records book/page search (genuinely new attempt, confirmed dead end)
`gadsdenclerk.com/publicinquiry/Search.aspx?Type=Document` (distinct ASP.NET WebForm portal from
CourtScribe, would in principle let us pull the actual OR Book 317 Page 772 deed that defines
ALL parcels in this subdivision, which is the one document that could show which numbered parcel
corresponds to which fl_parcels ID) returns HTTP 200 and is reachable, but requires a client-side
`__doPostBack` event with ASP.NET `__VIEWSTATE` to actually execute a Book/Page search — plain
GET query-string parameters (`?Book=317&Page=772`) do not trigger a server-side search. Not
reachable via curl/urllib in this sandbox without a JS-executing browser. Confirmed via direct
test, not assumed.

## Why E stays FAIL: the actual, honest reason
Both candidate parcels are legitimate 1-acre unincorporated lots owned by "RAMONS CONSTRUCTION
SERVICES L" on Ridgewood Rd, ~203 ft apart, functionally identical in every field `fl_parcels`
exposes (same owner, same land value $6,200, same lot size 43,560 sqft, same 2024 sale price
$50,000, same zip). The court record — now pulled directly from 3 independent real filings
(lis pendens, final judgment, the mortgage itself) — confirms the correct case/defendant/amount
beyond doubt, but the legal description it cites ("Parcel 3" of OR Book 317 Page 772) requires
the underlying **plat/deed** to resolve which of the two fl_parcels IDs is "Parcel 3" versus
whichever other parcel number the other lot carries. That deed is not retrievable through any
channel reachable from this sandbox this session. Guessing between the two would be exactly the
kind of fabrication this project's B/F and lake-G incidents warn against. Per BLANK > WRONG,
declining.

## Live evaluation JSON — BEFORE (session start, 2026-07-20)
```json
{"A":{"pass":true,"detail":"fc=16 td=7","metric":7},"B":{"pass":true,"detail":"verified=1 closed_sold=1","metric":100.0},"C":{"pass":true,"detail":"matched_clean=22","metric":95.7},"D":{"pass":true,"detail":"matched_any=22","metric":95.7},"E":{"pass":false,"detail":"parcel_linked=21","metric":91.3},"F":{"pass":true,"detail":"tier1_sold=1 closed_sold=1","metric":100.0},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":0.1},"I":{"pass":false,"detail":"card_complete=13 of 23","metric":56.5},"J":{"pass":true,"detail":"deal_complete=23 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"gadsden","V2_LITMUS":null,"auctions_total":23}
```

## Live evaluation JSON — AFTER (session end, same session, no writes made)
Identical to BEFORE — confirmed via re-run of `pencil_dod_evaluate_county('gadsden')` at session
end. No DB write was made for `multi_county_auctions` case `25000901CA`; `parcel_id` remains NULL.

## SQL / endpoints used
```
GET  ${SUPABASE_URL}/rest/v1/multi_county_auctions?case_number=eq.25000901CA&county=eq.gadsden&select=*
GET  ${SUPABASE_URL}/rest/v1/fl_parcels?co_no=eq.30&own_name=ilike.*RAMON*&select=*
POST ${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county  body {"p_county":"gadsden"}  (run twice, before/after, identical)
POST ${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit  (1 row, letter=E, survived=true, id=8060)
GET  https://www.gadsdenclerk.com/CourtScribePublicInquiry/CourtScribe/SearchClerk?input=CASE_NUMBER=25000901CA
GET  https://www.gadsdenclerk.com/CourtScribePublicInquiry/CourtScribe/GetCaseDetailsPI?CaseDataID=726040
GET  https://www.gadsdenclerk.com/CourtScribePublicInquiry/CourtScribe/GetDocumentPDF?DocketID=12604730  (Lis Pendens)
GET  https://www.gadsdenclerk.com/CourtScribePublicInquiry/CourtScribe/GetDocumentPDF?DocketID=12703263  (Final Judgment)
GET  https://www.gadsdenclerk.com/CourtScribePublicInquiry/CourtScribe/GetDocumentPDF?DocketID=12604724  (Verified Complaint + Mortgage Exhibit A)
GET  https://api.firecrawl.dev/v1/team/credit-usage
```

## Residual gaps / recommendation for next session
- **E (2 rows)**: `25000901CA` still ambiguous between the 2 Ridgewood Rd parcels — the ONE
  remaining lead is OR Book 317 Page 772 (the plat/deed that created "Parcel 3"), retrievable in
  principle via `gadsdenclerk.com/publicinquiry/Search.aspx?Type=Document` but that portal
  requires a JS-executing browser (ASP.NET postback + VIEWSTATE) not available in this sandbox.
  A future session with real browser automation (e.g. a working headless-Chromium tool) could
  plausibly close this by pulling that one deed. The other E gap row (per the dispatch context,
  gadsden has 2 E-gap rows total) was not investigated this session — scope was limited to
  `gadsden_E_901CA` per the assigned item.
- **I**: still structurally capped below 95% until E closes (unchanged analysis from the prior
  2026-07-19 session, re-confirmed, not re-litigated this session).
- Do not re-attempt qpublic.schneidercorp.com or gadsdencountyfl.gov via plain fetch (confirmed
  WAF-blocked 3+ times now across sessions). Do not re-attempt gadsdenpa.com (also 403). Do not
  use gadsdencountypropertyappraiser.org (confirmed unofficial ad site).

## Honesty notes
- All claims in this report are VERIFIED (live HTTP responses pasted/observed this session)
  except the traverse-math interpretation, which is INFERRED from the metes-and-bounds text with
  the reasoning shown (standard PLSS bearing convention, closure-error check as the validity
  proof).
- No parcel_id, address, or geo value was written or guessed for `25000901CA`. The row is
  reported as still-NULL, unchanged.
- H's metric drifted from the prior session's 28.9 to 0.1 purely from `last_seen_at` wall-clock
  proximity to session start — not a write made this session, consistent with the pattern
  documented in the prior 2026-07-19 report.

dispatch_id: 52bf028c-78fe-49ad-ae77-284c02a1f201
audit_row_id: 8060
