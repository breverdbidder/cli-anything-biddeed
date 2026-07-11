export const meta = {
  name: 'gold-standard-shard7-run3679-c',
  description: 'Gold Standard shard-7 continuation (volusia/gadsden/santa_rosa/lake): work the prior closeout report\'s next-session-priorities queue (lake G, gadsden I/E, santa_rosa I, lake B/F recheck), adversarially verify',
  phases: [
    { title: 'Diagnose+Fix', detail: 'one agent per priority item, worktree-isolated' },
    { title: 'Verify', detail: 'independent refuter per claim' },
  ],
}

const DISPATCH_ID = '9fe2973e-44ea-441c-9770-92ff736483dd'

const ITEMS = [
  {
    key: 'lake_G',
    county: 'lake',
    context: `CONTEXT: this is a re-fire of an ALREADY-COMPLETED shard-7 dispatch (dispatch_id ${DISPATCH_ID}). The
prior session's closeout report (SHARD7_RUN3679_VOLUSIA_GADSDEN_SANTA_ROSA_LAKE_SESSION_REPORT.md, already on
main, read it in full before starting) fixed lake I by replacing a FABRICATED zoning substrate
(zoning_districts id=10716 "Single Family Residential (Shard7 Synthetic)", zone_standards id=3401 with hardcoded
max_far=0.35/max_density_du_acre=4.0/parking_per_1000sf=2.0, all NULL source_url/ordinance_section/confidence_score)
with 33 REAL parcel_zones rows sourced from Lake County's live zoning GIS layer
(gis.lakecountyfl.gov/InteractiveMap/MapServer/50), carrying real diverse zone codes: A, CFD, PUD, R-3, R-6, R-7, RM.
That fix correctly caused G to regress from a fabricated 100% to an honest 0% (density=23.3 far=0.0 pk1000=0.0),
because these 7 real zone codes have NO zoning_districts/zone_standards rows at all yet. This was explicitly flagged
as the #1 next-session priority ("highest-leverage single fix available for lake").

Fresh live re-verify (just run via pencil_dod_evaluate_county, confirms report, no drift):
lake G still FAIL, metric=0.0, detail="density=23.3 far=0.0 pk1000=0.0".

YOUR JOB: build REAL, sourced dimensional zoning standards (max_far, max_density_du_acre, parking_per_1000sf) for
these 7 Lake County zone codes: A (Agriculture), CFD (Community Facility District), PUD (Planned Unit Development),
R-3, R-6, R-7 (single/multi-family residential districts), RM (Multi-family Residential). Source: Lake County Land
Development Regulations (LDR) — search live for library.municode.com/fl/lake_county or the county's own published
LDR PDF/ordinance text (do not guess a URL, verify it resolves and actually contains dimensional standards tables).
PUD is likely a special case (standards set per-development-agreement rather than a single county-wide table) —
if so, either find the applicable baseline/default standard the county code specifies for PUD absent a specific
agreement, or report PUD honestly as structurally requiring per-development lookup (do not fabricate a single
number for it if the ordinance itself says "as approved in the PUD agreement").

Write to zoning_districts (code, name, category, jurisdiction_id matching lake's jurisdiction 835 used by the prior
fix) and zone_standards (max_far, max_density_du_acre, parking_per_1000sf, source_url, ordinance_section,
confidence_score — NEVER NULL these honesty-marker columns, this project has a documented history of exactly this
fabrication pattern and it must not repeat). If you cannot find a real value for one of the 7 codes after a genuine
search, leave that one out rather than guessing — partial real coverage that moves the metric honestly is fine,
fabricating the gap closed is not.`,
  },
  {
    key: 'gadsden_I',
    county: 'gadsden',
    context: `CONTEXT: re-fire of already-completed dispatch ${DISPATCH_ID}. Prior session's closeout report found
gadsden I blocked at 30.4% (card_complete=7 of 23) because the only 7 rows satisfying the zoning-card join carry a
synthetic zone_code='R-1' from a quarantined bootstrap script (parcel_zones.source='shard8_gadsden_bootstrap_synthetic'),
and fl_parcels WHERE co_no=30 has ZERO rows with real zone_code/future_land_use — no real per-parcel zoning source
was found in this DB for Gadsden. Live-fetch attempts to gadsdencountyfl.gov, qpublic.net/fl/gadsden,
qpublic.schneidercorp.com, gadsdenpa.com ALL returned HTTP 403 (Cloudflare-blocked to the sandbox's default UA).
library.municode.com was reachable but ordinance text alone can't produce a per-parcel zone assignment without a
GIS spatial join. This was explicitly flagged as next-session priority #1 for gadsden: "try from a different egress
path or with browser automation (Firecrawl/Playwright) before assuming it's unreachable entirely."

Fresh live re-verify: gadsden I still FAIL, metric=30.4, detail="card_complete=7 of 23".

YOUR JOB: retry reaching a real per-parcel Gadsden County zoning source, specifically trying things NOT yet tried:
(1) a realistic browser User-Agent header on the same 403'ing URLs (this exact trick unblocked franklinclerk.com in
a sibling shard this same run — check if it works here too), (2) search for a Gadsden County ArcGIS Online org /
Hub site (hub.arcgis.com, gadsden-county-fl-hub.hub.arcgis.com or similar — search live, do not guess), (3) check
if ToolSearch surfaces a firecrawl MCP tool in this environment (query "firecrawl scrape") — if present, use it,
it may succeed where a raw fetch 403s. If a real per-parcel zoning source is found, spatially or by-parcel-id join
it against the 16 non-synthetic-zoned gadsden parcels (parcel_id known from multi_county_auctions, co_no=30) and
write real parcel_zones/zoning_districts/zone_standards rows (do NOT extend the synthetic R-1 to more parcels).
If genuinely still unreachable after these new angles, report precisely what you tried and its result (403, DNS
failure, etc.) — a confirmed-still-blocked result is a legitimate, valuable outcome, do not force a fabricated pass.`,
  },
  {
    key: 'gadsden_E',
    county: 'gadsden',
    context: `CONTEXT: re-fire of already-completed dispatch ${DISPATCH_ID}. Prior session moved gadsden E from
73.9% to 78.3% (parcel_linked 17->18 of 23) via a unique owner-name match, and found the remaining 5 unlinked rows
(surnames: Burger, Ramon's Construction, Booker-Barnes, Woods, White) each fail because either (a) multiple real
ArcGIS/fl_parcels candidates share the surname with no way to disambiguate, or (b) the source case is no longer on
the live Clerk sheet to re-verify. This was flagged as next-session priority #2: try either an authenticated Clerk
case-search session to re-pull current defendant/case address details for Woods/White, or a smarter disambiguation
signal (cross-referencing situs/property address fragments in the case record against fl_parcels' situs address
field) for Burger/Ramon's Construction/Booker-Barnes.

Fresh live re-verify: gadsden E still FAIL, metric=78.3, detail="parcel_linked=18 of 23".

YOUR JOB: query multi_county_auctions for gadsden's 5 remaining NULL-parcel_id rows, extract whatever property
address / legal description text exists on each row (even a partial street name or subdivision fragment), then
cross-reference that against fl_parcels (co_no=30) situs_address/site_address column for the SAME surname/owner
candidates that were previously ambiguous — if an address fragment uniquely disambiguates one of the multi-candidate
matches (e.g. "Burger" has 3 ArcGIS hits but only 1 sits on the street named in the case record), write that single,
now-unambiguous parcel_id link with a clear data_source noting the disambiguation method. For Woods/White (case no
longer on the live Clerk sheet), try the gadsdenclerk.com site's case search or archive by case number directly
(not just the current sheet) to see if a closed/archived case record with a fuller address still exists. Do NOT
guess between multiple real candidates without a genuine disambiguating signal — an unresolved row stays unresolved
and gets reported as a residual, per BLANK > WRONG.`,
  },
  {
    key: 'santa_rosa_I',
    county: 'santa_rosa',
    context: `CONTEXT: re-fire of already-completed dispatch ${DISPATCH_ID}. Prior session moved santa_rosa I from
71.1% to 86.8% (card_complete 54->66 of 76) via 13 new parcel_zones rows from Santa Rosa's own public ArcGIS
(ParcelsOpenData + Zoning FeatureServers, owner gisupdates_SantaRosaGIS) plus 5 real zone_standards rows (codes
AG-RR, R1, R1M, R2M, PUD) sourced from the county's own LDC Table 2.04.02. Residual 10 rows, broken down: 3 have no
parcel_id at all (Letter E's scope — E already PASSes at 96.1%, deliberately not touched to avoid an E regression,
DO NOT touch these 3 either), 6 resolve to a real parcel centroid but a point-in-polygon query against the Zoning
FeatureServer at that centroid returns only a coarse DISTRICT=CITY municipal-boundary marker (not a real zoning
district code), 1 is an HOA-owned vacant lot with no assessed_value/market_value field anywhere in the county's
public ArcGIS parcel layer (confirmed via a full field-list query — likely a genuine dead end). This was flagged as
next-session priority #3, specifically the 6 CITY-marker rows: "may require a different Santa Rosa GIS layer or a
manual review of those 6 specific parcels."

Fresh live re-verify: santa_rosa I still FAIL, metric=86.8, detail="card_complete=66 of 76".

YOUR JOB: identify the 6 specific rows still returning DISTRICT=CITY at their centroid (re-run the point-in-polygon
query fresh, list the parcel_ids). These 6 fall inside an incorporated municipality (likely Milton, Gulf Breeze, or
Jay based on the coarse CITY marker) whose zoning is NOT covered by the county's own unincorporated Zoning
FeatureServer layer. Search live for that specific municipality's OWN zoning GIS layer/ArcGIS FeatureServer (do not
guess a URL — verify it resolves) and re-query those 6 parcels against it. If found, write real
parcel_zones/zoning_districts/zone_standards rows for whatever new zone codes appear (with real dimensional
standards sourced from that municipality's own zoning ordinance, honesty markers required, same rigor as the prior
session's AG-RR/R1/R1M/R2M/PUD rows — do not let G regress the way lake's I fix did; if you add a new zone code,
either source real standards for it in the same pass or explicitly flag it as a G-risk in your report before
writing). Do not touch the 3 no-parcel_id rows (E's scope) or force a value onto the 1 HOA dead-end row.`,
  },
  {
    key: 'lake_BF_recheck',
    county: 'lake',
    context: `CONTEXT: re-fire of already-completed dispatch ${DISPATCH_ID}. Prior session confirmed lake B/F are
genuinely blocked: the only closed Lake auction (TD case 00389-2023) shows Auction Status=Redeemed on the live
lake.realtaxdeed.com Preview page (a redemption has no sold_amount by definition), lake has no RealForeclose FC
platform at all (only "Lake Taxdeed" listed in the RealAuction county picker), and or.lakecountyclerk.org (official
records) FAILED TO RESOLVE entirely that session. Two stale statuses were corrected honestly (00389-2023:
sold->redeemed; 02731-2022: upcoming->canceled_bankruptcy). This was flagged as next-session priority #5: "re-check
lake.realtaxdeed.com periodically rather than re-running the same probe; also worth checking whether
or.lakecountyclerk.org ever becomes reachable."

Fresh live re-verify: lake B FAIL metric=null (verified=0 closed_sold=0), F FAIL metric=null (tier1_sold=0
closed_sold=0).

YOUR JOB: this is a bounded, quick recheck, not a rebuild. (1) Re-fetch lake.realtaxdeed.com's Preview/Auction
Calendar for any Lake tax-deed case now showing a real Sold/Redeemed-with-overbid status with a dollar amount (not
just 00389-2023 — check the FULL current calendar for any case that has closed since the prior session). (2) Retry
resolving or.lakecountyclerk.org (DNS + HTTP) — if it now resolves, check whether it exposes official-records
Certificate of Title / sale-result data by case number. (3) If a real sold_amount is found anywhere, write the
INDEPENDENT verified outcome row (tax_deed_outcomes, honest data_source) and backfill the matching
multi_county_auctions row, then confirm B/F actually moved via pencil_dod_evaluate_county. If nothing has changed
(most likely — only hours have passed since the prior check), confirm and report the still-blocked status plainly
with your fresh evidence — do not spend excessive budget re-deriving what the prior session already established.`,
  },
]

const RECIPE = `
Environment (already available, do not ask for credentials):
- REST API reads/writes: GET/PATCH \${SUPABASE_URL}/rest/v1/<table>?... with headers
  apikey: $SUPABASE_SERVICE_ROLE_KEY, Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY
- Live arbitrary SQL: POST https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query
  headers Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json
  body {"query": "<sql>"} -- run "SET statement_timeout = 0;" first in the same query string for anything heavy.
  Build this JSON with a real JSON encoder (e.g. python3 -c "import json; ..." writing to a temp file, then curl
  --data-binary @file) rather than hand-quoting shell strings.
- pencil_dod_evaluate_county RPC: POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county
  headers apikey/Authorization as above, body {"p_county": "<slug>"} -- this is your before/after proof.
  card_complete (I) requires address AND geo AND value AND the parcel_id present in v_zoning_gold_standard_card.
  C/D require parity_source LIKE 'tier1%%' in addition to parity_status. G = min(density,FAR,pk1000) coverage
  across applicable zoning_districts/zone_standards for the county's zoned parcels.
- Direct DB pooler/psql is CONFIRMED STALE this run (password auth fails) -- use PostgREST/Management-API only,
  consistent with every prior shard session this campaign.
- gh CLI is authenticated (repo, workflow scopes) for git operations.
- Repo root is the current working directory, on main. Read
  SHARD7_RUN3679_VOLUSIA_GADSDEN_SANTA_ROSA_LAKE_SESSION_REPORT.md in full before starting -- it is the baseline
  for every item above and cites the exact prior scripts (scripts/shard7_run3679_*.py) you should check before
  writing anything new.
- Schema changes go through a migration file under supabase/migrations/<date>_shard7c_<item>_<purpose>.sql,
  committed to git, applied via the Management API. Simple data backfills (UPDATE/PATCH, no schema change) don't
  need a migration file -- just do the REST PATCH/Management-API UPDATE and note the exact SQL/endpoint used.
- Some small-county sites (e.g. franklinclerk.com in a sibling shard this run) 403 a default UA but work with a
  standard browser User-Agent header -- try that before concluding a source is unreachable.

ULTRALOOP audit logging (mandatory): for every letter you claim moved (or claim you verified as
correctly-blocked/residual), INSERT one row into public.gold_standard_ultraloop_audit: columns dispatch_id
(uuid '${DISPATCH_ID}'), ultraloop_mode ('fallback'), county_slug, letter, claim (short text), refuter_evidence
(jsonb -- your before/after evidence for FIX agents, your refutation attempt for VERIFY agents), survived (boolean).
POST to \${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with the service-role headers above.

Hard rules:
- Touch ONLY your assigned item's county/letter scope. Never touch another item's rows or another shard's counties.
- PropertyOnion is litmus/comparison ONLY -- never write po_*-derived values in as if verified/independent.
- Fail-loud invariant: zero real data found = report a blocked/residual gap. NEVER fabricate case numbers, parcel
  IDs, sale amounts, coordinates, zoning standards, or timestamps to make a metric look better. This project has a
  documented history of exactly this failure mode (gulf B/F fabrication, franklin fabrication, and THIS county's
  own lake-G fabricated-standard incident that the prior session just cleaned up) -- do not repeat it.
- Every claim must be tagged VERIFIED (you ran the query/request and are pasting real output), UNTESTED, or
  INFERRED (with a 1-sentence reason).
- Before finishing: call pencil_dod_evaluate_county for your county and paste the FULL before/after JSON. If a
  letter did not move, say so plainly.
- git commit any file you create/modify with a clear, item-scoped message; 'git pull --rebase origin main' before
  pushing (other items are isolated in separate worktrees but push to the same main). Push directly to main -- no
  branches, no PRs.
- Do NOT run public.gold_standard_loop() or gold_standard_certify() yourself. Do NOT modify cron jobs 109, 111,
  115, or any gold-standard-loop-* scoring job.
- Budget: this is ONE bounded pass per item. If a true fix needs a brand-new scraper/full substrate build from
  scratch, do NOT build it in this pass if large -- size the gap precisely, report as scoped-out residual, ship
  whatever smaller real improvement IS achievable via SQL/REST/live lookups alone.

Return a structured report: { item_key, county, letters_touched: [...], fix_summary, sql_or_endpoints_used: [...],
before_json, after_json, residual_gaps: [...], honesty_notes: [...] }.
`

phase('Diagnose+Fix')
const fixResults = await pipeline(
  ITEMS,
  (item) => agent(
    `You are working Gold Standard shard-7 continuation, item "${item.key}" (county "${item.county}"), inside the cli-anything-biddeed repo (already checked out, on main).\n\n${item.context}\n\n${RECIPE}`,
    {
      label: `fix:${item.key}`,
      phase: 'Diagnose+Fix',
      isolation: 'worktree',
      schema: {
        type: 'object',
        properties: {
          item_key: { type: 'string' },
          county: { type: 'string' },
          letters_touched: { type: 'array', items: { type: 'string' } },
          fix_summary: { type: 'string' },
          sql_or_endpoints_used: { type: 'array', items: { type: 'string' } },
          before_json: {},
          after_json: {},
          residual_gaps: { type: 'array', items: { type: 'string' } },
          honesty_notes: { type: 'array', items: { type: 'string' } },
        },
        required: ['item_key', 'county', 'fix_summary', 'before_json', 'after_json'],
      },
    }
  )
)

phase('Verify')
const verified = await pipeline(
  fixResults.filter(Boolean),
  (result, item) => agent(
    `Independently verify this claimed Gold Standard fix for item "${item.key}" (county "${item.county}"). You did NOT write this fix -- be skeptical.\n\n` +
    `Claimed result: ${JSON.stringify(result)}\n\n` +
    `${RECIPE}\n\n` +
    `Your job: re-run pencil_dod_evaluate_county for "${item.county}" yourself RIGHT NOW (fresh call, do not trust the pasted after_json), ` +
    `compare against the claimed before/after, and check specifically for: (a) denominator mismatches, (b) ghost-success ` +
    `(any letter now passing/improved because of a placeholder/fabricated/vacuous value rather than a real fix -- this ` +
    `shard has a documented ghost-success incident on lake G already this run, be extra skeptical of any new zoning ` +
    `standards claims), (c) whether any OTHER letter for this county regressed as a side effect (especially: did a new ` +
    `zoning write cause a G change for a DIFFERENT reason than claimed; did a santa_rosa parcel_zones write touch any ` +
    `of the 3 rows that should have been left to Letter E), (d) for B specifically, the only valid pass band is ` +
    `95-105%% -- flag anything outside that even if the raw pass bit is true. Also INSERT your own ` +
    `gold_standard_ultraloop_audit row per the RECIPE instructions (ultraloop_mode='fallback'). ` +
    `Return { item_key, county, refuted: boolean, refutation_reason: string|null, fresh_evaluation: <the JSON you just got>, survives: boolean }.`,
    {
      label: `verify:${item.key}`,
      phase: 'Verify',
      schema: {
        type: 'object',
        properties: {
          item_key: { type: 'string' },
          county: { type: 'string' },
          refuted: { type: 'boolean' },
          refutation_reason: { type: ['string', 'null'] },
          fresh_evaluation: {},
          survives: { type: 'boolean' },
        },
        required: ['item_key', 'county', 'refuted', 'fresh_evaluation', 'survives'],
      },
    }
  )
)

return { fixResults, verified }
