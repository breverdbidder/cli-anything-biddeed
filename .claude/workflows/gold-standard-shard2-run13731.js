export const meta = {
  name: 'gold-standard-shard2-run13731',
  description: 'Gold Standard shard-2 (dispatch f6a6977d, loop run 13731): gadsden C cancelled-row litmus, calhoun single-row C/D/I fix, levy 2-row E/I/J lookup, pinellas I zoning-linkage gap, broward I/J value+bd backfill — ULTRALOOP diagnose/fix/adversarial-verify',
  phases: [
    { title: 'Fix', detail: 'one agent per county, worktree-isolated, mechanical fixes only' },
    { title: 'Verify', detail: 'independent refuter per letter claimed' },
  ],
}

const DISPATCH_ID = 'f6a6977d-0263-42f8-8255-d26612af2a16'

const GROUND_TRUTH = `Ground truth gathered LIVE this session (VERIFIED via the Management API SQL endpoint and
pencil_dod_evaluate_county RPC — treat this as already-confirmed, do not re-derive from scratch, just act on it):

=== pencil_dod_evaluate_county actual SQL logic (pulled via pg_get_functiondef) ===
- Denominator for ALL letters excludes rows where data_source='propertyonion' unless tier1_authoritative=true.
- C (matched_clean): parity_status='matched_clean' AND parity_source LIKE 'tier1%%'  OR  parity_status IN ('PARITY_OK','CLERK_VERIFIED').
- D (matched_any): C's set PLUS parity_status='matched_divergent' (with tier1%% source) PLUS parity_status='CLERK_SSOT_CANCELLED'.
- E: parcel_id IS NOT NULL, threshold 95%%.
- I (card_complete): property_address NOT NULL AND (latitude OR po_latitude) NOT NULL AND (longitude OR po_longitude) NOT NULL
  AND (assessed_value OR market_value) NOT NULL AND parcel_id (or its match to tax_account) present with a NON-NULL
  zone_code in v_zoning_gold_standard_card.
- J (deal_complete): a bid_decisions row matched by case_number with arv+max_bid+ml_score all NOT NULL AND factors
  jsonb containing ALL of distress_location, distress_property, distress_owner, cma_distressed, cma_resale.
- refresh_parity_tier1_outcomes(p_county) is the ONLY sanctioned writer of parity_status/parity_source via matching
  against tax_deed_outcomes/foreclosure_outcomes (case_number or unambiguous parcel_id join). It only touches rows
  with auction_status IN ('redeemed','completed','sold','cancelled','canceled') -- note LOWERCASE literal match,
  confirmed case-sensitive in Postgres. Fleet-wide auction_status casing values that mean "cancelled" are:
  'canceled','canceled_bankruptcy','cancelled','CANCELLED' -- the uppercase 'CANCELLED' value will NOT match this
  function's WHERE clause today. This is a real, narrow, additive bug (wrapping the auction_status comparisons in
  lower()) but it is a SHARED fleet-wide function used by every other shard/county -- do NOT patch it inside this
  session without being very sure it's additive-only (adds new matches, never removes/changes existing ones) and
  even then prefer to just document the finding precisely rather than ship a fleet-wide function edit under time
  pressure; a documented finding with exact evidence is more valuable than a rushed shared-code change.
- CONFIRMED (checked live): for gadsden's 10 CLERK_SSOT_CANCELLED tax-deed rows AND calhoun's cancelled row "546 OF
  2024", there is ZERO row in tax_deed_outcomes or foreclosure_outcomes for those case numbers -- there is currently
  NO independent data to match against even if the casing bug were fixed. Do not assume fixing the casing bug alone
  would flip these; it would not, because the join target is empty. A real fix requires sourcing genuine independent
  confirmation of the cancellation (e.g. a second official source, or a documented PropertyOnion litmus comparison
  used STRICTLY as a read-only comparison, never written back as data_source) -- or an honest structural-ceiling
  writeup if no such source exists for a not-yet-past-due tax deed cancellation.

=== gadsden (C fail 84.8%%, 56 of 66; denominator confirmed 66 rows) ===
10 rows are parity_status='CLERK_SSOT_CANCELLED', parity_source like 'gadsden_clerk_tax_deed', auction_status=
'CANCELLED' (uppercase), auction_date='2026-09-02' (future), case numbers: 26000027TDC, 26000034TDC, 26000025TDC,
26000035TDC, 26000032TDC, 26000022TDC, 26000029TDC, 26000018TDC, 26000021TDC, 26000024TDC. All have po_market_value/
parity_po_id/data_source = NULL (no litmus comparison has ever been attempted on these). These 10 already count
toward D (100%% PASS, do not touch) but not C. 45 rows are PARITY_OK, 11 are matched_clean -- those 56 are fine,
leave them alone. I is 65/66 (one row incomplete) -- find it fresh via SQL, it is NOT one of the 10 cancelled rows
above (those already have lat/value populated per the earlier per-row check).

=== calhoun (C fail 77.8%%=7/9, D fail 88.9%%=8/9, I fail 88.9%%=8/9; tiny county, only 9 rows total) ===
Full 9-row detail already pulled. Exactly ONE row is responsible for the D and I gaps, and is one of TWO rows
responsible for the C gap:
  case_number=25-52CA, sale_type=foreclosure, auction_status=upcoming, parcel_id=29-1N-08-0000-0030-0000,
  property_address="20156 NE Hentz Ave Blountstown FL 32424", latitude=NULL, assessed_value=NULL, market_value=NULL,
  parity_status=NULL, parity_source=NULL, source_url=https://calhounclerk.com/foreclosures/25-52ca/,
  data_source=calhoun_clerk_scrape.
The second C-blocking row: case_number="546 OF 2024", tax_deed, auction_status=CANCELLED, parity_status=
CLERK_SSOT_CANCELLED (same structural-ceiling pattern as gadsden above -- zero independent outcome row exists for
it, confirmed live).
Fixing 25-52CA's geo+value via a real Calhoun County Property Appraiser lookup (parcel 29-1N-08-0000-0030-0000) and
then calling refresh_parity_tier1_outcomes('calhoun') (in case a real tax_deed_outcomes/foreclosure_outcomes row
exists for 25-52CA that just hasn't been matched yet -- check this, don't assume) would flip D to 9/9=100%% and I to
9/9=100%%. C would still be 8/9=88.9%% (546 OF 2024 remains a structural-ceiling FAIL) unless a genuine independent
source for that cancellation is found.

=== levy (E/I/J all fail at 93.5%%=29/31; denominator 31) ===
Exactly 2 rows have NULL parcel_id, property_address, latitude, assessed_value -- i.e. completely unenriched stub
rows: case_number=2026-4163TD (tax_deed) and case_number=2025000075CAAXMX (foreclosure). These same 2 rows are
almost certainly also the J-failing rows (no address/parcel means no CMA inputs means no bid_decisions row). A real
fix needs a genuine lookup: Levy County Property Appraiser (qpublic/Schneider-style site typical for small FL
counties -- verify the actual platform) cross-referenced with the Levy County Clerk case docket for the case number
to recover a real property address, then geocode/parcel-match. If either case genuinely has no published property
record yet (e.g. a foreclosure still early in litigation with no address of record), document as structural-ceiling
residual with the real evidence found, not a guess.

=== pinellas (I fail 94.3%%=415/440; denominator 440) ===
Breakdown of the 25-row gap (rows can fail more than one sub-condition so these overlap): missing_address=4,
missing_geo=2, missing_value=2, missing_parcel=6, and — the dominant, distinct bucket — 18 rows that DO have a
parcel_id but that parcel_id is NOT found (with a non-null zone_code) in v_zoning_gold_standard_card. That 18-row
bucket is a ZONING-INGESTION gap, not an auction-enrichment gap: those specific Pinellas parcels/jurisdictions are
not covered by whatever zoning_districts/parcel_zones data currently backs v_zoning_gold_standard_card for
pinellas. Find which jurisdiction(s) those 18 parcels fall in (query multi_county_auctions joined to the parcel_id
list, look at property_address/city) and check pipeline.counties / zoning_districts / parcel_zones coverage for
that jurisdiction. If it's a genuine ingestion gap (jurisdiction never loaded), size it and report as residual
(building a full new zoning-ingestion pipeline for a jurisdiction is out of scope for one session, per the G
playbook precedent) -- but if it's something narrower like a stale parcel_zones snapshot or a join-key mismatch
(e.g. parcel_id format mismatch, STRAP vs folio), that IS fixable this session. Diagnose before concluding which
case it is. The other ~7-13 rows (address/geo/value/parcel gaps) are ordinary auction-enrichment gaps -- backfill
via a real Pinellas County Property Appraiser (PCPAO) lookup using the existing parcel_id where present.

=== broward (I fail 91.4%%=737/806, J fail 94.4%%=761/806; denominator 806) ===
I-gap breakdown: missing_value (assessed_value AND market_value both NULL) = 67 rows -- this is the dominant driver
of the 69-row I gap (806*0.95=765.7, actual=737, gap=~29 to reach threshold but 69 total rows are individually
incomplete). missing_address=10, missing_geo=17, missing_parcel=3 (these overlap with the missing_value set to some
degree -- verify actual distinct failing row count fresh). Most of these rows DO have parcel_id (only 3 missing it),
so a real Broward County Property Appraiser (BCPA) lookup keyed by parcel_id to pull assessed/just value for the 67
rows is the highest-leverage, most mechanical fix available -- BCPA publishes a public parcel search / open data
layer, confirm the live endpoint before bulk-querying.
J-gap: 806 auctions total, 761 have ANY bid_decisions row at all (45 have zero rows, i.e. the generator/batch has
simply never run for those 45 case numbers -- not a data-quality problem, a coverage/scheduling gap), and of the
761 that do have a row, ALL 761 are already deal_complete (arv+max_bid+ml_score+5 factors all present) -- so J's
gap is ENTIRELY the 45 auctions the deal-triangle pipeline hasn't reached yet, not incomplete rows. Investigate WHY
those 45 case numbers were skipped (new rows added after the last batch run? a case_number normalization mismatch
between multi_county_auctions and whatever feeds bid_decisions?) before deciding whether it's a quick re-run of an
existing batch vs a genuine gap needing the batch's input criteria widened. Do NOT build a new J generator -- if one
already exists (gen_valuations_comps_batch / the Shapira pipeline per CLAUDE.md), the fix is getting it to cover
these 45 rows, not writing a new one.`

const RECIPE = `
Environment (already available, do not ask for credentials):
- Live arbitrary SQL (the ONLY working DB path -- direct psql/pooler connections FAIL with password auth errors,
  confirmed this session, do not waste time re-testing that): POST
  https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query
  headers Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json
  body {"query": "<sql>"} -- run "SET statement_timeout = 0;" first in the same query string for anything heavy.
  Build the JSON body with python3 -c "import json; ..." to a temp file, then curl --data-binary @file, never
  hand-quote SQL into shell strings.
- REST reads/writes: GET/PATCH/POST \${SUPABASE_URL}/rest/v1/<table>?... with headers
  apikey: $SUPABASE_SERVICE_ROLE_KEY, Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY
- pencil_dod_evaluate_county RPC: POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county
  body {"p_county": "<county>"} -- your before/after proof. Call it fresh, do not trust cached numbers.
- refresh_parity_tier1_outcomes(p_county) is the canonical parity matcher -- call it via the Management API SQL
  endpoint (SELECT * FROM public.refresh_parity_tier1_outcomes('<county>');) after inserting/updating any
  tax_deed_outcomes/foreclosure_outcomes row, never hand-write parity_status/parity_source yourself for a
  case/parcel match. (Structural-ceiling rows with zero independent outcome data are the one exception -- there is
  nothing to "run the matcher" against, say so plainly.)
- gh CLI is authenticated (repo, workflow scopes) for git operations. Repo root is the current working directory
  (worktree-isolated), on main.
- Any UPDATE to multi_county_auctions/tax_deed_outcomes/foreclosure_outcomes columns is a data backfill, not a
  schema change -- still write a short documentation migration file under
  supabase/migrations/<date>_shard2_<county>_<purpose>.sql per this campaign's house style: a narrative comment
  block with VERIFIED evidence, then the idempotent SQL mirroring what you ran live. A genuine schema change (new
  column/table) needs a real migration, not just documentation, and should be avoided this session if a data-only
  fix suffices.

ULTRALOOP audit logging (mandatory): for every letter you touch OR conclusively re-verify (moved, still-blocked, or
structural-ceiling), INSERT one row into public.gold_standard_ultraloop_audit: columns dispatch_id
(uuid '${DISPATCH_ID}'), ultraloop_mode ('fallback' -- manual Workflow-tool fan-out, not native /effort ultracode),
county_slug, letter, claim (short text), refuter_evidence (jsonb -- your real evidence), survived (boolean, true
only if it held up under your own re-check with a fresh query). POST to
\${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with service-role headers.

Hard rules:
- You own ONLY your assigned county below. Never touch any other county's rows or any other shard's files.
- PropertyOnion is litmus/comparison ONLY -- never write po_*-derived values in as an independent/verified source,
  never set data_source to anything PropertyOnion-derived, never mark a row PARITY_OK/matched_clean based solely on
  a PropertyOnion match (that is C's job in the litmus sense only if the evaluator already treats it that way --
  it does NOT; C requires parity_source LIKE 'tier1%%' or PARITY_OK/CLERK_VERIFIED sourced from a genuine
  independent official-records match, not PropertyOnion).
- Fail-loud invariant: if a fix attempt finds zero real data for a row, report it as blocked/structural-ceiling.
  NEVER fabricate case numbers, parcel IDs, addresses, coordinates, sold amounts, or ordinance values to make a
  metric look better -- this campaign has a documented fabrication-then-purge history in another county (dixie B/F,
  2026-07-10); do not repeat it in any form, in either direction. A metric that does not move because the real data
  does not exist yet is an honest, acceptable outcome.
- Every claim must be tagged VERIFIED (you ran the query/request and are pasting real output), UNTESTED, or
  INFERRED (say why).
- Before finishing: call pencil_dod_evaluate_county for your county and paste the FULL before/after JSON. If a
  letter did not move, say so plainly.
- git commit any file you create/modify with a clear, county-scoped message. 'git pull --rebase origin main' before
  pushing (other shards may push concurrently to shared paths). Push directly to main -- no branches, no PRs.
- Do NOT run public.gold_standard_loop() or gold_standard_certify() -- other shards may be mid-session. Do NOT
  modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job. Do NOT edit shared fleet-wide functions
  (e.g. refresh_parity_tier1_outcomes, pencil_dod_evaluate_county) even if you find a real bug in them -- document
  the finding with exact evidence instead; a shared-function edit needs review outside a single county-scoped pass.
- Budget yourself: this is ONE bounded pass. If a true fix requires building a brand-new scraper or zoning-ingestion
  pipeline, do NOT build it now -- size the gap precisely and report it as scoped-out residual.

Return: { county, letters_touched: [...], fix_summary, endpoints_or_sql_used: [...], before_json, after_json,
residual_gaps: [...], honesty_notes: [...] }.
`

const TASKS = [
  {
    key: 'gadsden',
    letters: ['C'],
    prompt: `You are working Gold Standard shard-2, county "gadsden", letter C (parity_clean, currently 84.8%%,
56 of 66), inside the cli-anything-biddeed repo (already checked out, on main).

${GROUND_TRUTH}

Your job:
1. Also find gadsden's single I-failing row fresh via SQL (I=98.5%%, 65 of 66) -- it is one row somewhere in the 66,
   not among the 10 cancelled rows (those already have complete geo/value per the earlier check). Identify it and
   attempt a real fix (property appraiser / clerk lookup for whatever field is missing) if the data is genuinely
   available; otherwise document as structural-ceiling.
2. For the 10 CLERK_SSOT_CANCELLED tax-deed rows blocking C: attempt to find a genuine SECOND independent source
   confirming the cancellation (check gadsdenclerk.com directly for a cancellation notice/status page per case
   number, and separately check whether PropertyOnion shows these as cancelled too -- as a read-only litmus
   comparison ONLY, per the hard rules, never written back as a data source). If you find real, citable evidence
   from an independent source, you may INSERT a row into tax_deed_outcomes with a genuinely independent data_source
   describing exactly what you checked (e.g. 'gadsden_clerk_cancellation_notice_verified_20260823'), then call
   refresh_parity_tier1_outcomes('gadsden') and re-check. If no independent source exists (plausible -- these are
   FUTURE auctions dated 2026-09-02, not yet past due), report this honestly as a structural ceiling: these 10 rows
   cannot pass C until independent confirmation becomes available, likely only after the sale date passes and an
   official record is published. Do not force a match.
3. Log gold_standard_ultraloop_audit rows for C (and I if touched) per the RECIPE.

${RECIPE}`,
  },
  {
    key: 'calhoun',
    letters: ['C', 'D', 'I'],
    prompt: `You are working Gold Standard shard-2, county "calhoun", letters C (77.8%%=7/9), D (88.9%%=8/9), I
(88.9%%=8/9), inside the cli-anything-biddeed repo (already checked out, on main). This is a 9-row county -- every
single row matters and is individually traceable.

${GROUND_TRUTH}

Your job:
1. Fix case_number=25-52CA (parcel_id=29-1N-08-0000-0030-0000, address "20156 NE Hentz Ave Blountstown FL 32424"):
   look up the real assessed/just value and confirm/refine the geocode via the Calhoun County Property Appraiser
   (search for their live site/GIS -- small FL county, may be a qpublic/Schneider or BeaconTaxCollector-style
   platform, verify the actual live URL before trusting it) keyed by that parcel_id or address. Also check whether
   a tax_deed_outcomes/foreclosure_outcomes row now exists for 25-52CA (it did not at last check) and if so run
   refresh_parity_tier1_outcomes('calhoun') to let it match properly -- if none exists, C for this row remains
   structural-ceiling (it's an 'upcoming' foreclosure with no independent outcome yet, which is expected and honest)
   but D and I can still be fixed by the geo/value backfill alone (D does not require this row's parity to move,
   only I and, separately, C's OTHER blocking row below need parity work).
   Wait -- re-derive fresh: confirm via a live query which specific condition(s) 25-52CA currently fails for D
   (matched_any includes CLERK_SSOT_CANCELLED and matched_divergent+tier1, not just matched_clean -- re-verify
   whether a geo/value-only fix is sufficient for D or whether D also needs a parity_status value for this row).
2. For case_number="546 OF 2024" (CLERK_SSOT_CANCELLED, blocking C only): same structural-ceiling investigation as
   gadsden above -- check calhounclerk.com directly and PropertyOnion (read-only litmus only) for independent
   confirmation of the cancellation. If found, insert a genuinely independently-sourced outcomes row and re-run the
   matcher; if not, document as structural ceiling with the real evidence.
3. Log gold_standard_ultraloop_audit rows for C, D, and I per the RECIPE, even for letters that remain
   structural-ceiling (log survived=true for the FINDING that it's structural, not for a fix that didn't happen).

${RECIPE}`,
  },
  {
    key: 'levy',
    letters: ['E', 'I', 'J'],
    prompt: `You are working Gold Standard shard-2, county "levy", letters E/I/J (all 93.5%%=29/31), inside the
cli-anything-biddeed repo (already checked out, on main).

${GROUND_TRUTH}

Your job:
1. For case_number=2026-4163TD (tax_deed) and case_number=2025000075CAAXMX (foreclosure), both completely
   unenriched (NULL address/parcel_id/geo/value): attempt a real lookup via the Levy County Clerk's case docket
   (confirm the live platform -- civitek OCRS is common for small FL counties, verify) for the case detail, and the
   Levy County Property Appraiser (likely qpublic/Schneider -- confirm live URL) for a parcel/address match once you
   have any identifying detail (owner name, legal description, or a partial address) from the docket. If you recover
   real values, UPDATE multi_county_auctions for that case_number, then re-check E (parcel_id present),
   I (needs the same fields plus a zoned parcel -- check Levy's zoning coverage for the recovered parcel_id via
   v_zoning_gold_standard_card, report separately if zoning coverage is itself missing), and J (needs a
   bid_decisions row -- check whether the deal-triangle pipeline picks these up automatically once parcel_id exists,
   or whether it needs an explicit re-run for these 2 case numbers).
2. If either case genuinely has no published address/parcel yet at the source (plausible for an early-stage
   foreclosure or a very recent tax certificate), report it as structural-ceiling with the actual page/response you
   found, including the case's real status and any date that would make it worth rechecking later.
3. Log gold_standard_ultraloop_audit rows for E, I, J per the RECIPE.

${RECIPE}`,
  },
  {
    key: 'pinellas',
    letters: ['I'],
    prompt: `You are working Gold Standard shard-2, county "pinellas", letter I (94.3%%=415/440), inside the
cli-anything-biddeed repo (already checked out, on main).

${GROUND_TRUTH}

Your job:
1. First, precisely identify the 18 rows that have parcel_id but no matching zone_code in
   v_zoning_gold_standard_card -- pull their parcel_id, property_address, city fresh via SQL. Determine which
   jurisdiction(s) they fall in and check zoning_districts/parcel_zones coverage for that jurisdiction (query the
   relevant tables directly). Distinguish clearly between: (a) a genuine ingestion gap -- that jurisdiction was
   never loaded into the zoning pipeline (in which case, per the G-letter playbook precedent, building a full new
   jurisdiction's zoning ingestion is OUT OF SCOPE for this session -- size it precisely and report as residual);
   vs (b) a narrower, genuinely fixable issue -- e.g. a parcel_id format/join-key mismatch (STRAP vs folio vs
   different zero-padding) between multi_county_auctions.parcel_id and parcel_zones/v_zoning_gold_standard_card's
   key, where the underlying zoning data for that parcel actually exists but isn't joining. If it's (b), fix the
   join/normalization and re-verify; if it's (a), document with exact counts and jurisdiction name(s).
2. For the remaining ~7-13 rows failing on ordinary address/geo/value/parcel gaps: backfill via a real Pinellas
   County Property Appraiser (PCPAO) lookup -- confirm the live endpoint (likely an ArcGIS FeatureServer or their
   own parcel search) keyed by existing parcel_id or address, and only write values you actually retrieved.
3. Log gold_standard_ultraloop_audit rows for I per the RECIPE.

${RECIPE}`,
  },
  {
    key: 'broward',
    letters: ['I', 'J'],
    prompt: `You are working Gold Standard shard-2, county "broward", letters I (91.4%%=737/806) and J
(94.4%%=761/806), inside the cli-anything-biddeed repo (already checked out, on main). This is the largest county in
your shard (806 rows) -- prioritize the highest-leverage bucket first.

${GROUND_TRUTH}

Your job, in priority order:
1. I: the 67 rows missing BOTH assessed_value and market_value are the dominant driver of the I gap, and most of
   them already have parcel_id. Find/confirm the live Broward County Property Appraiser (BCPA) public data source
   (they publish an open parcel search / GIS layer -- verify the actual live endpoint, do not assume a URL) and
   bulk-backfill assessed/market value for these 67 rows keyed by their existing parcel_id, writing ONLY values you
   actually retrieved from a real response. Then separately handle the smaller missing_address (10) / missing_geo
   (17) / missing_parcel (3) buckets the same way, noting overlap with the value-gap rows (get a fresh distinct
   failing-row count before and after, don't just sum the buckets).
2. J: 45 of 806 auctions have ZERO bid_decisions row at all (the other 761 that do have a row are ALL already
   deal_complete). This reads as a coverage/scheduling gap, not a data-quality gap. Investigate: are these 45 recently
   added rows (check created_at/scrape_timestamp) that simply haven't been picked up by the next scheduled
   deal-triangle batch run yet? Or is there a case_number normalization mismatch preventing the join? Check whether
   the pipeline that populates bid_decisions is a cron/batch you can safely trigger for JUST these 45 case numbers
   (per CLAUDE.md, "the per-minute valuations_comps batch (cron 109) builds inputs -- do not modify it" -- you may
   NOT modify cron 109, but check whether there is a separate way to enqueue/re-run it for specific rows, or whether
   waiting is the honest answer). Do NOT build a new J generator. If the honest finding is "these 45 rows are queued
   and will clear on the next scheduled run, no session-time fix available," report that plainly with the evidence
   (e.g. cron schedule, queue table state) rather than forcing something.
3. Log gold_standard_ultraloop_audit rows for I and J per the RECIPE.

${RECIPE}`,
  },
]

phase('Fix')
const fixResults = await pipeline(
  TASKS,
  (task) => agent(task.prompt, {
    label: `fix:${task.key}`,
    phase: 'Fix',
    isolation: 'worktree',
    schema: {
      type: 'object',
      properties: {
        county: { type: 'string' },
        letters_touched: { type: 'array', items: { type: 'string' } },
        fix_summary: { type: 'string' },
        endpoints_or_sql_used: { type: 'array', items: { type: 'string' } },
        before_json: {},
        after_json: {},
        residual_gaps: { type: 'array', items: { type: 'string' } },
        honesty_notes: { type: 'array', items: { type: 'string' } },
      },
      required: ['county', 'fix_summary', 'before_json', 'after_json'],
    },
  })
)

phase('Verify')
const verified = await pipeline(
  fixResults.filter(Boolean),
  (result) => {
    const county = result.county
    const task = TASKS.find((t) => t.key === county) || { letters: (result.letters_touched || []).map((l) => String(l).split(' ')[0]) }
    return parallel(
    task.letters.map((letter) => () => agent(
      `Independently verify this claimed Gold Standard result for shard-2 county "${county}", letter "${letter}". ` +
      `You did NOT write this -- be skeptical.\n\n` +
      `Claimed full result for this county (covers multiple letters, focus your check on letter ${letter}): ` +
      `${JSON.stringify(result)}\n\n` +
      `${RECIPE}\n\n` +
      `Your job: re-run pencil_dod_evaluate_county('${county}') yourself RIGHT NOW (fresh call, do not trust the ` +
      `pasted after_json), read letter ${letter}'s pass/metric/detail, and check specifically for: (a) denominator ` +
      `mismatches vs the claimed before/after, (b) ghost-success (any row now passing because of a placeholder or ` +
      `implausible value rather than something genuinely retrieved -- e.g. a parcel_id that doesn't resolve on the ` +
      `county GIS, a geocode far outside the county's real bounds, a suspiciously round dollar value, an ` +
      `outcomes-table row whose data_source string doesn't actually describe an independent source), (c) whether ` +
      `letter ${letter} or ANY other letter for this county regressed as a side effect (call the RPC and check ALL ` +
      `10 letters, not just this one), (d) if a structural-ceiling claim was made instead of a fix, confirm the ` +
      `claimed evidence (e.g. the outcomes-table emptiness, or the zoning-coverage gap) by re-querying it yourself. ` +
      `Also INSERT your own gold_standard_ultraloop_audit row for county="${county}" letter="${letter}" per the ` +
      `RECIPE (ultraloop_mode='fallback', survived=true only if the claim holds up). ` +
      `Return { county, letter, refuted: boolean, refutation_reason: string|null, fresh_evaluation: <the JSON you ` +
      `just got for this county>, survives: boolean }.`,
      {
        label: `verify:${county}:${letter}`,
        phase: 'Verify',
        schema: {
          type: 'object',
          properties: {
            county: { type: 'string' },
            letter: { type: 'string' },
            refuted: { type: 'boolean' },
            refutation_reason: { type: ['string', 'null'] },
            fresh_evaluation: {},
            survives: { type: 'boolean' },
          },
          required: ['county', 'letter', 'refuted', 'fresh_evaluation', 'survives'],
        },
      }
    )))
  }
)

return { fixResults, verified: verified.flat().filter(Boolean) }
