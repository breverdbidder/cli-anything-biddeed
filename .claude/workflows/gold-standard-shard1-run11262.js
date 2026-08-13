export const meta = {
  name: 'gold-standard-shard1-run11262',
  description: 'Gold Standard shard-1 (brevard/manatee/bradford/lake/taylor, dispatch 7bcb4434, loop run 11262): diagnose-fix-verify per failing letter, ULTRALOOP adversarial audit',
  phases: [
    { title: 'Diagnose' },
    { title: 'Fix' },
    { title: 'Verify' },
  ],
}

const DISPATCH_ID = '7bcb4434-c068-4a5d-b140-0dcf65c8c87f'
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
    script_path: { type: ['string', 'null'] },
    notes: { type: 'string' },
  },
  required: ['pair', 'action_taken', 'rows_written', 'script_path', 'notes'],
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
You are working in the repo at ${REPO} (BidDeed.AI gold-standard county-conquest campaign, dispatch_id ${DISPATCH_ID}).

DB ACCESS: direct psql (port 5432/6543) is NOT reachable from this sandbox (auth fails at network level). The ONLY working DB path is Supabase PostgREST via env vars $SUPABASE_URL and $SUPABASE_SERVICE_ROLE_KEY (already set in your shell — NEVER echo/print these values, only reference them as $VARNAME inside curl/python commands per CREDENTIAL HANDLING rules in CLAUDE.md).
- Read: curl "$SUPABASE_URL/rest/v1/<table>?<filters>" -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
- Evaluate a county live: curl -X POST "$SUPABASE_URL/rest/v1/rpc/pencil_dod_evaluate_county" -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" -H "Content-Type: application/json" -d '{"p_county":"<county>"}'
- Write: PostgREST POST/PATCH to /rest/v1/<table> (Prefer: return=representation), OR python3 + httpx following the exact pattern in scripts/manatee_i_bare_rows_ajax_backfill_10bc7bc6.py (read it first). There is no generic exec_sql RPC — table writes must go through PostgREST, not raw SQL. If a fix genuinely requires DDL (new column/function), do NOT attempt it — flag it in your report as requiring a proper Supabase migration + db push, which is out of scope for this sandbox.

HARD GUARDRAILS (from CLAUDE.md, do not violate):
1. PropertyOnion = litmus ONLY, never ingest as a data source.
2. Fail-loud invariant: parsed>0 AND inserted=0 must raise. NEVER add silent exception handling / try-except-pass around real work.
3. Never fabricate zoning/appraisal/outcome values. Ghost-success (writing plausible-looking but unverified numbers) is a Honesty Protocol CRITICAL violation.
4. Do not modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring function.
5. Do NOT git commit or git push — just write files and report; the orchestrator handles commits.
6. REUSE-FIRST: grep scripts/ for existing helpers for this county (ArcGIS linkage, clerk parsers, zoning lookups) before writing new fetch logic from scratch.
7. Every claim carries VERIFIED (you ran the query/script and pasted output) / UNTESTED / INFERRED per the Honesty Protocol. Never claim a row count you didn't observe.
`

const PAIRS = [
  {
    pair: 'brevard-I',
    county: 'brevard',
    letters: ['I'],
    before: 'I=84.5% (card_complete=6121 of 7248) — dominant known blocker per prior sessions: ~1568 rows with zero address (structural, unresolved by any source tried so far), plus smaller buckets: missing-parcel, missing-geo, missing-value, missing-zone-match. A prior session flagged a data-integrity bug: ~23% of pre-existing clerk_brevard parcel_id links may point to the wrong property (sampled 3/13) — auditing/correcting THIS bucket is the one lever not yet tried and could plausibly move the metric without needing new external data.',
    task: 'Query multi_county_auctions for brevard rows failing the I card-completeness gate (missing address/geo/value/zoned-parcel) via v_zoning_gold_standard_card or the equivalent view used by pencil_dod_evaluate_county (grep functions for the I definition first). Bucket the failures by missing field. Prioritize the data-integrity-bug lever: sample clerk_brevard-sourced parcel_id links against AcclaimWeb (https://vaclmweb1.brevardclerk.us/AcclaimWeb/, VERIFIED live per prior session) case lookups and correct any mismatches found. Do NOT re-attempt the 1568 zero-address bucket unless you find a genuinely new source (prior sessions exhausted BCPAO/Firecrawl there — check Firecrawl credit status live before assuming it is still exhausted, it may have refreshed since Aug 8).',
  },
  {
    pair: 'manatee-G',
    county: 'manatee',
    letters: ['G'],
    before: 'G=94.4% (density is the sole binding sub-metric; far=100.0, pk1000=100.0 already passing). Least-researched pair — no prior session drilled into which specific zoning_district rows have null max_density_du_acre for manatee.',
    task: 'Identify the exact zoning_districts/zone_standards rows for manatee jurisdictions with null max_density_du_acre that are pulling the density sub-metric below 95%. Use v_zoning_gold_standard_kpi_v3 (or grep for the G definition inside pencil_dod_evaluate_county to find the exact view/columns) to find county=manatee rows failing density. For each missing district, look up the real max_density_du_acre value from the jurisdiction ordinance (Municode library.municode.com/fl/<city> or the city zoning code PDF) — do not guess. This should be a small, tractable number of districts (94.4% is already close to 95%).',
  },
  {
    pair: 'lake-C',
    county: 'lake',
    letters: ['C'],
    before: 'C=88.3% (matched_clean=106, denominator ~120). Prior sessions found officialrecords.lakecountyclerk.org / courtrecords.lakecountyclerk.org/showcaseweb sit behind an SPA disclaimer-gate that plain curl/WebFetch cannot pass, and Firecrawl credits were reported exhausted (claimed reset date 2026-08-28, which has NOT yet passed as of today). Do not re-burn effort assuming Firecrawl works without checking live first.',
    task: 'First check live whether Firecrawl credits have actually been restored (a single cheap test call) or whether an alternative path exists (browser-use skill, direct ArcGIS/clerk REST endpoint bypassing the SPA gate, or a JSON API the SPA itself calls under the hood — inspect network calls via WebFetch on the page source for an XHR/API endpoint). If a real lever exists, reconcile the missing ~14 auctions/cases into parity. If genuinely still blocked, say so plainly with evidence — do not retry the exact same blocked path a 4th time.',
  },
  {
    pair: 'lake-G',
    county: 'lake',
    letters: ['G'],
    before: 'G=25.0% (density=91.4, far=82.4, pk1000=25.0 is the binding constraint — parking-per-1000sf). Prior sessions found Municode is reCAPTCHA-gated for Lake jurisdictions; Mount Dora R-1A/R-2 density data marked as placeholder/absent in Municode; Groveland R3 truncated at GIS source. One untried lever flagged: mooredora.elaws.us/code/ldc_chiii_sec3.4 was returning 503 (temporarily down, NOT gated) in the last session and should be retried.',
    task: 'Retry mooredora.elaws.us live first (503 may have cleared). Then identify the specific Lake-county zoning_districts with null parking_per_1000sf — this is the binding sub-metric, not density or far, so focus fix effort there. Check whether any Lake jurisdiction publishes its Land Development Code outside Municode (city website PDF, e-laws instances for other Lake cities) to source real parking-per-1000sf values. Ordinance-text values only, with honesty markers — no guessing.',
  },
  {
    pair: 'taylor-C',
    county: 'taylor',
    letters: ['C'],
    before: 'C=72.7% (matched_clean=8 of 11 matched_any). This contradicts an older report claiming taylor C already passed at 100% — that claim is STALE/wrong (superseded by this live pull), treat C as a genuinely open, likely fresh gap. D=100% (matched_any=11) so the 3-row gap is specifically in the stricter "clean" match, not missing rows entirely.',
    task: 'Find the exact 3 taylor rows where matched_any=true but matched_clean=false (likely a normalization/parity-key mismatch, not missing data — e.g. case-number format drift, date mismatch, or a PropertyOnion-vs-clerk field disagreement). Query the parity views/tables directly to find them, diagnose the specific mismatch per row, and fix the matching/normalization so they clear the clean-match bar. This is very likely a quick, mechanical fix, not a new-data-source problem — do not assume it needs external research before checking the DB rows first.',
  },
  {
    pair: 'taylor-BF',
    county: 'taylor',
    letters: ['B', 'F'],
    before: 'B=null F=null (verified=0 closed_sold=0). 5+ prior sessions confirmed structural: Cloudflare Turnstile on most portals, and the one real unblocked lever (taylorclerk.com/wp-json/kma/v1 API) hard-deletes closed-case data server-side after sale — confirmed across 3 sessions, never observed a transient sold status. Do NOT re-attempt the same exhausted sources (pubrecords.taylorclerk.com, myfloridacounty.com, jud3.flcourts.org, auction.com, foreclosure.com, Wayback Machine on those URLs).',
    task: 'LIGHTWEIGHT RECHECK ONLY (do not re-run the full exhausted research pass): live-query the taylor auctions with a past auction_date and null sold_amount, and do ONE fresh check of kma/v1 API + taylorclerk.com/tax-deed-sales/ for those specific case numbers to see if results have posted since the last session (time has passed — some may have appeared). If still empty, report NO_LEVER with the specific case numbers checked and move on quickly. Do not spend more than a few tool calls on this pair.',
  },
  {
    pair: 'bradford-BF',
    county: 'bradford',
    letters: ['B', 'F'],
    before: 'B=null F=null (verified=0 closed_sold=0, 5 total auctions). 6+ prior sessions confirmed structural: same Cloudflare Turnstile + server-side hard-deletion-after-close pattern as taylor. One case (25000457CAAXMX, sale date 2026-07-16) was the only one past-due as of the last session.',
    task: 'LIGHTWEIGHT RECHECK ONLY (do not re-run the full exhausted research pass): live-query bradford auctions for any past auction_date with null sold_amount, and do ONE fresh check on case 25000457CAAXMX plus any other now-past-due cases via bradfordclerk.com / officialrecords.bradfordclerk.com / kma-style API if bradford has one. If still empty, report NO_LEVER with evidence and move on quickly.',
  },
]

const results = await pipeline(
  PAIRS,
  (p) => agent(
    `${COMMON_PREAMBLE}\nPAIR: ${p.pair} (county=${p.county}, letters=${p.letters.join(',')})\nBASELINE (VERIFIED live via pencil_dod_evaluate_county moments ago): ${p.before}\nTASK: ${p.task}\n\nDo real diagnosis now: read relevant existing scripts/reports for ${p.county}, run live PostgREST queries to size and locate the exact gap, attempt any live external lookups needed (WebFetch/curl to appraiser/clerk/GIS/Municode sites) to determine whether a genuine, non-fabricated lever exists. Return your findings via the required schema. If has_lever=true, fix_plan must be concrete enough that a follow-up agent with no other context can execute it (exact tables/columns/case-numbers/districts/values, and a plan for a script under scripts/ following the repo's existing httpx+PostgREST pattern, e.g. scripts/manatee_i_bare_rows_ajax_backfill_10bc7bc6.py). If has_lever=false, evidence must show what you actually checked live (not just cited from old reports).`,
    { label: `diagnose:${p.pair}`, phase: 'Diagnose', schema: DIAGNOSE_SCHEMA }
  ),
  (diag, p) => agent(
    `${COMMON_PREAMBLE}\nPAIR: ${p.pair} (county=${p.county}, letters=${p.letters.join(',')})\n\nDIAGNOSIS FROM PRIOR STAGE:\n${JSON.stringify(diag)}\n\nTASK: If has_lever is false, do nothing further — return action_taken="none, structural blocker confirmed" and rows_written=[]. If has_lever is true, execute fix_plan for real: write a script under scripts/ (name it shard1_run11262_${p.pair.replace(/-/g, '_').toLowerCase()}.py or similar, reuse existing helper functions per REUSE-FIRST), run it with python3, and report the ACTUAL row counts written per table from the script's own output (paste the real numbers, never estimate). Only claim VERIFIED counts you saw in command output. Set script_path to the file you wrote (or null if no fix attempted).`,
    { label: `fix:${p.pair}`, phase: 'Fix', schema: FIX_SCHEMA }
  ),
  (fix, p) => agent(
    `${COMMON_PREAMBLE}\nPAIR: ${p.pair} (county=${p.county}, letters=${p.letters.join(',')})\nBASELINE BEFORE THIS SESSION: ${p.before}\n\nFIX STAGE RESULT (claims to adversarially verify):\n${JSON.stringify(fix)}\n\nYOU ARE THE ADVERSARIAL REFUTER. Your only goal is to try to break this claim, per the ULTRALOOP protocol in CLAUDE.md. Steps:\n1. Re-run pencil_dod_evaluate_county('${p.county}') live right now via PostgREST RPC — paste the raw JSON output.\n2. Compare the target letter(s) metric before vs after. Did it actually move? By how much?\n3. Check for anomaly patterns explicitly: denominator/numerator mismatches, double-counting, values outside a sane 0-105% band (the canonical example: brevard B once read 134.1% due to a scope bug — treat >105% or a suspicious jump as FAIL by default), fabricated-looking round numbers, or a script that reported rows_written>0 but the live metric didn't move at all (evidence of a silent no-op or wrong table).\n4. Regression check: for at least the county's other currently-passing letters near this one (spot check 1-2), confirm nothing regressed as a side effect of the fix.\n5. POST one row to gold_standard_ultraloop_audit via PostgREST (columns: dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived) for EACH letter in this pair — dispatch_id="${DISPATCH_ID}", ultraloop_mode="native", county_slug="${p.county}", claim=one-line summary of what was claimed, refuter_evidence=jsonb object with your before/after numbers and reasoning, survived=true only if the letter's live metric now PASSES per pencil_dod_criteria (or, for structural-blocker pairs, survived=false with claim describing the blocker so it's on record, not silently dropped).\n\nReturn your verdict via the schema. moved=true only if the raw before/after numbers you pasted actually differ. survived=true only if you would stake the Honesty Protocol on this claim.`,
    { label: `verify:${p.pair}`, phase: 'Verify', schema: VERIFY_SCHEMA }
  )
)

return { pairs: results.filter(Boolean) }
