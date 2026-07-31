# Gold Standard shard-13 — lee — run 7553 duplicate re-fire #2 addendum

dispatch_id: `850748bb-e511-4a3d-bfe5-3714665723b5`
chat_session: `architect-20260731T000000`
county: **lee** (8/10: A,B,C,D,F,G,H,J PASS; E,I FAIL)

## This dispatch was fired a third time

The exact same dispatch_id + chat_session had already shipped twice: the
original fix (commit `6e51f24f`) and a first duplicate re-fire (commit
`162d5ecd`, ~75 minutes earlier the same day). At this session's start, live
`pencil_dod_evaluate_county('lee')` matched the `162d5ecd` addendum's final
state exactly:

```json
{"E":{"pass":false,"metric":93.2,"detail":"parcel_linked=300"},
 "I":{"pass":false,"metric":87.3,"detail":"card_complete=281"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000=100.0"},
 "county":"lee","auctions_total":322}
```

Zero drift confirmed before doing any new work. Rather than stop at "already
handled twice," this session picked up the one concrete, unresolved item the
prior addendum left open: confirm or refute whether case `20-CA-005572`
("1067 Danpark Loop") is actually 14067 Danpark Loop — a hypothesis the prior
session raised from centroid proximity alone but explicitly declined to write
on, for lacking primary-source confirmation.

## Before / after (`SELECT public.pencil_dod_evaluate_county('lee')`)

| Letter | Session start | This session's final (live) | Gate | Status |
|---|---|---|---|---|
| A–D, F, H, J | PASS | unchanged | — | — |
| **E** | FAIL 93.2 (300/322) | **FAIL 93.5 (301/322)** | 95 | improved, still FAIL |
| G | PASS 100.0/100.0/100.0 | **PASS 100.0/100.0/100.0 (re-verified, no regression)** | 95 | — |
| **I** | FAIL 87.3 (281/322) | **FAIL 87.6 (282/322)** | 95 | improved, still FAIL |

**8/10, unchanged.** One row moved both E and I; neither letter crossed the
95% gate. No regression on any of the 8 previously-passing letters.

## What moved: case 20-CA-005572 confirmed as 14067 Danpark Loop

Dispatched an ultracode Workflow (`wf_44752cdd-38c`) with two independent
research agents plus an adversarial verifier, specifically to close out the
prior session's unconfirmed hypothesis rather than re-attempt already-exhausted
leads. Result: **CONFIRMED**, and this session found a third independent
corroborating fact beyond what the workflow itself surfaced.

1. **Primary court record.** *Business Observer* legal notices (Nov 29, 2024),
   "Notice of Foreclosure Sale" for Case No. 20-CA-005572, *MTGLQ Investors,
   L.P. v. Douglas Spiegel, Heather Spiegel, Daniels Park Homeowners
   Association, Inc.* Legal description: "LOT 15, DANIELS PARK, ... PLAT BOOK
   82, PAGES 79 THROUGH 83, ... LEE COUNTY, FLORIDA." The notice itself prints
   "Property Address: 1067 Danpark Loop" — confirming the dropped-digit
   truncation traces back to the original court filing, not to our scrape.
2. **Property appraiser match.** Lee County ArcGIS Parcels FeatureServer
   (STRAP `21452513000000150`): `LEGAL = "DANIELS PARK PB 82 PGS 79-83 LOT
   15"` — matches the Final Judgment's legal description verbatim (plat book,
   pages, and lot number all agree).
3. **New this session:** the same ArcGIS record's current owner field
   (`O_NAME`) reads `"MTGLQ INVESTORS LP"` — the exact plaintiff from the
   Final Judgment. A parcel whose owner-of-record is now the foreclosing
   plaintiff is exactly the expected post-sale state for a concluded
   foreclosure where the lender took title by credit bid, independently
   consistent with this row's `auction_status='concluded'`,
   `auction_date=2026-03-12`.

Three independent, converging primary-source facts — not the proximity/
geocoding inference the prior session correctly declined to act on.

**Adversarial verification:** the refuter agent independently re-downloaded
the court-notice PDF (via `pdfplumber`, since plain fetch couldn't parse it)
and independently re-fetched the property-appraiser record, rather than
trusting the research agent's transcription. Confirmed both verbatim, found
additional independent corroboration (a Redfin listing for 14067 Danpark
Loop, and confirmation that no address near "1067" exists anywhere on Danpark
Loop), and returned `refuted=false`.

**Writes applied** (guarded on `parcel_id IS NULL`, idempotent):
- `multi_county_auctions`: `parcel_id=21452513000000150`,
  `latitude=26.540005`, `longitude=-81.812995`, `assessed_value=150672`
  (ArcGIS values — not the original scrape's `centroid_lat/lng`, which
  pointed to a different, unrelated $0-assessed common-element parcel).
- `parcel_zones`: new row linking `21452513000000150` → jurisdiction 630
  (Lee County unincorporated), `zone_code=RPD`, source tag
  `lee_shard13_run7553_2ndrefire_danpark_005572` (fresh, never reused).

**G-risk check before the zone-link write:** RPD already exists in
`zoning_districts` (id 11210) at jurisdiction 630, with
`zone_standards.max_density_du_acre=5.0` already populated.
`v_zoning_district_applicability` confirms `far_applicable=false`,
`pk1000_applicable=false`, `density_applicable=true` — the one regulated
dimension already carries a real value, so the write carries zero
G-denominator risk. Live-reconfirmed after the write: G unchanged at
100.0/100.0/100.0.

Both claims (E, I) logged to `gold_standard_ultraloop_audit`
(ids 11485, 11486) with `survived=true`, satisfying the ULTRALOOP PROTOCOL
certify-gate requirement.

## Not re-investigated this session (settled, per prior sessions — BLANK>WRONG)

1. **25-CA-002593 / 25-CA-003385 dedup collision.** Re-confirmed live: still
   two genuinely distinct cases (different `judgment_amount`/`opening_bid`,
   same property/auction date), blocked by the shared
   `uq_mca_county_sale_date_parcel` constraint. This remains an open
   **architect policy decision** — extend the unique key to include
   `case_number` (fleet-wide change) or accept the row cannot carry a
   `parcel_id` under the current schema. Not something a single-shard lee
   session should unilaterally decide. No new evidence gathered this
   session; the evidence-gathering itself was already settled.
2. **25-CA-004959 condo-unit and the 14-row no-address bucket.** Not
   re-attempted — both confirmed exhausted for search-only tooling across
   multiple consecutive sessions. RealForeclose's case-detail page
   (`AID=1491561`) was directly re-confirmed this session to require an
   authenticated bidder login (returns a login splash page to anonymous
   requests). Lee Clerk remains blocked by Akamai WAF. Needs an authenticated
   session or a funded Firecrawl/Playwright pass — not another search-tool
   attempt.

## SQL VERIFICATION

```sql
-- run 2026-07-31T02:10Z via POST rpc/pencil_dod_evaluate_county {"p_county":"lee"}
```
```json
{"A":{"pass":true,"metric":40,"detail":"fc=282 td=40"},
 "B":{"pass":true,"metric":100.0,"detail":"verified=20 closed_sold=20"},
 "C":{"pass":true,"metric":98.8,"detail":"matched_clean=318"},
 "D":{"pass":true,"metric":98.8,"detail":"matched_any=318"},
 "E":{"pass":false,"metric":93.5,"detail":"parcel_linked=301"},
 "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=20 closed_sold=20"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000=100.0"},
 "H":{"pass":true,"metric":0.0,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":false,"metric":87.6,"detail":"card_complete=282 of 322"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=322"},
 "county":"lee","auctions_total":322}
```

## Loop / certify — skipped by design

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()`
were **not** run this session: the most recent commit on `main` at session
start (`8ea82069`, wakulla shard-7 ULTRALOOP close-out) landed minutes before
this dispatch, indicating another shard session is mid-flight. Reporting via
per-county `pencil_dod_evaluate_county('lee')` only, as instructed.

## Next session priorities for lee

1. **Architect policy decision** on the `25-CA-002593`/`25-CA-003385` dedup
   (unchanged from prior session — not further investigation, a decision).
2. The 14-row no-address bucket remains the single largest E gap, confirmed
   blocked on Lee Clerk's Akamai WAF + RealForeclose's login requirement
   across 4+ sessions — needs an authenticated RealAuction bidder session or
   funded Firecrawl/Playwright pass.
3. `25-CA-004959` condo-unit: needs a docket/legal-description source that
   actually surfaces unit numbers — general web search is exhausted.
4. No further ArcGIS-address-typo hypotheses remain open for lee — this
   session closed out the one flagged lead (`20-CA-005572`). Future E/I gains
   for lee likely require the new-data-source unlock in item 2, not more
   single-row ArcGIS probing.

## Process note

Third consecutive firing of the identical dispatch. Rather than treat that as
a signal to stop, each firing has picked up exactly the prior firing's own
documented open item, avoiding both wasted re-investigation of settled
questions and idling. This firing closed the loop on a hypothesis the first
re-fire correctly declined to act on for insufficient evidence — the
ultracode workflow's adversarial-verify stage did its job by independently
re-fetching primary sources rather than trusting the research agent's
transcription, and a third convergent fact (plaintiff-to-current-owner match)
surfaced from a manual follow-up check that the automated workflow itself
didn't run. One genuine gain from one well-scoped question; everything else
correctly left untouched as either settled (dedup) or exhausted for the
tooling available (no-address bucket, condo unit).

---
dispatch_id: 850748bb-e511-4a3d-bfe5-3714665723b5
chat_session: architect-20260731T000000 (duplicate re-fire #2, this addendum)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
