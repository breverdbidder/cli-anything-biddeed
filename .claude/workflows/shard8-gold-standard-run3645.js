export const meta = {
  name: 'shard8-gold-standard-run3645',
  description: 'Gold Standard shard-8 (st_lucie/charlotte/lee/gulf): diagnose, fix, adversarially verify letters C/D/E/I per county',
  phases: [
    { title: 'Diagnose+Fix', detail: 'one agent per county, worktree-isolated' },
    { title: 'Verify', detail: 'independent refuter per county claim' },
  ],
}

const COUNTIES = [
  {
    slug: 'st_lucie',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county p_county=st_lucie, just run): 9/10, only I fails at 87.8%
(card_complete=72 of 82 active auctions). Root cause found by prior investigation this session: querying
v_auction_property_card for county=st_lucie with auction_status not in (redeemed,cancelled) shows ALL 68 rows
returned have zoning_code = NULL (0% zoning match), yet several other fields (address/geo/value) are also
patchy. The 87.8% in the evaluator vs 0% zoning-code-populated in this raw check suggests either (a) the real
I query has a different/looser zoning join than v_auction_property_card, or (b) v_auction_property_card is
stale/wrong. DO NOT GUESS. Find the actual SQL definition of the I criterion as used by pencil_dod_evaluate_county
(query pg_get_functiondef via the Management API: POST https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query
with body {"query": "select pg_get_functiondef('public.pencil_dod_evaluate_county'::regproc)"} , auth Bearer $SUPABASE_ACCESS_TOKEN)
before writing any fix. Also check whether St Lucie has ANY rows in parcel_zones / zoning_districts / zone_standards
(the G criterion PASSED at 100% density, which is suspicious — could be a vacuous pass from zero applicable parcels,
same pattern flagged for Brevard/Duval in project history — verify the G denominator is non-trivial before trusting it).`,
  },
  {
    slug: 'charlotte',
    context: `Baseline (VERIFIED live): 7/10. Failing: B (50.0%, verified=2 closed_sold=4), C (16.5%, matched_clean=17 of 103),
D (16.5%, matched_any=17 of 103). VERIFIED this session: SELECT parity_status, count(*) FROM multi_county_auctions
WHERE county='charlotte' GROUP BY parity_status -> {matched_clean: 17, null: 86}. 86 of 103 auctions have NEVER
been run through the parity/litmus matcher at all (parity_status IS NULL) — this looks like a WIRING gap (the
litmus job isn't covering these rows), not a true source-of-truth mismatch. Before building anything new, find
and run the existing parity/litmus pipeline for charlotte: check scripts/cd_litmus_v2_realauction_harvest.py,
scripts/cd_litmus_v2_realauction_parity.py, scripts/shard7_charlotte_fixes.py, scripts/shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py,
scripts/shard24_charlotte_freshness_fix.py for whether charlotte is already wired into a cron/workflow and why
86 rows were skipped (e.g. window_start/window_end date range too narrow, or the job never ran for charlotte).
Also reconcile B: verified_outcomes(2) vs closed_sold(4) — find the 2 closed/sold charlotte auctions lacking an
INDEPENDENT (non-promoted) verified outcome and see if a clerk source can close the gap. Per STANDING AUTHORIZATIONS,
you are pre-authorized to adopt clerk/official-records as supplementary litmus if you prove PropertyOnion coverage
(not our matcher) is the root cause for C/D — document evidence, do not re-ask.`,
  },
  {
    slug: 'lee',
    context: `Baseline (VERIFIED live): 6/10. Failing: C (91.6%, matched_clean=250 of 273), D (91.9%, matched_any=251 of 273),
E (90.8%, parcel_linked=248 of 273), I (71.4%, card_complete=195 of 273). VERIFIED this session: the unlinked rows
have case_number values like "PO-1070678", "PO-1018587" etc (PropertyOnion-style IDs used AS the case_number
instead of a real Lee County court case number) with parcel_id IS NULL, and several of these PO-case_numbers appear
TWICE in the table (duplicate rows) — e.g. PO-1070678, PO-1018587, PO-1184533, PO-1065802, PO-1070082, PO-1085872,
PO-1219450, PO-1032268, PO-1167967, PO-1033208 each appeared twice in a 25-row unlinked sample. This is the SAME
root-cause pattern already diagnosed for Duval in this project's history (PO id used as case_number blocks real
matching). Query the full unlinked set: SELECT id,case_number,parcel_id,property_address,auction_status FROM
multi_county_auctions WHERE county='lee' AND parcel_id IS NULL (use the Supabase REST endpoint, service role key
in env SUPABASE_SERVICE_ROLE_KEY, url env SUPABASE_URL). For each distinct PO-case, try to recover a real parcel_id
via property_address using the Lee County Property Appraiser ArcGIS FeatureServer (search for it — Lee County GIS
open data, same pattern as the BCPAO/Brevard reference implementation described in this repo's zonewise pipeline)
or via case_number lookup on the Lee Clerk's site if address match fails. If you cannot get a live, real parcel_id
for a row, do NOT fabricate one — leave it unlinked and report it as a residual gap. lee_zone_standards_fix.py and
lee_enrich_shard14.py already did G/other lee work this campaign — read them first to avoid duplicating effort or
regressing G (which currently PASSES at 100%).`,
  },
  {
    slug: 'gulf',
    context: `Baseline (VERIFIED live): 3/10. Only 5 auctions total, all foreclosure/upcoming or cancelled, all
last_seen_at = 2026-06-26 (stale — H FAILS at ~105h+ since SLA is 48h and it is now 2026-07-10, so this scraper
has not run in ~2 weeks). VERIFIED this session: 3 of the 5 rows have FABRICATED-LOOKING parcel_id placeholders:
"Property Appraiser" (literal field-label string, not a parcel number), "GULF-PA-000060CAAXMX-02", and
"GULF-PA-000072CAAXMX-01" (synthetic case-number-derived strings, not real Gulf County Property Appraiser folio
numbers — contrast with the two legitimate-looking rows: parcel_id "06248-410R" and "06051-008R" which match Gulf
County's real folio format). E currently shows PASS at 100% (5 of 5 parcel-linked) but this is a GHOST-SUCCESS:
3 of those "links" are placeholder junk, not real parcel joins. IMPORTANT CONTEXT: scripts/shard7_gulf_bf_outcomes.py
documents that a PRIOR version of gulf's B/F pipeline fabricated 5 invented case numbers/sale amounts labeled
"clerk proxy records" and that fabrication was found and PURGED from production on 2026-07-10 (today, earlier this
session cycle) — B and F are correctly FAIL/null right now because there are zero real closed/sold gulf auctions
and NO fabrication must be reintroduced. Your job: (1) audit and, if confirmed fake, null out the 3 placeholder
parcel_id values (this will honestly DROP E below 100% — that is correct, not a regression, per ULTRALOOP's
explicit purpose of catching exactly this pattern) UNLESS you can find each row's REAL Gulf County Property
Appraiser parcel/folio number via a live GIS/appraiser lookup (Gulf County FL GIS or property appraiser site) and
replace the placeholder with a real value — prefer this over nulling if you can verify it live. (2) Diagnose why
last_seen_at is frozen at 2026-06-26: check whether a gulf-specific scraper/workflow exists and is scheduled
(search .github/workflows/ for gulf, and pipeline.counties for gulf's platform config) and if broken, say so
precisely — do not re-scrape by fabricating fresher timestamps. (3) DO NOT touch B or F — they are correctly
failing per the fresh purge; do not attempt to backfill them without a genuinely new independent live source, and
if you find none, leave them alone and report UNTESTED/blocked rather than inventing anything.`,
  },
]

const RECIPE = `
Environment (already available, do not ask for credentials):
- REST API reads/writes: GET/PATCH \${SUPABASE_URL}/rest/v1/<table>?... with headers
  apikey: $SUPABASE_SERVICE_ROLE_KEY, Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY
- Live arbitrary SQL (verified working this session): POST
  https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query
  headers Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json
  body {"query": "<sql>"} -- run "SET statement_timeout = 0;" first in the same query string for anything heavy.
- pencil_dod_evaluate_county RPC: POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county
  headers apikey/Authorization as above, body {"p_county": "<slug>"} -- this is your before/after proof.
- gh CLI is authenticated (repo, workflow scopes) for git operations and workflow dispatch if needed.
- Repo root is the current working directory. Schema changes MUST go through a migration file under
  supabase/migrations/<date>_shard8_<county>_<purpose>.sql, committed to git — even though you CAN run SQL
  directly via the Management API, still write the migration file for the historical record and apply it the
  same way (either directly via the Management API call above, or by committing + gh workflow run "Run SQL Migration"
  --field file=<path> and polling gh run watch). Simple data backfills (UPDATE/PATCH on existing columns, no
  schema change) do not need a migration file — just do the REST PATCH or a direct UPDATE via the Management API
  and note the exact SQL/endpoint used in your report.

Hard rules (from the campaign brief — follow exactly):
- You own ONLY your assigned county. Never touch another county's rows.
- PropertyOnion is litmus/comparison ONLY — never write po_* derived values in as if they were verified/independent.
- Fail-loud invariant: if a fix attempt finds zero real data, report it as a blocked/residual gap. NEVER fabricate
  case numbers, parcel IDs, sale amounts, or timestamps to make a metric look better. This project had a real
  fabrication incident (gulf B/F, purged today) — do not repeat that pattern in any form, including "close enough"
  placeholder values.
- Every claim you return must be tagged VERIFIED (you ran the query/request and are pasting real output),
  UNTESTED, or INFERRED (say why).
- Before finishing: call pencil_dod_evaluate_county for your county and paste the FULL before (already given
  above) and after JSON. If a letter did not move, say so plainly — do not spin it.
- git commit any file you create/modify with a clear message, county-scoped, and 'git pull --rebase origin main'
  before pushing (other shards may be pushing concurrently to shared paths — you are isolated in a worktree so
  conflicts should be rare, but rebase defensively anyway). Push directly to main — no branches, no PRs.
- Do NOT run public.gold_standard_loop() or gold_standard_certify() — other shards may be mid-session.
- Budget yourself: this is ONE bounded pass, not a 6-hour campaign. If the true fix requires building a brand-new
  scraper (e.g. a tax-deed lane that doesn't exist, or a full clerk-records harvester), do NOT build it from
  scratch in this pass — instead size the gap precisely, report it as a scoped-out residual with what a future
  session needs to do, and ship whatever smaller, real, verifiable improvement IS achievable via SQL/REST alone
  (data backfill, wiring an existing-but-unrun pipeline, honesty corrections).

Return a structured report: { county, letters_touched: [...], fix_summary, sql_or_endpoints_used: [...],
before_json, after_json, residual_gaps: [...], honesty_notes: [...] }.
`

phase('Diagnose+Fix')
const fixResults = await pipeline(
  COUNTIES,
  (county) => agent(
    `You are working Gold Standard shard-8, county "${county.slug}", inside the cli-anything-biddeed repo (already checked out, on main).\n\n${county.context}\n\n${RECIPE}`,
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
    `Independently verify this claimed Gold Standard fix for county "${county.slug}". You did NOT write this fix — be skeptical.\n\n` +
    `Claimed result: ${JSON.stringify(result)}\n\n` +
    `${RECIPE}\n\n` +
    `Your job: re-run pencil_dod_evaluate_county for "${county.slug}" yourself RIGHT NOW (fresh call, do not trust the pasted after_json), ` +
    `compare against the claimed before/after, and check specifically for: (a) denominator mismatches (does the ` +
    `"total" auction count match what you independently query?), (b) ghost-success (any letter now passing because ` +
    `of a placeholder/fabricated value rather than a real fix — this campaign has a documented history of exactly ` +
    `this failure mode), (c) whether any OTHER letter for this county regressed as a side effect. Anomalous ratios ` +
    `(e.g. a percentage >100%) auto-fail. Return { county, refuted: boolean, refutation_reason: string|null, ` +
    `fresh_evaluation: <the JSON you just got>, survives: boolean }.`,
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
