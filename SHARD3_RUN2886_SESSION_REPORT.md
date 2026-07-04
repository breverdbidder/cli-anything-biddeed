# SHARD-3 Session Report (loop run 2886) — charlotte, highlands, volusia, manatee, liberty (2026-07-04)

dispatch_id: 31da8c5f-9710-4642-ace0-8147d76c4680
chat_session: architect-20260704T080000

## Summary

One letter flipped FAIL→PASS: **manatee G** (zoning density, 90.4%→96.3%), via a single
`zone_standards` row backfill for the previously-unverified `A-1` (Agricultural Suburban) district —
33 parcels, the single highest-leverage gap in manatee's zoning coverage. Adversarially verified
SURVIVED by an independent refuter agent (logged to `gold_standard_ultraloop_audit`).

Everything else investigated this session hit a genuine evidentiary wall and was correctly left
alone rather than forced: **charlotte** was already 10/10 (verified, no regression). **highlands**
C/D (2.1%) turned out to already be a prior session's honest-ceiling correction from earlier today
(a fabricated `tier1_realforeclose_highlands` label was reverted at 08:17Z, before this session
started — the brief's "36.8%" figure was stale/pre-revert); this session additionally wired
`pipeline.counties` for highlands from already-verified `realauction_subdomains` discovery data
(both FQDNs `is_active=true`, `http_status=200` since 2026-05-24) and extended
`county-outcome-harvest.yml` to support highlands/manatee/liberty, then dispatched live harvester
runs for all three plus volusia — all four returned **0 new live-scrape results** (RealAuction
login/archive genuinely returns nothing for these county+date-range combinations from the GHA
runner, not a sandbox network artifact). **volusia** C/D (71.8%) is a temporal ceiling, not a bug:
of 105 unmatched in-scope rows, 84 are `auction_status=upcoming` (no outcome can exist yet) and the
remaining 21 concluded rows have zero rows in `foreclosure_outcomes` for those case numbers — a real
outcomes-coverage gap requiring authenticated scraping, not something this session fabricated a fix
for. **manatee** C/D (26.1%) and **liberty** (near-zero-activity county, 1 total auction, "no docket
either side" per prior discovery work) remain genuinely blocked on the same authenticated-scraping
wall.

## Before / after (live `pencil_dod_evaluate_county`)

### charlotte — 10/10, untouched (verified no regression)
No changes made. Re-verified live at session start: all 10 letters PASS, matches the brief exactly.

### manatee — G flips FAIL→PASS (7/10, was 6/10)
```json
// BEFORE
{"G":{"pass":false,"metric":90.4,"detail":"density=90.4 far=100.0 pk1000="}}
// AFTER
{"G":{"pass":true,"metric":96.3,"detail":"density=96.3 far=100.0 pk1000="}}
```
Root cause: `zoning_districts.code='A-1'` (Agricultural Suburban District, Unincorporated Manatee
County, 33 parcels) had **no `zone_standards` row at all** — the district was flagged
`density_regulated=NULL` ("unverified"). `max_density_du_acre=1.00` CONFIRMED from Manatee County
LDC Sec. 602.1.2.2, Figure 6-2 schedule, cross-validated against the already-verified "A" (General
Agriculture) district figure (0.20 DUA) in the same table, which matches our existing DB value
exactly. `confidence_score=0.85` (not 1.0): the specific PDF pulled was a 2015 staff-redline draft
copy of Ch.4; Municode's live JS-rendered page could not be scraped to confirm word-for-word — this
caveat is recorded in the migration and the `zone_standards.ordinance_section` text.
Migration: `supabase/migrations/20260704_shard3_manatee_a1_density_backfill.sql`.
Adversarially verified SURVIVED (independent refuter re-ran all 4 checks live, no red flags,
no denominator gaming) — logged `gold_standard_ultraloop_audit` id=3330.

manatee's remaining gaps (A=fc=69/td=0, C/D=26.1%) are a genuine outcomes-coverage wall:
`tax_deed_outcomes` has **zero** manatee rows; `foreclosure_outcomes` has exactly 5 (all matching
the 5 closed/sold auctions, which is why B/F already pass at 100%). The 16 cancelled auctions have
no independent record to match against. Dispatched `county-outcome-harvest.yml` for manatee this
session (run 28702470331) — live scrape returned 0 new results; not fabricated.

### highlands — 8/10, unchanged this session (infra wired, no letter flip)
```json
{"A":{"pass":true,"metric":2},"B":{"pass":true,"metric":100.0},
 "C":{"pass":false,"metric":2.1,"detail":"matched_clean=3"},
 "D":{"pass":false,"metric":2.1,"detail":"matched_any=3"},
 "E":{"pass":true,"metric":98.6},"F":{"pass":true,"metric":100.0},
 "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":1.9},
 "I":{"pass":true,"metric":97.9},"J":{"pass":true,"metric":100.0},"auctions_total":144}
```
The brief handed to this session quoted C/D=36.8% (53/144) — that was a **ghost success**: another
session earlier today (08:17Z, before this dispatch) found and reverted a fabricated
`tier1_realforeclose_highlands` label on 50 rows (all `auction_status=upcoming`, `sold_amount=null`,
zero backing in `foreclosure_outcomes`/`tax_deed_outcomes`, never emitted by
`refresh_parity_tier1_outcomes`), correcting the metric to the honest 2.1% (3/144) — logged
`gold_standard_ultraloop_audit` ids 3305/3307 (also documents that changing the shared C/D CTE to
exclude upcoming rows is campaign-wide canon, out of scope for a single-county fix). This session
re-confirmed that live and did not re-litigate it.

New work this session: `pipeline.counties.highlands` was an auto-seeded placeholder
(`foreclosure_platform`/`taxdeed_platform`=NULL, `pipeline_status='pending'`) despite
`public.realauction_subdomains` already showing both `highlands.realforeclose.com` and
`highlands.realtaxdeed.com` verified live (`is_active=true`, `http_status=200`,
`last_verified='2026-05-24'`). Wired from that verified data
(`supabase/migrations/20260704_shard3_highlands_pipeline_wiring.sql`). Extended
`.github/workflows/county-outcome-harvest.yml` (previously hardcoded to 6 counties) with
highlands/manatee/liberty FQDN cases and dispatched it live (run 28702468944): 3 pre-existing closed
auctions found, live scrape of 24 months of highlands.realforeclose.com calendar pages returned
**0 AITEM blocks** (`realforeclose login: may have failed`) — a genuine negative result from the GHA
runner itself, not a local sandbox network artifact. C/D unchanged; real fix needs working
RealAuction authentication for this specific county or a clerk-records alternative.

### volusia — 8/10, unchanged (temporal ceiling correctly not forced)
```json
{"C":{"pass":false,"metric":71.0,"detail":"matched_clean=265"},
 "D":{"pass":false,"metric":71.8,"detail":"matched_any=268"},"auctions_total":373}
```
The brief quoted C/D=91.4/92.4% against a denominator of 290; live denominator has grown to 373 (83
more in-scope rows ingested since) while the matched count held flat — this reads as regression but
isn't one. Re-ran `refresh_parity_tier1_outcomes('volusia')` live: no change (265/268, confirming the
matcher is already current). Broke down all 105 unmatched in-scope rows by `auction_status`: **84 are
`upcoming`** (calendar-swept future auctions with no possible outcome yet — cannot honestly be
matched) and **21 are `concluded`** with zero corresponding `foreclosure_outcomes` rows for those
case numbers (genuine outcomes-coverage gap). Dispatched the harvester for volusia too (run
28702497962, `skip_live_scrape=false`, 24-month lookback) — 0 new live-scrape results. Honest
achievable ceiling this session without authenticated scraping: ~77.5% (289/373), still short of 95%
— did not force a fake pass.

### liberty — 3/10, unchanged
```json
{"A":{"pass":false,"metric":0},"B":{"pass":false,"metric":null},
 "C":{"pass":false,"metric":0.0},"D":{"pass":false,"metric":0.0},
 "E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null},
 "G":{"pass":false,"metric":null},"H":{"pass":true,"metric":0.6},
 "I":{"pass":false,"metric":0.0},"J":{"pass":true,"metric":100.0},"auctions_total":1}
```
Only 1 auction exists in the entire county. Per `public.realauction_subdomains`, liberty's
foreclosure/tax_deed RealAuction subdomains were discovered but flagged `is_active=false` with
`parity_verdict='no docket either side (us+PO zero all-time); low/no online FC'` — i.e. this is a
genuinely near-zero-activity rural county, not a scraper bug. Dispatched the extended
`county-outcome-harvest.yml` for liberty anyway (run 28702471907) to confirm: 0 closed auctions, 0
live-scrape results, consistent with the prior discovery finding. No fabricated data added.

## Adversarial verification (ULTRALOOP)

| County | Letter | Claim | Verdict |
|---|---|---|---|
| manatee | G | zone_standards A-1 backfill, 90.4%→96.3% | **SURVIVED** (independent refuter, 4/4 checks clean, logged id=3330) |
| highlands | C | prior session's ghost-success revert (36.8%→2.1%) | SURVIVED (pre-existing, ids 3305/3307, re-confirmed live) |

## Shipped to main

- `supabase/migrations/20260704_shard3_highlands_pipeline_wiring.sql` (applied live)
- `supabase/migrations/20260704_shard3_manatee_a1_density_backfill.sql` (applied live)
- `.github/workflows/county-outcome-harvest.yml` (highlands/manatee/liberty support added, 4 live
  dispatches executed this session: runs 28702468944, 28702470331, 28702471907, 28702497962)
- This report

## Scoreboard delta

| County | Before | After |
|---|---|---|
| charlotte | 10/10 | 10/10 (unchanged) |
| highlands | 8/10 | 8/10 (unchanged; infra wired for future sessions) |
| volusia | 8/10 | 8/10 (unchanged; honest ceiling ~77.5% without auth scraping) |
| manatee | 6/10 | **7/10** (G flip) |
| liberty | 3/10 | 3/10 (unchanged; near-zero-activity county) |

## Next session should

1. **Fix RealAuction authentication** for highlands/manatee/liberty/volusia — `REALFORECLOSE_EMAIL`/
   `REALFORECLOSE_PASSWORD` secrets exist but login failed/returned 0 results for all 4 counties
   dispatched this session. This is the single blocker behind every remaining C/D gap in this shard.
2. Once auth is fixed, re-run `county-outcome-harvest.yml` for manatee (16 cancelled auctions),
   volusia (21 concluded-unmatched), highlands (141 residual).
3. Do not re-litigate clay/highlands/orange ghost-success reverts already logged today — check
   `gold_standard_ultraloop_audit` for `dispatch_id` history before re-diagnosing.
