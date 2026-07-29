export const meta = {
  name: 'gold-standard-shard8-okeechobee-run7283-4bc551f5',
  description: 'Gold Standard shard-8 okeechobee-only (dispatch 4bc551f5, loop run 7283): dedup 7 mislabeled sale_type duplicate rows, TaxSmartWeb+FL-GIO enrich 24 genuine upcoming tax_deed rows for C/D/I, adversarially verify',
  phases: [
    { title: 'Diagnose+Fix', detail: 'single county, worktree-isolated' },
    { title: 'Verify', detail: 'independent refuter' },
  ],
}

const DISPATCH_ID = '4bc551f5-b43e-4c14-9ac3-4fac58e37c1a'

const CONTEXT = `
Baseline (VERIFIED live via pencil_dod_evaluate_county RPC just now, matches the brief exactly):
{"A":{"pass":true,"metric":41,"detail":"fc=56 td=41"},"B":{"pass":true,"metric":100.0,"detail":"verified=6 closed_sold=6"},
"C":{"pass":false,"metric":68.0,"detail":"matched_clean=66"},"D":{"pass":false,"metric":68.0,"detail":"matched_any=66"},
"E":{"pass":true,"metric":100.0,"detail":"parcel_linked=97"},"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=6 closed_sold=6"},
"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.1},"I":{"pass":false,"metric":68.0,"detail":"card_complete=66 of 97"},
"J":{"pass":true,"metric":100.0,"detail":"deal_complete=97"}, "auctions_total":97}
Target letters: C, D, I (critical-three letter I included; B is critical-three and already passes at exactly 100.0 -- do
not touch it, and if any of your work changes closed_sold/verified_outcomes counts, re-check B stays in the 95-105 band).

ROOT-CAUSE DIAGNOSIS (VERIFIED this session via direct SQL against multi_county_auctions, GROUP BY sale_type/parity_status/
null-field-flags, cross-referenced against pipeline.counties and bid_decisions -- re-verify yourself before acting, this is
a starting point not gospel):

okeechobee has 97 rows total, 66 matched_clean (parity_source LIKE 'tier1%'), 31 unmatched (parity_status IS NULL). All 97
already have parcel_id (E=100%, do not re-touch E). The 31-row gap splits into TWO distinct issues:

ISSUE 1 -- 7 duplicate/mislabeled rows (case_numbers 2026TD055, 2026TD070, 2026TD052, 2026TD072, 2026TD080, 2026TD081,
2026TD079; ids ba97fc75-8327-431b-8760-c2b621096ea4, 56013ad4-f9a4-47e0-937a-f7ead876bc24, 26ceeb9b-682a-4c5f-94b6-
c74dea0618d3, 54ab4f12-c1be-4562-80df-e862742dcdba, 4d226d0c-0297-46f6-87f7-69d25dd266e0, a73e6ac0-eebe-4101-9fd4-
8cc4a533b19b, 2ade10e5-cbd5-4a75-a937-285145ad41aa). These rows carry sale_type='foreclosure' but "TD"-prefixed case
numbers (Florida clerk convention: TD = Tax Deed docket, never used for foreclosure/CA cases -- real okeechobee foreclosure
cases use the format 472025CA000130CAAXMX per prior-session notes), data_source IS NULL, created_at='2026-07-27' (2 days
before this session, i.e. a recent seed), and every one of parcel_id+address+lat+value is null or near-null. For EACH of
these 7 case_numbers, an EXACT-MATCHING row already exists with sale_type='tax_deed', the SAME case_number, the SAME
auction_date, a real parcel_id, parity_status='matched_clean', and parity_source
'tier1_okeechobee_clerk_taxsmart:GridSearchData:cert_XXXX-2024' (a real Okeechobee Clerk TaxSmartWeb certificate match) --
i.e. these are literal duplicate seed-insert junk from calendar_sweep_mca_v3 misclassifying tax-deed calendar items as
sale_type='foreclosure'. Confirmed further: scripts/shard8_okeechobee_cd_parity_new_dates.py (a PRIOR session, dispatch
ac288257, different from today's 4bc551f5) already attempted to harvest these exact 7 (well, 8 -- one more, 2026TD040/045/
046/047/048 also mentioned) via the okeechobee.realforeclose.com AJAX foreclosure platform and evidently found nothing (they
remain unmatched/data_source NULL today) -- consistent with fail-loud behavior (no fabrication) on a genuinely nonexistent
foreclosure case, further confirming these are misclassified tax-deed duplicates, not real foreclosure records.
Also VERIFIED this session: bid_decisions rows for these case_numbers exist keyed by (county_slug, case_number) --
NOT by multi_county_auctions.id -- so deleting these 7 auction rows will NOT orphan or break J (the real tax_deed row
with the same case_number remains and J's join is by case_number). NOTE (out of scope, do not act on it, just log as a
residual honesty_note): bid_decisions has heavy row-level duplication for okeechobee (dozens of rows per case_number,
likely from repeated un-deduped cron 109 runs) -- do NOT touch cron 109 or attempt a bid_decisions dedup, that is explicitly
out of scope per the campaign's hard guardrails; just note it.
YOUR FIX for issue 1: independently re-verify each of the 7 pairs yourself (do not trust this summary blindly -- confirm
live), then DELETE the 7 bogus sale_type='foreclosure' duplicate rows from multi_county_auctions (by id, listed above).
This is a data-hygiene/dedup fix, not fabrication -- you are removing rows that duplicate already-correct, already-matched
records, not adding unverified data. If ANY of the 7 does NOT have a matching real tax_deed counterpart when you check,
do NOT delete that one -- treat it as a residual gap instead and say so.

ISSUE 2 -- 24 genuine, non-duplicate upcoming tax_deed rows (data_source='calendar_sweep_mca_v3', auction dates spanning
2026-08-06 through 2026-09-17, real distinct case_numbers e.g. 2026TD049, 2026TD050, 2026TD041, 2026TD042, 2026TD044,
2026TD065, 2026TD068, 2026TD069, 2026TD073, 2026TD053, 2026TD054, 2026TD056, 2026TD057 and 11 more -- re-query yourself for
the full live list, WHERE county='okeechobee' AND sale_type='tax_deed' AND parity_status IS NULL, these do NOT overlap with
the issue-1 case numbers). Each already has a real parcel_id (from prior E-linkage work) but lacks parity_status,
property_address, latitude/longitude, and assessed_value.
Existing proven tooling: scripts/shard9_okeechobee_taxsmartweb_litmus.py hits the Okeechobee Clerk's public, anonymous,
no-login TaxSmartWebLive system (https://pioneer.okeechobeelandmark.com/TaxSmartWebLive, confirmed live 2026-07-02) via
fetch_taxsmartweb_case(case_number) and writes parity_status='matched_clean'/parity_source=
'tier1_okeechobee_taxsmartweb_clerk_shard9:<date>' through apply_match() -- this is your PROVEN path for the C/D half of
issue 2. Run/adapt it (update the source-date suffix, do not silently overwrite the file's original intent) against all 24
case_numbers. NOTE the TaxSmartWeb cell payload does NOT include property_address/lat/lon/assessed_value (only applicant,
case_number, cert_number, parcel_id, auction_date, status, opening_bid) -- it moves C/D but NOT I on its own.
For I (card_complete needs property_address + latitude/longitude + assessed_value + a zoned parcel match, in addition to
the parcel_id these rows already have), since every row already has a real parcel_id, the FL GIO statewide cadastral API
(same one scripts/ingest_county.py uses for the campaign's Phase-1 baseline ingestion, keyed by parcel ID / PARCEL_ID field,
returns site address + JV assessed value + geometry centroid for lat/lon) is the fastest real path -- find okeechobee's
co_no by querying the FL GIO service or grepping scripts/ingest_county.py's county table (do not guess it), then look up
each of the 24 parcel_ids and backfill property_address/latitude/longitude/assessed_value from real FL GIO response fields
only. If FL GIO doesn't cover a parcel cleanly, the Okeechobee Property Appraiser (search for an existing okeechobee PA
GIS/search endpoint, e.g. via pipeline.counties.parcel_data_url or a fresh web search) is the fallback -- but do not
fabricate or estimate any value; a row you can't source stays incomplete and gets reported as residual, tagged UNTESTED
or the honest gap, never guessed.

Existing scripts to check before writing anything new (avoid duplicating): scripts/shard9_okeechobee_taxsmartweb_litmus.py,
scripts/shard9_run3534_okeechobee_cd_tier1.py, scripts/shard8_okeechobee_cd_parity_new_dates.py,
scripts/shard_gs_clay_okeechobee_cd_parity.py, scripts/gold_standard_shard6_walton_okeechobee_gulf_fd6f48d0.py,
scripts/enrich_property_cards.py (generic I-enrichment template for indian_river/osceola/sarasota -- okeechobee is not
configured in it; you may extend its COUNTY_APPRAISERS dict with a real okeechobee entry if useful, or just query FL GIO
directly, your call, but read it first so you don't reinvent an already-solved pattern).
`

const RECIPE = `
Environment (already available, do not ask for credentials):
- REST API reads/writes: GET/PATCH/POST/DELETE \${SUPABASE_URL}/rest/v1/<table>?... with headers
  apikey: $SUPABASE_SERVICE_ROLE_KEY, Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY
- Live arbitrary SQL (verified working this session): POST
  https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query
  headers Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json
  body {"query": "<sql>"} -- run "SET statement_timeout = 0;" first in the same query string for anything heavy.
  Build this JSON with a real JSON encoder (python3 -c "import json; ..." to a temp file, then curl --data-binary @file)
  rather than hand-quoting shell strings. Direct psql to the pooler FAILED this session (password auth error) -- use the
  Management API path, not psql, unless you first confirm psql works for you. Some heavy/complex queries (e.g.
  pg_get_viewdef) timed out at 2 minutes this session over this HTTP path -- keep queries targeted and add explicit
  WHERE/LIMIT clauses rather than broad introspection queries.
- pencil_dod_evaluate_county RPC: POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county
  headers apikey/Authorization as above, body {"p_county": "okeechobee"} -- this is your before/after proof. C/D require
  parity_status='matched_clean' (or matched_any-equivalent for D) AND parity_source LIKE 'tier1%' -- parity_status alone is
  NOT sufficient. Rows with data_source='propertyonion' and tier1_authoritative != true are excluded from the denominator
  entirely (do not worry about PropertyOnion rows for okeechobee, none were found in this county's data this session).
- gh CLI is authenticated (repo, workflow scopes) for git operations and workflow dispatch if needed.
- Repo root is the current working directory, on main. Schema changes MUST go through a migration file under
  supabase/migrations/<date>_shard8_okeechobee_<purpose>.sql, committed to git -- even though you CAN run SQL directly via
  the Management API, still write the migration file for the historical record and apply it the same way. Simple data
  backfills/deletes (no schema change) do not need a migration file -- just do the REST call and note the exact
  SQL/endpoint used in your report.

ULTRALOOP audit logging (mandatory per campaign protocol, docs/ULTRALOOP-SSOT.md): for every letter you claim moved (or
verified as correctly-blocked/residual), INSERT one row into public.gold_standard_ultraloop_audit: columns dispatch_id
(uuid '${DISPATCH_ID}'), ultraloop_mode ('fallback' -- this session used manual Task/Workflow subagent fan-out, not native
/effort ultracode), county_slug ('okeechobee'), letter, claim (short text), refuter_evidence (jsonb -- for the FIX agent,
your own before/after evidence; for the VERIFY agent, your refutation attempt and findings), survived (boolean -- true
only if the claim held up under adversarial check). POST to \${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with the
service-role headers above. Do this as normal work, not an afterthought.

Hard rules (from the campaign brief -- follow exactly):
- You own ONLY okeechobee. Never touch any other county's rows.
- PropertyOnion is litmus/comparison ONLY -- never write po_* derived values in as if verified/independent.
- Fail-loud invariant: if a fix attempt finds zero real data for a row, report it as a blocked/residual gap. NEVER
  fabricate case numbers, parcel IDs, addresses, sale amounts, coordinates, or timestamps to make a metric look better.
  This campaign has a documented history of exactly this failure mode (ghost-success fabrication) in sibling shard-8
  counties (walton, baker, okaloosa) -- do not repeat it in any form, including "close enough" placeholder values.
- Every claim you return must be tagged VERIFIED (you ran the query/request and are pasting real output), UNTESTED, or
  INFERRED (say why).
- Before finishing: call pencil_dod_evaluate_county('okeechobee') fresh and paste the FULL before (given above, or
  re-verify if you suspect drift) and after JSON. If a letter did not move, say so plainly.
- git commit any file you create/modify with a clear, county-scoped message. Run 'git pull --rebase origin main' before
  pushing (other shards may be pushing concurrently to shared paths). Push directly to main -- no branches, no PRs, per
  the SHIP-TO-MAIN MANDATE.
- Do NOT run public.gold_standard_loop() or gold_standard_certify() -- other shards may be mid-session. Do NOT modify
  cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job. Do NOT touch bid_decisions deduplication (noted as
  out-of-scope residual above).
- Budget yourself: this is ONE bounded pass. If real work requires something you cannot complete (e.g. FL GIO doesn't
  cover a parcel, TaxSmartWeb has no record for a case), size the gap precisely, report it as a scoped residual, and ship
  whatever smaller, real, verifiable improvement IS achievable. Do not force all 24 rows to complete if some genuinely
  can't be sourced -- partial, honest progress beats a fabricated 100%.

Return a structured report: { county: 'okeechobee', letters_touched: [...], fix_summary, sql_or_endpoints_used: [...],
before_json, after_json, residual_gaps: [...], honesty_notes: [...] }.
`

phase('Diagnose+Fix')
const fixResult = await agent(
  `You are working Gold Standard shard-8, county "okeechobee", inside the cli-anything-biddeed repo (already checked out, on main).\n\n${CONTEXT}\n\n${RECIPE}`,
  {
    label: 'fix:okeechobee',
    phase: 'Diagnose+Fix',
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
      },
      required: ['county', 'fix_summary', 'before_json', 'after_json'],
    },
  }
)

phase('Verify')
const verified = fixResult ? await agent(
  `Independently verify this claimed Gold Standard fix for county "okeechobee". You did NOT write this fix -- be skeptical.\n\n` +
  `Claimed result: ${JSON.stringify(fixResult)}\n\n` +
  `${RECIPE}\n\n` +
  `Your job: re-run pencil_dod_evaluate_county('okeechobee') yourself RIGHT NOW (fresh call, do not trust the pasted ` +
  `after_json), compare against the claimed before/after, and check specifically for: (a) denominator mismatches -- does ` +
  `auctions_total still make sense (started at 97; if the fix agent deleted the 7 duplicate rows, 97-7=90 is the expected ` +
  `new total -- confirm this, and be suspicious of any other change to the total), (b) ghost-success -- did the fix agent ` +
  `write any property_address/latitude/assessed_value that isn't traceable to a real, citable source (FL GIO response, ` +
  `TaxSmartWeb cell, or an appraiser page) -- spot-check at least 3 of the newly-enriched rows by independently re-fetching ` +
  `the SAME source yourself and confirming the value actually appears there, (c) did the 7-row delete actually verify a ` +
  `real tax_deed counterpart existed for each deleted case_number before deleting (query multi_county_auctions yourself for ` +
  `at least 3 of the 7 case_numbers and confirm exactly one row remains, with parity_status='matched_clean'), (d) did B ` +
  `stay in the 95-105%% band (it must, it's critical-three and started at exactly 100.0%%), (e) did any OTHER letter ` +
  `(A, E, F, G, H, J) regress as a side effect -- especially J, since bid_decisions duplication was flagged as a risk. ` +
  `Also INSERT your own gold_standard_ultraloop_audit row per the RECIPE instructions (ultraloop_mode='fallback') for ` +
  `each letter you're adjudicating. Return { county: 'okeechobee', refuted: boolean, refutation_reason: string|null, ` +
  `fresh_evaluation: <the JSON you just got>, survives: boolean }.`,
  {
    label: 'verify:okeechobee',
    phase: 'Verify',
    schema: {
      type: 'object',
      properties: {
        county: { type: 'string' },
        refuted: { type: 'boolean' },
        refutation_reason: { type: ['string', 'null'] },
        fresh_evaluation: {},
        survives: { type: 'boolean' },
      },
      required: ['county', 'refuted', 'fresh_evaluation', 'survives'],
    },
  }
) : null

return { fixResult, verified }
