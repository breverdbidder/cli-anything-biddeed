export const meta = {
  name: 'gold-standard-shard5-pinellas-osceola-suwannee-baker-5d40a513',
  description: 'Gold Standard shard-5 (dispatch 5d40a513, loop run 9630): pinellas I zone-linkage backfill, osceola G Osceola-County PD/AC parking research + I truncated-STRAP/PO backfill, baker C/D/E/I/J 10-row research, suwannee audit-freshness refresh (already 10/10 live), adversarially verify all',
  phases: [
    { title: 'Fix', detail: 'one agent per work item, worktree-isolated' },
    { title: 'Verify', detail: 'independent refuter per claim' },
  ],
}

const DISPATCH_ID = '5d40a513-fb55-4c9c-ad49-be84afb8388f'

const RECIPE = `
Environment (already available, do not ask for credentials):
- Live arbitrary SQL: POST https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query
  headers Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json, body {"query": "<sql>"}.
  Run "SET statement_timeout = 0;" first (in the same query string) for anything heavy. Build the JSON body with
  python3 -c "import json;..." to a temp file, then curl --data-binary @file -- do not hand-quote SQL in shell.
- REST reads/writes: GET/PATCH/POST \${SUPABASE_URL}/rest/v1/<table>?... with headers apikey:
  $SUPABASE_SERVICE_ROLE_KEY, Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY. Never echo/print a resolved header
  value into any file/comment/log/commit message -- reference the env var name, not the secret.
- pencil_dod_evaluate_county RPC: POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county body
  {"p_county": "<slug>"} -- returns one jsonb object with keys A..J (each {pass,metric,detail}), county,
  auctions_total, V2_LITMUS. This is your before/after proof.
- VERIFIED evaluator internals (read this session, do not re-derive): the evaluator's denominator EXCLUDES rows
  where data_source='propertyonion' UNLESS tier1_authoritative=true -- always add
  "(COALESCE(data_source,'')<>'propertyonion' OR COALESCE(tier1_authoritative,false)=true)" to any gap query or your
  row counts will not match the scoreboard. B passes ONLY in the 95-105%% band (verified_outcomes/closed_sold), and
  verified_outcomes requires a tax_deed_outcomes/foreclosure_outcomes row with data_source NOT ILIKE '%%promote%%'.
  C/D require parity_status IN ('matched_clean') for C / ('matched_clean','matched_divergent') for D AND
  parity_source LIKE 'tier1%%'. E = parcel_id IS NOT NULL. I requires property_address + (latitude OR po_latitude) +
  (longitude OR po_longitude) + (assessed_value OR market_value) ALL non-null, AND (parcel_id resolves in
  v_zoning_gold_standard_card.parcel_id OR .tax_account, where that view requires zone_code IS NOT NULL). G is
  v_zoning_gold_standard_kpi_v3's pct_density/pct_far/pct_pk1000_of_applicable (min of the three, gated by
  v_zoning_district_applicability -- default applicable=true if no override row exists). parcel_zones joins to
  zoning_districts by (jurisdiction_id, zone_code) -- NOT a zoning_district_id foreign key column, there isn't one.
  J requires a bid_decisions row matched by case_number with arv+max_bid+ml_score+factors containing ALL of
  distress_location, distress_property, distress_owner, cma_distressed, cma_resale. public.refresh_levy_bid_decisions
  and public.gen_valuations_comps_batch / gen_valuations_sourced_batch are the existing J-generator functions --
  DO NOT write a new one, call the existing one(s) after any E/parcel-linkage fix and confirm it populated
  bid_decisions for your case numbers.
- The canonical parity matcher is public.refresh_parity_tier1_outcomes(p_county text) -- call it via the SQL
  endpoint after any parity-relevant insert/update, never hand-write parity_status/parity_source yourself.
- Skills available via the Skill tool: "browser-use" and "firecrawl-browser" for real interactive/rendered browser
  sessions (JS execution, WAF/Cloudflare-cleared, form fills); "firecrawl-scrape"/"firecrawl-search" for simple
  static content and general web search. FIRECRAWL_API_KEY is present with credit.
- gh CLI is authenticated. Repo root is the current working directory (worktree-isolated copy, on main). Any UPDATE
  to existing multi_county_auctions/zone_standards/parcel_zones columns is a data backfill, not a schema change --
  still write a short documentation migration file under
  supabase/migrations/<date>_gold_standard_shard5_5d40a513_<county>_<purpose>.sql per house style (narrative comment
  block with VERIFIED evidence/source URLs, then the idempotent SQL mirroring what you ran live -- see any recent
  supabase/migrations/2026*_gold_standard_shard*.sql file for the pattern), then apply via the SQL endpoint as usual.

ULTRALOOP audit logging (mandatory): for every letter you claim moved, or claim you re-confirmed as
correctly-passing/residual, INSERT one row into public.gold_standard_ultraloop_audit: columns dispatch_id (uuid
'${DISPATCH_ID}'), ultraloop_mode ('fallback' -- manual Workflow-tool fan-out), county_slug, letter, claim (short
text), refuter_evidence (jsonb -- your evidence), survived (boolean -- the FIX agent should only self-mark
survived=true as its own sanity check; the real adversarial gate is the separate Verify-phase agent). POST to
\${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with service-role headers.

Hard rules (from the campaign brief and this repo's CLAUDE.md -- follow exactly):
- You own ONLY pinellas, osceola, suwannee, and baker. Never touch any other county's rows or any other shard's files.
- PropertyOnion (po_* fields, data_source LIKE 'propertyonion%%' or 'PO-%%' case numbers) is litmus/comparison ONLY
  -- never write PropertyOnion-derived values in as if they were verified/independent, and never let a PO-* stub
  row count as a "fix" for B/C/D/F. Using a PO-* address purely as a search LEAD to find the county's own real
  parcel record is fine.
- Fail-loud invariant: if a fix attempt finds zero real data, report it as blocked/residual. NEVER fabricate case
  numbers, parcel IDs, STRAPs, addresses, coordinates, zoning values, or sold amounts to make a metric look better.
  WATCH FOR PRE-EXISTING FABRICATION: this session's live pinellas-I gap query found 4 rows sharing the IDENTICAL
  placeholder-looking values latitude=27.9 / assessed_or_market_value=150000 (case numbers 522023CA006219XXCICI,
  522025CA000532XXCICI, 522025CA003843XXCICI, 522025CA006625XXCICI) -- this looks like a prior fabricated-default
  fallback, NOT real per-property data. Investigate before trusting or reusing these values; if confirmed
  fabricated, flag it (do not silently "fix" I by leaving fake values in place -- report to the Verify agent and
  in your honesty_notes; correcting or nulling out prior fabrication is in-scope even though it wasn't your fix).
- Every claim must be tagged VERIFIED (you ran the query/request and are pasting real output), UNTESTED, or
  INFERRED (say why).
- Before finishing: call pencil_dod_evaluate_county for your county and paste the FULL before/after JSON. If a
  letter did not move, say so plainly -- a genuinely source-exhausted row is a valid, honest outcome.
- git commit any file you create/modify with a clear, county-scoped message. 'git pull --rebase origin main' before
  pushing (other shards may push concurrently). Push directly to main -- no branches, no PRs, per SHIP-TO-MAIN.
- Do NOT run public.gold_standard_loop() or gold_standard_certify() -- the orchestrator (outside your worktree) runs
  those once at session close. Do NOT modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job.
- Budget yourself. If a true fix requires building a brand-new scraper from scratch, do NOT build it in this pass --
  size the gap precisely, report it as a scoped-out residual.

Return: { work_item, county, letters_touched: [...], fix_summary, sql_or_endpoints_used: [...], before_json,
after_json, residual_gaps: [...], honesty_notes: [...] }.
`

const WORK_ITEMS = [
  {
    key: 'pinellas_i',
    county: 'pinellas',
    letters: ['I'],
    prompt: `You are working Gold Standard shard-5, county "pinellas", letter I, dispatch ${DISPATCH_ID}, inside the
cli-anything-biddeed repo (already checked out, on main).

Live baseline (VERIFIED this session via pencil_dod_evaluate_county('pinellas')): 9/10, only I failing.
I FAIL metric=93.4 [card_complete=395 of 423]. Do NOT touch A/B/C/D/E/F/G/H/J -- all already PASS.

ROOT CAUSE (VERIFIED this session via a direct query replicating the evaluator's exact filter, including the
propertyonion exclusion clause and the v_zoning_gold_standard_card zone_code join): ~26-28 gap rows, almost all
foreclosure cases, split into two patterns:
(a) MAJORITY (~20 rows): a real, valid 18-digit STRAP parcel_id, real address, real lat/long, real
assessed/market value -- but has_zone=false, meaning parcel_zones has no row for that exact parcel_id (or the
matching zoning_districts/zone_standards chain doesn't resolve zone_code). Examples: 522019CA002412XXCICI (STRAP
162819451980000100, 2269 RICHTER ST DUNEDIN), 522024CA000566XXCICI (STRAP 162803855080000460, 4767 STONEVIEW CIR
OLDSMAR), 522025CA000730XXCICI (STRAP 163005722580060010, 6003 137TH AVE N CLEARWATER, also missing latitude),
522025CA002431XXCICI (STRAP 153016786490000420, 11783 111TH TER SEMINOLE, missing latitude),
522025CC010725XXCOCO (STRAP 162735311590000400, 3284 GLENRIDGE CT PALM HARBOR, missing latitude) -- re-run the
query fresh (below) for the full current list, it may have shifted slightly since this session started.
(b) MINORITY (~6 rows): garbage/missing parcel_id -- two rows literally have parcel_id='PERSONAL PROPERTY' or
'Property Appraiser' (case 522023CA006219XXCICI, 522026CA006711XXCICI) which are clearly not real STRAPs, one row
has parcel_id=null with a real address (522024CC007590XXCOCO, 8543 13TH STREET N # C ST PETERSBURG), and 4 rows
share an IDENTICAL SUSPICIOUS placeholder pair latitude=27.9 / value=150000 with parcel_id=null and (mostly)
address=null (522023CA006219XXCICI, 522025CA000532XXCICI, 522025CA003843XXCICI, 522025CA006625XXCICI) -- this
looks like leftover fabricated-default data from a prior session, NOT real per-property values. Do not trust or
build on these 4 values; investigate their origin (check migration history / data_source / created_at) and either
find the REAL underlying property (Pinellas Clerk case search by case number reveals the real defendant
address/parcel) or null out the fabricated placeholder and report it honestly as still-gap.

Reproduce the exact live gap list fresh (evaluator-exact filter) before starting:
WITH zc AS (SELECT DISTINCT parcel_id, tax_account FROM v_zoning_gold_standard_card WHERE lower(county)=norm_county_key('pinellas') AND zone_code IS NOT NULL)
SELECT a2.case_number, a2.sale_type, a2.parcel_id, a2.property_address,
  COALESCE(a2.latitude, a2.po_latitude::double precision) lat, COALESCE(a2.assessed_value, a2.market_value) val,
  (a2.parcel_id IN (SELECT parcel_id FROM zc) OR a2.parcel_id IN (SELECT tax_account FROM zc WHERE tax_account IS NOT NULL)) has_zone
FROM multi_county_auctions a2
WHERE lower(a2.county)='pinellas' AND (COALESCE(a2.data_source,'')<>'propertyonion' OR COALESCE(a2.tier1_authoritative,false)=true)
  AND NOT (a2.property_address IS NOT NULL AND COALESCE(a2.latitude, a2.po_latitude::double precision) IS NOT NULL
    AND COALESCE(a2.longitude, a2.po_longitude::double precision) IS NOT NULL AND COALESCE(a2.assessed_value, a2.market_value) IS NOT NULL
    AND (a2.parcel_id IN (SELECT parcel_id FROM zc) OR a2.parcel_id IN (SELECT tax_account FROM zc WHERE tax_account IS NOT NULL)))
ORDER BY a2.case_number;

YOUR JOB:
1. For pattern (a) rows (valid STRAP, just missing zone link, plus a couple missing only latitude): query Pinellas
   County's parcel/zoning GIS (pcpao.org for the Property Appraiser; Pinellas County's own zoning GIS -- search
   "Pinellas County GIS ArcGIS REST zoning" and confirm the live FeatureServer, e.g. something under
   pinellascounty.org or pinellas.maps.arcgis.com) by the exact STRAP to get the real zone_code and jurisdiction
   (confirm municipality from the parcel record's own city/muni field -- Pinellas has 24 municipalities, do not
   assume from the mailing address). Where the zoning_districts row for that (jurisdiction, zone_code) doesn't
   already exist, create it with real ordinance-sourced zone_standards (or leave zone_standards blank and let a
   future G session fill it -- do not fabricate numeric standards, that is out of scope for I, I only needs
   zone_code to resolve). INSERT/UPDATE parcel_zones (parcel_id=STRAP, jurisdiction_id, zone_code). For rows
   missing only latitude, geocode via the same GIS parcel query and UPDATE multi_county_auctions.latitude/longitude.
2. For pattern (b) rows: resolve the real parcel via the Pinellas Clerk's case search (mypinellasclerk.gov or
   similar -- verify live domain) by exact case number to find the real defendant property address, then match to
   pcpao.org / the county GIS to get a real STRAP, address, value, and zone. Fix or null-and-report the 4 suspicious
   placeholder rows per the fabrication-guard instructions above -- do not just leave the placeholder in and claim I
   moved past those rows.
3. Prioritize pattern (a) rows first (cheaper -- zone linkage only, ~20 rows available), then attempt pattern (b) as
   budget allows.
4. Re-run pencil_dod_evaluate_county('pinellas') and report the real before/after I metric. Log
   gold_standard_ultraloop_audit for I with your real row count moved and explicitly note what happened with the
   4 suspicious placeholder rows (fixed / nulled-and-residual / left-as-is-with-explanation).

${RECIPE}`,
  },
  {
    key: 'osceola_g',
    county: 'osceola',
    letters: ['G'],
    prompt: `You are working Gold Standard shard-5, county "osceola", letter G, dispatch ${DISPATCH_ID}, inside the
cli-anything-biddeed repo (already checked out, on main).

Live baseline (VERIFIED this session via pencil_dod_evaluate_county('osceola')): 8/10. G FAIL metric=78.6
[density=94.4 pk1000=78.6 (binding constraint)]. Do NOT touch A/B/C/D/E/F/H/J. I is a separate work item in this
same shard (osceola_i) -- coordinate only through the DB, do not touch its rows/files.

ROOT CAUSE (VERIFIED this session via a direct query joining parcel_zones -> zoning_districts (by jurisdiction_id +
code, there is no zoning_district_id FK column on parcel_zones) -> zone_standards, restricted to zone codes that
actually have osceola auction parcels mapped to them, WHERE parking_per_1000sf IS NULL): the two highest-leverage
gaps by far are BOTH unincorporated Osceola County (not Kissimmee) districts:
  zoning_districts.id=11796  jurisdiction "Osceola County"  code "PD"   (Planned Development) -- 40 osceola auction
    parcels mapped to it, parking_per_1000sf NULL, max_density_du_acre NULL, max_far NULL (fully blank).
  zoning_districts.id=11793  jurisdiction "Osceola County"  code "AC"   (likely Agricultural/Conservation -- verify
    the real category name from the ordinance) -- 37 osceola auction parcels, max_density_du_acre=0.20 already on
    file (do not touch), parking_per_1000sf NULL, max_far NULL.
Smaller gaps (id / jurisdiction / code / osceola parcel count): 11798 Osceola County RMH (4), 13180 Kissimmee SRPUD
(3 -- a prior session already researched Sec 14-4-8 for this one, see zone_standards.ordinance_section for id 5515
if it still exists, do not re-derive from scratch, just try to finish the parking-chapter lookup it left open),
13181 St. Cloud R-3 (3, density already on file), 13179 Kissimmee RA-3 (2), 13226 Osceola County RS-2 (2, density
on file), 13220 Kissimmee T3 (2), 13221 Kissimmee T5-M (2), 13385 Osceola County RS-3 (2, density on file). Fixing
PD+AC alone (77 of the ~86-ish gap-parcel total) would move the vast majority of the pk1000 gap.

YOUR JOB:
1. Research Osceola County's own Land Development Code (osceola.org -- search "Osceola County LDC Chapter 3" or
   similar; municode.com/fl/osceola_county is another mirror) for the real parking requirement applicable to PD
   (Planned Development) and AC districts. PD parking is very commonly "per approved PD master plan / per the
   underlying use" with no single fixed county-wide number -- if that's what the ordinance actually says, that is a
   legitimate real answer: research whether a v_zoning_district_applicability row should mark
   pk1000_applicable=false for PD (genuinely case-by-case, not measurable as a fixed ratio) rather than leaving it
   silently null forever -- but verify this against the actual ordinance text before concluding it, do not assume.
   AC (agricultural/conservation) districts commonly have minimal-to-no structured parking requirements either --
   same investigate-before-concluding approach; note AC already has a real density value on file, so it is not
   "no development permitted", check what the ordinance actually says about parking for whatever level of
   development AC does allow.
2. For any value you find with a real citation: UPDATE zone_standards SET parking_per_1000sf = <value> (and max_far
   if you also find that while researching), source_url, ordinance_section, scraped_at = now() WHERE id IN
   (11796, 11793, ...). INSERT if a zone_standards row for that district doesn't exist. Write a migration file
   documenting the exact ordinance section/text you read for each district you touch.
3. For genuinely inapplicable cases (case-by-case/no-fixed-standard, confirmed by actual ordinance text, not
   assumed): write a real v_zoning_district_applicability row (inspect via pg_get_viewdef/table definition first to
   confirm how that view/table is actually populated) with real justification. Do NOT fabricate a plausible number
   for a discretionary/case-by-case standard just to clear the bar.
4. Budget: prioritize PD (40 parcels) and AC (37 parcels) first -- they alone are ~90%% of the gap-parcel count.
   Attempt the smaller districts (RMH, SRPUD, RA-3, T3, T5-M) only if time remains.
5. Re-run pencil_dod_evaluate_county('osceola') and report the real before/after G metric (density/far/pk1000
   sub-values). Log gold_standard_ultraloop_audit for G with your real districts fixed and citations.

${RECIPE}`,
  },
  {
    key: 'osceola_i',
    county: 'osceola',
    letters: ['I'],
    prompt: `You are working Gold Standard shard-5, county "osceola", letter I, dispatch ${DISPATCH_ID}, inside the
cli-anything-biddeed repo (already checked out, on main).

Live baseline (VERIFIED this session via pencil_dod_evaluate_county('osceola')): 8/10. I FAIL metric=92.7
[card_complete=127 of 137]. Do NOT touch A/B/C/D/E/F/H/J. G is a separate work item in this same shard (osceola_g,
a zone_standards-only fix on districts PD/AC/etc) -- coordinate only through the DB, do not touch its rows/files.

ROOT CAUSE (VERIFIED this session via a live query, evaluator-exact filter applied): ~10 gap rows, all tax_deed or
one synthetic-parcel foreclosure case, ALL sharing the SAME documented osceola-specific trap seen in a prior
session (.claude/workflows/gold-standard-shard4-bradford-osceola-nassau-41bd7ce3.js and
gold-standard-shard9-highlands-osceola-255f0be0-v2.js -- read both for full prior methodology, reuse it, do not
re-derive from scratch): parcel_id is stored as a TRUNCATED ~12-digit STRAP PREFIX (e.g. "012630000101" is only the
sec-twn-rng-subdivision prefix of the real 18-character Osceola STRAP), so any zoning/parcel_zones lookup by that
truncated value will never match -- you must resolve the REAL FULL STRAP per case via a case-number-keyed lookup.

Live gap rows this session (re-query fresh, may have shifted -- use the evaluator-exact filter: county='osceola'
AND (data_source<>'propertyonion' OR tier1_authoritative=true) AND NOT card_complete): tax_deed cases with
truncated-prefix parcel_ids and generic placeholder addresses ("Osceola County, FL 34741" -- not a real street
address, also needs real address resolution): 1302024 (prefix 012630000101), 27092022 (152529324000), 35922022
(192733273000), 40652024 (212632351900), 41922024 (223033000000), 43912024 (242629367000), 48132023
(282529138700), 58662022 (012730495000), 7772024 (042630495000); one synthetic-parcel foreclosure case "2025 CA
001721 MF" (parcel_id="OSC-2CEAE2B1037A", a placeholder, no real address at all -- hardest row, needs full docket
research). NOTE: PO-* rows (PropertyOnion-sourced, e.g. PO-1000727, PO-1001158, PO-1001190, PO-1001391, PO-1001942
and others) appear to have real addresses/market_value already but are EXCLUDED from I's denominator entirely
unless tier1_authoritative=true (per the evaluator filter) -- do NOT spend budget on PO-* rows unless you also flip
them to tier1_authoritative with real independent verification, which is likely out of scope here; confirm this
with a fresh live count before touching any PO-* row.

METHOD (reuse the prior sessions' proven approach):
1. For each tax_deed case: search Osceola's Tax Deed Division (osceolaclerk.org / myclerk.osceola.org / possibly
   osceola.realtaxdeed.com) by the exact numeric case_number (try format variants like "TD-<n>-<year>" if a literal
   number search fails) to find the case-specific record showing the FULL STRAP, real address, and value directly.
2. For "2025 CA 001721 MF": search Osceola Clerk's civil/foreclosure case search (myclerk.osceola.org) for the exact
   case number to find the real defendant property address from the docket, then resolve the parcel via
   gis.osceola.org's Parcels FeatureServer (https://gis.osceola.org/hosting/rest/services/Parcels/FeatureServer/3/
   query -- confirmed live in a prior session, re-verify it's still live) by address or spatial search.
3. Once you have a real full STRAP: cross-check/get lat-lon and assessed value via the same gis.osceola.org Parcels
   FeatureServer (query Strap=eq the full value), and get the zoning code from Osceola County's own zoning GIS layer
   if unincorporated, or the relevant municipality's zoning layer/LDC if incorporated (Kissimmee, St Cloud) --
   verify jurisdiction from the parcel record's own city/muni field, not the mailing address.
4. For each resolved parcel: UPDATE parcel_zones (parcel_id=full STRAP, jurisdiction_id, zone_code) and, if the
   stored multi_county_auctions.parcel_id was the truncated prefix, UPDATE it to the real full STRAP (only if
   certain it's the correct match for that specific case). If the zoning_districts/zone_standards rows don't exist
   for that (jurisdiction, zone_code), either link to an existing equivalent or create it (match code format
   exactly, e.g. hyphenation, to existing zoning_districts.code values for that jurisdiction -- a documented past
   mistake in this campaign was a hyphenation mismatch that silently broke a different county's G).
5. Where a real STRAP/address cannot be resolved (expected for the hardest row), leave it and report as residual --
   do not fabricate.
6. Budget: prioritize rows with the fewest steps to a real value; do the 9 tax_deed rows before the harder
   synthetic-parcel foreclosure case.
7. Re-run pencil_dod_evaluate_county('osceola') and report the real before/after I metric. Log
   gold_standard_ultraloop_audit for I with your real row count moved. Also double-check osceola G's metric did NOT
   regress from any zoning_districts row you created here (a documented precedent: creating a new district row with
   blank zone_standards adds to G's applicable-denominator without a numerator -- if you create any NEW
   zoning_districts row, flag it explicitly in your report so the osceola_g work item / a future session knows to
   backfill its standards).

${RECIPE}`,
  },
  {
    key: 'baker_cdeij',
    county: 'baker',
    letters: ['C', 'D', 'E', 'I', 'J'],
    prompt: `You are working Gold Standard shard-5, county "baker", letters C/D/E/I/J, dispatch ${DISPATCH_ID},
inside the cli-anything-biddeed repo (already checked out, on main).

Live baseline (VERIFIED this session via pencil_dod_evaluate_county('baker')): 5/10. C FAIL metric=41.2
(matched_clean=7 of 17), D FAIL metric=41.2 (matched_any=7 of 17), E FAIL metric=47.1 (parcel_linked=8 of 17), I FAIL
metric=41.2 (card_complete=7 of 17), J FAIL metric=88.2 (deal_complete=15 of 17). Passing: A=8(fc=9 td=8)
B=100(verified=1 closed_sold=1) F=100(tier1_sold=1 closed_sold=1) G=100(density=100 far=100 pk1000=100) H=0.0h.
Do NOT touch A/B/F/G/H.

ROOT CAUSE (VERIFIED this session via a full row dump of all 17 baker multi_county_auctions rows): baker already has
a WORKING tier1 matcher/scraper for some rows -- 7 rows (case_numbers 022025CA000038CAAXMX x2 [fc+td],
022025CA000148CAAXMX x2 [fc+td], 022026CA000018CAAXMX x2 [fc+td], 022026XX000002TDAXMX) show real parcel_id, real
address, real lat/long, real assessed_value, and parity_status='matched_clean' with parity_source
'tier1_baker_realforeclose_bakerpa_v1[...]' or 'tier1_tax_deed_outcome' -- REUSE this exact existing pipeline
pattern/scraper, do not build a new one. The remaining 10 rows are the gap, in two groups:
  FULLY BLANK (8 rows -- no parcel_id, no address, no value, no parity): 022025CA000002CAAXMX(fc),
    022025CA000108CAAXMX(td), 022025CA000117CAAXMX(fc+td), 022025CA000124CAAXMX(fc+td), 022025CC000132CCAXMX(fc),
    022026CA000007CAAXMX(td).
  PARTIAL (2 rows -- some data already present, finish the rest): 022025CA000108CAAXMX(fc) has a real address
    "11018 AARON FISH ROAD, GLEN ST. MARY, FL- 32040" but no parcel_id/lat-long/value/parity;
    022026CA000007CAAXMX(fc) has real parcel_id "063S22004100040100" + address "9999 PERSIMMON RD, MACCLENNY, FL-
    32063" + assessed_value 165762 but no lat/long and no parity_status.
J's gap is narrower and largely a DOWNSTREAM effect of E: only 2 case numbers have zero bid_decisions row at all --
022025CA000002CAAXMX and 022025CC000132CCAXMX (both are also in the fully-blank group above). Every OTHER baker
case, including several that still fail C/D/I, already has a bid_decisions row with ml_score/max_bid/arv populated
(public.refresh_levy_bid_decisions or the gen_valuations_* batch already ran for them even without a parcel_id) --
so J is likely close to self-resolving once those 2 rows get a case-appropriate identity; if it doesn't auto-populate,
call refresh_levy_bid_decisions / gen_valuations_comps_batch / gen_valuations_sourced_batch (check each function's
signature via pg_get_functiondef first) directly for those 2 case numbers after you've backfilled real data for them.

YOUR JOB:
1. Baker's tier1 sources (VERIFIED via pipeline.counties -- confirm live, may differ slightly):
   foreclosure_platform likely realforeclose (bakerclerk.realforeclose.com or similar -- confirm the real domain
   from pipeline.counties.foreclosure_url), taxdeed via Baker County Clerk's tax deed division, and Baker County
   Property Appraiser (search "Baker County FL Property Appraiser" -- likely bakerpa.com or similar, matches the
   parity_source string "tier1_baker_realforeclose_bakerpa_v1" already used for the 7 working rows -- find and
   reuse whatever script/config produced that parity_source, check for it under scripts/ or similar before writing
   anything new).
2. For each of the 8 fully-blank rows: look up the case number on the Baker Clerk's realforeclose/tax-deed calendar
   or case search by exact case number to find the real defendant/property address, then cross-reference Baker
   County PA's GIS/records by address or owner name to get parcel_id, lat/long, and assessed_value (and market_value
   if available -- I's evaluator logic accepts assessed_value OR market_value, confirm this before assuming you need
   both).
3. For 022025CA000108CAAXMX(fc): use its existing real address directly to search Baker PA for parcel_id/lat-long/
   value (skip the clerk-lookup step, you already have the address).
4. For 022026CA000007CAAXMX(fc): use its existing parcel_id directly against Baker PA's GIS to get lat/long (you
   already have parcel_id/address/assessed_value).
5. After populating parcel_id/address/value for any row: call public.refresh_parity_tier1_outcomes('baker') via the
   SQL endpoint to flip parity_status/parity_source to matched_clean/tier1%% -- never hand-write those columns.
6. For the 2 J-gap rows (022025CA000002CAAXMX, 022025CC000132CCAXMX): after backfilling real data in step 2, check
   whether bid_decisions now has a row for them (a nightly/hourly job may pick it up automatically). If not after a
   reasonable wait, manually invoke the existing generator function(s) for those 2 case numbers.
7. Where a real property record cannot be found for a case (case number is fake/malformed, or the source has no
   record), leave it and report as residual -- do not fabricate parcel_id, address, coordinates, or value.
8. Re-run pencil_dod_evaluate_county('baker') and report the real before/after C/D/E/I/J metrics (baker has only
   17 total rows so each single row fixed moves the percentage by ~5.9 points -- be precise about exactly which
   case numbers you resolved). Log gold_standard_ultraloop_audit for each letter you moved.

${RECIPE}`,
  },
  {
    key: 'suwannee_audit_freshness',
    county: 'suwannee',
    letters: ['A', 'E', 'G', 'H'],
    prompt: `You are working Gold Standard shard-5, county "suwannee", dispatch ${DISPATCH_ID}, inside the
cli-anything-biddeed repo (already checked out, on main).

IMPORTANT -- this county needs NO DATA FIXES. Live baseline (VERIFIED this session via
pencil_dod_evaluate_county('suwannee')): 10/10, ALL letters PASS (A: fc=4 td=31; B: verified=4 closed_sold=4/100%%;
C: matched_clean=35/100%%; D: matched_any=35/100%%; E: parcel_linked=35/100%%; F: tier1_sold=4 closed_sold=4/100%%;
G: density=100 far=100 pk1000=100; H: 0.0h; I: card_complete=35 of 35/100%%; J: deal_complete=35/100%%). This
CONTRADICTS the stale campaign-brief numbers you may see referencing suwannee at 7/10 with B/I/J failing -- those
were fixed by an earlier session TODAY (2026-08-07, audit rows exist from ~08:56 and ~15:19 UTC). Trust the live
evaluator call you make yourself, not the brief.

THE REAL GAP -- certification is blocked by AUDIT FRESHNESS, not by metrics. Per this campaign's SQL CERTIFY GATE
rule, gold_standard_certify() requires survived=true rows in gold_standard_ultraloop_audit for ALL 10 letters within
a 7-day rolling window. VERIFIED this session via a direct query: letters B, C, D, F, I, J already have fresh
survived=true rows from TODAY. Letters A, E, G, H have NOT been touched since 2026-07-20 / 2026-07-24 -- outside the
7-day window as of today 2026-08-07 -- so certification is blocked purely on paperwork despite the county being
genuinely 10/10 live.

YOUR JOB (lightweight, no data changes expected):
1. Independently re-verify each of A, E, G, H against live data yourself (do not just trust the cached scoreboard
   value) -- run the underlying evaluator logic or spot-check: A = count of foreclosure + tax_deed rows both > 0
   for suwannee (confirm via a direct COUNT with the evaluator's exact propertyonion-exclusion filter); E = COUNT
   parcel_id IS NOT NULL / COUNT(*) >= 95%% (again with the exact filter); G = re-query
   v_zoning_gold_standard_kpi_v3 for suwannee and confirm density/far/pk1000 are still all >= 95%%; H = confirm
   MAX(last_changed_at/last_seen_at/scraped_at/scrape_timestamp/created_at) is within the last 48 hours.
2. If all 4 genuinely still pass (expected outcome): INSERT one gold_standard_ultraloop_audit row per letter
   (A, E, G, H) with claim describing the fresh re-verification and the real numbers you got, refuter_evidence
   containing your actual query output, survived=true, dispatch_id='${DISPATCH_ID}', ultraloop_mode='fallback',
   county_slug='suwannee'.
3. If ANY of A/E/G/H has actually regressed since last checked (unlikely but check honestly), report it plainly as
   a FAIL and do not fabricate a survived=true row -- flag it for a real fix in a future session instead.
4. Also spot-check that B/C/D/F/I/J (already freshly audited today by an earlier session) have not regressed as a
   side effect of anything else running today -- one fresh pencil_dod_evaluate_county('suwannee') call covers this,
   paste the full result.
5. Report the complete current audit-freshness state (which letters have a survived=true row within 7 days,
   post-your-work) so the close-out step knows whether suwannee is now eligible for the loop's automatic
   certification (2 consecutive 10/10 daily 07:30Z runs, per campaign rules -- you do not trigger certification
   yourself, just clear the audit-freshness blocker).

${RECIPE}`,
  },
]

phase('Fix')
const fixResults = await pipeline(
  WORK_ITEMS,
  (item) => agent(item.prompt, {
    label: `fix:${item.key}`,
    phase: 'Fix',
    isolation: 'worktree',
    schema: {
      type: 'object',
      properties: {
        work_item: { type: 'string' },
        county: { type: 'string' },
        letters_touched: { type: 'array', items: { type: 'string' } },
        fix_summary: { type: 'string' },
        sql_or_endpoints_used: { type: 'array', items: { type: 'string' } },
        before_json: {},
        after_json: {},
        residual_gaps: { type: 'array', items: { type: 'string' } },
        honesty_notes: { type: 'array', items: { type: 'string' } },
      },
      required: ['fix_summary', 'before_json', 'after_json'],
    },
  })
)

phase('Verify')
const verified = await pipeline(
  fixResults.filter(Boolean),
  (result) => {
    const county = result.county
    const letters = (result.letters_touched && result.letters_touched.length) ? result.letters_touched.join('/') : '(see result)'
    const label = result.work_item || `${county}-${letters}`
    return agent(
      `Independently verify this claimed Gold Standard fix for shard-5 work item "${label}" (county "${county}", letters ${letters}). You did NOT write this fix -- be skeptical.\n\n` +
      `Claimed result: ${JSON.stringify(result)}\n\n` +
      `${RECIPE}\n\n` +
      `Your job: re-run pencil_dod_evaluate_county('${county}') yourself RIGHT NOW (fresh call, do not trust the pasted after_json), ` +
      `compare against the claimed before/after, and check specifically for: (a) denominator mismatches (the propertyonion-exclusion filter ` +
      `must match what the claim used), (b) ghost-success (any letter now passing because of a placeholder/fabricated/default value rather ` +
      `than a real fix -- for pinellas_i specifically, spot-check that the 4 suspicious lat=27.9/value=150000 rows were genuinely resolved or ` +
      `honestly left as residual, NOT silently left in place while claiming I moved; for osceola_g, spot-check the parking_per_1000sf/max_far ` +
      `values against the cited ordinance URL/section yourself; for osceola_i, spot-check 2-3 of the claimed full-STRAP resolutions actually ` +
      `resolve via gis.osceola.org and aren't reused/guessed, and confirm G did not regress from any new zoning_districts row created; for ` +
      `baker_cdeij, verify the tier1_baker_realforeclose_bakerpa_v1 parity rows genuinely resolve to real Baker PA records, not reused/guessed ` +
      `values, and that no case number was fabricated; for suwannee_audit_freshness, confirm the audit rows the agent inserted actually have ` +
      `real query evidence in refuter_evidence, not a rubber-stamp), (c) whether any OTHER letter for this county regressed as a side effect ` +
      `(always check the full A-J JSON, not just the targeted letters -- this campaign has a documented precedent of an I-fix accidentally ` +
      `regressing G via a zone_code hyphenation mismatch), (d) for C/D specifically the only valid PASS reflects parity_source LIKE 'tier1%%', ` +
      `not just parity_status being set. Also INSERT your own gold_standard_ultraloop_audit row per the RECIPE (ultraloop_mode='fallback'). ` +
      `Return { work_item, county, refuted: boolean, refutation_reason: string|null, fresh_evaluation: <the JSON you just got>, survives: boolean }.`,
      {
        label: `verify:${county}:${letters}`,
        phase: 'Verify',
        schema: {
          type: 'object',
          properties: {
            work_item: { type: 'string' },
            county: { type: 'string' },
            refuted: { type: 'boolean' },
            refutation_reason: { type: ['string', 'null'] },
            fresh_evaluation: {},
            survives: { type: 'boolean' },
          },
          required: ['refuted', 'fresh_evaluation', 'survives'],
        },
      }
    )
  }
)

return { fixResults, verified }
