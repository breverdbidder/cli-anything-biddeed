export const meta = {
  name: 'gold-standard-shard11-run3645',
  description: 'GOLD STANDARD shard11 (bay/leon/hendry/hardee): fix failing letters live, then adversarially verify each claimed improvement',
  phases: [
    { title: 'Fix' },
    { title: 'Verify' },
  ],
}

const DB_ACCESS = `
DB ACCESS (verified working in this session):
- REST (PostgREST) reads/writes: base URL $SUPABASE_URL/rest/v1/<table>, headers "apikey: $SUPABASE_SERVICE_ROLE_KEY" and "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY". GET with query params, PATCH/POST with Content-Type: application/json and "Prefer: return=representation" or "resolution=merge-duplicates,return=minimal" for upserts.
- Raw SQL / DDL / migrations: Supabase Management API. POST to https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query with header "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" and JSON body {"query":"<sql>"}. Verified live with curl (works). NOTE: a plain python urllib.request call to this same endpoint returned 403 in this session for unknown reasons -- use curl, not urllib, for the Management API. Example:
  curl -s -X POST "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query" -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" -H "Content-Type: application/json" -d '{"query":"SELECT 1"}'
- Direct psql / psycopg2 pooler connections: CONFIRMED BROKEN this session (SUPABASE_DB_PASSWORD auth fails on every host/port/user combination tried: aws-0-us-east-1/us-west-2 pooler on 5432/6543, db.mocerqjnksmhcjzxrewo.supabase.co:5432). Do not waste time on psql/psycopg2 -- use the Management API for SQL and REST for row-level CRUD.
- Evaluator: SELECT public.pencil_dod_evaluate_county('<county>') via REST RPC (POST $SUPABASE_URL/rest/v1/rpc/pencil_dod_evaluate_county with body {"p_county":"<county>"}) is the canonical live scoreboard. Always call this BEFORE your first change and AFTER your last change for the county, and report BOTH raw JSON blobs verbatim -- never paraphrase or invent numbers (HONESTY PROTOCOL, 3x penalty for wrong VERIFIED claims).
`

const EVALUATOR_LOGIC = `
EVALUATOR CONTRACT (public.pencil_dod_evaluate_county, read the live source with:
  curl -s -X POST "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query" -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" -H "Content-Type: application/json" -d '{"query":"SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname=\\'pencil_dod_evaluate_county\\'"}'
if you need the exact SQL):
- Denominator for A/C/D/E/F/J = multi_county_auctions rows for the county WHERE data_source <> 'propertyonion' OR tier1_authoritative = true.
- C (matched_clean) needs parity_status='matched_clean' AND parity_source LIKE 'tier1%'. D (matched_any) also accepts parity_status='matched_divergent'. NEVER set parity_status/parity_source without a real independent auction-calendar or clerk-record match -- a fabricated 'tier1%' label is a HARD FAIL of canon and will be caught by the verify pass.
- B needs an independent (data_source NOT ILIKE '%promote%') row in tax_deed_outcomes or foreclosure_outcomes with the same case_number, for rows where sold_amount IS NOT NULL. PropertyOnion-derived data_source is a HARD FAIL.
- F needs tier1_sold_amount populated on multi_county_auctions for rows where sold_amount IS NOT NULL.
- I (card_complete) needs, per auction row: property_address NOT NULL AND (latitude/longitude OR po_latitude/po_longitude) NOT NULL AND (assessed_value OR market_value) NOT NULL AND parcel_id resolves (exact match on parcel_id or tax_account) to a row in v_zoning_gold_standard_card for that county with zone_code NOT NULL. v_zoning_gold_standard_card joins parcel_zones -> jurisdictions (for county) -> zoning_districts/zone_standards. A parcel_id format mismatch between multi_county_auctions.parcel_id and parcel_zones.parcel_id is a SEPARATE failure mode from "no zoning data exists" -- check both before concluding a county has no zoning coverage.
- G = LEAST(density,far,pk1000) from v_zoning_gold_standard_kpi_v3, keyed by norm_county_key(county). This view has ONE row per county from parcel_zones/zoning_districts/zone_standards coverage.
- J (deal_complete) needs a bid_decisions row per case_number with arv, max_bid, ml_score all NOT NULL and factors containing keys distress_location, distress_property, distress_owner, cma_distressed, cma_resale.
`

const GUARDRAILS = `
HARD GUARDRAILS (from CLAUDE.md, non-negotiable):
1. PropertyOnion is litmus ONLY -- never write data_source='propertyonion' rows as if they were verified/tier1.
2. Fail-loud: if you parse/harvest >0 items but write 0 rows, RAISE/throw -- never swallow silently.
3. Schema changes only via supabase/migrations/*.sql files (county-scoped filenames, e.g. 20260710_gold_standard_shard11_<county>_<purpose>.sql). Write the file to disk AND execute it live via the Management API in this same session -- a migration file that was never executed is not a fix (SHIP GATE mandate).
4. Do NOT modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job.
5. Do NOT touch any table rows for counties other than your assigned one.
6. Before writing ANY row that would flip a letter from FAIL to PASS, ask: is this a REAL independent source, or am I papering over a gap? If you find existing rows that look like synthetic/placeholder/seed data (fake-looking case numbers, "(synthetic seed)" addresses, SYN- prefixed parcel ids, round suspiciously-clean values with no real source) -- these are almost certainly fabrication left over from a prior bad run (precedent: hardee had exactly this purged in commit 397c3393 "hardee ghost-success permanent fix"). Do NOT build on top of them. Purge them (with a migration) and report the corrected (usually lower) denominator honestly instead. BLANK > WRONG.
7. Every claim you return must be VERIFIED (you ran the query, here's the literal output), never invented.
8. Use "SET statement_timeout = 0;" as the first statement in any heavy SQL you run via the Management API.
9. Do NOT git add/commit/push. Just write files to disk with git-mergeable, county-scoped names and make the live DB writes. The orchestrating session will commit everything in one batch after your work + the verify pass complete.
`

const COUNTY_BRIEFS = {
  bay: `
COUNTY: bay (currently 8/10 -- A,B,C,D,E,F,H,J pass; G and I fail)

G FAIL (metric=3.3, density=71.4 far=3.3 pk1000=0.0):
Prior session (2026-07-10, in pipeline.counties.notes for bay) diagnosed: municode.com 403'd on all 5 Bay jurisdictions (no Firecrawl key that session), and structurally, v_zoning_district_applicability hardcodes pk1000_applicable=false FLEET-WIDE so pk1000 can never reach 95% as currently designed (that part is out of single-county scope -- do not attempt to fix the shared view, just note it). What IS in scope: bay's far/pk1000 sub-metrics are additionally dragged down by ~30 orphan parcel_zones rows whose zone_code does not join to any row in zoning_districts, which defaults them to applicable=true via a COALESCE in the view (so they count against the denominator with no standards). Read v_zoning_district_applicability and v_zoning_gold_standard_kpi_v3 definitions live via the Management API to see the exact COALESCE logic, then: (a) find bay's distinct parcel_zones.zone_code values that have no matching zoning_districts row (join parcel_zones -> jurisdictions where county_name ilike 'bay' or county ilike 'bay', LEFT JOIN zoning_districts on jurisdiction_id+code, WHERE zoning_districts.id IS NULL), (b) for each such code, verify it is a REAL Bay zoning code (cross-check against gis.baycountyfl.gov/arcgis/rest/services/Land_Use_Planning/MapServer/1's legend/domain, or Bay County's published zoning ordinance) and insert a real zoning_districts row + zone_standards row with values sourced from Bay's actual zoning ordinance (municode.com/fl/bay_county or the county's own published zoning table) -- never invent setback/density/FAR numbers. If municode still 403s, try a plain WebFetch/curl on the ordinance PDF/HTML directly, or the county planning department's published zoning table page. If you truly cannot source real standards for a code, leave it and document why -- do not guess.

I FAIL (metric=94.9, card_complete=112 of 118 -- need 113+/118 for PASS):
Exactly 6 rows are incomplete (query below reproduces them). 3 are parser artifacts with garbage parcel_id ("TIMESHARE","Property Appraiser","MULTIPLE PARCELS") from the AJAX calendar decoder for cases 25000412CA, 23001239CA, 25000637CA -- try re-fetching each case's REALFORECLOSE case DETAIL page (index.cfm?zaction=AUCTION&Zmethod=DETAIL or similar -- probe bay.realforeclose.com's detail view for these AIDs) which may carry the real parcel_id where the calendar summary just linked to "Property Appraiser". 1 row (25000874CA) has zero data in our source at all -- low priority, likely not fixable this session, document as genuine gap if so. 2 rows (25001221CA parcel 09647-000-000, 25000985CA parcel 10024-000-000) have full address/geo/value but parcel_id does not resolve to a zoned row -- Bay's own Land_Use_Planning GIS layer explicitly returns no usable ZONING value for these ("See FLU") per the prior session's direct lookup; do not fabricate a zone_code for these two. Fixing just 1 of the 3 parser-artifact rows is enough to cross the 95% threshold (113/118=95.8%).
Diagnostic query for the 6 incomplete rows:
WITH zc AS (SELECT DISTINCT parcel_id, tax_account FROM v_zoning_gold_standard_card WHERE lower(county)=norm_county_key('bay') AND zone_code IS NOT NULL) SELECT case_number, property_address, latitude, po_latitude, longitude, po_longitude, assessed_value, market_value, parcel_id FROM multi_county_auctions a2 WHERE lower(a2.county)='bay' AND (COALESCE(a2.data_source,'')<>'propertyonion' OR COALESCE(a2.tier1_authoritative,false)=true) AND NOT (a2.property_address IS NOT NULL AND COALESCE(a2.latitude,a2.po_latitude::double precision) IS NOT NULL AND COALESCE(a2.longitude,a2.po_longitude::double precision) IS NOT NULL AND COALESCE(a2.assessed_value,a2.market_value) IS NOT NULL AND (a2.parcel_id IN (SELECT parcel_id FROM zc) OR a2.parcel_id IN (SELECT tax_account FROM zc WHERE tax_account IS NOT NULL)));
`,
  leon: `
COUNTY: leon (currently 7/10 -- A,B,E,F,G,H,J pass; C,D,I fail)

C/D FAIL (matched_clean=153, matched_any=153, of 162 -- need 154+/162 for 95%):
Exactly 9 rows have parity_status IS NULL (never harvested/matched): 7 foreclosure-sale-type rows on leon.realforeclose.com for auction dates 2026-07-10, 2026-07-15, 2026-07-20 (x3), 2026-07-22 (x2), and 2 tax_deed-sale-type rows on leon.realtaxdeed.com for auction date 2026-08-19 (case numbers 14-0367, 16-0785 -- note the short case-number format, these may be re-filed/redemption-lane cases, verify they still appear on the live calendar).
REUSE the proven harvester at scripts/shard2_run2450_ajax_realforeclose_harvest.py (harvest_date(subdomain, county_slug, "MM/DD/YYYY", platform_domain="realforeclose.com"|"realtaxdeed.com") -- already handles the AJAX decode, pagination, and cookie/UA WAF workaround) plus the match_and_fix() pattern in scripts/shard14_martin_bay_alachua_lake_cd_e_i_fix.py (exact case_number match -> parity_status='matched_clean', parity_source='tier1:shard11_run3645_ajax_harvest:<sale_type>:<date>'; also backfills parcel_id/property_address/assessed_value on match when those fields are NULL, which contributes to I for the same rows). Write a county-scoped script (e.g. scripts/gold_standard_shard11_leon_cd_i_ajax_harvest.py) adapting these two files for leon's 9 target dates, run it live, and report parsed/matched counts. Fail loud if parsed>0 and matched=0 for a date.

I FAIL (card_complete=146 of 162=90.1%, need 154+/162 for 95%):
After the C/D harvest above lands (which backfills address/value for its 9 rows but NOT lat/lng), re-run the I diagnostic below. There are ~6 additional rows already parity-matched but where parcel_id fails to resolve against v_zoning_gold_standard_card -- leon's parcel_zones table stores PLAIN NUMERIC parcel ids (e.g. "212711000019", "410273") while some multi_county_auctions rows for leon carry Leon Property Appraiser's condo/subdivision-suffix format (e.g. "212662 A0050", "112105 E0012" -- space then letter+digits, a Leon-specific PIN convention for platted units). DO NOT assume a normalization rule and rewrite these -- first verify against the real Leon County Property Appraiser parcel lookup (https://www.leonpa.org or Leon PA's ArcGIS) that a specific transform (e.g. strip the space, or extract only the leading numeric segment) actually resolves to the SAME real parcel as the base parcel_zones entry, for at least 2-3 sample rows, before writing any bulk fix. If you cannot verify a safe transform, leave those rows and document the gap honestly -- do not guess-link parcels (a wrong parcel link is worse than a missing one).
Diagnostic query for incomplete card rows:
WITH zc AS (SELECT DISTINCT parcel_id, tax_account FROM v_zoning_gold_standard_card WHERE lower(county)=norm_county_key('leon') AND zone_code IS NOT NULL) SELECT case_number, property_address IS NOT NULL has_addr, COALESCE(latitude,po_latitude::double precision) IS NOT NULL has_lat, COALESCE(assessed_value,market_value) IS NOT NULL has_val, parcel_id, (parcel_id IN (SELECT parcel_id FROM zc) OR parcel_id IN (SELECT tax_account FROM zc WHERE tax_account IS NOT NULL)) zoned FROM multi_county_auctions a2 WHERE lower(a2.county)='leon' AND (COALESCE(a2.data_source,'')<>'propertyonion' OR COALESCE(a2.tier1_authoritative,false)=true) AND NOT (a2.property_address IS NOT NULL AND COALESCE(a2.latitude,a2.po_latitude::double precision) IS NOT NULL AND COALESCE(a2.longitude,a2.po_longitude::double precision) IS NOT NULL AND COALESCE(a2.assessed_value,a2.market_value) IS NOT NULL AND (a2.parcel_id IN (SELECT parcel_id FROM zc) OR a2.parcel_id IN (SELECT tax_account FROM zc WHERE tax_account IS NOT NULL)));
For rows missing lat/lng specifically, geocode the property_address (free-tier geocoder or the FL GIO / county GIS address-point layer) if time allows -- lower priority than the C/D harvest and the parcel-format investigation.
`,
  hendry: `
COUNTY: hendry (currently 5/10 -- A,E,G,H,J pass; B,C,D,F,I fail)

CRITICAL FIRST STEP -- VERIFY THESE ARE REAL CASES BEFORE TOUCHING THEM:
The two rows driving B/C/D/F failures have case_number "HENDRY-FC-2026-001" and "HENDRY-FC-2026-002" -- this does NOT look like a real Florida circuit court case number format (should resemble "24-CA-000123" or similar clerk-issued format). This is exactly the shape of the synthetic/seed fabrication that was found and purged in hardee (see commit 397c3393 "hardee ghost-success permanent fix" and the shard9 run3497 notes in pipeline.counties for hardee -- rows like HARDEE-FC-SEED-2026 with parcel_id SYN-HRD-*). Before doing ANY work on B/C/D/F for hendry: pull the full row for both HENDRY-FC-2026-001 and HENDRY-FC-2026-002 (all columns, especially data_source, created_at, and any notes/raw_jsonb fields), and independently check whether a real case with a matching address (100 S MAIN ST / 200 S MAIN ST, LABELLE FL 33935) and a real $58,000 sale actually exists via Hendry Clerk of Court records (hendryclerk.org or similar) or the Hendry County Property Appraiser. If you cannot find independent confirmation these are real, they are almost certainly fabricated placeholders -- write a migration that PURGES them (both the multi_county_auctions rows and any linked bid_decisions/tax_deed_outcomes/foreclosure_outcomes rows), which will correctly DROP hendry's denominators (auctions_total 19->17, closed_sold 1->0) rather than paper over a ghost-success. Only if you find genuine independent confirmation should you instead promote them to matched_clean/verified outcomes.

I FAIL (card_complete=5 of 19=26.3%, need 18-19/19 for 95%):
ALL 14 incomplete rows have real Hendry Property Appraiser PIN-format parcel_ids already present (e.g. "1 28 44 07 A00 0203.0000") but resolve zoned=false. Hendry DOES have zoning coverage (21 parcel_zones rows across LaBelle/Clewiston jurisdictions, verified live) -- but parcel_zones stores a DIFFERENT delimiter convention (hyphenated, e.g. "1-28-43-A0-00080-0000.00") than multi_county_auctions (space-separated, e.g. "1 28 44 07 A00 0203.0000"). This LOOKS like a simple space-vs-hyphen normalization but the segment values also differ (28-43 vs 28-44, subdivision/block ordering) -- do NOT assume a blind space->hyphen replace is correct. Verify against the real Hendry County Property Appraiser parcel lookup (qpublic.net/fl/hendry or the county's own GIS) for at least 3 sample parcel_ids from both tables to confirm whether these are actually the SAME underlying parcels in different notations, or genuinely different parcels (in which case hendry's parcel_zones coverage may just be too sparse -- 21 rows total -- to cover most of these 19 auctions, and the honest answer is I stays low this session). Diagnostic query:
WITH zc AS (SELECT DISTINCT parcel_id, tax_account FROM v_zoning_gold_standard_card WHERE lower(county)=norm_county_key('hendry') AND zone_code IS NOT NULL) SELECT case_number, property_address IS NOT NULL has_addr, COALESCE(latitude,po_latitude::double precision) IS NOT NULL has_lat, COALESCE(assessed_value,market_value) IS NOT NULL has_val, parcel_id FROM multi_county_auctions a2 WHERE lower(a2.county)='hendry' AND (COALESCE(a2.data_source,'')<>'propertyonion' OR COALESCE(a2.tier1_authoritative,false)=true) AND NOT (a2.property_address IS NOT NULL AND COALESCE(a2.latitude,a2.po_latitude::double precision) IS NOT NULL AND COALESCE(a2.longitude,a2.po_longitude::double precision) IS NOT NULL AND COALESCE(a2.assessed_value,a2.market_value) IS NOT NULL AND (a2.parcel_id IN (SELECT parcel_id FROM zc) OR a2.parcel_id IN (SELECT tax_account FROM zc WHERE tax_account IS NOT NULL)));
Raw parcel_zones rows for comparison: SELECT pz.parcel_id, pz.zone_code FROM parcel_zones pz JOIN jurisdictions j ON j.id=pz.jurisdiction_id WHERE j.county_name ILIKE '%hendry%';
`,
  hardee: `
COUNTY: hardee (currently 2/10 -- G,H pass; A,B,C,D,E,F,I,J fail)

Tiny scope: exactly ONE auction row exists, case_number 25000327CAAXMX, sale_type foreclosure, auction_status upcoming, auction_date 2026-07-22, data_source='hardee_clerk_direct' (this one IS confirmed real per prior session notes -- sourced from hardeeclerk.com in-person sale listing, NOT a synthetic seed). property_address='1841 State Road 66, Zolfo Springs, FL' but parcel_id/lat/lng/assessed_value/market_value are all NULL.
A is FAIL because tax_deed count=0 (fc=1,td=0) -- Hardee's tax-deed sales are also in-person via hardeeclerk.com/departments/tax-deeds/tax-deed-sales/ (see pipeline.counties.taxdeed_url) but no case has been found/ingested yet. If time allows, fetch that page (WebFetch or curl with a browser UA) and see if a real upcoming/recent tax-deed case can be added -- this is the only way to fix A this session (needs BOTH fc>0 and td>0).
E/I: look up parcel_id via the Hardee County Property Appraiser (hardeepa.com or qpublic.net/fl/hardee) by the address "1841 State Road 66, Zolfo Springs FL" or by searching the site for the case's defendant/property. Once you have a real parcel_id, pull assessed_value and geo coordinates from the same source (or the FL GIO statewide cadastral API as a fallback, CO_NO for Hardee=21) and backfill multi_county_auctions. For I to fully pass you'd also need this parcel to resolve against a hardee row in v_zoning_gold_standard_card -- check whether jurisdictions/parcel_zones has ANY hardee coverage yet (likely not, G shows 100.0/100.0/blank which for a single-parcel county with zero applicable parcels can trivially read as 100% -- verify this is not a hollow pass before relying on it, i.e. check v_zoning_gold_standard_kpi_v3's underlying applicable-parcel counts for hardee are not just 0/0).
C/D: hardee has no RealAuction subdomain (hardee.realforeclose.com/realtaxdeed.com both redirect to the unprovisioned splash page, confirmed dead-end per pipeline.counties notes) so the standard AJAX-harvest litmus does not apply. Per the STANDING AUTHORIZATION for a clerk/official-records supplementary litmus, the only available second source IS hardeeclerk.com itself -- if you can independently re-fetch the live foreclosure-sales listing page and confirm case 25000327CAAXMX is still listed with matching details, that constitutes a genuine two-touch verification and you may set parity_status='matched_clean' with parity_source='tier1_clerk_hardeeclerk_direct_v1' (NOT a PropertyOnion-style single-source label). If you cannot get a second independent touch, leave parity_status alone and document why.
B/F: sold_amount is NULL (auction hasn't happened -- sale date is 2026-07-22, in the future). B/F are structurally not-yet-measurable for this county this session; do not fabricate an outcome. Leave as-is and say so explicitly.
J: once/if you have real parcel_id + assessed_value (from the E/I work above), check whether the existing J generator (bid_decisions pipeline -- county-agnostic per CLAUDE.md, already at 100% for bay/leon/hendry) can be re-run/triggered for this one case now that inputs exist. Look for the generator script (grep scripts/ for "j_generator" or "bid_decisions" INSERT logic) and run it scoped to hardee if feasible. If the generator needs comps/CMA data this tiny rural county doesn't have available, document that honestly rather than forcing a bid_decisions row with placeholder numbers.
`,
}

const FIX_SCHEMA = {
  type: 'object',
  required: ['county', 'before_json', 'after_json', 'actions', 'claims'],
  properties: {
    county: { type: 'string' },
    before_json: { type: 'string', description: 'verbatim JSON output of pencil_dod_evaluate_county before any changes' },
    after_json: { type: 'string', description: 'verbatim JSON output of pencil_dod_evaluate_county after all changes' },
    actions: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          letter: { type: 'string' },
          description: { type: 'string' },
          files_written: { type: 'array', items: { type: 'string' } },
          rows_affected: { type: 'number' },
          evidence_query: { type: 'string', description: 'the exact SQL/REST call used to verify this action, runnable independently' },
        },
      },
    },
    claims: {
      type: 'array',
      description: 'one entry per letter you believe moved or is now passing -- these get independently adversarially verified, do not include letters you did not touch',
      items: {
        type: 'object',
        required: ['letter', 'claim'],
        properties: {
          letter: { type: 'string' },
          claim: { type: 'string', description: 'what changed and why it should now pass/improve, in plain language with numbers' },
        },
      },
    },
    honest_gaps: { type: 'array', items: { type: 'string' }, description: 'letters/rows you could NOT fix, and why -- required for BLANK>WRONG compliance' },
  },
}

const REFUTE_SCHEMA = {
  type: 'object',
  required: ['survived', 'refuter_evidence', 'live_metric_now'],
  properties: {
    survived: { type: 'boolean' },
    refuter_evidence: { type: 'string' },
    live_metric_now: { type: ['number', 'null'] },
  },
}

phase('Fix')
const fixResults = await pipeline(
  ['bay', 'leon', 'hendry', 'hardee'],
  (county) => agent(
    `You are working GOLD STANDARD CAMPAIGN shard11 (dispatch dd396ee4-e383-45ea-8953-5ad92fb1c1af), county="${county}" ONLY. This is a live production Supabase project (mocerqjnksmhcjzxrewo) feeding a real foreclosure/tax-deed deal-sourcing business (BidDeed.AI). Real money decisions are made from this data -- accuracy over speed, and BLANK > WRONG on every claim.\n\n${DB_ACCESS}\n${EVALUATOR_LOGIC}\n${GUARDRAILS}\n${COUNTY_BRIEFS[county]}\n\nSTART by calling pencil_dod_evaluate_county('${county}') and recording the verbatim JSON as before_json. Work through the failing letters in the brief above in priority order (whichever is highest-leverage / most-tractable first). For every change: write the migration/script file to disk (git-mergeable path, do not commit), execute it live via the Management API or REST, then re-verify with a targeted SQL query BEFORE claiming success. When you are done (or have made all the progress you honestly can in this session), call pencil_dod_evaluate_county('${county}') again and record the verbatim JSON as after_json. Return the FIX_SCHEMA structure: before_json, after_json, actions taken (with evidence_query for each so someone else can independently re-check it), claims (one per letter you believe improved), and honest_gaps (letters/rows you could not fix and why). Do not claim a letter passes unless the after_json literally shows pass:true for it.`,
    { phase: 'Fix', label: `fix:${county}`, schema: FIX_SCHEMA }
  ),
  (fixResult, county) => {
    if (!fixResult || !fixResult.claims || fixResult.claims.length === 0) {
      log(`${county}: no claims to verify (fix agent returned nothing or no improvements claimed)`)
      return { county, fixResult, refutations: [] }
    }
    return parallel(fixResult.claims.map((c) => () =>
      agent(
        `You are an adversarial refuter for the GOLD STANDARD CAMPAIGN (shard11, dispatch dd396ee4-e383-45ea-8953-5ad92fb1c1af). Someone else just claimed the following about county="${county}" letter="${c.letter}":\n\nCLAIM: ${c.claim}\n\nYour ONLY job is to try to break this claim. You did NOT do this work and have no stake in it being right.\n${DB_ACCESS}\n${EVALUATOR_LOGIC}\n${GUARDRAILS}\n\nIndependently: (1) call pencil_dod_evaluate_county('${county}') live right now and read the actual current value for letter ${c.letter}. (2) If the claim involves new rows (parity_status, tax_deed_outcomes/foreclosure_outcomes, parcel_zones, zoning_districts, bid_decisions, etc.), query those tables directly and check for: fabrication (data_source suggesting PropertyOnion or 'promote'-derived), ghost-success (values that look invented rather than sourced), denominator mismatches, double-counting, or a parity_source labeled 'tier1%' that isn't backed by a real independent second source. (3) The canonical failure mode this layer exists to catch is an anomalous ratio (e.g. B verified_outcomes > closed_sold like brevard's historical 134% bug) or a fabricated match -- actively look for these. Default to survived=false if you are not confident the claim is real and verifiable RIGHT NOW from live data. Return REFUTE_SCHEMA: survived (true only if the claim holds up under your independent check), refuter_evidence (what you actually queried and saw), live_metric_now (the current numeric metric value for this letter from your own fresh pencil_dod_evaluate_county call, or null if not applicable e.g. for a row-count claim).`,
        { phase: 'Verify', label: `verify:${county}:${c.letter}`, schema: REFUTE_SCHEMA }
      ).then((v) => ({ letter: c.letter, claim: c.claim, verdict: v }))
    )).then((refutations) => ({ county, fixResult, refutations: refutations.filter(Boolean) }))
  }
)

return fixResults
