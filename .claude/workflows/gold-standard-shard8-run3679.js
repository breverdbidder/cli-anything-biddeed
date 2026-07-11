export const meta = {
  name: 'gold-standard-shard8-run3679',
  description: 'Gold Standard shard-8 (walton/okeechobee/baker/okaloosa): diagnose, fix, adversarially verify failing letters per county',
  phases: [
    { title: 'Diagnose+Fix', detail: 'one agent per county, worktree-isolated' },
    { title: 'Verify', detail: 'independent refuter per county claim' },
  ],
}

const DISPATCH_ID = 'ac288257-fde4-4e26-a8d7-abb78447619f'

const COUNTIES = [
  {
    slug: 'walton',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now, supersedes the brief): ALREADY 10/10 --
A=6, B=100.0(4/4), C=100.0(37/37), D=100.0(37/37), E=97.3(36/37), F=100.0(4/4), G=100.0, H=9.8h, I=97.3(36/37),
J=100.0(37/37). The brief's numbers match this live read (this county was already fixed by a prior session, see
supabase/migrations/20260710164500_walton_i_real_gis_zoning_and_geo_backfill.sql and
supabase/migrations/20260705_shard9_walton_upcoming_sold_amount_ghost_success_fix.sql -- read both before touching
ANYTHING, the second is a ghost-success REVERT, i.e. a prior session fabricated data here and it was purged).

CRITICAL CONTEXT -- walton has a documented ghost-success history (20260704_shard5_walton_175k_ghost_success_revert.sql
also exists). This county is fragile: do NOT attempt any "improvement" that isn't backed by a real, independently
verifiable source. Your job this session is NARROW: (1) re-confirm all 10 letters PASS with a fresh call (paste
the JSON), (2) if genuinely all 10 pass, do NOT invent work -- log one gold_standard_ultraloop_audit row per letter
(10 rows total) with claim="already passing, reconfirmed live" and survived=true, citing the fresh evaluation as
refuter_evidence, so the SQL CERTIFY GATE (needs survived=true rows for all 10 letters within 7 days) has fresh
evidence and this county isn't blocked from certification on a technicality, (3) only if you find a REAL discrepancy
between what's live and what's claimed, report it plainly and do not paper over it. Do not touch multi_county_auctions
rows for walton beyond what's needed to log audit evidence. This is a verification-and-audit-logging pass, not a
fix pass -- there is nothing to fix here today.`,
  },
  {
    slug: 'okeechobee',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now -- differs from the brief, which is stale):
8/10. PASS: A=10, B=100.0(6/6), C=100.0(54/54), D=100.0(54/54), E=96.3(52/54, brief said FAIL 94.4/51-of-54 -- this
already moved past threshold, do NOT re-touch E), F=100.0(6/6), H=1.2h, J=100.0(54/54). FAIL: G (density=57.7
far=0.0 pk1000=null -- metric=0), I (card_complete=50 of 54, metric=92.6 -- brief said 50.0%/27-of-54, this also
already improved substantially, only 4 rows short of the 95% bar now).

VERIFIED this session -- the exact 3 (of what should be ~4) incomplete rows found via a targeted NULL-field query on
multi_county_auctions WHERE county='okeechobee': (a) case '2026TD050', tax sale_type, parcel_id
'1-25-37-35-0070-00060-1760' present, lat/lon present (27.3815/-80.8984), assessed_value 220865, but
property_address IS NULL -- purely an address-lookup gap, parcel_id already known; (b) case
'472025CA000130CAAXMX', foreclosure, parcel_id NULL, property_address NULL, but lat/lon/assessed_value already
present (27.3815/-80.8984, 261474.38) -- needs parcel_id + address only; (c) case '472025CA000205CAAXMX',
foreclosure, EVERYTHING null (parcel_id, address, lat/lon, assessed_value) -- needs full enrichment. My query only
found 3 rows failing on parcel_id/address/lat/value, but card_complete=50-of-54 implies a 4th gap row exists --
before doing enrichment work, re-run the NULL-field query yourself AND check the exact definition of
v_zoning_gold_standard_card (pg_get_viewdef) -- card_complete may ALSO require a zone_code match via parcel_zones,
which would mean the 4th row (or even these 3 after enrichment) still won't flip I if okeechobee's zoning substrate
doesn't cover their location. Confirm this before claiming a fix will move I.

G ROOT CAUSE (VERIFIED this session): zone_standards for the single 'Okeechobee' jurisdiction has 37 districts,
36-37 have NULL max_density_du_acre/max_far/parking_per_1000sf (only 1 district has any standard set) -- this is a
LARGE lift (37 districts needing real ordinance-sourced values), unlike baker's smaller 14-district gap. Per the
campaign's RECIPE budget rule, do NOT attempt to backfill all 37 districts from scratch in one pass -- if you can
find okeechobee's zoning ordinance (Okeechobee County Land Development Code, municode or county site) covering the
zone codes actually USED by the county's own parcels (check which zone_code values appear on real okeechobee parcels
first, then only backfill THOSE specific districts -- likely far fewer than 37 have any real parcels attached),
that's the tractable subset; otherwise size the gap precisely and report as residual. Prioritize I (only 3-4 rows,
much higher leverage per unit of work) before attempting any G work.

Existing scripts to check first (avoid duplicating): scripts/shard9_okeechobee_taxsmartweb_litmus.py,
scripts/shard9_run3534_okeechobee_cd_tier1.py, scripts/shard_gs_clay_okeechobee_cd_parity.py -- these targeted C/D/B
(already passing), none appear to target I's address/parcel enrichment specifically, confirm by reading before
assuming coverage. Okeechobee's tax deed platform in pipeline.counties is NULL (taxdeed_platform/taxdeed_url both
null, only foreclosure_platform='realforeclose' is set) -- worth a quick sanity check whether that's expected
(A already passes with fc=44 td=10 so tax deed data clearly exists from some source) or a stale config row, but
do not spend the session on this unless it's blocking one of your target letters.`,
  },
  {
    slug: 'baker',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now -- differs from brief, which is stale/worse
than current reality): 6/10. PASS: A=7, B=100.0(1/1), F=100.0(1/1), H=1.4h, J=100.0(15/15). FAIL: C=20.0(3/15),
D=20.0(3/15), E=20.0(3/15), G (density=0.0 far=50.0 pk1000=0.0, metric=0 -- this is a REGRESSION from the brief's
claimed G=PASS/100%, investigate why before assuming it's simply unstarted work), I=20.0(3/15).

VERIFIED this session -- full 15-row dump for county='baker': 7 distinct case numbers, 2 sale_types each (fc+td)
except one case is tax_deed-only:
  - '022025CA000038CAAXMX' (fc+td, 2 rows): COMPLETE -- parcel_id '043S22000000000540', address '1203 PINE CIR,
    MACCLENNY, FL- 32063', lat/lon present, assessed_value 208956, parity_status='matched_clean',
    parity_source='tier1_baker_realforeclose_bakerpa_v1'. Do not touch.
  - '022026XX000002TDAXMX' (td only, 1 row, auction_status='sold'): COMPLETE -- parcel_id '35-2S-20-0000-0000-0035',
    address 'COUNTY ROAD 229, SANDERSON, FL- 32087', lat/lon present, assessed_value 85000,
    parity_status='matched_clean', parity_source='tier1_tax_deed_outcome'. This is the B=1/F=1 verified-sold row.
    Do not touch.
  - SIX cases, 2 rows each (12 rows), ALL completely NULL (parcel_id, property_address, latitude, longitude,
    assessed_value, parity_status, parity_source), data_source='calendar_sweep_mca_v3' for all: '022025CA000108CAAXMX',
    '022025CA000117CAAXMX', '022025CA000124CAAXMX', '022025CA000148CAAXMX', '022026CA000007CAAXMX',
    '022026CA000018CAAXMX'. These 12 rows ARE the C/D/E/I gap (3-of-15 matched = the 2 complete cases' 3 rows above).
  These 6 case numbers came from the real Baker Clerk RealAuction calendar (baker.realforeclose.com/...CALENDAR --
  pipeline.counties confirms foreclosure_platform='realforeclose', taxdeed_platform='realtaxdeed', both live) --
  they are genuine scraped case numbers, not fabricated, so this is real enrichment work, not sourcing-from-zero.

REAL, ACHIEVABLE WORK -- prioritize in this order (this is the highest-leverage county in the shard, small and
tractable):
1. E/parcel-linkage for the 6 unlinked cases: find each case's parcel via the Baker County Property Appraiser
   (bakerpa.com or similar -- note parity_source 'tier1_baker_realforeclose_bakerpa_v1' on the working rows implies
   a bakerpa.com-based matcher already exists somewhere in scripts/ or supabase functions; search for
   'bakerpa' across scripts/ and supabase/migrations/ before building anything new) or via the Baker Clerk's own
   case detail page (which typically lists the property address/parcel for a foreclosure/tax-deed case). Backfill
   parcel_id + property_address + lat/lon + assessed_value for these 6 cases (12 rows) with REAL sourced data only.
2. C/D parity: once parcel_id is real and matches the tier1 baker_realforeclose source pattern, set
   parity_status='matched_clean' and parity_source starting with 'tier1' (required by the evaluator's C/D
   definition -- parity_status alone is not sufficient) using the SAME matcher logic as the 2 already-working cases,
   for genuine, verifiable matches only.
3. I/card-complete follows automatically once E's enrichment lands (card requires parcel_id+address+geo+value, same
   fields).
4. G REGRESSION -- baker's zoning substrate (14 districts under jurisdiction 'Macclenny', 9 with NULL
   max_density_du_acre, 9 with NULL max_far, 6 with NULL parking_per_1000sf -- VERIFIED live this session) is a
   MUCH smaller lift than okeechobee's 37-district gap and may be tractable within budget if real ordinance values
   can be sourced (Baker County / Macclenny zoning code, municode). Also check WHY this regressed from the brief's
   claimed PASS -- did a recent cross-county zoning migration change the applicability view or denominator for
   baker specifically? A quick git log/grep on recent zoning migrations mentioning 'baker' or 'macclenny' may
   explain it before you spend time re-backfilling values that might already exist under a different key. Attempt
   this only after 1-3 are done and if session budget remains.
Existing script to check first: scripts/shard3_baker_full_fix.py -- read it before duplicating any of this work.`,
  },
  {
    slug: 'okaloosa',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now, matches brief): 4/10, tiny county --
only 2 auctions total. PASS: A=1(fc=1,td=1), G=100.0(vacuous -- treat as unreliable per campaign norms, not a real
signal, but not in your fail list so no action needed), H=8.9h, J=100.0(2/2). FAIL: B(null,0/0), C=0.0(0/2),
D=0.0(0/2), E=0.0(0/2), F(null,0/0), I(null,0/0).

CRITICAL -- READ BEFORE TOUCHING ANYTHING: okaloosa has the heaviest ghost-success history in this campaign.
supabase/migrations/20260705_shard4_okaloosa_ghost_success_purge.sql documents a PRIOR session fabricating rows
with parcel_id='SYN-OKA-FC-001'/'SYN-OKA-TD-001' and property_address containing the literal string
'INFERRED SYN-OKA-...', plus fake bid_decisions with factors.cma_resale = the literal string
'bootstrap INFERRED from assessed_value'. That session's own pipeline.scrape_runs showed 281 failed / 0 succeeded
attempts -- proof the fabricated rows could not have come from a real scrape. It was purged, 6/10 (ghost) -> 1/10
(honest). DO NOT REPEAT THIS. Any new row you write for okaloosa must trace to a real, live, fetchable source you
can cite by URL, with a timestamp, or you must not write it.

The 2 real rows today: case '2024-CA-000470' (foreclosure) and '2024-TDD-000089' (tax_deed), both auction_date
2026-08-19, both auction_status='upcoming', both source_url='https://okaloosa.realforeclose.com', both with
NULL parcel_id/property_address/judgment_amount/sold_amount/data_source. Note data_source is literally NULL for
both -- unusual, worth understanding (possibly seeded from a calendar listing before the platform migration was
discovered dead).

VERIFIED PLATFORM STATE (from supabase/migrations/20260710_shard9_run3497_hardee_clerk_realdata_okaloosa_bid4assets_altsource.sql,
a prior session's live-fetched research, read it in full): okaloosa.realforeclose.com / okaloosa.realtaxdeed.com are
DEAD (302-redirect to realauction.com marketing splash, re-confirmed twice, most recently
2026-07-10 per supabase/migrations/20260710_shard10_citrus_e_i_fixes_and_okaloosa_notes.sql). The REAL live platform
is Bid4Assets: https://www.bid4assets.com/OkaloosaFL/listings (foreclosure) and
https://www.bid4assets.com/OkaloosaFLTax/listings (tax deed) -- both confirmed HTTP 200 with real 2026 sale dates
via plain fetch, but per-case row data loads via a backend AJAX call NOT present in the static HTML, so no prior
plain-fetch session could extract case-level data. pipeline.counties.county_slug='okaloosa' STILL shows
foreclosure_platform='realforeclose'/taxdeed_platform='realtaxdeed' pointing at the dead URLs -- this is stale and
should be corrected to Bid4Assets once you've verified it yourself.

THE REAL LEVER THIS SESSION: you have Firecrawl/browser-automation skills available (firecrawl-browser,
firecrawl-scrape, browser-use) that prior non-Firecrawl sessions did not have. Use one of them to actually load
https://www.bid4assets.com/OkaloosaFL/listings and https://www.bid4assets.com/OkaloosaFLTax/listings with real JS
execution (the AJAX grid needs it) and extract the live auction grid (case/auction IDs, court case numbers,
addresses, debt/opening amounts, sale dates). Then: (a) cross-check whether our 2 existing seed cases
('2024-CA-000470', '2024-TDD-000089') appear anywhere in that live grid -- if genuinely absent (a prior session
already checked once and found them absent from the 'today' single-row view; you now have the FULL grid, check
again properly), decide honestly whether they're stale/cancelled placeholders or still real-but-unlisted-yet,
(b) if the live grid surfaces genuine parcel/address/amount data for either of our 2 cases, backfill it with a
cited source URL + fetch timestamp -- this is your path to B/C/D/E/F/I movement, entirely from 2 rows so full 100%
is achievable if both cases resolve. Do NOT insert any NEW case numbers beyond what the live Bid4Assets grid
actually shows matching our 2 existing cases -- expanding okaloosa's denominator with unrelated real Bid4Assets
auctions is out of scope (other counties' A/H already pass; do not inflate okaloosa's auction set without a
clear reason tied to these 2 target letters). If the AJAX grid still can't be reached even with a browser tool
(e.g. Cloudflare/anti-bot), say so plainly, update pipeline.counties.notes with what you tried and found (do not
silently repeat the prior session's dead-end), and report this as a residual gap -- a documented, well-scoped
blocker is a valid and honest outcome for this county given its history.`,
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
  then curl --data-binary @file) rather than hand-quoting shell strings -- nested single/double quotes in SQL break
  naive shell quoting and can silently produce an empty/wrong query. Direct psql to the pooler FAILED this session
  (password auth error) -- use the Management API path above, not psql, unless you first confirm psql works for you.
- pencil_dod_evaluate_county RPC: POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county
  headers apikey/Authorization as above, body {"p_county": "<slug>"} -- this is your before/after proof. The
  live function definition (per prior sessions' pg_get_functiondef reads) computes every letter from
  multi_county_auctions filtered to lower(county)=<slug> AND (data_source <> 'propertyonion' OR
  tier1_authoritative=true) -- i.e. PropertyOnion-sourced rows are excluded from the denominator entirely unless
  explicitly marked tier1_authoritative. C/D specifically require parity_source LIKE 'tier1%%' in addition to
  parity_status -- setting parity_status alone does NOT satisfy C/D.
- gh CLI is authenticated (repo, workflow scopes) for git operations and workflow dispatch if needed.
- Repo root is the current working directory. Schema changes MUST go through a migration file under
  supabase/migrations/<date>_shard8_<county>_<purpose>.sql, committed to git -- even though you CAN run SQL
  directly via the Management API, still write the migration file for the historical record and apply it the
  same way. Simple data backfills (UPDATE/PATCH on existing columns, no schema change) do not need a migration
  file -- just do the REST PATCH or a direct UPDATE via the Management API and note the exact SQL/endpoint used.

ULTRALOOP audit logging (mandatory per campaign protocol): for every letter you claim moved (or claim you
verified as correctly-blocked/residual, or reconfirmed already-passing), INSERT one row into
public.gold_standard_ultraloop_audit: columns dispatch_id (uuid '${DISPATCH_ID}'), ultraloop_mode ('fallback' --
this session used manual Task subagent fan-out, not native /effort ultracode), county_slug, letter, claim (short
text of what you claim), refuter_evidence (jsonb -- for the FIX agent, put your own before/after evidence; for the
VERIFY agent, put your refutation attempt and what you found), survived (boolean -- true only if the claim held up
under adversarial check). Use the REST endpoint: POST \${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with
the service-role headers above. Do this as part of your normal work, not as an afterthought.

Hard rules (from the campaign brief -- follow exactly):
- You own ONLY your assigned county. Never touch another shard-8 county's rows, or any other shard's counties.
- PropertyOnion is litmus/comparison ONLY -- never write po_* derived values in as if they were verified/independent.
- Fail-loud invariant: if a fix attempt finds zero real data, report it as a blocked/residual gap. NEVER fabricate
  case numbers, parcel IDs, sale amounts, coordinates, or timestamps to make a metric look better. THREE of your
  FOUR counties (walton, baker, okaloosa) have a documented history of exactly this failure mode in this campaign
  (ghost-success fabrication, purged) -- do not repeat it in any form, including "close enough" placeholder values.
- Every claim you return must be tagged VERIFIED (you ran the query/request and are pasting real output), UNTESTED,
  or INFERRED (say why).
- Before finishing: call pencil_dod_evaluate_county for your county and paste the FULL before (already given
  above, or re-verify fresh if you suspect drift) and after JSON. If a letter did not move, say so plainly.
- git commit any file you create/modify with a clear message, county-scoped, and 'git pull --rebase origin main'
  before pushing (other shards may be pushing concurrently to shared paths -- you are isolated in a worktree so
  conflicts should be rare, but rebase defensively anyway). Push directly to main -- no branches, no PRs.
- Do NOT run public.gold_standard_loop() or gold_standard_certify() -- other shards may be mid-session. Do NOT
  modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job.
- Budget yourself: this is ONE bounded pass, not a 6-hour campaign. If the true fix requires building a brand-new
  scraper from scratch, do NOT build it in this pass -- size the gap precisely, report it as a scoped-out residual
  with what a future session needs to do, and ship whatever smaller, real, verifiable improvement IS achievable
  via SQL/REST/live lookups/Firecrawl alone (data backfill, wiring an existing-but-unrun pipeline, honesty
  corrections).

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
    `Independently verify this claimed Gold Standard fix for county "${county.slug}". You did NOT write this fix -- be skeptical.\n\n` +
    `Claimed result: ${JSON.stringify(result)}\n\n` +
    `${RECIPE}\n\n` +
    `Your job: re-run pencil_dod_evaluate_county for "${county.slug}" yourself RIGHT NOW (fresh call, do not trust the pasted after_json), ` +
    `compare against the claimed before/after, and check specifically for: (a) denominator mismatches (does the ` +
    `"auctions_total" / "closed_sold" count match what you independently query?), (b) ghost-success (any letter now ` +
    `passing because of a placeholder/fabricated/vacuous value rather than a real fix -- this campaign has a ` +
    `documented history of exactly this failure mode in THIS shard's counties specifically (walton, baker, okaloosa ` +
    `ghost-success purges), be extra skeptical of any new row in those three, (c) whether ` +
    `any OTHER letter for this county regressed as a side effect, (d) for B specifically, the only valid pass band ` +
    `is 95-105%% -- an anomalous ratio outside that (even if the raw pass/fail bit says true) should be flagged, ` +
    `(e) for okaloosa specifically, verify any Bid4Assets-sourced data by independently re-fetching the same URL ` +
    `yourself and confirming the case/amount/address actually appears -- do not trust a screenshot description. ` +
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
