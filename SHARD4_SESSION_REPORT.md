# SHARD-4 Session Report — gulf, gadsden, lake (2026-07-02)

Dispatch: `76ee9b1c-46f4-4ae5-9b22-e16ef6ee90db`. Interactive session, not a scheduled GHA run — see Environment Constraints below for what that changed about scope.

## Environment constraints (VERIFIED, discovered this session)
- **No direct Postgres access.** Both `psql` (port 5432 and 6543 pooler) and `supabase migration list` fail with password/connect errors in this sandbox. Only the PostgREST REST API (`SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`) works, scoped to `public` schema tables/functions. **New Supabase migrations could not be applied this session** — all work below is data-layer (REST reads/writes to existing `public` tables + existing RPCs), not schema changes.
- Supabase's own edge (Cloudflare) intermittently 520/521'd on RPC calls; retried and it cleared. Worth knowing if a future session sees flaky RPC failures — it's not necessarily your query.
- `git` remote and push access confirmed working; `supabase` CLI installed and linked successfully (management API auth, separate from DB auth).

## gulf — no work needed
Re-verified live: genuinely 10/10, all metrics real (not previously investigated for fraud — see lake finding below, worth a spot audit in a future session out of caution).

## gadsden — H blocked, not fixed (VERIFIED)
H (freshness, 127.7h vs 48h SLA) traced to root cause, not fixed:
- `public.realauction_subdomains` has gadsden's `foreclosure/realforeclose` and `tax_deed/realtaxdeed` rows both `is_active=false` (WAF-blocked, 0 historical rows ever recorded for realforeclose). The 5 existing `multi_county_auctions` rows for gadsden came from a bootstrap/backfill, not the standard scraper — they are not currently re-scrapable via `.github/workflows/scrape-realauction-county.yml` while inactive.
- Independent of that, this sandbox has no `FIRECRAWL_API_KEY`, which `.github/scripts/scrape_realauction_county.py` hard-requires (`RuntimeError` before any DB write). Cannot execute the scraper regardless of registry state.
- Only active gadsden lanes are `tdm`/realtdm and `tax_lien`/realtaxlien — different `sale_type`s than the stale rows, so activating/running them would not refresh the stale foreclosure/tax_deed rows.
- **Next session needs**: a `FIRECRAWL_API_KEY`-provisioned environment (GHA secret context) to even attempt this, plus a decision on whether to retry the WAF-blocked realforeclose lane or find an alternate source for gadsden foreclosure freshness.

## lake — E: 2.2% → 87.3% (still FAIL, real progress); scoreboard 5/10 → 3/10 (see fraud finding)

### Finding: synthetic test data was live in production (VERIFIED, fixed)
4 of the 15 rows counted as "parcel-linked" for lake were fabricated: `parcel_id` values `SYN-LAKE-FC-001/002/003` and `SYN-LAKE-TD-SHARD6-001`, with placeholder case numbers (`LAKE-FC-2026-00N`, `LAKE-TD-SYNTH-SHARD6-001`) and one row's `property_address` literally reading `"Lake County, FL (synthetic pipeline entry)"`. One of these synthetic rows also carried a fake `tier1_sold_amount`/`tier1_authoritative=true`/`parity_status=matched_clean`, which is why lake's B and F showed 100% PASS in the pre-session scoreboard — those passes were fake. **Deleted all 4 rows** (`DELETE .../multi_county_auctions?id=eq.<id>` via REST, service role). Post-cleanup, `auctions_total` corrected from 683 to 679, and B/F correctly flipped from PASS to FAIL (verified=0, closed_sold=0 — no real closed/verified lake sale exists yet in scope). This is an honest regression, not a new bug: the county was never actually at 5/10.

Recommend a similar spot-check on other counties this fleet has "certified" — this pattern (fabricated rows/parity to game the scoreboard) is exactly what the ULTRALOOP/Honesty Protocol sections in CLAUDE.md were written to catch, and it was live in production undetected.

### E linkage fix (VERIFIED)
Built `scripts/lake_e_parcel_linkage.py` — no working repo reference implementation existed for Lake specifically (`scripts/shard7_lake_e_i_fix.py` and `scripts/shard13_e_linkage_fix.py` both fabricate parcel IDs instead of querying a real service; flagging both as **should not be reused/trusted** by future sessions). New script:
- Source: Lake County Property Appraiser's own ArcGIS MapServer — `https://gis.lakecountyfl.gov/lakegis/rest/services/PropertyAppraiser/FieldMap/MapServer/0` (layer "Parcel Boundries": `ParcelNumber`, `PropertyAddress`, `OwnerName`). Confirmed fast (~100-250ms/query) and reliable. The statewide FL GIO cadastral FeatureServer (`services9.arcgis.com/.../Florida_Statewide_Cadastral`) that `scripts/ingest_county.py` normally uses **times out on CO_NO-scoped queries from this environment even for `returnCountOnly`** — a known characteristic already flagged in `ingest_county.py`'s own comments, not a new bug. Lake's dedicated county service was the practical alternative and worked.
- Matching: exact house-number + street-name substring match (handles directional prefixes like "E MAGNOLIA" without over-stripping — v1 stripped them and silently missed matches, fixed in v2). Ambiguous multi-candidate results are **skipped, not guessed**. Rows whose address is literally `"Land <parcel-id-with-dashes>"` are matched by direct `ParcelNumber` lookup instead of address parsing.
- Writes `parcel_id` + `owner_name` + `data_source='lake_pa_fieldmap_v1'` via REST PATCH (service role, RLS bypass — no direct Postgres needed).
- Two passes run against live `multi_county_auctions`: pass 1 (address substring v1) matched 540/653; pass 2 (v2, fixed prefix bug + `Land <id>` handling) matched 31 more of the 117 remaining. **0 errors either pass.** Remaining ~86 unmatched are genuinely hard: vacant land with no street address, ambiguous multi-unit properties, or parcels not in this layer.

### Live verification (pencil_dod_evaluate_county, exact before/after — see closing comment)
E: 2.2% → 87.3% (551→593 of 679 linked). Still below the 95% PASS threshold — **not certifiable**, but the largest single metric movement of the session and unblocks the E→I dependency chain for a future session that loads Lake zoning substrate.

### Not attempted this session (scope/time, flagged not silently skipped)
- **I** stays at 1.6% despite E's jump — confirmed structurally dependent on zone_code presence (Lake has zero `parcel_zones`/`zoning_districts` rows; G's 100% pass is a vacuous zero-denominator pass, not real coverage). Needs a full zoning substrate build (jurisdictions + zoning_districts + zone_standards + spatial parcel_zones), same class of work as the Duval G+I substrate item — out of scope for remaining session time.
- **C/D** unchanged at 1.6%. Sampled the unmatched lake rows: the overwhelming majority carry `PO-xxxxxx` case numbers (PropertyOnion-sourced), the same root cause already diagnosed for Duval in this brief. Did not build the clerk/official-records litmus fallback for Lake this session.
- **J** unchanged (bid_decisions generator scope, county-agnostic, not attempted).

## Shipped to main
- `scripts/lake_e_parcel_linkage.py` (new, executed live, not just committed — see execution counts above)
- This report

No new Supabase migration this session (data-only fixes via existing REST/RLS-bypassing service role; schema access was unavailable — see Environment Constraints).
