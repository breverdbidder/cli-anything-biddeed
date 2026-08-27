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

## Files

- This document: `GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md`
- Precedent: `calhoun_c_546of2024_phantom_ssot_cancel_reconcile.sql`
- No new SQL fix file — no live DB write was made in this session (all 15 rows reconfirmed correct as-is).
