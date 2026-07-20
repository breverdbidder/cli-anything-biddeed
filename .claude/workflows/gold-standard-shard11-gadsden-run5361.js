export const meta = {
  name: 'gold-standard-shard11-gadsden-run5361',
  description: 'Gold Standard shard-11 gadsden (dispatch 52bf028c, loop run 5361): E parcel disambiguation via court docket + chattel-property check, I municipal zoning new-source attempt, H freshness rewire',
  phases: [
    { title: 'Diagnose+Fix', detail: 'one agent per item, worktree-isolated' },
    { title: 'Verify', detail: 'independent refuter per claim' },
  ],
}

const DISPATCH_ID = '52bf028c-78fe-49ad-ae77-284c02a1f201'

const ITEMS = [
  {
    key: 'gadsden_E_901CA',
    county: 'gadsden',
    context: `CONTEXT (read carefully -- this exact row has been researched by 3+ prior sessions, do not repeat
their dead ends): gadsden auction case 25000901CA (foreclosure, plaintiff "JLT Mortgage", defendant "Ramon's
Construction", property legal description on file is only "Section 26, Township 2 North, Gadsden County, FL",
judgment $56,245.27) has NULL parcel_id -- this is 1 of gadsden's 2 remaining E-gap rows (E is at 21/23=91.3%,
needs a real linked+zoned parcel on at least one of the 2 gaps to reach 22/23=95.65% and PASS).

ALREADY CONFIRMED DEAD (do not re-try): (a) qpublic.schneidercorp.com owner-name search -- 403 via plain HTTP
AND via real non-stealth headless Chromium (Cloudflare "Just a moment..." managed challenge, confirmed 2
independent methods). (b) fl_parcels (our own already-ingested table, WHERE co_no=30 -- confirmed empirically
this session that co_no=30 is gadsden's real code in fl_parcels, NOT co_no=20 which some jurisdictions rows use)
WHERE own_name ILIKE '%RAMON%' returns exactly 2 candidates, both "RAMONS CONSTRUCTION SERVICES L", both vacant
land (dor_uc=000, jv=$6200, lnd_val=$6200, lnd_sqfoot=43560, no buildings), both on RIDGEWOOD RD, parcel_ids
3-26-2N-5W-0000-00424-0500 and 3-26-2N-5W-0000-00424-1000 -- the section/township/range in both parcel_ids
(26-2N-5W) matches the case's own PLSS description exactly, confirming this IS the right owner/area, but the two
parcels are functionally identical (same owner, same land value, same lot size, adjacent) with NO signal in
fl_parcels to tell them apart. A prior session (scripts/shard7_run3679_gadsden_e_fix.py) already found and
recorded this exact same 2-parcel ambiguity and correctly declined to guess. Both parcels' municipality field is
"COUNTY" (unincorporated) -- meaning if EITHER is correctly identified, it auto-qualifies for the gadsden
Unincorporated RR/AG-1/AG-2 zoning already established (jurisdiction_id 1474, see
migrations/20260719_gold_standard_shard13_gadsden_uninc_rr_ag_verified.sql) -- likely AG-1 or AG-2 given the
~1-acre vacant-land profile, so resolving E here would very plausibly also make this row card_complete for I.

YOUR JOB -- try genuinely NEW angles not yet attempted on this specific case:
1. The clerk's summary sale sheet (gadsdenclerk.com/Foreclosures/Foreclosures_files/sheet001.htm, reachable with
   a real browser User-Agent per a prior session's finding -- plain curl/urllib gets 403, a realistic
   Mozilla/Chrome UA string gets 200) only has 6 columns (Sale Date/Case#/Plaintiff/Defendant/Address/Judgment) --
   no legal description with lot/parcel specificity. The actual court FILE (the foreclosure complaint or the
   final judgment) would cite the SPECIFIC legal description (likely referencing one of the two parcel numbers
   or a plat/lot reference) -- try to find Gadsden County's civil case docket / official court record search
   (search live for it, e.g. a Clerk "eCourt"/"OCRS"/case-search portal, or the Florida Courts e-Filing Portal's
   public docket view for case 25000901CA in the 2nd Judicial Circuit) and see if a docket entry or an attached
   document (Notice of Lis Pendens is often filed with the full legal description and is commonly public even
   when full case files require login) is retrievable. Do not guess a URL -- verify it resolves and actually
   shows this case before trusting it.
2. Check if ToolSearch surfaces a firecrawl MCP tool (query "firecrawl scrape") -- a prior session (2026-07-19,
   same day) found Firecrawl at 0 remaining credits; check again, credits may have refilled since.
3. Check the Gadsden County Property Appraiser's site by a DIFFERENT vendor path than qpublic if one exists
   (search live -- do not assume qpublic is the only appraiser portal; some FL county appraisers publish a
   separate GIS/parcel-search tool alongside qpublic).
4. If, after genuinely trying the above, you still cannot disambiguate between the 2 parcels with a real,
   specific signal (not "pick the lower ID" or similar): do NOT guess. Report this row as still-ambiguous,
   confirmed via [whatever new method you tried], and move to reporting a residual gap.`,
  },
  {
    key: 'gadsden_E_942CA',
    county: 'gadsden',
    context: `CONTEXT: gadsden auction case 25000942CA (foreclosure, plaintiff "21st Mortgage", defendant "Woods",
property description on file "2021 Live Oak Manufactured Home, Gadsden County, FL", judgment $139,477.73,
auction_date 2026-07-02) has NULL parcel_id -- this is gadsden's OTHER E-gap row. Auction_status in our DB
currently still says "upcoming" with a past auction_date, which looks stale/wrong -- a prior session (2026-07-19)
found this case had already dropped off the live clerk sale sheet (interpreted then as "already sold"); this may
be worth a quick fresh check of its current status too, but that is secondary to the parcel-linkage question below.

ALREADY CONFIRMED DEAD for a plain surname match (do not re-run this exact query): fl_parcels WHERE co_no=30 AND
own_name ILIKE '%WOODS%' returns 16 distinct real "Woods"-surnamed owners across Quincy/Chattahoochee/Midway/
unincorporated county, none with an address containing "Live Oak", 2 with dor_uc='002' (mobile-home use code --
WOODS TEMEKA at 187 Tyler Sanders Rd, WOODS ROSELIND at 215 Blind Brook Rd) but neither is a confirmed match, and
no first name for the defendant is on file anywhere in our DB (only the bare surname "Woods" was ever captured,
per scripts/shard8_gadsden_bootstrap.py's original ingestion comment). qpublic owner search is the same
confirmed-403 dead end as the 901CA item above.

A NEW HYPOTHESIS worth investigating first (has NOT been checked by any prior session): the plaintiff "21st
Mortgage Corporation" is a well-known specialist lender for MANUFACTURED/MOBILE homes financed as PERSONAL
PROPERTY (chattel, titled like a vehicle through FLHSMV) rather than as real property attached to land -- this is
common when the home sits on a rented lot in a mobile-home park or on land the borrower doesn't own. If that is
the case here, there may be NO real-property parcel_id to link at all -- this would be a real, structural,
non-fixable characteristic of the underlying collateral, not a scraping gap. Investigate: (a) does the case
docket/complaint (if reachable, same portals as the 901CA item) describe this as a chattel/personal-property
foreclosure/replevin rather than a mortgage foreclosure on real property? (b) does "Live Oak" refer to a known
mobile-home park or subdivision name in Gadsden County (search live) that would confirm a rented-lot scenario? If
you confirm this is a chattel case with no underlying real-property parcel, report that explicitly and precisely
-- it is a legitimate, valuable, honest finding (not a residual "still trying"), and flag it for the AI Architect
to consider whether this case belongs in the real-estate-auction pipeline at all (do NOT unilaterally remove or
reclassify the row yourself -- that changes other letters' denominators and is out of your scope).
If it turns out to genuinely be real property after all, then and only then try to further narrow the 16 "Woods"
candidates with any address/park-name signal you found. Do NOT guess between multiple candidates without a real
disambiguating signal.`,
  },
  {
    key: 'gadsden_I_municipal_zoning',
    county: 'gadsden',
    context: `CONTEXT: gadsden I is at 56.5% (13 of 23 card_complete) -- structurally capped below the 95% PASS
threshold this session regardless of what you do here (max achievable via this item alone is 21/23=91.3%,
because I's denominator is ALL 23 auctions and 2 have no parcel_id at all -- that is the E items' scope, not
yours). Of the 21 parcel-linked auctions, 13 are already zoned (unincorporated RR/AG-1/AG-2, PASSING G and
contributing to I). The remaining 8 sit inside Quincy/Chattahoochee/Havana city limits and have NO per-parcel
municipal zoning source in this DB at all.

ALREADY CONFIRMED DEAD (do not re-search these, exhaustively covered across 4+ prior sessions): qpublic.net/fl/
gadsden and qpublic.schneidercorp.com (Cloudflare 403, both plain HTTP and real headless Chromium methods),
gadsdencountyfl.gov and maps.gadsdencountyfl.gov (domain-wide Akamai 403 WAF block, confirmed via real headless
browser too), library.municode.com/fl/gadsden_county (loads fine but has NO Zoning/Land Development chapter --
Chapter 18 Buildings jumps straight to Chapter 20 Economic Development), api.municode.com clientId=5945 search
(NumberOfHits:0, Products endpoint 204 No Content), ArcGIS Online public index searched exhaustively for
"Quincy_Zoning"/"Chattahoochee_Zoning"/similar FeatureServers (none exist), Havana_Zoning_Districts_WFL1 layer 0
(exists but is a road-reference polyline dataset despite its name, not usable, and moot since no auction parcel
is in Havana anyway).

YOUR JOB -- try genuinely NEW angles, specifically NOT yet tried by any prior session:
1. Search live (do not guess a URL) for whether the CITY of Quincy or the Town of Chattahoochee itself (not the
   county) runs its OWN ArcGIS Online organization separate from the county's ARPC-hosted org (the Gadsden_FLUM
   service found previously is hosted under an Apalachee Regional Planning Council org, not a city org) -- e.g.
   search "City of Quincy Florida GIS", "site:hub.arcgis.com quincy florida", "Chattahoochee Florida zoning map".
2. Search for a Wayback Machine (web.archive.org CDX API) snapshot of gadsdencountyfl.gov's planning/zoning pages
   or a static PDF zoning map for Quincy/Chattahoochee -- the same technique that found the LDC Chapter 4 PDF for
   the unincorporated-county fix (prior session, migration 20260719_gold_standard_shard13_gadsden_uninc_rr_ag_
   verified.sql) has not yet been tried specifically for the 2 incorporated cities' own zoning maps/ordinances.
3. Check if ToolSearch surfaces a firecrawl MCP tool (query "firecrawl scrape") for a stealthier fetch of the
   qpublic/gadsdencountyfl.gov WAFs -- confirm current credit balance first (a same-day prior session found 0).
4. If a real, sourced zoning district + ordinance-cited dimensional standards (density/FAR/parking, with
   confidence_score and source_url, NEVER guessed) can be found for Quincy and/or Chattahoochee, and a real
   per-parcel assignment method exists (spatial GIS join or an authoritative address-to-zone lookup tool, not a
   guess), write it. Remember: even a full win here caps I at 21/23=91.3%, still FAIL -- report this honestly as
   real progress toward, not achievement of, a PASS. If genuinely still blocked after these new angles, report
   precisely what you tried and its result -- a confirmed-still-blocked outcome is legitimate and valuable, do
   not force a fabricated zone_code to look like progress.`,
  },
  {
    key: 'gadsden_H_freshness',
    county: 'gadsden',
    context: `CONTEXT: gadsden H (freshness, SLA 48h) is LIVE-FAILING right now at 51.1 hours since last_seen --
this regressed from the dispatch brief's snapshot of 43.4h (PASS) purely from wall-clock drift; nothing scraped
gadsden in between. ROOT CAUSE (verified this session): gadsden's only real data source is a bespoke scraper for
the custom clerk site (gadsdenclerk.com/Foreclosures/Foreclosures_files/sheet001.htm, source_platform=
'custom_clerk') -- it has NEVER been wired to any recurring executor. The two existing daily GHA sweeps that
list gadsden as a covered county (.github/workflows/calendar-sweep-dark-counties.yml, cron 05:15 UTC daily, and
.github/workflows/calendar-sweep-gap-counties.yml) BOTH only query the realauction_subdomains table and hit
RealForeclose/RealTaxDeed platform URLs -- gadsden is NOT on RealAuction at all, so these sweeps silently never
touch gadsden's rows despite listing its slug. This is a genuine, fixable freshness gap, distinct from the E/I
research items above -- it needs a scraper RUN, not research.

YOUR JOB (bounded, mechanical, not a rebuild):
1. Find the existing gadsden clerk-sheet fetch logic (scripts/shard8_gadsden_bootstrap.py and/or
   scripts/shard7_run3679_gadsden_e_fix.py already contain a working fetch against
   gadsdenclerk.com/Foreclosures/Foreclosures_files/sheet001.htm using a real browser User-Agent header --
   reuse/extend this, do not rewrite from scratch).
2. Re-fetch the live sheet now, diff it against the 23 existing gadsden multi_county_auctions rows (by
   case_number), and UPDATE last_seen_at (and any other freshness-relevant timestamp column the evaluator reads:
   last_changed_at/scraped_at/scrape_timestamp/created_at -- check pencil_dod_evaluate_county's actual SQL, it
   takes GREATEST() of last_changed_at/last_seen_at/scraped_at/scrape_timestamp/created_at) for every row that is
   still present and unchanged on the live sheet, and apply any real field changes (new cases, status changes,
   sold amounts) you find -- per the fail-loud invariant, if the sheet parses with >0 rows, every matched row
   must get a real write, never a silent no-op.
3. WIRING MANDATE compliance: this fetch must be wired to a recurring executor in THIS session, not left as a
   one-off script run. Add a small, focused new GitHub Actions workflow (e.g.
   .github/workflows/gadsden-clerk-freshness.yml) with a daily cron (pick a time that doesn't collide with the
   05:15 UTC dark-counties sweep or 05:30Z cycle already documented) that runs this fetch+update for gadsden
   specifically. Commit it, and also RUN it once this session (workflow_dispatch or by executing the underlying
   script directly against live Supabase, whichever is faster) so last_seen_at is real and fresh right now, not
   just scheduled for tomorrow.
4. Confirm via pencil_dod_evaluate_county('gadsden') that H's metric drops back under 48 and pass flips true.`,
  },
]

const RECIPE = `
Environment (already available, do not ask for credentials):
- REST API reads/writes: GET/PATCH \${SUPABASE_URL}/rest/v1/<table>?... with headers
  apikey: $SUPABASE_SERVICE_ROLE_KEY, Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY
- Live arbitrary SQL: POST https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query
  headers Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json
  body {"query": "<sql>"} -- run "SET statement_timeout = 0;" first in the same query string for anything heavy.
  IMPORTANT (confirmed this session): plain python urllib/requests-style calls to api.supabase.com get a
  Cloudflare 403 (error code 1010, TLS/bot-fingerprint block) from this sandbox. Use \`curl\` with an explicit
  realistic browser User-Agent header, e.g.:
  curl -s -X POST "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query" \\
    -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" -H "Content-Type: application/json" \\
    -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \\
    --data @file.json
  Build the JSON body with a real encoder (python3 -c "import json; ..." to a temp file) rather than hand-quoted
  shell strings. This curl+UA approach is CONFIRMED WORKING this session -- use it, do not conclude Management
  API access is blocked from a urllib-only failure.
- pencil_dod_evaluate_county RPC (works fine via plain PostgREST, no UA issue there):
  POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county headers apikey/Authorization as above,
  body {"p_county": "gadsden"} -- this is your before/after proof.
- fl_parcels table: gadsden's real per-parcel appraiser data is already ingested at co_no=30 (CONFIRMED this
  session empirically via municipality ILIKE match on Quincy/Chattahoochee/Havana -- co_no=20 used elsewhere in
  this DB, e.g. one jurisdictions row, is NOT gadsden, it returns Clay County municipalities; treat that as a
  pre-existing cosmetic mismatch in that one row, do not spend time fixing it unless it actually breaks a query
  you need). Useful columns: parcel_id, own_name, phy_addr1, phy_city, dor_uc, municipality, jv, lnd_val,
  lnd_sqfoot, no_buldng, no_res_unt, centroid_lat, centroid_lng, future_land_use.
- v_zoning_gold_standard_card / v_zoning_gold_standard_kpi_v3: the views the evaluator joins against for G and I.
  I's card_complete requires (per the live function definition, fetched this session): property_address NOT NULL
  AND lat/lon present AND (assessed_value OR market_value) present AND parcel_id (or tax_account) present in
  v_zoning_gold_standard_card WHERE zone_code IS NOT NULL for this county. card_rows (I's denominator) = ALL 23
  gadsden auctions, not just parcel-linked ones -- so I cannot exceed (23 - unlinked_count)/23.
- Direct DB pooler/psql is CONFIRMED STALE this run (password auth fails) -- use the curl+UA Management API or
  PostgREST only.
- gh CLI is authenticated (repo, workflow scopes) for git operations and workflow dispatch.
- Repo root is the current working directory, on main. Read
  GOLD_STANDARD_SHARD13_GADSDEN_DISPATCH_47974994_2ND_REFIRE_SESSION_REPORT.md and
  GOLD_STANDARD_SHARD13_GADSDEN_DISPATCH_47974994_SESSION_REPORT.md in full before starting -- they are the
  baseline for every item above, document 4+ prior sessions' exhaustive research, and cite the exact prior
  scripts (scripts/shard7_run3679_gadsden_e_fix.py, scripts/shard8_gadsden_bootstrap.py) you should check before
  writing anything new.
- Schema changes go through a migration file under supabase/migrations/<date>_shard11_gadsden_<item>_<purpose>.sql,
  committed to git, applied via the curl+UA Management API. Simple data backfills (UPDATE/PATCH, no schema
  change) don't need a migration file -- just do the REST PATCH/Management-API UPDATE and note the exact
  SQL/endpoint used.
- Some small-county sites 403 a default UA but work with a standard browser User-Agent header (confirmed for
  gadsdenclerk.com in a prior session, and for franklinclerk.com in a sibling shard) -- try that before
  concluding a source is unreachable. gadsdencountyfl.gov and qpublic are confirmed WAF/Cloudflare-blocked even
  with a real headless browser -- do not re-spend budget on those two specific domains via plain fetch methods,
  only via the genuinely new angles named in your item.

ULTRALOOP audit logging (mandatory): for every letter you claim moved (or claim you verified as
correctly-blocked/residual), INSERT one row into public.gold_standard_ultraloop_audit: columns dispatch_id
(uuid '${DISPATCH_ID}'), ultraloop_mode ('fallback'), county_slug ('gadsden'), letter, claim (short text),
refuter_evidence (jsonb -- your before/after evidence for FIX agents, your refutation attempt for VERIFY agents),
survived (boolean). POST to \${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with the service-role headers
above (this table is plain PostgREST, no UA issue).

Hard rules:
- Touch ONLY gadsden's rows. Never touch another shard's counties.
- PropertyOnion is litmus/comparison ONLY -- never write po_*-derived values in as if verified/independent.
- Fail-loud invariant: parsed>0 AND inserted/updated=0 must raise. NEVER add silent exception handling.
- Every claim must be tagged VERIFIED (you ran the query/request and are pasting real output), UNTESTED, or
  INFERRED (with a 1-sentence reason).
- Before finishing: call pencil_dod_evaluate_county('gadsden') and paste the FULL before/after JSON. If a letter
  did not move, say so plainly.
- git commit any file you create/modify with a clear, item-scoped message; 'git pull --rebase origin main' before
  pushing (other items are isolated in separate worktrees but push to the same main). Push directly to main --
  no branches, no PRs, per the SHIP-TO-MAIN MANDATE.
- Do NOT run public.gold_standard_loop() or gold_standard_certify() yourself. Do NOT modify cron jobs 109, 111,
  115, or any gold-standard-loop-* scoring job.
- This project has a documented history of fabrication failure modes (gulf B/F, franklin, this county's own
  lake-G incident from a sibling shard). NEVER fabricate a case number, parcel ID, sale amount, coordinate,
  zoning standard, or timestamp to make a metric look better. An honest, unmoved metric with a clearly documented
  reason is always the correct outcome over a fabricated pass.

Return a structured report: { item_key, county, letters_touched: [...], fix_summary, sql_or_endpoints_used: [...],
before_json, after_json, residual_gaps: [...], honesty_notes: [...] }.
`

phase('Diagnose+Fix')
const fixResults = await pipeline(
  ITEMS,
  (item) => agent(
    `You are working Gold Standard shard-11 gadsden session (dispatch ${DISPATCH_ID}, loop run 5361), item "${item.key}", inside the cli-anything-biddeed repo (already checked out, on main).\n\n${item.context}\n\n${RECIPE}`,
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
    `Your job: re-run pencil_dod_evaluate_county('gadsden') yourself RIGHT NOW (fresh call via PostgREST, do not ` +
    `trust the pasted after_json), compare against the claimed before/after, and check specifically for: ` +
    `(a) denominator mismatches, (b) ghost-success (any letter now passing/improved because of a placeholder/` +
    `fabricated/vacuous value rather than a real fix -- this project has a documented history of exactly this ` +
    `failure mode, be extra skeptical of any parcel_id link or zoning-standard claim), (c) whether the parcel_id ` +
    `written for an E item (if any) is genuinely disambiguated by a real signal, not a coin-flip between the ` +
    `known-ambiguous candidates documented in the item context, (d) for the H item, that last_seen_at (or ` +
    `whichever timestamp column the evaluator's GREATEST() reads) was updated with a REAL fetch, not just an ` +
    `UPDATE ... SET last_seen_at = now() with no underlying re-verification of the row's content, (e) whether any ` +
    `OTHER letter for gadsden regressed as a side effect (especially G, which is currently PASS 100 -- confirm ` +
    `it is still PASS after any new zoning writes). Also INSERT your own gold_standard_ultraloop_audit row per ` +
    `the RECIPE instructions (ultraloop_mode='fallback'). Return { item_key, county, refuted: boolean, ` +
    `refutation_reason: string|null, fresh_evaluation: <the JSON you just got>, survives: boolean }.`,
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
