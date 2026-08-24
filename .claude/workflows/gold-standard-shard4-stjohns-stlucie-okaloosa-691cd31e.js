export const meta = {
  name: 'gold-standard-shard4-stjohns-stlucie-okaloosa-691cd31e',
  description: 'Gold Standard shard-4 (dispatch 691cd31e): st_johns I, st_lucie C/I, okaloosa C/D/E/I — research known blockers, fix with real data, ULTRALOOP adversarial verify',
  phases: [
    { title: 'Diagnose-Fix' },
    { title: 'Adversarial Verify' },
    { title: 'Closeout' },
  ],
}

const COUNTIES = [
  {
    slug: 'st_johns',
    failing: ['I'],
    context: 'I: card_complete=87 of 108 (80.6%%, need >=95%% i.e. >=103/108 — a 16-row gap). All other letters (A-H,J) already PASS live per the session brief — do not touch them. I <= E by construction (card requires a linked parcel resolving through v_zoning_gold_standard_card with zone_code NOT NULL) but E is already PASS at 100%% (parcel_linked=108), so the gap here is NOT parcel linkage — it is address/geo/value completeness or the zoning-card join itself. Check property_address, latitude/longitude (or po_latitude/po_longitude), assessed_value/market_value NULLs on the 21 incomplete rows first, then check whether their linked parcel_id actually resolves in v_zoning_gold_standard_card (st_johns G is PASS at 100%% so zoning substrate should be loaded).',
    priorFiles: 'scripts/gold_standard_shard4_st_johns_e_taxsmart_strap_backfill.py, scripts/gold_standard_shard11_st_johns_e_i_reverify_5074ac68.py, scripts/gold_standard_shard7_st_johns_e_i_diagnostic_run3713.py, scripts/gold_standard_shard4_st_johns_j_assessed_value_backfill.py, supabase/migrations/20260724_gold_standard_shard2_stjohns_i_j_final4_parcel_zones_bid_decisions_ffe1aa89.sql, supabase/migrations/20260812_architect_triage_18870_stjohns_g_zoning_backfill.sql, GOLD_STANDARD_SHARD2_NASSAU_STJOHNS_DISPATCH_FFE1AA89_SESSION_REPORT.md, GOLD_STANDARD_SHARD4_MARION_HAMILTON_STLUCIE_STJOHNS_DISPATCH_7D59C973_SESSION_REPORT.md, GOLD_STANDARD_SHARD12_OKEECHOBEE_STJOHNS_DISPATCH_704E70A0_SESSION_REPORT.md — grep GOLD_STANDARD_*.md for "st_johns" and "I:" for more prior attempts at this exact letter before repeating a dead end.',
  },
  {
    slug: 'st_lucie',
    failing: ['C', 'I'],
    context: 'C: matched_clean=188 of ~237 (79.3%%, need >=95%% i.e. >=226/237 — a ~38-row gap, the larger problem in this county). D is PASS at 97.5%% (matched_any=231/237) — meaning ~43 rows are matched_divergent/CLERK_SSOT_CANCELLED (count toward D but not C) or unmatched; the C-vs-D gap (231 vs 188 = 43 rows) is where matched_any-but-not-clean rows live — investigate parity_status/parity_source on exactly those 43 rows first, this is the highest-leverage lever. I: card_complete=214 of 237 (90.3%%, need >=95%% i.e. >=226/237 — a 12-row gap). E is PASS at 97.5%% (parcel_linked=231) so most of I gap is address/geo/value completeness on already-linked rows, not linkage itself — check the ~17 rows that are E-linked but not I-complete.',
    priorFiles: 'scripts/gold_standard_shard1_6a9e3c3a_stlucie_c_parity_fix.py, scripts/gold_standard_shard7_stlucie_cdi_fix.py, scripts/stlucie_dispatch_group1_cd_fix.py, scripts/stlucie_dispatch_group2_ei_fix.py, scripts/gold_standard_shard4_st_lucie_e_parcel_id_backfill.py, scripts/gold_standard_shard3_stlucie_zoning_geo_fix.py, scripts/shard1_st_lucie_all_fixes.py, scripts/stlucie_audit_refresh_2026-07-27.py, GOLD_STANDARD_SHARD4_STLUCIE_DISPATCH_8198896F_SESSION_REPORT.md, GOLD_STANDARD_SHARD3_VOLUSIA_STLUCIE_DISPATCH_8C78A8DF_SESSION_REPORT.md (+ 3RD_FIRING_REPORT), docs/gold-standard-sessions/shard6-highlands-stlucie-run6288-2026-07-25.md — read these before re-attempting C, several prior sessions already worked this letter.',
  },
  {
    slug: 'okaloosa',
    failing: ['C', 'D', 'E', 'I'],
    context: 'C/D/I all sit at exactly 87.8%% (matched_clean=matched_any=card_complete=72 of 82) and E sits at 89.0%% (parcel_linked=73 of 82) — this is the classic single-cluster-of-rows pattern (see franklin in the shard-ecbe151d template): find the ~9-10 rows blocking C/D/I as one group, plus check whether the E=73 row is a superset or distinct from that group. Need >=95%% i.e. >=78/82 for C/D/I (6-row gap) and >=78/82 for E (5-row gap). WARNING: okaloosa C/D/E have an extensive multi-session failure history (SHARD3_ORANGE_HERNANDO_MIAMIDADE_OKALOOSA session + 2 addenda, SHARD5_OKALOOSA dispatch f3702b8e, SHARD7_OKALOOSA_HOLMES, SHARD9 run6080, SHARD2_FRANKLIN_LEVY_STLUCIE_OKALOOSA, shard9_okaloosa_run6080_cde_fix.py, okaloosa_ce_shard3_cont2_fix.py, okaloosa_zoning_substrate_build.py) — read the most recent of these FIRST (by file mtime) to find out exactly why it stalled last time and whether it is a genuine structural ceiling (e.g. specific auction rows with no matching clerk/appraiser record) before spending session time re-deriving the same diagnosis.',
    priorFiles: 'scripts/shard9_okaloosa_run6080_cde_fix.py, scripts/okaloosa_ce_shard3_cont2_fix.py, scripts/okaloosa_parcel_gis_enrich.py, scripts/gold_standard_shard9_okaloosa_wp4_i_fix.py, scripts/shard7_run757_okaloosa_ei_g_fix.py, scripts/shard3_7be9b60b_okeechobee_okaloosa_fix.py, migrations/20260812_gold_standard_shard3_okaloosa_cde_i_backfill.sql, migrations/20260810_gold_standard_shard2_a56d9693_okaloosa_i_regression_fix.sql, migrations/20260809_architect_triage_18472_okaloosa_i_address_backfill_APPLIED.sql, GOLD_STANDARD_SHARD3_ORANGE_HERNANDO_MIAMIDADE_OKALOOSA_DISPATCH_C366EE22_SESSION_REPORT.md (+ CONTINUATION_ADDENDUM + 3RD_FIRING_ADDENDUM), GOLD_STANDARD_SHARD5_OKALOOSA_DISPATCH_F3702B8E_SESSION_REPORT.md, GOLD_STANDARD_SHARD7_OKALOOSA_HOLMES_DISPATCH_E0481214_SESSION_REPORT.md, docs/gold-standard-sessions/shard4-polk-jefferson-okaloosa-run6354-2026-07-25.md, docs/gold-standard-sessions/okaloosa-wp4-i-2nd-pass-2026-07-24.md — this letter set has been attempted 6+ times, read the newest report in full before touching anything.',
  },
]

const SHARED_CONTEXT = `
GOLD STANDARD CAMPAIGN — dispatch_id 691cd31e-21e3-40ce-9d73-3b05482763b6, shard-4 (st_johns/st_lucie/okaloosa).
Repo: /home/runner/work/cli-anything-biddeed/cli-anything-biddeed (already checked out, you are running there).
Non-interactive headless session, zero-HITL, execute-first. Do not ask questions — you are the only agent that will act on this.

CREDENTIALS (already in your shell env, never print/echo/log their raw values):
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY -> PostgREST reads/writes: curl "$SUPABASE_URL/rest/v1/<table>?..." -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
  SUPABASE_ACCESS_TOKEN -> Supabase Management API for arbitrary SQL (DDL/complex joins/ad-hoc SELECT):
    curl -s "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query" -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" -H "Content-Type: application/json" -d '{"query":"SELECT ..."}'
  Direct psql/SUPABASE_DB_PASSWORD is a KNOWN, already-documented constraint in this environment — do not waste session time re-diagnosing it, use the Management API above for ad-hoc SQL instead (this is the established working pattern this pipeline runs on daily).
  RPC for scoring: POST $SUPABASE_URL/rest/v1/rpc/pencil_dod_evaluate_county with body {"p_county":"<slug>"} — this is the canonical live scorer, ALWAYS re-run it fresh, never trust a cached/remembered number from a prior report.
  DB session note: if you do run ad-hoc SQL via the Management API on a heavy query, prefix with SET statement_timeout = 0; in the same request — the role default (2 min) kills heavy joins/aggregates.

EVALUATOR SQL SEMANTICS (confirm current behavior yourself via pg_get_functiondef on pencil_dod_evaluate_county through the Management API before assuming anything below is still accurate — it has been revised (V6) since these notes were written):
  - Base population = multi_county_auctions WHERE lower(county)=<slug> AND (data_source <> 'propertyonion' OR tier1_authoritative=true). PropertyOnion-sourced rows are EXCLUDED from every denominator unless flagged tier1_authoritative.
  - C metric = matched_clean/auctions_total >= 95. matched_clean requires parity_status IN ('matched_clean' with parity_source LIKE 'tier1%') OR IN ('PARITY_OK','CLERK_VERIFIED').
  - D metric = matched_any/auctions_total >= 95. Slightly looser: also allows 'matched_divergent' (tier1%) and 'CLERK_SSOT_CANCELLED'.
  - E metric = has_parcel/auctions_total >= 95, where has_parcel = parcel_id IS NOT NULL.
  - I metric = card_complete/card_rows >= 95. card_complete requires property_address NOT NULL, (latitude/po_latitude) NOT NULL, (longitude/po_longitude) NOT NULL, (assessed_value or market_value) NOT NULL, AND parcel_id present in v_zoning_gold_standard_card (a REAL zoning-linked parcel, zone_code NOT NULL) for this county. I <= E structurally.
  - B metric = verified_outcomes/closed_sold >= 95 AND <=105 (must be independently sourced: EXISTS in tax_deed_outcomes or foreclosure_outcomes with case_number match AND data_source NOT ILIKE '%%promote%%'). B PASSES ONLY in the 95-105%% band — anything above 105%% is an anomaly, not a pass, and must be reconciled not celebrated.
  - F metric = tier1_sold/closed_sold >= 95, tier1_sold = count where tier1_sold_amount NOT NULL AND sold_amount NOT NULL. Same closed_sold denominator as B.
  - J metric = deal_complete/auctions_total >= 95. deal_complete requires a bid_decisions row matching case_number with arv, max_bid, ml_score all NOT NULL AND factors jsonb containing keys distress_location, distress_property, distress_owner, cma_distressed, cma_resale.
  - CERT SCOPE: some counties evaluate against a denominator frozen at a snapshot date (gold_standard_cert_scope) — check whether st_johns/st_lucie/okaloosa are in that table; if so your fixes must close numerator gaps within the frozen population, not chase newly-ingested rows outside it.

HARD GUARDRAILS (non-negotiable, see this repo's CLAUDE.md for full text):
  1. PropertyOnion data is litmus/comparison ONLY — never write it into multi_county_auctions as an authoritative source, never set it as the sole basis for C/D/E/I fixes.
  2. Fail-loud: if you build N rows and insert 0, raise/stop and report it — never silently swallow with a bare except or "|| true".
  3. NEVER fabricate/guess a value to force a metric to pass. Multiple prior sessions in this exact campaign were caught doing this and had to revert (fabricated zone_code, hardcoded county-wide ARV in bid_decisions, ghost-success zoning inserts) — see migrations/*ghost_purge*.sql and migrations/*revert_ghost_success*.sql for the pattern to avoid. If you cannot find a REAL, sourced value (county GIS/appraiser API, clerk record, ordinance text), leave the row unfixed and report it as a genuine structural gap. BLANK > WRONG.
  4. PARALLEL-FLEET RULES: you own ONLY the county assigned to you in this task (st_johns, st_lucie, or okaloosa — never touch the others or any county outside this shard). git pull --rebase before every push to main; other concurrent shard sessions may land unrelated commits mid-session — that is normal, do not investigate or revert them. Do NOT run public.gold_standard_loop() or gold_standard_certify() yourself — the Closeout stage handles that once, after all three counties finish.
  5. Do not modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job.
  6. Any SQL/table changes: write a migrations/<date>_<slug>.sql file documenting what you ran (matching the style of existing files in migrations/ or supabase/migrations/), even though you apply it live via the Management API/PostgREST.
  7. ULTRALOOP: every claim you make that a letter moved MUST be backed by a query you actually ran in this session, not memory of a prior session's number. Tag every claim VERIFIED (query attached) / UNTESTED / INFERRED per the Honesty Protocol.

YOUR TASK for county "{{SLUG}}" (failing letters: {{FAILING}}):
{{CONTEXT}}

Prior-session files most relevant to this exact problem (read the ones that exist before doing anything — many sessions have already tried and failed on these exact letters, do not repeat a dead end):
{{PRIORFILES}}

Work in three rounds, reported back at the end of each:
ROUND 1 (RESEARCH): Read the prior-session files above (grep for the county name across GOLD_STANDARD_*.md session reports too, there may be more not listed, sort by mtime and prioritize the newest). Run pencil_dod_evaluate_county('{{SLUG}}') fresh to confirm current state. For each failing letter, identify the EXACT rows/case_numbers blocking it (query multi_county_auctions directly) and WHY they're blocked (missing parcel_id? missing lat/long? no matching parity source? zoning card join failing? no matching clerk record?). State plainly whether you believe each gap is fixable with real data this session, or whether it is a genuine structural/data-availability ceiling — cite your evidence either way.
ROUND 2 (FIX): For gaps you judge fixable, fix them using ONLY real, sourced data (county property appraiser / ArcGIS FeatureServer / clerk records / municode ordinance text / the county's own scraped source). Use WebFetch/WebSearch/firecrawl skills as needed to pull real per-property or per-parcel data. Write the migration file. Apply live via Management API/PostgREST. For gaps you judge structural, do not force anything — document the evidence.
ROUND 3 (SELF-CHECK): Re-run pencil_dod_evaluate_county('{{SLUG}}') fresh. Confirm every letter you touched actually moved, and confirm you did NOT regress any letter that was previously passing (diff the full A-J object before vs after). Ask yourself: could the specific rows you inserted/updated be wrong in a way that inflates the metric without being real (ghost-success)? If yes, revert and report honestly instead.

Return a structured summary: {county, failing_letters_at_start, evaluator_before (full A-J JSON with exact numbers), work_done (list of concrete actions with row counts), evaluator_after (full A-J JSON with exact numbers), still_failing (list with honest reason — structural vs unattempted vs attempted-but-insufficient), migration_file_path(s), git_commit_sha(s)}.
`

async function runCounty(c) {
  const prompt = SHARED_CONTEXT
    .replace(/\{\{SLUG\}\}/g, c.slug)
    .replace('{{FAILING}}', c.failing.join(', '))
    .replace('{{CONTEXT}}', c.context)
    .replace('{{PRIORFILES}}', c.priorFiles)
  return await agent(prompt, { label: `fix:${c.slug}`, phase: 'Diagnose-Fix' })
}

function refuterPrompt(c, result) {
  return `
ULTRALOOP ADVERSARIAL VERIFY — dispatch 691cd31e-21e3-40ce-9d73-3b05482763b6, county "${c.slug}".
Repo: /home/runner/work/cli-anything-biddeed/cli-anything-biddeed (already checked out).

A prior agent in this same session claims to have worked county "${c.slug}" (failing letters at start: ${c.failing.join(', ')}) and returned this report:

${JSON.stringify(result, null, 2)}

Your ONLY goal is to try to REFUTE this claim. You did not write this fix — treat it with default skepticism. Default to refuted=true if you cannot positively confirm the claim with a fresh query.

Do the following, using the same credentials/RPC pattern documented in this repo (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY for PostgREST, SUPABASE_ACCESS_TOKEN for the Management API SQL endpoint at https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query):
1. Re-run POST $SUPABASE_URL/rest/v1/rpc/pencil_dod_evaluate_county with body {"p_county":"${c.slug}"} RIGHT NOW, fresh — do not trust the numbers in the report above, they may be stale or fabricated.
2. Compare the fresh result to the report's claimed "evaluator_after". Do the numbers match?
3. For any letter the report claims moved from FAIL to PASS (or materially improved), spot-check the underlying rows: query multi_county_auctions directly for a sample of the specific rows claimed fixed. Are the inserted/updated values REAL (traceable to a real source: county GIS parcel, clerk record, appraiser record) or do they look fabricated/guessed/duplicated/copy-pasted from another row?
4. Check for the B>100%% anomaly pattern and its structural cousins: does any claimed-passing letter sit on a suspicious ratio (e.g. numerator suspiciously equals denominator exactly after a bulk UPDATE, or a value repeated identically across many rows in a way real per-property data would not)?
5. Check for regression: did any letter that was PASSing before this session's changes get worse? (Diff against the "evaluator_before" in the report for letters NOT in the failing list — those should be untouched.)
6. If a migration file path was given, read it and confirm the SQL it documents matches what was actually applied (no drift between documented and live state).

Return your verdict as a JSON object: {county: "${c.slug}", letters_checked: [...], per_letter: [{letter, claimed_metric, fresh_metric, matches: true/false, sample_rows_checked: [...], real_data_confirmed: true/false/undetermined, regression_detected: true/false, verdict: "survived"|"refuted", reason}], overall_verdict: "survived"|"refuted"|"partially_survived", notes}.
Be concrete and cite the actual query results you ran — a verdict without a query attached is worthless here.
`
}

phase('Diagnose-Fix')
log(`Starting gold-standard shard-4 (691cd31e): ${COUNTIES.map(c => c.slug).join(', ')}`)

const verified = await pipeline(
  COUNTIES,
  c => runCounty(c),
  (fixResult, c) => agent(refuterPrompt(c, fixResult), { label: `verify:${c.slug}`, phase: 'Adversarial Verify', schema: {
    type: 'object',
    properties: {
      county: { type: 'string' },
      overall_verdict: { type: 'string', enum: ['survived', 'refuted', 'partially_survived'] },
      per_letter: { type: 'array' },
      notes: { type: 'string' },
    },
    required: ['county', 'overall_verdict'],
  } }).then(verdict => ({ county: c.slug, failing_at_start: c.failing, fixResult, verdict }))
)

log('All 3 counties fixed + adversarially verified. Results:')
verified.forEach(v => {
  if (v) log(`${v.county}: ${v.verdict?.overall_verdict ?? 'unknown'}`)
  else log('a county agent failed/skipped')
})

phase('Closeout')
const closeoutPrompt = `
SESSION CLOSEOUT — dispatch 691cd31e-21e3-40ce-9d73-3b05482763b6, shard-4 (st_johns/st_lucie/okaloosa).
Repo: /home/runner/work/cli-anything-biddeed/cli-anything-biddeed.

Three counties were worked this session with fix + adversarial-verify results below. Your job is ONLY to close out the session per the mandatory protocol — do not attempt any further fixes.

RESULTS:
${JSON.stringify(verified, null, 2)}

STEPS:
1. For each county, run SET statement_timeout = 0; SELECT public.pencil_dod_evaluate_county('<slug>'); fresh via the Management API (https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query, Authorization: Bearer $SUPABASE_ACCESS_TOKEN) to get the final live A-J JSON for st_johns, st_lucie, okaloosa.
2. For each county, run this close-out UPDATE (adjust criteria_passed to the REAL final A-J booleans from step 1, not the pre-session brief numbers, and only treat a letter as passing if refuter overall_verdict was "survived" or "partially_survived" for it — a "refuted" claim must NOT be recorded as passed even if the raw metric looks like it crossed 95%%):
   UPDATE public.gold_standard_campaign
   SET criteria_passed = '{"A": true, "B": true, ...}'::jsonb,
       criteria_total = 10,
       exit_reason = 'timeout',
       session_end_at = now()
   WHERE dispatch_id = (SELECT id FROM summit_chat_dispatch WHERE state='processing' ORDER BY updated_at DESC LIMIT 1);
   If the dispatch_id subquery doesn't resolve to a row scoped to this shard/session, look up the correct row by dispatch_id '691cd31e-21e3-40ce-9d73-3b05482763b6' directly against summit_chat_dispatch instead, and report which path you used.
3. Do NOT run public.gold_standard_loop() or public.gold_standard_certify() — other shards may be mid-flight concurrently per the parallel-fleet rules. Only run per-county pencil_dod_evaluate_county.
4. Any letter where the refuter verdict was "refuted": log it explicitly in your summary as a false-positive, not counted as progress, and do not write it as true in criteria_passed.
5. Produce the final session report as a single structured object: {dispatch_id: '691cd31e-21e3-40ce-9d73-3b05482763b6', counties: [{slug, letters_targeted, before (A-J from the session brief), after (fresh A-J from step 1), refuter_verdict_summary, migration_files, git_commits}], closeout_sql_executed: true/false, closeout_row_updated: true/false}.
This report IS the loop closure required by CLAUDE.md — paste literal before/after JSON per county, do not summarize away the numbers.
`
const closeout = await agent(closeoutPrompt, { label: 'closeout', phase: 'Closeout' })

return { dispatch_id: '691cd31e-21e3-40ce-9d73-3b05482763b6', counties: COUNTIES.map(c => c.slug), verified, closeout }
