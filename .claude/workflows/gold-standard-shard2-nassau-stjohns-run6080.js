export const meta = {
  name: 'gold-standard-shard2-nassau-stjohns-run6080',
  description: 'Gold Standard shard-2 (dispatch ffe1aa89, loop run 6080): st_johns C/D/E/I/J 4-row enrichment gap (calendar_sweep_mca_v3 stub rows), nassau 10/10 audit-freshness refresh, adversarially verify',
  phases: [
    { title: 'Investigate+Fix', detail: 'stjohns_enrich + nassau_audit agents, worktree-isolated' },
    { title: 'Verify', detail: 'independent refuter per claim' },
  ],
}

const DISPATCH_ID = 'ffe1aa89-758e-42a2-8ac2-73ceeee9d290'

const BASELINE = `Baseline (VERIFIED live via pencil_dod_evaluate_county() just now, more current than the brief's numbers --
the brief's st_johns C/D/E/I/J read 86-92%%, live reads 92%% across the board, meaning some drift/partial-fix already
landed since the brief was written; treat the live numbers below as ground truth, not the brief):

nassau: 10/10, ALL PASS. A=5(fc=29,td=5) B=100.0(verified=11,closed_sold=11) C=100.0(matched_clean=34)
D=100.0(matched_any=34) E=100.0(parcel_linked=34) F=100.0(tier1_sold=11,closed_sold=11) G=100.0(density=100.0,
far=blank/no-applicable-parcels,pk1000=blank) H=9h(SLA 48h) I=100.0(card_complete=34 of 34) J=100.0(deal_complete=34).
auctions_total=34. gold_standard_ultraloop_audit freshness (VERIFIED live query): A/B/C/D/E/F/H/I fresh within the
7-day certify window (2026-07-20/21), J freshest (2026-07-23), but G's last audit row is 2026-07-18 -- 6 days old as
of today 2026-07-24, will fall OUTSIDE the 7-day certify-gate window within ~24h. This is the one concrete, real gap
in an otherwise fully-passing county.

st_johns: 5/10. A=PASS(fc=47,td=3) B=PASS(verified=1,closed_sold=1) F=PASS(tier1_sold=1,closed_sold=1)
G=PASS(density=100.0,far=100.0,pk1000=blank) H=PASS(1.1h). C=FAIL 92.0(matched_clean=46) D=FAIL 92.0(matched_any=46)
E=FAIL 92.0(parcel_linked=46) I=FAIL 92.0(card_complete=46 of 50) J=FAIL 92.0(deal_complete=46). auctions_total=50.
gold_standard_ultraloop_audit: all 10 letters last audited 2026-07-19 (5 days ago, still inside the 7-day window,
expires ~2026-07-26 -- not urgent today but do not let your work go un-logged).

ROOT CAUSE, ALREADY IDENTIFIED (VERIFIED via direct query on multi_county_auctions just now -- do not re-derive,
start from this): C/D/E/I/J are ALL blocked by the EXACT SAME 4 rows out of 50 (46/50=92.0%% matches every one of
those letters exactly, confirming a single shared root cause, not five independent problems):
  case_number   sale_type    status    parcel_id  property_address  lat        assessed_value  plaintiff  owner_name  source_url  data_source            parity_status       created_at
  CA22-1233     foreclosure  upcoming  NULL       NULL              29.8943    200000          NULL       NULL        NULL        calendar_sweep_mca_v3  matched_divergent   2026-07-22
  CA25-1470     foreclosure  upcoming  NULL       NULL              29.8943    200000          NULL       NULL        NULL        calendar_sweep_mca_v3  matched_divergent   2026-07-23
  CC25-0048     foreclosure  upcoming  NULL       NULL              29.8943    200000          NULL       NULL        NULL        calendar_sweep_mca_v3  matched_divergent   2026-07-22
  CC25-2919     foreclosure  upcoming  NULL       NULL              29.8943    200000          NULL       NULL        NULL        calendar_sweep_mca_v3  matched_divergent   2026-07-23
These are bare stub rows written by the calendar_sweep_mca_v3 scraper: it registered the case exists (case_number,
sale_type='foreclosure', auction_status='upcoming') but never enriched property_address, parcel_id, plaintiff, or
owner_name, and never set source_url. HONESTY FLAG worth a quick look before you build on top of it: latitude=29.8943
and assessed_value=200000 are IDENTICAL across all 4 rows, which reads like a county-centroid/placeholder default
rather than 4 independently scraped values -- confirm whether calendar_sweep_mca_v3 is writing a hardcoded default
for these two fields (if so this may affect other counties fed by the same scraper, worth a one-line note in your
report, but do NOT go audit other counties in this session -- out of shard, out of scope, just flag it).

PRIOR SESSION CONTEXT ON ST_JOHNS (2026-07-10, pipeline.counties.notes, VERIFIED still there): a DIFFERENT set of 5
case numbers (CA25-0128, CA25-0351, CA25-0475, CA25-1757, CC25-4817 -- none overlap with today's 4) were found to
genuinely have no Property Address on saintjohns.realforeclose.com's raw AITEM HTML and empty parcel KeyValue=,
confirmed directly (not a scraper bug), with a recommendation to recheck near actual auction dates. Also confirmed
just now: apps.stjohnsclerk.com (Landmark/TaxSmart official records) returns 403 to plain WebFetch (WAF-protected),
and saintjohns.realforeclose.com's calendar page ALSO 403s plain WebFetch -- both need an authenticated
session/browser automation, not raw HTTP GET (use the firecrawl-browser or browser-use skill, not WebFetch, for
these two hosts). St Johns Property Appraiser search (cross-reference only, not a case-number search) lives at
https://qpublic.schneidercorp.com/Application.aspx?App=StJohnsCountyFL&Layer=Parcels&PageType=Search (Schneider/
QPublic platform, confirmed live). pipeline.counties: foreclosure_platform='realforeclose', foreclosure_url=
'https://saintjohns.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR', taxdeed_platform=null (foreclosure
lane only for this county).`

const RECIPE = `
Environment (already available, do not ask for credentials):
- Live arbitrary SQL (the ONLY working DB path -- direct psql/pooler connections FAIL with password auth errors,
  confirmed this session, do not waste time on that): POST
  https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query
  headers Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json
  body {"query": "<sql>"} -- run "SET statement_timeout = 0;" first in the same query string for anything heavy.
  Build the JSON body with a real encoder (python3 -c "import json; ..." to a temp file, then curl --data-binary
  @file) rather than hand-quoting shell strings.
- REST reads/writes: GET/PATCH/POST \${SUPABASE_URL}/rest/v1/<table>?... with headers
  apikey: $SUPABASE_SERVICE_ROLE_KEY, Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY
- pencil_dod_evaluate_county RPC (confirmed live this session): POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county
  body {"p_county": "st_johns"} (or "nassau") -- returns one jsonb object with keys A..J (each {pass,metric,detail}),
  county, auctions_total, V2_LITMUS. This is your before/after proof. C/D require parity_status='matched_clean' (C) or
  IN ('matched_clean','matched_divergent') (D) AND parity_source LIKE 'tier1%%' -- setting parity_status alone does
  NOT satisfy C/D, parity_source must also start with 'tier1'. E = parcel_id IS NOT NULL, no threshold beyond 95%%. I
  additionally requires property_address, lat/long (or po_latitude/po_longitude), assessed_value/market_value ALL
  non-null AND the parcel_id (or tax_account) present with zone_code in v_zoning_gold_standard_card. J requires a
  bid_decisions row matched by case_number with arv+max_bid+ml_score+all 5 factor keys.
- The canonical parity matcher is public.refresh_parity_tier1_outcomes(p_county text default 'brevard') -- an RPC,
  not something to reimplement. Call it via the Management API SQL endpoint
  (SELECT * FROM public.refresh_parity_tier1_outcomes('st_johns');) after inserting/updating rows, never hand-write
  parity_status/parity_source yourself.
- realforeclose.com and stjohnsclerk.com hosts 403 plain WebFetch (WAF-protected) -- use the firecrawl-browser or
  browser-use skill (authenticated/rendered session) for these, not raw WebFetch/curl.
- gh CLI is authenticated (repo, workflow scopes) for git operations.
- Repo root is the current working directory (worktree-isolated), on main. Any UPDATE to multi_county_auctions
  columns is a data backfill, not a schema change -- still write a short documentation migration file under
  supabase/migrations/<date>_shard2_stjohns_<purpose>.sql or supabase/migrations/<date>_shard2_nassau_<purpose>.sql
  per this campaign's house style: narrative comment block with VERIFIED evidence, then the idempotent SQL that
  mirrors what you ran live (see supabase/migrations/20260718p_gold_standard_dixie_cd_structural_ceiling_refutation_487365d5.sql
  for the exact pattern). Any genuine schema change (new column, new table) needs a real migration, not just
  documentation.

ULTRALOOP audit logging (mandatory): for every letter you claim moved OR claim you verified as
correctly-passing/correctly-blocked/residual, INSERT one row into public.gold_standard_ultraloop_audit: columns
dispatch_id (uuid '${DISPATCH_ID}'), ultraloop_mode ('fallback' -- manual Workflow-tool fan-out, not native
/effort ultracode), county_slug, letter, claim (short text), refuter_evidence (jsonb -- your evidence), survived
(boolean, true only if it held up under adversarial check). POST to
\${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with service-role headers.

Hard rules:
- You own ONLY nassau and st_johns. Never touch any other county's rows or any other shard's files.
- PropertyOnion is litmus/comparison ONLY -- never write po_* derived values in as verified/independent.
- Fail-loud invariant: if a fix attempt finds zero real data for a row, report it as blocked/residual. NEVER
  fabricate case numbers, parcel IDs, addresses, coordinates, or sold amounts to make a metric look better -- this
  campaign has a documented fabrication-then-purge history in another county (dixie B/F, 2026-07-10); do not repeat
  it in any form, in either direction.
- Every claim must be tagged VERIFIED (you ran the query/request and are pasting real output), UNTESTED, or
  INFERRED (say why).
- Before finishing: call pencil_dod_evaluate_county for your county and paste the FULL before/after JSON. If a
  letter did not move, say so plainly -- a genuinely source-exhausted row is a valid, honest outcome.
- git commit any file you create/modify with a clear, county-scoped message. 'git pull --rebase origin main' before
  pushing (other shards may push concurrently to shared paths). Push directly to main -- no branches, no PRs.
- Do NOT run public.gold_standard_loop() or gold_standard_certify() -- other shards may be mid-session. Do NOT
  modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job.
- Budget yourself: this is ONE bounded pass. If a true fix requires building a brand-new scraper, do NOT build it
  now -- size the gap precisely and report it as scoped-out residual.

Return: { letters_touched: [...], fix_summary, sql_or_endpoints_used: [...], before_json, after_json,
residual_gaps: [...], honesty_notes: [...] }.
`

const TASKS = [
  {
    key: 'stjohns_enrich',
    prompt: `You are working Gold Standard shard-2, county "st_johns", letters C/D/E/I/J, inside the
cli-anything-biddeed repo (already checked out, on main).

${BASELINE}

Your job, in priority order:
1. For each of the 4 stub rows (CA22-1233, CA25-1470, CC25-0048, CC25-2919), attempt a REAL enrichment: use the
   firecrawl-browser or browser-use skill to look up the case on saintjohns.realforeclose.com (search/detail page by
   case number -- try the FNC=UPDATE diff endpoint or the standard case-detail view, plain WebFetch 403s this host)
   and/or the St Johns Clerk's official records (stjohnsclerk.com / apps.stjohnsclerk.com -- also needs browser
   automation, not WebFetch). Extract, if genuinely present: property_address, parcel_id/STRAP, plaintiff, owner
   name, sale_date, assessed/market value, and cross-reference the parcel via
   https://qpublic.schneidercorp.com/Application.aspx?App=StJohnsCountyFL&Layer=Parcels&PageType=Search (owner-name
   or address search) to get a real geocode and a confirmed parcel ID. If you find real data for a row, UPDATE
   multi_county_auctions for that case_number with the real values (never touch the placeholder-looking
   lat=29.8943/assessed_value=200000 fields with a GUESS -- only overwrite them with something you actually
   verified). If a row's data is genuinely not published yet (case truly has no address/parcel attached at the
   source, matching the pattern already confirmed for 5 OTHER st_johns cases in 2026-07-10), do not fabricate --
   report it as still-blocked with the live evidence you found, and note the actual sale date so a future session
   knows when to recheck.
2. After any UPDATE, run public.refresh_parity_tier1_outcomes('st_johns') via the Management API SQL endpoint to
   let the canonical matcher recompute parity_status/parity_source, then re-check pencil_dod_evaluate_county for
   E (parcel_id), C/D (parity), I (card completeness -- needs zone_code via v_zoning_gold_standard_card too, so a
   row can gain a real parcel_id and still miss I if st_johns zoning coverage doesn't reach that parcel; check and
   report this distinction if it happens), and J (independent of the other four -- check whether st_johns has ANY
   bid_decisions rows at all; if the generator has never run for this county, size the gap and report as residual,
   do not build a new generator this session).
3. Quick honesty check (do not rabbit-hole): confirm whether the identical lat=29.8943/assessed_value=200000 across
   all 4 rows is a calendar_sweep_mca_v3 scraper default -- note it plainly either way, do not fix the scraper itself
   this session (out of scope), just flag it accurately.
4. Log gold_standard_ultraloop_audit rows for whichever of C/D/E/I/J you touched or conclusively re-verified as
   blocked, per the RECIPE.

${RECIPE}`,
  },
  {
    key: 'nassau_audit',
    prompt: `You are working Gold Standard shard-2, county "nassau", auditing all 10 currently-PASSING letters
(A-J, nassau is 10/10) for gold_standard_ultraloop_audit freshness, inside the cli-anything-biddeed repo (already
checked out, on main).

${BASELINE}

Per EVALUATOR V6 RULES, gold_standard_certify() requires survived=true audit rows for ALL 10 letters within a 7-DAY
freshness window before a county can certify, even at 10/10. Nassau's G letter's most recent audit row is
2026-07-18 -- 6 days old as of today (2026-07-24) and will fall outside the 7-day window within ~24h. This is real
and worth fixing today. The other 9 letters (A/B/C/D/E/F/H/I/J) are still inside the window but several expire
within the next 1-3 days -- refresh anything you can within budget, prioritizing G first.

Your job: for each of the 10 letters, do a SHORT real adversarial sanity check against LIVE data (not just
re-reading the old audit row, actually query it fresh) and log ONE fresh gold_standard_ultraloop_audit row per
letter with survived=true -- UNLESS your sanity check finds a genuine problem, in which case investigate further and
either fix it (small, surgical, evidence-backed) or log survived=false with the honest reason. Since nassau is
already 10/10, your default expectation is confirmation, not fixing -- but be genuinely skeptical, don't rubber-stamp.

Suggested per-letter checks (adapt as needed, use real queries against live tables, not the cached numbers above):
- A: confirm fc=29 td=5 by counting real rows grouped by sale_type for nassau, fresh right now.
- B: confirm verified=11 closed_sold=11 is a real 1:1 count -- spot-check 2-3 of the 11 verified outcomes have real,
  non-PropertyOnion data_source values in tax_deed_outcomes/foreclosure_outcomes, not fabricated/promoted rows.
- C/D: confirm matched_clean/matched_any=34 (100%%) by spot-checking a few rows' parity_source actually starts with
  'tier1', not just parity_status being set.
- E: parcel_linked=34 of 34 -- spot-check a handful of parcel_id values are real Nassau County parcel/STRAP formats,
  not placeholders.
- F: tier1_sold=11 closed_sold=11 -- confirm real sold amounts, not zeros or round-number placeholders.
- G: density=100.0, far/pk1000 blank -- confirm via v_zoning_gold_standard_kpi_v3 / v_zoning_district_applicability
  that the blank far/pk1000 genuinely means "no applicable districts in nassau" (legitimate N/A), not missing data
  silently excluded from the denominator. This is the letter closest to expiring -- give it the most scrutiny.
- H: confirm last_seen_at is a genuine recent scrape timestamp, not stale/frozen.
- I: card_complete=34 of 34 -- confirm card fields (address, geo, value, zoned parcel) are non-placeholder for a
  couple of sampled rows.
- J: deal_complete=34 -- confirm bid_decisions rows have real arv/max_bid/ml_score and all 5 factor keys
  (distress_location, distress_property, distress_owner, cma_distressed, cma_resale), not zeros/nulls.

${RECIPE}`,
  },
]

phase('Investigate+Fix')
const fixResults = await pipeline(
  TASKS,
  (task) => agent(task.prompt, {
    label: `fix:${task.key}`,
    phase: 'Investigate+Fix',
    isolation: 'worktree',
    schema: {
      type: 'object',
      properties: {
        task: { type: 'string' },
        letters_touched: { type: 'array', items: { type: 'string' } },
        fix_summary: { type: 'string' },
        sql_or_endpoints_used: { type: 'array', items: { type: 'string' } },
        before_json: {},
        after_json: {},
        residual_gaps: { type: 'array', items: { type: 'string' } },
        honesty_notes: { type: 'array', items: { type: 'string' } },
      },
      required: ['fix_summary', 'before_json', 'after_json'],
    },
  })
)

phase('Verify')
const verified = await pipeline(
  fixResults.filter(Boolean),
  (result, task) => agent(
    `Independently verify this claimed Gold Standard result for shard-2 (${task.key === 'stjohns_enrich' ? 'st_johns' : 'nassau'}), ` +
    `task "${task.key}". You did NOT write this -- be skeptical.\n\n` +
    `Claimed result: ${JSON.stringify(result)}\n\n` +
    `${RECIPE}\n\n` +
    `Your job: re-run pencil_dod_evaluate_county('${task.key === 'stjohns_enrich' ? 'st_johns' : 'nassau'}') yourself ` +
    `RIGHT NOW (fresh call, do not trust the pasted after_json), compare against the claimed before/after, and check ` +
    `specifically for: (a) denominator mismatches, (b) ghost-success (any letter now passing/still-passing because ` +
    `of a placeholder/fabricated/default value rather than a real fix or a genuinely-verified real value -- ` +
    `especially scrutinize any lat/long or assessed_value that matches the known placeholder pattern ` +
    `lat=29.8943/assessed_value=200000), (c) whether any OTHER letter regressed as a side effect, (d) for B ` +
    `specifically, the only valid pass band is 95-105%%. If gold_standard_ultraloop_audit rows were claimed as ` +
    `inserted, spot-check 2-3 of them actually exist with real refuter_evidence (not boilerplate). Also INSERT your ` +
    `own gold_standard_ultraloop_audit row per the RECIPE (ultraloop_mode='fallback'). ` +
    `Return { task, refuted: boolean, refutation_reason: string|null, fresh_evaluation: <the JSON you just got>, survives: boolean }.`,
    {
      label: `verify:${task.key}`,
      phase: 'Verify',
      schema: {
        type: 'object',
        properties: {
          task: { type: 'string' },
          refuted: { type: 'boolean' },
          refutation_reason: { type: ['string', 'null'] },
          fresh_evaluation: {},
          survives: { type: 'boolean' },
        },
        required: ['refuted', 'fresh_evaluation', 'survives'],
      },
    }
  )
)

return { fixResults, verified }
