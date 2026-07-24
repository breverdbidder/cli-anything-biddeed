export const meta = {
  name: 'gold-standard-shard9-okaloosa-run6080',
  description: 'Gold Standard okaloosa-only (loop run 6080, dispatch f8de10ec): fabrication-guard fix, B/C/D/E/I/G real-data fixes, adversarial verify',
  phases: [
    { title: 'Fix', detail: 'sequential real-data fixes, one work-package at a time' },
    { title: 'Verify', detail: 'parallel independent refuter per letter' },
  ],
}

const DISPATCH_ID = 'f8de10ec-e7af-4ac2-9af7-6b7dd80c3809'
const COUNTY = 'okaloosa'

const BASELINE = `LIVE-VERIFIED baseline (pencil_dod_evaluate_county, just queried, matches the session brief exactly):
auctions_total=57. PASS: A=28(fc=29,td=28), F=100.0(tier1_sold=5,closed_sold=5), H=7.4h, J=100.0(57/57).
FAIL: B=80.0(verified=4,closed_sold=5), C=89.5(matched_clean=51), D=93.0(matched_any=53), E=89.5(parcel_linked=51),
G=75.6(density=75.6 far=100.0 pk1000=100.0), I=63.2(card_complete=36 of 57).
Thresholds (from pencil_dod_criteria, all >=95 except B which is a 95-105 BAND and H which is <=48h):
C/D/E/I/G need >=95% i.e. >=55/57. B needs the verified/closed_sold ratio in [95,105].`

const RECIPE = `
Environment (already available, do not ask for credentials):
- REST API reads/writes: GET/PATCH \${SUPABASE_URL}/rest/v1/<table>?... with headers
  apikey: $SUPABASE_SERVICE_ROLE_KEY, Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY
- Live arbitrary SQL (verified working this session): POST
  https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query
  headers Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json
  body {"query": "<sql>"} -- run "SET statement_timeout = 0;" first in the same query string for anything heavy.
  IMPORTANT: build this JSON with a real JSON encoder (python3 -c "import json; ..." to a temp file, then
  curl --data-binary @file) rather than hand-quoting shell strings.
- pencil_dod_evaluate_county RPC: POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county
  headers apikey/Authorization as above, body {"p_county": "okaloosa"} -- your before/after proof.
- gh CLI is authenticated (repo, workflow scopes).
- Repo root is the current working directory (cli-anything-biddeed, on main, worktree-isolated for you).
  Before starting: git pull --rebase origin main (a prior work-package in this same session may have already
  pushed -- you must build on top of it, not overwrite it). Schema changes go in
  supabase/migrations/<date>_shard9_okaloosa_<purpose>.sql, committed. Simple data PATCH/UPDATEs don't need a
  migration file -- just note the exact SQL/endpoint used in your report.
- Push directly to main when done. No branches, no PRs (SHIP-TO-MAIN MANDATE). If push is rejected (another
  push landed), git pull --rebase origin main and retry.

ULTRALOOP audit logging (mandatory): for every letter you claim moved (or claim genuinely blocked/residual),
INSERT one row into public.gold_standard_ultraloop_audit: columns dispatch_id (uuid '${DISPATCH_ID}'),
ultraloop_mode ('fallback' -- manual Task subagent fan-out via Workflow, not native /effort ultracode),
county_slug ('okaloosa'), letter, claim (short text), refuter_evidence (jsonb -- your before/after evidence),
survived (boolean -- true only if you are confident it holds up; the Verify phase will independently re-check).
POST \${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with service-role headers.

Hard rules:
- You own ONLY okaloosa. Never touch another county's rows. If you must edit a SHARED script file (one that
  loops over multiple counties), scope your code change narrowly to okaloosa's entry/branch only -- do not
  remove or alter behavior for other counties, and say so explicitly in your report so other shards aren't
  surprised.
- PropertyOnion is litmus/comparison ONLY -- never write po_* derived values in as if verified/independent.
- Fail-loud invariant: if a fix attempt finds zero real data, report it as a blocked/residual gap. NEVER
  fabricate case numbers, parcel IDs, sale amounts, coordinates, or timestamps to make a metric look better.
  okaloosa has THE heaviest ghost-success history in this entire campaign (multiple prior purges document a
  full purge-and-restart from a 6/10 ghost score down to 1/10 honest). This session already found a LIVE,
  currently-scheduled fabrication bug (see FIX 1) -- be paranoid about repeating any variant of it.
- Every claim you return must be tagged VERIFIED (you ran the query/request and are pasting real output),
  UNTESTED, or INFERRED (say why).
- Do NOT run public.gold_standard_loop() or gold_standard_certify() -- other shards may be mid-session. Do NOT
  modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job.
- Budget yourself: this is ONE bounded work-package, not the whole session. If a true fix needs a from-scratch
  build beyond what's described, size the gap precisely and report it as a scoped residual instead.

Return a structured report: { letters_touched: [...], fix_summary, sql_or_endpoints_used: [...], before_json,
after_json, residual_gaps: [...], honesty_notes: [...] }.
`

phase('Fix')

const fix1 = await agent(
  `You are working Gold Standard, county "okaloosa" ONLY, inside the cli-anything-biddeed repo (on main).\n\n${BASELINE}\n\n` +
  `WORK-PACKAGE 1 of 5: FABRICATION GUARD (do this FIRST, before any other okaloosa work -- it is actively ` +
  `corrupting data on a daily cron right now).\n\n` +
  `VERIFIED THIS SESSION: scripts/shard4_run472_main_executor.py, function phase_i_property_cards(), contains a ` +
  `hardcoded county_median dict with "okaloosa": 310000. It bulk-PATCHes multi_county_auctions SET ` +
  `assessed_value=310000, market_value=325500.0 (310000*1.05) on ANY okaloosa row where assessed_value IS NULL. ` +
  `This script is wired to a LIVE daily cron: .github/workflows/gold-standard-shard4-run472.yml, schedule 08:05 ` +
  `UTC daily. The SAME bug pattern was already caught and fixed for "bradford" in this exact function (see the ` +
  `comment block right above the county_median dict, dated 2026-07-10) -- bradford is excluded with a clear ` +
  `honesty comment, but okaloosa (and clay/nassau/flagler, NOT your concern, out of scope) were never excluded. ` +
  `CONFIRMED LIVE: exactly 19 of okaloosa's 57 rows currently carry assessed_value=310000 AND ` +
  `market_value=325500.0 -- an exact match to this formula, occurring across rows created from 2026-07-05 ` +
  `through 2026-07-23 (i.e. this cron has been re-fabricating on every run for real properties whose actual ` +
  `assessed value the harvester didn't capture). This makes I's card_complete metric partially rest on fake ` +
  `financial data -- NOT currently inflating the numerator (all 19 rows also lack geo so none pass card_complete ` +
  `today), but it WILL start silently ghost-passing I the moment a later work-package in this session adds real ` +
  `geo to those rows unless the fake value is purged first.\n\n` +
  `YOUR TASK:\n` +
  `1. Edit scripts/shard4_run472_main_executor.py: add "okaloosa" to the skip/exclusion path in ` +
  `phase_i_property_cards() the SAME way "bradford" is already excluded (skip with a clear comment referencing ` +
  `this fabrication finding). Do NOT change behavior for clay/nassau/flagler -- leave them exactly as-is (flag ` +
  `them as a residual honesty note for whichever shard owns them; do not fix them yourself, out of scope).\n` +
  `2. Purge the fabrication for okaloosa: SET assessed_value=NULL, market_value=NULL WHERE county='okaloosa' AND ` +
  `assessed_value=310000 AND market_value=325500.0 (verify the exact row count first with a SELECT count(*), ` +
  `expect 19 -- if it's a different number, stop and re-investigate before writing, do not blindly trust this ` +
  `prompt's number over what you observe live).\n` +
  `3. Update pipeline.counties.notes for okaloosa (append, don't overwrite) with a one-line dated honesty note ` +
  `documenting this fix.\n` +
  `4. Confirm via pencil_dod_evaluate_county that no letter regressed as a side effect of the purge (I was 63.2% ` +
  `before touching anything -- purging NULL values on rows that already failed card_complete should not move I ` +
  `at all; if it does move, understand why before proceeding).\n` +
  `5. git commit (county+purpose-scoped message), git pull --rebase origin main, push to main.\n\n${RECIPE}`,
  {
    label: 'fix1:fabrication-guard',
    phase: 'Fix',
    isolation: 'worktree',
    schema: {
      type: 'object',
      properties: {
        letters_touched: { type: 'array', items: { type: 'string' } },
        fix_summary: { type: 'string' },
        sql_or_endpoints_used: { type: 'array', items: { type: 'string' } },
        before_json: {}, after_json: {},
        residual_gaps: { type: 'array', items: { type: 'string' } },
        honesty_notes: { type: 'array', items: { type: 'string' } },
        rows_purged: { type: 'number' },
      },
      required: ['fix_summary', 'before_json', 'after_json'],
    },
  }
)

const fix2 = await agent(
  `You are working Gold Standard, county "okaloosa" ONLY, inside the cli-anything-biddeed repo (on main). ` +
  `git pull --rebase origin main FIRST -- a prior work-package in this session already pushed a fabrication-guard ` +
  `fix, you must build on top of it.\n\n${BASELINE}\n\n` +
  `WORK-PACKAGE 2 of 5: B (verified realized outcomes).\n\n` +
  `VERIFIED THIS SESSION: closed_sold=5 (rows with sold_amount IS NOT NULL). 4 of 5 already have a matching ` +
  `foreclosure_outcomes row (data_source not ILIKE '%promote%'): case_numbers 2024CC002856F, 2025-CA-002268-C, ` +
  `2025CA001112C, 2024CA002158F. The 5th, case_number='B4A-1291686', sale_type='tax_deed', sold_amount=1932.0, ` +
  `tier1_sold_amount=1932.0, auction_status='sold to plaintiff', source_url=` +
  `'https://www.bid4assets.com/OkaloosaFLTax/listings?salesdate=20260811', auction_date=2026-08-11, has NEITHER ` +
  `a tax_deed_outcomes NOR foreclosure_outcomes row.\n\n` +
  `ROOT CAUSE (VERIFIED, read scripts/okaloosa_bid4assets_harvest.py yourself to confirm): the FC lane (around ` +
  `line 238) appends to outcome_rows and upserts them into foreclosure_outcomes when sold_amount is set. The TD ` +
  `lane (around line 251-292) builds the sold_amount/tier1_sold_amount fields on the auction row itself but NEVER ` +
  `appends anything to outcome_rows -- there is no tax_deed_outcomes mirroring at all in this script. That is why ` +
  `every TD sold case silently never gets an independent outcome row, capping B below 100% whenever any TD case ` +
  `closes.\n\n` +
  `YOUR TASK:\n` +
  `1. Fix scripts/okaloosa_bid4assets_harvest.py: in the TD lane, when sold_amount is not None, append a record ` +
  `to a new td_outcome_rows list (case_number, county='okaloosa', sale_type='tax_deed', auction_date, ` +
  `outcome='sold', winning_bid=sold_amount, parcel_id=apn, property_address=clean_address, ` +
  `data_source='bid4assets_scrape:SHARD3-OKALOOSA-V1', source_url). Add a matching upsert_outcomes_td() writing ` +
  `to tax_deed_outcomes with on_conflict=case_number,county,auction_date (check the table schema yourself first: ` +
  `column is "winning_bid" not "sold_amount" -- SELECT column_name FROM information_schema.columns WHERE ` +
  `table_name='tax_deed_outcomes'). Wire it into main().\n` +
  `2. Backfill the ONE existing gap row (B4A-1291686) directly: this is legitimate mirroring of data ALREADY on ` +
  `the tier1_authoritative=true auction row (not new fabrication) -- INSERT INTO tax_deed_outcomes ` +
  `(case_number, county, auction_date, outcome, winning_bid, data_source, source_url) using the exact values ` +
  `already on the multi_county_auctions row (case_number='B4A-1291686', county='okaloosa', ` +
  `auction_date='2026-08-11', outcome='sold', winning_bid=1932.0, data_source='bid4assets_scrape:` +
  `SHARD3-OKALOOSA-V1', source_url from the row). Write a migration file for this insert.\n` +
  `3. Verify B via pencil_dod_evaluate_county -- expect verified=5, closed_sold=5, ratio=100.0, PASS. If the ` +
  `evaluator's B band is [95,105], confirm you land inside it, not just >=95.\n` +
  `4. git commit, git pull --rebase origin main, push to main.\n\n${RECIPE}`,
  {
    label: 'fix2:B-outcomes',
    phase: 'Fix',
    isolation: 'worktree',
    schema: {
      type: 'object',
      properties: {
        letters_touched: { type: 'array', items: { type: 'string' } },
        fix_summary: { type: 'string' },
        sql_or_endpoints_used: { type: 'array', items: { type: 'string' } },
        before_json: {}, after_json: {},
        residual_gaps: { type: 'array', items: { type: 'string' } },
        honesty_notes: { type: 'array', items: { type: 'string' } },
      },
      required: ['fix_summary', 'before_json', 'after_json'],
    },
  }
)

const fix3 = await agent(
  `You are working Gold Standard, county "okaloosa" ONLY, inside the cli-anything-biddeed repo (on main). ` +
  `git pull --rebase origin main FIRST -- prior work-packages already pushed.\n\n${BASELINE}\n\n` +
  `WORK-PACKAGE 3 of 5: C/D/E (parity + parcel linkage) -- these three share the exact same 6-row gap.\n\n` +
  `VERIFIED THIS SESSION: the 6 rows with parcel_id IS NULL or not (matched_clean AND tier1 parity):\n` +
  `1. case '2024-CA-000470' (FC, upcoming): parcel_id/address/geo/parity all NULL, data_source NULL, ` +
  `assessed_value was a fabrication (see fix1) now purged. This is a documented STALE PLACEHOLDER -- confirmed ` +
  `absent from the live Bid4Assets platform across 3+ prior sessions (search git log for "2024-CA-000470" for ` +
  `the full history). Do NOT attempt to backfill; leave as an honest residual.\n` +
  `2. case '2024-TDD-000089' (TD, upcoming): same as above -- documented stale placeholder, same treatment.\n` +
  `3. case '2025-CA-002043-F' (FC, stayed): HAS address '2419 EDGEWATER DR' + real geo (30.5079727738733, ` +
  `-86.4433887518738), currently parity_status='matched_divergent' (parcel_id still NULL). Real, recoverable.\n` +
  `4. case '2025-CA-002956-C' (FC, preview): address '414 CHICKADEE STREET, CRESTVIEW, FL 32539', no geo yet, ` +
  `parcel_id NULL, no parity. Real, recoverable.\n` +
  `5. case '2025-CA-003450-C' (FC, preview): address '4320 Cooper Lance, Holt, FL 32564' + real geo ` +
  `(30.6975426263878, -86.7685616271071), parity_status='matched_divergent', parcel_id NULL. A PRIOR session's ` +
  `script (scripts/shard4_run472_okaloosa_cei_g_fix.py equivalent, never merged) flagged this one as ` +
  `"known_unresolvable_separate_agent" without explaining why -- re-investigate fresh, do not assume it's ` +
  `actually unresolvable just because a prior unmerged attempt punted on it.\n` +
  `6. case '2025CA000832F' (FC, preview): address '1201 WALTER AVE, CRESTVIEW, FL 32536', no geo, parcel_id ` +
  `NULL, no parity. Real, recoverable.\n\n` +
  `THE LEVER: okaloosa's real parcel/address GIS layer is confirmed live: ` +
  `https://okgis.myokaloosa.com/arcgis/rest/services/Land-Ownership/Parcels_with_Addressing/MapServer/121/query ` +
  `-- outFields PIN,SITE_ADDR,TOTALAPPR,ASSEDVAL, query by "SITE_ADDR LIKE '<street-number+name>%'". A prior ` +
  `unmerged session (branch claude/issue-12952-20260721-1601, scripts/shard4_run5668_okaloosa_cei_g_fix.py) ` +
  `wrote working address-normalization + GIS-match logic for exactly this problem (street suffix/directional/unit ` +
  `parsing, centroid-from-geometry-rings) -- fetch it with ` +
  `"git show origin/claude/issue-12952-20260721-1601:scripts/shard4_run5668_okaloosa_cei_g_fix.py" and adapt/reuse ` +
  `its _street_prefixes/_gis_query/_centroid logic rather than writing from scratch (it was never executed or ` +
  `verified live -- treat it as a starting point, not ground truth; verify every match it produces).\n\n` +
  `YOUR TASK: for cases 3-6, resolve a real parcel_id via SITE_ADDR match against the GIS layer above (a single ` +
  `confident match only -- if the address query returns 0 or >1 results, do not guess, report as unresolved). On ` +
  `a confident match, PATCH multi_county_auctions: parcel_id=PIN, and if not already present, latitude/longitude ` +
  `from the feature geometry centroid, assessed_value/market_value from ASSEDVAL/TOTALAPPR (only if currently ` +
  `NULL -- do not overwrite anything real). Set parity_status='matched_clean', ` +
  `parity_source='tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:` +
  `shard9_okaloosa_run6080'. For case '2025-CA-003450-C' specifically, actually attempt the match (don't just ` +
  `re-flag it unresolvable) -- if it genuinely fails, state the concrete reason (0 results / ambiguous / etc).\n\n` +
  `Verify C, D, E via pencil_dod_evaluate_county. If all 4 real cases resolve: C 51->55/57=96.5%% PASS, ` +
  `D 53->57/57=100%% PASS (E was matched_divergent already for 2 of them so D's baseline may differ slightly -- ` +
  `just verify live), E 51->55/57=96.5%% PASS. If fewer resolve, report the exact count and resulting metric ` +
  `honestly -- do not round up.\n\n` +
  `git commit, git pull --rebase origin main, push to main.\n\n${RECIPE}`,
  {
    label: 'fix3:CDE-parcel-linkage',
    phase: 'Fix',
    isolation: 'worktree',
    schema: {
      type: 'object',
      properties: {
        letters_touched: { type: 'array', items: { type: 'string' } },
        fix_summary: { type: 'string' },
        sql_or_endpoints_used: { type: 'array', items: { type: 'string' } },
        before_json: {}, after_json: {},
        residual_gaps: { type: 'array', items: { type: 'string' } },
        honesty_notes: { type: 'array', items: { type: 'string' } },
      },
      required: ['fix_summary', 'before_json', 'after_json'],
    },
  }
)

const fix4 = await agent(
  `You are working Gold Standard, county "okaloosa" ONLY, inside the cli-anything-biddeed repo (on main). ` +
  `git pull --rebase origin main FIRST -- prior work-packages already pushed (including fix3's parcel linkage ` +
  `work, which you should build on, and fix1's fabrication purge).\n\n${BASELINE}\n\n` +
  `WORK-PACKAGE 4 of 5: I (property card completeness) -- the biggest gap in this county (36 of 57, needs 55).\n\n` +
  `VERIFIED THIS SESSION: I's exact SQL requires, per row: property_address IS NOT NULL AND geo(lat+lon) IS NOT ` +
  `NULL AND COALESCE(assessed_value,market_value) IS NOT NULL AND parcel_id resolves to a zone_code in ` +
  `v_zoning_gold_standard_card. Of the 21 currently-failing rows, 17 already have address AND value but are ` +
  `MISSING geo+zone-match; 2 more need address+geo+zone (these overlap with fix3's work, re-check after fix3); ` +
  `2 are the documented stale placeholder seed rows (2024-CA-000470, 2024-TDD-000089) -- leave those, not ` +
  `recoverable.\n\n` +
  `The 17 geo-only-gap rows are dominated by the tax_deed lane: BEFORE fix1 purged them, tax_deed had only ` +
  `12 of 28 rows with any lat/lon at all -- specifically the 15 real "B4A-1299795" through "B4A-1299809" rows ` +
  `(scraped 2026-07-23, real APN-format parcel_id already present, e.g. '351S24274800000040', real distinct ` +
  `street addresses in Fort Walton Beach/Crestview/Niceville/Destin/Mary Esther/Baker) have NO lat/lon at all. ` +
  `Fix1 also purged their fabricated assessed_value, so they now need BOTH real geo AND real value.\n\n` +
  `THE LEVER: since these 15 rows already have a real parcel_id (PIN), a SINGLE GIS point query per row against ` +
  `https://okgis.myokaloosa.com/arcgis/rest/services/Land-Ownership/Parcels_with_Addressing/MapServer/121/query ` +
  `with where=PIN='<their PIN>' and outFields PIN,SITE_ADDR,TOTALAPPR,ASSEDVAL,and requesting geometry, returns ` +
  `BOTH the real assessed/market value AND a polygon whose centroid gives real lat/lon -- one query closes both ` +
  `gaps for each row. This exact TD-lane-by-APN enrichment function already exists (written, never executed) at ` +
  `"git show origin/claude/issue-12952-20260721-1601:scripts/shard4_run5668_okaloosa_cei_g_fix.py" -- see ` +
  `run_parcel_gis_enrichment()'s TD lane (matches by "PIN = '<apn>'", takes centroid via _centroid()). Adapt and ` +
  `verify it, don't blindly trust it (it predates fix1's purge and fix3's work, so re-diagnose current gap rows ` +
  `fresh before running).\n\n` +
  `After geo+value are real for these rows, they still need a parcel_zones entry with a resolved zone_code to ` +
  `pass the "zone-match" clause. Run the zoning-substrate step: for any okaloosa row with parcel_id+lat+lon not ` +
  `yet in parcel_zones, resolve city via ` +
  `https://okgis.myokaloosa.com/arcgis/rest/services/Admin-Boundaries/Admin_Boundaries/MapServer/99/query ` +
  `(point-in-polygon, outField ICLPY_CITY_CODE), then resolve zone via the matching per-city GIS layer or, if ` +
  `UNINCORPORATED, https://okgis.myokaloosa.com/arcgis/rest/services/Planning-Development/Zoning/MapServer/28/query ` +
  `(outField ZNGPY_ZONE). The same referenced script's run_zoning_substrate()/resolve_city_code()/resolve_zone() ` +
  `functions and the CITY_ZONING_SOURCES dict (Crestview/Fort Walton Beach/Niceville/Destin GIS endpoints) cover ` +
  `this -- adapt, verify live, don't trust blindly. The 'Unincorporated Okaloosa County' jurisdiction row must ` +
  `already exist (supabase/migrations/20260719_shard3_okaloosa_i_unincorporated_jurisdiction.sql landed on main ` +
  `already per git log -- confirm, don't re-create).\n\n` +
  `Only insert parcel_zones rows you can source from a real, live GIS response -- if a point query returns 0 or ` +
  `>1 features, or the zone field is null, do NOT guess a zone_code; report the row as unresolved.\n\n` +
  `Verify I via pencil_dod_evaluate_county. Report the exact before/after card_complete count -- if it lands ` +
  `short of 55/57, say so plainly and list the specific remaining rows and why, do not round up or imply PASS.\n\n` +
  `git commit, git pull --rebase origin main, push to main.\n\n${RECIPE}`,
  {
    label: 'fix4:I-property-card',
    phase: 'Fix',
    isolation: 'worktree',
    schema: {
      type: 'object',
      properties: {
        letters_touched: { type: 'array', items: { type: 'string' } },
        fix_summary: { type: 'string' },
        sql_or_endpoints_used: { type: 'array', items: { type: 'string' } },
        before_json: {}, after_json: {},
        residual_gaps: { type: 'array', items: { type: 'string' } },
        honesty_notes: { type: 'array', items: { type: 'string' } },
      },
      required: ['fix_summary', 'before_json', 'after_json'],
    },
  }
)

const fix5 = await agent(
  `You are working Gold Standard, county "okaloosa" ONLY, inside the cli-anything-biddeed repo (on main). ` +
  `git pull --rebase origin main FIRST -- prior work-packages already pushed.\n\n${BASELINE}\n\n` +
  `WORK-PACKAGE 5 of 5: G (zoning gold standard) -- density only, far/pk1000 already at 100%%.\n\n` +
  `VERIFIED THIS SESSION (via v_zoning_gold_standard_kpi_v3's underlying parcel_zones join, not just the summary ` +
  `view): 45 applicable parcels total, 11 missing max_density_du_acre (45-11=34, 34/45=75.6%%, matches the live ` +
  `metric exactly). The 11-parcel gap is concentrated in exactly two zone codes, both under jurisdiction ` +
  `"Unincorporated Okaloosa County": zone_code='R-1' (8 parcels), zone_code='MU' (3 parcels).\n\n` +
  `A prior unmerged session's research (git show ` +
  `origin/claude/issue-12952-20260721-1601:scripts/shard4_run5668_okaloosa_cei_g_fix.py, and an earlier landed ` +
  `migration supabase/migrations/20260719h_gtm22j_shard3_okaloosa_g_real_ordinance_zone_standards.sql -- read ` +
  `both) hypothesized these are BIFURCATED by geography per the Okaloosa County LDC: R-1 = 4 du/acre north of ` +
  `the Eglin AFB boundary vs 5 du/acre south; MU = 25 du/acre inside the Urban Development Area Boundary (UDAB) ` +
  `vs 4 du/acre outside. That hypothesis was NEVER independently verified against the actual ordinance text -- ` +
  `treat it as a lead, not a fact.\n\n` +
  `YOUR TASK:\n` +
  `1. Find and read the REAL Okaloosa County Land Development Code text for R-1 and MU density (Municode: ` +
  `library.municode.com/fl/okaloosa_county, or the county's own LDC PDF). Confirm or refute the bifurcation ` +
  `hypothesis with an actual citation (chapter/section). If the ordinance sets ONE density value per zone code ` +
  `(not bifurcated), this is much simpler -- just backfill that single real value into zone_standards for ` +
  `(Unincorporated Okaloosa County, R-1) and (Unincorporated Okaloosa County, MU).\n` +
  `2. If it genuinely IS bifurcated by location, the current zone_standards schema stores one density value per ` +
  `(jurisdiction, zoning_district) pair -- it cannot express "depends which side of a line the parcel is on" ` +
  `without either a schema change or a per-parcel override. Do NOT invent a schema change in this session unless ` +
  `it's trivial and clearly safe (e.g. an optional column). If it's non-trivial, the honest move is: (a) probe ` +
  `whether the Eglin AFB boundary / UDAB boundary layers actually exist and are queryable on ` +
  `okgis.myokaloosa.com (Admin-Boundaries and Planning-Development/Zoning service trees -- list their layers via ` +
  `?f=json and look for AFB/UDAB/urban-development keywords), (b) if they exist, do point-in-polygon for the ` +
  `specific 11 gap parcels (get their parcel_zones.parcel_id -> geometry via the Parcels_with_Addressing layer) ` +
  `to see if they ALL land on the same side (in which case one value covers all 11 and there's no real ` +
  `bifurcation problem to solve), (c) if they genuinely split across both sides, report the precise structural ` +
  `gap and do NOT guess a value for any parcel.\n` +
  `3. Only write real, ordinance-or-GIS-sourced values. Fabricating a "close enough" density number to reach ` +
  `95%% is explicitly banned by this campaign's guardrails.\n\n` +
  `Verify G via pencil_dod_evaluate_county. Report exactly how many of the 11 parcels resolved and the resulting ` +
  `density/G metric -- if it's a partial fix or a documented structural residual, say so plainly.\n\n` +
  `git commit, git pull --rebase origin main, push to main.\n\n${RECIPE}`,
  {
    label: 'fix5:G-zoning-density',
    phase: 'Fix',
    isolation: 'worktree',
    schema: {
      type: 'object',
      properties: {
        letters_touched: { type: 'array', items: { type: 'string' } },
        fix_summary: { type: 'string' },
        sql_or_endpoints_used: { type: 'array', items: { type: 'string' } },
        before_json: {}, after_json: {},
        residual_gaps: { type: 'array', items: { type: 'string' } },
        honesty_notes: { type: 'array', items: { type: 'string' } },
      },
      required: ['fix_summary', 'before_json', 'after_json'],
    },
  }
)

const fixResults = [fix1, fix2, fix3, fix4, fix5].filter(Boolean)

phase('Verify')
const LETTERS = ['B', 'C', 'D', 'E', 'G', 'I']
const verified = await parallel(LETTERS.map((letter) => () =>
  agent(
    `Independently verify the Gold Standard claim(s) for county "okaloosa", letter "${letter}". You did NOT ` +
    `write any of this work -- be skeptical. git pull --rebase origin main first to get the latest state.\n\n` +
    `${BASELINE}\n\nAll five fix-package reports from this session (for context, do not trust blindly): ` +
    `${JSON.stringify(fixResults.map(r => ({ letters: r?.letters_touched, summary: r?.fix_summary, after: r?.after_json })))}\n\n` +
    `${RECIPE}\n\nYour job: re-run pencil_dod_evaluate_county('okaloosa') yourself RIGHT NOW (fresh call, do not ` +
    `trust any pasted after_json), and specifically check for letter "${letter}": (a) does the metric actually ` +
    `sit at or past its threshold (>=95%% for C/D/E/G/I, or the [95,105] band for B)? (b) any denominator mismatch ` +
    `-- does auctions_total/closed_sold match what you independently query? (c) GHOST-SUCCESS: is any row counted ` +
    `toward a pass because of a placeholder/fabricated/vacuous value rather than a real fix -- this campaign has ` +
    `a documented history of EXACTLY this failure mode in okaloosa specifically (multiple purges), and this ` +
    `session itself found and purged a live fabrication bug (assessed_value=310000 default) -- confirm that fix ` +
    `actually landed and that no row still carries that placeholder pair (SELECT count(*) WHERE ` +
    `assessed_value=310000 AND market_value=325500.0, expect 0), and confirm no NEW placeholder pattern was ` +
    `introduced by a later work-package (e.g. all rows sharing one suspiciously-identical lat/lon, or one ` +
    `zone_code, etc -- spot check for repeated identical values across distinct real properties). (d) for B ` +
    `specifically, the valid pass band is 95-105%% -- flag any ratio outside that even if a raw bit says pass. ` +
    `(e) did any OTHER letter regress as a side effect of this letter's fix? (f) for any GIS-sourced parcel/geo/` +
    `zone claim, independently re-query the SAME live GIS endpoint yourself for at least one row and confirm the ` +
    `response actually matches what was written to the DB -- do not trust a description of a query result.\n\n` +
    `Also INSERT your own gold_standard_ultraloop_audit row (dispatch_id '${DISPATCH_ID}', county_slug ` +
    `'okaloosa', letter '${letter}', ultraloop_mode 'fallback', your refutation attempt + fresh evaluation in ` +
    `refuter_evidence, survived = your honest verdict).\n\n` +
    `Return { letter, refuted: boolean, refutation_reason: string|null, fresh_evaluation: <the JSON you just ` +
    `got>, survives: boolean }.`,
    {
      label: `verify:${letter}`,
      phase: 'Verify',
      schema: {
        type: 'object',
        properties: {
          letter: { type: 'string' },
          refuted: { type: 'boolean' },
          refutation_reason: { type: ['string', 'null'] },
          fresh_evaluation: {},
          survives: { type: 'boolean' },
        },
        required: ['letter', 'refuted', 'fresh_evaluation', 'survives'],
      },
    }
  )
))

return { fixResults, verified }
