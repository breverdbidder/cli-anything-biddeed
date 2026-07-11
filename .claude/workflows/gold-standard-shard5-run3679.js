export const meta = {
  name: 'gold-standard-shard5-run3679',
  description: 'Gold Standard shard-5 (manatee/flagler/orange/hamilton): diagnose, fix, adversarially verify failing letters per county',
  phases: [
    { title: 'Diagnose+Fix', detail: 'one agent per county, worktree-isolated' },
    { title: 'Verify', detail: 'independent refuter per county claim' },
  ],
}

const DISPATCH_ID = 'f2a233c6-485e-4148-a691-ec249292470c'

const COUNTIES = [
  {
    slug: 'manatee',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now, supersedes the stale brief numbers):
10/10 -- ALL LETTERS PASS. A=3(min fc/td), B=100.0(verified=5 closed_sold=5), C=96.4(matched_clean=81 of 84),
D=96.4(matched_any=81 of 84), E=96.4(parcel_linked=81 of 84), F=100.0(tier1_sold=5 closed_sold=5),
G=96.3(density=96.3 far=100.0), H=4.3h, I=96.4(card_complete=81 of 84), J=100.0(deal_complete=84 of 84).
auctions_total=84 (grew from 72 in the stale brief -- ingestion is ongoing, all margins held).

YOUR JOB IS NOT TO "FIX" ANYTHING -- there is nothing failing. Per EVALUATOR V6 RULES, gold_standard_certify()
now requires survived=true rows in gold_standard_ultraloop_audit for ALL 10 letters within a 7-day freshness
window before a county can certify, even if the scoreboard shows 10/10. Manatee is very likely sitting on stale or
missing audit coverage for several letters (prior sessions moved letters without always logging the audit row).
Your job: (1) re-verify each of the 10 letters fresh against pencil_dod_evaluate_county output (paste the literal
JSON), (2) for each letter, do a SHORT adversarial sanity check in the same spirit as the refuter pass (does the
denominator make sense? B is in the 95-105%% valid band at exactly 100.0 -- good, don't touch it; check G isn't a
zero-applicable-parcels ghost-pass by confirming v_zoning_gold_standard_kpi_v3 has a nonzero denominator for
manatee; check I's card_complete fields are real non-null values, not placeholders), (3) INSERT one
gold_standard_ultraloop_audit row per letter (10 rows total) with survived=true and real refuter_evidence for each,
UNLESS you find a genuine problem -- in which case fix it for real (small, surgical, evidence-backed) before
logging, or log survived=false with the honest reason if it can't be fixed this pass. Do not spend more than a
fraction of a normal session's budget here; this county is in maintenance mode, not build mode. If you find real
issues, fix them; otherwise your main deliverable is a complete, fresh, honest audit trail that unblocks
certification the next time the daily loop runs 10/10 twice in a row.`,
  },
  {
    slug: 'flagler',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now): 8/10. Only B and F fail, both with
metric=null because closed_sold=0 -- ZERO of flagler's 137 auctions (23 'sold' status + 7 'completed' status rows)
have sold_amount populated at all. All other letters PASS: A=40(fc=40 td=97), C=97.8(134 of 137), D=97.8,
E=99.3(136 of 137), G=100.0, H=8.9h, I=95.6(131 of 137), J=100.0(137 of 137).

CRITICAL PRIOR-SESSION CONTEXT -- read scripts/shard6_run3645_flagler_sold_amount_source_probe.py in full AND its
docs commit befbb731 ("docs(gold-standard-flagler): document B/F sold_amount source investigation") before doing
ANYTHING. That session, TODAY, exhaustively probed FOUR public no-login sold_amount sources for flagler and
confirmed all four are dead ends: (1) realtdm case-detail page has no amount field for sold cases, (2)
realtaxdeed FNC=UPDATE returns empty for closed dates, (3) qpublic.schneidercorp.com parcel pages are WAF-blocked
(403, "needs Firecrawl to bypass"), (4) records.flaglerclerk.gov (landmarkweb official records) is gated behind a
reCAPTCHA v3 ShowCaptcha check on the actual search POST. Run that script fresh first thing
(python3 scripts/shard6_run3645_flagler_sold_amount_source_probe.py) -- it prints CONFIRMED/CHANGED per source; if
any source's status has genuinely changed since this morning, that is your opening. FIRECRAWL_API_KEY was checked
in this session's environment and is ABSENT (empty) -- so the WAF-bypass path flagged as the one live option is
NOT available to you this session either; do not assume it is and do not silently skip that fact, report it.

If all four sources reconfirm as dead ends and no new one turns up (check: does Flagler use RealAuction/RealTaxDeed
for tax deeds per pipeline.counties, and if so does its authenticated results page expose winning-bid amounts the
way other counties' does per playbook F -- this is a genuinely different angle than the four already-probed public
sources and hasn't been ruled out; also check for a Flagler tax collector "surplus funds" or "excess proceeds" page,
which other counties have used as an independent sold-amount proxy), then B/F remain a genuine residual for
flagler -- do NOT fabricate a sold_amount or backdate a promoted value to fake INDEPENDENT provenance. Spend the
rest of your budget on: confirming the other 8 passing letters are real (not ghost-passes) and logging
gold_standard_ultraloop_audit rows for all 10 letters (survived=false with honest reason for B/F if still blocked,
survived=true with fresh evidence for the 8 that pass).`,
  },
  {
    slug: 'orange',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now, denominator has grown from 832 in
the stale brief to 855 -- ingestion is ongoing): 7/10. Failing: C=77.1(matched_clean=659 of 855),
D=77.1(matched_any=659 of 855), I=93.1(card_complete=796 of 855, just under the 95%% bar). Passing: A=321(fc=534
td=321), B=100.0(verified=207 closed_sold=207 -- ALREADY IMPROVED from the stale brief's 86.0%%, do not touch it,
it is in the valid 95-105%% band exactly at 100.0), E=99.1(847 of 855), F=100.0(207 of 207), G=100.0, H=9.8h,
J=100.0(855 of 855). V2_LITMUS shows role=primary source=realauction match_pct=52.3 our_count=23 source_count=44 --
a separate side-metric, not the C/D pass/fail input, but corroborating evidence Orange's tier1 comparison source
is RealAuction.

VERIFIED this session -- exact root cause of the C/D gap: ALL 196 unmatched rows (176 with parity_status=NULL +
20 with parity_status='mca_only') have auction_status='upcoming'. ZERO closed/cancelled/redeemed/completed rows
are unmatched (matched_clean breakdown: cancelled=283, completed=206, redeemed=170, sums to 659). This is the exact
same signature documented in a prior shard's palm_beach investigation. The reason is structural, not a data gap:
public.refresh_parity_tier1_outcomes() (read its full definition via
SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname='refresh_parity_tier1_outcomes' through the Management
API) ONLY operates on auction_status IN ('redeemed','completed','sold','cancelled','canceled') and matches against
tax_deed_outcomes/foreclosure_outcomes -- tables that only get populated AFTER a sale/result exists. It structurally
CANNOT touch upcoming auctions because there is no outcome yet. Calling it again will not move C/D.

THE REAL LEVER (already proven elsewhere in this campaign -- do not reinvent): several counties get matched_clean
on UPCOMING rows via a DIFFERENT mechanism -- an "AJAX harvest" that scrapes the live RealAuction/RealTaxDeed
calendar directly (a LISTING comparison, not an OUTCOME comparion) and writes parity_source values like
'tier1_realauction_ajax_harvest_shard2_hillsborough_...' or 'tier1:shard9_flagler_ajax_harvest:...'. Read
scripts/shard9_flagler_cd_ajax_harvest.py in full -- it is a working, recently-shipped reference implementation
for exactly this pattern (built on top of the reusable scripts/shard2_run2450_ajax_realforeclose_harvest.py
harvester). Port/adapt this pattern to Orange: for each distinct (sale_type, auction_date) among Orange's 196
unmatched upcoming rows, harvest Orange's live RealAuction/RealTaxDeed AJAX calendar for that date, exact-match by
normalized case_number, and PATCH parity_status='matched_clean' (or 'matched_divergent' if the details genuinely
disagree) with parity_source starting 'tier1' (e.g. 'tier1:shard5_orange_ajax_harvest:<sale_type>:<date>') --
remember matched_clean/matched_any specifically require parity_source LIKE 'tier1%%', setting parity_status alone
does not satisfy C/D. The flagler script's harvester also opportunistically backfills parcel_id/property_address/
assessed_value on NULL fields during the same pass -- doing the same for Orange should also help close I's gap
(43 of the 59 missing card_complete rows are missing property_address specifically; 8 missing parcel_id, 3 missing
geo, 3 missing value -- verified via live count). Check first whether Orange already has a platform-specific
harvester under a different name (scripts/shard28_run338_i_orange.py, scripts/shard7_orange_e_parcel_linkage.py,
scripts/gold_standard_orange_bcd_outcomes_backfill.py, scripts/gold_standard_orange_upcoming_reclassify.py,
scripts/shard13_e_linkage_fix.py, scripts/shard13_letter_b_verified_outcomes.py all touch orange -- read them
before writing anything new) so you don't duplicate work; confirm via pipeline.counties which platform (RealAuction
vs RealTaxDeed vs other) Orange actually uses for tax deeds vs foreclosures before assuming the AJAX endpoint shape.
This is the highest-leverage fix in this shard -- prioritize it.`,
  },
  {
    slug: 'hamilton',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now): 4/10. Passing: A=6(fc=6 td=10),
G=100.0, H=1.1h, J=100.0(16 of 16). Failing: B=null(verified=0 closed_sold=0), C=43.8(matched_clean=7 of 16),
D=43.8(matched_any=7 of 16), E=93.8(parcel_linked=15 of 16), F=null(tier1_sold=0 closed_sold=0),
I=6.3(card_complete=1 of 16).

CRITICAL: a session in THIS SAME dispatch wave already worked hamilton TODAY, commit bff21708
("fix(gold-standard-hamilton): E parcel linkage 68.8%%->93.8%% via tax collector search; C/D/B/F confirmed
structurally blocked, not bugs"). Read that commit's full message (git log -1 --format=%B bff21708) AND
scripts/shard5_run3679_hamilton_e_linkage.py AND the companion diagnosis SQL file it shipped BEFORE touching
anything -- your live numbers above already reflect that fix (E=93.8%% matches exactly, confirming no drift).
That session's conclusions, which you must independently RE-VERIFY (do not just trust them, but they are
plausible and well-evidenced -- this is exactly what the adversarial refuter step exists for):
- C/D: the 9 unmatched rows (6 upcoming foreclosure 'mca_only' + 3 upcoming tax_deed with NULL parity) cannot
  match because public.refresh_parity_tier1_outcomes() structurally excludes auction_status='upcoming' by design
  (only matches against outcome tables, which are empty until a sale happens). Re-verify: are these 9 cases
  genuinely still upcoming/unsold live right now, or has any since closed? If any closed, the outcome-matching
  function should now be able to match it -- check.
- B/F: 0 of 16 hamilton rows have sold_amount populated. The 7 'redeemed' tax_deed rows are legitimately redeemed
  (no sale price by definition -- redemption means the sale never happened). The clerk's surplus-funds page
  reportedly returned "No available properties at this time" live-checked this morning -- re-check it fresh,
  pages change. If nothing closed since, B/F remain a genuine data ceiling for a tiny rural county with almost no
  sale volume -- do not fabricate.
- I: card_complete=1 of 16 (worst of the shard). Prior session found FL GIO ArcGIS has no PARCEL_ID crosswalk for
  Hamilton's local parcel numbering, qpublic/hamiltonpa.com is Cloudflare-blocked (403), and the tax collector site
  only exposes mailing address (not situs/property address, correctly not substituted). This was reported as
  "genuinely blocked this session" not "permanently impossible" -- take ONE more real crack at it: check whether
  Hamilton County itself runs its own ArcGIS FeatureServer (distinct from the FL GIO statewide layer) per playbook
  E's guidance to use "the county property appraiser ArcGIS FeatureServer" directly (try
  gis.hamiltoncountyfl.us or similar county-hosted endpoints, not just hamiltonpa.com/qpublic which are
  confirmed blocked) -- if a real one exists with address+geo+value fields, that could move both E's last row and
  I meaningfully. FIRECRAWL_API_KEY is ABSENT in this session's environment (checked), so a Firecrawl-based
  Cloudflare bypass is not available to you either -- do not assume it is.

Given how recently and thoroughly this county was already worked, weight your time toward (a) a fast, honest
adversarial re-verification of the four structurally-blocked claims (this doubles as your ULTRALOOP refuter
evidence), (b) the one genuinely new I angle above, and (c) do NOT re-run probes that were already conclusively
answered hours ago without a reason to think the answer changed -- that wastes shard budget better spent on
flagler/orange. If nothing new is found, say so plainly and log the residual honestly.`,
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
  then curl --data-binary @file) rather than hand-quoting shell strings -- nested single/double quotes in SQL break
  naive shell quoting and can silently produce an empty/wrong query.
  NOTE: direct psycopg2/psql pooler connections were tried this session and password auth FAILED against both
  aws-0-us-west-2.pooler.supabase.com and db.mocerqjnksmhcjzxrewo.supabase.co -- do not waste time on that path,
  use the Management API / REST above exclusively, consistent with prior shard sessions' notes.
  The public.exec_sql RPC does NOT currently exist in the schema (checked live, PGRST202) -- use the Management
  API endpoint above for arbitrary SQL, not rpc/exec_sql.
- pencil_dod_evaluate_county RPC: POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county
  headers apikey/Authorization as above, body {"p_county": "<slug>"} -- this is your before/after proof. The
  live function definition (verified this session via pg_get_functiondef) computes every letter from
  multi_county_auctions filtered to lower(county)=<slug> AND (data_source <> 'propertyonion' OR
  tier1_authoritative=true) -- i.e. PropertyOnion-sourced rows are excluded from the denominator entirely unless
  explicitly marked tier1_authoritative. C/D specifically require parity_source LIKE 'tier1%%' in addition to
  parity_status -- setting parity_status alone does NOT satisfy C/D. B only passes in the 95-105%% band, not just
  >=95%%.
- gh CLI is authenticated (repo, workflow scopes) for git operations and workflow dispatch if needed.
- Repo root is the current working directory. Schema changes MUST go through a migration file under
  supabase/migrations/<date>_shard5_<county>_<purpose>.sql, committed to git -- even though you CAN run SQL
  directly via the Management API, still write the migration file for the historical record and apply it the
  same way. Simple data backfills (UPDATE/PATCH on existing columns, no schema change) do not need a migration
  file -- just do the REST PATCH or a direct UPDATE via the Management API and note the exact SQL/endpoint used.

ULTRALOOP audit logging (mandatory per campaign protocol): for every letter you claim moved (or claim you
verified as correctly-blocked/residual), INSERT one row into public.gold_standard_ultraloop_audit:
  columns: dispatch_id (uuid '${DISPATCH_ID}'), ultraloop_mode ('fallback' -- this session used manual Task
  subagent fan-out, not native /effort ultracode), county_slug, letter, claim (short text of what you claim),
  refuter_evidence (jsonb -- for the FIX agent, put your own before/after evidence; for the VERIFY agent, put your
  refutation attempt and what you found), survived (boolean -- true only if the claim held up under adversarial
  check). Use the REST endpoint: POST \${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with the service-role
  headers above. Do this as part of your normal work, not as an afterthought.

Hard rules (from the campaign brief -- follow exactly):
- You own ONLY your assigned county. Never touch another shard-5 county's rows, or any other shard's counties.
- PropertyOnion is litmus/comparison ONLY -- never write po_* derived values in as if they were verified/independent.
- Fail-loud invariant: if a fix attempt finds zero real data, report it as a blocked/residual gap. NEVER fabricate
  case numbers, parcel IDs, sale amounts, coordinates, or timestamps to make a metric look better. This project has
  a documented history of exactly this failure mode (gulf B/F fabrication, purged) -- do not repeat it in any form,
  including "close enough" placeholder values.
- Every claim you return must be tagged VERIFIED (you ran the query/request and are pasting real output), UNTESTED,
  or INFERRED (say why).
- Before finishing: call pencil_dod_evaluate_county for your county and paste the FULL before (already given
  above, or re-verify fresh if you suspect drift) and after JSON. If a letter did not move, say so plainly.
- git commit any file you create/modify with a clear message, county-scoped, and 'git pull --rebase origin main'
  before pushing (other shards may be pushing concurrently to shared paths -- you are isolated in a worktree so
  conflicts should be rare, but rebase defensively anyway). Push directly to main -- no branches, no PRs.
- Do NOT run public.gold_standard_loop() or gold_standard_certify() -- other shards may be mid-session. Do NOT
  modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job.
- Budget yourself: this is ONE bounded pass, not a 6-hour campaign in itself. If the true fix requires building a
  brand-new scraper from scratch, do NOT build it in this pass -- size the gap precisely, report it as a
  scoped-out residual with what a future session needs to do, and ship whatever smaller, real, verifiable
  improvement IS achievable via SQL/REST/live lookups alone (data backfill, wiring an existing-but-unrun pipeline,
  honesty corrections).

Return a structured report: { county, letters_touched: [...], fix_summary, sql_or_endpoints_used: [...],
before_json, after_json, residual_gaps: [...], honesty_notes: [...] }.
`

phase('Diagnose+Fix')
const fixResults = await pipeline(
  COUNTIES,
  (county) => agent(
    `You are working Gold Standard shard-5, county "${county.slug}", inside the cli-anything-biddeed repo (already checked out, on main).\n\n${county.context}\n\n${RECIPE}`,
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
    `documented history of exactly this failure mode, e.g. G passing 100%% on zero applicable parcels), (c) whether ` +
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
