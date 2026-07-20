export const meta = {
  name: 'gold-standard-shard1-run5361',
  description: 'Gold Standard shard-1 (clay/manatee/martin/holmes): diagnose, fix, adversarially verify failing letters per county',
  phases: [
    { title: 'Diagnose+Fix', detail: 'one agent per county, worktree-isolated' },
    { title: 'Verify', detail: 'independent refuter per county claim' },
  ],
}

const DISPATCH_ID = '7abd0202-3b36-494c-bed2-9bdea65987e2'

const COUNTIES = [
  {
    slug: 'clay',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now, matches the brief exactly):
10/10 -- ALL LETTERS PASS. A=68(fc=68 td=72), B=100.0(verified=11 closed_sold=11), C=100.0(140 of 140),
D=100.0(140 of 140), E=100.0(140 of 140), F=100.0(11 of 11), G=97.6(density=97.6), H=1.0h, I=100.0(140 of 140),
J=100.0(140 of 140). auctions_total=140.

YOUR JOB IS NOT TO "FIX" ANYTHING -- there is nothing failing. Per EVALUATOR V6 RULES, gold_standard_certify()
requires survived=true rows in gold_standard_ultraloop_audit for ALL 10 letters within a 7-day freshness window
before a county can certify, even if the scoreboard shows 10/10. VERIFIED live via a direct query just now: clay
has FRESH (within 7 days) audit rows for C, D, G, I, J only -- letters A, B, E, F, H have ZERO audit rows in the
last 7 days (some may have older rows, but freshness requires <=7d). That is your primary deliverable: close this
gap honestly.

Your job: (1) re-verify each of the 10 letters fresh against pencil_dod_evaluate_county output (paste the literal
JSON), (2) for each of the 5 gap letters (A, B, E, F, H) specifically, do a SHORT adversarial sanity check (does
the denominator make sense? for B, confirm 100.0 is a real ratio of real independent-source rows, not a
coincidental 11/11 that masks a scoping issue; for E, spot-check a handful of parcel_id values are real BCPAO
parcel numbers, not placeholders; for H, confirm last_seen is a genuine recent scrape timestamp), (3) INSERT one
gold_standard_ultraloop_audit row per letter for ALL 10 letters (the 5 gap letters are mandatory net-new rows; for
C/D/G/I/J you may add a fresh confirmation row too if you have time, but the 5 gap letters are the actual
deliverable) with survived=true and real refuter_evidence for each, UNLESS you find a genuine problem -- in which
case fix it for real (small, surgical, evidence-backed) before logging, or log survived=false with the honest
reason if it can't be fixed this pass. Do not spend more than a small fraction of a normal session's budget here;
this county is in maintenance mode, not build mode.`,
  },
  {
    slug: 'manatee',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now, matches the brief exactly): 9/10.
Only G fails: metric=64.7 (density=96.3 far=100.0 pk1000=64.7 -- G is LEAST(density,far,pk1000), pk1000 is the
binding constraint). All other letters PASS: A=3(fc=81 td=3), B=100.0(verified=5 closed_sold=5), C=96.4(81 of 84),
D=96.4(81 of 84), E=96.4(81 of 84), F=100.0(5 of 5), H=2.0h, I=96.4(81 of 84), J=100.0(84 of 84).

G ROOT CAUSE, FULLY SIZED (VERIFIED live via v_zoning_gold_standard_kpi_v3 and a direct parcel_zones/zoning_districts/
zone_standards join just now -- do not re-derive this, it is exact): manatee has 971 total zoned parcels. Density
(96.3%%) and FAR (100.0%%) both already clear the 95%% bar -- do NOT touch them. Parking (pk1000) has only 17
"pk1000_applicable" parcels county-wide (per v_zoning_district_applicability), and exactly 6 of those 17 are NULL,
giving 64.7%%. The 6 NULL parcels resolve to exactly TWO zoning districts, both in "Unincorporated Manatee County"
(jurisdiction_id=1257):
  - code=HM "Heavy Manufacturing (verified FAR)", district_id=11249, standard_id=3988, 5 parcels. Already has a
    REAL ordinance citation for FAR: source_url=".../ldc-ch4-zoning-v64-comments.pdf" (Manatee LDC Ch.4 zoning
    table), ordinance_section="Sec 401.4, Figure 6-2, page 4-25 (top of page 74)". parking_per_1000sf is NULL.
  - code=LM "Light Manufacturing", district_id=10896, standard_id=3602, 1 parcel. Its existing source_url is
    "shard9_run651_INFERRED:standard_fl_ldr_pattern_manatee_lm" -- a PRIOR SESSION'S INFERRED PLACEHOLDER, not a
    real ordinance citation. parking_per_1000sf is NULL.

Manatee's LDC keeps off-street parking requirements in a SEPARATE parking-ratio table (typically Article 7 /
"Off-Street Parking and Loading" or similar), organized BY USE not by district -- the dimensional-standards table
you already have citations for (Sec 401.4) covers lot/setback/FAR/height, not parking ratios. Find the real Manatee
County LDC parking chapter (search mymanatee.org LDC PDF, likely the same ldc document set as the ch4 file already
cited, look for the chapter covering "off-street parking" or "parking and loading"), locate the industrial-use
parking ratio (Heavy Manufacturing / Light Manufacturing or the general "Industrial" use classification if the
code doesn't split HM/LM separately -- if the code applies one ratio to all industrial uses, that is a legitimate
finding, cite it as such), and UPDATE zone_standards.parking_per_1000sf for standard_id 3988 and 3602 with the real
value + source_url + ordinance_section citation. This is a 2-row, precisely-scoped backfill -- do NOT touch
density or FAR (already passing), do NOT touch any other manatee district, do NOT touch any other county.

If after a genuine search you cannot find a real, citable parking ratio for these two use classes (e.g. the code
is silent or industrial parking is regulated by a formula you can't map to parking_per_1000sf cleanly), do NOT
fabricate a number or replace the LM placeholder with a different guess -- report the gap honestly as residual and
do not touch the rows. BLANK > WRONG. This campaign has a documented history of exactly this failure mode (gulf
B/F fabrication, purged) -- the existing LM row is itself a mild version of it (an INFERRED placeholder standing
in for a real citation) and should be corrected to either a real value or left honestly null, not deepened.`,
  },
  {
    slug: 'martin',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now, matches the brief exactly): 8/10.
E and I both fail at the SAME metric=91.9 (parcel_linked=34, card_complete=34, both of 37) -- this is not a
coincidence, I is structurally gated on E (a property card cannot be complete without a linked parcel_id), so
fixing E's 3 rows will very likely fix I for free. All other letters PASS: A=1(fc=36 td=1), B=100.0(verified=1
closed_sold=1), C=97.3(36 of 37), D=97.3(36 of 37), F=100.0(1 of 1), G=100.0, H=2.0h, J=100.0(37 of 37).

IMPORTANT PRIOR CONTEXT (read before doing anything): martin was already brought to a VERIFIED 10/10 on
2026-06-27 via commit fe94c9fe ("corrected martin_fix run1113 ... martin: 10/10 PASS A-J auctions_total=29").
auctions_total has since grown from 29 to 37 (8 new rows ingested) -- this is the SAME "growing denominator"
regression pattern flagged elsewhere in this campaign (see recent commit d416248d "restore lee C/D after
incidental live sweep grew denominator"), not a new bug. There is also a STALE gold_standard_ultraloop_audit row
for martin E/I dated 2026-07-19T21:49 with survived=true -- that row is now inaccurate (it predates the current
regression) and must NOT be relied on; log fresh rows once you've re-fixed the metric.

THE EXACT GAP (VERIFIED live via a direct query just now, do not re-derive): all 3 parcel_id-NULL rows are
foreclosure cases, auction_status='upcoming', all with property_address currently just the generic
"Stuart, Martin County, FL 34997" (no street address captured):
  case_number 23001555CCAXMX
  case_number 25001634CCAXMX
  case_number 25001632CCAXMX

Read scripts/shard4_martin_geocode_backfill.py, scripts/shard12_run1113_martin_fix.py, and
scripts/shard14_martin_bay_alachua_lake_cd_e_i_fix.py in full before writing anything new -- they are the prior
sessions' working martin E/I/geocode patterns; reuse rather than reinvent. Since these are FORECLOSURE cases (not
tax deed), the property address is not on the tax roll by case number -- it needs to come from the case docket
(the lis pendens / complaint typically states the legal description and situs address). Try, in order: (1)
martin.realforeclose.com case-detail page for each case number (search the calendar/case-search UI) -- RealAuction
foreclosure case pages often surface the property address directly; (2) Martin County Clerk's official records /
court case search (martinclerk.com or similar) for the case number to pull the address from the docket; (3) once
you have a street address, Martin County Property Appraiser (search for Martin County PA's ArcGIS FeatureServer,
e.g. via pa.martin.fl.us or mcpafl.org-style domain -- verify the real live domain, do not guess) to resolve
parcel_id + geo + assessed value. Playbook E: "link parcel_id via the county property appraiser ArcGIS
FeatureServer" is the reference pattern.

If a case number genuinely cannot be resolved to an address/parcel via any live public source (e.g. case sealed,
docket not public, PA has no match), do not fabricate a parcel_id -- report it as a residual with the specific
blocker. Only 3 rows are in play; a full fix (all 3) or partial (1-2) are both real progress, report exactly which.`,
  },
  {
    slug: 'holmes',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now, matches the brief exactly): 6/10.
Failing: B=null(verified=0 closed_sold=0), C=61.5(matched_clean=8 of 13), D=61.5(matched_any=8 of 13),
F=null(tier1_sold=0 closed_sold=0). Passing: A=3(fc=3 td=10), E=100.0(13 of 13), G=100.0, H=7.0h,
I=100.0(13 of 13), J=100.0(13 of 13). auctions_total=13 -- this is a genuinely tiny county.

CRITICAL PRIOR CONTEXT -- read this in full before spending any budget: holmes B/C/D/F has now been independently
investigated and reconfirmed BLOCKED across (at least) 3 consecutive sessions over 8+ days:
  - commit 786b84ef (shard-2, holmes bootstrap)
  - commit 08b75f29 (shard-12 run3534): "gold-standard-shard12 holmes: clerk C/D re-verify harvester + B/F
    not-yet-measurable finding" -- confirmed holmesclerk.com is forward-looking-notice-board ONLY, no
    results/disposition page, no case-search tool, "Lands Available for Taxes" explicitly empty. The 5 remaining
    unmatched TD# cases (TD#2023-225, TD#2023-496, TD#2023-584, TD#2023-185, TD#2020-589) have rolled off the live
    "upcoming sales" listing entirely and cannot be matched from that source.
  - commit 11848338 (shard-6 run4870): "holmes B/C/D/F residual investigation, 3 new avenues exhausted" --
    Firecrawl (zero credits at the time), Official Records index (CAPTCHA-gated on the actual search POST), Tax
    Collector roll lookup (real data, but status-only, no disposition/dollar field). No writes made.
Read scripts/shard12_run3534_holmes_clerk_cd_bf_harvest.py and scripts/shard6_run4870_holmes_cd_bf_residual_investigation.py
in full for exact URLs/endpoints already tried -- do NOT re-run the same probes expecting a different answer without
a concrete reason to think something changed.

ONE THING HAS CHANGED (VERIFIED live just now, worth exactly one fresh attempt): FIRECRAWL_API_KEY is present in
this session's environment, but a live credit-usage check just now (https://api.firecrawl.dev/v1/team/credit-usage)
returned remaining_credits=0 -- so Firecrawl is STILL not usable, confirming the shard-6 finding holds. Do not
spend budget retrying Firecrawl unless you independently reverify credits are nonzero.

gold_standard_ultraloop_audit already has FRESH (within the last 24-40h) survived=true rows for B, C, D, and F
documenting this as a genuine, verified residual -- so the audit-freshness gate for those 4 letters is currently
satisfied and does not block certification by itself. What's missing (VERIFIED via a direct query just now): A,
E, G, H, I, J have ZERO audit rows in the last 7 days despite all six PASSING. That gap-closure is real,
achievable work this session, unlike re-litigating B/C/D/F for a 4th time.

Your job, in priority order: (1) log fresh gold_standard_ultraloop_audit rows for the 6 passing-but-unaudited
letters (A, E, G, H, I, J), each with a real adversarial sanity check (E=100.0/13 of 13 -- spot check a couple of
parcel_id values are real; I=100.0 -- confirm card fields are non-placeholder; J=100.0 -- confirm bid_decisions
rows have real arv/max_bid/ml_score, not zeros). (2) ONLY if you find a genuinely new, not-yet-tried avenue for
B/C/D/F after reading the two prior investigation scripts (e.g. a different records vendor covering the FL
panhandle, a state-level DOR sale-results archive, a downloadable tax-collector results PDF distinct from the
roll-lookup already checked) -- try it once, honestly, and report what you find either way. Do NOT spend more than
a small fraction of your budget re-confirming already-exhausted avenues; the honest, evidence-backed conclusion
"still blocked, here's why" is a valid and expected outcome for this county, not a failure.`,
  },
]

const RECIPE = `
Environment (already available, do not ask for credentials):
- REST API reads/writes: GET/PATCH \${SUPABASE_URL}/rest/v1/<table>?... with headers
  apikey: $SUPABASE_SERVICE_ROLE_KEY, Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY
  (pipeline.counties is in the "pipeline" schema, not exposed via the default REST root -- use the Management API
  SQL endpoint below to query it, or add Accept-Profile: pipeline / Content-Profile: pipeline headers if the REST
  root has PostgREST schema exposure configured for it; verify which works live rather than assuming.)
- Live arbitrary SQL (verified working this session): POST
  https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query
  headers Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json
  body {"query": "<sql>"} -- run "SET statement_timeout = 0;" first in the same query string for anything heavy.
  Build this JSON with a real JSON encoder (e.g. python3 -c "import json; ..." writing to a temp file, then curl
  --data-binary @file) rather than hand-quoting shell strings -- nested quotes in SQL break naive shell quoting.
  Direct psql/psycopg2 pooler connections FAIL (password auth failed against both
  aws-0-us-west-2.pooler.supabase.com and db.mocerqjnksmhcjzxrewo.supabase.co, reconfirmed this session) -- do not
  waste time on that path, use the Management API / REST above exclusively.
- pencil_dod_evaluate_county RPC: POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county
  headers apikey/Authorization as above, body {"p_county": "<slug>"} -- this is your before/after proof. The
  live function definition computes every letter from multi_county_auctions filtered to lower(county)=<slug> AND
  (data_source <> 'propertyonion' OR tier1_authoritative=true) -- PropertyOnion-sourced rows are excluded from the
  denominator entirely unless explicitly marked tier1_authoritative. C/D specifically require parity_source LIKE
  'tier1%%' in addition to parity_status -- setting parity_status alone does NOT satisfy C/D. B only passes in the
  95-105%% band, not just >=95%%. G = LEAST(density,far,pk1000) computed from v_zoning_gold_standard_kpi_v3, which
  joins parcel_zones -> zoning_districts -> zone_standards and is gated by v_zoning_district_applicability (a
  district/dimension pair that's genuinely not applicable does not count against the denominator -- do not treat
  a low "_applicable_parcels" count as a bug, it may be correct).
- gh CLI is authenticated (repo, workflow scopes) for git operations and workflow dispatch if needed.
- Repo root is the current working directory. Schema changes MUST go through a migration file under
  supabase/migrations/<date>_shard1_<county>_<purpose>.sql, committed to git -- even though you CAN run SQL
  directly via the Management API, still write the migration file for the historical record and apply it the
  same way. Simple data backfills (UPDATE/PATCH on existing columns, no schema change) do not need a migration
  file -- just do the REST PATCH or a direct UPDATE via the Management API and note the exact SQL/endpoint used.

ULTRALOOP audit logging (mandatory per campaign protocol): for every letter you claim moved (or claim you
verified as correctly-passing/correctly-blocked/residual), INSERT one row into public.gold_standard_ultraloop_audit:
  columns: dispatch_id (uuid '${DISPATCH_ID}'), ultraloop_mode ('fallback' -- this session used manual Task
  subagent fan-out via the Workflow tool, not native /effort ultracode), county_slug, letter, claim (short text of
  what you claim), refuter_evidence (jsonb -- for the FIX agent, put your own before/after evidence; for the VERIFY
  agent, put your refutation attempt and what you found), survived (boolean -- true only if the claim held up
  under adversarial check). Use the REST endpoint: POST \${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with
  the service-role headers above. Do this as part of your normal work, not as an afterthought.

Hard rules (from the campaign brief -- follow exactly):
- You own ONLY your assigned county. Never touch another shard-1 county's rows, or any other shard's counties.
- PropertyOnion is litmus/comparison ONLY -- never write po_* derived values in as if they were verified/independent.
- Fail-loud invariant: if a fix attempt finds zero real data, report it as a blocked/residual gap. NEVER fabricate
  case numbers, parcel IDs, sale amounts, coordinates, ordinance values, or timestamps to make a metric look
  better. This project has a documented history of exactly this failure mode (gulf B/F fabrication, purged) -- do
  not repeat it in any form, including "close enough" placeholder values or INFERRED citations standing in for
  real ones.
- Every claim you return must be tagged VERIFIED (you ran the query/request and are pasting real output), UNTESTED,
  or INFERRED (say why).
- Before finishing: call pencil_dod_evaluate_county for your county and paste the FULL before (already given
  above, or re-verify fresh if you suspect drift) and after JSON. If a letter did not move, say so plainly.
- git commit any file you create/modify with a clear message, county-scoped, and 'git pull --rebase origin main'
  before pushing (other shards may be pushing concurrently to shared paths -- you are isolated in a worktree so
  conflicts should be rare, but rebase defensively anyway). Push directly to main -- no branches, no PRs.
- Do NOT run public.gold_standard_loop() or gold_standard_certify() -- other shards may be mid-session. Do NOT
  modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job.
- Budget yourself: this is ONE bounded pass, not a 6-hour campaign in itself. If the true fix requires building a
  brand-new scraper from scratch, do NOT build it in this pass -- size the gap precisely, report it as a
  scoped-out residual with what a future session needs to do, and ship whatever smaller, real, verifiable
  improvement IS achievable via SQL/REST/live lookups alone (data backfill, wiring an existing-but-unrun pipeline,
  honesty corrections).

Return a structured report: { county, letters_touched: [...], fix_summary, sql_or_endpoints_used: [...],
before_json, after_json, residual_gaps: [...], honesty_notes: [...] }.
`

phase('Diagnose+Fix')
const fixResults = await pipeline(
  COUNTIES,
  (county) => agent(
    `You are working Gold Standard shard-1, county "${county.slug}", inside the cli-anything-biddeed repo (already checked out, on main).\n\n${county.context}\n\n${RECIPE}`,
    {
      label: `fix:${county.slug}`,
      phase: 'Diagnose+Fix',
      isolation: 'worktree',
      schema: {
        type: 'object',
        properties: {
          county: { type: 'string' },
          letters_touched: { type: 'array', items: { type: 'string' } },
          fix_summary: { type: 'string' },
          sql_or_endpoints_used: { type: 'array', items: { type: 'string' } },
          before_json: {},
          after_json: {},
          residual_gaps: { type: 'array', items: { type: 'string' } },
          honesty_notes: { type: 'array', items: { type: 'string' } },
        },
        required: ['county', 'fix_summary', 'before_json', 'after_json'],
      },
    }
  )
)

phase('Verify')
const verified = await pipeline(
  fixResults.filter(Boolean),
  (result, county) => agent(
    `Independently verify this claimed Gold Standard fix for county "${county.slug}". You did NOT write this fix -- be skeptical.\n\n` +
    `Claimed result: ${JSON.stringify(result)}\n\n` +
    `${RECIPE}\n\n` +
    `Your job: re-run pencil_dod_evaluate_county for "${county.slug}" yourself RIGHT NOW (fresh call, do not trust the pasted after_json), ` +
    `compare against the claimed before/after, and check specifically for: (a) denominator mismatches (does the ` +
    `"auctions_total" / "closed_sold" count match what you independently query?), (b) ghost-success (any letter now ` +
    `passing because of a placeholder/fabricated/vacuous value rather than a real fix -- this campaign has a ` +
    `documented history of exactly this failure mode, e.g. G passing 100%% on zero applicable parcels, or an ` +
    `INFERRED citation standing in for a real ordinance section), (c) whether any OTHER letter for this county ` +
    `regressed as a side effect, (d) for B specifically, the only valid pass band is 95-105%% -- an anomalous ratio ` +
    `outside that (even if the raw pass/fail bit says true) should be flagged. ` +
    `Also INSERT your own gold_standard_ultraloop_audit row per the RECIPE instructions (ultraloop_mode='fallback'). ` +
    `Return { county, refuted: boolean, refutation_reason: string|null, fresh_evaluation: <the JSON you just got>, survives: boolean }.`,
    {
      label: `verify:${county.slug}`,
      phase: 'Verify',
      schema: {
        type: 'object',
        properties: {
          county: { type: 'string' },
          refuted: { type: 'boolean' },
          refutation_reason: { type: ['string', 'null'] },
          fresh_evaluation: {},
          survives: { type: 'boolean' },
        },
        required: ['county', 'refuted', 'fresh_evaluation', 'survives'],
      },
    }
  )
)

return { fixResults, verified }
