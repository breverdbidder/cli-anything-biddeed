export const meta = {
  name: 'gold-standard-shard3-bay-run3713',
  description: 'Gold Standard shard-3 (bay): fix G (zoning FAR/density coverage) and I (property card completeness) via real ordinance + GIS research, apply, adversarially verify',
  phases: [
    { title: 'Research', detail: 'parallel: PC MU-1/RLD-1, PCB CH/R/R-1c, Callaway R-6/R-6M, GIS point lookups' },
    { title: 'Apply', detail: 'single agent: migration SQL + live writes + re-evaluate' },
    { title: 'Verify', detail: 'independent refuter re-checks live DB' },
  ],
}

const DISPATCH_ID = 'ef2bce50-7c8f-4df0-b9d9-b7f8b1a83ed8'
const COUNTY = 'bay'

const BASELINE = `VERIFIED live via pencil_dod_evaluate_county('bay') at session start:
{"A":{"pass":true,"metric":50},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":100},"D":{"pass":true,"metric":100},
"E":{"pass":true,"metric":96.6,"detail":"parcel_linked=114"},"F":{"pass":true,"metric":100},
"G":{"pass":false,"metric":0,"detail":"density=90.0 far=46.7 pk1000=0.0"},"H":{"pass":true,"metric":0.4},
"I":{"pass":false,"metric":92.4,"detail":"card_complete=109 of 118"},"J":{"pass":true,"metric":100},"auctions_total":118}
Only G and I fail. 8/10 today.

G ROOT CAUSE (VERIFIED via v_zoning_gold_standard_kpi_v3 + a manual per-district breakdown query, do not re-derive,
build on this): v_zoning_gold_standard_kpi_v3.pct_pk1000_of_applicable=0.0 is caused ENTIRELY by 8 parcel_zones rows
whose zone_code has NO matching row in zoning_districts for their jurisdiction (a LEFT JOIN miss), which makes
v_zoning_district_applicability return NULL for them, and the kpi view's COALESCE(a.pk1000_applicable, true)
defaults a NULL applicability to TRUE -- i.e. these 8 "orphan" parcels are the ONLY parcels in bay counted as
pk1000-applicable at all (every other, already-matched, bay zoning_districts row has pk1000_applicable hardcoded
false by v_zoning_district_applicability's definition: "false AS pk1000_applicable" unconditionally). Practical
consequence: resolving these 8 orphans into real zoning_districts rows will make pk1000_applicable_parcels drop to
0 county-wide, pct_pk1000_of_applicable become NULL, and Postgres LEAST() IGNORES NULL args (LEAST only returns
NULL if ALL args are NULL) -- so G's metric becomes MIN(density%, far%) only, no longer gated by pk1000 at all.
This is THE highest-leverage fix. The 8 orphan parcel_zones rows (VERIFIED via direct query):
  jurisdiction 884 Panama City: zone_code "MU 1" (note the space, not a dash) -- parcel_ids 16582-000-000, 28388-000-000
  jurisdiction 907 Panama City Beach: zone_code "CH" -- parcel_ids 34994-682-000, 38229-000-000, 40000-300-031
  jurisdiction 907 Panama City Beach: zone_code "R" -- parcel_id 32823-000-000
  jurisdiction 907 Panama City Beach: zone_code "R-1c" -- parcel_ids 33885-000-000, 32812-010-000
Resolving these means: EITHER insert a new zoning_districts row (+ zone_standards if you can source real dimensional
values) with code EXACTLY matching the stored zone_code text ("MU 1", "CH", "R", "R-1c") so the join succeeds, OR if
your research determines the stored zone_code is a normalization/typo of an existing bay zoning_districts.code
(e.g. "MU 1" might really mean the same district Panama City calls "MU-2" in an older/inconsistent scrape -- verify
this is NOT the case before assuming it, Panama City's LDC genuinely may have a separate MU-1 district), UPDATE
parcel_zones.zone_code to the canonical code instead of inserting a duplicate district. Do not guess; confirm from
the actual Panama City / Panama City Beach ordinance text which is correct.

Additionally, of bay's 110 density-applicable parcels, 11 are missing max_density_du_acre (this is the remaining
density gap: 90.0% -> need >=95%, i.e. at most 5 of 110 missing after fixes): the 8 orphans above (once resolved,
if their real district has a density value) PLUS 3 already-matched districts sitting at max_density_du_acre=NULL:
  Panama City (884) code "RLD 1" "Residential Low Density-1" -- 1 parcel
  Callaway (983) code "R-6" "single-family residential-zoning regulations" -- 1 parcel (has max_far=40.00 already
    populated, which is suspiciously high for a residential code -- verify this FAR value is even real/correct
    while you're in the Callaway ordinance; do not fix density by inventing a number, and flag if FAR looks wrong,
    but do not touch/revert it unless you can source the correct value -- out of scope if unverifiable, just note it)
  Callaway (983) code "R-6M" "single family residential (mobile homes)" -- 1 parcel (same max_far=40 caveat)
Resolving the 8 orphans (if they turn out to be non-residential/mixed-use with FAR standards) is what closes the
far_applicable gap too: far_applicable_parcels=15, far present for only 7 -- the other 8 are exactly these same
orphan parcels (defaulted far_applicable=true because no district match, same NULL-default mechanism as pk1000).
Once matched to a real district, far_applicable will be computed correctly from that district's actual category
(residential codes in bay are consistently far_applicable=false already, e.g. all the R-1 variants) -- so if "CH",
"R", "R-1c" turn out to be residential-family codes, far_applicable_parcels drops for them too (correctly), which
also helps pct_far_of_applicable cross 95%. If "MU 1" is genuinely mixed-use/commercial, it SHOULD carry a real
max_far value if the ordinance publishes one -- source it if possible.

I ROOT CAUSE (VERIFIED via a direct query reproducing the evaluator's exact card_complete boolean, all 9 gap rows
pulled by id): three groups:
  (a) 3 rows with placeholder non-parcel text in parcel_id ("TIMESHARE", "Property Appraiser", "MULTIPLE PARCELS")
      and no address at all -- case 25000412CA, 23001239CA, 25000637CA. These are AJAX-decoder parsing artifacts,
      not real parcel numbers. A prior bay session (scripts/gold_standard_bay_zoning_backfill.py, 2026-07-10)
      already investigated this exact pattern for bay and documented it as out-of-scope without independent
      case-record research. Do NOT fabricate a parcel_id for these. You MAY spend a LIMITED amount of time (one
      lookup each) checking the Bay County Clerk case docket for these 3 case numbers to see if a real property
      description is recoverable; if not, leave as documented residual.
  (b) 1 row with NOTHING -- case 25000874CA, parcel_id/address/geo/value all NULL. Same prior session documented
      this exact case as having nothing in source data. Leave as residual unless you find something genuinely new.
  (c) 2 rows with a REAL parcel_id and full address/geo/value already, but NOT zone-linked -- parcel_ids
      09647-000-000 (case 25001221CA) and 10024-000-000 (case 25000985CA). The prior session's docstring claims
      Bay County's own zoning GIS layer (gis.baycountyfl.gov Land_Use_Planning/MapServer/1) returns "See FLU" (no
      usable ZONING attribute) for both, confirmed via direct parcel-number lookup against TEST_Parcels too. VERIFY
      THIS FRESH (GIS data can change) rather than trust the old finding -- if the zoning layer now returns a real
      code for either, insert the parcel_zones row (jurisdiction likely "Unincorporated Bay County" id=1332 or
      "Lynn Haven" id=873 given the addresses are in Lynn Haven -- verify from the GIS response, not the mailing
      city). If still "See FLU"/null, this stays a genuine, documented residual -- do not fabricate a zone code.
  (d) 3 rows that are NEW since the prior bay session (auctions_total grew) -- have full address+geo+value+lat/lon
      already in multi_county_auctions, but parcel_id IS NULL and consequently zone-unlinked. THIS IS THE REAL,
      ACHIEVABLE WIN for I -- these all have usable lat/lon already, so a point-in-polygon GIS query (no address
      matching needed) against both gis.baycountyfl.gov TEST_Parcels (MapServer, for parcel_id/PARCELNO) and
      Land_Use_Planning/MapServer/1 (for zone code) at that exact lat/lon should resolve both parcel_id and
      zone_code directly:
        26000195CA -- "4321 BRANNON RD, PANAMA CITY, FL 32404" -- lat 30.226522495599, lon -85.592765508811
        25000943CA -- "810 N HARRIS AVE, PANAMA CITY, FL 32401" -- lat 30.166397783762, lon -85.643893336042
        25000934CA -- "2817 LONGLEAF ROAD, PANAMA CITY, FL 32405" -- lat 30.198293387105, lon -85.69586127883
      NOTE: "PANAMA CITY" as the mailing city does NOT necessarily mean inside Panama City's incorporated limits --
      confirm the true jurisdiction from the GIS response/boundary, do not assume jurisdiction_id=884.
  Doing the math: 118 total, need >=95% i.e. >=113 of 118 card_complete (112/118=94.9% still fails on rounding).
  Currently 109. Fixing ONLY group (d) [3 rows] gets to 112/118=94.9% -- STILL FAILS. You need at least ONE more
  from group (c) [the "See FLU" recheck] to reach 113/118=95.8% and pass. Prioritize accordingly: do group (d)
  first (highest confidence), then group (c) recheck, then attempt (a)/(b) only if time remains.`

const TOOLS = `
Environment (already available, no credentials needed):
- Live arbitrary SQL: POST https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query
  headers Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json, body {"query": "<sql>"}.
  Build the JSON body with a real encoder (python3 -c "import json..." to a temp file, then curl --data-binary
  @file) -- do not hand-quote SQL containing single quotes into a shell -d string, it breaks.
- REST reads/writes: ${'${SUPABASE_URL}'}/rest/v1/<table> with headers apikey/Authorization: Bearer
  $SUPABASE_SERVICE_ROLE_KEY.
- pencil_dod_evaluate_county RPC (your before/after proof): POST ${'${SUPABASE_URL}'}/rest/v1/rpc/pencil_dod_evaluate_county
  body {"p_county": "bay"}.
- Bay County GIS (public, unauthenticated, verified live 2026-07-10):
  Zoning: https://gis.baycountyfl.gov/arcgis/rest/services/Land_Use_Planning/MapServer/1/query
  Parcels: https://gis.baycountyfl.gov/arcgis/rest/services/TEST_Parcels/MapServer/1/query
  Point query pattern: ?f=json&geometry={lon},{lat}&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=*&returnGeometry=false
  Read scripts/gold_standard_bay_zoning_backfill.py first -- it documents field names and prior findings, do not
  re-derive from scratch.
- Ordinance research: Panama City LDC and Panama City Beach UDC and Callaway LDC are on library.municode.com
  (library.municode.com/fl/panama_city, /fl/panama_city_beach, /fl/callaway) -- these are JS-rendered Municode
  sites, web_fetch/plain HTTP GET will NOT render them; use the firecrawl-scrape skill or WebFetch (which may
  render JS) -- try WebFetch first, fall back to firecrawl-scrape if content comes back empty/app-shell-only.
  If Municode fails, try a direct web search for "panama city beach unified development code zoning districts CH R
  R-1c" or similar, and Callaway's ordinances may be on amlegal.com instead of municode -- check both.
- Repo root is cwd, on main. Write your migration to
  supabase/migrations/20260711_gold_standard_shard3_bay_g_i_zoning_parcel_backfill.sql (schema changes/inserts) --
  still write this file for the historical record even though you apply directly via the Management API.
- gh CLI is authenticated for git commit/push (repo, workflow scopes). Push directly to main, no branches/PRs.

ULTRALOOP audit logging (mandatory): for every letter you claim moved (or claim verified-still-blocked), INSERT one
row into public.gold_standard_ultraloop_audit: dispatch_id (uuid '${DISPATCH_ID}'), ultraloop_mode ('fallback' --
this session used manual Task subagent fan-out via the Workflow tool, not native /effort ultracode toggle),
county_slug ('bay'), letter, claim (short text), refuter_evidence (jsonb -- your before/after evidence or
refutation attempt), survived (boolean). POST ${'${SUPABASE_URL}'}/rest/v1/gold_standard_ultraloop_audit with the
service-role headers above.

Hard rules:
- You own ONLY bay. Never touch another county's rows.
- Fail-loud, BLANK > WRONG: if you can't source a real value, leave it NULL and say so. NEVER fabricate a zone
  code, parcel_id, dimensional standard, or coordinate to make a metric look better. This campaign has a
  documented history of exactly this failure mode (gulf B/F fabrication, purged) -- do not repeat it.
- Every claim must be tagged VERIFIED (you ran the query/request, pasting real output), UNTESTED, or INFERRED
  (say why).
- Schema/data changes go through a migration file AND are applied live via the Management API in the same session
  (files-only = not shipped, per the campaign's SHIP GATE).
- Do NOT run public.gold_standard_loop() or gold_standard_certify() -- other shards may be mid-session. Do NOT
  modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job.
- PropertyOnion is litmus/comparison ONLY -- never write po_*-derived values in as verified/independent.`

phase('Research')
const [pcResult, pcbResult, callawayResult, gisResult] = await parallel([
  () => agent(
    `Research Panama City, Florida's Land Development Code zoning district "MU 1" / "MU-1" (Mixed Use) and confirm ` +
    `whether it is a genuinely distinct district from the existing "MU-2"/"MU-3" already in our zoning_districts table ` +
    `(jurisdiction_id=884), or a normalization variant of one of those. Also source the real max_density_du_acre for ` +
    `Panama City's "RLD 1" (Residential Low Density-1) district if the ordinance publishes a number. Every value you ` +
    `report must carry a source_url and ordinance/section citation, or be explicitly reported as not found -- do not ` +
    `guess.\n\n${BASELINE}\n\n${TOOLS}\n\nYou are RESEARCH-ONLY in this call: do NOT write to the database yet, just ` +
    `gather and report real, citable findings. Return your findings in the schema.`,
    {
      label: 'research:panama_city_mu1_rld1',
      phase: 'Research',
      schema: {
        type: 'object',
        properties: {
          mu1_is_distinct_district: { type: ['boolean', 'null'] },
          mu1_findings: { type: 'string' },
          mu1_category: { type: ['string', 'null'] },
          mu1_max_density_du_acre: { type: ['number', 'null'] },
          mu1_max_far: { type: ['number', 'null'] },
          mu1_source_url: { type: ['string', 'null'] },
          mu1_source_section: { type: ['string', 'null'] },
          rld1_max_density_du_acre: { type: ['number', 'null'] },
          rld1_source_url: { type: ['string', 'null'] },
          rld1_source_section: { type: ['string', 'null'] },
          confidence_tag: { type: 'string', enum: ['VERIFIED', 'UNTESTED', 'INFERRED', 'NOT_FOUND'] },
          notes: { type: 'string' },
        },
        required: ['mu1_findings', 'confidence_tag', 'notes'],
      },
    }
  ),
  () => agent(
    `Research Panama City Beach, Florida's Unified Development Code / zoning ordinance districts coded "CH", "R", ` +
    `and "R-1c" (these exact short codes are stored in our parcel_zones table for real PCB parcels but we only have ` +
    `PCB's "R-1" district in our zoning_districts table today -- CH/R/R-1c are unmatched). Identify what each code ` +
    `actually stands for (e.g. Coastal High Hazard, Resort, a Residential-1 variant), its category ` +
    `(residential/commercial/mixed-use/etc), and any published dimensional standards (density du/acre, FAR, height, ` +
    `setbacks) with source_url + section citation for each of the 3 codes independently. If PCB's zoning code list ` +
    `does not confirm one of these codes exists as a formal zoning district (e.g. it might be a Future Land Use ` +
    `code, not a zoning code), report that explicitly -- do not force-fit it.\n\n${BASELINE}\n\n${TOOLS}\n\n` +
    `RESEARCH-ONLY in this call, do not write to the database. Return findings in the schema.`,
    {
      label: 'research:pcb_ch_r_r1c',
      phase: 'Research',
      schema: {
        type: 'object',
        properties: {
          codes: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                code: { type: 'string' },
                real_meaning: { type: 'string' },
                category: { type: ['string', 'null'] },
                is_formal_zoning_district: { type: ['boolean', 'null'] },
                max_density_du_acre: { type: ['number', 'null'] },
                max_far: { type: ['number', 'null'] },
                source_url: { type: ['string', 'null'] },
                source_section: { type: ['string', 'null'] },
                confidence_tag: { type: 'string', enum: ['VERIFIED', 'UNTESTED', 'INFERRED', 'NOT_FOUND'] },
              },
              required: ['code', 'real_meaning', 'confidence_tag'],
            },
          },
          notes: { type: 'string' },
        },
        required: ['codes', 'notes'],
      },
    }
  ),
  () => agent(
    `Research Callaway, Florida's Land Development Code (try library.municode.com/fl/callaway, fall back to ` +
    `amlegal.com or a direct web search if municode doesn't have it) for zoning districts "R-6" and "R-6M". We ` +
    `already have both in our zoning_districts table with max_far=40.00 (which looks suspicious/possibly wrong for ` +
    `a residential code -- verify it, but do NOT change it unless you can source the correct real value; if you ` +
    `can't verify it either way, just flag it as unverified, do not touch it) but max_density_du_acre is NULL for ` +
    `both. Source the real max_density_du_acre for R-6 (single-family residential) and R-6M (single-family/mobile ` +
    `home residential) with citation.\n\n${BASELINE}\n\n${TOOLS}\n\nRESEARCH-ONLY, do not write to the database. ` +
    `Return findings in the schema.`,
    {
      label: 'research:callaway_r6_r6m',
      phase: 'Research',
      schema: {
        type: 'object',
        properties: {
          r6_max_density_du_acre: { type: ['number', 'null'] },
          r6_source_url: { type: ['string', 'null'] },
          r6_source_section: { type: ['string', 'null'] },
          r6m_max_density_du_acre: { type: ['number', 'null'] },
          r6m_source_url: { type: ['string', 'null'] },
          r6m_source_section: { type: ['string', 'null'] },
          far_40_verdict: { type: 'string', description: 'is the existing max_far=40 plausible/correct/wrong/unverifiable' },
          confidence_tag: { type: 'string', enum: ['VERIFIED', 'UNTESTED', 'INFERRED', 'NOT_FOUND'] },
          notes: { type: 'string' },
        },
        required: ['far_40_verdict', 'confidence_tag', 'notes'],
      },
    }
  ),
  () => agent(
    `Run live GIS point queries against Bay County's public ArcGIS REST services for 3 specific coordinates and ` +
    `also re-verify a prior finding for 2 specific parcel numbers. Read scripts/gold_standard_bay_zoning_backfill.py ` +
    `FIRST for field names/query patterns already proven to work.\n\n` +
    `TASK 1 -- point lookups (parcel_id + zone via TEST_Parcels and Land_Use_Planning/MapServer/1) at:\n` +
    `  case 26000195CA: lat=30.226522495599, lon=-85.592765508811 ("4321 BRANNON RD, PANAMA CITY")\n` +
    `  case 25000943CA: lat=30.166397783762, lon=-85.643893336042 ("810 N HARRIS AVE, PANAMA CITY")\n` +
    `  case 25000934CA: lat=30.198293387105, lon=-85.69586127883 ("2817 LONGLEAF ROAD, PANAMA CITY")\n` +
    `For each, get the real parcel_id/PARCELNO and the real zone code, AND determine the true jurisdiction (do not ` +
    `assume "Panama City" from the mailing address -- check whichever jurisdiction/boundary field the GIS response ` +
    `gives, or reverse it against our jurisdictions table: Panama City=884, Panama City Beach=907, Callaway=983, ` +
    `Lynn Haven=873, Mexico Beach=985, Springfield=984, Unincorporated Bay County=1332).\n\n` +
    `TASK 2 -- re-verify FRESH (do not trust the old finding, GIS data can change) whether ` +
    `gis.baycountyfl.gov's zoning layer now returns a usable zone code (vs "See FLU"/null) for parcel_id ` +
    `09647-000-000 (case 25001221CA, 709 E 8TH ST, LYNN HAVEN) and 10024-000-000 (case 25000985CA, 1213 MICHIGAN ` +
    `AVE, LYNN HAVEN). If a real code appears now, get it and its jurisdiction.\n\n${BASELINE}\n\n${TOOLS}\n\n` +
    `RESEARCH-ONLY, do not write to the database yet -- just query GIS and report exactly what came back (paste raw ` +
    `field values, tag VERIFIED). Return findings in the schema.`,
    {
      label: 'research:gis_point_lookups',
      phase: 'Research',
      schema: {
        type: 'object',
        properties: {
          point_lookups: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                case_number: { type: 'string' },
                parcel_id_found: { type: ['string', 'null'] },
                zone_code_found: { type: ['string', 'null'] },
                jurisdiction_name: { type: ['string', 'null'] },
                jurisdiction_id: { type: ['number', 'null'] },
                confidence_tag: { type: 'string', enum: ['VERIFIED', 'UNTESTED', 'INFERRED', 'NOT_FOUND'] },
              },
              required: ['case_number', 'confidence_tag'],
            },
          },
          see_flu_recheck: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                parcel_id: { type: 'string' },
                still_see_flu: { type: ['boolean', 'null'] },
                zone_code_if_found: { type: ['string', 'null'] },
                jurisdiction_id: { type: ['number', 'null'] },
              },
              required: ['parcel_id'],
            },
          },
          notes: { type: 'string' },
        },
        required: ['point_lookups', 'see_flu_recheck', 'notes'],
      },
    }
  ),
])

phase('Apply')
const applyResult = await agent(
  `You are applying the Gold Standard shard-3 fix for bay county (G and I letters), based on FOUR independent ` +
  `research findings from parallel subagents (below). You did NOT do the research yourself -- read it carefully, ` +
  `and where a research finding is NOT_FOUND/low-confidence, do NOT invent a value to fill the gap; treat it as a ` +
  `documented residual instead.\n\n${BASELINE}\n\n` +
  `RESEARCH FINDING 1 (Panama City MU-1 / RLD-1): ${JSON.stringify(pcResult)}\n\n` +
  `RESEARCH FINDING 2 (Panama City Beach CH/R/R-1c): ${JSON.stringify(pcbResult)}\n\n` +
  `RESEARCH FINDING 3 (Callaway R-6/R-6M): ${JSON.stringify(callawayResult)}\n\n` +
  `RESEARCH FINDING 4 (GIS point lookups + See-FLU recheck): ${JSON.stringify(gisResult)}\n\n${TOOLS}\n\n` +
  `Your job:\n` +
  `1. For each researched code with a real, cited value: INSERT into zoning_districts (jurisdiction_id, code EXACTLY ` +
  `   matching what's stored in parcel_zones.zone_code, name, category, far_regulated, density_regulated as ` +
  `   appropriate) and zone_standards (max_density_du_acre, max_far, source_url, ordinance_section) as your research ` +
  `   supports -- set far_regulated/density_regulated explicitly (true/false) based on your research rather than ` +
  `   leaving them to the view's category-guessing fallback, when you have real evidence either way.\n` +
  `2. For the GIS point-lookup results: UPDATE multi_county_auctions.parcel_id for the 3 NULL-parcel_id rows if a ` +
  `   real parcel_id was found, and INSERT a parcel_zones row (jurisdiction_id, parcel_id, zone_code) for each so ` +
  `   they become zone-linked -- and if their zone_code needs a NEW zoning_districts row too (not covered by finding ` +
  `   1-3), create it the same way, with real data only.\n` +
  `3. For the See-FLU recheck: if a real zone code now exists for 09647-000-000 / 10024-000-000, insert their ` +
  `   parcel_zones rows too (they likely already have SOME parcel_zones row given E passes and I already partially ` +
  `   counts them -- check first with a SELECT, UPDATE if a row exists with a null/placeholder zone_code, INSERT if ` +
  `   none exists).\n` +
  `4. Write supabase/migrations/20260711_gold_standard_shard3_bay_g_i_zoning_parcel_backfill.sql capturing every ` +
  `   INSERT/UPDATE you actually ran (for the historical record), and apply everything live via the Management API ` +
  `   in this same session (files-only is not shipped).\n` +
  `5. Re-run pencil_dod_evaluate_county('bay') and paste the fresh JSON. Report exactly which of G/I moved and by ` +
  `   how much, and precisely which of the 9 I-gap rows / which zoning gaps remain as residuals with reasons.\n` +
  `6. Insert your ultraloop_audit rows (letters G and I, your own before/after as refuter_evidence, survived=true ` +
  `   only if YOU independently believe the claim holds -- the separate Verify phase will adversarially re-check ` +
  `   you, this is just your own self-assessment).\n` +
  `7. git add + commit (message scoped to gold-standard-shard3-bay) + git pull --rebase origin main + git push to ` +
  `   main directly. No branches, no PRs.\n\n` +
  `Return your report in the schema.`,
  {
    label: 'apply:bay',
    phase: 'Apply',
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
        migration_file: { type: 'string' },
        git_pushed: { type: 'boolean' },
      },
      required: ['county', 'fix_summary', 'before_json', 'after_json'],
    },
  }
)

phase('Verify')
const verifyResult = await agent(
  `Independently, adversarially verify this claimed Gold Standard fix for bay county (G and I letters). You did ` +
  `NOT write this fix -- be skeptical. Your #1 job is to catch ghost-success: e.g. a pk1000 dimension that now ` +
  `"passes" only because its denominator became vacuous (0 applicable parcels -> NULL -> ignored by LEAST()) is a ` +
  `LEGITIMATE structural fix (documented in this county's baseline as the expected mechanism) and should NOT be ` +
  `flagged as ghost-success by itself -- but you MUST verify the underlying zoning_districts/zone_standards rows ` +
  `that were inserted are REAL (have a real source_url/ordinance_section, not fabricated placeholder text), and ` +
  `that no residential district was mis-marked far_applicable=false or density N/A just to dodge the denominator ` +
  `without ordinance support.\n\n` +
  `Claimed result: ${JSON.stringify(applyResult)}\n\n${BASELINE}\n\n${TOOLS}\n\n` +
  `Do this: (1) re-run pencil_dod_evaluate_county('bay') yourself RIGHT NOW, fresh, do not trust the pasted ` +
  `after_json. (2) spot-check at least 2 of the newly-inserted zoning_districts/zone_standards rows by fetching ` +
  `their source_url yourself and confirming the cited value actually appears in the ordinance text (or GIS response ` +
  `for GIS-sourced parcel_zones rows). (3) check whether E, C, D, or any other previously-passing letter regressed ` +
  `as a side effect (they should NOT have -- this session should only touch G/I-relevant tables, but new ` +
  `zoning_districts rows could theoretically shift E's parcel-linkage logic if it depends on jurisdiction/zone ` +
  `matching too, verify it did not). (4) confirm no fabricated parcel_id, zone_code, or coordinate was written -- ` +
  `every new value must trace to a real GIS/ordinance response. Also INSERT your own gold_standard_ultraloop_audit ` +
  `rows for letters G and I (ultraloop_mode='fallback', your refutation evidence, survived=your independent ` +
  `verdict). Return { county, refuted, refutation_reason, fresh_evaluation, survives } in the schema.`,
  {
    label: 'verify:bay',
    phase: 'Verify',
    schema: {
      type: 'object',
      properties: {
        county: { type: 'string' },
        refuted: { type: 'boolean' },
        refutation_reason: { type: ['string', 'null'] },
        fresh_evaluation: {},
        survives: { type: 'boolean' },
        spot_checks: { type: 'array', items: { type: 'string' } },
      },
      required: ['county', 'refuted', 'fresh_evaluation', 'survives'],
    },
  }
)

return { research: { pcResult, pcbResult, callawayResult, gisResult }, applyResult, verifyResult }
