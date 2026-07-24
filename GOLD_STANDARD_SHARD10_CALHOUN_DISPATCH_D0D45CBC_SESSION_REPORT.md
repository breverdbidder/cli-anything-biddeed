# Gold Standard shard-10: calhoun — dispatch d0d45cbc, loop run 6148

## Result: 7/10 → 8/10 — I flipped FAIL→PASS via real address backfill; B/F reconfirmed genuinely blocked, adversarially verified

| Letter | Before | After | Notes |
|---|---|---|---|
| A | PASS (fc=2 td=5) | PASS (fc=2 td=5) | Unchanged |
| B | FAIL null (verified=0 closed_sold=0) | FAIL null (verified=0 closed_sold=0) | Unchanged — genuinely no closed calhoun auction exists yet, verified live, see below |
| C | PASS 100.0 | PASS 100.0 | Unchanged |
| D | PASS 100.0 | PASS 100.0 | Unchanged |
| E | PASS 100.0 | PASS 100.0 | Unchanged |
| F | FAIL null (tier1_sold=0 closed_sold=0) | FAIL null (tier1_sold=0 closed_sold=0) | Unchanged — same root cause as B |
| G | PASS 100.0 | PASS 100.0 | Unchanged |
| H | PASS 0.9h | PASS 1.9h | Unchanged, healthy (daily cron confirmed running) |
| **I** | **FAIL 28.6 (2 of 7)** | **PASS 100.0 (7 of 7)** | **Flipped — real reverse-geocode address backfill, see below** |
| J | PASS 100.0 | PASS 100.0 | Unchanged |

**County status: 8/10.** Per PARALLEL-FLEET RULES (other shards mid-flight), did not run
`gold_standard_loop()`/`certify()` — verified per-county via `pencil_dod_evaluate_county('calhoun')`
before and after, live. Per ULTRALOOP PROTOCOL (ultracode opted in), ran one Workflow
(`gold-standard-shard10-calhoun-verify`, `wf_b4bba21c-1f4`) with 2 independent adversarial refuters
— one attacking the I-letter claim, one attacking the B/F-blocked claim. **Both claims SURVIVED.**
Logged 3 rows to `gold_standard_ultraloop_audit` (ids 9147-9149, all `survived=true`).

## What happened

### Pre-flight: confirmed the brief's baseline live, found a stale prior claim
`pencil_dod_evaluate_county('calhoun')` at session start matched the brief exactly: I=28.6%
(card_complete=2 of 7). Direct query isolated the exact gap: all 7 calhoun auctions already had
real lat/lng, an assessed/market value, and a zoned+linked parcel_id (the
`20260711g_gold_standard_calhoun_g_i_fabrication_purge_and_density_backfill.sql` migration had
already fixed G and cleaned up 20 fabricated `parcel_zones` rows) — the *only* blocking condition
across the 5 failing rows was `property_address IS NULL`.

**Flagged, not silently trusted:** that same 2026-07-11 migration's commit comment explicitly
claimed "I: card_complete=2 of 7 -> 7 of 7 (100%)... side effect of removing 20 orphaned duplicate
rows." That claim does not hold today — re-verified live before touching anything, still 2 of 7.
Logged as a discrepancy in the new migration's comments rather than repeated.

### I: FAIL 28.6% → PASS 100.0% (real fix)
The 5 rows missing `property_address` (621 OF 2026, 171 OF 2023, 227 OF 2024, 546 OF 2024, 268 OF
2023) all originate from `calhoun_clerk_scrape` (calhounclerk.com foreclosure/tax-deed calendar
pages), which publishes parcel ID + judgment/opening-bid but not always a street address for
tax-deed cards. Their lat/lng, however, were already real and already passing E/G checks.

Reverse-geocoded each of the 5 coordinates via OpenStreetMap Nominatim (public API, no key). All 5
independently resolved inside Calhoun County, FL (cross-checked against Alabama risk explicitly —
`gis.calhouncounty.org`, the first GIS candidate found by web search, turned out to be **Calhoun
County, Alabama**, caught via its own `documentInfo.Keywords` field before any query was run
against it, and discarded). Two of the five (171 OF 2023, 268 OF 2023) are road-level only (no
house number) — expected for unaddressed rural parcels, disclosed as such rather than inventing a
house number.

Migration `supabase/migrations/20260724_shard10_calhoun_i_address_backfill.sql` applied live via
the Supabase Management API (direct `psql`/pooler access is not reachable from this sandbox;
Management API + PostgREST is the working path, consistent with prior shard sessions' scripts).
Committed to main as `f210633d`.

### B/F: reconfirmed genuinely blocked, not a pipeline bug
All 7 calhoun auctions are `upcoming` or `cancelled`; `sold_amount`/`tier1_sold_amount` are NULL
for all 7. Checked three independent live sources beyond the DB:
- `calhounclerk.com` foreclosure + tax-deed-sales listings (WP REST custom-post-type endpoints
  `wp-json/wp/v2/foreclosures` and `wp-json/wp/v2/taxdeeds` — more reliable than the existing
  scraper's HTML regex, see note below) — no case shows a sold/closed status.
- `calhounclerk.com/county-recorder/tax-deed-surplus/` overbid list (`wp-json/wp/v2/taxdeedoverbids`,
  39 records) — none of calhoun's 5 tax-deed parcel_ids appear.
- Case `171 OF 2023`'s sale date (2026-07-09) has already passed as of this session (2026-07-24),
  but the clerk's own status field still reads `"scheduled"` — the county hasn't posted an outcome
  yet. Nothing to record without fabricating a sale.

No calhoun auction has actually closed. Out of scope for a data fix this session per HARD
GUARDRAILS (no fabricated `sold_amount`). The existing daily harvester
(`.github/workflows/calhoun-clerk-harvest.yml`, cron `45 5 * * *`) is confirmed healthy — 5
consecutive daily green runs — and will pick up a real sale the moment the clerk posts one; H's
1.9h freshness confirms it ran this morning before this session started.

**Flag for a future session (not implemented — out of scope, no letter to move by doing it now):**
`scripts/calhoun_clerk_harvest.py` scrapes via fragile HTML regex (its own docstring documents a
prior silent breakage when the tax-deed page's markup changed). This session discovered
calhounclerk.com exposes a proper WP REST API (`/wp-json/wp/v2/{foreclosures,taxdeeds,
taxdeedoverbids}`) that would be materially more robust, and additionally exposes the overbid/
surplus list which the current harvester never reads at all. Worth a future session wiring the
harvester onto the JSON API and adding surplus-list matching so B/F auto-resolve the instant
calhoun's first sale posts, without needing another manual session to notice.

## Adversarial verification (ULTRALOOP, ultracode fallback mode)

Two independent refuter agents, each with live DB + live web access, tried to break the two claims
above. Both returned **SURVIVED**:

- **I claim**: confirmed denominator unchanged (7), confirmed no duplicate/placeholder addresses,
  independently re-geocoded 2 of 5 coordinates and got an exact match, confirmed pre-existing
  fields (parcel_id, value) were untouched by the migration, confirmed the RPC result live and
  fresh.
- **B/F claim**: confirmed all 7 rows null via direct query (plus an `ilike` check ruling out a
  county-casing/whitespace matching bug), independently re-fetched the WP REST endpoints and
  matched every specific data point in the claim (the 39-record overbid count, the 171 OF 2023
  "scheduled despite passed date" detail), found no closed sale being silently ignored.

Logged to `gold_standard_ultraloop_audit`: 3 rows (letter I, B, F), `ultraloop_mode='fallback'`
(native `/effort ultracode` menu was not invoked from this chat context; used direct Workflow
fan-out + adversarial-refuter pattern per the protocol's fallback branch), all `survived=true`.

## Verification protocol (before/after JSON)

**Before** (session start, matches dispatch brief exactly):
```json
{"A":{"pass":true,"metric":2,"detail":"fc=2 td=5"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100.0,"detail":"matched_clean=7"},
 "D":{"pass":true,"metric":100.0,"detail":"matched_any=7"},
 "E":{"pass":true,"metric":100.0,"detail":"parcel_linked=7"},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000="},
 "H":{"pass":true,"metric":0.9,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":false,"metric":28.6,"detail":"card_complete=2 of 7"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=7 (triangle + two-arm CMA + ml_score + max_bid)"},
 "county":"calhoun","auctions_total":7}
```

**After** (re-run live post-migration + post-verification):
```json
{"A":{"pass":true,"metric":2,"detail":"fc=2 td=5"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100.0,"detail":"matched_clean=7"},
 "D":{"pass":true,"metric":100.0,"detail":"matched_any=7"},
 "E":{"pass":true,"metric":100.0,"detail":"parcel_linked=7"},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000="},
 "H":{"pass":true,"metric":1.9,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":true,"metric":100.0,"detail":"card_complete=7 of 7"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=7 (triangle + two-arm CMA + ml_score + max_bid)"},
 "county":"calhoun","auctions_total":7}
```

## Commits
- `f210633d` — `fix(gold-standard-shard10-calhoun): I letter address backfill via reverse-geocode`
  (`supabase/migrations/20260724_shard10_calhoun_i_address_backfill.sql`), pushed to main.

## Next-session priorities
1. B/F: watch for calhoun's first posted sale (171 OF 2023 is overdue for a status update from the
   clerk); no action possible until the county posts one.
2. Consider porting `calhoun_clerk_harvest.py` from HTML regex to the WP REST API
   (`wp-json/wp/v2/{foreclosures,taxdeeds,taxdeedoverbids}`) discovered this session — more
   robust, and adds surplus-list matching so B/F can auto-resolve without a manual session.
3. County is 8/10 — only B and F remain, both structurally blocked on real-world sale timing, not
   code. No further calhoun work is actionable until a sale posts.

dispatch_id: d0d45cbc-e63c-43a7-a634-baf9b247210a
