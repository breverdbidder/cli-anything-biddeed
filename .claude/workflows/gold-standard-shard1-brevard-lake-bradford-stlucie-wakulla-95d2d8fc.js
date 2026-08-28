export const meta = {
  name: 'gold-standard-shard1-brevard-lake-bradford-stlucie-wakulla-95d2d8fc',
  description: 'Gold Standard shard-1 (dispatch 95d2d8fc, 2026-08-28 08:00Z wave): brevard I, lake C, bradford B/F past-due recheck, st_lucie C/G, wakulla C/I+J — ULTRALOOP diagnose/fix/adversarial-verify',
  phases: [
    { title: 'Diagnose' },
    { title: 'Fix' },
    { title: 'Verify' },
  ],
}

const DISPATCH_ID = '95d2d8fc-cb62-4ba1-a58b-7e1134cf00cf'
const REPO = '/home/runner/work/cli-anything-biddeed/cli-anything-biddeed'

const DIAGNOSE_SCHEMA = {
  type: 'object',
  properties: {
    pair: { type: 'string' },
    has_lever: { type: 'boolean' },
    lever_description: { type: 'string' },
    fix_plan: { type: 'string' },
    evidence: { type: 'string' },
  },
  required: ['pair', 'has_lever', 'lever_description', 'fix_plan', 'evidence'],
}

const FIX_SCHEMA = {
  type: 'object',
  properties: {
    pair: { type: 'string' },
    action_taken: { type: 'string' },
    rows_written: {
      type: 'array',
      items: {
        type: 'object',
        properties: { table: { type: 'string' }, count: { type: 'number' } },
        required: ['table', 'count'],
      },
    },
    migration_path: { type: ['string', 'null'] },
    notes: { type: 'string' },
  },
  required: ['pair', 'action_taken', 'rows_written', 'migration_path', 'notes'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    pair: { type: 'string' },
    county: { type: 'string' },
    letters: { type: 'array', items: { type: 'string' } },
    before_metric: { type: 'string' },
    after_metric: { type: 'string' },
    moved: { type: 'boolean' },
    survived: { type: 'boolean' },
    anomaly_notes: { type: 'string' },
    regression_check: { type: 'string' },
  },
  required: ['pair', 'county', 'letters', 'before_metric', 'after_metric', 'moved', 'survived', 'anomaly_notes', 'regression_check'],
}

const COMMON_PREAMBLE = `
You are working in the repo at ${REPO} (BidDeed.AI gold-standard county-conquest campaign, dispatch_id ${DISPATCH_ID}, headless session, no human in the loop).

DB ACCESS: direct psql is NOT reachable from this sandbox. The ONLY working DB path is Supabase PostgREST via env vars $SUPABASE_URL and $SUPABASE_SERVICE_ROLE_KEY (already set in your shell — NEVER echo/print these values, only reference them as $VARNAME inside curl/python commands per CREDENTIAL HANDLING rules in CLAUDE.md).
- Read: curl "$SUPABASE_URL/rest/v1/<table>?<filters>" -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
- Evaluate a county live: curl -X POST "$SUPABASE_URL/rest/v1/rpc/pencil_dod_evaluate_county" -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" -H "Content-Type: application/json" -d '{"p_county":"<county>"}'
- Supabase intermittently threw transient Cloudflare 520/521 errors during this session's setup and recovered within ~10s — if a call fails with a 5xx HTML error body (not JSON), retry with a short backoff before concluding anything is broken.
- Write: PostgREST POST/PATCH to /rest/v1/<table> (Prefer: return=representation). There is no generic exec_sql RPC — table writes must go through PostgREST, not raw SQL, from this sandbox. If a fix genuinely requires DDL (new column/function), do NOT attempt it — flag it as requiring a proper migration.
- Column names: multi_county_auctions uses "latitude"/"longitude" (NOT "lat"/"lon"), and "city"/"zip" are frequently NULL even when embedded in the "property_address" free-text string — check actual columns with a 1-row select before assuming names.
- After a real fix, WRITE a Supabase migration file under supabase/migrations/ (naming: YYYYMMDD_gold_standard_shard1_95d2d8fc_<county>_<letters>_<slug>.sql) documenting the baseline, the lever found, the exact writes made (with live before/after pencil_dod_evaluate_county JSON pasted in SQL comments), and any residuals — following the style of existing files in that directory (read 2-3 recent ones for the house style first). The migration body itself can be the same PostgREST-equivalent writes recorded as SQL (UPDATE ... WHERE case_number=...) for the historical record, or 'SELECT 1;' if this was a no-write research/recheck session — either way it is what gets committed. Do NOT run this migration via psql/supabase db push (unreachable) — just write the file; the orchestrating session applies-by-record and commits it.

HARD GUARDRAILS (from CLAUDE.md, do not violate):
1. PropertyOnion = litmus ONLY, never ingest as a data source.
2. Fail-loud invariant: parsed>0 AND inserted=0 must raise. NEVER add silent exception handling / try-except-pass around real work.
3. Never fabricate zoning/appraisal/outcome values. Ghost-success (writing plausible-looking but unverified numbers) is a Honesty Protocol CRITICAL violation. BLANK > WRONG always.
4. Do not modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring function.
5. Do NOT git commit or git push — just write files (scripts/migrations) and report; the orchestrator handles commits.
6. REUSE-FIRST: grep scripts/ and supabase/migrations/ for existing helpers/prior findings for this county+letter before writing new fetch logic from scratch (this campaign has run 100+ prior sessions — assume deep history exists and read it).
7. Every claim carries VERIFIED (you ran the query/script and pasted output) / UNTESTED / INFERRED per the Honesty Protocol. Never claim a row count you didn't observe.
8. Canon reminder: B passes ONLY in the 95-105% band (anomalous ratios auto-fail). C/D "clean" vs "any" match distinction matters — read pencil_dod_criteria or the evaluator function source if unsure which one a fix affects.
`

const PAIRS = [
  {
    pair: 'brevard-I',
    county: 'brevard',
    letters: ['I'],
    before: 'I=85.7% (card_complete=6271 of 7315). PASS threshold is 95% (needs ~6949, gap ~678 rows). Two prior migrations exist: 20260802_gold_standard_shard1_brevard_i_gis_backfill.sql and 20260803_gold_standard_shard1_1f5f4ede_brevard_i_zoning_backfill.sql — read both first for exact prior bucket sizes/blockers before doing anything (this is a large, well-worked county; do not re-derive from scratch).',
    task: 'Read the two prior brevard-I migrations plus any ARCHITECT_TRIAGE_*BREVARD* session reports in repo root to get the current bucket breakdown (missing address / missing parcel_id / missing value / missing zone-match). Query multi_county_auctions live for brevard rows failing card-completeness right now and diff against the prior sessions documented buckets to see what has genuinely changed (auction_status transitions, new rows added since last session, etc.) versus what is a re-confirmed structural ceiling. Focus fix effort on whichever bucket is smallest/most tractable and NOT already marked exhausted in prior reports — do not re-attempt a source already confirmed dead (e.g. re-scraping BCPAO the same way twice).',
  },
  {
    pair: 'lake-C',
    county: 'lake',
    letters: ['C'],
    before: 'C=87.8% (matched_clean=122 of ~139, need ~132). Read supabase/migrations/20260814_gold_standard_shard2_5f3a88a5_lake_ceij_efollowup.sql first: prior session documented 13 of 14 mismatched rows as CLERK_SSOT_CANCELLED (court-confirmed cancellations, rechecked live against courtrecords.lakecountyclerk.org/sci docket API with no reschedule/sale-confirming entry found) — a likely genuine structural ceiling, NOT re-fabricatable. Also check 20260803_gold_standard_shard2_lake_c_status_recheck.sql and 20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql for full history.',
    task: 'First determine if the C metric denominator/numerator have moved since 2026-08-14 (new auctions added, or a docket status change on any of the 13 previously-cancelled cases) via a fresh live check of courtrecords.lakecountyclerk.org/sci for each of the 13 case numbers listed in the 20260814 migration. If genuinely nothing changed, do a lightweight reconfirm (do not re-run the full research pass) and report has_lever=false with evidence of what was checked. If a real docket change is found for any case (sale confirmed/rescheduled), that is the lever — get the real matching data and reconcile parity for that row.',
  },
  {
    pair: 'bradford-BF',
    county: 'bradford',
    letters: ['B', 'F'],
    before: 'B=null F=null (verified=0 closed_sold=0, 5 total auctions). Prior sessions (6+, see gold-standard-shard6-bradford-run7177-f68d2ec5.js and gold-standard-shard5-hardee-bradford-d07c1eba.js) found bradfordclerk.com and most portals Cloudflare-Turnstile-blocked, and one lever (records.bradfordco.org/PSI/) login-gated. FRESH FINDING FROM THIS SESSION (live query moments ago, VERIFIED): the 5 bradford rows are 24000431CAAXMX (auction_date 2026-08-20, status still "upcoming"), 25000457CAAXMX (2026-07-16, "upcoming"), 04-2026-TD-002 (2026-09-09, genuinely future), 25000439CAAXMX (2026-08-13, "upcoming"), 25000487CAAXMX (2026-08-13, "upcoming"). TODAY IS 2026-08-28. FOUR of the five cases have auction_date already in the PAST while auction_status still reads "upcoming" and sold_amount is null — this is a genuinely new, previously-unexamined angle: 3 of these 4 (24000431, 25000439, 25000487) were NOT the case prior sessions focused on (which was only 25000457).',
    task: 'For each of the 4 past-due bradford cases (24000431CAAXMX, 25000457CAAXMX, 25000439CAAXMX, 25000487CAAXMX), do a fresh live check for a posted outcome: try any working, non-exhausted Bradford Clerk data path found by prior sessions (check the prior reports for what specifically was NOT yet tried — e.g. new leads section in gold-standard-shard6-bradford-run7177-f68d2ec5.js mentions untried vendor/domain leads found via Firecrawl search) plus a fresh WebSearch/Firecrawl-search for each case number by name (may surface a news item, OCRS-equivalent, or surplus-funds listing even if the clerk site itself is blocked). If Firecrawl previously reported HTTP 402 (no credits), check live whether credits have refreshed before assuming it is still dead. If truly nothing new for any of the 4, report has_lever=false with the specific evidence per case (do not silently skip any of the 3 previously-unexamined cases).',
  },
  {
    pair: 'st_lucie-C',
    county: 'st_lucie',
    letters: ['C'],
    before: 'C=80.7% (matched_clean=201 of 249, need ~237, gap ~36). No prior st_lucie-C-specific migration found in a search of supabase/migrations — this may be a genuinely fresh/under-worked pair. D=100% (matched_any=249) so the gap is specifically in the stricter clean-match, not missing rows — likely a normalization/parity-key mismatch (case-number format, date drift, or a PropertyOnion-vs-clerk field disagreement), not missing data.',
    task: 'Query the parity views/tables (grep pencil_dod_evaluate_county or related SQL functions for how C/clean-match is computed for st_lucie) to find the exact ~36-48 rows where matched_any=true but matched_clean=false. Diagnose the specific field mismatch per row (or per bucket if they share a pattern) and fix the matching/normalization. If a genuinely new external-source lever is needed (e.g. clerk docket confirmation), check stlucieclerk.gov / St. Lucie realforeclose/realtaxdeed live before assuming blocked.',
  },
  {
    pair: 'st_lucie-G',
    county: 'st_lucie',
    letters: ['G'],
    before: 'G=0.0% (density=91.0 far=0.0 pk1000=0.0 — FAR and parking are both entirely at 0%, density is close to passing at 91%). This is a substrate-gap pattern like the one documented for brevard/duval in the campaign SSOT: zoning_districts likely exist with density data but zone_standards max_far and parking_per_1000sf are wholesale NULL across St. Lucie jurisdictions, not a few scattered rows. Live jurisdictions for st_lucie found this session (VERIFIED): id=1400 "St. Lucie County (Unincorporated)", id=1128 "St. Lucie Village", id=971 "Fort Pierce", id=953 "Port St. Lucie". zone_standards table schema was NOT yet inspected this session (a query assuming a "jurisdiction_id" column failed with 42703 — the real FK column name is unconfirmed, check the actual schema first).',
    task: 'First inspect the real zone_standards table schema (select * limit 1) to find the correct jurisdiction linkage column. Then query zone_standards for rows belonging to the 4 st_lucie jurisdictions above and quantify exactly how many districts are missing max_far and parking_per_1000sf (confirm the substrate-gap hypothesis or find the real cause if different). For the highest-parcel-count districts missing FAR/parking, source real values from ordinance text (Municode library.municode.com/fl/<city>, or St. Lucie County / Port St. Lucie / Fort Pierce zoning code PDFs) — no guessing, honesty markers required. This is likely a multi-session effort; make concrete progress on the largest-leverage districts rather than trying to cover all of them.',
  },
  {
    pair: 'wakulla-C',
    county: 'wakulla',
    letters: ['C'],
    before: 'C=84.1% (matched_clean=37 of 44). DOCUMENTED 7-SESSION CEILING (see supabase/migrations/20260825b_gold_standard_wakulla_c_44row_ceiling_reconfirm.sql, 20260826_gold_standard_wakulla_ec_new_angles_ceiling_reconfirm.sql, 20260827_gold_standard_wakulla_ce_25ca105_post_auction_recheck_no_write.sql — read all three, they document exhausted sources: civitekflorida.com, taxcertsale.com/wakullataxsale, qpublic, 4 foreclosure aggregators, Wayback Machine). HOWEVER: 20260827f (same day, later) BROKE the parallel E/I/J ceiling using a genuinely new, previously-untried lever — LandmarkWeb (www.wakullaclerk.com/LandmarkWeb) NameSearch/GetSearchResults/GetDocumentInformation/GetDocumentImage API, reverse-engineered live from the clerk site JS. Read 20260827f in full: it is the most promising untried angle for C too, since it surfaced real recorded documents (Notice of Application for Tax Deed + Release, and Lis Pendens + Final Judgment) for the exact 6 rows that were blocking C/E/I/J. C remained unmoved by that session because its writes only targeted address/parcel/value fields, not clean-match parity keys.',
    task: 'Using the LandmarkWeb API pattern documented in 20260827f (do not re-derive the reverse-engineering — read the exact search/session-cookie/disclaimer flow from that migration file and any script it references), check whether the specific parity-key mismatch blocking clean-match for the 7 wakulla rows failing C can be resolved via the same document search (case number NameSearch surfacing the official record with a matchable sale-status/case-format). If LandmarkWeb does not apply to whatever specific field is causing the clean-match failure, diagnose the exact field mismatch first via the parity view/table before concluding no lever exists — do not simply re-cite the pre-Aug27f ceiling docs without checking if the new lever changes anything.',
  },
  {
    pair: 'wakulla-IJ',
    county: 'wakulla',
    letters: ['I', 'J'],
    before: 'I=86.4% J=86.4% (both card_complete/deal_complete=38 of 44, i.e. the SAME 6 rows fail both). VERIFIED live this session: all 44 wakulla rows already have non-null property_address, parcel_id, market_value/assessed_value, latitude/longitude (confirmed by direct query) — so the I gate is NOT missing address/geo/value. The most likely remaining I blocker is the "zoned parcel" sub-requirement (parcel_id must resolve to a real zone_code via v_zoning_gold_standard_card / parcel_zones), which the 20260827f migration (E/I/J fix, read it in full) explicitly did NOT address — it wrote only multi_county_auctions fields, not parcel_zones/zoning rows for the 6 newly-discovered parcels (2026-TXD-097/117/118/120/122 and 25-CA-105). J additionally requires bid_decisions rows (arv+max_bid+ml_score+5 factor keys via the Shapira generator) which were also not touched for these 6 cases.',
    task: 'Confirm the diagnosis: query v_zoning_gold_standard_card (or whatever view pencil_dod_evaluate_county actually joins for I — grep the function source first) for the 6 parcel_ids (00-00-055-429-19932-034 [25-CA-105], 23-5S-02W-128-02816-078 [TXD-097], 00-00-092-000-11669-002 [TXD-117], 00-00-086-188-11586-05B [TXD-118], 00-00-036-076-09686-001 [TXD-120], 30-2S-01W-000-04171-004 [TXD-122]) and check if they have a zone_code. If missing, check whether these parcels fall inside an existing wakulla parcel_zones/zoning_districts jurisdiction (Wakulla is mostly unincorporated — should have single-county coverage, unlike Lake\'s incorporated-municipality gap) — if the county-wide zoning layer already covers this geography, this may be a simple missing spatial-join backfill for just 6 rows, not a new-data-source problem. Separately, check bid_decisions for these 6 case_numbers and if a Shapira J-generator already exists elsewhere in the repo (check scripts/ and recent migrations mentioning bid_decisions/ml_score/shapira before writing a new one), run it for these 6 cases using the real assessed/market values already on file.',
  },
]

const results = await pipeline(
  PAIRS,
  (p) => agent(
    `${COMMON_PREAMBLE}\nPAIR: ${p.pair} (county=${p.county}, letters=${p.letters.join(',')})\nBASELINE (VERIFIED live via pencil_dod_evaluate_county moments ago at session start): ${p.before}\nTASK: ${p.task}\n\nDo real diagnosis now: read relevant existing scripts/migrations/reports for ${p.county} named above (and search for more if the ones named don't fully explain the gap), run live PostgREST queries to size and locate the exact gap, attempt any live external lookups needed (WebFetch/curl to appraiser/clerk/GIS/Municode/LandmarkWeb sites) to determine whether a genuine, non-fabricated lever exists. Return your findings via the required schema. If has_lever=true, fix_plan must be concrete enough that a follow-up agent with no other context can execute it (exact tables/columns/case-numbers/districts/values). If has_lever=false, evidence must show what you actually checked live (not just cited from old reports).`,
    { label: `diagnose:${p.pair}`, phase: 'Diagnose', schema: DIAGNOSE_SCHEMA }
  ),
  (diag, p) => agent(
    `${COMMON_PREAMBLE}\nPAIR: ${p.pair} (county=${p.county}, letters=${p.letters.join(',')})\n\nDIAGNOSIS FROM PRIOR STAGE:\n${JSON.stringify(diag)}\n\nTASK: If has_lever is false, do nothing further — write a short no-write documentation migration (SELECT 1; body, per the house style of 20260827_gold_standard_wakulla_ce_25ca105_post_auction_recheck_no_write.sql) recording what was checked, and return action_taken="none, structural blocker (re)confirmed" with rows_written=[]. If has_lever is true, execute fix_plan for real against PostgREST (or write a python3+httpx script under scripts/ if the fix needs to run repeatedly/be reusable, following the repo's existing pattern — reuse a prior county's script as a template rather than writing from scratch), run it, and report the ACTUAL row counts written per table from the command's own output (paste the real numbers, never estimate). Then write the migration file documenting this (baseline, lever, exact writes, before/after) per the naming convention in the preamble. Only claim VERIFIED counts you saw in command output.`,
    { label: `fix:${p.pair}`, phase: 'Fix', schema: FIX_SCHEMA }
  ),
  (fix, p) => agent(
    `${COMMON_PREAMBLE}\nPAIR: ${p.pair} (county=${p.county}, letters=${p.letters.join(',')})\nBASELINE BEFORE THIS SESSION: ${p.before}\n\nFIX STAGE RESULT (claims to adversarially verify):\n${JSON.stringify(fix)}\n\nYOU ARE THE ADVERSARIAL REFUTER. Your only goal is to try to break this claim, per the ULTRALOOP protocol in CLAUDE.md. Steps:\n1. Re-run pencil_dod_evaluate_county('${p.county}') live right now via PostgREST RPC — paste the raw JSON output.\n2. Compare the target letter(s) metric before vs after. Did it actually move? By how much?\n3. Check for anomaly patterns explicitly: denominator/numerator mismatches, double-counting, values outside a sane 0-105% band, fabricated-looking round numbers, or a script that reported rows_written>0 but the live metric didn't move at all (evidence of a silent no-op or wrong table).\n4. Regression check: spot-check 1-2 of the county's other currently-passing letters to confirm nothing regressed as a side effect.\n5. POST one row to gold_standard_ultraloop_audit via PostgREST (columns: dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived) for EACH letter in this pair — dispatch_id="${DISPATCH_ID}", ultraloop_mode="native", county_slug="${p.county}", claim=one-line summary of what was claimed, refuter_evidence=jsonb object with your before/after numbers and reasoning, survived=true only if the letter's live metric now PASSES per pencil_dod_criteria (or, for structural-blocker pairs, survived=false with claim describing the blocker so it's on record, not silently dropped).\n\nReturn your verdict via the schema. moved=true only if the raw before/after numbers you pasted actually differ. survived=true only if you would stake the Honesty Protocol on this claim.`,
    { label: `verify:${p.pair}`, phase: 'Verify', schema: VERIFY_SCHEMA }
  )
)

return { pairs: results.filter(Boolean) }
