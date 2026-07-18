export const meta = {
  name: 'gold-standard-shard6-run4870',
  description: 'Gold Standard shard-6 (charlotte/union/holmes): diagnose, fix, adversarially verify failing letters per county',
  phases: [
    { title: 'Diagnose+Fix', detail: 'one agent per county, worktree-isolated' },
    { title: 'Verify', detail: 'independent refuter per county claim' },
  ],
}

const DISPATCH_ID = '95f77ed6-fc70-4c15-9db4-b9b64bef5d1c'

const COUNTIES = [
  {
    slug: 'charlotte',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now, matches the brief exactly, no drift):
9/10, only B fails: metric=89.5 (verified=17 closed_sold=19). Everything else PASSES (A=31, C=97.1, D=97.1, E=100,
F=100, G=97.9, H=5.8h, I=98.1, J=100). auctions_total=103. B's pass band is 95-105%%, so you need verified>=19
(18/19=94.7%% still fails -- ALL 19 closed_sold rows must carry an independent outcome).

VERIFIED this session -- the exact closed_sold=19 row set (sold_amount IS NOT NULL AND (data_source<>'propertyonion'
OR tier1_authoritative=true), which is the evaluator's REAL filter, confirmed via pg_get_functiondef): 17 of these 19
already have a foreclosure_outcomes row with data_source NOT ILIKE '%%promote%%' (has_fc_outcome=true) -- these are
fine, do not touch them. The exact 2 gap rows, BOTH propertyonion/tier1_authoritative=true with sold_amount='0.0'
(a suspicious placeholder value, not confirmed real) and NO tax_deed_outcomes/foreclosure_outcomes match at all:
  - case_number 25000552CA, auction_date 2026-06-05
  - case_number 25000869CA, auction_date 2026-06-10

CRITICAL PRIOR-SESSION CONTEXT -- read scripts/shard9_charlotte_b_metric_independent_outcome_backfill.py in full
before doing anything (it already solved 15 of 17 currently-verified rows on 2026-07-11). Its documented RESIDUAL
list included these same 2 cases (plus 5 others now already resolved by later sessions) and it explicitly could NOT
close them because: "RealForeclose.com preview pages returned empty case listings ... and the Charlotte Clerk's
Benchmark court-records portal (courts.charlotteclerk.com/Benchmark) requires JS-driven session interaction not
reachable via curl/WebFetch, and no Firecrawl API key was configured in this session's environment."
THIS HAS CHANGED: FIRECRAWL_API_KEY is now set in this environment (verified) and the firecrawl-browser /
firecrawl-scrape skills are available for JS-driven interaction. This is your real, new lever -- use Firecrawl
(browser automation, not curl) against courts.charlotteclerk.com/Benchmark (case search by case_number) and/or
Charlotte's RealForeclose.com auction-result pages for these 2 specific case numbers and their auction dates, to find
a genuine sale outcome (sold/cancelled/redeemed) and, if sold, the real winning bid amount.
IMPORTANT: the verified_outcomes check only requires an independent tax_deed_outcomes/foreclosure_outcomes row to
EXIST for the case_number (data_source NOT ILIKE '%%promote%%') -- it does NOT require sold_amount to match exactly.
So the minimal honest fix is: if you confirm via Benchmark/RealForeclose that these cases really did result in a
foreclosure sale, insert an independent outcome row (data_source e.g. 'benchmark:charlotte_clerk' or
'realforeclose:charlotte', NOT containing 'promote') with whatever real winning_bid you can verify. If the real
winning bid differs from the current placeholder sold_amount='0.0' on multi_county_auctions, correct that field too
(per Honesty Protocol, a known-wrong placeholder should not be left in place once you have the truth). If, after a
genuine Firecrawl-driven attempt, these 2 cases are still unreachable/unconfirmable, report that honestly as a
residual -- do not fabricate a dollar amount or insert an outcome row without real evidence.`,
  },
  {
    slug: 'union',
    context: `Baseline (VERIFIED live just now, matches brief exactly): 8/10, only B (verified=0 closed_sold=0) and F
(tier1_sold=0 closed_sold=0) fail -- both show metric=null because closed_sold=0. Only 3 total auctions in this
tiny county. All other letters PASS (A=1, C=100, D=100, E=100, G=100, H=1.1h, I=100, J=100).

VERIFIED this session -- full row dump (3 rows, all parity_status='matched_clean' via tier1:union_clerk_live_20260711):
  - 63-2024-CA-0047: auction_status='upcoming', auction_date=2026-10-15 (genuinely future, ~3 months out -- NOT
    closable, do not touch, do not force a status change)
  - 63-2025-CA-0053: auction_status='upcoming', auction_date=2026-08-13 (genuinely future, ~1 month out -- same,
    do not touch)
  - UNION-TD-CERT223: auction_status='unknown_past_due', auction_date=2026-03-12 (over 4 months in the past)

CRITICAL PRIOR-SESSION CONTEXT -- read scripts/shard10_run3645_union_b_cert223.py in full before doing anything. It
already ran an exhaustive live Playwright investigation of CERT223 on 2026-07-10: unionclerk.com/tax-deed-sales/
still lists it as SCHEDULED (stale, not updated); the Lands-Available-for-Taxes page does NOT list it (rules out
"went unsold", but doesn't confirm sold-vs-redeemed or an amount); no results/disposition page exists on the domain;
the OCRS court-records portal (civitekflorida.com) is Person/Case Search only, structurally has no deed/Official
Records index for a Ch.197 tax deed sale (there is no case filed in court for these). Conclusion at the time: no
sold_amount is discoverable from unionclerk.com. It correctly did NOT fabricate a value, and instead just corrected
auction_status from 'upcoming' to 'unknown_past_due' (the only honest write available then).
TWO explicitly-flagged-but-NOT-YET-ATTEMPTED follow-ups from that script's own conclusion, which you should try now
(FIRECRAWL_API_KEY is now available, which that session also lacked -- use firecrawl-browser for JS-driven forms):
  1. http://unioncountytc.com/ (Union County Tax Collector) -- only the homepage was reviewed; a cert-status lookup
     tool, if one exists, was never attempted. Check the nav for a tax-deed-certificate search.
  2. http://union.floridapa.com/ (Property Appraiser GIS, GrizzlyLogic iframe) -- Playwright could not drive the
     nested-iframe #searchInput reliably (30s timeout); Firecrawl's browser automation may handle this better, or
     may not -- a genuine parcel-history / sale-price lookup here (parcel 32-05-20-22-018-0022-0) could substitute
     for a clerk source if it shows a real recorded transfer amount.
  Budget this to ONE more focused attempt each -- do not re-run the exact same unionclerk.com checks the prior
  script already exhausted. If both remain blocked, report CERT223 as a confirmed structural residual (clerk site
  has no disposition data) rather than sinking the whole session into a 3-row county.
  Note: even if CERT223 resolves, closed_sold only becomes 1 (of 3) -- B/F would then be verified=1/closed_sold=1
  (100%%, PASS) or verified=0/closed_sold=1 (0%%, still FAIL) depending on whether you can also source an
  independent outcome row, not just a status correction. A bare status correction alone does not move B or F.`,
  },
  {
    slug: 'holmes',
    context: `Baseline (VERIFIED live just now, matches brief exactly): 6/10, failing B (verified=0 closed_sold=0),
C (matched_clean=8 of 13, 61.5%%), D (matched_any=8 of 13, 61.5%%), F (tier1_sold=0 closed_sold=0). E, G, H, I, J
all PASS (I=100, meaning holmes already has real zoning-card data for all 13 rows).

VERIFIED this session -- full 13-row dump: 8 rows carry parity_status='matched_clean' with parity_source
'tier1:holmes_clerk_live_20260710' or 'tier1:holmes_clerk_live_gsc_shard12_run3534' (real, working parity). The
exact 5 unmatched rows (parity_status/parity_source both NULL): TD#2020-589, TD#2023-185, TD#2023-225, TD#2023-496,
TD#2023-584 -- ALL still auction_status='upcoming'. Separately, there is exactly ONE row with auction_status=
'completed' (case HOLMES-LEGACY-123a1bd5-...), sold_amount NULL, data_source NULL, parity_status='matched_clean' --
this is the only row that could ever contribute to closed_sold; all other 12 rows are 'upcoming' and structurally
cannot be closed_sold yet.

CRITICAL PRIOR-SESSION CONTEXT -- read scripts/shard12_run3534_holmes_clerk_cd_bf_harvest.py in full (2026-07-10,
run3534) AND note that a LATER session (shard9, dispatch ddbb047c, also 2026-07-10) re-diagnosed holmes with the
IDENTICAL 5 unmatched TD# cases and recommended re-checking why they didn't match -- meaning this gap has now
persisted UNRESOLVED across at least 2 prior sessions and 8+ days (today is 2026-07-18). The shard12 script's own
finding: holmesclerk.com's foreclosure/tax-deed pages are a forward-looking notice board with NO results/disposition
field; it explicitly observed these 5 TD# cases had "rolled off" the live tax-deed page between its scrapes (no
longer listed as upcoming), which "strongly suggests they already sold" but the site has no way to confirm that,
and its Lands-Available-for-Taxes page was explicitly empty (rules out "went unsold"). C/D matching there is a plain
case_number exact-match against whatever the live page currently shows -- if a case rolled OFF the page, the
matcher correctly stops matching it; this is not a matcher bug, it may be a genuine source-coverage gap.
YOUR JOB, in priority order (C/D gap is the single highest-leverage fix in this shard -- 5 cases takes holmes from
61.5%% to 100%%):
1. Re-scrape holmesclerk.com's foreclosure/tax-deed pages FRESH right now (do not trust the 8-day-old scrape) --
   if the 5 TD# cases are still genuinely absent, that alone doesn't resolve C/D (matched_clean requires a live
   tier1 source confirmation, not an absence). FIRECRAWL_API_KEY is now available (the prior sessions did not
   document trying Firecrawl specifically) -- use it to check for pages the plain-requests scraper in shard12's
   script might have missed: look for an "Official Records Search" / recording index on holmesclerk.com (many rural
   FL clerks expose a Landmark Web / iDoc Official Records search even when their foreclosure/tax-deed notice pages
   are disposition-free) -- if a Certificate of Title or Tax Deed got RECORDED for these 5 cases, that recording
   would carry a real date/grantee and could serve as an honest 'matched_clean' tier1 confirmation and, if it states
   a consideration amount, a real B/F sold_amount too. Also try the Holmes County Property Appraiser and Tax
   Collector sites for a per-parcel sale-history / cert-status lookup as an alternate independent source.
2. If a real Official-Records or Property-Appraiser source confirms any of the 5 cases sold (or redeemed/cancelled),
   write parity_status='matched_clean' with a parity_source starting with 'tier1' (required for C/D credit per the
   evaluator's exact filter: parity_source LIKE 'tier1%%') reflecting the NEW source, e.g.
   'tier1:holmes_official_records_<date>'. Do this only for cases you can actually confirm live -- do not mark all
   5 matched on the strength of one confirmed case.
3. For the single 'completed' row (HOLMES-LEGACY-123a1bd5), the same new source (if found) may also yield a real
   sold_amount -- if so, write it plus an independent tax_deed_outcomes/foreclosure_outcomes row
   (data_source NOT ILIKE '%%promote%%') to move B and F together. Do NOT fabricate a dollar figure if no source
   states one.
4. If, after a genuinely new attempt (not a re-run of the already-exhausted holmesclerk.com notice-board checks),
   nothing new is found, report B/C/D/F precisely as a persistent structural residual with the exact evidence of
   what you tried that the prior 2 sessions had not -- this is more valuable than a 3rd identical "still blocked"
   writeup with no new avenue attempted.`,
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
  Build this JSON with a real JSON encoder (python3 -c "import json; ..." writing to a temp file, then
  curl --data-binary @file) rather than hand-quoting shell strings.
- pencil_dod_evaluate_county RPC: POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county
  headers apikey/Authorization as above, body {"p_county": "<slug>"} -- this is your before/after proof. The live
  function definition (already pulled this session via pg_get_functiondef, ground truth, do not re-derive) computes
  every letter from multi_county_auctions filtered to lower(county)=<slug> AND (data_source <> 'propertyonion' OR
  tier1_authoritative=true). B = verified_outcomes / closed_sold where closed_sold = count(sold_amount IS NOT NULL)
  under that same filter, and verified_outcomes additionally requires an independent (data_source NOT ILIKE
  '%%promote%%') tax_deed_outcomes OR foreclosure_outcomes row matching case_number+county. F = tier1_sold (both
  tier1_sold_amount and sold_amount NOT NULL) / closed_sold. C/D require parity_source LIKE 'tier1%%' in addition to
  parity_status -- setting parity_status alone does NOT satisfy C/D.
- FIRECRAWL_API_KEY is SET in this environment -- this is a genuinely new capability vs several prior sessions on
  these same counties that were explicitly blocked for lacking it (see per-county context). Use the firecrawl-scrape
  / firecrawl-browser skills (or direct Firecrawl API calls) for any JS-rendered or form-driven page.
- gh CLI is authenticated (repo, workflow scopes) for git operations.
- Repo root is the current working directory, on main. Schema changes MUST go through a migration file under
  supabase/migrations/<date>_shard6_<county>_<purpose>.sql, committed to git. Simple data backfills (UPDATE/PATCH
  on existing columns, no schema change, e.g. inserting an outcome row or setting parity_status) do not need a
  migration file -- just do the REST PATCH/POST or a direct UPDATE via the Management API and note the exact
  SQL/endpoint used.

ULTRALOOP audit logging (mandatory per campaign protocol): for every letter you claim moved (or claim you verified
as correctly-blocked/residual), INSERT one row into public.gold_standard_ultraloop_audit: columns dispatch_id
(uuid '${DISPATCH_ID}'), ultraloop_mode ('fallback' -- this session used Workflow-tool agent fan-out, not native
/effort ultracode), county_slug, letter, claim (short text), refuter_evidence (jsonb -- for the FIX agent, your own
before/after evidence; for the VERIFY agent, your refutation attempt and findings), survived (boolean, true only if
the claim held up under adversarial check). POST to \${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with the
service-role headers above.

Hard rules (from the campaign brief -- follow exactly):
- You own ONLY your assigned county. Never touch another shard's counties or rows.
- PropertyOnion is litmus/comparison ONLY -- never write po_*-derived values in as if verified/independent.
- Fail-loud invariant: if a fix attempt finds zero real data, report it as a blocked/residual gap. NEVER fabricate
  case numbers, parcel IDs, sale amounts, or timestamps to make a metric look better. This campaign has a documented
  history of exactly this failure mode (gulf B/F fabrication, purged) -- do not repeat it, including "close enough"
  placeholder values. The charlotte and holmes contexts above both flag existing sold_amount='0.0'/NULL placeholders
  -- do not paper over these with guesses; only replace them with values you can cite a real source for.
- Every claim you return must be tagged VERIFIED (you ran the query/request and are pasting real output), UNTESTED,
  or INFERRED (say why).
- Before finishing: call pencil_dod_evaluate_county for your county and paste the FULL before (already given above,
  or re-verify fresh if you suspect drift) and after JSON. If a letter did not move, say so plainly.
- git commit any file you create/modify with a clear message, county-scoped, and 'git pull --rebase origin main'
  before pushing (other shards may push concurrently to shared paths -- you are isolated in a worktree so conflicts
  should be rare, but rebase defensively anyway). Push directly to main -- no branches, no PRs.
- Do NOT run public.gold_standard_loop() or gold_standard_certify() -- other shards may be mid-session. Do NOT
  modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job.
- Budget yourself: this is ONE bounded pass per county, not a 6-hour campaign. If a true fix requires building a
  brand-new scraper from scratch, do NOT build it in this pass -- size the gap precisely, report it as a scoped-out
  residual, and ship whatever smaller, real, verifiable improvement IS achievable now.

Return a structured report: { county, letters_touched: [...], fix_summary, sql_or_endpoints_used: [...],
before_json, after_json, residual_gaps: [...], honesty_notes: [...] }.
`

phase('Diagnose+Fix')
const fixResults = await pipeline(
  COUNTIES,
  (county) => agent(
    `You are working Gold Standard shard-6, county "${county.slug}", inside the cli-anything-biddeed repo (already checked out, on main).\n\n${county.context}\n\n${RECIPE}`,
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
    `Independently verify this claimed Gold Standard fix for county "${county.slug}". You did NOT write this fix -- be skeptical.\n\n` +
    `Claimed result: ${JSON.stringify(result)}\n\n` +
    `${RECIPE}\n\n` +
    `Your job: re-run pencil_dod_evaluate_county for "${county.slug}" yourself RIGHT NOW (fresh call, do not trust the pasted after_json), ` +
    `compare against the claimed before/after, and check specifically for: (a) denominator mismatches (does the ` +
    `"auctions_total" / "closed_sold" count match what you independently query?), (b) ghost-success (any letter now ` +
    `passing because of a placeholder/fabricated/vacuous value rather than a real fix -- this campaign has a ` +
    `documented history of exactly this failure mode, e.g. G passing 100%% on zero applicable parcels, or sold_amount ` +
    `left at a suspicious '0.0' placeholder), (c) whether any OTHER letter for this county regressed as a side ` +
    `effect, (d) for B specifically, the only valid pass band is 95-105%% -- an anomalous ratio outside that (even ` +
    `if the raw pass/fail bit says true) should be flagged, (e) if a claimed fix relied on a new outcome/parity row, ` +
    `spot-check that its cited source (URL/page) actually says what the fix claims it says. Also INSERT your own ` +
    `gold_standard_ultraloop_audit row per the RECIPE instructions (ultraloop_mode='fallback'). ` +
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
