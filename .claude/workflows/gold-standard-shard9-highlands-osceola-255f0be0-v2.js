export const meta = {
  name: 'gold-standard-shard9-highlands-osceola-255f0be0-v2',
  description: 'Gold Standard shard-9 2nd firing (highlands+osceola, dispatch 255f0be0): corrected osceola-I case-number lookups, osceola-G high-leverage PD/AC districts, highlands-I unincorporated-county zoning research, ULTRALOOP adversarial verify',
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
          old_parcel_id: { type: 'string' },
          found: { type: 'boolean' },
          full_strap: { type: ['string', 'null'] },
          site_address: { type: ['string', 'null'] },
          assessed_value: { type: ['number', 'null'] },
          just_value: { type: ['number', 'null'] },
          latitude: { type: ['number', 'null'] },
          longitude: { type: ['number', 'null'] },
          source_url: { type: ['string', 'null'] },
          confidence: { type: 'string', enum: ['VERIFIED', 'INFERRED', 'UNKNOWN'] },
          notes: { type: 'string' },
        },
        required: ['case_number', 'old_parcel_id', 'found', 'confidence', 'notes'],
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
          zoning_district_id: { type: 'number' },
          jurisdiction: { type: 'string' },
          zone_code: { type: 'string' },
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
        required: ['zoning_district_id', 'jurisdiction', 'zone_code', 'far_applicable', 'pk1000_applicable', 'density_applicable', 'confidence', 'notes'],
      },
    },
  },
  required: ['zones'],
}

const RESEARCH_SCHEMA_HI = {
  type: 'object',
  properties: {
    source_found: { type: 'boolean' },
    source_url: { type: ['string', 'null'] },
    source_notes: { type: 'string' },
    parcels: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          case_number: { type: 'string' },
          parcel_id: { type: 'string' },
          zone_code: { type: ['string', 'null'] },
          zone_name: { type: ['string', 'null'] },
          category: { type: ['string', 'null'] },
          source_url: { type: ['string', 'null'] },
          confidence: { type: 'string', enum: ['VERIFIED', 'INFERRED', 'UNKNOWN'] },
          notes: { type: 'string' },
        },
        required: ['case_number', 'parcel_id', 'confidence', 'notes'],
      },
    },
  },
  required: ['source_found', 'parcels'],
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
    fabrication_suspected: { type: 'boolean' },
    sources_spot_checked: { type: 'number' },
    sources_confirmed_real: { type: 'number' },
    survived: { type: 'boolean' },
    reasoning: { type: 'string' },
  },
  required: ['letter', 'county_slug', 'metric_before', 'metric_after', 'pass_after', 'anomaly_detected', 'survived', 'reasoning'],
}

phase('Research')

const osceolaIResearch = agent(`
You are researching REAL property data for 14 specific Osceola County, Florida TAX DEED / foreclosure auction cases, to fill a property-card-completeness gold-standard gap. DO NOT FABRICATE any value.

IMPORTANT METHOD NOTE: a prior research pass on these SAME cases failed because it tried to look up parcels by parcel_id, and our stored parcel_id for these 13 tax-deed cases is a TRUNCATED 12-digit prefix of the real 18-character Osceola STRAP (e.g. "202529183000" is only the sec-twn-rng-subdivision prefix; the real STRAP has a 6-more-character block/lot suffix, and 16-800+ different real parcels share the same 12-digit prefix, so you CANNOT resolve it by parcel_id lookup/prefix-match — do not repeat that mistake). Instead, look these up by CASE NUMBER, which should uniquely identify one specific tax deed file with its own listed parcel/STRAP.

The 13 tax_deed case_numbers to research (case_number | truncated_parcel_id_prefix_for_reference_only):
10902023 | 062629000000
1302024 | 012630000101
2132023 | 012630495000
27092022 | 152529324000
29162024 | 152529152000
35922022 | 192733273000
38742024 | 202529183000
40652024 | 212632351900
41922024 | 223033000000
43912024 | 242629367000
48132023 | 282529138700
58662022 | 012730495000
7772024 | 042630495000

Plus 1 foreclosure case with NO real parcel data on file at all: "2025 CA 001721 MF" (our internal placeholder parcel_id "OSC-2CEAE2B1037A" is not a real STRAP, ignore it).

Method for the 13 tax_deed cases:
1. Osceola County tax deed sales are administered through RealTaxDeed (search "Osceola County RealTaxDeed" or try https://osceola.realtaxdeed.com or https://osceola.realforeclose.com) and/or the Osceola County Clerk of Courts Tax Deed Division (osceolaclerk.org or myclerk.osceola.org — search "tax deed sale search"). These numeric case_numbers (e.g. "10902023") likely correspond to a tax deed file/certificate number format used by that specific auction platform — search for the exact case number string on whichever platform you find, or try formatting variants (e.g. "TD-1090-2023", "1090-2023", etc.) if an exact literal search fails.
2. The case file / auction listing for a specific tax deed case should show the FULL STRAP/parcel ID, property address, and assessed/market value directly — this is a direct case-keyed lookup, not a parcel-id lookup, so it should resolve uniquely.
3. If RealTaxDeed/clerk search doesn't work, try a general web search for the case number combined with "Osceola County tax deed" or "Osceola County Florida parcel".
4. For "2025 CA 001721 MF" specifically: search the Osceola County Clerk of Courts case search (myclerk.osceola.org or similar civil/foreclosure case search) for that exact case number to find the real defendant property address from the case docket, then use that address to find the parcel on gis.osceola.org's Parcels FeatureServer (https://gis.osceola.org/hosting/rest/services/Parcels/FeatureServer/3/query — confirmed live and working in a prior research pass, query by address or spatial search) to get STRAP/assessed value/lat-lon.
5. Once you have a real full STRAP, you can also cross-check/get lat-lon and assessed value via the same gis.osceola.org Parcels FeatureServer (query by Strap=eq exact full value).

Report via the schema — one entry per case_number (old_parcel_id = the truncated prefix given above, for traceability). full_strap = the real resolved STRAP if found. Use confidence="VERIFIED" only when you found a real, case-specific source. If you truly cannot resolve a case, found=false, confidence="UNKNOWN" — expected and fine for some of these.

You have Bash (curl -sk for TLS-flaky sites), WebFetch, WebSearch. Use them. Research only, do not write to any database.
`, { phase: 'Research', schema: RESEARCH_SCHEMA_OI, label: 'research:osceola-I-v2' })

const osceolaGResearch = agent(`
You are researching REAL zoning ordinance values for the two HIGHEST-LEVERAGE zoning districts in unincorporated Osceola County, Florida, for a zoning-completeness gold-standard criterion. These two districts cover 484 of 509 (95%) of the county's linked parcels, so getting real data here (rather than the small districts a prior pass already closed) is what will actually move the metric. DO NOT FABRICATE any numeric standard — if the ordinance genuinely does not regulate a dimension for a district (real, sourced, positive evidence of that), report null value with the *_applicable flag set to false and cite why; otherwise if you cannot find real information, report null value with *_applicable=true and confidence="UNKNOWN" (do not guess a plausible-looking number).

Districts to research (both in Osceola County unincorporated, jurisdiction_id=1186):
1. zoning_district_id=11796, zone_code="PD" (Plan Development / Planned Development), 447 parcels. Known so far: far_regulated is already set false in our DB (i.e. FAR was already determined not applicable for PD — do not re-litigate that, just report far_applicable=false, max_far=null in your output to keep it consistent). Need REAL values for max_density_du_acre and parking_per_1000sf — PD districts in FL are typically approved individually with density/parking set by the specific PD's approved master plan/ordinance rather than a single countywide number; research whether Osceola County's LDC (Land Development Code) publishes a DEFAULT or CAP density/parking standard that applies when a specific PD doesn't override it, or a typical/base density range. Be honest if this genuinely varies per-PD-ordinance and there is no single countywide default — in that case report confidence="UNKNOWN" for that field rather than inventing an average.
2. zoning_district_id=11793, zone_code="AC" (Agricultural / Agricultural Conservation), 37 parcels. Need REAL values for max_density_du_acre, max_far, and parking_per_1000sf (or genuine real evidence that some of these are not applicable — FL agricultural zones commonly regulate density via minimum lot size / dwelling units per acre e.g. "1 unit per 5 or 10 acres" rather than FAR, and often have no parking-per-1000sf standard at all since it's not a commercial-intensity zone — if the ordinance text confirms this, that is a legitimate not-applicable finding, cite the section).

Source: Osceola County Land Development Code — try library.municode.com/fl/osceola_county (Chapter 3, Zoning Districts) or osceola.org Growth Management Department LDC pages. Search specifically for "Osceola County LDC Agricultural district AC" and "Osceola County LDC Planned Development PD density".

Report via the schema, one entry per district (use the exact zoning_district_id given). Use confidence="VERIFIED" only when you fetched real ordinance text and the value/absence is directly stated there.

You have Bash (curl -sk), WebFetch, WebSearch. Research only, do not write to any database.
`, { phase: 'Research', schema: RESEARCH_SCHEMA_G, label: 'research:osceola-G-v2' })

const highlandsIResearch = agent(`
You are researching REAL parcel-level zoning classification for 45 specific real-estate-auction parcels that a prior research pass CONFIRMED (via live spatial point-in-polygon check against Highlands County's own Municipal_Boundary ArcGIS layer) are all located in UNINCORPORATED Highlands County, Florida — NOT within the city limits of Sebring, Lake Placid, or Avon Park despite their mailing addresses using those town names (this is normal in rural FL: mailing/ZIP city ≠ incorporation status). We have just created a new "Highlands County" (unincorporated) jurisdiction row in our database, jurisdiction_id=1654, specifically to hold this data — your findings will be written there. DO NOT FABRICATE a zone code for any parcel.

Background you can use: Highlands County's own Land Development Regulations (LDRs) are published at https://cms2.revize.com/revize/highlandscountyfl/departments/development_services/planning/LDRS%20thru%20Ord%2021-22-28%20(6-21-22)%20ADA.pdf (this is the COUNTY's own LDR document — it governs unincorporated land, which is exactly what these 45 parcels are, so this is a directly on-point real source, not a guess). It's a large PDF; if you can fetch and search it, look for the countywide zoning district list, typically in an early chapter (residential districts like R-1, R-2, R-3, RE (Rural Estate), A-1/A-2 (Agricultural), etc.) and any zoning-district map reference.

Step 1 — try to determine, per-parcel or per-area, the REAL zone via one of, in order of reliability:
a) A real Highlands County GIS zoning layer if one exists (search "Highlands County Florida GIS zoning ArcGIS REST" — note: gis.hcpafl.org is CONFIRMED to be a mislabeled/wrong server serving Hillsborough County data, do NOT use it; try gis.hcpao.org, or the county's own hcbcc.net / highlandsfl.gov GIS presence, or a Future-Land-Use/Zoning-specific ArcGIS FeatureServer distinct from the Municipal_Boundary layer already found in the prior pass).
b) The Highlands County Property Appraiser (www.hcpao.org, confirmed live) parcel detail page for each STRAP — some FL property appraiser sites list a Zoning field directly on the parcel record; check one or two sample parcels first to see if this field exists before spending effort on all 45.
c) The county LDR PDF's zoning map exhibit / district descriptions cross-referenced with subdivision names or platted areas visible in the parcel addresses (below) — e.g. many of these are in named subdivisions near Lake Placid (Sun'N Lake area platted subdivisions commonly zoned R-1/RE in unincorporated Highlands County).

The 45 parcels (case_number | parcel_id | mailing address — actual jurisdiction is unincorporated per prior verified spatial check):
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

Note: the "C-" prefix on our parcel_id is our own internal county-code prefix, not part of Highlands County's own PIN format — when searching HCPAO's tools, try without the "C-" prefix and with different dash groupings.

It is fine and expected for some/many of these to end up UNKNOWN if no real per-parcel or reliable area-level source exists — do not pad with guesses. But if you find the LDR's default/predominant unincorporated residential district and can support applying it broadly with real evidence (e.g., the LDR states a specific district applies countywide absent a more specific rezoning, or you find genuine confirmation these platted subdivisions are all zoned e.g. R-1 per the LDR's zoning map), that is a legitimate area-level INFERRED finding — report it with the real ordinance/map citation.

Report via the schema. You have Bash (curl -sk), WebFetch, WebSearch. Research only, do not write to any database.
`, { phase: 'Research', schema: RESEARCH_SCHEMA_HI, label: 'research:highlands-I-v2' })

const [oiResult, ogResult, hiResult] = await parallel([
  () => osceolaIResearch,
  () => osceolaGResearch,
  () => highlandsIResearch,
])

log(`Research done. osceola-I parcels=${oiResult?.parcels?.length ?? 0} osceola-G zones=${ogResult?.zones?.length ?? 0} highlands-I parcels=${hiResult?.parcels?.length ?? 0}`)

phase('Fix')

const oiFix = oiResult ? await agent(`
Apply these RESEARCHED (not fabricated by you) findings about 14 Osceola County auction parcels to the live Supabase database, mechanically. Only apply fields where confidence is VERIFIED or INFERRED (not UNKNOWN) and a real value is present — skip (count in skipped_no_real_data) anything found=false/UNKNOWN.

Research JSON:
${JSON.stringify(oiResult)}

For each row with usable data, PATCH multi_county_auctions filtered by case_number=eq.<URL_ENCODED_CASE_NUMBER>&county=eq.osceola via curl against $SUPABASE_URL/rest/v1/multi_county_auctions (env vars SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY already in your shell; headers apikey/Authorization/Content-Type/Prefer: return=minimal). Body should set whichever of property_address / assessed_value / latitude / longitude / parcel_id (only overwrite parcel_id if full_strap was found and is a real longer/more-specific STRAP than what's on file — do not overwrite with something shorter or equal) you have real values for. Verify each PATCH returns HTTP 204. After each write, GET the row back and confirm the value persisted as sent.

Also — IMPORTANT — after all writes, re-run this check yourself to confirm you actually closed the right gap: GET multi_county_auctions rows for county=osceola and check how many of the 14 target case_numbers now have property_address, assessed_value (or market_value), latitude, longitude ALL non-null. Report this count explicitly in your summary.

Report via schema.
`, { phase: 'Fix', schema: FIX_SCHEMA, label: 'fix:osceola-I-v2' }) : null

const ogFix = ogResult ? await agent(`
Apply these RESEARCHED (not fabricated by you) zoning ordinance findings for the PD and AC zoning districts in unincorporated Osceola County to the live Supabase database, mechanically. Only apply where confidence is VERIFIED or INFERRED with a real basis — skip (count in skipped_no_real_data) anything confidence="UNKNOWN".

Research JSON:
${JSON.stringify(ogResult)}

For each researched district (zoning_district_id given directly, e.g. 11796=PD, 11793=AC):
1. GET the existing zone_standards row: $SUPABASE_URL/rest/v1/zone_standards?zoning_district_id=eq.<id>&select=*
2. If found, PATCH it (filter id=eq.<standards_row_id>) — only set fields you have real non-null researched values for; NEVER null-out an existing non-null value, and NEVER touch max_far for PD (id 11796) since that's already correctly set false/null and out of scope here.
3. If no zone_standards row exists for that zoning_district_id, POST a new one with zoning_district_id + the real fields + source_url + ordinance_section + confidence_score (0.9 if VERIFIED, 0.7 if INFERRED).
4. If your research determined a dimension is genuinely not applicable (far_applicable/pk1000_applicable/density_applicable=false with real evidence), also PATCH the corresponding zoning_districts row (id 11796 or 11793) to set far_regulated/pk1000_regulated/density_regulated accordingly (check first via GET whether these columns exist on zoning_districts — if a pk1000_regulated column does not exist, skip that specific flag update and note it, don't error out).

Verify each write's HTTP status. Report via schema.
`, { phase: 'Fix', schema: FIX_SCHEMA, label: 'fix:osceola-G-v2' }) : null

const hiFix = hiResult ? await agent(`
Apply these RESEARCHED (not fabricated by you) findings about unincorporated-Highlands-County parcel zoning to the live Supabase database, mechanically. Only apply rows with a non-null zone_code and confidence VERIFIED or INFERRED — skip (count in skipped_no_real_data) anything zone_code=null or confidence="UNKNOWN".

Research JSON:
${JSON.stringify(hiResult)}

Target jurisdiction_id=1654 ("Highlands County", unincorporated — newly created this session specifically for this data, confirm it exists via GET $SUPABASE_URL/rest/v1/jurisdictions?id=eq.1654 first).

For each usable parcel:
1. Ensure a zoning_districts row exists for (jurisdiction_id=1654, code=zone_code) — GET first (jurisdiction_id=eq.1654&code=eq.<code>), POST if missing (category from research, or "residential" if unstated and the zone name suggests residential).
2. Confirm no existing parcel_zones row for that exact parcel_id + jurisdiction_id=1654 (idempotency check).
3. POST a new parcel_zones row: parcel_id (use the ORIGINAL "C-..." prefixed value exactly as given in this list, since that's what matches multi_county_auctions.parcel_id and is what the gold-standard evaluator joins on), jurisdiction_id=1654, zone_code, zone_name, source = "shard9_255f0be0_highlands_i_v2_research_verified" if research confidence was VERIFIED, or "shard9_255f0be0_highlands_i_v2_research_inferred" if INFERRED — be honest, do not tag INFERRED as verified.

Use env vars SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY already in your shell; do not print raw key values. Verify each write's HTTP status. Report via schema.
`, { phase: 'Fix', schema: FIX_SCHEMA, label: 'fix:highlands-I-v2' }) : null

log(`Fix done. osceola-I=${JSON.stringify(oiFix?.tables_written)} osceola-G=${JSON.stringify(ogFix?.tables_written)} highlands-I=${JSON.stringify(hiFix?.tables_written)}`)

phase('Verify')

const BEFORE = {
  osceola: { I: 89.8, G: 0.0 },
  highlands: { I: 82.6 },
}

const verifyTargets = [
  { county: 'osceola', letter: 'I', fixSummary: oiFix, claim: '2nd-firing osceola-I: case-number-keyed lookup for the 14 real gap rows (not the mis-scoped 7 from the 1st firing) raised card-completeness toward pass' },
  { county: 'osceola', letter: 'G', fixSummary: ogFix, claim: '2nd-firing osceola-G: real PD/AC zone_standards backfill (95% of parcel_zones denominator) closed the density/FAR/pk1000 gap' },
  { county: 'highlands', letter: 'I', fixSummary: hiFix, claim: '2nd-firing highlands-I: new unincorporated-Highlands-County jurisdiction (id=1654) + real parcel_zones backfill raised card-completeness toward pass' },
].filter(t => t.fixSummary)

const verifyResults = await parallel(verifyTargets.map(t => () => agent(`
You are an INDEPENDENT adversarial refuter. Your only goal is to try to BREAK this claim, not confirm it. You were not involved in the research or fix — verify everything fresh against the live database.

CLAIM: "${t.claim}"
County: ${t.county}, Letter: ${t.letter}
Metric BEFORE this session's fixes (both firings combined, i.e. the ORIGINAL session-start value): ${BEFORE[t.county][t.letter]}
Fix agent's self-reported summary (DO NOT TRUST THIS AT FACE VALUE — verify independently): ${JSON.stringify(t.fixSummary)}

NOTE: an earlier 1st-firing pass on this exact dispatch mistakenly researched the WRONG set of osceola-I case numbers (mixed up with the J-criterion gap list) and wrote real-but-irrelevant data that did not move the I metric (confirmed still 89.8 as of the start of this 2nd firing) — that is why metric_before here is the ORIGINAL 89.8/0.0/82.6 values, not whatever the 1st firing's own verify step reported.

Do the following, using curl against the Supabase REST API with env vars SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY (already in your shell, do not print raw values):

1. Re-run the live evaluator: POST $SUPABASE_URL/rest/v1/rpc/pencil_dod_evaluate_county with body {"p_county":"${t.county}"}. Extract the "${t.letter}" object's metric/pass/detail. This is your metric_after/pass_after — ground truth.
2. Check for the anomaly class (metric implausibly >100% or an impossible jump) — auto survived=false if found.
3. Spot-check at least 2 of the source_url values the fix actually wrote to the DB (query the specific rows/districts this fix touched directly, e.g. for osceola-I query multi_county_auctions for the case_numbers involved and any source_url column; for osceola-G query zone_standards.source_url for zoning_district_id 11796/11793; for highlands-I query parcel_zones.source for jurisdiction_id=1654 rows) — fetch each URL with curl -sk and confirm real, relevant content (not 404/dead/placeholder).
4. Look for fabrication signatures (byte-identical values across dissimilar rows, suspiciously round unsourced numbers, VERIFIED tags on empty/irrelevant source_urls).
5. If metric_after did not move versus metric_before despite the fix claiming writes, investigate why (live count query on the specific rows/districts the fix claims to have touched) before deciding survived — do not just take "it didn't move" at face value without checking if the fix's OWN claimed writes are even present in the DB.
6. INSERT one row into gold_standard_ultraloop_audit via POST $SUPABASE_URL/rest/v1/gold_standard_ultraloop_audit (Prefer: return=minimal): {"dispatch_id": "${DISPATCH_ID}", "ultraloop_mode": "native", "county_slug": "${t.county}", "letter": "${t.letter}", "claim": ${JSON.stringify(t.claim + ' (2nd firing)')}, "refuter_evidence": <jsonb object with what you checked/found>, "survived": <verdict>}. Confirm HTTP 201/204.

Report your verdict via the required schema.
`, { phase: 'Verify', schema: VERIFY_SCHEMA, label: `verify:${t.county}-${t.letter}-v2` })))

log(`Verify done: ${verifyResults.filter(Boolean).map(v => `${v.county_slug}.${v.letter}=${v.survived ? 'SURVIVED' : 'REFUTED'}(${v.metric_before}->${v.metric_after})`).join(', ')}`)

return {
  research: { osceola_I: oiResult, osceola_G: ogResult, highlands_I: hiResult },
  fix: { osceola_I: oiFix, osceola_G: ogFix, highlands_I: hiFix },
  verify: verifyResults.filter(Boolean),
}
