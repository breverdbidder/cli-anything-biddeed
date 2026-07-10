export const meta = {
  name: 'shard7-gold-standard-run3645',
  description: 'Gold Standard shard-7 (citrus/st_johns/holmes/bradford): diagnose, fix, adversarially verify failing letters per county',
  phases: [
    { title: 'Diagnose+Fix', detail: 'one agent per county, worktree-isolated' },
    { title: 'Verify', detail: 'independent refuter per county claim' },
  ],
}

const COUNTIES = [
  {
    slug: 'citrus',
    context: `Baseline from the dispatch brief (RE-VERIFY live first, do not trust this number blindly):
9/10, only I fails at ~94.2-94.7% (card_complete=178-179 of 189 auctions, need 180+/189 for 95%). All other
letters (A,B,C,D,E,F,G,H,J) PASS. This is the highest-leverage target in the shard: exactly 1-2 more complete
rows crosses the threshold. Diagnostic query for incomplete card rows:
WITH zc AS (SELECT DISTINCT parcel_id, tax_account FROM v_zoning_gold_standard_card WHERE lower(county)=norm_county_key('citrus') AND zone_code IS NOT NULL)
SELECT case_number, property_address IS NOT NULL has_addr, COALESCE(latitude,po_latitude::double precision) IS NOT NULL has_lat,
COALESCE(assessed_value,market_value) IS NOT NULL has_val, parcel_id,
(parcel_id IN (SELECT parcel_id FROM zc) OR parcel_id IN (SELECT tax_account FROM zc WHERE tax_account IS NOT NULL)) zoned
FROM multi_county_auctions a2 WHERE lower(a2.county)='citrus' AND (COALESCE(a2.data_source,'')<>'propertyonion' OR COALESCE(a2.tier1_authoritative,false)=true)
AND NOT (a2.property_address IS NOT NULL AND COALESCE(a2.latitude,a2.po_latitude::double precision) IS NOT NULL
AND COALESCE(a2.longitude,a2.po_longitude::double precision) IS NOT NULL AND COALESCE(a2.assessed_value,a2.market_value) IS NOT NULL
AND (a2.parcel_id IN (SELECT parcel_id FROM zc) OR a2.parcel_id IN (SELECT tax_account FROM zc WHERE tax_account IS NOT NULL)));
For each incomplete row, figure out which specific field is missing (address/geo/value/parcel-zoning-join) and backfill from a
real source: Citrus County Property Appraiser (citruspa.org or qpublic.net/fl/citrus) for address/value/parcel_id, FL GIO
statewide cadastral API (CO_NO for Citrus=17) as fallback for geo, or a live geocoder for lat/lng if address exists but
coordinates don't. If parcel_id exists but doesn't resolve against v_zoning_gold_standard_card, check whether it's a format
mismatch (compare a couple of citrus parcel_zones.parcel_id values directly) before assuming no zoning coverage exists.
Since G already passes at 97.7% density (far/pk1000 blank — verify this isn't a hollow/vacuous pass by checking the underlying
applicable-parcel denominator is non-trivial), zoning substrate for citrus is mostly there — the gap is likely address/geo/value
enrichment on a handful of specific rows, not a missing zoning layer.`,
  },
  {
    slug: 'st_johns',
    context: `Baseline from the dispatch brief (RE-VERIFY live first): 8/10. Failing: E (86.5%, parcel_linked=32 of 37,
need 36+/37), I (81.1%, card_complete=30 of 37, need 36+/37). Small denominator (37 total) means every single row fixed
moves the needle ~2.7 points — very tractable. E gates I (I requires parcel_id to resolve into v_zoning_gold_standard_card,
so fixing E rows may fix I rows for free per the evaluator's documented E<=I dependency chain). Diagnostic query:
SELECT case_number, property_address, parcel_id, latitude, po_latitude, longitude, po_longitude, assessed_value, market_value
FROM multi_county_auctions WHERE lower(county)='st_johns' AND (COALESCE(data_source,'')<>'propertyonion' OR COALESCE(tier1_authoritative,false)=true)
AND parcel_id IS NULL;
Recover missing parcel_id via St Johns County Property Appraiser (sjcpa.us or qpublic.net/fl/st_johns) ArcGIS FeatureServer
by matching property_address, or via St Johns Clerk case lookup if address match fails. Do NOT fabricate a parcel_id if no
live source confirms it -- leave unlinked and report as residual. Once E rows are fixed, re-run the I diagnostic query
(same pattern as other counties in this campaign -- join against v_zoning_gold_standard_card by parcel_id/tax_account) to
confirm which I rows resolved automatically vs still need address/geo/value enrichment separately.`,
  },
  {
    slug: 'holmes',
    context: `Baseline from the dispatch brief (RE-VERIFY live first): 6/10. Passing: A,E,G,H,I,J. Failing: B (null,
verified=0 closed_sold=0), C (61.5%, matched_clean=8 of 13), D (61.5%, matched_any=8 of 13), F (null, tier1_sold=0
closed_sold=0). Tiny county (13 total auctions) -- tractable if real sources exist. B/F are structurally "null" because
closed_sold=0: check whether ANY holmes auctions have actually closed/sold yet (auction_status/sale outcome) -- if zero
have closed, B/F are NOT-YET-MEASURABLE (correctly null, do not force a value) rather than a bug to fix; verify this before
spending time on B/F. C/D: 5 of 13 rows have parity_status NULL or not matched -- check whether holmes has a RealAuction
subdomain (holmes.realforeclose.com / holmes.realtaxdeed.com) via pipeline.counties.foreclosure_url/taxdeed_url and whether
the AJAX litmus harvester has ever been run for holmes (grep scripts/ for existing holmes-specific work first to avoid
duplicating). If holmes has no RealAuction presence (small rural county, may be clerk-only in-person sales like hardee),
invoke the pre-authorized clerk/official-records supplementary litmus: find Holmes Clerk of Court's published sale calendar
(holmesclerk.com or similar) and independently cross-check the 5 unmatched cases. Diagnostic query:
SELECT case_number, parity_status, parity_source, sale_type, auction_status, auction_date FROM multi_county_auctions
WHERE lower(county)='holmes' AND (COALESCE(data_source,'')<>'propertyonion' OR COALESCE(tier1_authoritative,false)=true);`,
  },
  {
    slug: 'bradford',
    context: `Baseline from the dispatch brief (RE-VERIFY live first): 3/10. Passing: G,H,J only. Failing: A (fc=4 td=0),
B (null, verified=0 closed_sold=0), C (0.0%, matched_clean=0 of 4), D (0.0%, matched_any=0 of 4), E (50.0%, parcel_linked=2
of 4), I (null, card_complete=0 of 4). Tiny county (only 4 auctions total, all foreclosure, zero tax-deed) -- this is the
smallest and rawest county in the shard. CRITICAL FIRST STEP per the campaign's fabrication-guardrail history (see hardee/
gulf precedent documented in CLAUDE.md and prior shard sessions): before touching ANY of these 4 rows, pull the full row
data (all columns, especially data_source, created_at, case_number format, parcel_id format) and verify these look like
REAL Bradford County court cases (case_number should resemble a real Bradford Clerk format, e.g. "24-CA-XXXXXX") and real
parcel_ids (Bradford Property Appraiser format), not synthetic placeholders. If genuine: (1) A needs BOTH fc>0 AND td>0 --
Bradford currently has fc=4 td=0, so find whether Bradford has any tax-deed sales at all (bradfordclerk.com or
bradford.realtaxdeed.com) and ingest at least one real case if it exists. (2) E: 2 of 4 rows lack parcel_id -- recover via
Bradford County Property Appraiser (bradfordappraiser.com or qpublic.net/fl/bradford) matching property_address, real
values only. (3) C/D: check if Bradford has a RealAuction subdomain (bradford.realforeclose.com) and whether the AJAX
litmus harvester has ever run for it; if it's clerk-only, use the pre-authorized clerk-records supplementary litmus
against Bradford Clerk's published foreclosure sale listing. (4) B/F: only measurable once a real closed/sold case exists
-- do not fabricate an outcome for a case that hasn't sold. (5) I follows E+address/geo/value enrichment once parcel
linkage is fixed. Diagnostic query: SELECT case_number, parity_status, parcel_id, property_address, sale_type,
auction_status, data_source FROM multi_county_auctions WHERE lower(county)='bradford' AND (COALESCE(data_source,'')<>'propertyonion'
OR COALESCE(tier1_authoritative,false)=true);`,
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
  headers apikey/Authorization as above, body {"p_county": "<slug>"} -- this is your before/after proof. Call it
  FIRST (before any change) and record the verbatim JSON, then again at the end.
- gh CLI is authenticated (repo, workflow scopes) for git operations and workflow dispatch if needed.
- Repo root is the current working directory (you are in an isolated git worktree). Schema changes MUST go through
  a migration file under supabase/migrations/<date>_shard7_<county>_<purpose>.sql, committed to git -- even though
  you CAN run SQL directly via the Management API, still write the migration file for the historical record and
  apply it the same way (directly via the Management API call above). Simple data backfills (UPDATE/PATCH on
  existing columns, no schema change) do not need a migration file -- just do the REST PATCH or a direct UPDATE via
  the Management API and note the exact SQL/endpoint used in your report.

Hard rules (from the campaign brief in CLAUDE.md -- follow exactly):
- You own ONLY your assigned county. Never touch another county's rows, and never run public.gold_standard_loop()
  or gold_standard_certify() (other shards may be mid-session).
- PropertyOnion is litmus/comparison ONLY -- never write po_* derived values in as if they were verified/independent,
  never set parity_status/parity_source to a 'tier1%' label without a real independent second source.
- Fail-loud invariant: if a fix attempt finds zero real data, report it as a blocked/residual gap. NEVER fabricate
  case numbers, parcel IDs, sale amounts, or timestamps to make a metric look better. This campaign has a documented
  history of exactly this failure mode (hardee HARDEE-FC-SEED rows, gulf's purged "clerk proxy records") -- do not
  repeat it in any form, including "close enough" placeholder values. Ghost-success (a letter passing because of a
  fabricated/placeholder value) is worse than an honest FAIL.
- Every claim you return must be tagged VERIFIED (you ran the query/request and are pasting real output), UNTESTED,
  or INFERRED (say why).
- Before finishing: call pencil_dod_evaluate_county for your county and paste the FULL before and after JSON
  verbatim. If a letter did not move, say so plainly -- do not spin it.
- git commit any file you create/modify with a clear, county-scoped message, 'git pull --rebase origin main' before
  pushing (other shards push concurrently to shared paths). Push directly to main -- no branches, no PRs.
- Budget yourself: this is ONE bounded pass, not a 6-hour campaign. If the true fix requires building a brand-new
  scraper from scratch, do NOT build it in this pass -- size the gap precisely, report it as a scoped-out residual
  with what a future session needs, and ship whatever smaller, real, verifiable improvement IS achievable via
  SQL/REST + targeted live lookups (data backfill, wiring an existing-but-unrun pipeline, honesty corrections).

Return a structured report: { county, letters_touched: [...], fix_summary, sql_or_endpoints_used: [...],
before_json, after_json, residual_gaps: [...], honesty_notes: [...] }.
`

phase('Diagnose+Fix')
const fixResults = await pipeline(
  COUNTIES,
  (county) => agent(
    `You are working GOLD STANDARD CAMPAIGN shard-7 (dispatch f4e7f681-ebf0-4732-af8c-ae2ace00840b), county "${county.slug}" ONLY, inside the cli-anything-biddeed repo (already checked out, on main). This is a live production Supabase project (mocerqjnksmhcjzxrewo) feeding a real foreclosure/tax-deed deal-sourcing business (BidDeed.AI). Real money decisions are made from this data -- accuracy over speed, and BLANK > WRONG on every claim.\n\n${county.context}\n\n${RECIPE}`,
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
    `"total" auction count match what you independently query?), (b) ghost-success (any letter now passing because ` +
    `of a placeholder/fabricated value rather than a real fix -- this campaign has a documented history of exactly ` +
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
