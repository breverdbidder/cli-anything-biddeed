export const meta = {
  name: 'gold-standard-shard1-clay-alachua-run7177-39b013c6',
  description: 'Gold Standard shard-1 (dispatch 39b013c6, loop run 7177): clay certification-freshness restore (metric 10/10, cert revoked on stale adversarial audits), alachua E/I/J enrichment for the 10 unlinked-parcel rows, adversarially verify',
  phases: [
    { title: 'Investigate+Fix', detail: 'clay_audit_refresh + alachua_e_enrich agents, worktree-isolated' },
    { title: 'Verify', detail: 'independent refuter per claim' },
  ],
}

const DISPATCH_ID = '39b013c6-4112-4004-92b1-e85938869ce3'

const BASELINE = `Baseline (VERIFIED live via pencil_dod_evaluate_county() + gold_standard_scoreboard + gold_standard_certifications
+ gold_standard_ultraloop_audit freshness query, all run moments ago -- more current than the dispatch brief, treat
this as ground truth):

CLAY: 10/10, ALL PASS (auctions_total=151). A=71(fc=71,td=80) B=100.0(verified=11,closed_sold=11)
C=99.3(matched_clean=150) D=99.3(matched_any=150) E=100.0(parcel_linked=151) F=100.0(tier1_sold=11,closed_sold=11)
G=97.8(density=97.8,far=blank,pk1000=blank) H=0h(SLA 48h) I=99.3(card_complete=150 of 151)
J=100.0(deal_complete=151). gold_standard_scoreboard confirms gold_standard=true, critical_three_pass=true,
evaluated_at=2026-07-29 01:30:00 UTC.

BUT gold_standard_certifications shows clay certified=FALSE, revoked_at=2026-07-28 08:56:40 UTC,
consecutive_gold=0, consecutive_non_gold=15, last_evaluated_run_id=7178,
revocation_reason="clay run=7178 consecutive_non_gold=15 reason=adversarial_survival_4_of_10". Per EVALUATOR V6
RULES, certify() requires survived=true gold_standard_ultraloop_audit rows for ALL 10 letters within a rolling
7-day window, on top of the metric PASS. Fresh per-letter audit query (VERIFIED just now) confirms the exact gap:
  A: last audit 2026-07-20 (8d 8h old -- STALE, outside 7-day window)
  B: last audit 2026-07-20 (8d 8h old -- STALE)
  C: last audit 2026-07-23 (5d 11h old -- inside window but aging)
  D: last audit 2026-07-23 (5d 11h old -- inside window but aging)
  E: last audit 2026-07-20 (8d 8h old -- STALE)
  F: last audit 2026-07-20 (8d 8h old -- STALE)
  G: last audit 2026-07-20 (8d 8h old -- STALE)
  H: last audit 2026-07-20 (8d 8h old -- STALE)
  I: last audit 2026-07-23 (5d 11h old -- inside window but aging)
  J: last audit 2026-07-28 16:42 (10h old -- fresh; J gets audited ~every 8h by an existing automated cadence)
That is exactly 4 of 10 letters (C,D,I,J) inside the 7-day window -- matches "adversarial_survival_4_of_10" in the
revocation reason precisely. THE REAL, CONCRETE GAP FOR CLAY THIS SESSION IS NOT DATA QUALITY (metrics are already
10/10) -- IT IS STALE ADVERSARIAL-AUDIT EVIDENCE on A,B,E,F,G,H (and soon C,D,I too). Fix = genuine fresh skeptical
re-verification of each letter against live tables, logging real gold_standard_ultraloop_audit rows.

ALACHUA: 7/10 (auctions_total=57). A=3(fc=54,td=3) B=100.0(verified=6,closed_sold=6) C=98.2(matched_clean=56)
D=98.2(matched_any=56) F=100.0(tier1_sold=6,closed_sold=6) G=97.9(density=97.9,far=blank,pk1000=blank) H=0h(SLA 48h)
-- all PASS. FAILING: E=82.5(parcel_linked=47 of 57) I=78.9(card_complete=45 of 57) J=82.5(deal_complete=47 of 57).
gold_standard_scoreboard confirms e_parcel_linkage=FAIL, i_property_card=FAIL, j_deal_thesis=FAIL, pass_count=7,
gold_standard=false. Note the dispatch brief's numbers (E=78.9/45, I=78.9/45, J=78.9/45) are stale -- some background
process already moved E/J slightly since the brief was written (45->47); do not re-derive, use the live numbers above.

ROOT CAUSE FOR E (VERIFIED via direct query on multi_county_auctions just now): exactly 10 alachua rows have
parcel_id IS NULL (57-47=10), all sale_type='foreclosure', case numbers: 01 2025 CA 003287 (auction_date
2026-05-04, already past), 01 2025 CA 001928 (2026-05-14, past), 01 2025 CA 002643 (2026-07-23, past/today),
01 2025 CA 001634 (2026-08-11), 01 2023 CA 004261 (2026-08-18), 01 2025 CA 003919 (2026-08-18),
01 2025 CC 001127 (2026-08-27), 01 2026 CA 000211 (2026-08-27), 01 2025 CC 007164 (2026-08-27),
01 2024 CC 005935 (2026-09-01). All 10 have property_address=NULL (except 003287 which has the placeholder string
"ALACHUA COUNTY FL"), no legal_description, no owner_name. 6 of the 10 are data_source='calendar_sweep_mca_v3' stub
rows for auctions 3-5 weeks out.

PRIOR ALACHUA E RESEARCH ALREADY DONE (do not re-derive, extend from this): the working chain (established
2026-07-10, scripts/shard10_run3645_alachua_e_parcel_backfill.py, and multiple follow-on sessions per
GOLD_STANDARD_SHARD10_ALACHUA_DISPATCH_A36233A1_SESSION_REPORT.md) is: (1) RealForeclose's own AJAX calendar
payload (alachua.realforeclose.com, FNC=UPDATE diff endpoint, same harvester as
scripts/shard2_run2450_ajax_realforeclose_harvest.py) embeds a Clerk cross-reference link
isol.alachuaclerk.org/RealEstate/SearchDetail.aspx?docid=<n> in the raw AITEM HTML's Case# column href (NOT parsed
by the existing case_number-only parser -- you must fetch the href, not just the anchor text) for cases the Clerk
has already cross-referenced a recorded document to; (2) for cases WITH a non-empty docid, use Playwright/browser
automation (plain WebFetch/curl is NOT sufficient -- SearchDetail.aspx lazy-loads tab content via client-side JS,
confirmed multiple times) against that docid to get real Grantor/Grantee names + Legal Description (subdivision/lot
or section-township-range); (3) cross-reference those names/legal-description against the Alachua County Property
Appraiser's own public ArcGIS FeatureServer (PublicParcel/FeatureServer/0) by Owner_Mail_Name or lot-number-encoded
parcel suffix pattern to resolve exactly one parcel_id -- only write if the match is UNIQUE and non-ambiguous (bulk
developer/LLC holders of many parcels in one plat need the lot-number-suffix trick, documented in the script). CASES
ALREADY CONFIRMED GENUINELY BLOCKED as of 2026-07-10 (empty docid in the AJAX payload = Clerk has not
cross-referenced any document yet, a true source-side gap, not fixable without fabrication): 01 2025 CA 001928 (one
of the 4 confirmed-empty then), plus case 01 2025 CA 003287 was found to be "MULTIPLE PARCEL" per its own legal
description (spans 3 lots) and was correctly SKIPPED rather than guessing which lot -- do not attempt to force a
single parcel_id onto it. qpublic.schneidercorp.com (an alternate Alachua appraiser search UI) returns HTTP 403 from
Cloudflare on every plain request -- do not waste time on it, use the ArcGIS FeatureServer directly instead. The 6
newer calendar_sweep_mca_v3 stub rows (001634, 004261, 003919, 001127, 000211, 007164, 005935 -- note 005935 is
also new) have NOT been attempted by any prior session -- these are your highest-value fresh targets, but expect
several to be genuinely blocked too (future-dated auctions 3-5 weeks out commonly have no Clerk cross-reference yet
and, per Florida court e-filing latency, cases with a CC (county court) case-type prefix are often quiet-title or
tax-related actions distinct from the CA foreclosure docket -- verify case type before assuming a foreclosure
lookup path applies).`

const RECIPE = `
Environment (already available, do not ask for credentials):
- Live arbitrary SQL (the ONLY working direct-DB path -- plain psql/pooler connections FAIL with password auth
  errors, confirmed this session, do not waste time on that): POST
  https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query
  headers Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json
  body {"query": "<sql>"} -- run "SET statement_timeout = 0;" first in the same query string for anything heavy.
  Build the JSON body with a real encoder (python3 -c "import json; ..." to a temp file, then curl --data-binary
  @file) rather than hand-quoting shell strings.
- REST reads/writes: GET/PATCH/POST \${SUPABASE_URL}/rest/v1/<table>?... with headers
  apikey: $SUPABASE_SERVICE_ROLE_KEY, Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY
- pencil_dod_evaluate_county RPC (confirmed live this session; NOTE the param name is p_county, not
  county_slug_arg): POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county body {"p_county": "clay"} (or
  "alachua") -- returns one jsonb object with keys A..J (each {pass,metric,detail}), county, auctions_total,
  V2_LITMUS. This is your before/after proof. C/D require parity_status='matched_clean' (C) or IN
  ('matched_clean','matched_divergent') (D) AND parity_source LIKE 'tier1%%' -- setting parity_status alone does
  NOT satisfy C/D. E = parcel_id IS NOT NULL, no threshold beyond 95%%. I additionally requires property_address,
  lat/long (or po_latitude/po_longitude), assessed_value/market_value ALL non-null AND the parcel_id present with
  zone_code in v_zoning_gold_standard_card. J requires a bid_decisions row matched by case_number with
  arv+max_bid+ml_score+all 5 factor keys (distress_location, distress_property, distress_owner, cma_distressed,
  cma_resale).
- gold_standard_scoreboard and gold_standard_certifications tables are readable via REST or the Management API SQL
  endpoint -- use them to confirm certification-eligibility state, but do NOT write to gold_standard_certifications
  yourself, it is written only by the automated gold_standard_certify() cron.
- The canonical parity matcher is public.refresh_parity_tier1_outcomes(p_county text default 'brevard') -- an RPC,
  not something to reimplement. Call it via the Management API SQL endpoint
  (SELECT * FROM public.refresh_parity_tier1_outcomes('alachua');) after inserting/updating rows, never hand-write
  parity_status/parity_source yourself.
- realforeclose.com and alachuaclerk.org hosts are JS-gated for docid tab content (SearchDetail.aspx lazy-loads via
  client-side JS) -- use the firecrawl-browser or browser-use skill (rendered session) for these, not raw
  WebFetch/curl. qpublic.schneidercorp.com 403s Cloudflare on every plain request -- do not use it; use the Alachua
  ArcGIS PublicParcel FeatureServer (see BASELINE) directly instead.
- gh CLI is authenticated (repo, workflow scopes) for git operations. FIRECRAWL_API_KEY is set in env.
- Repo root is the current working directory (worktree-isolated), on main. Any UPDATE to multi_county_auctions
  columns is a data backfill, not a schema change -- still write a short documentation migration file under
  supabase/migrations/<date>_shard1_clay_<purpose>.sql or supabase/migrations/<date>_shard1_alachua_<purpose>.sql
  per this campaign's house style: narrative comment block with VERIFIED evidence, then the idempotent SQL that
  mirrors what you ran live. Any genuine schema change (new column, new table) needs a real migration, not just
  documentation.

ULTRALOOP audit logging (mandatory): for every letter you claim moved OR claim you verified as
correctly-passing/correctly-blocked/residual, INSERT one row into public.gold_standard_ultraloop_audit: columns
dispatch_id (uuid '${DISPATCH_ID}'), ultraloop_mode ('fallback' -- manual Workflow-tool fan-out, not native
/effort ultracode), county_slug, letter, claim (short text), refuter_evidence (jsonb -- your evidence), survived
(boolean, true only if it held up under adversarial check). POST to
\${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with service-role headers. For clay this IS the primary
deliverable, not a formality -- certification is blocked purely on the absence of these rows within the 7-day
window, so log one genuinely-checked row per letter (A,B,C,D,E,F,G,H,I,J), even the ones that are already fresh
(re-confirm them too rather than skipping, since a couple age out within days).

Hard rules:
- You own ONLY clay and alachua. Never touch any other county's rows or any other shard's files. Other shards
  (including a bradford-only shard on this SAME loop run 7177) are running concurrently -- git pull --rebase before
  every push.
- PropertyOnion is litmus/comparison ONLY -- never write po_* derived values in as verified/independent.
- Fail-loud invariant: if a fix attempt finds zero real data for a row, report it as blocked/residual. NEVER
  fabricate case numbers, parcel IDs, addresses, coordinates, or sold amounts to make a metric look better -- this
  campaign has a documented fabrication-then-purge history in another county (dixie B/F, 2026-07-10); do not repeat
  it in any form, in either direction. Do NOT force a single parcel_id onto a "MULTIPLE PARCEL" case (e.g. 003287)
  -- that is the documented anti-pattern this campaign already caught once.
- Every claim must be tagged VERIFIED (you ran the query/request and are pasting real output), UNTESTED, or
  INFERRED (say why).
- Before finishing: call pencil_dod_evaluate_county for your county and paste the FULL before/after JSON. If a
  letter did not move, say so plainly -- a genuinely source-exhausted row is a valid, honest outcome.
- git commit any file you create/modify with a clear, county-scoped message. 'git pull --rebase origin main' before
  pushing (other shards may push concurrently to shared paths). Push directly to main -- no branches, no PRs.
- Do NOT run public.gold_standard_loop() or gold_standard_certify() -- another shard (bradford, same loop run 7177)
  is likely mid-session. Do NOT modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job.
- Budget yourself: this is ONE bounded pass. If a true fix requires building a brand-new scraper, do NOT build it
  now -- size the gap precisely and report it as scoped-out residual.

Return: { letters_touched: [...], fix_summary, sql_or_endpoints_used: [...], before_json, after_json,
residual_gaps: [...], honesty_notes: [...] }.
`

const TASKS = [
  {
    key: 'clay_audit_refresh',
    county: 'clay',
    prompt: `You are working Gold Standard shard-1, county "clay", ALL 10 letters (A-J), inside the
cli-anything-biddeed repo (already checked out, on main). Clay is metric-PASS 10/10 but certification is currently
REVOKED because 6 of 10 letters' adversarial-audit evidence (gold_standard_ultraloop_audit) has gone stale (>7
days). Your job is NOT to fix data -- it is to genuinely, skeptically re-verify each letter against LIVE tables and
log fresh evidence.

${BASELINE}

Your job, in priority order:
1. Re-verify A,B,E,F,G,H FIRST (these are the 8-day-stale ones, most urgent). For each letter, run a real query
   against live tables (not just re-reading pencil_dod_evaluate_county's summary number) that would catch the kind
   of problem this campaign has hit before in other counties -- ghost-success (placeholder/default values passed
   off as real), denominator mismatches, PropertyOnion-derived data masquerading as independent. Suggested checks:
   - A: recount fc/td by sale_type fresh, confirm fc=71 td=80 (or whatever it is right now).
   - B: spot-check 2-3 of the 11 verified outcomes have real, non-PropertyOnion data_source values in
     tax_deed_outcomes/foreclosure_outcomes, not fabricated/promoted rows. Confirm ratio is in the 95-105%% valid
     band (100%% here, but recompute the numerator/denominator from source tables, not the cached percentage).
   - E: spot-check a handful of parcel_id values are real Clay County parcel/STRAP formats, not placeholders like
     "Property Appraiser" or "MULTIPLE PARCEL" or empty strings.
   - F: confirm real sold amounts for the 11 tier1_sold rows, not zeros or round-number placeholders.
   - G: via v_zoning_gold_standard_kpi_v3 / v_zoning_district_applicability, confirm the blank far/pk1000 for clay
     genuinely means no applicable districts (legitimate N/A), not missing data silently excluded from the
     denominator.
   - H: confirm last_seen_at values are genuine recent scrape timestamps, not stale/frozen.
2. Then re-verify C,D,I (5-day-stale, less urgent but aging) and J (already fresh from an existing ~8h automated
   cadence -- log one more fresh row anyway to keep it current, but do not spend much time here).
   - C/D: spot-check a few rows' parity_source actually starts with 'tier1', not just parity_status being set.
   - I: spot-check card fields (address, geo, value, zoned parcel) are non-placeholder for a couple of sampled
     rows.
   - J: spot-check bid_decisions rows have real arv/max_bid/ml_score and all 5 factor keys, not zeros/nulls.
3. Log ONE gold_standard_ultraloop_audit row per letter (10 total minimum) with survived=true ONLY if your check
   genuinely held up -- if you find a real problem in any letter, do NOT rubber-stamp it; investigate, fix if small
   and surgical, or log survived=false with the honest reason (this would be a significant, reportable finding
   since it would mean clay's PASS is currently wrong).
4. Do not run gold_standard_certify() yourself -- once the audit rows are fresh, the existing automated cron will
   pick it up. Your job ends at logging genuine fresh evidence.

${RECIPE}`,
  },
  {
    key: 'alachua_e_enrich',
    county: 'alachua',
    prompt: `You are working Gold Standard shard-1, county "alachua", letters E/I/J (C/D/A/B/F/G/H already PASS,
leave them alone unless your work on E has a direct side effect), inside the cli-anything-biddeed repo (already
checked out, on main).

${BASELINE}

Your job, in priority order:
1. For each of the 10 unlinked-parcel rows listed in BASELINE, attempt REAL enrichment via the established chain:
   (a) fetch alachua.realforeclose.com's live AJAX calendar payload for that case's auction_date (use the same
   FNC=UPDATE diff-endpoint pattern as scripts/shard2_run2450_ajax_realforeclose_harvest.py) and extract the raw
   href on the Case# column, not just the anchor text, to find the isol.alachuaclerk.org SearchDetail.aspx?docid=
   link; (b) if a non-empty docid exists, use the firecrawl-browser or browser-use skill (JS-rendering required,
   plain WebFetch/curl will NOT surface the lazy-loaded tab content) to pull Grantor/Grantee + Legal Description;
   (c) cross-reference against the Alachua County Property Appraiser's public ArcGIS PublicParcel FeatureServer by
   owner name or legal-description/lot-number pattern to resolve exactly ONE unambiguous parcel_id. If a case has
   multiple plausible parcels (bulk owner, multi-lot legal description) and you cannot disambiguate to one, do NOT
   guess -- leave it blocked and say so. If a case has an empty docid in the AJAX payload, or produces zero/multiple
   ArcGIS matches, it is genuinely blocked -- report it plainly, do not fabricate.
2. For any row you successfully resolve, UPDATE multi_county_auctions (parcel_id, and property_address if you also
   found a real verified site address) via PostgREST, then run public.refresh_parity_tier1_outcomes('alachua') via
   the Management API SQL endpoint to let the canonical matcher recompute parity_status/parity_source, then
   re-check pencil_dod_evaluate_county for E, I (needs zone_code via v_zoning_gold_standard_card too -- a row can
   gain a real parcel_id and still miss I if alachua zoning coverage doesn't reach that parcel; check and report
   this distinction if it happens), and J (check whether bid_decisions already has a generator picking up newly
   linked parcels automatically -- alachua's J metric has already been tracking E's metric almost exactly [47 vs 47
   in the live baseline], suggesting a fleet-wide J generator already exists and reacts to new parcel linkage; if
   so you likely do not need to build anything for J, just confirm it picked up your new rows -- if J does NOT
   move after E does, investigate why before assuming you need to build a new generator, and do not build one this
   session if the gap is large, just size and report it).
3. Case 01 2025 CA 003287 was previously confirmed "MULTIPLE PARCEL" (legal description spans 3 lots) -- do not
   force a single parcel_id onto it; re-confirm this is still true (sources can update) but expect it to remain
   blocked.
4. Log gold_standard_ultraloop_audit rows for E, I, and J per the RECIPE, whether you moved them or conclusively
   re-confirmed them as genuinely blocked.

${RECIPE}`,
  },
]

phase('Investigate+Fix')
const fixResults = await pipeline(
  TASKS,
  (task) => agent(task.prompt, {
    label: `fix:${task.key}`,
    phase: 'Investigate+Fix',
    isolation: 'worktree',
    schema: {
      type: 'object',
      properties: {
        task: { type: 'string' },
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
  (result, task) => agent(
    `Independently verify this claimed Gold Standard result for shard-1 (${task.county}), task "${task.key}". ` +
    `You did NOT write this -- be skeptical.\n\n` +
    `Claimed result: ${JSON.stringify(result)}\n\n` +
    `${RECIPE}\n\n` +
    `Your job: re-run pencil_dod_evaluate_county('${task.county}') yourself RIGHT NOW (fresh call, do not trust ` +
    `the pasted after_json), compare against the claimed before/after, and check specifically for: (a) denominator ` +
    `mismatches, (b) ghost-success (any letter now passing/still-passing because of a placeholder/fabricated/` +
    `default value rather than a real fix or a genuinely-verified real value), (c) whether any OTHER letter ` +
    `regressed as a side effect, (d) for B specifically, the only valid pass band is 95-105%%, (e) for the clay ` +
    `task specifically, spot-check that at least 2-3 of the newly-inserted gold_standard_ultraloop_audit rows cite ` +
    `real, non-boilerplate refuter_evidence (a genuine query result, not a copy-pasted template), (f) for the ` +
    `alachua task, if any parcel_id was written, independently re-query the Alachua ArcGIS PublicParcel ` +
    `FeatureServer yourself for that parcel_id and confirm it is real and matches the claimed evidence -- do not ` +
    `just trust the claim. Also INSERT your own gold_standard_ultraloop_audit row per the RECIPE ` +
    `(ultraloop_mode='fallback'). Return { task, refuted: boolean, refutation_reason: string|null, ` +
    `fresh_evaluation: <the JSON you just got>, survives: boolean }.`,
    {
      label: `verify:${task.key}`,
      phase: 'Verify',
      schema: {
        type: 'object',
        properties: {
          task: { type: 'string' },
          refuted: { type: 'boolean' },
          refutation_reason: { type: ['string', 'null'] },
          fresh_evaluation: {},
          survives: { type: 'boolean' },
        },
        required: ['refuted', 'fresh_evaluation', 'survives'],
      },
    }
  )
)

return { fixResults, verified }
