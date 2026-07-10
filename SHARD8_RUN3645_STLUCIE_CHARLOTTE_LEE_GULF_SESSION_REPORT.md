# SHARD-8 run3645 — st_lucie / charlotte / lee / gulf

dispatch_id: `d8ed4911-53fc-411a-825a-802dda1ae109`

## Status board (BEFORE brief baseline → AFTER, live `pencil_dod_evaluate_county`, independently re-verified by the session, not just pasted from the fix agents)

| County | Letters PASS (before) | Letters PASS (after) | Notes |
|---|---|---|---|
| st_lucie | 9/10 (I fails) | 9/10 (I fails) | Unchanged. Root-caused, no fabrication attempted — see below. |
| charlotte | 7/10 (B, C, D fail) | **9/10** (B fails) | **C and D flipped PASS** (16.5%→97.1%). |
| lee | 6/10 (C, D, E, I fail) | 6/10 (C, D, E, I fail) | No letter flipped, but I materially improved (71.4%→86.4%); G dropped 100.0%→97.8% (still passes) as a disclosed side effect. |
| gulf | 3/10 (E, G, H, J pass) | 3/10 (G, H, J pass) | **E flipped PASS→FAIL** (100%→40%) — this is a correction, not a regression: 3 of 5 parcel_id values were fabricated-looking placeholders, confirmed and purged. H flipped FAIL→PASS as a side effect of a DB trigger, not a real freshness fix (flagged explicitly, see below). |

Also fixed, infra-level: `.github/workflows/run-sql-migration.yml` was silently broken since 2026-07-03 (still wired to the dead `SUPABASE_DB_PASSWORD` instead of `SUPABASE_ACCESS_TOKEN`) — 5/5 recent dispatches had failed. Fixed and verified live before any county work began (`2e7a4a2c`).

## What actually moved this session (ULTRALOOP-verified: fan-out fix per county in an isolated worktree, then an independent refuter agent per county — all 4 claims SURVIVED, logged to `gold_standard_ultraloop_audit` ids 4505–4506 for charlotte C/D)

### charlotte C/D: 16.5% → 97.1% (17/103 → 100/103)
Script: `scripts/shard8_charlotte_litmus_run.py`. Root cause was a pure **wiring gap**, not a data gap: 86 of 103 rows had `parity_status IS NULL` because they had never been run through any litmus matcher. `scripts/shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py` already defined the needed harvest/match helpers but its `__main__` never actually invoked them for charlotte. Live-harvested all 52 unmatched foreclosure dates plus discovered — live, not assumed — that charlotte's tax-deed sales also run on `charlotte.realforeclose.com` rather than a separate platform (`pipeline.counties.taxdeed_platform` is still NULL for charlotte, flagged as a residual wiring gap for whoever owns that config). Promoted 83 rows to `matched_clean` via exact case-number match against live AJAX data. Self-caught a mid-session mistake: the first-pass `parity_source` label didn't match the RPC's `LIKE 'tier1%'` filter, so the fix was invisible until re-verified and relabeled.

3 remaining rows are PropertyOnion-origin and correctly left unmatched (PropertyOnion may never be the basis for a parity promotion). 100/103 = 97.1%, both C and D now pass.

Refuter (independent agent, fresh RPC call): confirmed C/D pass at 97.1%, matched_clean/any=100, no anomalous ratio, no regression on A/E/F/G/H/I/J, B correctly still failing/untouched. **SURVIVED.**

### charlotte B: investigated, not moved (50.0%, 2/4)
The 2 unresolved closed_sold rows (25000552CA, 25000869CA) have no independent verified outcome anywhere in the DB. Confirmed live that `charlotte.realforeclose.com`'s static preview page has zero post-sale result markup (fully AJAX-gated) and `charlotteclerk.com` (reachable, HTTP 200) requires a JS-driven session to search by case number — a real scraper/session-automation build, out of scope for this bounded pass. Reported as residual, not attempted with a shortcut.

### lee I: 71.4% → 86.4% (195/273 → 236/273), C/D/E unchanged
Script: `scripts/lee_shard8_parcel_zones_backfill.py`. First re-checked the campaign brief's stated root cause (PO-prefixed case_numbers blocking C/D/E) against the RPC's own scoping clause — **it does not hold**: all 2,818 PO-prefixed rows carry `data_source='propertyonion'` and are already excluded from the 273-row DoD scope. Reported this discrepancy rather than chasing it. The real gap: 53 in-scope rows had a genuine `parcel_id` but no `parcel_zones` row. Queried Lee County's live ArcGIS Parcels FeatureServer by STRAP, matched 51/51 unique straps live, inserted 49 `parcel_zones` rows (2 skipped — ArcGIS returned empty ZONING, not fabricated).

**Self-caught regression:** G collapsed live from 100.0%→0.0% immediately after the insert (4 newly-linked parcels resolved to a Fort Myers zone code with no `zoning_districts` row — a failure mode already documented in `lee_enrich_shard14.py`'s comments from a prior session). Fixed by adding the missing `zoning_districts`/`zone_standards` rows (mirroring existing conventions for comparable zones), re-verified G back to 97.8% (still passes; the residual 2.2-point gap is a pre-existing NULL-density data gap at 3 Fort Myers zone_standards rows, exposed for the first time rather than created). Also fixed a latent substring bug in `lee_enrich_shard14.py`'s jurisdiction map ("north fort myers" matching the "fort myers" substring key, mis-assigning unincorporated parcels).

Migration: `supabase/migrations/20260710_shard8_lee_parcel_zones_backfill_and_929rs1_gfix.sql`.

Refuter: fresh RPC confirms I=86.4% (up from 71.4%), G=97.8% (still passes, disclosed drop from 100%), C/D/E unchanged as claimed, no other regression. **SURVIVED** (as material progress on I's metric — no letter flipped, reported honestly as such).

### gulf E: 100% → 40% (5/5 → 2/5) — a correction, not a regression
Confirmed 3 of gulf's 5 `parcel_id` values were not real: `"Property Appraiser"` is literally scraped UI anchor-text from the `gulf.realforeclose.com` splash/login-gate page (verified via live curl of the exact page); `"GULF-PA-000060CAAXMX-02"` / `"GULF-PA-000072CAAXMX-01"` are synthetic case-number-derived strings that don't match Gulf's real folio format (cross-checked against gulf's own 2 legitimate parcel_ids and against calhoun/franklin's differently-formatted real folios). Nulled all 3 via direct REST PATCH after exhausting live alternatives (gulfpa.com/qpublic.net Cloudflare-blocked, gulfcountypropertyappraiser.org reachable but the 2 affected rows have no real address — only a litigant-privacy "Address On File" placeholder — to search by, civitekflorida.com is a session/JS-driven form not fetchable via a single GET). This is the campaign's own stated purpose for the ULTRALOOP layer — catching exactly this pattern — so E's drop is reported as a correction.

Migration: `supabase/migrations/20260710_shard8_gulf_parcel_fabrication_purge.sql`.

**Also diagnosed, not fixed (H — flagging so the flip to PASS isn't misread):** gulf's real freshness problem is that `scripts/cairn_multi_county_scraper.py` has gulf configured as `platform='custom_clerk'` → `gulfclerk.com/foreclosure`, but `parse_custom_clerk()` is an unimplemented stub that always returns a probe-only result — confirmed live via `gh run view` on today's 08:11Z run. The scraper code deliberately withholds `last_seen_at` updates for probe-only results specifically to avoid ghost-success, which is why the column has been frozen at 2026-06-26 despite the job running daily without error — correct, pre-existing defensive design, not something this session broke or fixed. **H's flip to PASS in the after-JSON is a side effect**: `pencil_dod_evaluate_county` computes H from `GREATEST()` across 5 timestamp columns including `last_changed_at`, which a pre-existing DB trigger bumped when the parcel_id PATCH landed. The underlying scraper is still broken. Do not read gulf's H as fixed.

Refuter: fresh RPC confirms E=40.0% (2/5, matches claim), G/H/J unchanged pass, A/B/C/D/F unchanged fail (correctly untouched). No anomalous ratio. **SURVIVED.**

### st_lucie: investigated, no write made
Root-caused letter I via `pg_get_functiondef('public.pencil_dod_evaluate_county')`: the RPC joins directly to `v_zoning_gold_standard_card` (parcel_zones-backed), not to `v_auction_property_card.zoning_code` as this session's initial hypothesis assumed — that hypothesis is now a confirmed dead end, not a fix path. Of the 10 failing rows: 7 have a real, correctly-formatted `parcel_id` that simply does not exist in St Lucie's `parcel_zones` table (213 St Lucie parcels ingested total — a genuine zoning-coverage gap); 3 are same-day fresh calendar-sweep rows with no BCPAO/geocode enrichment at all (no St Lucie-scoped enrichment table exists anywhere in the schema, unlike Brevard's `bcpao_results`). Both require a real scraper/ETL build, out of scope for this bounded pass. One apparent duplicate case_number (`26-001`) was checked and confirmed to be two genuinely distinct, independently-sourced auctions (a foreclosure docket and a tax-deed sale) that happen to share a short case string — left untouched; deleting either would have destroyed real data.

**Honesty flag (not St Lucie-specific):** St Lucie's G currently passes at 100% but this is a **vacuous pass** — FAR and parking-per-1000 have 0 applicable parcels out of 213 (both sub-metrics are NULL), and Postgres `LEAST()` silently drops NULL arguments, so the RPC's `LEAST(density, far, pk1000)` collapses to just the density component. This is a shared-RPC scoring characteristic (same pattern previously flagged for Brevard/Duval), not unique to St Lucie, and was deliberately **not** touched — editing the shared `pencil_dod_evaluate_county` mid-session would affect every other shard's county concurrently. Flagging for whoever owns cross-county RPC maintenance.

## Residual gaps confirmed genuine this session (no fabrication attempted)

- **st_lucie I** (87.8%, 72/82): 7 rows need expanded St Lucie zoning-parcel ingestion; 3 rows need a St Lucie BCPAO/appraiser enrichment pipeline (does not exist today). Both are real scraper builds.
- **charlotte B** (50.0%, 2/4): needs either an authenticated RealAuction session or a `charlotteclerk.com` session-automation integration. Sized at ~1-2 hours for a future session with credentials or Firecrawl-browser.
- **charlotte**: `pipeline.counties.taxdeed_platform`/`taxdeed_url` still NULL despite tax-deed sales confirmed live on `charlotte.realforeclose.com` — any future job branching on that config will keep skipping charlotte tax-deed rows.
- **lee C/D** (91.6%/91.9%): 21 rows have a real parcel_id but zero matching `foreclosure_outcomes` rows — all recent/future auction dates the tier1 harvester hasn't processed yet. Needs a harvester run, not a data fix. Case numbers listed in the raw workflow output.
- **lee E/I**: 25 rows have `parcel_id IS NULL` (22 have no address at all; 3 mobile-home-park lot addresses don't match Lee's ArcGIS parcel layer by address). 2 straps returned empty ZONING live. 1 row has literal `parcel_id='MULTIPLE PARCEL'` (needs manual disambiguation). None fabricated.
- **lee G** (97.8%, still passes): 3 pre-existing Fort Myers zone_standards rows (RS-6, RS-7, PUD) have `max_density_du_acre=NULL` — a data-quality gap that predates this session, exposed for the first time by the new parcel links.
- **gulf A/B/C/D/F**: untouched, correctly still FAIL. Gulf's real scraper gap (`custom_clerk` stub vs the actual `gulf.realforeclose.com`/`gulfclerk.com` sources) is sized in the fix_summary above; building either is a genuine new-scraper task.
- **gulf E residual** (2 of 5 still unlinked): both have only an "Address On File" privacy placeholder — no address/owner to look up against any appraiser site. Needs an authenticated realforeclose session or a manual clerk case-file pull.

## Infra fix (unblocks future sessions fleet-wide)

`fix(infra): wire run-sql-migration.yml to SUPABASE_ACCESS_TOKEN` — the generic SQL-migration-dispatch workflow had been dead since 2026-07-03 (100% failure rate on its last 5 runs, silently, because it still passed the retired `SUPABASE_DB_PASSWORD` secret into a script that had already been switched to the Management API). Verified the Management API path directly before landing the fix. This was blocking every shard's ability to apply schema-changing migrations via the standard dispatch path.

## Verification protocol compliance

All 4 before/after pairs above were independently re-confirmed by this session via a fresh `pencil_dod_evaluate_county` call per county (not just the pasted values from the fix agents), matching the fix agents' own after-JSON exactly. 2 ULTRALOOP audit rows logged (charlotte C, D — the only letters that flipped PASS this session) to `gold_standard_ultraloop_audit` (ids 4505–4506, `ultraloop_mode='fallback'`, ` survived=true`). Did not run `gold_standard_loop()` or `gold_standard_certify()` — other shards (shard6, confirmed via concurrent commits on main) were mid-session.
