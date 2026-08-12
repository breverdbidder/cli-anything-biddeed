export const meta = {
  name: 'gold-standard-shard1-brevard-bradford-stjohns-madison-calhoun-7323433f',
  description: 'Gold Standard shard-1 (dispatch 7323433f): brevard I, st_johns I/J, calhoun C/D, madison A, three-county B/F sold-amount discovery — ULTRALOOP diagnose/fix/adversarial-verify',
  phases: [
    { title: 'Diagnose' },
    { title: 'Fix' },
    { title: 'Verify' },
    { title: 'Closeout' },
  ],
}

const DISPATCH_ID = '7323433f-7f95-4837-b952-1d569ec1acb6'
const CAMPAIGN_ROW_ID = 4183
const ISSUE_NUMBER = 18870
const REPO = 'breverdbidder/cli-anything-biddeed'

const RECIPE = `
ENVIRONMENT (already available in this sandbox, do not ask for credentials, NEVER echo/print/log any secret value):
- REST reads/writes: curl -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" "\${SUPABASE_URL}/rest/v1/<table>?...". PostgREST supports GET/POST/PATCH. Table multi_county_auctions uses columns: county (lowercase slug), case_number, sale_type (foreclosure|tax_deed), auction_date, auction_status, property_address, latitude, longitude, po_latitude, po_longitude, assessed_value, market_value, parcel_id, sold_amount, tier1_sold_amount, tier1_authoritative, tier1_sold_source, data_source. NOT "address" or "county_slug" -- those columns do not exist, this has already been confirmed live.
- pencil_dod_evaluate_county RPC (your before/after proof, ALWAYS run fresh, never reuse a stale paste): curl -X POST -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" -H "Content-Type: application/json" -d '{"p_county":"<slug>"}' "\${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county". Returns one JSON object keyed A..J, each {pass,metric,detail}.
- Live arbitrary SQL (DDL/DML/complex updates) -- this DOES work, confirmed live this session, use it freely for backfills and migrations: build the JSON body with python3 -c "import json; print(json.dumps({'query': SQL}))" > /tmp/q.json then curl -X POST -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" -H "Content-Type: application/json" --data-binary @/tmp/q.json "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query" -- then rm /tmp/q.json. Do not hand-quote SQL into a shell string, use the python json encoder. Direct psql / supabase CLI db push against the pooler and db host BOTH fail password auth in this sandbox (confirmed twice) -- do not retry them, use the Management API above instead for anything psql would normally do.
- gh CLI is authenticated (repo+workflow scopes) against ${REPO}, already on main, tree clean. Commit + push migrations directly to main per this repo's ship-to-main mandate -- no branches, no PRs.
- Skills available via the Skill tool for hard-to-scrape sites: "browser-use" and "firecrawl-browser" (real JS-executing browser sessions), "firecrawl-scrape"/"firecrawl-search" (static content + web search), WebSearch.
- Exact criterion I SQL contract (public.pencil_dod_evaluate_county, CTE c): a row counts as card_complete iff ALL of: property_address IS NOT NULL, COALESCE(latitude, po_latitude::double precision) IS NOT NULL, COALESCE(longitude, po_longitude::double precision) IS NOT NULL, COALESCE(assessed_value, market_value) IS NOT NULL, AND parcel_id is present in v_zoning_gold_standard_card (matched by parcel_id OR tax_account) WHERE zone_code IS NOT NULL for that county.
- Exact criterion J SQL contract (CTE d): a row counts as deal_complete iff a bid_decisions row exists with matching case_number AND arv IS NOT NULL AND max_bid IS NOT NULL AND ml_score IS NOT NULL AND factors ? 'distress_location' AND factors ? 'distress_property' AND factors ? 'distress_owner' AND factors ? 'cma_distressed' AND factors ? 'cma_resale'. Reference generator implementations exist for other counties: grep supabase/migrations/*.sql for "refresh_leon_bid_decisions" and "refresh_levy_bid_decisions" -- read one as a working pattern for the factors JSON shape and Shapira arv/max_bid math (there is no live county-agnostic generator function any more -- generate_bid_decisions_batch was checked live this session and no longer exists in pg_proc -- write county-scoped SQL/RPC yourself following the leon/levy pattern).
- Exact criterion B/F contract: closed_sold = count(*) WHERE sold_amount IS NOT NULL (NOT based on auction_status). B additionally requires an INDEPENDENT row in tax_deed_outcomes or foreclosure_outcomes for that case_number with data_source NOT ILIKE '%promote%'. F requires tier1_sold_amount populated on the same row with tier1_authoritative=true. B passes ONLY in the 95-105% band -- exceeding 105% is an auto-fail anomaly (denominator/double-count bug), not a pass.
- Exact criterion A contract: LEAST(count foreclosure rows, count tax_deed rows) > 0 for that county -- BOTH sale_type lanes must have at least one row.
- Exact criterion C/D contract: matched_clean / matched_any against parity_status on multi_county_auctions, denominator = auctions_total (PropertyOnion-excluded/tier1-authoritative rows only, per the WHERE clause on every CTE: county is lowercase AND (data_source <> 'propertyonion' OR tier1_authoritative=true)).

HARD RULES (from this codebase's CLAUDE.md and the dispatch brief -- follow exactly, no exceptions):
- You own ONLY the county+letter assigned to you in this prompt. Never touch another county's rows or another letter's fix.
- PropertyOnion (data_source='propertyonion', or any po_* field) is litmus/comparison ONLY. NEVER write po_*-derived values into sold_amount, tier1_sold_amount, or any field feeding B/F/C/D as if independently verified. NEVER set data_source='propertyonion' on a row you are trying to make PASS B.
- Fail-loud invariant: if you find zero real data for a fix, report it as blocked/residual with confidence UNTESTED or the honest reason. NEVER fabricate an address, geo coordinate, valuation, sold amount, date, or party name, and NEVER copy another row's/parcel's numbers as a stand-in. This exact repo has a documented double-revert history of fabricated Bradford I-values (supabase/migrations/20260703_shard13_polk_cd_realforeclose_matches_bradford_i_honesty_fix.sql and its revert 20260710_shard_bradford_i_refabrication_stop_and_e_appraiser_lookup.sql) -- zero tolerance, do not repeat that failure mode in ANY county.
- Ghost-success (lowering a threshold, redefining a criterion, or narrowing a denominator to manufacture a pass) is BANNED.
- Schema changes (new columns/tables) go through a committed supabase/migrations/<date>_shard1_<county>_<letter>_<purpose>.sql file, applied live via the Management API endpoint above, then committed+pushed to main. Data-only fixes (INSERT/UPDATE into existing tables/columns) do not need a migration file, just do them live via REST or the Management API and mention what you ran.
- Do NOT attempt to solve or bypass any CAPTCHA/Turnstile challenge. If one blocks you, report it and stop that angle.
- Do not run public.gold_standard_loop(), public.gold_standard_certify(), or modify cron jobs 109/111/115 or any gold-standard-loop-* job.
- Every claim you return must carry a confidence tag: VERIFIED (you ran the request yourself this turn and are basing the claim on real output), UNTESTED, or INFERRED (say why in one clause).
`

const TARGETS = [
  {
    county: 'brevard', letter: 'I',
    label: 'brevard-I',
    context: `Live baseline (VERIFIED this session): I metric=84.1 (card_complete=6096 of 7248), all other 9 letters PASS. Breakdown already run: missing_address=1109, missing_geo=131, missing_value=81 (these overlap, don't sum them). property_address is by far the dominant gap. parcel_id values for the gap rows look like short numeric BCPAO account numbers (e.g. "2406230") -- E (parcel linkage) already passes at 98.9% so parcel_id itself is populated on almost all rows, the gap is address/geo/value enrichment plus possibly the zoning-card join. ALREADY RULED OUT this session (do not repeat): joining multi_county_auctions.parcel_id to parcel_cache.parcel_id or to the generic "parcels" table produced ZERO matches for brevard -- those tables are not keyed the way brevard's BCPAO account numbers are. bcpao_enriched=true on only 157 of 7248 rows and bcpao_data IS NOT NULL on only 168 -- the BCPAO enrichment pipeline referenced in this repo's playbooks (E: "link parcel_id via the county property appraiser ArcGIS FeatureServer, Brevard/BCPAO pipeline is the reference implementation") has NOT been run against these gap rows. Find that existing BCPAO ArcGIS ingestion code (grep the repo for bcpao, BCPAO, ArcGIS, FeatureServer) and reuse/extend it for a bulk backfill of property_address + latitude/longitude + assessed_value for the ~1109 gap rows, keyed by parcel_id (BCPAO account number). This is the single largest point block in this session (1152-row gap out of ~19k total gap rows across the whole shard) -- prioritize real throughput over polish, a partial backfill that moves the metric materially still counts.`,
  },
  {
    county: 'st_johns', letter: 'I',
    label: 'st_johns-I',
    context: `Live baseline (VERIFIED this session): I metric=63.4 (card_complete=52 of 82). Small county, only ~30 gap rows -- feasible to inspect individually if bulk enrichment doesn't cover all of them. E already passes at 100% (parcel_id populated on every row) and G passes at 97.1%, so the zoning-card join should mostly work once address/geo/value are filled -- check with a live query which of the 4 card_complete conditions each gap row is actually failing before assuming it's the same shape as brevard.`,
  },
  {
    county: 'st_johns', letter: 'J',
    label: 'st_johns-J',
    context: `Live baseline (VERIFIED this session): J metric=65.9 (deal_complete=54 of 82), ~28 gap rows. bid_decisions rows likely exist for some of these with partial data (missing one of arv/max_bid/ml_score/the 5 factors keys) rather than missing entirely -- check with a live query (SELECT case_number, arv, max_bid, ml_score, factors FROM bid_decisions WHERE case_number IN (SELECT case_number FROM multi_county_auctions WHERE lower(county)='st_johns')) before writing any generator SQL, so you don't duplicate rows that already partially exist.`,
  },
  {
    county: 'calhoun', letter: 'C',
    label: 'calhoun-CD',
    context: `Live baseline (VERIFIED this session): C metric=87.5 (matched_clean=7), D metric=87.5 (matched_any=7), auctions_total=8 -- exactly ONE row is unmatched/divergent against the parity litmus (PropertyOnion comparison, litmus only, never a data source). This is a single-row forensic fix: find the one auction row with parity_status NULL or divergent, diagnose why (missing auction date, case-number format mismatch, etc per this repo's C/D playbook), and either backfill the matching field or document why it is a genuine litmus gap (PropertyOnion never covered it) -- if the latter, you are pre-authorized by this repo's STANDING AUTHORIZATIONS section to adopt a clerk/official-records supplementary litmus source instead, document the evidence.`,
  },
  {
    county: 'madison', letter: 'A',
    label: 'madison-A',
    context: `Live baseline (VERIFIED this session): A metric=0, detail "fc=6 td=0" -- madison has 6 foreclosure rows but ZERO tax_deed rows, confirmed via a direct REST query this session (multi_county_auctions WHERE county=eq.madison AND sale_type=eq.tax_deed returns an empty array). A requires BOTH lanes to have at least one row. Find Madison County FL's real tax deed sale source (per this repo's A playbook: configure both lanes per the pipeline county config; Madison is a small panhandle county, check for a RealTaxDeed / RealAuction / clerk-hosted tax deed sale list) and ingest at least the real, currently-scheduled tax deed auctions -- do not fabricate a single row to flip the boolean, it must be a real upcoming or historical Madison County tax deed sale with a real case/certificate number.`,
  },
  {
    county: 'madison', letter: 'B',
    label: 'madison-BF',
    context: `Live baseline (VERIFIED this session): B and F both FAIL with metric=null (closed_sold=0), because closed_sold is defined as count(*) WHERE sold_amount IS NOT NULL and every madison row has sold_amount NULL. One row is a strong lead, already confirmed via direct query this session: case_number "24-62-CA", auction_date 2026-07-28 (past), auction_status already set to "sold" in our data -- but sold_amount was never populated. Find the real sale outcome for Madison County FL foreclosure case 24-62-CA (clerk of court records, OCRS, or a real web search for the case number + "Madison County Florida foreclosure sale") and, if you find a genuine sold amount from an independent (non-PropertyOnion) source, write it to sold_amount + tier1_sold_amount + tier1_authoritative=true on that row, AND insert a corresponding row into foreclosure_outcomes with a real, non-'%promote%' data_source. If you cannot find it, report residual/blocked -- do not fabricate.`,
  },
  {
    county: 'calhoun', letter: 'B',
    label: 'calhoun-BF',
    context: `Live baseline (VERIFIED this session): B and F both FAIL with metric=null (closed_sold=0). Strong lead, already confirmed via direct query this session: tax_deed case_number "171 OF 2023", auction_date 2026-07-09 (past), auction_status already "completed" in our data -- but sold_amount was never populated. Find the real sale outcome for Calhoun County FL tax deed case "171 OF 2023" (clerk of court tax deed sale results, or a real web search) and, if you find a genuine sold amount from an independent (non-PropertyOnion) source, write it to sold_amount + tier1_sold_amount + tier1_authoritative=true on that row, AND insert a corresponding row into tax_deed_outcomes with a real, non-'%promote%' data_source. If you cannot find it, report residual/blocked -- do not fabricate.`,
  },
  {
    county: 'bradford', letter: 'B',
    label: 'bradford-BF',
    context: `Live baseline (VERIFIED this session): B and F both FAIL with metric=null (closed_sold=0). This exact target (case 25000457CAAXMX, auction_date 2026-07-16 past, still auction_status "upcoming" with sold_amount NULL) has ALREADY been worked by a prior session -- see .claude/workflows/gold-standard-shard6-bradford-run7177-f68d2ec5.js in this repo for the full history: civitekflorida.com OCRS anonymous search and the bradfordclerk.com Box.com "FORECLOSURE SALE LIST" link were both pursued and reportedly dead-ended (Cloudflare-blocked / no results). Read that file first. Spend at most one focused attempt on a genuinely NEW angle not already listed in that file (e.g. a different OCRS county code, a direct clerk phone/records-request page, or a fresh web search for the specific case number or property address that a prior session did not try) -- if you find nothing new, report residual/blocked immediately rather than re-running the same dead leads, this county has had 6+ prior sessions on this exact case.`,
  },
]

phase('Diagnose')
const results = await pipeline(
  TARGETS,
  (target) => agent(
    `Gold Standard ULTRALOOP shard-1, dispatch ${DISPATCH_ID}. You are the DIAGNOSE agent for county="${target.county}" letter="${target.letter}".\n\n${RECIPE}\n\nTARGET CONTEXT:\n${target.context}\n\nYOUR JOB: run live queries (REST or Management API SQL, your choice) to independently confirm the current metric and pin down the exact root cause of the gap for THIS county+letter only. Do not fix anything yet. Propose a concrete, scoped fix plan that uses only real data (no fabrication) and is executable via REST/Management-API/gh from this sandbox.\n\nReturn structured output: county, letter, root_cause (what you found, cite the query), fixable ("yes"|"no"|"partial"), fix_plan (concrete steps + exact tables/columns/sources), confidence (VERIFIED|UNTESTED|INFERRED), evidence (the actual query output you saw).`,
    {
      label: `diagnose:${target.label}`,
      phase: 'Diagnose',
      schema: {
        type: 'object',
        properties: {
          county: { type: 'string' },
          letter: { type: 'string' },
          root_cause: { type: 'string' },
          fixable: { type: 'string', enum: ['yes', 'no', 'partial'] },
          fix_plan: { type: 'string' },
          confidence: { type: 'string', enum: ['VERIFIED', 'UNTESTED', 'INFERRED'] },
          evidence: { type: 'string' },
        },
        required: ['county', 'letter', 'root_cause', 'fixable', 'fix_plan', 'confidence', 'evidence'],
      },
    }
  ),
  (diagnosis, target) => {
    if (!diagnosis || diagnosis.fixable === 'no') {
      log(`${target.label}: diagnosed as not fixable this session, skipping fix stage. Root cause: ${diagnosis ? diagnosis.root_cause : 'diagnose agent returned null'}`)
      return Promise.resolve({ target, diagnosis, fix: null })
    }
    return agent(
      `Gold Standard ULTRALOOP shard-1, dispatch ${DISPATCH_ID}. You are the FIX agent for county="${target.county}" letter="${target.letter}". A separate diagnose agent (not you) already investigated this and produced the plan below -- verify it still holds with a fresh query before acting, root causes can be stale by the time you run.\n\n${RECIPE}\n\nTARGET CONTEXT:\n${target.context}\n\nDIAGNOSIS FROM PRIOR STAGE:\n${JSON.stringify(diagnosis)}\n\nYOUR JOB: capture a fresh BEFORE metric via pencil_dod_evaluate_county for "${target.county}", then actually execute the fix plan (or your own better plan if the diagnosis was wrong) using real data only. Write real rows/columns via REST or Management API SQL. Commit+push any migration file to main if you created one. Then capture a fresh AFTER metric via pencil_dod_evaluate_county for "${target.county}" and report exact row counts written per table.\n\nReturn structured output: county, letter, action_taken (what you actually ran, be specific), rows_written (object mapping table name to integer count, empty object if none), before_metric (the letter's {pass,metric,detail} object from your BEFORE call), after_metric (same shape, from your AFTER call), claim (one sentence: what changed and why it should now pass, or honest statement that it's still blocked), confidence (VERIFIED|UNTESTED|INFERRED).`,
      {
        label: `fix:${target.label}`,
        phase: 'Fix',
        schema: {
          type: 'object',
          properties: {
            county: { type: 'string' },
            letter: { type: 'string' },
            action_taken: { type: 'string' },
            rows_written: { type: 'object' },
            before_metric: {},
            after_metric: {},
            claim: { type: 'string' },
            confidence: { type: 'string', enum: ['VERIFIED', 'UNTESTED', 'INFERRED'] },
          },
          required: ['county', 'letter', 'action_taken', 'claim', 'confidence'],
        },
      }
    ).then((fix) => ({ target, diagnosis, fix }))
  },
  (fixed) => {
    if (!fixed || !fixed.fix) {
      return Promise.resolve({ ...fixed, verify: null })
    }
    const { target, fix } = fixed
    return agent(
      `Gold Standard ULTRALOOP shard-1, dispatch ${DISPATCH_ID}. You are the ADVERSARIAL REFUTER for county="${target.county}" letter="${target.letter}". You did NOT do this fix -- be skeptical, your only goal is to try to break the claim below.\n\n${RECIPE}\n\nCLAIMED FIX:\n${JSON.stringify(fix)}\n\nYOUR JOB: (1) run pencil_dod_evaluate_county for "${target.county}" yourself, fresh, right now -- do not trust the pasted after_metric. (2) Check for the anomaly classes this protocol exists to catch: B or F metric > 105% (denominator/double-count bug, auto-fail), any po_*-derived or data_source='propertyonion' row masquerading as an independent B/F outcome, any fabricated-looking value (round numbers, copied from another row, no source citation), ghost-success (threshold/denominator narrowed instead of genuinely fixed). (3) If letter is B, confirm the outcome row's data_source does NOT ILIKE '%promote%' and is genuinely independent. Then write your verdict as a row into gold_standard_ultraloop_audit via REST POST: curl -X POST -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" -H "Content-Type: application/json" -H "Prefer: return=minimal" -d '{"dispatch_id":"${DISPATCH_ID}","ultraloop_mode":"fallback","county_slug":"${target.county}","letter":"${target.letter}","claim":"<the claim text>","refuter_evidence":{...your real findings...},"survived":true_or_false}' "\${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit" -- build the JSON body with python3's json.dumps, do not hand-quote. Confirm the insert succeeded (HTTP 201, or check for a returned/queryable row) before returning.\n\nReturn structured output: county, letter, claim (echo the claim you evaluated), refuted (boolean), refutation_reason (string or null), fresh_metric (the {pass,metric,detail} object you just measured), survives (boolean -- your final verdict), audit_row_written (boolean -- did your POST to gold_standard_ultraloop_audit actually succeed).`,
      {
        label: `verify:${target.label}`,
        phase: 'Verify',
        schema: {
          type: 'object',
          properties: {
            county: { type: 'string' },
            letter: { type: 'string' },
            claim: { type: 'string' },
            refuted: { type: 'boolean' },
            refutation_reason: {},
            fresh_metric: {},
            survives: { type: 'boolean' },
            audit_row_written: { type: 'boolean' },
          },
          required: ['county', 'letter', 'refuted', 'survives', 'audit_row_written'],
        },
      }
    ).then((verify) => ({ ...fixed, verify }))
  }
)

const survived = results.filter(Boolean).filter(r => r.verify && r.verify.survives)
const refuted = results.filter(Boolean).filter(r => r.verify && !r.verify.survives)
const notAttempted = results.filter(Boolean).filter(r => !r.fix)
log(`ULTRALOOP complete: ${survived.length} fixes survived adversarial verification, ${refuted.length} refuted (logged as false positives), ${notAttempted.length} not fixable this session.`)

phase('Closeout')
const closeout = await agent(
  `Gold Standard ULTRALOOP shard-1, dispatch ${DISPATCH_ID}, campaign row id ${CAMPAIGN_ROW_ID}, GitHub issue #${ISSUE_NUMBER} in ${REPO}. You are the CLOSEOUT agent -- this is the mandatory session close-out for this shard (brevard, bradford, st_johns, madison, calhoun).\n\n${RECIPE}\n\nSESSION RESULTS FROM THIS WORKFLOW (diagnose/fix/verify already ran per-letter, do not redo the fixes, just report on them honestly):\n${JSON.stringify(results.filter(Boolean))}\n\nYOUR JOB, IN ORDER:\n1. Run pencil_dod_evaluate_county fresh for EACH of brevard, bradford, st_johns, madison, calhoun (5 separate calls, all fresh right now -- do not reuse any number from the JSON above without re-querying, that JSON may already be stale). Build the literal A-J pass/fail JSON for each county.\n2. Compile a plain-text session report: for each county, list the before (from the original dispatch brief numbers below) vs after (your fresh query) score out of 10, and which specific letters moved and why (or why not, for refuted/blocked items -- be honest about failures, BLANK > WRONG).\n\nORIGINAL DISPATCH BRIEF SCORES (for your before/after comparison only, these are what the session started at): brevard 9/10 (I failing), bradford 8/10 (B,F failing), st_johns 8/10 (I,J failing), madison 7/10 (A,B,F failing), calhoun 6/10 (B,C,D,F failing).\n3. Post your session report as a comment on GitHub issue #${ISSUE_NUMBER} in ${REPO} using: gh issue comment ${ISSUE_NUMBER} --repo ${REPO} --body-file <path to a temp file containing your report> (write the report to a temp file first, do not try to inline a multi-paragraph body as a shell argument).\n4. Update the campaign checkpoint row via REST PATCH: curl -X PATCH -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" -H "Content-Type: application/json" -d '{"criteria_passed":{...the actual A-J true/false for whichever single county is most representative, or note in exit_reason that this is a 5-county shard...},"criteria_total":10,"exit_reason":"timeout","session_end_at":"<current UTC ISO8601 timestamp from date -u>"}' "\${SUPABASE_URL}/rest/v1/gold_standard_campaign?id=eq.${CAMPAIGN_ROW_ID}" -- get the real current timestamp from the date command, do not guess it, Date.now() is unavailable to you but the shell 'date' command is not.\n5. Confirm both the issue comment and the campaign PATCH actually succeeded (re-fetch and check) before returning.\n\nReturn a plain text summary (not JSON) of: the 5 fresh before/after scores, which letters survived adversarial verification and shipped, which were refuted, which are residual/blocked and why, confirmation the issue comment posted (with its URL), and confirmation the campaign row was updated.`,
  { label: 'closeout', phase: 'Closeout' }
)

return { results, closeout }
