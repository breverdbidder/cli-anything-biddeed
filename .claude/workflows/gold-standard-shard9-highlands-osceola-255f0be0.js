export const meta = {
  name: 'gold-standard-shard9-highlands-osceola-255f0be0',
  description: 'Gold Standard shard-9 (highlands+osceola, dispatch 255f0be0): research-fix-verify for osceola I/G and highlands I via real GIS/ordinance sources, ULTRALOOP adversarial verify',
  phases: [
    { title: 'Research' },
    { title: 'Fix' },
    { title: 'Verify' },
  ],
}

const DISPATCH_ID = '255f0be0-1ba1-4263-8e19-885e00df6958'

const RESEARCH_SCHEMA_OI = {
  type: 'object',
  properties: {
    parcels: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          case_number: { type: 'string' },
          parcel_id: { type: 'string' },
          found: { type: 'boolean' },
          site_address: { type: ['string', 'null'] },
          assessed_value: { type: ['number', 'null'] },
          just_value: { type: ['number', 'null'] },
          latitude: { type: ['number', 'null'] },
          longitude: { type: ['number', 'null'] },
          source_url: { type: ['string', 'null'] },
          confidence: { type: 'string', enum: ['VERIFIED', 'INFERRED', 'UNKNOWN'] },
          notes: { type: 'string' },
        },
        required: ['case_number', 'parcel_id', 'found', 'confidence', 'notes'],
      },
    },
  },
  required: ['parcels'],
}

const RESEARCH_SCHEMA_G = {
  type: 'object',
  properties: {
    zones: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          jurisdiction: { type: 'string' },
          jurisdiction_id: { type: 'number' },
          zone_code: { type: 'string' },
          zone_name: { type: ['string', 'null'] },
          category: { type: 'string', enum: ['residential', 'commercial', 'industrial', 'mixed-use', 'agricultural', 'other'] },
          max_far: { type: ['number', 'null'] },
          far_applicable: { type: 'boolean' },
          parking_per_1000sf: { type: ['number', 'null'] },
          pk1000_applicable: { type: 'boolean' },
          max_density_du_acre: { type: ['number', 'null'] },
          density_applicable: { type: 'boolean' },
          ordinance_section: { type: ['string', 'null'] },
          source_url: { type: ['string', 'null'] },
          confidence: { type: 'string', enum: ['VERIFIED', 'INFERRED', 'UNKNOWN'] },
          notes: { type: 'string' },
        },
        required: ['jurisdiction', 'zone_code', 'category', 'far_applicable', 'pk1000_applicable', 'density_applicable', 'confidence', 'notes'],
      },
    },
  },
  required: ['zones'],
}

const RESEARCH_SCHEMA_HI = {
  type: 'object',
  properties: {
    gis_source_found: { type: 'boolean' },
    gis_source_url: { type: ['string', 'null'] },
    gis_source_notes: { type: 'string' },
    parcels: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          case_number: { type: 'string' },
          parcel_id: { type: 'string' },
          jurisdiction: { type: 'string', enum: ['sebring', 'lake_placid', 'avon_park', 'unincorporated_highlands', 'unknown'] },
          zone_code: { type: ['string', 'null'] },
          zone_name: { type: ['string', 'null'] },
          source_url: { type: ['string', 'null'] },
          confidence: { type: 'string', enum: ['VERIFIED', 'INFERRED', 'UNKNOWN'] },
          notes: { type: 'string' },
        },
        required: ['case_number', 'parcel_id', 'jurisdiction', 'confidence', 'notes'],
      },
    },
  },
  required: ['gis_source_found', 'parcels'],
}

const FIX_SCHEMA = {
  type: 'object',
  properties: {
    tables_written: { type: 'array', items: { type: 'object', properties: { table: { type: 'string' }, rows_inserted: { type: 'number' }, rows_updated: { type: 'number' } }, required: ['table', 'rows_inserted', 'rows_updated'] } },
    skipped_no_real_data: { type: 'number' },
    skipped_case_numbers: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
  required: ['tables_written', 'skipped_no_real_data', 'summary'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    letter: { type: 'string' },
    county_slug: { type: 'string' },
    metric_before: { type: 'number' },
    metric_after: { type: 'number' },
    pass_after: { type: 'boolean' },
    anomaly_detected: { type: 'boolean' },
    sources_spot_checked: { type: 'number' },
    sources_confirmed_real: { type: 'number' },
    fabrication_suspected: { type: 'boolean' },
    survived: { type: 'boolean' },
    reasoning: { type: 'string' },
  },
  required: ['letter', 'county_slug', 'metric_before', 'metric_after', 'pass_after', 'anomaly_detected', 'survived', 'reasoning'],
}

phase('Research')

const osceolaIResearch = agent(`
You are researching REAL property data for 14 specific auction rows in Osceola County, Florida, to fill gaps in a property-card-completeness gold-standard criterion. DO NOT FABRICATE any value. If you cannot find a real value from a real source, mark found=false and confidence="UNKNOWN" for that field/row rather than guessing.

Context: multi_county_auctions has 13 rows with a real 12-digit Osceola County Property Appraiser parcel STRAP (format like "202529183000") but only a placeholder address "Osceola County, FL 34741" and no assessed_value/market_value/latitude/longitude. One additional row (case_number "2025 CA 001721 MF") has a synthetic internal parcel_id "OSC-2CEAE2B1037A" and NO real address at all — try to find the real property via a Osceola Clerk of Court case docket search for that case number, which should reveal a real property address/legal description; if you cannot find it, report found=false, confidence="UNKNOWN".

The 13 real-STRAP rows to research (case_number, parcel_id):
2011 CA 003872 MF | 072530272401950380
2019 CA 000153 MF | 3026315130000D0070
2025 CA 001061 MF | 242528105500010240
2025 CA 002509 MF | 252628610006000090
53772024 | 302530497100011070
53942024 | 302530497100011720
6632024 | 032530420800010220
38742024 | 202529183000
35922022 | 192733273000
40652024 | 212632351900
41922024 | 223033000000
48132023 | 282529138700
27092022 | 152529324000
29162024 | 152529152000
10902023 | 062629000000
58662022 | 012730495000
2132023 | 012630495000
7772024 | 042630495000
1302024 | 012630000101
43912024 | 242629367000

Wait — that list has more than 13; use exactly this full list of 20 case_number/parcel_id pairs (some earlier counts were approximate; research ALL of them, it is not harmful to have extra real data).

Method:
1. Find the real Osceola County Property Appraiser (OCPA) parcel search tool. Try https://www.property-appraiser.org/ (Osceola County PA) and also search the web for "Osceola County Property Appraiser parcel search" if that URL does not work. Also try an ArcGIS REST discovery: probe https://maps.osceola.org/arcgis/rest/services and https://gis.osceola.org/arcgis/rest/services (these may 404 — if so, web-search for "Osceola County GIS ArcGIS REST services" to find the real live endpoint).
2. For each parcel STRAP, look up (via the PA site's parcel detail page, or an ArcGIS FeatureServer/MapServer query by STRAP/PARCEL_ID attribute) the real: site address, assessed value (or just/market value), and lat/lon (if the GIS layer exposes parcel centroid geometry, or you can derive lat/lon from an ArcGIS query result's geometry in WGS84/EPSG:4326 — if the service returns a different spatial reference, note it in source_url/notes and still report the raw coordinates with a note, do not silently reproject incorrectly).
3. For case "2025 CA 001721 MF" specifically, search the Osceola County Clerk of Courts case search (myclerk.osceola.org or similar) for that case number to find the real defendant property address from the case docket.
4. Report EVERY row via the required schema, one entry per case_number. Use confidence="VERIFIED" only if you fetched a real live page/API response and the data is directly visible there. Use confidence="INFERRED" if you had to reason/estimate. Use found=false + confidence="UNKNOWN" if nothing real was found — this is the CORRECT and EXPECTED answer for rows you truly cannot resolve; do not force an answer.

You have Bash (curl, network egress works — TLS cert errors are common on some Florida gov sites, use curl -sk to bypass), WebFetch, and WebSearch tools. Use them. Do not write to any database — you are research-only, another agent will apply your findings.
`, { phase: 'Research', schema: RESEARCH_SCHEMA_OI, label: 'research:osceola-I' })

const osceolaGResearch = agent(`
You are researching REAL zoning ordinance values for a small, specific list of zoning districts in Osceola County, Florida (county government + Kissimmee + St. Cloud municipalities), for a zoning-completeness gold-standard criterion. DO NOT FABRICATE any numeric standard. If a district genuinely does not regulate a given dimension (e.g. a single-family residential zone with no FAR cap, common in FL — lot coverage/setbacks are used instead), that is a legitimate real answer: set the value to null AND the corresponding *_applicable flag to false, with a note citing why (e.g. "FL single-family zones regulate via lot coverage/setback, not FAR — confirmed absence in ordinance text, not a lookup failure"). Do not mark something not-applicable just because you couldn't find it — only when the ordinance itself is genuinely silent on that dimension for that use type AND you have positive evidence of that (e.g. read the ordinance section and it has no FAR table for this district).

Districts to research (jurisdiction, zone_code, current parcel count in our data, current gap):
1. Kissimmee (jurisdiction_id=957), zone_code="RA-3" — 2 parcels — need max_density_du_acre, max_far, parking_per_1000sf
2. Kissimmee (jurisdiction_id=957), zone_code="T3" — 2 parcels — Kissimmee uses a Form-Based Code (Chapter 14-5, Land Development Code) with Transect zones T1-T6; T3 = Sub-Urban Zone
3. Kissimmee (jurisdiction_id=957), zone_code="T5-M" — 1 parcel — T5-M = Urban Center Zone, Multi-family/mixed variant, same Form-Based Code
4. Kissimmee (jurisdiction_id=957), zone_code="SRPUD" — 1 parcel — likely "Suburban Residential Planned Unit Development" or similar PUD designation
5. St. Cloud (jurisdiction_id=894), zone_code="R-3" — 2 parcels — St. Cloud multi-family residential district
6. Osceola County unincorporated (jurisdiction_id=1186), zone_code="E-1" — 1 parcel — Osceola County LDC "Estate" residential district
7. Osceola County unincorporated (jurisdiction_id=1186), zone_code="MXD" — 1 parcel — "Mixed Use" district; ONLY max_density_du_acre is missing here (max_far and parking_per_1000sf are already populated in our DB, do not worry about those, only research density)

Sources to use, in order of preference:
- Kissimmee: library.municode.com/fl/kissimmee — Chapter 14-4 (Zoning, conventional districts like RA-3) and Chapter 14-5 (Form-Based Code, Transect zones T1-T6) of the Land Development Code. Also check kissimmee.gov planning department pages for a zoning summary table or form-based code "regulating plan" standards table (these commonly publish a one-page table per transect zone with density/height/parking).
- St. Cloud: library.municode.com/fl/st._cloud or stcloud.org planning/zoning ordinance.
- Osceola County: library.municode.com/fl/osceola_county or osceola.org Growth Management / Land Development Code (Chapter 3, Zoning).

For T3/T5-M (form-based code transect zones): these typically express density in dwelling units/acre and either omit FAR (if not form-based-metric-driven for that dimension) or include a build-to-zone/frontage standard instead of a percent lot coverage — read the actual regulating plan table for T3 and T5-M and report exactly what is published, real numbers, with the ordinance/table citation.

Report via the required schema — one entry per (jurisdiction, zone_code). Use confidence="VERIFIED" only when you fetched real ordinance/municode/city text and the number is directly stated there. Use confidence="INFERRED" if reasoning from adjacent evidence. If you truly cannot find real information for a field, set it null with far_applicable/pk1000_applicable/density_applicable=true (still applicable, just unresolved) and confidence="UNKNOWN" — do not invent a plausible-looking number.

You have Bash (curl -sk for TLS-cert-flaky gov/municode sites), WebFetch, and WebSearch. Use them — actually fetch and read the ordinance text, do not answer from general knowledge of typical FL zoning without checking the real source. Do not write to any database — research only.
`, { phase: 'Research', schema: RESEARCH_SCHEMA_G, label: 'research:osceola-G' })

const highlandsIResearch = agent(`
You are researching REAL parcel-level zoning classification for 45 specific real-estate-auction parcels in Highlands County, Florida (cities of Lake Placid and Avon Park, plus a residual set inside Sebring), for a property-card-completeness gold-standard criterion. DO NOT FABRICATE a zone code for any parcel. If you cannot determine a real zone for a parcel, report zone_code=null, confidence="UNKNOWN".

Background/context (already verified in our DB, do not re-derive): our existing zoning_districts/parcel_zones for Highlands County Sebring jurisdiction (jurisdiction_id=918) were bootstrapped with a blanket INFERRED "R-1A Single Family Residential, 4.0 DU/acre" assignment at confidence 0.75 for ALL Sebring parcels — that bootstrap is why Sebring is 223/238 zoned already, but the tag is honest about being a low-confidence blanket default, not verified per-parcel. Lake Placid (jurisdiction_id=840) and Avon Park (jurisdiction_id=955) currently have ZERO parcel_zones rows at all. Your job is to do BETTER than a blind copy of that same blanket-default pattern where possible: find a real Highlands County or municipal GIS zoning layer and determine the REAL per-parcel zone if you can.

Step 1 — find a real GIS source. Try, in order:
- https://www.hcpao.org (Highlands County Property Appraiser — confirmed live) — look for a GIS/map link, or an ArcGIS REST services root (try https://gis.hcpao.org/arcgis/rest/services and sibling subdomains — NOTE: gis.hcpafl.org (note: "hcpaFL" not "hcpaO") was already probed and found to be a MISLABELED/WRONG server actually serving Hillsborough County data — do not use gis.hcpafl.org, it is confirmed NOT Highlands County despite the domain name resembling it).
- Highlands County government GIS: search "Highlands County Florida GIS zoning ArcGIS" — the county Planning/Zoning department likely has a public zoning layer covering the whole county including incorporated Lake Placid/Avon Park if joint-planning applies, or the two towns may have their own separate small-town zoning maps.
- Town of Lake Placid (lpfla.com or similar) and City of Avon Park (avonpark.cc or similar) — look for a published zoning map (often a static PDF map) or municode zoning ordinance (library.municode.com/fl/lake_placid, library.municode.com/fl/avon_park).

Step 2 — for whichever real source you find (GIS attribute/spatial query preferred over a static map read), resolve as many of the 45 parcels below as you realistically can within reasonable effort. If a GIS FeatureServer/MapServer exists, query it by parcel PIN/STRAP (the parcel_id format is like "C-22-37-30-040-0200-0140" — Highlands County's PIN format; you may need to look up how HCPAO's own site encodes/displays this same PIN to search it, e.g. it might show as "22-37-30-040-0200-0140" without the leading county prefix "C-"). If no queryable GIS exists, use the published zoning map + each property's known address (below) to make your best real determination, or the ordinance's default/predominant residential district for that specific area if you can support it with real evidence (e.g. "this subdivision is platted under X district per the recorded plat referenced in the ordinance/map").

The 45 parcels (case_number | parcel_id | address):
25000655 | C-04-34-28-100-1400-0140 | 4148 LIGURIA AVE, SEBRING, FL- 33872
25000777 | C-22-37-30-090-0570-0150 | 248 BLUE HORIZON DR, LAKE PLACID, FL- 33852
25000778 | C-22-37-30-090-0770-0230 | 207 BLUE HORIZON DR, LAKE PLACID, FL- 33852
25000779 | C-24-35-28-050-0050-0020 | 5804 QUINCE RD, SEBRING, FL- 33875
25000780 | C-22-37-30-191-1960-0440 | 929 CR 29, LAKE PLACID, FL- 33852
25000781 | C-22-37-30-040-0200-0140 | 218 MOON GLOW CT, LAKE PLACID, FL- 33852
25000782 | C-22-37-30-191-1840-0100 | 955 CR 29, LAKE PLACID, FL- 33852
25000783 | C-22-37-30-050-0280-0040 | (no address on file)
25000784 | C-22-37-30-050-0320-0090 | (no address on file)
25000785 | C-22-37-30-060-0240-0130 | 204 RAINBOW DR, LAKE PLACID, FL- 33852
25000786 | C-24-35-28-050-0010-0230 | 5713 N DELICIOUS RD, SEBRING, FL- 33875
25000787 | C-24-35-28-100-009A-0180 | 2239 HEATH AVE, SEBRING, FL- 33875
25000788 | C-24-35-28-101-0050-014C | 1324 HYACINTH AVE, SEBRING, FL- 33875
25000789 | C-24-35-28-101-0060-0240 | 1224 HYACINTH AVE, SEBRING, FL- 33875
25000790 | C-22-37-30-020-0640-0140 | 379 BLUE HORIZON DR, LAKE PLACID, FL- 33852
25000791 | C-24-35-28-101-0060-0400 | 2023 HYACINTH TER, SEBRING, FL- 33875
25000792 | C-22-37-30-050-0550-0220 | 365 ELEANOR BLVD, LAKE PLACID, FL- 33852
25000793 | C-24-35-28-101-009A-0210 | 1429 HYACINTH AVE, SEBRING, FL- 33875
25000794 | C-24-35-28-101-007A-0300 | 2033 IRIS AVE, SEBRING, FL- 33875
25000795 | C-22-37-30-070-0870-0060 | 341 RHYTHM DR, LAKE PLACID, FL- 33852
25000796 | C-22-37-30-070-0890-0120 | 322 CINEMA DR, LAKE PLACID, FL- 33852
25000797 | C-24-35-28-101-007A-0460 | 2148 HONEY DEW AVE, SEBRING, FL- 33875
25000798 | C-22-37-30-080-0690-0090 | 389 STARDUST AVE, LAKE PLACID, FL- 33852
25000800 | C-22-37-30-080-0720-0200 | 337 SUMMERDALE LN, LAKE PLACID, FL- 33852
25000801 | C-22-37-30-080-0760-0180 | 319 SUMMERSWEET DR, LAKE PLACID, FL- 33852
25000802 | C-24-35-28-120-0160-0140 | 3308 ALACHUA AVE, SEBRING, FL- 33875
25000803 | C-22-37-30-080-0690-0070 | 393 STARDUST AVE, LAKE PLACID, FL- 33852
25000804 | C-22-37-30-080-0890-0340 | 317 SUMMER HILL DR, LAKE PLACID, FL- 33852
25000805 | C-24-35-28-150-0460-0070 | 10013 CASTLEWOOD CT, SEBRING, FL- 33875
25000806 | C-24-35-28-160-0530-0370 | 2840 GINGER CT, SEBRING, FL- 33875
25000809 | C-24-35-28-180-0830-0050 | 3140 BROWNWOOD DR, SEBRING, FL- 33875
25000810 | C-22-37-30-110-1040-0150 | 236 DARGEN DR, LAKE PLACID, FL- 33852
25000811 | C-22-37-30-110-1030-0180 | 252 CRYSTAL LAKE DR, LAKE PLACID, FL- 33852
25000812 | C-22-37-30-110-1080-0200 | 213 DARGEN DR, LAKE PLACID, FL- 33852
25000813 | C-22-37-30-120-1060-0040 | 131 SUMMER OAK DR, LAKE PLACID, FL- 33852
25000814 | C-22-37-30-160-1660-0060 | 497 BLUE SKIES DR, LAKE PLACID, FL- 33852
25000815 | C-22-37-30-170-1740-0050 | 421 AMOROUS AVE, LAKE PLACID, FL- 33852
25000816 | C-22-37-30-170-1750-0190 | 420 SURRENDER CT, LAKE PLACID, FL- 33852
25000817 | C-22-37-30-170-1770-0050 | 411 WIND ROSE AVE, LAKE PLACID, FL- 33852
25000818 | C-22-37-30-020-0440-0110 | 358 CARTIER AVE, LAKE PLACID, FL- 33852
25000819 | C-22-37-30-050-0480-0190 | 332 SUNNYSIDE DR, LAKE PLACID, FL- 33852
25000820 | C-22-37-30-050-0510-0100 | 359 PARADISE AVE, LAKE PLACID, FL- 33852
25000821 | C-22-37-30-050-0500-0030 | 367 WHISPERING AVE, LAKE PLACID, FL- 33852
25000822 | C-22-37-30-050-0540-0190 | 264 SENTIMENTAL DR, LAKE PLACID, FL- 33852
25000823 | C-24-35-28-010-0000-3841 | 7019 GOLDENROD AVE, SEBRING, FL- 33875

Note the parcel_id prefix "C-" appears to be our internal county-code prefix, not part of the county's own PIN — when searching HCPAO's own tools, try the PIN both with and without the "C-" prefix, and also try it reformatted as digits-only or with different dash groupings, since county PIN display formats vary from how they're stored in our DB.

Report via the required schema: gis_source_found/gis_source_url/gis_source_notes describing what you found (even if it's "no queryable GIS found, used static zoning map at URL X"), then one parcels[] entry per case_number with your best real, sourced determination or an honest UNKNOWN. Use confidence="VERIFIED" only for a direct GIS/ordinance-map hit on that specific parcel or its specific subdivision. Use confidence="INFERRED" for area-level reasoning. It is completely acceptable and expected for many/most of these to end up UNKNOWN if no real per-parcel source exists — do not pad the count with guesses.

You have Bash (curl -sk), WebFetch, and WebSearch. Use them.
`, { phase: 'Research', schema: RESEARCH_SCHEMA_HI, label: 'research:highlands-I' })

const [oiResult, ogResult, hiResult] = await parallel([
  () => osceolaIResearch,
  () => osceolaGResearch,
  () => highlandsIResearch,
])

log(`Research done. osceola-I parcels=${oiResult?.parcels?.length ?? 0} osceola-G zones=${ogResult?.zones?.length ?? 0} highlands-I parcels=${hiResult?.parcels?.length ?? 0}`)

phase('Fix')

const oiFix = oiResult ? await agent(`
Apply these RESEARCHED (not fabricated by you) findings about 20 Osceola County auction parcels to the live Supabase database, mechanically. Only apply fields where found=true/confidence is VERIFIED or INFERRED (not UNKNOWN) and a real value is present — for anything found=false or confidence="UNKNOWN" or null value, SKIP that field/row and count it in skipped_no_real_data, do not invent a substitute.

Research JSON:
${JSON.stringify(oiResult)}

For each row with usable data, run an UPDATE against the multi_county_auctions table via the Supabase REST API (env vars SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are already set in your shell — use them directly with curl, do not print their raw values):
curl -s -X PATCH "$SUPABASE_URL/rest/v1/multi_county_auctions?case_number=eq.<CASE_NUMBER_URL_ENCODED>&county=eq.osceola" -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" -H "Content-Type: application/json" -H "Prefer: return=minimal" -d '{"property_address": "...", "assessed_value": ..., "latitude": ..., "longitude": ...}'
Only include keys in the JSON body for fields you actually have a real value for on that row. case_number must be URL-encoded (spaces as %20). Verify each PATCH returns HTTP 204 (success) — if not, report the error, do not silently continue past a failure without noting it.

After applying, report via the schema: tables_written (table="multi_county_auctions", rows_updated count), skipped_no_real_data count, skipped_case_numbers list, and a one-paragraph summary.
`, { phase: 'Fix', schema: FIX_SCHEMA, label: 'fix:osceola-I' }) : null

const ogFix = ogResult ? await agent(`
Apply these RESEARCHED (not fabricated by you) zoning ordinance findings for 7 Osceola County zoning districts to the live Supabase database, mechanically. Only apply where confidence is VERIFIED or INFERRED with a real basis — skip (count in skipped_no_real_data) anything confidence="UNKNOWN".

Research JSON:
${JSON.stringify(ogResult)}

Schema reminder for the two tables (read current columns first with a GET to confirm, e.g. curl "$SUPABASE_URL/rest/v1/zoning_districts?id=eq.1&select=*" -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"):
- zoning_districts: jurisdiction_id, code, name, category, description, density_regulated (bool), far_regulated (bool), pk1000_regulated (bool, if column exists — check first, it may not)
- zone_standards: zoning_district_id (FK), max_density_du_acre, max_far, parking_per_1000sf, parking_per_unit, source_url, ordinance_section, confidence_score

For each researched zone (jurisdiction_id + zone_code given):
1. Check if a zoning_districts row already exists for that (jurisdiction_id, code) via GET with filters jurisdiction_id=eq.<id>&code=eq.<code>. If not, POST a new one (category=research value, and set density_regulated/far_regulated to match the density_applicable/far_applicable booleans from research so the applicability view correctly marks non-regulated dimensions as N/A rather than a gap — check if a pk1000_regulated column exists on zoning_districts; if it does not exist, applicability for parking falls back to the category-based default in v_zoning_district_applicability, so just set category correctly).
2. Check if a zone_standards row exists for that zoning_district_id (GET filter zoning_district_id=eq.<id>). If yes, PATCH it; if no, POST a new one. Only set the numeric fields (max_density_du_acre / max_far / parking_per_1000sf) that have a real non-null researched value — leave others as-is (do not overwrite an existing real value with null). Set source_url and ordinance_section from the research, and confidence_score = 0.9 if research confidence was VERIFIED, 0.7 if INFERRED.
3. IMPORTANT — MXD (Osceola County) already has max_far and parking_per_1000sf populated in our DB; only research/apply max_density_du_acre for that one, do not touch its existing far/parking values.

Verify each write's HTTP status (200/201/204 = success). Report via schema: tables_written array (one entry each for zoning_districts and zone_standards with rows_inserted/rows_updated), skipped_no_real_data count, skipped list (as jurisdiction:zone_code strings in skipped_case_numbers), and summary.
`, { phase: 'Fix', schema: FIX_SCHEMA, label: 'fix:osceola-G' }) : null

const hiFix = hiResult ? await agent(`
Apply these RESEARCHED (not fabricated by you) findings about Highlands County parcel zoning to the live Supabase database, mechanically. Only apply rows with a non-null zone_code and confidence VERIFIED or INFERRED — skip (count in skipped_no_real_data) anything zone_code=null or confidence="UNKNOWN".

Research JSON:
${JSON.stringify(hiResult)}

Jurisdiction IDs: sebring=918, lake_placid=840, avon_park=955. If a parcel's researched jurisdiction is "unincorporated_highlands" or "unknown", SKIP it (we have no matching jurisdiction row for those in our DB — do not force it into sebring/lake_placid/avon_park).

For each usable parcel:
1. Ensure a zoning_districts row exists for (jurisdiction_id, code=zone_code) — GET first, POST if missing (category best-guess from the zone name research gave you, e.g. residential).
2. Confirm no existing parcel_zones row for that exact parcel_id (GET $SUPABASE_URL/rest/v1/parcel_zones?parcel_id=eq.<ID>&jurisdiction_id=eq.<jid> — these should currently be empty per our diagnosis, but double check to stay idempotent).
3. POST a new parcel_zones row: parcel_id, jurisdiction_id, zone_code, zone_name, source = "shard9_255f0be0_highlands_i_research" (plus append confidence, e.g. "shard9_255f0be0_highlands_i_research_verified" or "..._inferred" to match the research confidence — this must be honest about VERIFIED vs INFERRED, do not tag INFERRED findings as verified).

Use env vars SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY already in your shell for curl auth; do not print raw key values. Verify each write's HTTP status.

Report via schema: tables_written (zoning_districts + parcel_zones with counts), skipped_no_real_data count, skipped_case_numbers list, summary.
`, { phase: 'Fix', schema: FIX_SCHEMA, label: 'fix:highlands-I' }) : null

log(`Fix done. osceola-I=${JSON.stringify(oiFix?.tables_written)} osceola-G=${JSON.stringify(ogFix?.tables_written)} highlands-I=${JSON.stringify(hiFix?.tables_written)}`)

phase('Verify')

const BEFORE = {
  osceola: { I: 89.8, G: 0.0 },
  highlands: { I: 82.6 },
}

const verifyTargets = [
  { county: 'osceola', letter: 'I', fixSummary: oiFix, claim: 'osceola-I geo/value enrichment for gap rows raised card-completeness toward pass' },
  { county: 'osceola', letter: 'G', fixSummary: ogFix, claim: 'osceola-G zone_standards backfill for RA-3/T3/T5-M/SRPUD/R-3/E-1/MXD closed the density/FAR/pk1000 gap' },
  { county: 'highlands', letter: 'I', fixSummary: hiFix, claim: 'highlands-I parcel_zones backfill for Lake Placid/Avon Park/Sebring-residual raised card-completeness toward pass' },
].filter(t => t.fixSummary)

const verifyResults = await parallel(verifyTargets.map(t => () => agent(`
You are an INDEPENDENT adversarial refuter. Your only goal is to try to BREAK this claim, not confirm it. You were not involved in the research or fix — verify everything fresh against the live database.

CLAIM: "${t.claim}"
County: ${t.county}, Letter: ${t.letter}
Metric BEFORE this session's fix: ${BEFORE[t.county][t.letter]}
Fix agent's self-reported summary (DO NOT TRUST THIS AT FACE VALUE — verify independently): ${JSON.stringify(t.fixSummary)}

Do the following, using curl against the Supabase REST API with env vars SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY (already in your shell, do not print raw values):

1. Re-run the live evaluator: POST $SUPABASE_URL/rest/v1/rpc/pencil_dod_evaluate_county with body {"p_county":"${t.county}"} (headers apikey/Authorization as usual, Content-Type application/json). Extract the "${t.letter}" object's metric and pass fields. This is your metric_after and pass_after — ground truth, not the fix agent's claim.
2. Check for the B>100%-style anomaly class: if metric_after is implausibly high (e.g. exceeds 100 where the metric is a percentage, or an obviously wrong jump), set anomaly_detected=true and treat this as an automatic refutation (survived=false) regardless of anything else.
3. Spot-check at least 2 of the source_url values the fix claims to have used (from the fix summary's underlying research — if source URLs aren't in what was passed to you, query the actual rows this fix touched: for osceola-I query multi_county_auctions rows for the case_numbers involved; for osceola-G query zone_standards.source_url for the zoning_district ids involved; for highlands-I query parcel_zones.source for the newly inserted rows) — actually fetch each URL with curl -sk and confirm it returns real content (HTTP 200-ish, non-empty, plausibly relevant), not a 404/dead link/placeholder. Count sources_spot_checked and sources_confirmed_real.
4. Look for fabrication signatures: byte-identical values across dissimilar rows (e.g. every single row given the exact same assessed_value or the exact same lat/lon to many decimal places when they are different addresses), suspiciously round numbers with no cited source, or confidence tags that don't match what the underlying source actually shows (e.g. tagged VERIFIED but the source_url is empty/null or resolves to nothing relevant). Set fabrication_suspected=true if you find this.
5. Decide survived: true only if metric_after genuinely improved or matches what real evidence supports, no anomaly, and no fabrication suspected. If the metric did NOT move at all versus the BEFORE number and the fix claimed rows were written, treat that as suspicious (maybe the write didn't actually take) and investigate why (e.g. re-check the fix agent's claimed row counts against a live count query) before deciding survived.
6. Finally, INSERT one row into gold_standard_ultraloop_audit via POST $SUPABASE_URL/rest/v1/gold_standard_ultraloop_audit (Prefer: return=minimal) with body: {"dispatch_id": "${DISPATCH_ID}", "ultraloop_mode": "native", "county_slug": "${t.county}", "letter": "${t.letter}", "claim": ${JSON.stringify(t.claim)}, "refuter_evidence": <a jsonb object containing what you checked and found — metric_before, metric_after, sources checked with results, any anomaly/fabrication notes>, "survived": <your true/false verdict>}. Confirm this insert returned HTTP 201/204.

Report your verdict via the required schema.
`, { phase: 'Verify', schema: VERIFY_SCHEMA, label: `verify:${t.county}-${t.letter}` })))

log(`Verify done: ${verifyResults.filter(Boolean).map(v => `${v.county_slug}.${v.letter}=${v.survived ? 'SURVIVED' : 'REFUTED'}(${v.metric_before}->${v.metric_after})`).join(', ')}`)

return {
  research: { osceola_I: oiResult, osceola_G: ogResult, highlands_I: hiResult },
  fix: { osceola_I: oiFix, osceola_G: ogFix, highlands_I: hiFix },
  verify: verifyResults.filter(Boolean),
}
