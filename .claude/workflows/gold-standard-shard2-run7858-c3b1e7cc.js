export const meta = {
  name: 'gold-standard-shard2-run7858-indianriver-citrus-lee-liberty-columbia',
  description: 'Gold Standard SHARD-2 (dispatch c3b1e7cc, loop run 7858): indian_river/citrus/lee E+I parcel-linkage & card-completion fixes via county ArcGIS, liberty+columbia fresh structural-blocker rechecks, adversarial verify all claims',
  phases: [
    { title: 'Fix', detail: 'one agent per county/letter cluster, forking proven scripts where they exist' },
    { title: 'Verify', detail: 'independent refuter + live pencil_dod_evaluate_county re-check per claim' },
  ],
}

const RECIPE = `
Environment (already available, do not ask for credentials):
- REST API reads/writes: GET/PATCH/POST \${SUPABASE_URL}/rest/v1/<table>?... headers apikey: $SUPABASE_SERVICE_ROLE_KEY,
  Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY. NEVER echo/print/log the header value itself.
- Live arbitrary SQL (for schema lookups / verification queries ONLY, not for bulk writes if REST works):
  POST https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query, headers
  Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json, body {"query": "<sql>"}.
  Build JSON with a real encoder (python3 -c "import json..." to a temp file, curl --data-binary @file) -- never hand-quote.
  Direct psql/pooler connections FAIL password auth in this sandbox -- do not waste time on them, use Management API/REST only.
- pencil_dod_evaluate_county RPC: POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county body
  {"p_county":"<county>"} -- this is your ONLY source of truth for before/after proof. Run it before you touch
  anything and again after, and paste both raw JSON outputs in your return.
- repo root is the current working directory, on main, already checked out. gh CLI authenticated.
- Skills available via the Skill tool: "browser-use" and "firecrawl-browser" for real interactive browser
  sessions; "firecrawl-scrape"/"firecrawl-search"/WebSearch for static content.

Hard rules (from this repo's CLAUDE.md GOLD STANDARD campaign brief -- follow exactly):
- You own ONLY the one county assigned to you in your prompt. Never touch any other county's rows, and never
  touch letters other than the ones assigned to you for that county.
- PropertyOnion (data_source='propertyonion', tier1_authoritative != true) rows are EXCLUDED from every
  pencil_dod_evaluate_county metric already -- do not waste time fixing those rows, they don't count.
- Fail-loud invariant: if a batch API call reports parsed>0 rows but 0 written, treat that as an ERROR, not a
  silent skip.
- NEVER fabricate a parcel_id, address, lat/lon, assessed value, zone_code, sold amount, or party name. A
  garbage placeholder string already in parcel_id (e.g. "MULTIPLE PARCELS", "Property Appraiser", "TIMESHARE")
  is NOT a real parcel_id even though it is non-null -- if you cannot find the REAL parcel, leave it as residual
  and report it, do not invent one.
- Do NOT insert a parcel_zones row for a (jurisdiction_id, zone_code) pair that has zero zoning_districts
  precedent -- that creates a G-denominator entry that can never pass. Check zoning_districts first.
- Do NOT attempt to solve or bypass any CAPTCHA/Turnstile challenge. Report it and stop that angle.
- Do not run public.gold_standard_loop(), gold_standard_certify(), or modify cron jobs 109/111/115/any
  gold-standard-loop-* job.
- Tag every claim VERIFIED (you ran it, paste the real output) / UNTESTED / INFERRED.
- Commit nothing yourself -- writes go straight to the live DB via REST/RPC, not via a migration file, since
  these are row-level data backfills, not schema changes. Do not touch git in your task.
`

phase('Fix')

const LANES = [
  {
    key: 'lee_e_i_arcgis',
    prompt: `Gold Standard shard-2, county=lee ONLY, letters E and I.\n\n${RECIPE}\n\n` +
`BASELINE (VERIFIED live moments ago): lee is 8/10. E FAIL metric=94.1 (parcel_linked=303 of 322). I FAIL metric=87.6 (card_complete=282 of 322). Do NOT touch A/B/C/D/F/G/H/J -- they already pass.\n\n` +
`A PROVEN, ALREADY-WORKING pipeline exists for exactly this problem: scripts/gold_standard_shard5_lee_ei_arcgis_backfill.py (read it in full first). It uses the confirmed-live Lee County ArcGIS FeatureServer:\n` +
`  https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/Lee_County_Parcels/FeatureServer/0/query\n` +
`queried by STRAP (outFields STRAP,ZONING,LATITUDE,LONGITUDE,ASSESSED,JUST,SITEADDR,SITECITY), and a jurisdiction map (Cape Coral=815, Bonita Springs=914, Fort Myers Beach=912, Sanibel=942, Fort Myers=929, unincorporated/other=630). It only inserts a parcel_zones row when (jurisdiction_id, zone_code) already exists in zoning_districts (checked live) -- never invents a new zoning code precedent. FORK this script (do not rewrite from scratch), point it at the CURRENT failing row set (query multi_county_auctions live yourself, scoped exactly like the evaluator: WHERE lower(county)='lee' AND (COALESCE(data_source,'')<>'propertyonion' OR COALESCE(tier1_authoritative,false)=true), for E: parcel_id IS NULL; for I: the row also needs property_address, lat, lon, and (assessed_value OR market_value) all non-null AND parcel_id (or tax_account) must resolve in v_zoning_gold_standard_card with zone_code IS NOT NULL).\n\n` +
`Known specifics from a live query just run this session (verify freshly yourself, this may have shifted): ~18 rows have a real-looking dash-formatted STRAP parcel_id but no matching parcel_zones row (case A in the script -- STRAP lookup + conditional parcel_zones insert + geo/value backfill). 2 rows have a garbage parcel_id ("Property Appraiser", "TIMESHARE") -- for these, look up the real parcel via property_address if present, else via the case_number on a foreclosure records lookup (Lee Clerk's site or the ArcGIS SITEADDR search); if no real parcel can be found, leave as residual, do not invent one. ~4 rows have parcel_id NULL but a real property_address (case C in the script -- address lookup via SITEADDR LIKE, backfill parcel_id + geo/value, and parcel_zones only if the returned zoning code already has zoning_districts precedent for the matched jurisdiction). ~15 rows have neither parcel_id nor property_address (documented residual in the prior script's own docstring -- these need a court-record/case-detail lookup the ArcGIS approach cannot do; try a WebSearch or the Lee Clerk case search for the case_number to recover a property address before giving up on any of them, but do not force it).\n\n` +
`Execute the fixes LIVE (real PATCH/POST to multi_county_auctions and parcel_zones via REST, real writes, not dry-run). Re-run pencil_dod_evaluate_county('lee') when done. Return { county:'lee', before: <raw json>, after: <raw json>, rows_fixed_e: number, rows_fixed_i: number, residual_rows: array of {case_number, reason}, writes_made: array of {table, id_or_parcel_id, fields_changed}, confidence: "VERIFIED" }.`,
    schema: { type: 'object', properties: { county: { type: 'string' }, before: {}, after: {} }, required: ['county', 'before', 'after'], additionalProperties: true },
  },
  {
    key: 'citrus_e_i',
    prompt: `Gold Standard shard-2, county=citrus ONLY, letters E and I.\n\n${RECIPE}\n\n` +
`BASELINE (VERIFIED live moments ago): citrus is 8/10. E FAIL metric=94.2 (parcel_linked=180 of 191). I FAIL metric=94.2 (card_complete=180 of 191). Do NOT touch A/B/C/D/F/G/H/J.\n\n` +
`11 specific rows are the gap (query multi_county_auctions live yourself with the same scoping filter as scripts/shard28_run338_e_parcel_linkage.py's citrus config -- read that file first, it has a citrus ArcGIS URL marked INFERRED/unverified: https://gis.citruspa.org/arcgis/rest/services/ParcelData/MapServer/0/query -- your first job is to verify live whether that endpoint actually resolves (it may 404/wrong-schema; if so, discover the REAL Citrus County Property Appraiser ArcGIS FeatureServer via WebSearch for "Citrus County Property Appraiser GIS ArcGIS REST services" or citruspa.org's own GIS map page network requests). All 11 rows currently have parcel_id=NULL AND property_address=NULL -- case_number is your only lookup key (format like "2024 CA 000179 A", all foreclosure). You will likely need the Citrus Clerk's case search (or a Firecrawl/browser-use session against the clerk's OCRS/eCourt portal) to recover the property address from the case docket FIRST, then geocode/parcel-match via the appraiser's ArcGIS or address search. If a case has genuinely no public docket address available, report it as residual -- do not fabricate.\n\n` +
`Execute LIVE writes via REST once you have real, verified data for each row. Re-run pencil_dod_evaluate_county('citrus') when done. Return { county:'citrus', before: <raw json>, after: <raw json>, rows_fixed: number, residual_rows: array of {case_number, reason}, writes_made: array, confidence: "VERIFIED" }.`,
    schema: { type: 'object', properties: { county: { type: 'string' }, before: {}, after: {} }, required: ['county', 'before', 'after'], additionalProperties: true },
  },
  {
    key: 'indian_river_i',
    prompt: `Gold Standard shard-2, county=indian_river ONLY, letter I only (E/A/B/F/G/H/J/C/D already pass -- do NOT touch them).\n\n${RECIPE}\n\n` +
`BASELINE (VERIFIED live moments ago): indian_river is 9/10, only I fails, metric=93.3 (card_complete=98 of 105). 7 specific rows (query multi_county_auctions live yourself, scoped like the evaluator for county='indian_river'): 2 have garbage parcel_id ("MULTIPLE PARCELS", "2025 CA 000325"; "Property Appraiser", "2025 CA 000450") -- these need real parcel resolution, not fabrication; the "MULTIPLE PARCELS" case likely genuinely spans >1 parcel (a foreclosure can cover multiple contiguous lots) -- if so, pick the primary/largest parcel per the case docket rather than leaving a placeholder string, and document why. The other 5 have real-looking parcel_id values (33391000034000000001.0 etc, a raw 22-digit indian_river PA account-number format) but are missing property_address/lat/lon/assessed+market value. Check scripts/enrich_property_cards.py and scripts/shard7_run757_indian_river_i.py first (both already target this exact county/letter) -- read what they attempted and whether a working Indian River County Property Appraiser ArcGIS/GIS endpoint was ever found (enrich_property_cards.py's own COUNTY_APPRAISERS dict marks gis_endpoint as None/"to be discovered" -- your job includes finding the real one via WebSearch for "Indian River County Property Appraiser GIS ArcGIS REST services" or ircpa.org's map page network requests, or IRC's own open-data ArcGIS Hub). Use that endpoint (or a case-docket/clerk lookup for the 2 garbage-parcel_id rows) to backfill real values only.\n\n` +
`Execute LIVE writes via REST once you have real, verified data. Re-run pencil_dod_evaluate_county('indian_river') when done. Return { county:'indian_river', before: <raw json>, after: <raw json>, rows_fixed: number, residual_rows: array of {case_number, reason}, writes_made: array, confidence: "VERIFIED" }.`,
    schema: { type: 'object', properties: { county: { type: 'string' }, before: {}, after: {} }, required: ['county', 'before', 'after'], additionalProperties: true },
  },
  {
    key: 'liberty_recheck',
    prompt: `Gold Standard shard-2, county=liberty ONLY, letters A/B/F (structural blockers).\n\n${RECIPE}\n\n` +
`CRITICAL CONTEXT -- READ FIRST: this exact county/letter set has been independently reconfirmed blocked in 7+ consecutive sessions (2026-07-05 through 2026-07-29, most recently .claude/session-logs/2026-07-29-gold-standard-shard8-liberty-2nd-firing.yml -- read it and its linked prior firing). DO NOT repeat the exhausted methods documented there (libertyclerk.com tax-deed page has repeatedly shown zero active TD listings -- genuine absence, not a scraper gap; no historical TD case found anywhere after an exhaustive multi-path search; Liberty sells in-person on courthouse steps with no early-visibility bid feed).\n\n` +
`THE ONE GENUINELY NEW THING TO CHECK: the prior session explicitly flagged "next legitimate B/F recheck no earlier than 2026-07-31 (FL Certificate-of-Title recording window closes for the 2026-07-21 sale)" -- today is 2026-08-01, so this recheck is now due and has NOT been done yet. Case 24-CA-22 (Liberty's only auction) had sale date 2026-07-21, judgment $108,683.02, no result posted as of 2026-07-29. Check libertyclerk.com/courts/foreclosure-sales/ and any Certificate of Title / Certificate of Disbursements recording source for Liberty County (Liberty County Clerk's official records search, if one exists -- WebSearch for "Liberty County Florida Clerk official records search") for a sale result on this specific case. Also do one fresh check of libertyclerk.com/courts/tax-deeds/ for any newly-listed TD case (last confirmed empty 2026-07-29). Note: a Civitek OCRS scheduled maintenance window was flagged for today 2026-08-01 11:00-14:00 ET -- if you hit civitek and it's down, that's the maintenance window, not a new blocker; note the time you tried.\n\n` +
`If you find a real, verifiable sale result (winning bid / sold amount / cancelled / redeemed), write it as an INDEPENDENT outcome (foreclosure_outcomes table, data_source NOT containing 'promote', NOT PropertyOnion-derived) live via REST, matched by case_number. If nothing has changed, report that plainly -- a 8th consecutive confirmed-blocked finding is a valid, expected result, not a failure to find something.\n\n` +
`Re-run pencil_dod_evaluate_county('liberty') before and after. Return { county:'liberty', before: <raw json>, after: <raw json>, sale_result_found: boolean, evidence: string, writes_made: array, confidence: "VERIFIED" }.`,
    schema: { type: 'object', properties: { county: { type: 'string' }, before: {}, after: {} }, required: ['county', 'before', 'after'], additionalProperties: true },
  },
  {
    key: 'columbia_recheck',
    prompt: `Gold Standard shard-2, county=columbia ONLY, letters A/B/F/I.\n\n${RECIPE}\n\n` +
`CRITICAL CONTEXT -- READ FIRST: read GOLD_STANDARD_SHARD9_COLUMBIA_DISPATCH_FD02926F_RUN6871_SESSION_REPORT.md, its _CONTINUATION_ADDENDUM.md, and .claude/workflows/gold-standard-shard9-columbia-run7177-b5ef98e4.js (the last firing, 2026-07-29, only 3 days before today). That firing exhaustively re-tested and confirmed dead: columbiaclerk.com (Cloudflare 403 across every tool), columbiafl.realtaxlien.com (403), civitekflorida.com OCRS search action (server-side Turnstile-gated, confirmed via Playwright network trace, HTTP 401 on submit), gis.columbiacountyfla.com and gis11.cama.io zoning layers for the Fort White parcel (33-6S-16-04023-000 / STRAP 04023000166S33, zero features in both, second one now 500-errors entirely), Wayback Machine CDX (last snapshot 2024-11-10, stale). Given only 3 days have passed, DO NOT re-run any of these identical methods -- that would be a cost-discipline violation for near-zero expected new information (see this repo's Karpathy K1 guidance and the liberty 2nd-firing precedent in .claude/session-logs/2026-07-29-gold-standard-shard8-liberty-2nd-firing.yml for the correct lightweight pattern to follow here).\n\n` +
`YOUR JOB: (1) run pencil_dod_evaluate_county('columbia') live now and confirm it still matches the brief (6/10, A/B/F/I failing) -- if any metric has drifted, note it. (2) Query the current list of columbia foreclosure rows (multi_county_auctions, county='columbia', scoped like the evaluator) and check whether any case now has auction_date in the past with sold_amount still NULL that was NOT in the previously-checked 7-case list (2025-499-CA, 2025-396-CA, 2025-103-CA, 2023-492-CA, 2023-79-CA, 2025-2196-CC, 2025-501-CA) -- if genuinely new past-due cases exist, that IS new ground: use browser-use/firecrawl-browser against civitekflorida.com/ocrs/county/12/index.xhtml for those specific NEW case numbers only (Columbia's OCRS Turnstile-gating was confirmed for the general search action, but test the specific new case numbers fresh in case behavior differs -- do not assume, but do not spend more than one real attempt). (3) Do one fresh, cheap curl check (not a full browser session) of columbiaclerk.com and columbiafl.realtaxlien.com to confirm the 403 is unchanged (3 days is enough time for a site config to change, low cost to check, do not escalate beyond curl if still blocked). If everything is unchanged, report that plainly as an (Nth) consecutive confirmed-blocked finding -- do not force a fix or fabricate data. Do not touch git.\n\n` +
`Return { county:'columbia', before: <raw json>, after: <raw json>, new_cases_found: array, sale_result_found: boolean, evidence: string, writes_made: array, confidence: "VERIFIED" }.`,
    schema: { type: 'object', properties: { county: { type: 'string' }, before: {}, after: {} }, required: ['county', 'before', 'after'], additionalProperties: true },
  },
]

const fixResults = await parallel(LANES.map((lane) => () => agent(lane.prompt, {
  label: `fix:${lane.key}`,
  phase: 'Fix',
  schema: lane.schema,
})))

log(`Fix phase complete: ${fixResults.filter(Boolean).length}/${LANES.length} lanes returned.`)

phase('Verify')
// NOTE (found post-hoc 2026-08-01): agents return before/after as JSON-ENCODED STRINGS, not
// objects, despite the schema leaving them untyped ({}). Object.entries() on a string iterates
// its characters, so the old beforePass/afterPass comparison here was always 0-vs-0 and never
// triggered. That silently let citrus's real E-letter flip and lee's real writes skip adversarial
// verification entirely in the 2026-08-01 run -- caught manually afterward, both had real issues
// (see that session's report). Parse before comparing, and always verify when any row_fixed count
// is nonzero so a real, unflagged write can never slip through this filter again.
const claimsToVerify = fixResults.filter(Boolean).filter(r => {
  try {
    const before = typeof r.before === 'string' ? JSON.parse(r.before) : (r.before || {})
    const after = typeof r.after === 'string' ? JSON.parse(r.after) : (r.after || {})
    const beforePass = Object.entries(before).filter(([k, v]) => v && v.pass === true).length
    const afterPass = Object.entries(after).filter(([k, v]) => v && v.pass === true).length
    const rowsFixed = Number(r.rows_fixed || 0) + Number(r.rows_fixed_e || 0) + Number(r.rows_fixed_i || 0)
    return afterPass > beforePass || rowsFixed > 0 || r.sale_result_found === true || (r.writes_made && r.writes_made.length > 0)
  } catch (e) { return true } // parse failure -> verify to be safe, never silently skip
})

log(`${claimsToVerify.length}/${fixResults.filter(Boolean).length} lanes claim a metric-moving change -- adversarially verifying each.`)

let verifications = []
if (claimsToVerify.length > 0) {
  verifications = await parallel(claimsToVerify.map((r) => () => agent(
    `Independently verify this claimed Gold Standard fix for county=${r.county}. You did NOT do this work -- be skeptical, your only job is to try to refute it.\n\n` +
    `Claimed result: ${JSON.stringify(r).slice(0, 6000)}\n\n${RECIPE}\n\n` +
    `Your job: (1) re-run pencil_dod_evaluate_county('${r.county}') live yourself right now and confirm the 'after' metrics match what was claimed (paste your own fresh output). (2) For every row in writes_made, independently re-fetch that exact row from multi_county_auctions (and parcel_zones/foreclosure_outcomes if applicable) via REST and confirm the written values are real, non-fabricated, and internally consistent (e.g. a zone_code actually has zoning_districts precedent for its jurisdiction; a parcel_id/STRAP is a plausible real format for this county, not a placeholder). (3) Check the B anomaly rule if letter B was touched: verified_outcomes/closed_sold must land in the 95-105%% band, not merely be non-zero -- an out-of-band ratio is an AUTO-FAIL per this campaign's evaluator rules. (4) If a sale_result_found=true claim was made, confirm the source is genuinely independent (not PropertyOnion-derived) and the underlying page/document actually says what was claimed. Default to refuted=true if you cannot independently reproduce the exact same evidence or the metric doesn't actually match live.\n\n` +
    `Return { county: string, refuted: boolean, refutation_reason: string|null, live_recheck: object, survives: boolean }.`,
    {
      label: `verify:${r.county}`,
      phase: 'Verify',
      schema: {
        type: 'object',
        properties: { county: { type: 'string' }, refuted: { type: 'boolean' }, refutation_reason: {}, live_recheck: {}, survives: { type: 'boolean' } },
        required: ['county', 'refuted', 'survives'],
      },
    }
  )))
}

return { fixResults, verifications }
