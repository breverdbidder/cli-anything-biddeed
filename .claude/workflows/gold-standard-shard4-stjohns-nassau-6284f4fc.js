export const meta = {
  name: 'gold-standard-shard4-stjohns-nassau-6284f4fc',
  description: 'Gold Standard shard-4 (dispatch 6284f4fc): st_johns C light freshness re-check (reconfirmed ceiling), nassau C/D/E/I backlog enrichment (denominator grew 47->56 since last 10/10) — ULTRALOOP diagnose/fix/adversarial-verify',
  phases: [
    { title: 'Diagnose-Fix' },
    { title: 'Adversarial Verify' },
    { title: 'Closeout' },
  ],
}

const COUNTIES = [
  {
    slug: 'st_johns',
    failing: ['C'],
    mode: 'light-recheck',
    context: `C: matched_clean=113 of 119 (95.0%%, need >=95.0%% strictly greater i.e. >=114/119 — a 1-row gap).
This EXACT 1-row gap has been independently re-investigated with HIGH SCRUTINY twice in the last 24h:
  - dispatch b992b7ec, 2026-08-31 08:27Z: all 6 non-clean candidate rows independently re-derived against the live apps.stjohnsclerk.com/TaxSmart grid, confirmed genuinely REDEEMED/CANCELLED. Explicit "do not re-litigate" recommendation.
  - dispatch 9aa28d35, 2026-08-31 ~16:50Z (8h later): light freshness spot-check only (per K3, avoiding duplicate work) on the 2 future-dated rows (TD26-0059, TD26-0078) — re-fetched both live TaxSmart pages via curl (WebFetch 403'd, curl with browser UA succeeded), both still Status=REDEEMED matching DB's CLERK_SSOT_CANCELLED. Zero drift in ~8 hours. audit id 20122, survived=true.
DO NOT re-run a full re-investigation of this letter — that would be pure duplicate work per K3 (surgical changes) and the explicit "do not re-fire routine re-diagnosis until the source data itself changes" guidance from the most recent session. Your job for st_johns is narrow:
  1. Run pencil_dod_evaluate_county('st_johns') fresh to confirm C is still exactly 113/119 (if the number moved AT ALL from 113, that IS new evidence — investigate the delta specifically, not the whole letter).
  2. Do ONE light freshness spot-check: re-fetch the same 2 future-dated TaxSmart pages (case numbers TD26-0059 and TD26-0078 — confirm exact case_number strings via a quick multi_county_auctions query first, they may have shifted) via curl with a browser User-Agent (apps.stjohnsclerk.com/TaxSmart), confirm status is unchanged from last check.
  3. Also spot-check the other letters (A,B,D,E,F,G,H,I,J) for st_johns are still all PASS with unchanged metrics — a silent regression on a previously-passing letter would be more valuable to catch than re-litigating C.
  4. If and only if you find genuinely NEW evidence (a status change, a new row, a different case_number set than before) should you go deeper. Otherwise report the reconfirmation and STOP — do not spend session budget manufacturing new investigation on a well-established genuine ceiling.`,
    priorFiles: 'GOLD_STANDARD_SHARD4_STJOHNS_OKALOOSA_DISPATCH_9AA28D35_SESSION_REPORT.md (most recent, 2026-08-31, read this one first), GOLD_STANDARD_SHARD5_STJOHNS_OKALOOSA_DISPATCH_AA259B14_SESSION_REPORT.md, GOLD_STANDARD_SHARD2_LAFAYETTE_STJOHNS_JEFFERSON_WAKULLA_DISPATCH_B992B7EC_SESSION_REPORT.md, scripts/gold_standard_stjohns_c_phantom_tax_deed_reclassify.py, migrations/20260828e_gold_standard_stjohns_c_3row_matched_divergent_reconcile.sql, migrations/20260830_gold_standard_shard5_stjohns_c_phantom_firewall_fix.sql',
  },
  {
    slug: 'nassau',
    failing: ['C', 'D', 'E', 'I'],
    mode: 'backlog-enrichment',
    context: `C: matched_clean=48/56 (85.7%%, need >=54/56). D: matched_any=48/56 (85.7%%, need >=54/56). E: parcel_linked=53/56 (94.6%%, need >=54/56). I: card_complete=47/56 (83.9%%, need >=54/56).
CRITICAL CONTEXT: nassau reached a fully-verified, adversarially-confirmed 10/10 on 2026-08-11 (dispatch 14cdfac9) with auctions_total=47. The live evaluator now shows auctions_total=56 — 9 NEW rows have been ingested into multi_county_auctions for nassau since that certification, and none of them have been enriched yet. This is almost certainly NOT a re-emergence of the old structural gap — it is fresh backlog work on new rows using the SAME proven playbook from the Aug 11 session:
  - C/D (parity): the Aug 11 fix was reconciling 3 rows against nassau.realtaxdeed.com / nassauclerk.realforeclose.com (live clerk status). Also check for the same "PHANTOM_NOT_ON_CLERK" mislabeling pattern seen before (2026-07-04 revert) on any of the new rows before assuming they're genuinely unmatched.
  - E (parcel linkage): the Aug 11 fix used a RealTaxDeed PREVIEW backfill matching via embedded 6-digit case sequence for 9 new tax_deed rows (case format 26TDxxxxxxAXYX). Check whether the current 3-row E gap (53/56) is the SAME mechanism on the newest batch of rows — first query multi_county_auctions for nassau rows with parcel_id IS NULL to get exact case_numbers.
  - I (card completeness): the Aug 11 fix used the Nassau County PA ArcGIS layer at maps.ncpafl.com/ncflpa_arcgis/rest/services/nassau/TaxMap4_CitrixV2/MapServer/144 with field PIN (NOT dsp_strap — that field name does not exist on this layer and silently returns 0 features / HTTP 400, a bug that cost a prior session an entire cycle, see scripts/architect_triage_17241_nassau_cdi_pin_field_fix.py). Query with returnGeometry=true to get both a centroid lat/lon AND the ZoningDistrict attribute in one call. I <= E structurally (card requires a zone-linked parcel via v_zoning_gold_standard_card) so fix E's gap rows first, then check if the SAME rows resolve most of I's gap.
  - G-REGRESSION TRAP (documented root cause from Aug 11 session, Part 1 of the report): if any newly-linked zone code has no matching zoning_districts row, v_zoning_district_applicability silently defaults ALL THREE (density/far/pk1000) to "applicable" with no zone_standards value, which can drag G down even though G currently PASSes (97.4%%). Before finishing, check that every zone code you write via parcel_zones already has (or gets) a corresponding zoning_districts row, or you will regress a currently-passing letter.
  - FABRICATION WARNING (also from Aug 11 session): a prior session found 15 nassau rows with an IDENTICAL assessed_value=320000/market_value=336000 pair across distinct properties — confirmed fabricated placeholder data, since purged. If you see any suspiciously identical value pair across multiple rows during this session, treat it as a red flag, verify against the real ArcGIS JUSTVAL/FASMP_ASSD_VALUE_NS fields, and do not propagate it.
  Query multi_county_auctions directly for nassau rows added/modified since 2026-08-11 (or with NULL parcel_id / NULL assessed_value / non-clean parity_status) to get the exact 9-row (or however many) target set before writing anything.`,
    priorFiles: 'GOLD_STANDARD_SHARD2_BAY_NASSAU_DISPATCH_14CDFAC9_SESSION_REPORT.md (READ THIS FIRST — most recent full 10/10 with exact mechanism for every letter), scripts/shard2_nassau_run14cdfac9_i_geo_zone_backfill.py, scripts/shard2_bay_nassau_run14cdfac9_e_backfill.py, scripts/shard2_nassau_run14cdfac9_fabricated_value_purge.py, scripts/architect_triage_17241_nassau_cdi_pin_field_fix.py, supabase/migrations/20260818b_architect_triage_19316_walton_certify_nassau_collateral_repair.sql, scripts/clerk_ssot/parsers/nassau.py, scripts/shard_nassau_run_cd_bf_reharvest.py',
  },
]

const SHARED_CONTEXT = `
GOLD STANDARD CAMPAIGN — dispatch_id 6284f4fc-ce46-4f84-bb14-a92199aa0dcf, shard-4 (st_johns/nassau).
Repo: /home/runner/work/cli-anything-biddeed/cli-anything-biddeed (already checked out, you are running there).
Non-interactive headless session, zero-HITL, execute-first. Do not ask questions — you are the only agent that will act on this.

CREDENTIALS (already in your shell env, never print/echo/log their raw values):
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY -> PostgREST reads/writes: curl "$SUPABASE_URL/rest/v1/<table>?..." -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
  SUPABASE_ACCESS_TOKEN -> Supabase Management API for arbitrary SQL (DDL/complex joins/ad-hoc SELECT):
    curl -s "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query" -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" -H "Content-Type: application/json" -d '{"query":"SELECT ..."}'
  Direct psql/SUPABASE_DB_PASSWORD is a KNOWN, already-documented constraint in this environment — do not waste session time re-diagnosing it, use the Management API above for ad-hoc SQL instead.
  RPC for scoring: POST $SUPABASE_URL/rest/v1/rpc/pencil_dod_evaluate_county with body {"p_county":"<slug>"} — this is the canonical live scorer, ALWAYS re-run it fresh, never trust a cached/remembered number from a prior report.
  DB session note: if you do run ad-hoc SQL via the Management API on a heavy query, prefix with SET statement_timeout = 0; in the same request.

HARD GUARDRAILS (non-negotiable, see this repo's CLAUDE.md for full text):
  1. PropertyOnion data is litmus/comparison ONLY — never write it into multi_county_auctions as an authoritative source.
  2. Fail-loud: if you build N rows and insert 0, raise/stop and report it — never silently swallow with a bare except or "|| true".
  3. NEVER fabricate/guess a value to force a metric to pass. This exact campaign has caught and reverted fabricated zone_code, hardcoded ARV, ghost-success zoning inserts, and (in nassau specifically, Aug 11) a repeated fabricated assessed_value/market_value pair across 15 rows. If you cannot find a REAL, sourced value (county GIS/appraiser API, clerk record, ordinance text), leave the row unfixed and report it as a genuine gap. BLANK > WRONG.
  4. PARALLEL-FLEET RULES: you own ONLY st_johns and nassau — never touch any other county. git pull --rebase before every push to main; other concurrent shard sessions may land unrelated commits mid-session, that is normal, do not investigate or revert them. Do NOT run public.gold_standard_loop() or gold_standard_certify() yourself — the Closeout stage handles that, and even then only per-county evaluation per the brief.
  5. Do not modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job.
  6. Any SQL/table changes: write a migrations/<date>_<slug>.sql file documenting what you ran, even though you apply it live via the Management API/PostgREST.
  7. ULTRALOOP: every claim you make that a letter moved MUST be backed by a query you actually ran in this session. Tag every claim VERIFIED (query attached) / UNTESTED / INFERRED per the Honesty Protocol.

YOUR TASK for county "{{SLUG}}" (failing letters: {{FAILING}}, mode: {{MODE}}):
{{CONTEXT}}

Prior-session files most relevant to this exact problem (read the ones that exist before doing anything):
{{PRIORFILES}}

Work in three rounds, reported back at the end of each:
ROUND 1 (RESEARCH): Read the prior-session files above. Run pencil_dod_evaluate_county('{{SLUG}}') fresh to confirm current state matches this brief. For each failing letter, identify the EXACT rows/case_numbers blocking it and WHY. State plainly whether each gap is fixable this session with real data, or a genuine structural ceiling — cite evidence.
ROUND 2 (FIX): For gaps judged fixable, fix them using ONLY real, sourced data. Use WebFetch/WebSearch/firecrawl as needed. Write the migration file. Apply live via Management API/PostgREST. For gaps judged structural, document evidence and do not force anything.
ROUND 3 (SELF-CHECK): Re-run pencil_dod_evaluate_county('{{SLUG}}') fresh. Confirm every letter you touched actually moved, and confirm you did NOT regress any previously-passing letter (diff the full A-J object before vs after, this matters especially for G given the documented regression trap).

Return a structured summary: {county, failing_letters_at_start, evaluator_before (full A-J JSON with exact numbers), work_done (list of concrete actions with row counts), evaluator_after (full A-J JSON with exact numbers), still_failing (list with honest reason), migration_file_path(s), git_commit_sha(s)}.
`

async function runCounty(c) {
  const prompt = SHARED_CONTEXT
    .replace(/\{\{SLUG\}\}/g, c.slug)
    .replace('{{FAILING}}', c.failing.join(', '))
    .replace('{{MODE}}', c.mode)
    .replace('{{CONTEXT}}', c.context)
    .replace('{{PRIORFILES}}', c.priorFiles)
  return await agent(prompt, { label: `fix:${c.slug}`, phase: 'Diagnose-Fix' })
}

function refuterPrompt(c, result) {
  return `
ULTRALOOP ADVERSARIAL VERIFY — dispatch 6284f4fc-ce46-4f84-bb14-a92199aa0dcf, county "${c.slug}".
Repo: /home/runner/work/cli-anything-biddeed/cli-anything-biddeed (already checked out).

A prior agent in this same session claims to have worked county "${c.slug}" (failing letters at start: ${c.failing.join(', ')}) and returned this report:

${JSON.stringify(result, null, 2)}

Your ONLY goal is to try to REFUTE this claim. You did not write this fix — treat it with default skepticism. Default to refuted=true if you cannot positively confirm the claim with a fresh query.

Do the following, using SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY for PostgREST, SUPABASE_ACCESS_TOKEN for the Management API SQL endpoint at https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query:
1. Re-run POST $SUPABASE_URL/rest/v1/rpc/pencil_dod_evaluate_county with body {"p_county":"${c.slug}"} RIGHT NOW, fresh — do not trust the numbers in the report above.
2. Compare the fresh result to the report's claimed "evaluator_after". Do the numbers match?
3. For any letter the report claims moved from FAIL to PASS (or materially improved), spot-check the underlying rows: query multi_county_auctions directly for a sample of the specific rows claimed fixed. Are the inserted/updated values REAL (traceable to a real source: county GIS parcel, clerk record, appraiser record) or do they look fabricated/guessed/duplicated? Specifically for nassau: check for the exact fabrication signature already found once in this county (identical assessed_value/market_value pairs repeated across distinct rows) — if you find it again, this is an automatic refute.
4. Check for regression: did any letter that was PASSing before this session's changes get worse? For nassau specifically, check G did not regress (documented trap: newly-linked zone codes without a matching zoning_districts row silently default density/far/pk1000 to "applicable" with no standards, dragging G down).
5. For st_johns specifically: if the report claims C is unchanged (still a genuine ceiling), verify that claim too — re-run the evaluator and confirm the 113/119 (or whatever the fresh number is) matches. A "no change, ceiling reconfirmed" claim still needs a fresh query to survive, not just a citation of a prior day's report.
6. If a migration file path was given, read it and confirm the SQL it documents matches what was actually applied.

Return your verdict as a JSON object: {county: "${c.slug}", letters_checked: [...], per_letter: [{letter, claimed_metric, fresh_metric, matches: true/false, sample_rows_checked: [...], real_data_confirmed: true/false/undetermined, regression_detected: true/false, verdict: "survived"|"refuted", reason}], overall_verdict: "survived"|"refuted"|"partially_survived", notes}.
Be concrete and cite the actual query results you ran.
`
}

phase('Diagnose-Fix')
log(`Starting gold-standard shard-4 (6284f4fc): ${COUNTIES.map(c => c.slug).join(', ')}`)

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

log('Both counties fixed + adversarially verified. Results:')
verified.forEach(v => {
  if (v) log(`${v.county}: ${v.verdict?.overall_verdict ?? 'unknown'}`)
  else log('a county agent failed/skipped')
})

phase('Closeout')
const closeoutPrompt = `
SESSION CLOSEOUT — dispatch 6284f4fc-ce46-4f84-bb14-a92199aa0dcf, shard-4 (st_johns/nassau).
Repo: /home/runner/work/cli-anything-biddeed/cli-anything-biddeed.

Two counties were worked this session with fix + adversarial-verify results below. Your job is ONLY to close out the session per the mandatory protocol — do not attempt any further fixes.

RESULTS:
${JSON.stringify(verified, null, 2)}

STEPS:
1. For each county, run SET statement_timeout = 0; SELECT public.pencil_dod_evaluate_county('<slug>'); fresh via the Management API (https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query, Authorization: Bearer $SUPABASE_ACCESS_TOKEN) to get the final live A-J JSON for st_johns and nassau.
2. Run this close-out UPDATE (adjust criteria_passed to the REAL final A-J booleans from step 1, and only treat a letter as passing if refuter overall_verdict was "survived" or "partially_survived" for it — a "refuted" claim must NOT be recorded as passed even if the raw metric looks like it crossed 95%%):
   UPDATE public.gold_standard_campaign
   SET criteria_passed = '{"A": true, "B": true, ...}'::jsonb,
       criteria_total = 10,
       exit_reason = 'timeout',
       session_end_at = now()
   WHERE dispatch_id = (SELECT id FROM summit_chat_dispatch WHERE state='processing' ORDER BY updated_at DESC LIMIT 1);
   If that subquery doesn't resolve to a row scoped to this shard, look up the correct row by dispatch_id '6284f4fc-ce46-4f84-bb14-a92199aa0dcf' directly against summit_chat_dispatch instead, and report which path you used. This UPDATE is likely to need TWO rows written (one per county, if gold_standard_campaign is per-county) — check the table's actual grain (does it have a county/target_counties column?) before assuming a single row covers both.
3. Do NOT run public.gold_standard_loop() or public.gold_standard_certify() — other shards may be mid-flight concurrently. Only run per-county pencil_dod_evaluate_county.
4. Any letter where the refuter verdict was "refuted": log it explicitly in your summary as a false-positive, not counted as progress, and do not write it as true in criteria_passed.
5. Produce the final session report as a single structured object: {dispatch_id: '6284f4fc-ce46-4f84-bb14-a92199aa0dcf', counties: [{slug, letters_targeted, before (A-J from the session brief), after (fresh A-J from step 1), refuter_verdict_summary, migration_files, git_commits}], closeout_sql_executed: true/false, closeout_row_updated: true/false}.
This report IS the loop closure required by CLAUDE.md — paste literal before/after JSON per county, do not summarize away the numbers.
`
const closeout = await agent(closeoutPrompt, { label: 'closeout', phase: 'Closeout' })

return { dispatch_id: '6284f4fc-ce46-4f84-bb14-a92199aa0dcf', counties: COUNTIES.map(c => c.slug), verified, closeout }
