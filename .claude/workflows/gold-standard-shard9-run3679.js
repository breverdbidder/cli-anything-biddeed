export const meta = {
  name: 'gold-standard-shard9-run3679',
  description: 'Gold Standard shard-9 (charlotte/palm_beach/holmes/sumter): diagnose, fix, adversarially verify failing letters per county',
  phases: [
    { title: 'Diagnose+Fix', detail: 'one agent per county, worktree-isolated' },
    { title: 'Verify', detail: 'independent refuter per county claim' },
  ],
}

const DISPATCH_ID = 'ddbb047c-3aca-44b8-821a-58a26d127732'

const COUNTIES = [
  {
    slug: 'charlotte',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now, supersedes the stale brief numbers):
9/10, only B fails: metric=50.0 (verified=2 closed_sold=4). All other letters PASS (C=97.1, D=97.1, E=100, F=100,
G=97.9, H=8.2h, I=98.1, J=100). auctions_total=103, parity_status breakdown: matched_clean=100, null=3 (those 3 are
fine, don't chase C/D — they already pass at 97.1% >= 95%).

VERIFIED this session: SELECT id,case_number,auction_status,sold_amount,data_source FROM multi_county_auctions
WHERE county='charlotte' AND auction_status IN ('closed','sold') returns 20 rows with auction_status='sold' but
data_source='realtaxdeed' for ALL of them, and sold_amount IS NULL for every single one — yet the evaluator's
"closed_sold" denominator (count WHERE sold_amount IS NOT NULL) = 4, not 20. That means only 4 of these 20
'sold'-status rows already have sold_amount populated elsewhere (check which 4), and of THOSE 4, only 2 have an
INDEPENDENT verified outcome row in tax_deed_outcomes/foreclosure_outcomes (case_number match, data_source NOT
ILIKE '%promote%'). Two things to do: (1) find the exact 2 closed_sold rows lacking an independent outcome and
either locate a real clerk-published sale-result source for them (Charlotte County Clerk tax deed sale results /
official records), or determine it's genuinely unverifiable and report it as a residual gap — do NOT fabricate.
(2) separately worth a quick check: those other 16 'sold'-status/realtaxdeed rows with sold_amount NULL — are they
real completed sales missing a dollar figure (an F/tier1 opportunity, though F already passes at 100% today so
be careful not to change the closed_sold denominator in a way that could regress F), or misclassified? Investigate
before touching anything; if a real sold_amount can be sourced live from the Charlotte Clerk site for any of them,
backfilling it changes the closed_sold denominator too, so re-run the evaluator after any such write to confirm B
and F both still make sense (do not let a partial backfill drop F below 95%).
Existing scripts to check first (avoid duplicating): scripts/shard8_charlotte_litmus_run.py,
scripts/shard7_charlotte_fixes.py, scripts/shard24_charlotte_freshness_fix.py,
scripts/shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py — none of these appear to target B/independent-outcome
sourcing specifically per their names, confirm by reading before assuming coverage.`,
  },
  {
    slug: 'palm_beach',
    context: `Baseline (VERIFIED live just now — the brief's numbers are STALE, denominator has grown from 636 to 688
auctions as ingestion continues): 8/10, failing C (metric=69.0, matched_clean=475 of 688) and D (metric=69.5,
matched_any=478 of 688). Everything else PASSES: A=116, B=100.0 (verified=193 closed_sold=193 — do NOT touch B,
it is correct, and per EVALUATOR V6 RULES a B in the 95-105% band is the only valid pass band, this one is exactly
100.0 so leave it alone), E=100, F=100, G=100, H=0.1h, I=97.4, J=99.0.

CRITICAL PRIOR-SESSION CONTEXT (read supabase/migrations/20260710_shard5_palm_beach_tier1_only_promotion_fix.sql
and supabase/migrations/20260710_shard7_palm_beach_parity_null_source_bugfix.sql in full before doing ANYTHING —
both landed TODAY, 2026-07-10, immediately before this dispatch): two real matcher bugs in
public.refresh_palm_beach_parity_v2() (a NULL-trap in the WHERE clause, and a stale-row guard that permanently
skipped already-touched rows) were found and fixed this cycle, moving C from 465->475 and D from 468->478. The
fix migration's own conclusion, which you should VERIFY FRESH rather than trust: "the residual gap is a genuine
data ceiling (upcoming auctions with no real counterpart yet), not a matcher bug."

VERIFIED this session (fresh breakdown by parity_status x auction_status, non-PO rows only, sums to 688):
matched_clean/completed=178, matched_clean/cancelled=161, matched_clean/redeemed=78, matched_clean/upcoming=58,
mca_only/upcoming=45, null/upcoming=164, matched_divergent/cancelled=2, matched_divergent/upcoming=1,
tier1_only/upcoming=1. Every single unmatched or partially-matched row (mca_only + null + tier1_only = 210 rows)
has auction_status='upcoming' — ZERO closed/cancelled/redeemed/completed rows are unmatched. This is consistent
with the prior session's ceiling theory but does NOT prove it — a genuine ceiling means RealAuction simply hasn't
listed these future sale dates yet (their site typically surfaces auctions ~30-60 days out), which would be a real,
unfixable-today data-maturation gap, not a bug. Your job: pick a sample of the 164 'null' upcoming rows (case_number
+ auction_date), and LIVE-CHECK them against the actual palm_beach RealAuction site (or whatever tier1 source
refresh_palm_beach_parity_v2 queries — check public.realforeclose_aids and public.palm_beach_realtdm_raw table
freshness/coverage for those specific auction dates) to determine: (a) genuinely not listed yet (far-future date) —
confirms the ceiling, report as residual with the evidence, OR (b) IS listed on the tier1 source but our matcher
missed it (case_number format mismatch, parcel_id mismatch, a source table that hasn't been refreshed recently
enough) — if you find real matcher/wiring gaps, fix them. Also check cron/GHA scheduling for
refresh_palm_beach_parity_v2 (search for cron job 4103 mentioned in the migration comments, and for a scraper that
populates realforeclose_aids / palm_beach_realtdm_raw) — confirm it's actually running on schedule and not stale.
The V2_LITMUS snapshot in the evaluator output shows source_count=35, our_count=13, match_pct=37.1 for the
'realauction' primary source — this is a SEPARATE informational-only litmus surface (explicitly documented as
zero-effect on A-J), but its low count vs 688 total auctions may be a useful clue about how far out RealAuction's
own listing window really goes; treat it as a hint, not proof, and verify independently.
Do not re-derive the matcher bug fixes already shipped — read them first.`,
  },
  {
    slug: 'holmes',
    context: `Baseline (VERIFIED live just now): 6/10, failing B (metric=null, verified=0 closed_sold=0), C (metric=61.5,
matched_clean=8 of 13), D (metric=61.5, matched_any=8 of 13), F (metric=null, tier1_sold=0 closed_sold=0). E, G, H,
I, J all PASS (I=100, meaning holmes DOES have real zoning-card data already — v_zoning_gold_standard_card has 13
matching rows for holmes, confirmed live).

VERIFIED this session: ALL 13 holmes rows have auction_status IN ('completed','upcoming') — there is exactly ONE
'completed' row (case HOLMES-LEGACY-123a1bd5-...) and 12 'upcoming'. sold_amount IS NULL for all 13 rows — this is
why closed_sold=0 and B/F both show null-metric FAIL (the evaluator can't compute a percentage with 0 in the
denominator, and COALESCE(...,false) makes that a FAIL rather than N/A). If the one 'completed' case genuinely
already sold, find its real sale amount from the Holmes County Clerk (holmesclerk site, or the same
'holmes_clerk_live' source already feeding C/D matches below) and an INDEPENDENT verified-outcome row
(tax_deed_outcomes/foreclosure_outcomes, data_source NOT ILIKE '%promote%') — that would flip both closed_sold to 1
and, if amount matches, B and F could move. If it hasn't actually sold yet (check status precisely, "completed"
auction_status may not mean "sold" in this scraper's vocabulary), report that honestly and do not force a write.

C/D: 8 of 13 rows already carry parity_status='matched_clean', parity_source='tier1:holmes_clerk_live_20260710'
(today's date — an active, working scraper). The 5 unmatched rows (parity_status/parity_source both NULL) are:
TD#2023-185 (parcel 0607.00-000-000-005.000), TD#2020-589 (1327.04-001-002-096.000), TD#2023-496
(1316.00-000-000-022.000), TD#2023-225 (0811.04-001-000-041.000), TD#2023-584 (1327.04-000-000-002.000). Find the
script/function behind the 'tier1:holmes_clerk_live_*' parity_source (search for 'holmes_clerk_live' across
scripts/ and supabase/migrations/, likely scripts/shard12_run3534_holmes_clerk_cd_bf_harvest.py) and determine
why these 5 specific TD# cases didn't match on the last run — genuinely absent from the Holmes Clerk's current
listing (report as residual), or a matching-key issue (TD# formatting, case number normalization) you can fix.
Getting even 5 more matched_clean would take C/D from 61.5% to 100% (13 of 13) — this is the highest-leverage
single fix available in this shard, prioritize it.
Check whether scripts/shard12_run3534_holmes_clerk_cd_bf_harvest.py is wired to a cron/GHA schedule; if not, that
alone may explain staleness and is a real wiring-gap fix per the campaign's WIRING MANDATE.`,
  },
  {
    slug: 'sumter',
    context: `Baseline (VERIFIED live just now): only 11 total auctions (small county, tractable). 4/10 passing:
A=4, G=100(vacuous — v_zoning_gold_standard_card has only 4 rows for sumter, treat G's 100% pass as unreliable,
do not rely on it, but it is not in your fail list so no action needed unless it blocks I), H=7.2h, J=100. Failing:
B (metric=null, verified=0 closed_sold=0), C (metric=0.0, matched_clean=0 of 11), D (metric=0.0, matched_any=0 of
11), E (metric=90.9, parcel_linked=10 of 11), F (metric=null, tier1_sold=0 closed_sold=0), I (metric=null/0,
card_complete=0 of 11).

VERIFIED this session, full row dump (11 rows): 1 cancelled foreclosure (2025-CA-000255, no parcel_id, no address)
— this is the one E-unlinked row; 4 upcoming tax-deed (TD-5054/5056/5057/5058, all have parcel_id like G05R062,
NO property_address/lat/lon for any); 3 closed tax-deed (TD-5028/5031/5036, parcel_id present, no address/geo,
sold_amount NULL); 1 cancelled foreclosure with address (2023-CA-000091, "2621 CARIBE DR", no lat/lon);
2 closed foreclosure WITH address (2024-CA-000367 "3288 SHELBY STREET", 2024-CA-000364 "4266 CR 691", both no
lat/lon, sold_amount NULL for both). NONE of the 11 rows have latitude/longitude or assessed_value/market_value —
that alone is why I=0 (card requires address AND lat/lon AND value AND parcel-zone-linked, all four).

HARD-BLOCKED, DO NOT RE-ATTEMPT (already exhaustively investigated by scripts/shard10_run3645_sumter_bf_outcomes.py
— read its full docstring first, it is unusually detailed): TD-5028/5031/5036 sold-amount is UNVERIFIABLE without
fabrication — Sumter Clerk's site has no per-case sale-result page, only a "surplus funds" list proving a sale
occurred (not the winning bid $), and the official records / OCRS case search is Cloudflare-Turnstile-gated and
could not be automated. The 3 tax_deed_outcomes rows for these already exist with winning_bid=NULL by design (see
the script). Do not write a fabricated sold_amount for these three. 2024-CA-000364/2024-CA-000367: only a
PRE-sale final-judgment PDF was found (not a sale result); post-sale outcome unverified as of that prior session —
you MAY attempt ONE more live check (e.g. Sumter Clerk case docket page for these two case numbers directly, which
is a different page than what was tried before) but do not sink the whole session into this; if still blocked,
say so and move on.

REAL, ACHIEVABLE WORK for this session — prioritize in this order:
1. I (biggest available win): geocode/enrich the 8 rows that have a parcel_id (TD-5054/56/57/58, TD-5028/31/36,
   plus the 3 with addresses) via the Sumter County Property Appraiser (search for their ArcGIS FeatureServer or
   public GIS parcel search — Sumter's parcel_id format here, e.g. "G03A014", "D20G135", looks like Sumter's own
   folio/PIN scheme) to get real property_address (for the ones missing it), latitude/longitude, and
   assessed_value/market_value. This is a real live-data enrichment, same pattern as the BCPAO/Brevard reference
   pipeline. card_complete also requires the parcel linked into v_zoning_gold_standard_card (only 4 sumter rows
   there today) — check whether that's the actual blocker for the rows that DO get address+geo+value, and if so
   scope that as a residual (small G/zoning-ingestion gap for sumter, out of scope for a single session per the
   RECIPE budget rule) rather than trying to build a full zoning ingestion pipeline from scratch.
2. E: the 1 unlinked row (2025-CA-000255, cancelled) — find its real parcel_id via the Sumter Property Appraiser
   if the case has an associated property; if genuinely no parcel exists for a cancelled case with no address on
   record anywhere, report as residual rather than fabricating.
3. C/D: currently 0% — check whether ANY parity/litmus pipeline has ever run for sumter (parity_status is NULL
   for all 11 rows, no exceptions). Check scripts/shard1_run3534_sumter_td_case_backfill.py and search for a
   sumter-specific tier1 source table (pattern: sumterclerk_*, similar to holmes_clerk_live or the palm_beach
   realforeclose_aids tables). If no tier1 comparison source exists at all for sumter, this is a genuine build gap
   — per the RECIPE budget rule, do NOT build a brand-new scraper from scratch in this pass; instead check if the
   sumterclerk.com pages already fetched by shard10_run3645_sumter_bf_outcomes.py (tax-deed sale pages, foreclosure
   PDF) could cheaply double as a matching source for parity_status (i.e., if the auction already appears in a
   page we've fetched with confirmable status, that alone may satisfy a 'matched_clean' definition — check the
   exact SQL definition of matched_clean, which requires parity_source LIKE 'tier1%', so any UPDATE you write MUST
   use a source string starting with 'tier1' and must represent a REAL, verifiable comparison, not just "we scraped
   it once"). If a real, honest way to populate this is not achievable within budget, size the gap precisely and
   report it as residual — do not force a partial/misleading match.`,
  },
]

const RECIPE = `
Environment (already available, do not ask for credentials):
- REST API reads/writes: GET/PATCH \${SUPABASE_URL}/rest/v1/<table>?... with headers
  apikey: $SUPABASE_SERVICE_ROLE_KEY, Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY
- Live arbitrary SQL (verified working this session): POST
  https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query
  headers Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json
  body {"query": "<sql>"} -- run "SET statement_timeout = 0;" first in the same query string for anything heavy.
  IMPORTANT: build this JSON with a real JSON encoder (e.g. python3 -c "import json; ..." writing to a temp file,
  then curl --data-binary @file) rather than hand-quoting shell strings — nested single/double quotes in SQL break
  naive shell quoting and can silently produce an empty/wrong query.
- pencil_dod_evaluate_county RPC: POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county
  headers apikey/Authorization as above, body {"p_county": "<slug>"} -- this is your before/after proof. The
  live function definition (verified this session via pg_get_functiondef) computes every letter from
  multi_county_auctions filtered to lower(county)=<slug> AND (data_source <> 'propertyonion' OR
  tier1_authoritative=true) -- i.e. PropertyOnion-sourced rows are excluded from the denominator entirely unless
  explicitly marked tier1_authoritative. C/D specifically require parity_source LIKE 'tier1%%' in addition to
  parity_status -- setting parity_status alone does NOT satisfy C/D.
- gh CLI is authenticated (repo, workflow scopes) for git operations and workflow dispatch if needed.
- Repo root is the current working directory. Schema changes MUST go through a migration file under
  supabase/migrations/<date>_shard9_<county>_<purpose>.sql, committed to git — even though you CAN run SQL
  directly via the Management API, still write the migration file for the historical record and apply it the
  same way. Simple data backfills (UPDATE/PATCH on existing columns, no schema change) do not need a migration
  file — just do the REST PATCH or a direct UPDATE via the Management API and note the exact SQL/endpoint used.

ULTRALOOP audit logging (mandatory per campaign protocol): for every letter you claim moved (or claim you
verified as correctly-blocked/residual), INSERT one row into public.gold_standard_ultraloop_audit:
  columns: dispatch_id (uuid '${DISPATCH_ID}'), ultraloop_mode ('fallback' -- this session used manual Task
  subagent fan-out, not native /effort ultracode), county_slug, letter, claim (short text of what you claim),
  refuter_evidence (jsonb -- for the FIX agent, put your own before/after evidence; for the VERIFY agent, put your
  refutation attempt and what you found), survived (boolean -- true only if the claim held up under adversarial
  check). Use the REST endpoint: POST \${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with the service-role
  headers above. Do this as part of your normal work, not as an afterthought.

Hard rules (from the campaign brief — follow exactly):
- You own ONLY your assigned county. Never touch another shard-9 county's rows, or any other shard's counties.
- PropertyOnion is litmus/comparison ONLY — never write po_* derived values in as if they were verified/independent.
- Fail-loud invariant: if a fix attempt finds zero real data, report it as a blocked/residual gap. NEVER fabricate
  case numbers, parcel IDs, sale amounts, coordinates, or timestamps to make a metric look better. This project has
  a documented history of exactly this failure mode (gulf B/F fabrication, purged) — do not repeat it in any form,
  including "close enough" placeholder values.
- Every claim you return must be tagged VERIFIED (you ran the query/request and are pasting real output), UNTESTED,
  or INFERRED (say why).
- Before finishing: call pencil_dod_evaluate_county for your county and paste the FULL before (already given
  above, or re-verify fresh if you suspect drift) and after JSON. If a letter did not move, say so plainly.
- git commit any file you create/modify with a clear message, county-scoped, and 'git pull --rebase origin main'
  before pushing (other shards may be pushing concurrently to shared paths — you are isolated in a worktree so
  conflicts should be rare, but rebase defensively anyway). Push directly to main — no branches, no PRs.
- Do NOT run public.gold_standard_loop() or gold_standard_certify() — other shards may be mid-session. Do NOT
  modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job.
- Budget yourself: this is ONE bounded pass, not a 6-hour campaign. If the true fix requires building a brand-new
  scraper from scratch, do NOT build it in this pass — size the gap precisely, report it as a scoped-out residual
  with what a future session needs to do, and ship whatever smaller, real, verifiable improvement IS achievable
  via SQL/REST/live lookups alone (data backfill, wiring an existing-but-unrun pipeline, honesty corrections).

Return a structured report: { county, letters_touched: [...], fix_summary, sql_or_endpoints_used: [...],
before_json, after_json, residual_gaps: [...], honesty_notes: [...] }.
`

phase('Diagnose+Fix')
const fixResults = await pipeline(
  COUNTIES,
  (county) => agent(
    `You are working Gold Standard shard-9, county "${county.slug}", inside the cli-anything-biddeed repo (already checked out, on main).\n\n${county.context}\n\n${RECIPE}`,
    {
      label: `fix:${county.slug}`,
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
)

phase('Verify')
const verified = await pipeline(
  fixResults.filter(Boolean),
  (result, county) => agent(
    `Independently verify this claimed Gold Standard fix for county "${county.slug}". You did NOT write this fix — be skeptical.\n\n` +
    `Claimed result: ${JSON.stringify(result)}\n\n` +
    `${RECIPE}\n\n` +
    `Your job: re-run pencil_dod_evaluate_county for "${county.slug}" yourself RIGHT NOW (fresh call, do not trust the pasted after_json), ` +
    `compare against the claimed before/after, and check specifically for: (a) denominator mismatches (does the ` +
    `"auctions_total" / "closed_sold" count match what you independently query?), (b) ghost-success (any letter now ` +
    `passing because of a placeholder/fabricated/vacuous value rather than a real fix — this campaign has a ` +
    `documented history of exactly this failure mode, e.g. G passing 100% on zero applicable parcels), (c) whether ` +
    `any OTHER letter for this county regressed as a side effect, (d) for B specifically, the only valid pass band ` +
    `is 95-105%% -- an anomalous ratio outside that (even if the raw pass/fail bit says true) should be flagged. ` +
    `Also INSERT your own gold_standard_ultraloop_audit row per the RECIPE instructions (ultraloop_mode='fallback'). ` +
    `Return { county, refuted: boolean, refutation_reason: string|null, fresh_evaluation: <the JSON you just got>, survives: boolean }.`,
    {
      label: `verify:${county.slug}`,
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
  )
)

return { fixResults, verified }
