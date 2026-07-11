export const meta = {
  name: 'gold-standard-shard11-run3679-b',
  description: 'Gold Standard shard-11 continuation (leon/st_johns/suwannee/lafayette): fix remaining failing letters, adversarially verify',
  phases: [
    { title: 'Diagnose+Fix', detail: 'one agent per county, worktree-isolated' },
    { title: 'Verify', detail: 'independent refuter per county claim' },
  ],
}

const DISPATCH_ID = '17725211-9941-4675-87d5-14eacc6a6bcb'

const COUNTIES = [
  {
    slug: 'leon',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now): 10/10 -- ALL LETTERS PASS
(A=48, B=100, C=100, D=100, E=99.4, F=100, G=98.7, H=1.4h, I=98.8, J=100). This matches the prior run3679
closeout commit (c712aaf4) which took leon from 7/10 to 10/10 via real Tallahassee-Leon GIS zoning backfill,
Census geocode/PA enrichment, and an "Unincorporated Leon County" jurisdiction migration.

YOUR ONLY JOB for leon this session: CONFIRM, do not fix, do not modify anything.
1. Re-run pencil_dod_evaluate_county('leon') fresh and paste the JSON.
2. Confirm all 10 letters still PASS with no regression vs the numbers above.
3. If everything still passes, report letters_touched: [] and fix_summary explaining this is a
   verification-only pass because leon is already gold. Do NOT run gold_standard_certify or gold_standard_loop
   (other shards may be mid-session) -- certification is automatic after the second consecutive 10/10 daily run.
4. If you find ANY regression, report it precisely (which letter, old vs new metric) as a residual_gap --
   do not attempt a fix in this pass unless it is a one-line honest correction; prioritize accurate reporting.`,
  },
  {
    slug: 'st_johns',
    context: `Baseline (VERIFIED live just now): 7/10. Failing: E (metric=86.5, parcel_linked=32 of 37), G (metric=93.8,
density=93.8 far=100.0 pk1000=), I (metric=86.5, card_complete=32 of 37). Passing: A=3, B=100, C=100, D=100,
F=100, H=1.1h, J=100 (bid_decisions already has 37 rows for st_johns -- do NOT touch J, it's correct).

VERIFIED this session -- the exact 5 unlinked rows (all auction_status='upcoming', data_source='calendar_sweep_mca_v3',
parcel_id AND property_address both NULL):
  CA25-0475, CA25-1757, CA25-0128, CA25-0351, CC25-4817
These are St Johns County circuit-court case numbers with no property data attached yet (likely court-calendar
sweep found the case but never resolved a property record). Per the DEPENDENCY CHAIN in the campaign brief,
I <= E by construction (card requires parcel_id), so linking these 5 parcels is the highest-leverage single fix --
it can move E 86.5->100, and I follows for free IF the linked parcels also land in v_zoning_gold_standard_card
with zone_code (check this after linking, don't assume).

To link: find the real property/parcel for each case_number. St Johns Clerk case search
(https://www.stjohnsclerk.com, or their eCourt/case-search portal) usually shows defendant name + a legal
description or address on the docket for a foreclosure/civil case -- that address can then be matched against
the St Johns County Property Appraiser (sjcpa.gov) parcel search or ArcGIS FeatureServer (search
"stjohnscountyfl.gov arcgis rest services" or "sjcpa.gov GIS") to get parcel_id + address + lat/lon. Do this
per-case; if a case genuinely has no resolvable property (e.g. dismissed with no attached parcel), report it as
a residual with evidence rather than fabricating.

VERIFIED this session -- the G gap (93.8% = 30 of 32 currently-linked parcels have max_density_du_acre): of the
32 St Johns parcels in v_zoning_gold_standard_card, zone_code='R-1' (30 rows) has max_density_du_acre=4.00
already populated; zone_code='RS-3' (1 row) and zone_code='SAB' (1 row) have max_density_du_acre=NULL. Find the
REAL max_density_du_acre (and ideally max_far/parking_per_1000sf if missing) for St Johns County's RS-3 and SAB
zoning districts from the actual St Johns County Land Development Code (municode.com/fl/st_johns_county or the
county's own zoning ordinance PDF) -- do NOT guess or copy a neighboring county's number. If genuinely only 2
districts are affected this is a small, bounded, high-confidence fix. If the newly-linked 5 parcels above land in
NEW zone codes beyond R-1/RS-3/SAB, you'll need their standards too -- check after linking.

Do not fabricate coordinates, parcel IDs, or zoning standards under any circumstances -- this campaign has a
documented history of exactly that failure mode (suwannee/lafayette G fabrication, already purged in a prior
session). If a real source cannot be found for a specific case or district, report it as residual with the
evidence of what you tried.`,
  },
  {
    slug: 'suwannee',
    context: `Baseline (VERIFIED live just now): 7/10 (I already fixed to 100% in the prior run3679 session --
do NOT touch I, it's correct real per-parcel data from the Suwannee PA GSA-corp system). Failing: A (metric=0,
fc=0 td=9), B (metric=null, verified=0 closed_sold=0), F (metric=null, tier1_sold=0 closed_sold=0). Passing:
C=100, D=100, E=100, G=100, H=2.7h, J=100 (do not touch these).

PRIOR-SESSION FINDING (from run3679 closeout, VERIFY FRESH rather than trust): A is blocked because suwannee
genuinely has 0 live foreclosure listings on suwannee.realforeclose.com -- a real structural gap (small rural
county), not a scraper bug. Re-check this live before accepting it as still true (dates move forward daily).

NEW FINDING THIS SESSION (VERIFIED via live SQL, worth investigating before accepting the whole shard as
blocked): all 9 suwannee tax-deed auctions are still auction_status='upcoming', but two of them --
case_number 4666 and 4667 -- have auction_date=2026-07-09, which is IN THE PAST relative to today (2026-07-11).
A tax-deed sale that already happened but is still marked "upcoming" is a stale-status bug, and if these 2 sold,
that would give closed_sold>0 for the FIRST TIME, which is the only way B and F can ever move off their current
null/FAIL state (both formulas divide by closed_sold, currently 0 for the whole county).
suwannee.realtaxdeed.com returned HTTP 403 to a plain curl from this session (likely needs a proper
User-Agent/session, or an authenticated free-registered session per the campaign's playbook-A guidance on
RealAuction's anonymous-preview cap) -- do not conclude "blocked" from a bare 403, retry with a realistic
browser User-Agent header and/or check the FNC=UPDATE diff endpoint pattern used elsewhere in this repo for
RealAuction sites (search scripts/ for "realtaxdeed" + "User-Agent" for a working example to copy). If you can
confirm case 4666/4667 actually sold and get a real, clerk/RealAuction-sourced sale amount, write an INDEPENDENT
outcome row (tax_deed_outcomes, data_source starting with something other than 'promote'/'propertyonion') and
update auction_status to closed/sold -- then closed_sold becomes >=1 and B/F can be computed for the first time.
If the sites genuinely show these as not-yet-resulted (auction rescheduled, or result not yet posted), report
that precisely with the evidence and leave status untouched -- do not force a status change without a real
result.

Do not re-attempt the A foreclosure-lane investigation beyond one fresh live check -- it was already thoroughly
verified blocked in the prior session. Focus your budget on the 4666/4667 tax-deed status question, it is the
only genuinely new lever for this county.`,
  },
  {
    slug: 'lafayette',
    context: `Baseline (VERIFIED live just now): 3/10. Passing: E=100 (parcel linked), H=9h, I=100 (real data,
verified in prior run3679 session -- do NOT touch, and note G's prior 100% was un-fabricated to 0% in that same
session, which was the CORRECT honesty move, not damage). Failing: A (fc=1 td=0), B (null, closed_sold=0),
C (0.0, matched_clean=0 of 1), D (0.0, matched_any=0 of 1), F (null, closed_sold=0), G (0.0, density=0.0 far=0.0
pk1000=0.0), J (0.0, deal_complete=0 of 1). Only 1 total auction row for this county (Florida's least populous):
case_number 25000056CAAXMX, auction_status='upcoming', auction_date=2026-09-03 (future), parcel_id
1305110011064000030, address "185 SW Alachua Ave Mayo, FL 32066", lat/lon already populated, assessed_value=
market_value=70973, judgment_amount=104964.67, parity_status/parity_source both NULL, data_source=
'lafayette_clerk_scrape' (from scripts/lafayette_clerk_harvest.py, which is real and already correctly reports
the tax-deed page as genuinely empty -- "no properties on the list of tax deeds at this time", NOT a scrape bug,
this is td=0 explained; do not re-scrape or doubt this).

REAL AND ACHIEVABLE THIS SESSION, in priority order:

1. G (zoning, 0.0 -> real value): the single parcel is in Mayo, FL / Lafayette County. Read
   scripts/shard1_lafayette_bootstrap.py and scripts/shard12_run1113_lafayette_bf.py first (check if either
   already touched zoning for this parcel -- v_zoning_gold_standard_card currently has exactly 1 row for
   lafayette but its density/far/parking are presumably null/zero, confirm with a live SELECT before doing
   anything). Find the parcel's REAL zoning district from the actual Lafayette County zoning ordinance (Lafayette
   County FL is unincorporated-only with no municipalities of size -- check municode.com/fl/lafayette_county for
   the zoning code chapter) or from the Lafayette County Property Appraiser if it publishes a zoning field. Only
   write REAL max_density_du_acre / max_far / parking_per_1000sf values with a standards_source_url citation --
   if the ordinance genuinely doesn't specify a density/FAR/parking number for this district (common for large-lot
   rural agricultural zones), that may mean the parcel should be flagged N/A via v_zoning_district_applicability
   rather than counted against the denominator (check how the evaluator/view handles genuinely-N/A districts,
   per the G DIAGNOSIS note in the campaign brief) -- do NOT invent a number to force a pass.

2. C/D (parity, 0.0 -> real match): parity_status/parity_source are both NULL for the only row. There are ZERO
   PropertyOnion rows for lafayette (VERIFIED live, count=0) so the usual PO-litmus comparison has nothing to
   compare against. Check the exact evaluator definition of matched_clean/matched_any (parity_source LIKE
   'tier1%%') and find or build the smallest real comparison: since our own data_source
   'lafayette_clerk_scrape' IS the clerk's own published listing (a real, authoritative source, confirmed live
   reachable in scripts/lafayette_clerk_harvest.py's docstring), check whether re-running that harvest script
   right now still finds this exact case on the live page -- if it does, that is a genuine independent
   confirmation (the scrape re-observing the source matches our stored row) and can justify a
   parity_source='tier1:lafayette_clerk_scrape' + parity_status='matched_clean' write. If the live harvest no
   longer shows this case (e.g. it was pulled/settled), report that precisely instead of forcing a match.

3. J (deal generator, 0.0 -> real bid_decisions row): bid_decisions currently has 0 rows for lafayette
   (VERIFIED). Read scripts/shard5_leon_j_generator.py (or scripts/shard11_j_generator.py, gold_standard_shard5_sumter_j_generator.py)
   as the reference pattern for the evaluator contract: arv, max_bid = Shapira formula
   (ARV*70% - repairs - $10K - MIN($25K, 15%*ARV)), ml_score (Shapira V14, use the same 0.65 non-Brevard
   baseline the leon script uses unless a real model score is available), and factors jsonb with ALL 5 keys
   (distress_location, distress_property, distress_owner, cma_distressed, cma_resale). You have real inputs for
   this single case: assessed_value/market_value=70973 (use as the ARV baseline, same as the leon script's
   'assessed_value_factor' arv_source pattern), judgment_amount=104964.67. Adapt one of the reference scripts
   (do not build from scratch) for lafayette specifically and INSERT one real row. This is fully county-agnostic
   per the campaign brief's J diagnosis -- just needs to be run for this county's single case.

4. A/B/F: genuinely structurally blocked this session (td=0 is a real empty clerk listing; the row is
   auction_status='upcoming' with a Sept 2026 sale date, so closed_sold will be 0 until then no matter what you
   do). Do NOT attempt to force these -- report as residual with the evidence above (already gathered) rather
   than spending budget on them.

Do not fabricate zoning standards, parity matches, or deal-decision inputs under any circumstances -- this exact
county had a documented fabrication-and-purge cycle in the prior run3679 session (synthetic SYN-LAF-* zoning
rows removed). Every write in this pass must be backed by a real, cited source.`,
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
  IMPORTANT: build this JSON with a real JSON encoder (e.g. python3 -c "import json; ..." writing to a temp file,
  then curl --data-binary @file) rather than hand-quoting shell strings.
  Note the multi_county_auctions county column is compared case-insensitively but v_zoning_gold_standard_card
  stores county as lowercase WITH A SPACE ("st johns" not "st_johns") -- verify the exact stored value with a
  DISTINCT query before filtering, do not assume underscore-vs-space.
- pencil_dod_evaluate_county RPC: POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county
  headers apikey/Authorization as above, body {"p_county": "<slug>"} -- this is your before/after proof. C/D
  specifically require parity_source LIKE 'tier1%%' in addition to parity_status -- setting parity_status alone
  does NOT satisfy C/D. PropertyOnion-sourced rows are excluded from denominators entirely unless
  tier1_authoritative=true.
- gh CLI is authenticated (repo, workflow scopes) for git operations.
- Repo root is the current working directory, on main, already checked out. Schema changes MUST go through a
  migration file under supabase/migrations/<date>_shard11_<county>_<purpose>.sql, committed to git -- even
  though you CAN run SQL directly via the Management API, still write the migration file for the historical
  record and apply it the same way. Simple data backfills (UPDATE/PATCH on existing columns, no schema change)
  do not need a migration file -- just do the REST PATCH or a direct UPDATE via the Management API and note the
  exact SQL/endpoint used.

ULTRALOOP audit logging (mandatory per campaign protocol): for every letter you claim moved (or claim you
verified as correctly-blocked/residual), INSERT one row into public.gold_standard_ultraloop_audit:
  columns: dispatch_id (uuid '${DISPATCH_ID}'), ultraloop_mode ('fallback' -- this session used Workflow-tool
  agent fan-out, not native /effort ultracode), county_slug, letter, claim (short text of what you claim),
  refuter_evidence (jsonb -- for the FIX agent, put your own before/after evidence; for the VERIFY agent, put
  your refutation attempt and what you found), survived (boolean -- true only if the claim held up under
  adversarial check). Use the REST endpoint: POST \${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with the
  service-role headers above. Do this as part of your normal work, not as an afterthought.

Hard rules (from the campaign brief -- follow exactly):
- You own ONLY your assigned county. Never touch another shard's counties, their rows, or their county-specific
  files. Do not touch leon/st_johns/suwannee/lafayette files from a different county's agent.
- PropertyOnion is litmus/comparison ONLY -- never write po_* derived values in as if they were
  verified/independent.
- Fail-loud invariant: if a fix attempt finds zero real data, report it as a blocked/residual gap. NEVER
  fabricate case numbers, parcel IDs, sale amounts, coordinates, zoning standards, or timestamps to make a
  metric look better. This project has a documented history of exactly this failure mode in THIS shard
  (suwannee and lafayette G fabrication, both purged in the prior run3679 session) -- do not repeat it in any
  form, including "close enough" placeholder values.
- Every claim you return must be tagged VERIFIED (you ran the query/request and are pasting real output),
  UNTESTED, or INFERRED (say why).
- Before finishing: call pencil_dod_evaluate_county for your county and paste the FULL before (already given
  above, or re-verify fresh if you suspect drift) and after JSON. If a letter did not move, say so plainly.
- git commit any file you create/modify with a clear message, county-scoped, and 'git pull --rebase origin main'
  before pushing (other shards may be pushing concurrently to shared paths -- you are isolated in a worktree so
  conflicts should be rare, but rebase defensively anyway). Push directly to main -- no branches, no PRs.
- Do NOT run public.gold_standard_loop() or gold_standard_certify() -- other shards may be mid-session. Do NOT
  modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job.
- Budget yourself: this is ONE bounded pass, not a 6-hour campaign. If a true fix requires building a brand-new
  scraper from scratch, do NOT build it in this pass -- size the gap precisely, report it as a scoped-out
  residual with what a future session needs to do, and ship whatever smaller, real, verifiable improvement IS
  achievable via SQL/REST/live lookups alone (data backfill, wiring an existing-but-unrun pipeline, honesty
  corrections).

Return a structured report: { county, letters_touched: [...], fix_summary, sql_or_endpoints_used: [...],
before_json, after_json, residual_gaps: [...], honesty_notes: [...] }.
`

phase('Diagnose+Fix')
const fixResults = await pipeline(
  COUNTIES,
  (county) => agent(
    `You are working Gold Standard shard-11, county "${county.slug}", inside the cli-anything-biddeed repo (already checked out, on main).\n\n${county.context}\n\n${RECIPE}`,
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
    `documented history of exactly this failure mode IN THIS SHARD, e.g. suwannee/lafayette G fabrication ` +
    `already purged once -- watch closely for a repeat), (c) whether any OTHER letter for this county regressed ` +
    `as a side effect, (d) for B specifically, the only valid pass band is 95-105%% -- an anomalous ratio outside ` +
    `that (even if the raw pass/fail bit says true) should be flagged. ` +
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
