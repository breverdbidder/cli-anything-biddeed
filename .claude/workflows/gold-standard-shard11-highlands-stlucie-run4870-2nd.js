export const meta = {
  name: 'gold-standard-shard11-highlands-stlucie-run4870-2nd',
  description: 'Gold Standard shard-11 2nd firing (highlands/st_lucie, dispatch c7a1fa1a): highlands C/D live-litmus re-check, st_lucie I zoning-substrate + row completeness, adversarially verify',
  phases: [
    { title: 'Diagnose+Fix', detail: 'one agent per county, worktree-isolated' },
    { title: 'Verify', detail: 'independent refuter per county claim' },
  ],
}

const DISPATCH_ID = 'c7a1fa1a-c246-477c-80b0-aaa93b75e4c0'

const COUNTIES = [
  {
    slug: 'highlands',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now, this session): 8/10, only C and D fail:
matched_clean=151, matched_any=151, metric=83.9%% (need >=95%%, i.e. >=171 of auctions_total=180). A=2 fc/td, B=100
(verified=3 closed_sold=3), E=98.9 (parcel_linked=178), F=100 (tier1_sold=3 closed_sold=3), G=100 (density),
H=9h (fresh), I=97.2 (card_complete=175 of 180), J=99.4 (deal_complete=179). Do NOT touch any of these PASSing letters.

THIS IS A SECOND FIRING OF THE SAME DISPATCH (c7a1fa1a) TODAY. Read commit 42ca4761 (git show 42ca4761 -- highlands
section) in full before doing anything -- it already did a careful, adversarially-verified (4/4 survived) live
re-harvest of highlands.realtaxdeed.com for the 31 null-parity rows that existed at that time, and found only 4
of 31 genuinely matched a live calendar listing (case_number + parcel_id). It explicitly and correctly DECLINED to
promote the other 27 because they do not appear on the live calendar under any identifier -- promoting them would be
ghost-success (banned, this campaign has a documented fabrication-purge history). It moved matched_clean 147->151
(81.7%%->83.9%%) and flagged the residual as likely a genuine source-coverage gap, not a matcher bug.

VERIFIED this session -- the CURRENT exact 29-row gap (auctions_total grew by 2 since the prior firing, from a
routine calendar-sweep cron adding 2 new upcoming foreclosure rows -- this is NOT something you caused):
  - 27 rows, data_source='calendar_sweep_mca_v3', parity_status=NULL, parity_source=NULL, all auction_status='upcoming',
    case numbers in the 25000xxx format, spread across exactly 3 future sale dates: 2026-08-05 (10 rows), 2026-08-12
    (9 rows), 2026-08-19 (8 rows). These are (per the commit above) THE SAME 27 rows the prior firing already tried
    and could not match live on highlands.realtaxdeed.com.
  - 2 rows, data_source='realforeclose:shard5-highlands-fc-v1', parity_status='bootstrap_placeholder', parity_source=
    NULL, case_number 'HIGHLANDS-FC-2026-001' (auction_date 2026-08-11) and 'HIGHLANDS-FC-2026-002' (auction_date
    2026-08-26). These are FORECLOSURE (not tax-deed) bootstrap rows and were NOT part of the prior firing's 31-row
    tax-deed-only investigation -- this is a genuinely new, not-yet-attempted lever. Check these against
    highlands.realforeclose.com (the foreclosure calendar platform per pipeline.counties, NOT realtaxdeed.com) for
    the case_number under any format highlands.realforeclose.com uses (RealForeclose case numbers are often plain
    court-format like 'YYCA######' rather than the synthetic 'HIGHLANDS-FC-2026-NNN' bootstrap placeholder id --
    look for the real underlying case behind these 2 bootstrap rows, e.g. via the calendar for those exact 2 dates).

YOUR JOB, in priority order:
1. Check the 2 NEW realforeclose bootstrap rows (HIGHLANDS-FC-2026-001/002) against the LIVE highlands.realforeclose.com
   CALENDAR for 2026-08-11 and 2026-08-26 respectively. If a real case is listed for that date matching the property
   underlying the bootstrap row, promote it (parity_status='matched_clean', parity_source='tier1:highlands_realforeclose_live_<today's date>', and correct the case_number/data_source to the real value if the bootstrap placeholder id is wrong). If nothing is listed for those dates yet (auctions ~3-5 weeks out can legitimately not be posted yet), report that as UNTESTED->still-pending, do not fabricate.
2. Re-run a FRESH live harvest of highlands.realtaxdeed.com for the 3 dates (2026-08-05, 2026-08-12, 2026-08-19) --
   do not just trust yesterday's 4/31 result, the live calendar may have added listings since (auctions closer to
   date tend to get posted). Cross-check case_number AND parcel_id/property address against what's now live. Only
   promote rows with a genuine match. If the result is materially the same as yesterday (still ~27 unmatched), that
   is a legitimate, now-twice-confirmed finding -- report it plainly as a structural residual (source coverage gap:
   these specific case numbers from calendar_sweep_mca_v3 do not correspond 1:1 to what realtaxdeed.com currently
   publishes) rather than a 3rd blind re-attempt next session. Do not fabricate a match to hit 95%%.
3. Even a handful of new genuine matches move the needle: you need +20 (171 total) to flip C/D to PASS. Take
   whatever real matches you find, however few -- partial honest gain is the expected, acceptable outcome per this
   campaign's own precedent (the prior firing's "honest partial gain" of 147->151 was praised, not penalized).`,
  },
  {
    slug: 'st_lucie',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now, this session): 9/10, ONLY I fails now:
card_complete=80 of 93 (86.0%%, need >=95%%, i.e. >=89 of 93 -- need +9). A=13 fc/td, B=100 (verified=2 closed_sold=2),
C=97.8 PASS, D=100 PASS, E=97.8 PASS, F=100 (tier1_sold=2 closed_sold=2), G=96.4 PASS (density), H=3.1h (fresh),
J=100 (deal_complete=93). C/D/E were JUST fixed to PASS by the prior firing of this same dispatch today (commit
42ca4761 -- real live-harvest of stlucie.realforeclose.com, 4/4 adversarially survived). Do NOT touch C/D/E/G or
any other PASSing letter -- I is the ONLY remaining lever for this county.

THIS IS A SECOND FIRING OF THE SAME DISPATCH (c7a1fa1a) TODAY. The prior firing explicitly could not fix I: "exact
evaluator formula for card_complete could not be reverse-engineered without raw SQL access (Mgmt API blocked, DB
pooler auth failed) -- flagged for next session." THIS SESSION HAS WORKING SQL ACCESS (Management API POST
https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query with Authorization: Bearer
$SUPABASE_ACCESS_TOKEN, body {"query":"..."}) and the EXACT evaluator formula has already been pulled via
pg_get_functiondef this session (ground truth, do not re-derive): I requires, per auction row, ALL of: property_address
IS NOT NULL, COALESCE(latitude, po_latitude) IS NOT NULL, COALESCE(longitude, po_longitude) IS NOT NULL,
COALESCE(assessed_value, market_value) IS NOT NULL, AND parcel_id present in a zoning "card" view (v_zoning_gold_standard_card,
built from table parcel_zones joined to jurisdictions, filtered zone_code IS NOT NULL) matched on EITHER parcel_id OR
tax_account (tax_account is always NULL for st_lucie in practice, so effectively parcel_id must appear in
parcel_zones.parcel_id for st_lucie's own jurisdictions).

VERIFIED this session -- the EXACT 13-row gap, per-row cause (queried live, fresh):
  - 10 rows have address+lat/lon+value all present but FAIL solely on the zoning-card join (parcel_id not found in
    parcel_zones for any st_lucie jurisdiction): case_numbers 2024CA000939 (parcel_id 76601), 2025CA000428 (187800),
    2025CA001395 (163015), 2025CA000094 (3089), 2025CC002579 (169213), 2025CA000758 (171596), 2025CA002822 (56994),
    2025CC004638 (1826), 2025CA002588 (342056026250001), 2025CA001086 (parcel_id present but has_zone evaluates NULL
    -- double check this row's exact parcel_id value live, do not assume).
  - 1 row (2025CA001832, parcel_id 24840, 1120 COLONIAL RD, FORT PIERCE) has address+lat/lon+zoning-eligible but
    assessed_value AND market_value are BOTH NULL -- needs a real value backfilled (St Lucie Property Appraiser
    parcel search by account/parcel_id, or the same live source used for the other 16 rows the prior firing already
    backfilled -- see commit 42ca4761).
  - 1 row (2024CA000214, no address/lat/lon/value/parcel_id at all) is a much deeper gap -- needs re-identification
    from source (the case_number alone) before anything else can be filled; if it cannot be identified from a live
    source, report it honestly as residual rather than fabricating any field.

VERIFIED this session -- the zoning substrate gap root cause: v_zoning_gold_standard_card for st_lucie currently has
only 79 distinct parcel_id values total (feeding off table parcel_zones, jurisdiction_ids: 1400=St. Lucie County
Unincorporated, 953=Port St. Lucie, 971=Fort Pierce, 1128=St. Lucie Village). NONE of your 9-10 gap parcel_ids exist
in parcel_zones under any jurisdiction. Some existing parcel_zones rows for st_lucie carry source='arcgis_live_lookup_2026-07-11'
(REAL, from slcgis.stlucieco.gov's ArcGIS LandUse/Zoning MapServer -- this is the correct, real method, use it again)
-- but OTHERS carry source='shard1_st_lucie_synthetic' (a placeholder/synthetic source from an earlier session, NOT
a real ordinance/GIS citation). AUDIT FLAG, do not silently ignore: G currently PASSes for st_lucie at 96.4%% density,
and it is UNKNOWN how much of that rests on the synthetic rows vs the real arcgis_live_lookup rows -- note this in
your honesty_notes as a flagged-but-out-of-scope concern (G is not your assigned letter this firing; do not touch
existing parcel_zones rows), but do NOT yourself add any more synthetic rows. Every new parcel_zones row you insert
for these 9-10 parcels MUST come from a real live query against slcgis.stlucieco.gov's ArcGIS LandUse/Zoning
MapServer (or an equivalent real, citable St Lucie County GIS/Property Appraiser source) -- same method as the
existing real rows, never a guess or a copy of a neighboring parcel's zone_code.

YOUR JOB, in priority order (10 real zoning matches would take card_complete from 80 to potentially 90, already
clearing the +9 needed for PASS):
1. For each of the 10 zoning-gap parcel_ids, query slcgis.stlucieco.gov's ArcGIS LandUse/Zoning MapServer (REST API,
   query by parcel/PIN/account field -- inspect the MapServer's layer fields first, the existing real rows prove
   this endpoint works) to get the real zone_code (and zone_name/future_land_use if available) and which jurisdiction
   the parcel falls in (use the property_address city as a cross-check: PORT SAINT LUCIE addresses -> jurisdiction_id
   953; FORT PIERCE -> could be 971 (city) or 1400 (unincorporated, many Fort-Pierce-addressed parcels are actually
   unincorporated county) -- trust the ArcGIS response's own jurisdiction/municipality field over the mailing-address
   city if they conflict; SAINT LUCIE COUNTY -> jurisdiction_id 1400). Insert one parcel_zones row per confirmed
   parcel with source='arcgis_live_lookup_<today's date>' (matching the existing real-row naming convention).
2. For case 2025CA001832's missing assessed_value/market_value, and for re-identifying 2024CA000214, use the same
   real live source(s) the prior firing (commit 42ca4761) used for its 16-row value backfill and 3-row parcel_id
   backfill -- read that commit's actual SQL/script for the exact method before improvising a new one.
3. Report exactly how many of the 13 gap rows you closed and why any remainder is blocked -- partial honest gain
   (e.g. 8 of 10 zoning matches found) is an acceptable, expected outcome; do not force all 13 to pass artificially.`,
  },
]

const RECIPE = `
Environment (already available, do not ask for credentials):
- REST API reads/writes: GET/PATCH \${SUPABASE_URL}/rest/v1/<table>?... with headers
  apikey: $SUPABASE_SERVICE_ROLE_KEY, Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY
- Live arbitrary SQL (VERIFIED working this session): POST
  https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query
  headers Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json
  body {"query": "<sql>"} -- run "SET statement_timeout = 0;" first in the same query string for anything heavy.
  Build this JSON with a real JSON encoder (python3 -c "import json; ..." writing to a temp file, then
  curl --data-binary @file) rather than hand-quoting shell strings. WATCH FOR SQL THREE-VALUED-LOGIC BUGS when
  writing your own diagnostic gap queries: "NOT (x AND y)" silently drops rows where x or y is NULL (NULL, not
  FALSE) -- use "COALESCE(cond,false)" or explicit "IS NOT TRUE" wrapping, or you will undercount the real gap
  (this bit a diagnostic query earlier this session; the numbers pasted above are already corrected for it).
- pencil_dod_evaluate_county RPC: POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county
  headers apikey/Authorization as above, body {"p_county": "<slug>"} -- this is your before/after proof. The full
  live function definition (pulled via pg_get_functiondef this session, ground truth) computes every letter from
  multi_county_auctions filtered to lower(county)=<slug> AND (data_source <> 'propertyonion' OR tier1_authoritative
  = true). C/D require parity_source LIKE 'tier1%%' IN ADDITION to parity_status -- setting parity_status alone does
  NOT satisfy C/D. I requires the exact per-row AND condition spelled out in your county context above.
- FIRECRAWL_API_KEY is available in this environment for any JS-rendered or form-driven page (ArcGIS REST endpoints
  are typically plain JSON over HTTP and do not need it, but the realtaxdeed.com/realforeclose.com calendars may).
- gh CLI is authenticated (repo, workflow scopes) for git operations.
- Repo root is the current working directory, on main. Schema changes MUST go through a migration file under
  supabase/migrations/<date>_shard11_2nd_<county>_<purpose>.sql, committed to git. Simple data backfills (UPDATE/
  PATCH/INSERT on existing columns, no schema change) do not need a migration file -- just do the REST PATCH/POST/
  INSERT or a direct UPDATE via the Management API and note the exact SQL/endpoint used.

ULTRALOOP audit logging (mandatory per campaign protocol): for every letter you claim moved (or claim you verified
as correctly-blocked/residual), INSERT one row into public.gold_standard_ultraloop_audit: columns dispatch_id
(uuid '${DISPATCH_ID}'), ultraloop_mode ('fallback' -- this session used Workflow-tool agent fan-out, not native
/effort ultracode), county_slug, letter, claim (short text), refuter_evidence (jsonb -- for the FIX agent, your own
before/after evidence; for the VERIFY agent, your refutation attempt and findings), survived (boolean, true only if
the claim held up under adversarial check). POST to \${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with the
service-role headers above.

Hard rules (from the campaign brief -- follow exactly):
- You own ONLY your assigned county and letter(s). Never touch another shard's counties, or any other letter for
  your own county that is already PASSing.
- PropertyOnion is litmus/comparison ONLY -- never write po_*-derived values in as if verified/independent.
- Fail-loud invariant: if a fix attempt finds zero real data, report it as a blocked/residual gap. NEVER fabricate
  case numbers, parcel IDs, zone codes, sale amounts, or timestamps to make a metric look better. This campaign has
  a documented history of exactly this failure mode (gulf B/F fabrication, purged; st_lucie's own
  shard1_st_lucie_synthetic zoning rows flagged above) -- do not repeat it, including "close enough" placeholder
  values or copying a neighboring parcel's zone_code as a guess.
- Every claim you return must be tagged VERIFIED (you ran the query/request and are pasting real output), UNTESTED,
  or INFERRED (say why).
- Before finishing: call pencil_dod_evaluate_county for your county and paste the FULL before (already given above,
  or re-verify fresh if you suspect drift) and after JSON. If a letter did not move, say so plainly.
- git commit any file you create/modify with a clear message, county-scoped, and 'git pull --rebase origin main'
  before pushing (the other shard's counties are disjoint from yours but you are isolated in a worktree anyway --
  rebase defensively). Push directly to main -- no branches, no PRs.
- Do NOT run public.gold_standard_loop() or gold_standard_certify() -- other shards may be mid-session. Do NOT
  modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job.
- Budget yourself: this is ONE bounded pass per county, not a 6-hour campaign. Both gaps here are small and
  well-scoped (highlands needs +20 of 29 rows, st_lucie needs +9 of 13 rows) -- do not build new scraper
  infrastructure from scratch; use the existing real endpoints/methods already proven in this county's history.

Return a structured report: { county, letters_touched: [...], fix_summary, sql_or_endpoints_used: [...],
before_json, after_json, residual_gaps: [...], honesty_notes: [...] }.
`

phase('Diagnose+Fix')
const fixResults = await pipeline(
  COUNTIES,
  (county) => agent(
    `You are working Gold Standard shard-11, county "${county.slug}", inside the cli-anything-biddeed repo (already checked out, on main). This is the SECOND firing of dispatch ${DISPATCH_ID} today -- a prior firing already committed real progress (see commit 42ca4761), read it before starting.\n\n${county.context}\n\n${RECIPE}`,
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
    `compare against the claimed before/after, and check specifically for: (a) denominator mismatches (does ` +
    `"auctions_total" match what you independently query?), (b) ghost-success (any letter now passing because of a ` +
    `placeholder/fabricated/vacuous value rather than a real fix -- for st_lucie specifically, spot-check that any ` +
    `NEW parcel_zones row this fix inserted has source LIKE 'arcgis_live_lookup%%' or another real, citable source, ` +
    `NOT a copy/guess and NOT 'shard1_st_lucie_synthetic'-style; for highlands specifically, spot-check that any newly ` +
    `promoted matched_clean row actually appears on the live realtaxdeed.com/realforeclose.com calendar right now, by ` +
    `checking it yourself), (c) whether any OTHER letter for this county regressed as a side effect (re-check ALL ` +
    `10 letters, not just the ones claimed fixed), (d) if a claimed fix relied on a new outcome/parity/zoning row, ` +
    `spot-check at least 2 of them against the cited live source yourself. Also INSERT your own ` +
    `gold_standard_ultraloop_audit row per the RECIPE instructions (ultraloop_mode='fallback'). ` +
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
