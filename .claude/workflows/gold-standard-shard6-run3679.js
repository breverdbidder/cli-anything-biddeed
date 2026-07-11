export const meta = {
  name: 'gold-standard-shard6-run3679',
  description: 'Gold Standard shard-6 (polk/franklin/putnam/hendry): diagnose, fix, adversarially verify failing letters per county',
  phases: [
    { title: 'Diagnose+Fix', detail: 'one agent per county, worktree-isolated' },
    { title: 'Verify', detail: 'independent refuter per county claim' },
  ],
}

const DISPATCH_ID = 'e9951859-29fe-4c2e-aa04-ca05ced1d0c7'

const COUNTIES = [
  {
    slug: 'polk',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now, supersedes the stale brief numbers which
had claimed C/D FAIL at 98.2 — that was wrong, C/D actually PASS): 9/10, only I fails: metric=90.4
(card_complete=614 of 679). All other letters PASS: A=153 (fc=526 td=153), B=100.0 (verified=10 closed_sold=10 —
do not touch, exactly in the 95-105%% valid band), C=97.1 (matched_clean=659), D=97.1 (matched_any=659), E=99.9
(parcel_linked=678 of 679), F=100.0, G=100.0, H=1.0h, J=100.0.

VERIFIED this session (fresh SQL breakdown, eval-scope rows only i.e. data_source<>'propertyonion' OR
tier1_authoritative=true, 643 rows at query time vs evaluator's 679 auctions_total — denominator is growing as
ingestion continues, re-verify fresh rather than trust these exact counts):
addr_null=0, geo_null=63 (missing latitude/longitude), value_null=57 (missing BOTH assessed_value AND
market_value), parcel_null=1, and 64 of the eval-scope rows have a non-null parcel_id that does NOT appear in
v_zoning_gold_standard_card (the zoning-linkage join card_complete also requires). These populations overlap
heavily (a row missing geo is often also missing the zoning-card link) — the true gap is ~65 rows short of the 679
denominator, consistent with card_complete=614.

Existing scripts to check FIRST (avoid duplicating — search their docstrings before writing anything new):
gold_standard_shard6_polk_cd_i_ajax_harvest.py (name suggests I-relevant, check if it already ran / what it
covers), shard6_polk_j_gap_backfill.py, shard7_polk_fixes.py, shard2_polk_fix_run1635.py,
shard13_run3059_duval_polk_alachua_union_cd_e.py, shard13_run2_20260705_duval_polk_alachua_union_cd_e.py.

Your job: identify the exact ~65 rows failing card_complete (join against v_zoning_gold_standard_card fresh, don't
trust the counts above blindly), then (1) for the geo_null=63 rows, geocode via the Polk County Property Appraiser
(search live for their public GIS/ArcGIS FeatureServer or parcel search endpoint — do not guess a URL, verify it
resolves) using parcel_id as the join key; (2) for value_null=57, backfill assessed_value/market_value from the
same PA source; (3) for the 64 rows outside v_zoning_gold_standard_card, determine whether their parcel_id is
simply missing from parcel_zones (a real, scoped zoning-ingestion gap for those specific parcels — since G already
passes 100%% for polk overall, this may be a handful of parcels in a jurisdiction/zone not yet covered, not a
county-wide zoning rebuild) or a parcel_id formatting mismatch between multi_county_auctions and parcel_zones
(a real, fixable matching bug). Do NOT rebuild polk's zoning ingestion from scratch if it's a large gap — size it
precisely and report as residual if it exceeds one session's budget; but DO fix it if it's a small handful of
missing parcel_zones rows or a formatting mismatch, since that is the highest-leverage remaining lever (9/10 -> 10/10
for polk rides entirely on this one letter).`,
  },
  {
    slug: 'franklin',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now, matches brief): 8/10, only B and F fail
(both metric=null, verified=0/closed_sold=0 and tier1_sold=0/closed_sold=0). All else PASS: A=4 (fc=4 td=5), C=100.0
(matched_clean=9 of 9), D=100.0, E=100.0, G=100.0, H=9.9h, I=100.0, J=100.0. Only 9 total auctions — small, tractable
county.

CRITICAL — read scripts/franklin_bf_verified_no_sales_2026-07-10.py IN FULL before doing anything (it is an
unusually thorough same-week investigation, dated yesterday 2026-07-10, and its docstring alone is the report).
Summary of its VERIFIED findings: franklin's clerk (www.franklinclerk.com) is WordPress and exposes a real,
authoritative, no-auth REST API (GET .../wp-json/kma/v1/taxdeeds, /foreclosures, /taxdeedoverbids,
/landavailables — requires a browser User-Agent header, default UA gets HTTP 403 from their WAF). It found this
API's 5 taxdeed rows match our 5 franklin TDA-family MCA rows 1:1 by cert number, all still status='scheduled' or
'redeemed' with a Jul 8, 2026 sale_date — i.e. genuinely no sale outcome data exists anywhere upstream (no sold
status, no overbid/surplus record, no land-available reversion) for any of the 4 target 2023 tax-deed certs. It
also corrected pipeline.counties.taxdeed_platform/foreclosure_platform to 'clerk_wp_rest:franklinclerk.com/wp-json/kma/v1/...'
live via the Management API (already applied, do not redo), but deliberately left pipeline_status='blocked' since
the SALE-OUTCOME half (what B/F need) remains genuinely unobtainable. It explicitly did NOT write any row —
correctly, per HONESTY PROTOCOL BLANK > WRONG — and references a prior fabrication incident for this exact county
(supabase/migrations/20260702_shard5_franklin_outcome_bid_decision_fabrication_cleanup.sql) that must never repeat.

Your job (bounded, do not sink the session here): it is now 2026-07-11, three days past the Jul 8 sale date (one
day past when that investigation ran) — do ONE fresh live re-check of GET https://www.franklinclerk.com/wp-json/kma/v1/taxdeeds
and /taxdeedoverbids with a browser User-Agent header, for the same TDA 93-2023 / 411-2023 / 616-2023 / 624-2023 /
632-2023 certs. If the clerk's site has now updated any of these to a real sold status with a dollar amount (or an
overbid record), write the corresponding INDEPENDENT verified outcome row(s) (tax_deed_outcomes, data_source like
'clerk_wp_rest:franklinclerk.com') and backfill sold_amount on the matching multi_county_auctions row(s), then
re-run pencil_dod_evaluate_county to confirm B/F actually moved. If the API still shows no sold data (most likely,
given only 3 days have passed and the prior investigation found their post-sale update lag is itself an observed
behavior), confirm and report the blocked-residual status honestly with your fresh evidence pasted — do NOT
fabricate, do NOT force a partial write. Since franklin has no other failing letters, if B/F remain genuinely
blocked after your fresh check, that is a legitimate 8/10 outcome for this session; do not manufacture busywork.`,
  },
  {
    slug: 'putnam',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now, close to brief but denominator has grown
slightly, 239 total, and I is worse than the brief claimed — 92.1 vs brief's stale number, re-verify don't trust old
numbers): 7/10, failing C (metric=69.5, matched_clean=166 of 239), D (metric=69.5, matched_any=166 of 239), I
(metric=92.1, card_complete=220 of 239). All else PASS: A=38 (fc=38 td=201), B=100.0 (verified=3 closed_sold=3 —
exactly in the 95-105%% valid band, do not touch), E=96.7 (parcel_linked=231 of 239), F=100.0, G=100.0, H=1.4h,
J=98.7.

VERIFIED this session, full parity_status x parity_source x auction_status breakdown for putnam (sums to 239):
the ENTIRE C/D gap is 73 rows with parity_status=NULL / parity_source=NULL, auction_status='upcoming' — every
other row (166 of them) already carries parity_status='matched_clean' with parity_source starting 'tier1:' via an
existing harvester (parity_source pattern 'tier1:shard9_run3059_ajax_harvest:tax_deed:<date>' and
'tier1:shard9_run3059_ajax_harvest:foreclosure:<date>', covering dates 2026-07-22 (48 rows), 2026-07-08 (39),
2026-06-24 (35), plus a long tail of smaller foreclosure dates, plus a few 'tier1_realforeclose_aids_ajax_putnam'
and 'tier1_tax_deed_outcome'/'tier1_foreclosure_outcome' rows). No script with 'putnam' in its filename exists in
scripts/ (grepped, zero hits) — the working harvester is named for a DIFFERENT shard/run (shard9_run3059) but
clearly already covers putnam; find its actual file (search scripts/ and .github/scripts/ content, not just
filenames, for 'shard9_run3059_ajax_harvest' or 'realforeclose_aids_ajax_putnam') before writing anything new.

Your job: query the 73 NULL-parity rows for their distinct auction_date + sale_type combinations (they are exactly
the rows the harvester has NOT yet covered), then either (a) re-run the existing harvester script for those specific
missing dates (extend its target list, do not rewrite it), following the exact same 'tier1:<script>:<sale_type>:<date>'
parity_source naming convention so matched_clean is recognized identically, or (b) if those dates are genuinely
future/not-yet-listed on putnam.realforeclose.com / putnam.realtaxdeed.com (config confirmed both online at
putnam.realforeclose.com and putnam.realtaxdeed.com, fc_method='online' td_method='online' — no county exception
here), confirm that live and report as a residual data-maturation ceiling, same pattern as other counties' upcoming-only
gaps. For I: the zoning-card join is NOT the constraint here (v_zoning_gold_standard_card already covers 259 putnam
parcels vs 239 total auctions — i.e. zoning linkage is not putnam's bottleneck, unlike polk/hendry). VERIFIED
eval-scope breakdown: addr_null=5, geo_null=1, value_null=1, parcel_null=8 (summing to ~15, close to the 19-row gap
implied by 220/239, allow overlap). Backfill these via the Putnam County Property Appraiser (search live for their
GIS/parcel-search endpoint, do not guess a URL) keyed on parcel_id/case_number. This is a small, tractable
enrichment — prioritize it alongside the C/D harvest extension since both are achievable within budget.`,
  },
  {
    slug: 'hendry',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now — hendry has IMPROVED since the brief:
C and D now PASS at 100.0 (matched_clean=17 of 17, matched_any=17 of 17), already fixed by a prior session's
tier1:shard6_run3645_hendry_realtaxdeed_live_calendar_match harvest, confirmed live in the data — do not re-chase
C/D). Current live status 6/10: failing A (metric=0, fc=0 td=17), B (metric=null, verified=0 closed_sold=0), F
(metric=null, tier1_sold=0 closed_sold=0), I (metric=17.6, card_complete=3 of 17). PASS: C=100.0, D=100.0, E=100.0
(parcel_linked=17 of 17), G=100.0 (VACUOUS — see I note below, do not rely on this), H=9.8h, J=100.0.

VERIFIED this session: ALL 17 hendry multi_county_auctions rows are sale_type=tax_deed, auction_status='upcoming',
single auction_date 2026-07-16, data_source='calendar_sweep_mca_v3', parity_status='matched_clean'. There are
currently ZERO foreclosure rows for hendry in MCA at all (this is the A gap, fc=0). Per
scripts/shard11_run3534_hendry_cd_harvest.py's own documented investigation (read it — do not re-derive):
county_auction_config confirms hendry fc_method='in_person', fc_url=null, fc_courthouse_address=null — hendry has
NO online RealForeclose platform, matching the pattern in COUNTY EXCEPTIONS (courthouse in-person sales, like
Brevard). That script deliberately left foreclosure rows untouched pending "a genuine independent source."

Your job on A: find Hendry County Clerk's real foreclosure sale calendar/docket (search live for it — likely the
Hendry County Clerk of Courts site; do NOT guess a URL, verify whatever you find actually resolves and lists
foreclosure sales) and, if found, ingest at least the currently-scheduled foreclosure sales as new MCA rows tagged
with an honest platform label (e.g. 'clerk_html' or similar, NOT 'realauction'/'realforeclose' since it isn't one),
following the Brevard reference pattern (clerk-recorded calendar, not RealAuction). If genuinely no public online
foreclosure calendar exists for hendry (small rural county, plausible), report that precisely as a residual with
what you tried, rather than fabricating rows — do not force fc>0 with invented data.

On B/F: all 17 rows are 'upcoming' for a 2026-07-16 sale — none have actually sold yet, so closed_sold=0 is
currently correct and not fixable until a real sale clears; check briefly whether any OLDER/closed hendry cases
exist outside this single-date snapshot (query multi_county_auctions AND tax_deed_outcomes/foreclosure_outcomes
broadly for hendry, not just the 17 upcoming rows) — if none, report B/F as a genuine not-yet-applicable gap (same
honest pattern as franklin), do not fabricate a sold_amount.

On I: VERIFIED root cause — only 3 of 17 hendry parcels have ANY row in parcel_zones / v_zoning_gold_standard_card
at all (confirmed by direct join). This is why G's 100%% is VACUOUS (it's passing on a near-empty applicable set) —
do not treat G as evidence hendry's zoning is fine. The other 14 rows are missing the zoning-card link entirely,
which is the actual I blocker (address/geo/value are mostly already populated — only addr_null=5, geo_null=0,
value_null=0, parcel_null=0 out of 17). SEPARATE HONESTY FLAG (not the I blocker, but worth a line in your report):
13 of the 17 rows share the IDENTICAL latitude/longitude (26.7298, -81.0352) — this looks like a county-centroid
fallback rather than real per-parcel geocoding; it does not fail the current IS-NOT-NULL geo check so it isn't
blocking I today, but flag it as a data-quality residual, do not "fix" it by inventing more precise coordinates
without a real source. Real I fix: hendry is tiny (17 parcels across a handful of unincorporated areas plus
LaBelle/Clewiston) — attempt a minimal, real zoning substrate build (jurisdictions for LaBelle + Clewiston +
unincorporated Hendry, zone codes/parcel_zones for just these 17 parcels' actual zoning designation, sourced from
the Hendry County Property Appraiser if it exposes zoning per parcel, or the relevant municipal/county zoning map)
similar in spirit to the Duval G+I substrate-build item referenced in the campaign brief, but scoped down to
hendry's much smaller footprint. If a full substrate build proves too large for this session, size it precisely
and report as residual rather than forcing a partial/misleading zoning assignment.`,
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
  parity_status -- setting parity_status alone does NOT satisfy C/D. card_complete (I) requires address AND geo
  AND value AND the parcel_id present in v_zoning_gold_standard_card.
- gh CLI is authenticated (repo, workflow scopes) for git operations and workflow dispatch if needed.
- Repo root is the current working directory. Schema changes MUST go through a migration file under
  supabase/migrations/<date>_shard6_<county>_<purpose>.sql, committed to git — even though you CAN run SQL
  directly via the Management API, still write the migration file for the historical record and apply it the
  same way. Simple data backfills (UPDATE/PATCH on existing columns, no schema change) do not need a migration
  file — just do the REST PATCH or a direct UPDATE via the Management API and note the exact SQL/endpoint used.
- Franklin's clerk site (franklinclerk.com) requires a browser User-Agent header or you get HTTP 403 from its WAF
  (verified this session) — this likely applies to other small-county clerk sites too; if a fetch 403s with a
  default UA, retry with a standard browser User-Agent before concluding the source is unavailable.

ULTRALOOP audit logging (mandatory per campaign protocol): for every letter you claim moved (or claim you
verified as correctly-blocked/residual), INSERT one row into public.gold_standard_ultraloop_audit:
  columns: dispatch_id (uuid '${DISPATCH_ID}'), ultraloop_mode ('fallback' -- this session used manual Task
  subagent fan-out, not native /effort ultracode), county_slug, letter, claim (short text of what you claim),
  refuter_evidence (jsonb -- for the FIX agent, put your own before/after evidence; for the VERIFY agent, put your
  refutation attempt and what you found), survived (boolean -- true only if the claim held up under adversarial
  check). Use the REST endpoint: POST \${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with the service-role
  headers above. Do this as part of your normal work, not as an afterthought.

Hard rules (from the campaign brief — follow exactly):
- You own ONLY your assigned county (polk, franklin, putnam, or hendry). Never touch another shard's counties,
  their rows, or their county-specific files.
- PropertyOnion is litmus/comparison ONLY — never write po_* derived values in as if they were verified/independent.
- Fail-loud invariant: if a fix attempt finds zero real data, report it as a blocked/residual gap. NEVER fabricate
  case numbers, parcel IDs, sale amounts, coordinates, or timestamps to make a metric look better. This project has
  a documented history of exactly this failure mode (gulf B/F fabrication, franklin outcome/bid_decision
  fabrication — purged) — do not repeat it in any form, including "close enough" placeholder values.
- Every claim you return must be tagged VERIFIED (you ran the query/request and are pasting real output), UNTESTED,
  or INFERRED (say why).
- Before finishing: call pencil_dod_evaluate_county for your county and paste the FULL before (already given
  above, or re-verify fresh if you suspect drift) and after JSON. If a letter did not move, say so plainly.
- git commit any file you create/modify with a clear message, county-scoped, and 'git pull --rebase origin main'
  before pushing (other shards may be pushing concurrently to shared paths — you are isolated in a worktree so
  conflicts should be rare, but rebase defensively anyway). Push directly to main — no branches, no PRs.
- Do NOT run public.gold_standard_loop() or gold_standard_certify() yourself — other shards may be mid-session.
  Do NOT modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job.
- Budget yourself: this is ONE bounded pass, not a 6-hour campaign. If the true fix requires building a brand-new
  scraper or a full zoning substrate from scratch, do NOT build it in this pass if it's large — size the gap
  precisely, report it as a scoped-out residual with what a future session needs to do, and ship whatever smaller,
  real, verifiable improvement IS achievable via SQL/REST/live lookups alone (data backfill, wiring an
  existing-but-unrun pipeline, honesty corrections). Small/tractable substrate builds (e.g. hendry's 17-parcel
  zoning gap) ARE in scope if genuinely small.

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
    `Independently verify this claimed Gold Standard fix for county "${county.slug}". You did NOT write this fix — be skeptical.\n\n` +
    `Claimed result: ${JSON.stringify(result)}\n\n` +
    `${RECIPE}\n\n` +
    `Your job: re-run pencil_dod_evaluate_county for "${county.slug}" yourself RIGHT NOW (fresh call, do not trust the pasted after_json), ` +
    `compare against the claimed before/after, and check specifically for: (a) denominator mismatches (does the ` +
    `"auctions_total" / "closed_sold" count match what you independently query?), (b) ghost-success (any letter now ` +
    `passing because of a placeholder/fabricated/vacuous value rather than a real fix — this campaign has a ` +
    `documented history of exactly this failure mode, e.g. G passing 100% on zero applicable parcels, or hendry's ` +
    `own G=100 vacuous-pass noted in this shard's brief), (c) whether any OTHER letter for this county regressed as ` +
    `a side effect, (d) for B specifically, the only valid pass band is 95-105%% -- an anomalous ratio outside that ` +
    `(even if the raw pass/fail bit says true) should be flagged. Also INSERT your own gold_standard_ultraloop_audit ` +
    `row per the RECIPE instructions (ultraloop_mode='fallback'). ` +
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
