export const meta = {
  name: 'gold-standard-shard4-dixie-run6080',
  description: 'Gold Standard shard-4 dixie (dispatch 2a2187fa, loop run 6080): C/D fresh-check on 15-2023-CA-57 (sale date now passed) + 7-day audit-freshness sweep on the 8 stale-but-passing letters, adversarially verify',
  phases: [
    { title: 'Investigate+Fix', detail: 'cd_recheck + audit_sweep agents, worktree-isolated' },
    { title: 'Verify', detail: 'independent refuter per claim' },
  ],
}

const DISPATCH_ID = '2a2187fa-aa9f-426d-aa6f-f560909568d2'

const BASELINE = `Baseline (VERIFIED live via pencil_dod_evaluate_county('dixie') just now, matches the brief exactly): 8/10.
A=PASS metric=2 (fc=2 td=31). B=PASS metric=100.0 (verified=12 closed_sold=12). C=FAIL metric=75.8 (matched_clean=25).
D=FAIL metric=75.8 (matched_any=25). E=PASS metric=97.0 (parcel_linked=32). F=PASS metric=100.0 (tier1_sold=12
closed_sold=12). G=PASS metric=100.0 (density=100.0 far=100.0 pk1000=null/no-applicable-parcels). H=PASS metric=2.8h
(hours since last_seen, SLA 48h -- NOTE this metric drifts every time you re-query since it's a live "hours since
last scrape" clock; do not treat a slightly different number as a regression). I=PASS metric=97.0 (card_complete=32
of 33). J=PASS metric=100.0 (deal_complete=33). auctions_total=33.

CRITICAL PRIOR CONTEXT ON C/D -- read this in full before touching anything, this county has been independently
re-investigated at LEAST 8 times over 3 weeks (2026-07-04 through 2026-07-19):
  - Structural ceiling repeatedly re-confirmed: 33 total rows, 25 matched_clean, 8 unmatched. Of the 8: 6 are stale
    'DIXIE-SYNTH-*' tax-deed placeholder rows dated Aug 2025 (~11 months overdue on dixieclerk.com, status still
    reads 'scheduled' on the clerk's OWN site every time it's been checked -- 8+ source-exhaustion attempts across
    sessions: dixieclerk.com/tax-deed-sales + /tax-deeds/, dixietax.com (Cloudflare-blocked), qpublic.net/fl/dixie
    (Cloudflare hard-blocked), kofilequicklinks.com/DixieFL (no parcel-ID search field), civitekflorida.com/ocrs
    (court case index, not property/deed DB, and these are DIXIE-SYNTH placeholder identifiers not real case
    numbers anyway), myfloridacounty.com/orisearch/15 (Cloudflare Turnstile CAPTCHA-gated, cannot pass headless,
    confirmed on 3 separate attempts + later found NXDOMAIN from this sandbox), FL DOR Statewide Cadastral NAL
    FeatureServer (zero features -- Dixie's real DOR parcel STRAP format doesn't match our stored parcel_id format
    for these synthetic rows), RealTaxDeed/RealForeclose alt-subdomains (dead/redirect), GovEase/LienHub/Bid4Assets
    (none found), F.S.197.582 surplus-funds list (no public data). DO NOT re-run any of these 8 probes again without
    a concrete reason to think something changed -- re-litigating an exhausted lead is wasted budget, not diligence.
  - The other 2 unmatched are real, non-synthetic foreclosure cases: 15-2025-CA-46 (genuinely future, due
    2026-08-25, correctly unmeasurable, do not touch) and 15-2023-CA-57.

THE ONE THING THAT HAS GENUINELY CHANGED (worth exactly one fresh, real attempt -- this is why this county is in
today's shard): 15-2023-CA-57's sale date was 2026-07-21. As of the last investigation session (2026-07-19), it was
still 2 days in the future and correctly unresolved. Today is 2026-07-24 -- the sale date is now 3 days IN THE PAST.
Live query just now confirms multi_county_auctions already has auction_status='sold' for this case (from
dixieclerk.com_shard6_scraper, source_platform=clerk_website) but parity_status is still NULL -- meaning no
independent tax_deed_outcomes/foreclosure_outcomes row has been harvested+matched for it yet. This is a real,
achievable, non-duplicate lead. If it resolves cleanly it moves C/D from 25/33 (75.8%) to 26/33 (78.8%) -- still
short of the 95% gate on its own, but it is genuine progress and, per the 2026-07-19 session's own ceiling math (31/33
max assuming only the 6 synth rows never resolve), getting this row counted raises the true achievable ceiling to
32/33=97.0% -- ABOVE the 95% threshold -- if the 6 synth rows were ever to resolve. That reframes C/D from "hard
93.9% ceiling" to "97.0% ceiling, currently capped at 78.8% by 6 genuinely-stuck rows", which is worth documenting
precisely even if you can't close the remaining gap this session.`

const RECIPE = `
Environment (already available, do not ask for credentials):
- Live arbitrary SQL (the ONLY working DB path -- direct psql/pooler connections FAIL with password auth errors,
  reconfirmed this session, do not waste time on that): POST
  https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query
  headers Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json
  body {"query": "<sql>"} -- run "SET statement_timeout = 0;" first in the same query string for anything heavy.
  Build the JSON body with a real encoder (python3 -c "import json; ..." to a temp file, then curl --data-binary
  @file) rather than hand-quoting shell strings.
- REST reads/writes: GET/PATCH/POST \${SUPABASE_URL}/rest/v1/<table>?... with headers
  apikey: $SUPABASE_SERVICE_ROLE_KEY, Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY
- pencil_dod_evaluate_county RPC: POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county
  body {"p_county": "dixie"} -- this is your before/after proof. The live function filters
  multi_county_auctions to lower(county)='dixie' AND (data_source <> 'propertyonion' OR tier1_authoritative=true).
  C/D require parity_source LIKE 'tier1%%' in addition to parity_status -- setting parity_status alone does NOT
  satisfy C/D. B only passes in the 95-105%% band. G = LEAST(density,far,pk1000) from v_zoning_gold_standard_kpi_v3,
  gated by v_zoning_district_applicability (a genuinely-not-applicable dimension does not count against the
  denominator).
- The canonical parity matcher is public.refresh_parity_tier1_outcomes('dixie') -- an RPC, not something to
  reimplement. Call it via the same Management API SQL endpoint (SELECT * FROM public.refresh_parity_tier1_outcomes('dixie');)
  after inserting any new tax_deed_outcomes/foreclosure_outcomes row, never hand-write parity_status yourself.
- gh CLI is authenticated (repo, workflow scopes) for git operations.
- Repo root is the current working directory (worktree-isolated), on main. Schema changes MUST go through a
  migration file under supabase/migrations/<date>_shard4_dixie_<purpose>.sql, committed to git, even though you
  apply it live via the Management API SQL endpoint. Simple data backfills (UPDATE/INSERT on existing columns) still
  get a documentation migration file per this campaign's established pattern (see
  supabase/migrations/20260718p_gold_standard_dixie_cd_structural_ceiling_refutation_487365d5.sql for the exact
  house style: narrative comment block with VERIFIED evidence, then the idempotent SQL that mirrors what you ran
  live).

ULTRALOOP audit logging (mandatory): for every letter you claim moved OR claim you verified as
correctly-passing/correctly-blocked/residual, INSERT one row into public.gold_standard_ultraloop_audit: columns
dispatch_id (uuid '${DISPATCH_ID}'), ultraloop_mode ('fallback' -- manual Workflow-tool fan-out, not native
/effort ultracode), county_slug ('dixie'), letter, claim (short text), refuter_evidence (jsonb -- your evidence),
survived (boolean, true only if it held up under adversarial check). POST to
\${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with service-role headers.

Hard rules:
- You own ONLY dixie. Never touch any other county's rows or any other shard's files.
- PropertyOnion is litmus/comparison ONLY -- never write po_* derived values in as verified/independent.
- Fail-loud invariant: if a fix attempt finds zero real data, report it as blocked/residual. NEVER fabricate case
  numbers, parcel IDs, sale amounts, or timestamps to make a metric look better. This campaign has a documented
  history of exactly this failure mode in THIS county (dixie B/F fabrication, purged 2026-07-10, commit visible in
  gold_standard_ultraloop_audit) -- do not repeat it in any form.
- Every claim must be tagged VERIFIED (you ran the query/request and are pasting real output), UNTESTED, or
  INFERRED (say why).
- Before finishing: call pencil_dod_evaluate_county('dixie') and paste the FULL before/after JSON. If a letter did
  not move, say so plainly -- "still blocked, here's why" is a valid, expected, honest outcome for C/D given the
  investigation history above.
- git commit any file you create/modify with a clear, county-scoped message. 'git pull --rebase origin main' before
  pushing (other shards may push concurrently to shared paths). Push directly to main -- no branches, no PRs.
- Do NOT run public.gold_standard_loop() or gold_standard_certify() -- other shards may be mid-session. Do NOT
  modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job.
- Budget yourself: this is ONE bounded pass. If a true fix requires building a brand-new scraper, do NOT build it
  now -- size the gap precisely and report it as scoped-out residual.

Return: { letters_touched: [...], fix_summary, sql_or_endpoints_used: [...], before_json, after_json,
residual_gaps: [...], honesty_notes: [...] }.
`

const TASKS = [
  {
    key: 'cd_recheck',
    prompt: `You are working Gold Standard shard-4, county "dixie", letters C and D, inside the
cli-anything-biddeed repo (already checked out, on main).

${BASELINE}

Your job, in priority order:
1. Fresh-verify 15-2023-CA-57 live: check dixieclerk.com's foreclosure-sales page (and/or the clerk's official
   records search if reachable without a CAPTCHA) for the actual disposition (sold amount, winning bidder/cert
   holder) now that 2026-07-21 has passed. If you find a real, citable outcome: INSERT it into the appropriate
   outcomes table (foreclosure_outcomes for a CA case -- check the table exists and its schema first via
   information_schema.columns; if it doesn't exist yet for foreclosure cases, check how tax_deed_outcomes is
   structured and use the same data_source-tagging convention, independently sourced, never PropertyOnion-derived),
   then run public.refresh_parity_tier1_outcomes('dixie') to let the canonical matcher pick it up. If the site still
   shows the case as unresolved/scheduled, or you cannot reach a real disposition, do NOT fabricate one -- report it
   as still-blocked with the live evidence you found.
2. Only if you have genuine budget left AND can articulate a concretely NEW angle not in the exhausted-list above
   (not "try dixieclerk.com again the same way") -- make ONE honest attempt on the 6 stale DIXIE-SYNTH-* rows
   (12-09-13-4030-0005-0170, 30-13-12-2994-0003-5550, 36-09-13-4502-0000-0330, 36-10-13-5665-0008-0330,
   13-09-13-4051-0000-0490, 12-09-13-4030-0007-0050). If you can't think of a genuinely new angle, skip this
   entirely and say so -- do not force it.
3. Recompute the C/D structural-ceiling math precisely given whatever you found (auctions_total, matched now, true
   achievable max if the remaining rows resolved) and document it clearly, continuing this county's documentation
   pattern.
4. Log gold_standard_ultraloop_audit rows for C and D per the RECIPE.

${RECIPE}`,
  },
  {
    key: 'audit_sweep',
    prompt: `You are working Gold Standard shard-4, county "dixie", auditing the 8 currently-PASSING letters
(A, B, E, F, G, H, I, J) for gold_standard_ultraloop_audit freshness, inside the cli-anything-biddeed repo (already
checked out, on main).

${BASELINE}

CRITICAL CONTEXT (VERIFIED live via a direct query on gold_standard_ultraloop_audit just now, do not re-derive):
per EVALUATOR V6 RULES, gold_standard_certify() requires survived=true audit rows for ALL 10 letters within a
7-DAY freshness window before dixie can certify, even at 10/10. Live rows just now show: C and D have fresh audit
rows from 2026-07-19 (5 days ago -- still just inside the 7-day window but will expire in ~2 days, another session
owns re-freshening those, NOT your job here). Letters A, B, E, F, G, H, I, J have their MOST RECENT audit rows dated
2026-06-27 (27 days ago) -- STALE, outside the 7-day window. This is a real gap blocking certification even though
all 8 letters currently PASS.

Your job: for each of A, B, E, F, G, H, I, J, do a SHORT real adversarial sanity check against live data (not just
re-reading the old audit row) and log ONE fresh gold_standard_ultraloop_audit row per letter with survived=true --
UNLESS your sanity check finds a genuine problem, in which case investigate further and either fix it (small,
surgical, evidence-backed) or log survived=false with the honest reason.

Suggested per-letter checks (adapt as needed, use real queries):
- A: confirm fc=2 td=31 by counting real rows grouped by sale_type for dixie.
- B: confirm verified=12 closed_sold=12 is a real 1:1 count, not a coincidental match masking a scoping bug --
  spot-check 2-3 of the 12 verified outcomes have real data_source values, non-PropertyOnion, non-fabricated
  (this county has a documented B/F fabrication-then-purge history, 2026-07-10 -- confirm the CURRENT 12 are the
  real post-purge rows, not a regression back to fabricated ones).
- E: parcel_linked=32 of 33 -- spot-check a handful of parcel_id values are real Dixie County parcel/STRAP formats,
  not placeholders.
- F: tier1_sold=12 closed_sold=12 -- confirm real sold amounts, not zeros or round-number placeholders.
- G: density=100.0 far=100.0 pk1000=null -- confirm via v_zoning_gold_standard_kpi_v3 / v_zoning_district_applicability
  that the null pk1000 genuinely means "no parking-applicable districts in dixie" (a legitimate N/A), not missing data
  being silently excluded.
- H: confirm last_seen_at is a genuine recent scrape timestamp, not stale/frozen.
- I: card_complete=32 of 33 -- confirm card fields (address, geo, value, zoned parcel) are non-placeholder for a
  couple of sampled rows.
- J: deal_complete=33 -- confirm bid_decisions rows have real arv/max_bid/ml_score and all 5 factor keys
  (distress_location, distress_property, distress_owner, cma_distressed, cma_resale), not zeros/nulls.

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
    `Independently verify this claimed Gold Standard result for dixie, task "${task.key}". You did NOT write this -- be skeptical.\n\n` +
    `Claimed result: ${JSON.stringify(result)}\n\n` +
    `${RECIPE}\n\n` +
    `Your job: re-run pencil_dod_evaluate_county('dixie') yourself RIGHT NOW (fresh call, do not trust the pasted ` +
    `after_json), compare against the claimed before/after, and check specifically for: (a) denominator mismatches, ` +
    `(b) ghost-success (any letter now passing because of a placeholder/fabricated value rather than a real fix -- ` +
    `this county has a documented B/F fabrication history, be extra skeptical here), (c) whether any OTHER letter ` +
    `regressed as a side effect, (d) for B specifically, the only valid pass band is 95-105%%. If gold_standard_` +
    `ultraloop_audit rows were claimed as inserted, spot-check 2-3 of them actually exist with real refuter_evidence. ` +
    `Also INSERT your own gold_standard_ultraloop_audit row per the RECIPE (ultraloop_mode='fallback'). ` +
    `Return { task, refuted: boolean, refutation_reason: string|null, fresh_evaluation: <the JSON you just got>, survives: boolean }.`,
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
