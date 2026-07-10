# SHARD-5 run3025 Session Report — baker / hillsborough / gulf / putnam / collier

dispatch_id: `d9210c60-335b-4a88-a422-0afee09d472b`
chat_session: `architect-20260704T160000`
Mode: ULTRALOOP fallback (manual Task/Workflow fan-out — `/effort ultracode` menu not probed directly, but the Workflow tool's investigate→fix→adversarial-verify pattern was used per protocol intent)

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| gulf I | verify/fix if failing | Found a **ghost verification** from an earlier session today (claimed PASS, was never actually applied) and re-executed the real fix | Deviation: this wasn't in the original per-county target list — it surfaced from a mandatory regression check before trusting any prior "survived=true" claim |
| putnam C/D | investigate real ceiling | Found and purged 12 rows of **re-stamped ghost-success** (fabricated `parity_source` re-applied after an earlier same-day refutation) | Deviation: no score change (still FAIL), but the metric is now honest — required per Honesty Protocol even without a pass/fail change |
| putnam E | investigate parcel linkage gap | Found and fixed the root cause: `fl_parcels.co_no = fl_counties.co_no + 10`, a fleet-wide undocumented numbering offset. Flipped FAIL→PASS | Matches plan, root cause was deeper than expected (a data-scheme bug, not a scraper gap) |
| hillsborough C/D | attempt real parity fix | Investigated thoroughly (stale `auction_status` theory), found **zero evidence overlap** against outcomes tables for all 207 gap rows — concluded no legitimate fix exists without new clerk ingestion | No fix applied — correctly declined to fabricate |
| gulf C/D | check pre-authorized clerk-litmus fallback | Probed gulfclerk.com/RealForeclose fresh — confirmed same already-wired platform (JS-shell, no static data), and confirmed zero live tax-deed inventory via clerk page | No fix applied — re-confirms an already-adversarially-confirmed BLOCKED verdict, correctly not re-litigated |
| collier A | probe real ingestion feasibility | Probed ShowCase SPA, Laserfiche WebLink SPA, and the Cloudflare-gated tax-deed sales list — all non-scrapable via plain HTTP | No fix applied — recommend Playwright follow-up targeting specifically the tax-deed sales list (correct data model), not ShowCase/Laserfiche (wrong data model) |
| baker A | re-attempt if new evidence | No new evidence (still no FIRECRAWL_API_KEY in this session, bakerclerk.com still WAF-blocked) | Correctly not re-attempted per "no retry without new evidence" |

## Verification Evidence (live, this session)

**Before (from dispatch brief, run2820):**
baker 9/10 · hillsborough 8/10 · gulf 7/10 · putnam 6/10 · collier 1/10

**After (live `pencil_dod_evaluate_county`, pasted verbatim, 2026-07-04):**

```
baker: 9/10 (unchanged — A honestly blocked, in-person clerk + WAF, no Firecrawl key)
{"A": {"pass": false, "detail": "fc=0 td=1", "metric": 0}, "B": {"pass": true, "metric": 100.0}, "C": {"pass": true, "metric": 100.0}, "D": {"pass": true, "metric": 100.0}, "E": {"pass": true, "metric": 100.0}, "F": {"pass": true, "metric": 100.0}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "metric": 1.0}, "I": {"pass": true, "metric": 100.0}, "J": {"pass": true, "metric": 100.0}, "auctions_total": 1}

hillsborough: 8/10 (unchanged score, C/D root-caused but genuinely blocked)
{"A": {"pass": true, "metric": 377}, "B": {"pass": true, "metric": 100.0}, "C": {"pass": false, "detail": "matched_clean=709", "metric": 77.4}, "D": {"pass": false, "detail": "matched_any=709", "metric": 77.4}, "E": {"pass": true, "metric": 97.8}, "F": {"pass": true, "metric": 100.0}, "G": {"pass": true, "metric": 98.7}, "H": {"pass": true, "metric": 0.1}, "I": {"pass": true, "metric": 96.3}, "J": {"pass": true, "metric": 97.3}, "auctions_total": 916}

gulf: 7/10 -> 8/10 (I regression caught + re-fixed)
{"A": {"pass": true, "metric": 3}, "B": {"pass": true, "metric": 100.0}, "C": {"pass": false, "detail": "matched_clean=6", "metric": 37.5}, "D": {"pass": false, "detail": "matched_any=6", "metric": 37.5}, "E": {"pass": true, "metric": 100.0}, "F": {"pass": true, "metric": 100.0}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "metric": 0.4}, "I": {"pass": true, "detail": "card_complete=16 of 16", "metric": 100.0}, "J": {"pass": true, "metric": 100.0}, "auctions_total": 16}

putnam: 6/10 -> 7/10 (E real fix; C/D honesty-purged, no score change)
{"A": {"pass": true, "metric": 37}, "B": {"pass": true, "metric": 100.0}, "C": {"pass": false, "detail": "matched_clean=6", "metric": 2.5}, "D": {"pass": false, "detail": "matched_any=6", "metric": 2.5}, "E": {"pass": true, "detail": "parcel_linked=229", "metric": 96.2}, "F": {"pass": true, "metric": 100.0}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "metric": 0.3}, "I": {"pass": false, "detail": "card_complete=220 of 238", "metric": 92.4}, "J": {"pass": true, "metric": 99.2}, "auctions_total": 238}

collier: 1/10 (unchanged, honestly re-confirmed blocked)
{"A": {"pass": false, "metric": 0}, "B": {"pass": false, "metric": null}, "C": {"pass": false, "metric": null}, "D": {"pass": false, "metric": null}, "E": {"pass": false, "metric": null}, "F": {"pass": false, "metric": null}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": false, "metric": null}, "I": {"pass": false, "metric": null}, "J": {"pass": false, "metric": null}, "auctions_total": 0}
```

Timestamp: 2026-07-04 (session live queries, UTC).

## What actually shipped (SQL VERIFICATION)

Migration: `supabase/migrations/20260704_shard5_gulf_i_regression_refix_putnam_cd_purge_e_fix.sql` (commit `9b3b4943`), applied LIVE via REST PATCH during this session, not just committed.

```sql
-- gulf I: parcel_id 'Property Appraiser' -> 'GULF-PA-000157CCAXMX-03' for case 232024CC000157CCAXMX
-- putnam C/D: 12 rows with parity_source='tier1_realforeclose_putnam' -> NULL/NULL
-- putnam E: 3 rows address-matched to real fl_parcels (co_no=64) folios
```

Row counts touched: gulf 1 row (+1 orphaned `parcel_zones` row deleted), putnam 12 rows nulled + 3 rows parcel-linked.

## Key discovery: fleet-wide `co_no` numbering bug (all shards should know)

`fl_parcels.co_no` is NOT the same scheme as `fl_counties.co_no`. Empirically confirmed (via `phy_city` cross-reference against known county seats) for all 5 shard counties:

| County | fl_counties.co_no | fl_parcels.co_no | Confirmed via |
|---|---|---|---|
| baker | 2 | 12 | Macclenny / Sanderson |
| hillsborough | 29 | 39 | Tampa / Odessa |
| gulf | 23 | 33 | Wewahitchka |
| putnam | 54 | 64 | Palatka / Hawthorne / Georgetown |
| collier | 11 | 21 | Naples |

Offset is a constant **+10** across all 5. `scripts/shard28_run338_e_parcel_linkage.py`'s `link_from_fl_parcels_by_address()` queries a nonexistent `fl_parcels.county_slug` column — it has always been a silent no-op. This offset likely blocks E/I linkage for other counties fleet-wide too; flagging for other shards rather than fixing beyond putnam's own rows (per PARALLEL-FLEET RULES scope).

## Regression caught (process finding, not just a county finding)

A same-day ultraloop_audit row (00:21:32Z) claimed gulf I was fixed and **independently verified** at PASS 16/16. Live query at this session's start proved that verification was itself false — the migration file was correct but was never actually executed against live data. **Lesson: "survived=true" in the audit table is not self-certifying across sessions — a fresh live re-check before trusting any prior claim is mandatory, not optional.** This session's regression check is now the template: always re-verify a prior PASS live before building on it.

## Deferred / structurally blocked (not attempted further, with reasons)

- **baker A**: in-person foreclosure sales, bakerclerk.com WAF-blocks scraping, no FIRECRAWL_API_KEY in this session. Needs a Firecrawl-enabled session.
- **hillsborough C/D**: 207 gap rows have zero evidence in `tax_deed_outcomes`/`foreclosure_outcomes` (checked case_number AND parcel_id, both tables, plus ILIKE substring spot-checks). Needs a genuine clerk-outcome ingestion pass, not a status-flip.
- **gulf C/D**: 6 rows are confirmed-synthetic bootstrap data with no real-world referent; 4 rows need a Playwright/headless-browser session against gulf.realforeclose.com's live calendar (plain HTTP returns a JS shell with no static data). Gulf's own clerk page confirms zero active tax-deed inventory right now.
- **putnam I**: 92.4% (220/238), needs address/geo/value backfill beyond what's quickly available (checked; the 3 remaining card-incomplete linked-parcel rows are blocked by missing `centroid_lat/lng` in `fl_parcels` itself, not something a quick REST patch can fix).
- **collier A**: 0 auctions. ShowCase and Laserfiche WebLink are both client-rendered SPAs (wrong data model anyway — court-records search / document portal, not a sale calendar). The one candidate with the right data model, `collierclerk.com/tax-deed-sales/search-upcoming-sales-list/`, is behind a Cloudflare bot-challenge that plain curl cannot pass. Recommend a Playwright follow-up targeting specifically that page.

## Ultraloop audit trail

9 rows logged to `gold_standard_ultraloop_audit` this session under `dispatch_id=d9210c60-335b-4a88-a422-0afee09d472b`, all `survived=true` (4 real fixes/purges verified before/after live; 5 honest BLOCKED re-confirmations from the parallel workflow's adversarial verify phase).

## Scoreboard skip

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were **not** run — another shard (SHARD-11, gadsden/okeechobee) pushed concurrently to `main` during this session, confirming other sessions were mid-flight. Reporting per-county `pencil_dod_evaluate_county` evaluations only, as instructed.
