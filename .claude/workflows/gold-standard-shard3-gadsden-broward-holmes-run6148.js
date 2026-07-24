export const meta = {
  name: 'gold-standard-shard3-gadsden-broward-holmes-run6148',
  description: 'Gold Standard shard-3 (gadsden/broward/holmes, loop run 6148): broward I/J mechanical backfill via existing scripts, gadsden I spatial-GIS research for 10 zone-unlinked parcels, holmes B/C/D/F freshness recheck, adversarially verify all',
  phases: [
    { title: 'Apply', detail: 'parallel per-county tracks: broward (scripts), gadsden (GIS research then apply), holmes (recheck)' },
    { title: 'Verify', detail: 'independent refuters per county, re-check live DB' },
  ],
}

const DISPATCH_ID = '0f64d3fa-6878-48ac-b4d6-cb070032beab'

const SHARED_TOOLS = `
Environment (already available, no credentials needed):
- Live arbitrary SQL: POST https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query
  headers Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json, body {"query": "<sql>"}.
  Build the JSON body with python3 -c "import json..." to a temp file, then curl --data-binary @file -- do not
  hand-quote SQL containing single quotes into a shell -d string.
- REST reads/writes: \${SUPABASE_URL}/rest/v1/<table> with headers apikey / Authorization: Bearer
  $SUPABASE_SERVICE_ROLE_KEY.
- pencil_dod_evaluate_county RPC (before/after proof): POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county
  body {"p_county": "<county>"}.
- Repo root is cwd, on main. gh CLI is authenticated for git commit/push (repo, workflow scopes).
- git pull --rebase origin main BEFORE every push (other shards are pushing to main concurrently). Push directly
  to main, no branches, no PRs.
- You own ONLY your assigned county. NEVER touch another county's rows, or shared cron jobs 109/111/115, or any
  gold-standard-loop-* scoring job. Do NOT run public.gold_standard_loop() or gold_standard_certify() (other
  shards may be mid-session).

ULTRALOOP audit logging (mandatory): for every letter you claim moved (or claim re-confirmed still-blocked),
INSERT one row into public.gold_standard_ultraloop_audit: dispatch_id (uuid '${DISPATCH_ID}'), ultraloop_mode
('fallback' -- this session used manual Task subagent fan-out via the Workflow tool, not native /effort ultracode
toggle), county_slug, letter, claim (short text with before/after numbers), refuter_evidence (jsonb -- your
before/after evidence), survived (boolean, your own self-assessment; a separate Verify agent will independently
re-check you). POST \${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with the service-role headers above.

Hard rules (BLANK > WRONG):
- Fail-loud: if you can't source a real value, leave it NULL and say so. NEVER fabricate a zone code, parcel_id,
  assessed value, coordinate, or ml_score/CMA input to make a metric look better. This campaign has a documented
  history of exactly this failure mode (ghost-success ARV/max_bid/ml_score buckets, fake fallback lat/lon
  26.1224/-80.1373 for broward) -- do not repeat it.
- Every claim must be tagged VERIFIED (you ran the query/request, paste real output), UNTESTED, or INFERRED
  (say why).
- Schema/data changes: write a migration file under supabase/migrations/ for the historical record AND apply
  live via the Management API / REST in the SAME session (files-only is not shipped, per SHIP GATE).
- PropertyOnion is litmus/comparison ONLY -- never write po_*-derived values in as verified/independent.`

const BROWARD_BASELINE = `LIVE at session start (dispatch 0f64d3fa, VERIFIED via pencil_dod_evaluate_county('broward')):
auctions_total=664. A/B/D/E/F/G/H PASS. C was FAIL (94.7%, matched_clean=629) -- ALREADY FIXED this session
(before this workflow ran) by re-running the existing refresh_broward_parity_v1() SQL function with NO code
change: it picked up 3 already-scraped-but-unmatched foreclosure cases (CACE-24-011211, CACE-25-005443,
CACE-23-021250) already present in realforeclose_aids. matched_clean 629->632, metric 94.7->95.2, now PASS.
This has ALREADY been logged to gold_standard_ultraloop_audit (letter C, survived=true) -- do NOT redo this or
re-claim credit for it; your job is ONLY I and J below. Re-verify C is still passing as a side-effect check but
do not touch its mechanism.

I FAIL metric=93.2 [card_complete=619 of 664, need >=631]. Exact gap decomposition (VERIFIED live query against
the evaluator's own card_complete boolean -- property_address IS NOT NULL AND lat/lon present AND
assessed_value/market_value present AND parcel_id resolves to a zone_code via v_zoning_gold_standard_card), 45
failing rows grouped by exactly which field(s) are missing:
  - MISSING ONLY assessed_value/market_value (12 rows): CACE-18-021548, CACE-19-015217, CACE-20-015165,
    CACE-24-009692, CACE-25-005297, CACE-25-005705, CACE-25-007074, CACE-25-013872, and 4 more (query fresh --
    "SELECT case_number FROM multi_county_auctions WHERE lower(county)='broward' AND ... val IS NULL AND
    property_address IS NOT NULL AND lat/lon present AND zone_linked" to get the exact 12).
  - MISSING ONLY zone linkage (2 rows): CACE-25-007347, CACE-25-008008 -- these already have address+geo+value,
    just need a parcel_zones row (or their existing parcel_zones row's zone_code needs a zoning_districts match).
  - MISSING lat/lon + val + zone together (11 rows), MISSING ONLY lat/lon (10 rows), MISSING address+val (6
    rows), MISSING address+val+zone (3 rows), MISSING lat/lon+val only (1 row) -- lower priority, address-missing
    rows likely need a source lookup by case_number/legal description first.
  MATH: 664 total, need >=631 (95%) card_complete, currently 619. Fixing the 12-val-only + 2-zone-only groups
  alone = +14 = 633/664 = 95.3% -- PASSES. Prioritize those 14 first; the other 31 are bonus/lower-confidence.

J FAIL metric=94.6 [deal_complete=628 of 664, need >=631]. VERIFIED live: ALL 36 gap rows are missing a
bid_decisions row ENTIRELY (not partial -- no row exists at all for these case_numbers): CACE-16-002149,
CACE-18-021548, CACE-19-015217, CACE-20-015165, CACE-20-018707, CACE-22-015602, CACE-23-021250, CACE-24-004661,
CACE-24-009692, CACE-24-011211, CACE-25-001698, CACE-25-002454, CACE-25-005297, CACE-25-005443, CACE-25-005705,
CACE-25-007074, CACE-25-009971, CACE-25-010544, CACE-25-010548, CACE-25-011341, CACE-25-013872, CACE-25-014151,
CACE-25-016380, CACE-25-016631, CACE-25-017767, CACE-25-017818, CACE-25-018558, CACE-26-000767, COCE-25-001068,
COCE-25-030130, COCE-25-047596, COCE-25-080423, CONO-24-073504, COWE-25-036881, COWE-25-067830, COWE-26-021926.
Need only 3 more of these 36 to reach 631/664=95.0% PASS (631 is the razor edge -- aim for as many of the 36 as
the real Shapira pipeline can actually score, do not stop at exactly 3).`

const BROWARD_TOOLS = `
County-specific tools already in the repo (READ THEM FIRST, do not rebuild):
- scripts/broward_i_value_enrichment.py -- fetches REAL assessed_value/market_value from web.bcpa.net (Broward
  Property Appraiser public endpoint) for rows with a real 12-digit(+2 alpha) folio parcel_id and PATCHes them.
  Currently filters on data_source=eq.realforeclose -- if any of the 12 val-only-missing rows have a different
  data_source, either broaden the script's filter (still BCPA-sourced, still real) or write a small equivalent
  follow-up call for those specific case_numbers using the same BCPA endpoint pattern. Run it:
  python3 scripts/broward_i_value_enrichment.py
- scripts/gold_standard_shard9_broward_alachua_j_generator_real.py -- the REAL Shapira V14 XGBoost J generator
  (COUNTIES=["broward","alachua"], idempotent, only targets rows currently missing arv/max_bid/ml_score/factor
  keys -- matches pencil_dod_evaluate_county's deal_complete definition exactly). Run it:
  python3 scripts/gold_standard_shard9_broward_alachua_j_generator_real.py
  Needs parcel_valuations comps (from gen_valuations_comps_batch, cron 109 -- do NOT modify that cron) for a real
  ARV; rows with zero real ARV source (no comp, no assessed_value, no market_value) are correctly left
  incomplete per the script's own docstring -- do not force them.
- For the 2 zone-only-missing I rows (CACE-25-007347, CACE-25-008008): SELECT their parcel_id + any existing
  parcel_zones row first; if parcel_zones has a row but zone_code has no zoning_districts match for that
  jurisdiction, either INSERT the missing zoning_districts row (ordinance-sourced, cite it) or confirm via BCPA's
  landCalcZoning field / municipal GIS what the real code should be. Do not fabricate.
${SHARED_TOOLS}`

const GADSDEN_BASELINE = `LIVE at session start (dispatch 0f64d3fa, VERIFIED via pencil_dod_evaluate_county('gadsden')):
auctions_total=23. Only I fails: metric=56.5 (card_complete=13 of 23, need >=22/23=95.7%). VERIFIED via a direct
per-row query reproducing the evaluator's card_complete boolean: ALL 23 rows already have property_address +
lat/lon + assessed_value present -- the ENTIRE gap is zone-linkage (parcel_id resolving to a zone_code via
v_zoning_gold_standard_card). The 13 passing rows are ALL in jurisdiction_id=1474 "Unincorporated Gadsden County"
(13 parcel_zones rows exist there, zero in any municipality). The 10 failing rows have ZERO parcel_zones rows at
all (VERIFIED: direct query against parcel_zones for these exact 10 parcel_ids returned 0 rows) -- this needs new
spatial parcel-to-zone assignment, not a zoning_districts/zone_standards fix (those already exist for Quincy id=925,
Chattahoochee id=1003, Gretna id=1004, Havana id=1005, Midway id=1006, Greensboro id=1007, Unincorporated id=1474).

The 10 gap parcels, with real lat/lon already in our DB (use these directly for point-in-polygon GIS queries,
do NOT need address geocoding):
  23000820CA  2-03-3N-6W-0000-00342-0200  "924 Bethel St, Chattahoochee, FL"       lat=30.6822064 lon=-84.8299329
  25000148CA  3-07-2N-3W-0730-00000-1711  "208 S. Love St, Quincy, FL"             lat=30.5858856 lon=-84.5731865
  25000545CA  1-33-4N-6W-0000-00431-0400  "4 Parcels, Gadsden County, FL"          lat=30.6954484 lon=-84.8405978
  25000696CA  2-03-3N-6W-0000-00213-2300  "Section 3 Township 3 North, Gadsden"    lat=30.6901027 lon=-84.8295779
  25000901CA  3-26-2N-5W-0000-00424-0500  "Section 26 Township 2 North, Gadsden"   lat=30.537212  lon=-84.7039906
  25000942CA  3-19-2N-3W-1559-00000-0030  "1029 Joe Adams Rd, Quincy, FL 32351"    lat=30.5569477 lon=-84.5755808
  26000007TDC 1-33-4N-6W-0080-00006-0050  "520 Pearl St, Chattahoochee, FL"        lat=30.6992827 lon=-84.8501008
  26000009TDC 3-11-2N-4W-0000-00242-0500  "2320 Pavillion Dr, Quincy, FL"          lat=30.5886978 lon=-84.6102376
  26000010TDC 3-12-2N-4W-0980-0000L-0050  "614 Williams St, Quincy, FL"            lat=30.5789146 lon=-84.5942366
  26000011TDC 3-08-2N-3W-0780-0000A-0150  "226 Carver St, Quincy, FL"              lat=30.584623  lon=-84.5640176
Note: 3 of these (25000545CA, 25000696CA, 25000901CA) have vague legal-description "addresses" (no street
address) -- their true jurisdiction (municipal vs unincorporated) is NOT knowable from the mailing text, confirm
it from whatever GIS boundary/jurisdiction layer you find, do not assume unincorporated just because the text
looks rural.

MATH: 23 total, need >=22 card_complete (95.7%). Currently 13. You need AT LEAST 9 of these 10 to resolve to
reach 22/23=95.7% PASS -- this is a high bar, not "any progress counts." If your best real GIS source only
resolves some of the 5 Quincy-address parcels + 2 Chattahoochee-address parcels (7 of 10), that gets to 20/23
=87.0%, STILL FAILS. Report the honest ceiling if you cannot reach 9/10 -- do not force a fabricated match on
the last 1-2 to cross the line.

PRIOR DEAD ENDS (documented in commits 5b029a0d / fdc901f8, do NOT re-try these): Quincy's own branded "ArcGIS
org" search result is actually Quincy, WASHINGTON state, not FL -- a false lead, confirmed and rejected. Wayback
Machine snapshots of Chattahoochee's site are empty. FDOT statewide parcels API returns HTTP 499 (needs a token
we don't have). Zoneomics is paywalled. Using DOR_UC (property-appraiser use-code) as a zoning-district proxy was
deliberately rejected as fabrication (current-use != zoning district) -- do not do this either.
NEW ANGLE NOT YET TRIED: Gadsden County's own GIS/property-appraiser portal (try
gadsdenpa.com, qpublic.schneidercorp.com search for "Gadsden" FL, or Gadsden County's official website GIS page)
may host a COUNTYWIDE parcel + zoning layer that covers municipalities too (many small FL counties host one
shared ArcGIS/Beacon/qPublic GIS for the county AND its cities, distinct from each city's own separate ordinance
text) -- this was not checked by prior sessions (they only checked Quincy's own domain and Chattahoochee's
Municode). Also try a direct web search for "Gadsden County Florida GIS zoning parcel viewer" and check if
Quincy or Chattahoochee's official .gov sites (not Municode) link to a GIS map tool.`

const GADSDEN_TOOLS = `
${SHARED_TOOLS}
- Firecrawl (firecrawl-scrape / firecrawl-map skills) or WebFetch for any JS-rendered county/city GIS viewer page.
- If you find a real ArcGIS REST MapServer/FeatureServer, query it directly via curl with
  ?f=json&geometry={lon},{lat}&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=*&returnGeometry=false
  for each of the 10 coordinates above.
- Write your findings + any INSERTs to supabase/migrations/20260724_gold_standard_shard3_gadsden_i_parcel_zones_backfill.sql`

const HOLMES_BASELINE = `LIVE at session start (dispatch 0f64d3fa, VERIFIED via pencil_dod_evaluate_county('holmes')):
auctions_total=13. A/E/G/H/I/J PASS (already 6/10). B FAIL (null, verified=0 closed_sold=0), C FAIL (61.5%,
matched_clean=8 of 13), D FAIL (61.5%, matched_any=8 of 13), F FAIL (null, tier1_sold=0 closed_sold=0).

THIS IS A REPEATEDLY-CONFIRMED STRUCTURAL CEILING, not fresh territory: at least 8 independent prior sessions
(commits/docs including c6bb4d79, 58be9ee1, 28357764, 8dd3ff18, 11848338, bdd1a47d, db6d5901, 0ba7ed91, 586ab339,
411228b5, 08b75f29) have all reconfirmed the same root cause: Holmes County publishes NO post-sale
disposition/sold-amount data through ANY online channel. holmesclerk.com shows only forward-looking foreclosure
judgment listings, never results; the tax-deed page is a static "no sales scheduled" page. Every alternative
source tried (paywalled sites, an impersonator site, redirect loops, Firecrawl with credits exhausted, GovEase,
realTDM, qPublic 403) has been exhausted across 7+ sessions. The only non-automatable lever found is a manual,
human-authorized surplus-funds email contact (lbryant@holmesclerk.com) -- out of scope for an autonomous session.

YOUR JOB IS NARROW: do a FRESH, LIVE re-check (do not trust old findings blindly, they could be stale) of:
  1. holmesclerk.com -- does it now publish ANY sold-amount / disposition data for foreclosure or tax-deed cases?
  2. Firecrawl credit balance -- is it still exhausted, or has it refreshed (would open new scraping options)?
  3. Any of the 13 closed_sold candidates in multi_county_auctions for holmes -- spot check 2-3 case numbers
     directly against holmesclerk.com's public case search to triple-confirm no result page exists.
If truly nothing has changed, do NOT spend the session budget re-deriving this from scratch -- confirm it, log
one clean ultraloop_audit row per letter (B, C, D, F) with survived=true meaning "the blocked-finding survives",
and stop. If you DO find something genuinely new (a working source, a credit refresh that unblocks Firecrawl),
pursue it and attempt a real fix.`

const HOLMES_TOOLS = `${SHARED_TOOLS}`

phase('Apply')
const [browardResult, gadsdenResult, holmesResult] = await parallel([
  async () => {
    const applied = await agent(
      `Apply the Gold Standard shard-3 fix for broward county's I and J letters (C was already fixed this ` +
      `session, do not touch it). Use the EXISTING scripts documented below -- do not rebuild them from ` +
      `scratch.\n\n${BROWARD_BASELINE}\n\n${BROWARD_TOOLS}\n\n` +
      `Steps: (1) get exact fresh gap lists from a live query (case numbers may have shifted slightly since ` +
      `this baseline was written a few minutes ago). (2) run broward_i_value_enrichment.py for the val-only ` +
      `gap. (3) resolve the 2 zone-only I gap rows. (4) run the J generator script for as many of the 36 gap ` +
      `case_numbers as have a real ARV source. (5) re-run pencil_dod_evaluate_county('broward') fresh and paste ` +
      `the JSON. (6) write your migration file for the historical record, insert ultraloop_audit rows for I and ` +
      `J, git pull --rebase origin main, commit, push to main directly.\n\nReturn your report in the schema.`,
      {
        label: 'apply:broward',
        phase: 'Apply',
        isolation: 'worktree',
        schema: {
          type: 'object',
          properties: {
            county: { type: 'string' },
            letters_touched: { type: 'array', items: { type: 'string' } },
            fix_summary: { type: 'string' },
            before_json: {}, after_json: {},
            residual_gaps: { type: 'array', items: { type: 'string' } },
            honesty_notes: { type: 'array', items: { type: 'string' } },
            migration_file: { type: 'string' },
            git_pushed: { type: 'boolean' },
          },
          required: ['county', 'fix_summary', 'before_json', 'after_json'],
        },
      }
    )
    const verified = await agent(
      `Independently, adversarially verify this claimed Gold Standard fix for broward county (I and J letters). ` +
      `You did NOT write this fix -- be skeptical. Your #1 job is to catch ghost-success: fabricated ARV/max_bid/` +
      `ml_score values (check for suspiciously identical values across dissimilar properties -- this campaign's ` +
      `documented fabrication signature), fabricated assessed_value/coordinates, or a J row that has the 5 ` +
      `factor keys but with degenerate/constant content.\n\n` +
      `Claimed result: ${JSON.stringify(applied)}\n\n${BROWARD_BASELINE}\n\n${BROWARD_TOOLS}\n\n` +
      `Do this: (1) re-run pencil_dod_evaluate_county('broward') yourself RIGHT NOW, fresh. (2) spot-check at ` +
      `least 3 of the newly-written bid_decisions rows and 3 of the newly-written assessed_value/market_value ` +
      `rows against their real source (BCPA folio lookup, Shapira model inputs) to confirm they are not ` +
      `fabricated or duplicated. (3) confirm C/A/B/D/E/F/G/H did not regress. (4) insert your own ` +
      `gold_standard_ultraloop_audit rows for I and J (survived=your independent verdict). Return ` +
      `{ county, refuted, refutation_reason, fresh_evaluation, survives, spot_checks } in the schema.`,
      {
        label: 'verify:broward',
        phase: 'Verify',
        schema: {
          type: 'object',
          properties: {
            county: { type: 'string' }, refuted: { type: 'boolean' },
            refutation_reason: { type: ['string', 'null'] }, fresh_evaluation: {},
            survives: { type: 'boolean' }, spot_checks: { type: 'array', items: { type: 'string' } },
          },
          required: ['county', 'refuted', 'fresh_evaluation', 'survives'],
        },
      }
    )
    return { applied, verified }
  },
  async () => {
    const applied = await agent(
      `Research AND apply (single session) the Gold Standard shard-3 fix for gadsden county's I letter (the ` +
      `only failing letter, 56.5%, need >=95.7%). This requires real spatial parcel-to-zoning-district data for ` +
      `10 specific parcels -- read the prior-session dead-ends carefully so you don't repeat wasted work, and ` +
      `try the one genuinely new angle (Gadsden County's own countywide GIS/property-appraiser portal).\n\n` +
      `${GADSDEN_BASELINE}\n\n${GADSDEN_TOOLS}\n\n` +
      `Steps: (1) find a real, live Gadsden County / Quincy / Chattahoochee parcel-zoning GIS source (ArcGIS ` +
      `REST, Beacon, qPublic, or similar) -- verify it actually covers Florida's Gadsden County, not a same-` +
      `named place elsewhere. (2) for each of the 10 coordinates, query it and get the real zone code + confirm ` +
      `jurisdiction. (3) INSERT parcel_zones rows (and zoning_districts/zone_standards rows if a code doesn't ` +
      `exist yet, ordinance-sourced only) for whatever real matches you get -- do NOT fabricate any you can't ` +
      `source. (4) re-run pencil_dod_evaluate_county('gadsden') fresh and paste the JSON -- be honest if you ` +
      `land short of the 22/23 threshold, report the real ceiling and which specific parcels remain unresolved ` +
      `and why. (5) write your migration file, insert ultraloop_audit row(s) for I, git pull --rebase origin ` +
      `main, commit, push to main directly.\n\nReturn your report in the schema.`,
      {
        label: 'apply:gadsden',
        phase: 'Apply',
        isolation: 'worktree',
        schema: {
          type: 'object',
          properties: {
            county: { type: 'string' },
            letters_touched: { type: 'array', items: { type: 'string' } },
            fix_summary: { type: 'string' },
            source_found: { type: ['string', 'null'] },
            resolved_count: { type: ['number', 'null'] },
            before_json: {}, after_json: {},
            residual_gaps: { type: 'array', items: { type: 'string' } },
            honesty_notes: { type: 'array', items: { type: 'string' } },
            migration_file: { type: 'string' },
            git_pushed: { type: 'boolean' },
          },
          required: ['county', 'fix_summary', 'before_json', 'after_json'],
        },
      }
    )
    const verified = await agent(
      `Independently, adversarially verify this claimed Gold Standard fix for gadsden county (I letter). You ` +
      `did NOT write this fix -- be skeptical. Confirm any new parcel_zones/zoning_districts rows trace to a ` +
      `REAL GIS response or ordinance citation you can independently fetch yourself (paste what you see), not a ` +
      `guessed code. Watch specifically for the "Quincy is actually in Washington state" false-lead pattern ` +
      `documented in the baseline -- if the claimed source is not verifiably Gadsden County, Florida, REFUTE it.` +
      `\n\nClaimed result: ${JSON.stringify(applied)}\n\n${GADSDEN_BASELINE}\n\n${GADSDEN_TOOLS}\n\n` +
      `Do this: (1) re-run pencil_dod_evaluate_county('gadsden') yourself RIGHT NOW, fresh. (2) independently ` +
      `fetch the claimed GIS source yourself for at least 2 of the resolved coordinates and confirm the zone ` +
      `code matches what was written to the DB. (3) confirm E/other letters did not regress. (4) insert your ` +
      `own ultraloop_audit row for I (survived=your independent verdict). Return ` +
      `{ county, refuted, refutation_reason, fresh_evaluation, survives, spot_checks } in the schema.`,
      {
        label: 'verify:gadsden',
        phase: 'Verify',
        schema: {
          type: 'object',
          properties: {
            county: { type: 'string' }, refuted: { type: 'boolean' },
            refutation_reason: { type: ['string', 'null'] }, fresh_evaluation: {},
            survives: { type: 'boolean' }, spot_checks: { type: 'array', items: { type: 'string' } },
          },
          required: ['county', 'refuted', 'fresh_evaluation', 'survives'],
        },
      }
    )
    return { applied, verified }
  },
  async () => {
    const applied = await agent(
      `Do a FRESH, LIVE re-check of holmes county's B/C/D/F blocker (see baseline -- this is a repeatedly-` +
      `confirmed dead end across 8+ prior sessions, your job is a quick honest re-verification, NOT new deep ` +
      `research).\n\n${HOLMES_BASELINE}\n\n${HOLMES_TOOLS}\n\nReturn your report in the schema -- if genuinely ` +
      `nothing has changed, say so plainly and insert the 4 ultraloop_audit rows (B, C, D, F, survived=true ` +
      `meaning the blocked-finding survives) with your fresh check as refuter_evidence. If you find something ` +
      `new, describe it and, if it's a quick real fix, apply it (migration + live write + re-evaluate + git ` +
      `push to main).`,
      {
        label: 'apply:holmes',
        phase: 'Apply',
        schema: {
          type: 'object',
          properties: {
            county: { type: 'string' },
            still_blocked: { type: 'boolean' },
            fresh_check_notes: { type: 'array', items: { type: 'string' } },
            new_finding: { type: ['string', 'null'] },
            fix_applied: { type: 'boolean' },
            before_json: {}, after_json: {},
            git_pushed: { type: ['boolean', 'null'] },
          },
          required: ['county', 'still_blocked', 'fresh_check_notes'],
        },
      }
    )
    const verified = await agent(
      `Independently verify this holmes county B/C/D/F re-check. If it claims still-blocked, spot-check ONE ` +
      `holmesclerk.com case search yourself to confirm no disposition data appears, and confirm Firecrawl credit ` +
      `status independently. If it claims a fix was applied, adversarially verify it the same way other letters ` +
      `in this campaign are verified (re-run pencil_dod_evaluate_county('holmes') fresh, check for fabrication).` +
      `\n\nClaimed result: ${JSON.stringify(applied)}\n\n${HOLMES_BASELINE}\n\n${HOLMES_TOOLS}\n\nReturn ` +
      `{ county, refuted, refutation_reason, fresh_evaluation, survives, spot_checks } in the schema.`,
      {
        label: 'verify:holmes',
        phase: 'Verify',
        schema: {
          type: 'object',
          properties: {
            county: { type: 'string' }, refuted: { type: 'boolean' },
            refutation_reason: { type: ['string', 'null'] }, fresh_evaluation: {},
            survives: { type: 'boolean' }, spot_checks: { type: 'array', items: { type: 'string' } },
          },
          required: ['county', 'refuted', 'fresh_evaluation', 'survives'],
        },
      }
    )
    return { applied, verified }
  },
])

return { browardResult, gadsdenResult, holmesResult }
