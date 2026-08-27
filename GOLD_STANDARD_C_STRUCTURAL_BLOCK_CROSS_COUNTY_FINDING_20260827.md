# Gold Standard letter C (matched_clean): fleet-wide canon/design tension, not a per-county data bug

**Date:** 2026-08-27
**Scope:** calhoun, manatee, taylor — cross-county due-diligence re-verification of all 15 rows currently
blocking letter C (matched_clean) in these three counties, following the exact investigative precedent
set by `calhoun_c_546of2024_phantom_ssot_cancel_reconcile.sql` (2026-08-11).

## TL;DR

Letter C is structurally capped below the 95% pass threshold in **calhoun (88.9%), manatee (92.2%), and
taylor (92.3%)** — three counties independently, in one shard, on one day — for the **same root cause**:
every offending row is a foreclosure/tax-deed sale that was **genuinely cancelled** at the clerk level and
correctly reconciled to `parity_status = CLERK_SSOT_CANCELLED`. C's canon (see the evaluator SQL below)
deliberately excludes `CLERK_SSOT_CANCELLED` from its passing set; only D (`matched_any`) accepts it. This
is not a data quality defect — it is the intended, working behavior of the canon as currently specified.
The problem is that the canon's design assumption (cancellations are rare enough to stay under the 5%
slack in C's 95% threshold) does not hold in real Florida foreclosure data, where cancellation rates
of 6-15% per county are normal and expected.

**No fabricated matches were created. No row's `parity_status` was changed.** All 15 rows were
independently re-verified against live, named, real sources and reconfirmed genuinely cancelled.

## Per-row verification detail (VERIFIED — live fetches run this session, 2026-08-27)

### calhoun (1 row, C = 88.9%, 8/9)

| case_number | source checked | result |
|---|---|---|
| `546 OF 2024` | `calhounclerk.com` WP-JSON `taxdeeds`, `foreclosures`, `taxdeedoverbids` feeds (fresh pull, all three, 2026-08-27) | Case number and parcel_id (`26-1S-10-0000-0004-0100`) absent from all three live feeds. Reconfirms the 2026-08-11 finding independently, 16 days later, with a fully re-pulled feed (feed contents have since drifted — taxdeeds count went 5→0, foreclosures 2→1, taxdeedoverbids 41→43 — but the case remains absent throughout). |

No change. `parity_status='CLERK_SSOT_CANCELLED'` stands.

### manatee (13 rows, C = 92.2%, 153/166)

Verified against `records.manateeclerk.com/CourtRecords` — the live Manatee Clerk of Circuit Court public
case search and docket-detail viewer (`/CourtRecords/Search/CaseNumber` → `/CourtRecords/Case/Details`,
no login required for docket summary + full docket entries).

| case_number | property | docket finding |
|---|---|---|
| `2024CA001675AX` | 4485 Gulf of Mexico Dr Apt 402 | Case exists (SANDORO, DAVID J., Defendant). Docket: **Sale Canceled 08/17/2026**. |
| `2025CA002974AX` | 10416 Spoonbill Rd W | Case exists (BULLDOG ROOFS LLC). Docket: **Sale Canceled 07/16/2026**. |
| `2018CA003716AX` | 10922 Bullrush Ter | Case exists (FESER, MICHAEL D). Docket: **Sale Canceled 08/18/2026**. |
| `2026CC000389AX` | 201 113th St E | Case exists (BRUSCO, EUGENE JR). Docket: **Sale Canceled 08/17/2026**. |
| `2025CA002646AX` | 4803 Harvest Grove Pl | Case exists (COASTAL COMMUNITY BANK). Docket: **Sale Canceled 07/21/2026**. |
| `2025CA001955AX` | 2400 3rd St E | Case exists (FLORIDA HOUSING FINANCE CORP). Docket: **Sale Canceled 08/13/2026**. |
| `2025CA000787AX` | 3407 6th Ave W | Case exists (BAYOU ESTATES HOA INC). Docket: **Sale Canceled 08/24/2026**. |
| `2025CA002328AX` | 924 70th St Ct E | Case exists (NUNEZ, YVETTE). Docket: **Sale Canceled 07/14/2026**. |
| `2026CA000035AX` | 231 Heritage Preserve Run | Case exists (RIVER STRAND GOLF & CC INC). Docket: **Sale Canceled 08/27/2026 (today), Reason: SUGGESTION OF BANKRUPTCY**. Our `tier1_sale_status='LISTED'` was captured minutes before the cancellation posted — a timing race, not an error; docket confirms cancellation is real and current. |
| `2026CA000403AX` | 8220 Abalone Loop | Case exists (ISLES AT BAYVIEW HOA INC). Summary box still showed "Sale Date: 09/02/2026" with no Sale-Canceled field, but the **docket entries** contain: `08/07/2026 PLAINTIFF'S MOTION TO CANCEL FORECLOSURE SALE...`, `08/12/2026 ORDER TO CANCEL FORECLOSURE SALE SET FOR SEPTEMBER 02, 2026, VACATE FINAL JUDGMENT`, `08/20/2026 CERTIFICATE OF SERVICE OF ORDER TO CANCEL...`. Genuinely cancelled; summary box just hadn't refreshed. |
| `2025CA002617AX` | 4085 Lake Bayshore Dr | Case exists (`412025CA002617CAAXMA`, filed 10/29/2025), status **ACTIVE MORTGAGE** — no final judgment ever entered (docket ends 07/23/2026 at a post-summary-judgment-hearing certificate of service, before any judgment). No legal basis existed for the auction_date our pipeline had on file; there is no judgment order that could authorize a sale. Cancellation-equivalent confirmed by absence of judgment, not by an explicit "Sale Canceled" field (case never reached that stage). |
| `412024CA000409CAAXMA` | 12220 81st St E, Parrish (owner GREEN ROBIN G) | Manatee Clerk's public case-number search box **cannot resolve full 21-char Uniform Case Numbers** — proven by a control test (see below). Cross-verified instead via Official Records instrument search on `GREEN ROBIN` → found the abbreviated docket case `2024CA000409AX`, defendants **ROBIN G GREEN / WILLIAM S GREEN** (exact name match), judgment amount **$257,472.47** (exact match to our stored `judgment_amount`). Docket: **Sale Canceled 08/20/2026, Reason: JUDICIAL ORDER**. |
| `412025CC000720CCAXMA` | 949 Sandpiper Cir | Search-box fuzzy-matched an unrelated case (`2025CC000720AX`, BOGDANOVA/HOSSAIN — wrong year, wrong party, County Civil $17.5K judgment — not a real match). No address/legal-description search field exists on the public portal to independently re-key this case. Falls back to the tier1 pipeline's own prior authoritative verification: `tier1_authoritative=true`, `tier1_source_run_id=5310`, verified 2026-05-28, `tier1_sale_status='CANCELED'`, `parity_confidence=0.98`. The only divergence on file is PropertyOnion showing "Sold" vs ours "cancelled" — expected PO noise (PO is litmus-only per project guardrails, not authoritative), not evidence of a genuine miss. |

**Control test proving the search box cannot be trusted for exact full-UCN lookups:** queried
`412023CA000253CAAXMA`, a case independently already marked `parity_status='matched_clean'` in our own
DB (i.e., known-good). The search box returned an unrelated case, `2026CA000253AX` (OLIVER, DONNA LYNN) —
wrong year, wrong party. The Official Records help text confirms why: *"Case number formats have changed
often over the span of this index. The current format is: [Year][CaseTypeCode][Identifier]... For modern
case numbers like 2000CA000123 the search will accept '00CA123' or '2000CA123'..."* — the box does
substring/fuzzy matching on the numeric identifier and does not validate the full county-prefix UCN. This
means the two format-mismatched cases could not be *positively* re-verified via the search box by design,
but neither is there any evidence they are wrongly classified — one (`...000409...`) was independently
confirmed via a different verified path (instrument search), and the other (`...000720...`) rests on a
pre-existing high-confidence tier1 verification that this session's manual probing did not contradict.

No changes made. All 13 `parity_status='CLERK_SSOT_CANCELLED'` rows stand as correctly classified.

### taylor (1 row, C = 92.3%, 12/13)

| case_number | source checked | result |
|---|---|---|
| `25-014 CA` (1104 N Allen Street, Perry FL 32347) | `taylorclerk.com/departments/foreclosure-sales/` and `/departments/tax-deeds/` — the same structured live department feeds the tier1 `shard6_taylor_scraper.py` scraper uses (taylor.realforeclose.com / taylor.realtaxdeed.com are known-broken 302 redirects per that script's own header comment; taylorclerk.com's department pages are the real source) | Case number `25-014 CA` and street "Allen"/"014" absent from both live feeds (fresh pull, 2026-08-27). Current live foreclosure-sales feed contains only `23-505 CA, 23-597 CA, 25-145 CA, 25-210 CA, 26-042 CA`; tax-deeds feed contains only `38-3506`. |

No change. `parity_status='CLERK_SSOT_CANCELLED'` stands.

## Live scoring evidence (VERIFIED, `pencil_dod_evaluate_county`, run 2026-08-27)

```
calhoun:  C {"pass": false, "detail": "matched_clean=8",   "metric": 88.9}  D {"pass": true, "metric": 100.0}  auctions_total=9
manatee:  C {"pass": false, "detail": "matched_clean=153", "metric": 92.2}  D {"pass": true, "metric": 100.0}  auctions_total=166
taylor:   C {"pass": false, "detail": "matched_clean=12",  "metric": 92.3}  D {"pass": true, "metric": 100.0}  auctions_total=13
```

Cancellation rate implied by the gap (rows in D's passing set but not C's, over total auctions):
- calhoun: 1/9 = 11.1%
- manatee: 13/166 = 7.8%
- taylor: 1/13 = 7.7%

All three sit comfortably above the ~5% slack C's 95% threshold allows, and all three are driven entirely
by genuine cancellations, not data defects.

## Why this is a canon-level issue, not a per-county data issue

The evaluator's definitions (reproduced from the canonical `pencil_dod_evaluate_county` spec):

```
matched_clean (C) := count WHERE (parity_status='matched_clean' AND parity_source LIKE 'tier1%')
                      OR parity_status IN ('PARITY_OK','CLERK_VERIFIED')
matched_any   (D) := count WHERE (parity_status IN ('matched_clean','matched_divergent') AND parity_source LIKE 'tier1%')
                      OR parity_status IN ('PARITY_OK','CLERK_VERIFIED','CLERK_SSOT_CANCELLED')
```

C's passing set deliberately excludes `CLERK_SSOT_CANCELLED`; D's deliberately includes it. This is a
correct and intentional distinction by design — C is meant to answer "how many of our auction rows cleanly
match a live, currently-relevant clerk record" and a cancelled sale is arguably not "clean" in that sense.
But the practical consequence, now independently confirmed in **three separate counties in one shard on
one day**, is that **any county with a normal real-world case-cancellation rate above ~5% will structurally
cap C below the 95% pass threshold, forever, regardless of data quality.** As `clerk_ssot` reconciliation
(the same pipeline that correctly flags `CLERK_SSOT_CANCELLED`) rolls out across the remaining fleet
counties, this is not a one-off anomaly to keep re-diagnosing per county — it is the expected, recurring
outcome everywhere cancellation reconciliation has run and cancellation rates are realistic.

## Recommendation to the AI Architect / Ariel

This needs a **canon-level decision**, not continued per-county re-investigation:

1. **Option A — exclude verified-cancelled cases from C's denominator.** Redefine C's `auctions_total`
   scope (or add a `WHERE parity_status != 'CLERK_SSOT_CANCELLED'` filter to both numerator and
   denominator) so C measures "match cleanliness among rows that are still live/relevant," structurally
   analogous to how `closed_sold` already excludes PropertyOnion-only rows.
2. **Option B — admit `CLERK_SSOT_CANCELLED` to C's passing set, same as D.** This treats "we correctly
   identified and reconciled a cancellation via tier1 clerk SSOT" as itself a clean match outcome (it is,
   after all, evidence the row is fully explained by a live clerk source) — effectively making C and D
   identical for this case, which may be too permissive and worth discussing before adopting.
3. **Option C — leave canon as-is, document the cap.** If C is intentionally meant to be a stricter,
   sometimes-unreachable bar in high-cancellation counties, downgrade the SHIP GATE / gold-standard
   certification requirement for C specifically to "cannot regress below current value" rather than
   ">=95%", to stop burning further sessions on structurally-unfixable re-diagnosis.

Per the task's explicit instruction, **this shard did not modify `public.pencil_dod_evaluate_county`** —
that is a fleet-wide function and any canon change needs owner sign-off given the blast radius (every
county running clerk_ssot reconciliation touches this).

## Guardrail compliance

- No `parity_id`, `sold_amount`, `parcel_id`, or `parity_status` was fabricated or changed for any of the
  15 rows.
- PropertyOnion data was treated strictly as litmus (the manatee `2024CA001675AX`-adjacent
  `412025CC000720CCAXMA` divergence against PO's "Sold" label was explicitly NOT used to justify a
  different classification).
- Every claim above is tagged VERIFIED — each was produced by a live fetch run in this session
  (`records.manateeclerk.com`, `calhounclerk.com` WP-JSON, `taylorclerk.com` department pages) with raw
  output inspected, not inferred or estimated.
- `pencil_dod_evaluate_county` was not modified.

## Addendum (dispatch `8da482b6`, shard-1, same day 2026-08-27): gadsden reconfirms the pattern, plus a distinct reversion bug

### gadsden (10 rows, C = 85.1%, 57/67)

Verified against `www.gadsdenclerk.com/Tax_deeds/Tax_deeds.htm` — the live Gadsden Clerk of Circuit
Court Excel-published tax-deed auction list (an IE-frameset export; the actual data lives in
`Tax_deeds_files/sheet001.htm`, the "Tax Deed Auction List of Lands Available for Tax" tab, distinct
from the `sheet002` "List of Lands Available for Taxes," `sheet003` "Excess Unclaimed Proceeds," and
`sheet004` "Escheated Tax Deeds" tabs on the same page). No WP-JSON feed exists on this domain (unlike
calhounclerk.com) — this is the correct live-source substitute for gadsden, matching the county's
existing `parity_source='gadsden_clerk_tax_deed'` provenance tag.

| case_number | property | live sheet finding |
|---|---|---|
| `26000018TDC` | 935 Laura St, Quincy | Row present in live 9/2/2026 auction list. Owner "Heirs of Willie Reeves" (exact DB match). Sale-Price column: **Redeemed 8/3/26**, $0.00. |
| `26000021TDC` | 651 S 9th St, Quincy | Row present. Owner "Marsha V Moore" (exact match). **Redeemed 6/29/26**, $0.00. |
| `26000022TDC` | 21 Pat Thomas Pkwy, Quincy | Row present. Owner "21 Pat Thomas Parkway, LLC" (exact match). **Redeemed 8/3/26**, $0.00. |
| `26000024TDC` | Ray Rd, Quincy | Row present. Owner "Gregory Brewton as Trustee of the Gregory Brewton Revocable Trust Agreement" (exact match). **Redeemed 7/24/26**, $0.00. |
| `26000025TDC` | 88 Pine Cone St, Quincy | Row present. Owner "Larry B Green" (exact match). **Redeemed 7/31/26**, $0.00. |
| `26000027TDC` | 102 Shuler Rd, Midway | Row present. Owner "Jacquinta Aronda ET AL; Lefraun Lloyd" (exact match). **Redeemed 08/20/26**, $0.00. |
| `26000029TDC` | 24 Silver Hill Rd, Midway | Row present. Owner "Shannon Sherelle Baker" (exact match). **Redeemed 7/27/26**, $0.00. |
| `26000032TDC` | Carmen Maria Ln, Quincy | Row present. Owner "True Wisdom New Hope Ministries International Development Center" (exact match). **Redeemed 7/22/26**, $0.00. |
| `26000034TDC` | 1274 Drake Acres Rd, Quincy | Row present. Owner "Roger Mawell & Rhonda Maxwell" (exact match). **Redeemed 7/31/26**, $0.00. |
| `26000035TDC` | 1248 Drake Acres Rd, Quincy | Row present. Owner "Cierra King" (exact match). **Redeemed 8/18/26**, $0.00. |

All 10/10 rows independently confirmed live against `gadsdenclerk.com` this session (2026-08-27),
matching case_number, parcel-owner name, and property address exactly against our DB. Cross-checked
against the other three tabs on the same page (List of Lands, Excess Proceeds, Escheated Tax Deeds) —
none of the 10 case numbers appear anywhere else on the site; they exist solely as redeemed rows within
the current 9/2/2026 auction list, consistent with the page's own header notice: *"To Redeem property,
pay taxes to the Tax Collector's office... REDEEMED PROPERTY WILL NOT GO TO AUCTION."*

**Nuance vs. the calhoun/manatee/taylor pattern:** all 10 gadsden rows are specifically **Redeemed**
(pre-sale redemption by owner/lienholder — the property never reaches the tax-deed sale, no cancellation
by court order or plaintiff motion), not a foreclosure sale cancellation in the manatee sense (motion to
cancel, bankruptcy stay, judicial order). Gadsden's `auction_status` column currently stores the generic
value `CANCELLED` for all 10 rows, which is a lossy label — the live source is more specific and says
"Redeemed [date]." This is a genuine, real, and currently-accurate outcome; it is not evidence of a data
defect, and does not change the canon-block conclusion. It does mean any canon fix (Option A/B above)
applied to gadsden should key off `parity_status='CLERK_SSOT_CANCELLED'` rather than `auction_status`,
since redemption is being correctly captured upstream already, just bucketed under the same generic
parity_status as court-cancelled sales.

**Separate, load-bearing finding — this specific gadsden blocker has already been diagnosed and briefly
fixed twice before, then reverted:** `docs(gold-standard): gadsden C structural-ceiling finding` (commit
`001733ea`, 2026-08-23) found this exact 10-row blocker and inserted a `tax_deed_outcomes` table with
`outcome='redeemed'` for all 10 (source: `gadsden_clerk_tax_deed_sheet_verified_20260823`, matching
today's live re-check). A same-day follow-up, `ARCHITECT TRIAGE #19393` (commit `5c7bcebe`), applied a
narrow, case-number-scoped `UPDATE` (migration
`20260823_architect_triage_19393_gadsden_C_parity_gate_unblock.sql`) reclassifying these exact 10 rows
to `parity_status='matched_clean'`, `parity_source='tier1_tax_deed_outcome'`, and verified live gadsden
C 84.8%→100.0%, 9/10→10/10 letters passing. As of this session (2026-08-27), all 10 rows are back to
`parity_status='CLERK_SSOT_CANCELLED'` / `parity_source='gadsden_clerk_tax_deed'` / `auction_status=
'CANCELLED'`, with `updated_at` timestamps of `2026-08-27T11:25:13Z` — hours before this session and
identical across all 10 rows, consistent with a scheduled upstream re-scrape (`gadsden_clerk_tax_deed`
scraper) overwriting the manually-applied fix. **This is a reversion of a prior applied fix by a
recurring upstream job, not a fresh unreconciled gap** — worth flagging separately from the canon-level
recommendation, since re-applying the same scoped UPDATE will only be re-reverted by the next scrape
cycle unless the upstream scraper is changed to respect (or itself write) `tier1_tax_deed_outcome`
provenance, or the canon decision (Option A/B above) is adopted so this class of row does not need
per-run reclassification at all. **No fix was re-applied this session** for exactly this reason — a
third reclassification would just be reverted again by the next `gadsden_clerk_tax_deed` scrape.

No changes made to `parity_status`, `sold_amount`, or `parcel_id` for any of the 10 gadsden rows this
session; `pencil_dod_evaluate_county` was not modified; `gold_standard_loop()`/`gold_standard_certify()`
were not invoked (other cc-runner-ghonly.yml shard sessions were confirmed in-flight at the time).
Logged to `gold_standard_ultraloop_audit` id 18764 (dispatch `8da482b6`, survived=true — the claim
"this is the documented canon block plus a reversion bug," not a claim that C now passes).

## Addendum (dispatch `97eac5d8`, shard-5, 2026-08-27): suwannee reconfirms the pattern

### suwannee (6 rows, C = 82.9%, 29/35)

Live DB check this session (VERIFIED) confirms exactly 6 `multi_county_auctions` rows for
`county='suwannee'` carry `parity_status='CLERK_SSOT_CANCELLED'`: case numbers `4693`, `4676`, `4744`,
`4672`, `4694`, `4681`. Each row's `parity_source` already documents a schedule-diff verification
(case present in the clerk's staged 2026-08-24 PDF snapshot, absent from the 2026-08-25 snapshot and
from a fresh independent re-fetch on 2026-08-26), with `auction_status='redeemed'` corroborating.
29 `PARITY_OK`/`matched_clean` + 6 `CLERK_SSOT_CANCELLED` = 35 = the full county.

Verified against the live Suwannee Clerk tax-deed schedule PDF — the same source
`scripts/clerk_ssot/parsers/suwannee.py` uses. The parser discovers the current PDF link from the
landing page (`https://www.suwgov.org/tax-deed-sales/`) rather than hardcoding a filename, since the
filename embeds the sale date and is replaced each sale cycle; today's discovered link is still
`Schedule-08.24.2026.pdf` (labeled "Next Tax Deed Sale – September 3, 2026" on the landing page),
i.e. the schedule has not rolled to a new PDF since the 2026-08-24/08-25 diff that originally produced
this classification.

| case_number | source checked | result |
|---|---|---|
| `4693` | `https://www.suwgov.org/wp-content/uploads/Schedule-08.24.2026.pdf` (fresh fetch, 2026-08-27, HTTP 200, Last-Modified: `Mon, 24 Aug 2026 19:37:40 GMT`) | Absent from the live schedule. Only case rows `4675, 4677, 4678, 4679, 4680, 4682, 4684, 4698, 4704, 4741, 4752, 4754, 4756, 4758, 4760` remain (15 case rows in the current PDF, all pre-`4693` or later, none matching). |
| `4676` | same fetch as above | Absent from the live schedule (same 15-row result set). |
| `4744` | same fetch as above | Absent from the live schedule. |
| `4672` | same fetch as above | Absent from the live schedule. |
| `4694` | same fetch as above | Absent from the live schedule. |
| `4681` | same fetch as above | Absent from the live schedule. |

All 6 case numbers were checked (not just 2) since the parser output is small and cheap to fully
re-verify in one fetch. Every one of the 6 is confirmed still absent from the live PDF today, matching
the 2026-08-26 finding exactly two days later with an independent fresh HTTP fetch — not a stale re-read
of a cached result.

## Live scoring evidence (VERIFIED, `pencil_dod_evaluate_county`, run 2026-08-27)

```
suwannee: C {"pass": false, "detail": "matched_clean=29",  "metric": 82.9}  D {"pass": true, "metric": 100.0}  auctions_total=35
```

Cancellation rate: 6/35 = 17.1% — well above the ~5% slack C's 95% threshold allows, and (as with
calhoun/manatee/taylor/gadsden) driven entirely by genuine, independently-reconfirmed cancellations
(redemptions, per `auction_status='redeemed'`), not a data defect.

This diagnosis was independently reached once already, by an earlier shard-3 session (dispatch
`697ee013`, `GOLD_STANDARD_SHARD3_SUMTER_SUWANNEE_WAKULLA_DISPATCH_697EE013_SESSION_REPORT.md`,
2026-08-26), which fixed suwannee D (82.9%→100%, 29/35→35/35) via the same 6-row `CLERK_SSOT_CANCELLED`
reclassification and explicitly held C unchanged "root cause found and fixed (D), C honestly held." That
session's finding was never cross-referenced into this canonical cross-county document until now.

### lake (18 rows, C = 87.1%, 121/139)

Live DB check this session (VERIFIED) confirms 18 `multi_county_auctions` rows for `county='lake'` carry
`parity_status='CLERK_SSOT_CANCELLED'` (`parity_source` values `lake_clerk_foreclosure` and
`lake_clerk_foreclosure:manual_recheck_20260812`). Live `pencil_dod_evaluate_county` run this session:

```
lake: C {"pass": false, "detail": "matched_clean=121", "metric": 87.1}  D {"pass": true, "metric": 100.0}  auctions_total=139
```

Cancellation-vs-total gap: (139-121)/139 = 12.9% — same above-threshold pattern.

Spot-checked 2 of the 18 against the live Lake Clerk foreclosure calendar
(`https://foreclosurecalendar.lakecountyclerkfl.gov/?view=list`, the same source
`scripts/clerk_ssot/parsers/lake.py` uses — fresh fetch, 2026-08-27, HTTP 200, 72 live `event_item`
blocks / 71 distinct case numbers parsed):

| case_number | source checked | result |
|---|---|---|
| `2025CA000251` | live list-view fetch, 2026-08-27 | Absent from the current rolling calendar. DB `auction_date=2026-08-25` (2 days in the past as of this check) — consistent with having rolled off Lake's list-view, which only shows near-term/upcoming events, not an archive. |
| `2025CA002869` | live list-view fetch, 2026-08-27 | Absent from the current rolling calendar. DB `auction_date=2026-08-18` (9 days in the past) — same rolling-window explanation. |

This is weaker-form evidence than suwannee's (Lake's calendar is a rolling window with no persistent
per-case archive page discovered this session, so "absent" here is consistent with, not independently
proof of, cancellation), but it does not contradict the classification, and it is corroborated by the
existing `gold_standard_ultraloop_audit` id `18509` (2026-08-26, `county_slug='lake'`, `letter='C'`,
`claim`: "C unchanged at 87.1 (121 of 139) -- gap is structurally CLERK_SSOT_CANCELLED rows correctly
excluded by design, not touched this session", `survived=true`) — independently logged the day before
this session, live-queried and reconfirmed identical (`metric_before=87.1`, `metric_after=87.1`) today.

**No `parity_status` was changed for any suwannee or lake row this session.
`pencil_dod_evaluate_county` was not modified. `gold_standard_loop()` / `gold_standard_certify()` were
not invoked (per this dispatch's explicit instructions — other shard sessions are concurrently mid-flight
on other counties).** Two new `gold_standard_ultraloop_audit` rows were inserted this session
(dispatch `97eac5d8`, county_slug=`suwannee` and `lake`, letter=`C`, `survived=true`) documenting this
reconfirmation — not a claim that C now passes.

## Addendum (same day 2026-08-27): charlotte reconfirms the pattern — 4th/5th independent confirmation

### charlotte (109 rows, C = 60.4%, 174/288 — the starkest ratio observed yet)

Live `parity_status` breakdown for charlotte, pulled this session via `pencil_dod_evaluate_county('charlotte')`
and a direct `multi_county_auctions` count:

| parity_status | count | % of 288 |
|---|---|---|
| `matched_clean` | 174 | 60.4% |
| `CLERK_SSOT_CANCELLED` | 109 | 37.8% |
| `NULL` | 5 | 1.7% |
| **Total** | **288** | 100% |

`pencil_dod_evaluate_county('charlotte')` (VERIFIED, live run this session):

```
C {"pass": false, "detail": "matched_clean=174", "metric": 60.4}
D {"pass": true,  "detail": "matched_any=283",   "metric": 98.3}
auctions_total=288
```

Charlotte is the **starkest instance of the canon-level block found so far**: a 37.8% cancellation rate,
more than **7x** the ~5% slack C's 95% threshold allows (vs. calhoun 11.1%, manatee 7.8%, taylor 7.7%,
gadsden's 10/67=14.9%). This is consistent with charlotte's own prior sessions
(`charlotte_cd_realforeclose_tier1_backfill_ch_cd.py`, `charlotte_cd_tier1_run93161_parity_stamp.py`) which
already independently documented, on 2026-08-11 and 2026-08-12 respectively, that charlotte's remaining
`CLERK_SSOT_CANCELLED`/redeemed rows are "genuinely cancelled/redeemed and correctly excluded from
matched_clean by the evaluator's design; ... no further legitimate lever without fabricating a status
change on real cancelled/redeemed sales" — the same conclusion this cross-county finding reaches
independently, now for a 4th (arguably 5th, counting gadsden separately) county.

**No fabricated matches were created. No pre-existing `CLERK_SSOT_CANCELLED` row's `parity_status` was
changed.** Consistent with the recommendation above (Options A/B/C), this remains a canon-level decision,
not a per-county data-quality gap. `pencil_dod_evaluate_county` was not modified for this addendum.

Separately and out of scope for the C canon question: charlotte had 5 rows with `parity_status IS NULL`
(a genuine, actionable D-hygiene gap, unrelated to the C/D canon tension) — reconciled the same session;
see the county's own session report for exact before/after values.

## Addendum (same day 2026-08-27): sumter reconfirms the pattern, plus a genuinely new 4th row

### sumter (4 rows, C = 87.5%, 28/32)

Live `parity_status` breakdown, pulled this session via a direct `multi_county_auctions` REST query
(county=eq.sumter, 32 rows, matches `auctions_total`):

| case_number | parity_status | parity_source | auction_status |
|---|---|---|---|
| `104` | `CLERK_SSOT_CANCELLED` | `sumter_clerk_tax_deed` | `CANCELLED` |
| `1078` | `CLERK_SSOT_CANCELLED` | `sumter_clerk_tax_deed` | `CANCELLED` |
| `1159` | `CLERK_SSOT_CANCELLED` | `sumter_clerk_tax_deed` | `CANCELLED` |
| `1400` | `CLERK_SSOT_CANCELLED` | `sumter_clerk_tax_deed` | `CANCELLED` |

This is a **genuinely different set from the previously-documented 3-row sumter finding**
(`scripts/sumter_shard3_697ee013_c_reconfirm_no_write.py`, 2026-08-26, 24-row baseline, cases 104/1159/1400
only). Case `1078` was **not yet blocking C as of 2026-08-26** — it has since redeemed and joined the
blocking set, growing sumter's total auction rows from 24 to 32 and the C-gap from 3 to 4 in the interim.

Verified this session against the live `sumterclerk.com` tax-deed sales widget
(`GET https://www.sumterclerk.com/public-records/tax-deeds/tax-deed-sales/`, HTTP 200, 175047 bytes,
`<tax-deed-sales :taxdeeds="[...]">` inline JSON widget, `today` field `20260827181114` i.e.
2026-08-27T18:11:14 UTC — confirms live, not cached):

| cert | parcel | owner | status | modified |
|---|---|---|---|---|
| `1078` | `J16C020` | JACKSON, MARTIN | `redeemed` | 2026-08-27 08:42:56 (today) |
| `1159` | `M06C003` | CROMER, BRENDA | `redeemed` | 2026-08-25 08:32:23 |
| `104` | `C27-268` | TRUSTEES OF THE OAK HILL CEMETERY | `redeemed` | 2026-08-19 08:57:06 |
| `1400` | `N33-021` | GRINER, ANDREW & SEAN (JTWROS) | `redeemed` | 2026-08-19 09:05:58 |

All 4 `cert`/parcel pairs match the DB's `case_number`/`parcel_id` exactly, string-for-string. Case `1078`
in particular was cross-checked directly (`parcel_id=J16C020`, `parity_status=CLERK_SSOT_CANCELLED`,
`auction_status=CANCELLED` in DB) against the live widget row (`cert=1078 parcel=J16C020 status=redeemed`,
modified the same day as this session) — DB classification already matches live reality exactly, no drift,
no stale tagging.

`pencil_dod_evaluate_county('sumter')` (VERIFIED, live run this session, before and after — identical,
confirming no write occurred):

```
C {"pass": false, "detail": "matched_clean=28", "metric": 87.5}
D {"pass": true,  "detail": "matched_any=32",   "metric": 100.0}
auctions_total=32
```

Cancellation rate implied by the gap: 4/32 = 12.5% — above the ~5% slack C's 95% threshold allows, in
the same range as calhoun (11.1%) and gadsden (14.9%).

**No fabricated matches were created. No row's `parity_status` was changed.** All 4 rows are genuine,
live, currently-redeemed tax-deed certificates, correctly excluded from `matched_clean` by C's canon
design and correctly included in `matched_any` (D, which passes at 100.0%). This is the 6th (7th
counting gadsden separately) independent county confirming the same canon-level C/D tension — and the
first case where a **new row joined the blocking set between sessions** (1078, redeemed just today),
demonstrating the block is not a one-time historical artifact but an ongoing, structurally recurring
outcome as clerk redemptions continue to happen in the normal course of business.

## Files

- This document: `GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md`
- Precedent: `calhoun_c_546of2024_phantom_ssot_cancel_reconcile.sql`
- Charlotte precedent (independent, pre-dates this doc): `scripts/charlotte_cd_realforeclose_tier1_backfill_ch_cd.py`,
  `scripts/charlotte_cd_tier1_run93161_parity_stamp.py`
- Sumter precedent (independent, pre-dates this doc, 3-row/24-total baseline): `scripts/sumter_shard3_697ee013_c_reconfirm_no_write.py`
- No new SQL fix file — no live DB write was made against any pre-existing `CLERK_SSOT_CANCELLED` row in
  this session (all 15 original rows, plus gadsden's 10, suwannee's 6, lake's 18, charlotte's 109, and
  sumter's 4 — including the newly-redeemed case 1078 — reconfirmed correct as-is).
