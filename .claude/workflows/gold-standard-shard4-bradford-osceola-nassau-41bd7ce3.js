export const meta = {
  name: 'gold-standard-shard4-bradford-osceola-nassau-41bd7ce3',
  description: 'Gold Standard shard-4 (dispatch 41bd7ce3, loop run 8166): bradford B/F lightweight reconfirm (7th session, prior 6 exhausted), osceola G single-parcel Kissimmee SRPUD parking lever + I 33-row card-completeness backfill, nassau C/D/I 3-row tier1 parity + geo backfill, adversarially verify',
  phases: [
    { title: 'Diagnose+Fix', detail: 'one agent per work item, worktree-isolated' },
    { title: 'Verify', detail: 'independent refuter per claim' },
  ],
}

const DISPATCH_ID = '41bd7ce3-a9f5-465d-99a1-a3ed447d8ce4'

const RECIPE = `
Environment (already available, do not ask for credentials):
- Live arbitrary SQL (the ONLY working DB path -- direct psql/pooler connections FAIL with password auth errors,
  confirmed this session, do not waste time on that): POST
  https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query
  headers Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json
  body {"query": "<sql>"} -- run "SET statement_timeout = 0;" first in the same query string for anything heavy.
  Build the JSON body with a real encoder (python3 -c "import json; ..." to a temp file, then curl --data-binary
  @file) rather than hand-quoting shell strings. NOTE: this endpoint had one transient "hot standby mode is
  disabled" failure mid-diagnosis this session that cleared on retry after ~15s -- if you hit a transient
  connection error, wait ~15s and retry once before treating it as a real blocker.
- REST reads/writes: GET/PATCH/POST \${SUPABASE_URL}/rest/v1/<table>?... with headers
  apikey: $SUPABASE_SERVICE_ROLE_KEY, Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY. Never echo/print the
  resolved header value itself into any file/comment/log -- reference the env var, not the secret.
- pencil_dod_evaluate_county RPC (confirmed live this session): POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county
  body {"p_county": "<slug>"} -- returns one jsonb object with keys A..J (each {pass,metric,detail}), county,
  auctions_total, V2_LITMUS. This is your before/after proof. B passes ONLY in the 95-105%% band. C/D require
  parity_status IN ('matched_clean') for C / ('matched_clean','matched_divergent') for D AND parity_source LIKE
  'tier1%%' -- setting parity_status alone does NOT satisfy C/D. E = parcel_id IS NOT NULL. I additionally requires
  property_address, lat/long, assessed_value/market_value ALL non-null AND parcel_id present with zone_code
  resolvable in v_zoning_gold_standard_card (which requires a parcel_zones row keyed by that exact parcel_id/STRAP,
  joined to zoning_districts by (jurisdiction_id, zone_code), joined to zone_standards). J requires a bid_decisions
  row matched by case_number with arv+max_bid+ml_score+all 5 factor keys.
- The canonical parity matcher is public.refresh_parity_tier1_outcomes(p_county text) -- call it via the SQL
  endpoint after any parity-relevant insert/update, never hand-write parity_status/parity_source yourself.
- G is evaluated by v_zoning_gold_standard_kpi_v3, built from parcel_zones -> zoning_districts (by
  jurisdiction_id+zone_code) -> zone_standards, gated by v_zoning_district_applicability (far_applicable /
  pk1000_applicable / density_applicable, default true if no applicability row exists). Writing a real value to
  zone_standards for a district that already has a parcel_zones row pointing at it is the highest-leverage single
  write -- it can move every parcel currently zoned to that district in one shot.
- Skills available via the Skill tool: "browser-use" and "firecrawl-browser" for real interactive/rendered browser
  sessions (JS execution, WAF/Cloudflare-cleared, form fills); "firecrawl-scrape"/"firecrawl-search" for simple
  static content and general web search. FIRECRAWL_API_KEY is present with credit.
- gh CLI is authenticated. Repo root is the current working directory (worktree-isolated copy, on main). Any
  UPDATE to existing multi_county_auctions/zone_standards columns is a data backfill, not a schema change -- still
  write a short documentation migration file under
  supabase/migrations/<date>_gold_standard_shard4_41bd7ce3_<county>_<purpose>.sql per house style (narrative
  comment block with VERIFIED evidence/source URLs, then the idempotent SQL mirroring what you ran live -- see any
  recent supabase/migrations/2026073*_gold_standard_shard*.sql file for the pattern), then apply the real change via
  the Management API SQL endpoint / REST PATCH as usual.

ULTRALOOP audit logging (mandatory per campaign protocol): for every letter you claim moved, or claim you verified
as correctly-blocked/residual, INSERT one row into public.gold_standard_ultraloop_audit: columns dispatch_id (uuid
'${DISPATCH_ID}'), ultraloop_mode ('fallback' -- manual Workflow-tool fan-out, not native /effort ultracode),
county_slug, letter, claim (short text), refuter_evidence (jsonb -- your evidence), survived (boolean, true only if
the claim held up under adversarial check -- the FIX agent should insert survived=true only for its OWN sanity
check, the real adversarial gate is the separate Verify-phase agent). POST to
\${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with service-role headers.

Hard rules (from the campaign brief and this repo's CLAUDE.md -- follow exactly):
- You own ONLY bradford, osceola, and nassau. Never touch any other county's rows or any other shard's files.
- PropertyOnion (po_* fields, data_source LIKE 'propertyonion%%' or 'PO-%%' case numbers) is litmus/comparison ONLY
  -- never write PropertyOnion-derived values in as if they were verified/independent, and never let a PO-* stub
  row count as a "fix" for B/C/D/F.
- Fail-loud invariant: if a fix attempt finds zero real data, report it as blocked/residual. NEVER fabricate case
  numbers, parcel IDs, STRAPs, addresses, coordinates, zoning values, or sold amounts to make a metric look better.
  This campaign has a DOCUMENTED, repeated fabrication-then-revert history specifically in bradford (I:
  assessed_value=145000/market_value=152250 hardcoded across all rows, reverted twice) and osceola (multiple
  "ghost purge" migrations reverting fabricated I/G values) -- do not repeat it in any form, including reusing
  another row's numbers or a "close enough" placeholder.
- Every claim must be tagged VERIFIED (you ran the query/request and are pasting real output), UNTESTED, or
  INFERRED (say why).
- Before finishing: call pencil_dod_evaluate_county for your county and paste the FULL before/after JSON. If a
  letter did not move, say so plainly -- a genuinely source-exhausted row is a valid, honest outcome.
- git commit any file you create/modify with a clear, county-scoped message. 'git pull --rebase origin main' before
  pushing (other shards may push concurrently to shared paths -- you are isolated in a worktree so conflicts should
  be rare, but rebase defensively anyway). Push directly to main -- no branches, no PRs, per the SHIP-TO-MAIN
  mandate.
- Do NOT run public.gold_standard_loop() or gold_standard_certify() -- other shards may be mid-session. Do NOT
  modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job.
- Budget yourself. If a true fix requires building a brand-new scraper from scratch, do NOT build it in this pass
  -- size the gap precisely, report it as a scoped-out residual.

Return: { work_item, county, letters_touched: [...], fix_summary, sql_or_endpoints_used: [...], before_json,
after_json, residual_gaps: [...], honesty_notes: [...] }.
`

const WORK_ITEMS = [
  {
    key: 'bradford_bf',
    county: 'bradford',
    letters: ['B', 'F'],
    prompt: `You are working Gold Standard shard-4, county "bradford", letters B/F, dispatch ${DISPATCH_ID}, inside
the cli-anything-biddeed repo (already checked out, on main).

Live baseline (VERIFIED this session via pencil_dod_evaluate_county('bradford') and a direct row dump, matches the
campaign brief exactly): 8/10. Passing: A=1(fc=4 td=1, documented-blocked -- bradford genuinely has zero tax deed
sales scheduled per clerk PDF, do not re-probe), C=100(matched_clean=5) D=100(matched_any=5) E=100(parcel_linked=5)
G=100(density=100) H=1.7h I=100(card_complete=5 of 5) J=100(deal_complete=5). Failing: B=null(verified=0
closed_sold=0), F=null(tier1_sold=0 closed_sold=0). auctions_total=5. Do NOT touch A/C/D/E/G/H/I/J.

All 5 bradford rows are auction_status='upcoming'. Four have future auction_date (24000431CAAXMX 2026-08-20,
25000439CAAXMX 2026-08-13, 25000487CAAXMX 2026-08-13, 04-2026-TD-002 2026-09-09). ONE, case 25000457CAAXMX
(VyStar Credit Union v. Unknown Heirs of Debra Ilene Hunter, 18737 CHARLOTTE AVE, BROOKER FL 32622, parcel_id
00273-0-01000), has auction_date=2026-07-16 -- 17 days in the past as of today (2026-08-02) -- yet is still
'upcoming' with sold_amount=null. This is the ONLY lever for B/F.

CRITICAL CONTEXT -- READ BEFORE SPENDING ANY BUDGET: this exact case has now had SIX consecutive prior sessions
(dispatches 42aac1fb x2, d07c1eba x2, c475a06d x2, f68d2ec5) exhaust essentially every reachable public channel.
Read supabase/migrations/20260725_gold_standard_shard5_bradford_i_bf_residual_confirmation.sql,
20260725c_gold_standard_shard13_bradford_i_real_fix_bf_3rd_reconfirm.sql,
20260725d_gold_standard_shard13_bradford_bf_4th_reconfirm_ori_turnstile.sql,
20260729_gold_standard_shard6_bradford_bf_5th_reconfirm_civitek_turnstile.sql, and the session report
GOLD_STANDARD_SHARD10_BRADFORD_SEMINOLE_DISPATCH_96A9BC5D_SESSION_REPORT.md (6th session, 2026-07-31) for the full
dead-end list: bradfordclerk.com (Cloudflare 403 to curl/WebFetch/Firecrawl -- JS challenge doesn't resolve even
with waitFor), civitekflorida.com/ocrs/county/04 (Turnstile CAPTCHA on search submit), myfloridacounty.com/orisearch
(Turnstile), bctelegraph.com legal notices (checked through 7/30, no post-sale notice), surplusindex.com (404),
Wayback Machine (only captures the Cloudflare challenge page), records.bradfordco.org/PSI (login-gated),
bradford.realforeclose.com (confirmed not a RealAuction client). The 6th session's own explicit recommendation:
"the only remaining lever is human phone/records-request outreach to the Bradford Clerk or the surplus-funds
attorney of record, which is outside this campaign's autonomous scope. Suggest deprioritizing further automated
bradford B/F sessions until that human step happens."

YOUR JOB (deliberately small budget -- this is a reconfirmation, not a 7th full research sweep):
1. Do ONE fresh check of whether ANY of the dead-end sources above have changed state (e.g. bradfordclerk.com no
   longer Cloudflare-blocked, or a new bctelegraph.com issue since 7/30 has a post-sale notice for this case/
   property/parties). Do NOT re-attempt Turnstile/CAPTCHA-gated sources -- that is a hard no per campaign rules.
2. If you find one genuinely NEW, untried, non-CAPTCHA-gated lead (search web for "25000457CAAXMX" OR "Debra Ilene
   Hunter" OR "18737 Charlotte Ave Brooker" combined with "sale" / "certificate of title" / "surplus" -- something
   not already in the exhausted list), spend a small amount of budget on it. If it resolves to a real sold amount /
   status, write it in per the honesty rules below. If not, or if nothing new turns up, do not force it.
3. If still exhausted (the expected, honest outcome given 6 prior sessions): log ONE gold_standard_ultraloop_audit
   row for each of B and F with claim="7th session reconfirms structural block on case 25000457CAAXMX, no new
   public channel found" and survived=true (a correctly-identified, honestly-reported residual IS a valid outcome
   for this campaign, not a failure), and move on -- do not keep grinding on this. Update
   pipeline.counties.notes for bradford (append, do not overwrite) to record this as the 7th confirmed-exhausted
   session so an 8th session can skip straight to "still blocked" without re-deriving the dead-end list, unless a
   human outreach flag has been set.
4. Budget cap: spend no more than ~15-20% of your available time on this item, then stop and return your report
   regardless of outcome.

${RECIPE}`,
  },
  {
    key: 'osceola_g',
    county: 'osceola',
    letters: ['G'],
    prompt: `You are working Gold Standard shard-4, county "osceola", letter G, dispatch ${DISPATCH_ID}, inside the
cli-anything-biddeed repo (already checked out, on main).

Live baseline (VERIFIED this session via pencil_dod_evaluate_county('osceola')): 8/10. G FAIL metric=90.0
[density=97.6 far= pk1000=90.0]. Do NOT touch A/B/C/D/E/F/H/J -- they already pass (osceola is 9/10 if you count I
as a separate failing letter tracked by a different work item in this same shard; do not touch I's rows from this
task, coordinate only through the DB, not files).

ROOT CAUSE (VERIFIED live via v_zoning_gold_standard_kpi_v3's underlying query, direct SQL this session): exactly
ONE zoning_districts row is blocking pk1000 (the binding constraint) from reaching the 95%% threshold --
jurisdiction "Kissimmee", zone_code "SRPUD", zoning_districts.id=13180, currently zoned to 1 osceola parcel via
parcel_zones. Its zone_standards row (id=5515) has parking_per_1000sf = NULL. Every other applicable-district value
in osceola already clears the bar; this single write flips G if pk1000_applicable stays true and you find a real
number (or flips it if you can show pk1000 is genuinely inapplicable to SRPUD, which would need a
v_zoning_district_applicability row -- do NOT just fabricate applicability, verify it against the ordinance).

EXISTING RESEARCH TRAIL (VERIFIED, from zone_standards.ordinance_section / source_url for id=5515, written by a
prior session 2026-07-31): source_url=https://www.zoneomics.com/code/kissimmee-FL/chapter_8,
ordinance_section="Kissimmee LDC Sec. 14-4-8.C (SRPUD) and Sec. 14-4-8.B.4 (RPUD site design standards, incorporated
by reference); density N/A per Sec. 14-4-8.B.4.a.i (max density = 75%% of underlying future-land-use designation,
not a fixed du/acre figure). Parking ratio not found in Sec. 14-4-8 text; leaving null pending citywide
parking-chapter (14-6) lookup." That prior session correctly identified WHERE to look next but ran out of budget
before doing it -- your job is to finish that exact lookup.

YOUR JOB:
1. Find Kissimmee's Land Development Code Chapter 14-6 (or the current citywide parking/off-street-parking chapter
   -- confirm the chapter number is still current, municode/zoneomics numbering can shift) via municode.com
   (library.municode.com/fl/kissimmee) or zoneomics.com or the city's own published LDC PDF. Look for the parking
   ratio table that applies to residential PUD development under SRPUD/RPUD (Sec 14-4-8.B.4 explicitly incorporates
   RPUD site design standards by reference, so the citywide parking chapter's general residential ratio -- likely
   expressed per dwelling unit, e.g. "2 spaces per unit" -- is what actually governs; you will need to convert a
   per-unit ratio to per-1000-sqft using a reasonable typical unit size ONLY IF the ordinance itself expresses it
   that way, or better, check the actual parcel_zones row for this district for its real square footage / unit
   count from the source parcel record to do a real conversion, not an assumed one -- explain your conversion
   method plainly if you do this, tag it INFERRED, and cite the exact ordinance section).
2. If you find a real, citable value: UPDATE zone_standards SET parking_per_1000sf = <value>, source_url =
   '<the real chapter 14-6 URL>', ordinance_section = '<append the new citation to the existing one>', scraped_at =
   now() WHERE id = 5515. Write a migration file documenting the exact ordinance text/section you read.
3. If the parking chapter genuinely does not specify a numeric ratio applicable to SRPUD/RPUD (e.g. it's fully
   discretionary via site plan review with no numeric minimum), that is a legitimate finding -- in that case,
   research whether a v_zoning_district_applicability row should mark pk1000_applicable=false for district 13180
   (i.e., genuinely N/A, not missing data) and write that row with real justification, rather than leaving it as a
   silent gap. Do NOT fabricate a plausible-sounding number.
4. Re-run pencil_dod_evaluate_county('osceola') and confirm G's new value. Log gold_standard_ultraloop_audit.

${RECIPE}`,
  },
  {
    key: 'osceola_i',
    county: 'osceola',
    letters: ['I'],
    prompt: `You are working Gold Standard shard-4, county "osceola", letter I, dispatch ${DISPATCH_ID}, inside the
cli-anything-biddeed repo (already checked out, on main).

Live baseline (VERIFIED this session via pencil_dod_evaluate_county('osceola')): 8/10. I FAIL metric=75.9
[card_complete=104 of 137]. Do NOT touch A/B/C/D/E/F/H/J. G is a separate work item in this same shard (a single
Kissimmee SRPUD zone_standards write) -- do not duplicate that work, coordinate only through the DB.

ROOT CAUSE (VERIFIED this session via a direct LEFT JOIN of multi_county_auctions against
v_zoning_gold_standard_card for county=osceola): the ~33 incomplete rows split into two overlapping gap types --
(a) missing property_address / lat-long / assessed+market value on the raw multi_county_auctions row, and (b) EVERY
one of the ~33 sampled rows has has_zone=false, meaning even rows with a full address/geo/value card still fail I
because their parcel_id has no matching row in parcel_zones (or the parcel_zones zone_code doesn't resolve through
zoning_districts). This matches a well-documented osceola-specific trap from a prior session
(.claude/workflows/gold-standard-shard9-highlands-osceola-255f0be0-v2.js, read it for full method detail): many
osceola tax_deed rows store parcel_id as a TRUNCATED ~12-digit STRAP PREFIX (e.g. "202529183000" is only the
sec-twn-rng-subdivision prefix of the real 18-character Osceola STRAP), so parcel_zones/zoning lookups by that
truncated value will never match -- you must resolve the REAL FULL STRAP per case via case-number-keyed lookup, not
by treating the stored parcel_id as authoritative.

Representative gap rows (VERIFIED live sample this session, up to 40 of ~33 real gap rows -- re-query fresh, this
may have shifted slightly): tax_deed cases with truncated-prefix parcel_ids missing lat/long+value: 1302024
(012630000101), 27092022 (152529324000), 35922022 (192733273000), 40652024 (212632351900), 41922024 (223033000000),
43912024 (242629367000), 48132023 (282529138700), 58662022 (012730495000), 7772024 (042630495000); tax_deed cases
that HAVE lat/long/value already but still lack a zoning link: 1212023, 2132023, 28152023, 29162024, 31152023,
33772024, 3432023, 3452023, 35192022, 38582021, 38742024, 42202021, 47142022, 48482022 (dup parcel with
52562018/53252018 -- same real parcel 262630061300, all 3 cases should resolve identically once you find it once),
53772024, 53942024, 6632024, 77492018, 8642023; foreclosure cases: "2025 CA 001061 MF" (parcel
242528105500010240, has geo/value, needs zoning link only), "2025 CA 002509 MF" (parcel 252628610006000090, has
geo/value, needs zoning link only), "2025 CA 001721 MF" (parcel_id is a synthetic OSC-2CEAE2B1037A placeholder --
NO real address on file at all, needs full research from the case docket, hardest row); several PO-1xxxxxx rows
(PropertyOnion-sourced foreclosure stubs, e.g. PO-1000727/PO-1001391/PO-1002089/PO-1002281/PO-1002403/PO-1002790/
PO-1003718 and likely more beyond the 40-row sample) which have market_value from PropertyOnion but no
address/parcel_id/zoning -- for these, PropertyOnion's address IS usable as a lead to find the REAL parcel via
Osceola's own GIS (never write PropertyOnion's market_value in as if verified-independent, but using its address as
a search input to find the county's own record is fine and is exactly what the litmus-only rule permits).

METHOD (per the 255f0be0-v2 prior-session methodology, reuse it):
1. For tax_deed cases: Osceola tax deed sales run through osceola.realtaxdeed.com and/or the Osceola County Clerk's
   Tax Deed Division (osceolaclerk.org / myclerk.osceola.org) -- search the exact numeric case_number string (try
   format variants like "TD-<n>-<year>" if a literal search fails) to find the case-specific file, which should
   show the FULL STRAP, address, and value directly (a direct case-keyed lookup, not a parcel-id lookup).
2. For "2025 CA 001721 MF": search the Osceola Clerk's civil/foreclosure case search (myclerk.osceola.org) for the
   exact case number to find the real defendant property address from the docket, then resolve the parcel via
   gis.osceola.org's Parcels FeatureServer (https://gis.osceola.org/hosting/rest/services/Parcels/FeatureServer/3/
   query -- confirmed live in the prior session) by address or spatial search.
3. Once you have a real full STRAP for any parcel, cross-check/get lat-lon and assessed value via the same
   gis.osceola.org Parcels FeatureServer (query Strap=eq the full value), and get the zoning code from Osceola
   County's own zoning GIS layer if the parcel is unincorporated, or the relevant municipality's zoning layer/LDC
   if incorporated (Kissimmee, St Cloud) -- verify jurisdiction from the parcel record's own city/muni field, do
   not assume from the mailing address (a documented past mistake in this campaign for a different county).
4. For each parcel where you resolve a real full STRAP + zoning code: write/UPDATE parcel_zones (parcel_id=full
   STRAP, jurisdiction_id, zone_code) and, if you had to fix multi_county_auctions.parcel_id from the truncated
   prefix to the real full STRAP, UPDATE that too (only if you are certain it's the correct match for that specific
   case -- do not guess). If the zone_code's zoning_districts/zone_standards rows don't already exist for that
   jurisdiction, either link to an existing equivalent district or, if genuinely new, create it with real
   ordinance-sourced standards (do not leave it half-created with nulls that would then break G's denominator the
   way a documented seminole regression did -- match code format exactly, e.g. hyphenation, to existing
   zoning_districts.code values for that jurisdiction).
5. Where you cannot resolve a real STRAP/address (expected for some rows, e.g. "2025 CA 001721 MF" may be a
   genuine dead end), leave it and report as residual -- do not fabricate.
6. Budget: this is a 33-row gap, you will not resolve all of them -- prioritize the ones with existing geo/value
   already present (need zoning link only, cheapest fix) and the duplicate-parcel cluster (48482022/52562018/
   53252018 -- one lookup fixes three rows), before spending time on the harder full-research rows.
7. Re-run pencil_dod_evaluate_county('osceola') and report the real before/after I metric. Log
   gold_standard_ultraloop_audit for I with your real row count moved.

${RECIPE}`,
  },
  {
    key: 'nassau_cdi',
    county: 'nassau',
    letters: ['C', 'D', 'I'],
    prompt: `You are working Gold Standard shard-4, county "nassau", letters C/D/I, dispatch ${DISPATCH_ID}, inside
the cli-anything-biddeed repo (already checked out, on main).

Live baseline (VERIFIED this session via pencil_dod_evaluate_county('nassau')): 7/10. C FAIL metric=91.9
(matched_clean=34), D FAIL metric=91.9 (matched_any=34), I FAIL metric=91.9 (card_complete=34 of 37). Passing:
A=6(fc=31 td=6) B=100(verified=11 closed_sold=11) E=100(parcel_linked=37) F=100(tier1_sold=11 closed_sold=11)
G=100(density=100) H=0.0h J=100(deal_complete=37). Do NOT touch A/B/E/F/G/H/J.

ROOT CAUSE (VERIFIED this session via a direct row-level query for nassau: rows where parity_status is not
matched_clean, or parity_source doesn't start with tier1, or property_address/lat-long/value is missing): exactly
3 rows are the shared root cause for C/D/I (34/37 = 91.9%% matches all three letters exactly, confirming one shared
cause, not three independent ones):
  case_number             sale_type    parcel_id                    property_address                              lat/long  assessed_value  market_value  parity_status  data_source
  452025CA000241CAAXYX    foreclosure  26-2N-28-0552-0025-0000      32428 POND PARKE PL, FERNANDINA BEACH FL 32034  NULL/NULL 341709.00       336000.0      NULL           realforeclose
  452025CA000281CAAXYX    foreclosure  37-1N-25-0000-0019-0010      43761 RATLIFF RD, CALLAHAN FL 32011              NULL/NULL 268804.00       336000.0      NULL           realforeclose
  452026XX000003TDAXYX    tax_deed     33-2N-25-0000-0001-0010      55100 HART TER, CALLAHAN FL 32011                NULL/NULL 58547.00        NULL          NULL           NULL

All 3 already have real parcel_id/address/assessed_value from a genuine realforeclose ingest (NOT PropertyOnion
stub rows, unlike some other counties' gap rows in this campaign) -- the gap is (a) parity_status/parity_source
were never set (never run through the tier1 matcher, zero rows in realforeclose_aids for these case numbers as of
this session's check) and (b) latitude/longitude are null (blocks I even once C/D are fixed), and the tax_deed row
additionally lacks market_value (only assessed_value is present).

Nassau's tier1 sources (VERIFIED via pipeline.counties): foreclosure_platform=realforeclose, foreclosure_url=
https://nassauclerk.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR; taxdeed_platform=realtaxdeed,
taxdeed_url=https://nassau.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR.

YOUR JOB:
1. For the 2 foreclosure cases (452025CA000241CAAXYX, 452025CA000281CAAXYX): look them up on
   nassauclerk.realforeclose.com (case-detail view or the FNC=UPDATE diff endpoint, by case number) using a real
   browser session (firecrawl-browser or browser-use skill -- plain curl/WebFetch may be blocked, check first) to
   confirm/refresh the case record and pull a real source_url. If the platform record matches our existing
   address/value (it should, since data_source='realforeclose' already), this is your evidence to populate
   realforeclose_aids (or whatever table public.refresh_parity_tier1_outcomes reads from -- inspect its
   definition via pg_get_functiondef if unsure) with a tier1-sourced row for each case, then call
   public.refresh_parity_tier1_outcomes('nassau') via the SQL endpoint and confirm parity_status/parity_source flip
   to matched_clean/tier1%%.
2. For the tax_deed case (452026XX000003TDAXYX): same approach against nassau.realtaxdeed.com -- also try to find a
   real market_value while there (assessed_value already present; do not fabricate market_value if the source
   doesn't show one, leave it null and report that I may still gate on it if market_value is required alongside
   assessed_value -- check the evaluator's actual I logic to confirm assessed_value OR market_value is sufficient
   before assuming you need both).
3. For all 3 rows: find real latitude/longitude. Nassau County Property Appraiser (ncpafl.com or similar -- verify
   the real domain) or Nassau's ArcGIS parcel layer (search "Nassau County Florida GIS ArcGIS REST") should resolve
   a geocode from the parcel_id (STRAP format 26-2N-28-0552-0025-0000 etc, a standard section-township-range
   format) or address. UPDATE multi_county_auctions with real lat/long once found.
4. Re-run pencil_dod_evaluate_county('nassau') and report the real before/after C/D/I metrics. Log
   gold_standard_ultraloop_audit for each letter you moved.

${RECIPE}`,
  },
  {
    key: 'osceola_g_recovery',
    county: 'osceola',
    letters: ['G'],
    prompt: `You are working Gold Standard shard-4, county "osceola", letter G RECOVERY, dispatch ${DISPATCH_ID},
inside the cli-anything-biddeed repo (already checked out, on main).

CONTEXT -- this is a same-shard, same-session regression you are cleaning up, not a fresh assignment. An earlier
agent in this same dispatch (osceola letter I work item) fixed 21 property-card gaps by resolving real STRAPs and
real zone codes for parcels, and correctly, honestly created 9 NEW zoning_districts rows for codes that didn't
already exist in our substrate -- but deliberately left their zone_standards blank (that was out of its scope,
correctly deferred to you). Effect (VERIFIED live via pencil_dod_evaluate_county('osceola') just now): G dropped
from FAIL 90.0%% (density=97.6 pk1000=90.0) to FAIL 75.9%% (density=75.9 pk1000=78.6) -- still FAIL both before and
after (no pass-to-fail flip of a previously-passing letter), but a real, disclosed, in-shard regression because
these 9 districts now count as "applicable, no standard on file" in v_zoning_gold_standard_kpi_v3's denominator.
This is NOT a hyphenation bug like the seminole precedent -- the districts and their codes are correct, they
simply need real ordinance-sourced standards written in.

The 9 blank districts (VERIFIED live query this session, zoning_districts.id / jurisdiction / code / name):
  13383  St. Cloud        R-1     St Cloud Residential R-1
  13384  St. Cloud        R-2     St Cloud Residential R-2
  13385  Osceola County    RS-3    Residential Single Family
  13386  Osceola County    R-1     Rural R-1
  13387  Kissimmee         RA-2    RA-2 (Single Family Residential)
  13388  Kissimmee         RA-1    RA-1 (Single Family Residential)
  13389  Kissimmee         T4-R    T4-R (Neighborhood Restricted)
  13390  Kissimmee         T5-U    T5-U (Mixed-Use Urban Core)
  13391  Kissimmee         MUPUD   MUPUD (Mixed Use Planned Unit Development)
All 9 are residential/mixed-use districts -- real numeric max_density_du_acre, max_far, and parking_per_1000sf
values should exist in each jurisdiction's published code (St Cloud LDC, Osceola County LDC Ch 3, Kissimmee LDC
Chapter 14-4 for the T-zone/RA codes -- Kissimmee is form-based-code (Sec 14-4) for T4-R/T5-U/MUPUD, so density may
be expressed as "N/A, governed by building form" per Sec 14-4-x -- if so, that is a legitimate real answer, write
a v_zoning_district_applicability row marking density_applicable=false with real ordinance citation rather than
leaving it silently blank; do NOT guess a number for a form-based code that doesn't regulate density numerically).

YOUR JOB:
1. Research each of the 9 districts' real max_density_du_acre, max_far, and parking_per_1000sf (or confirm genuine
   inapplicability with a citation) via municode.com/zoneomics.com/the jurisdiction's own published LDC PDF for
   St Cloud (stcloud.org), Osceola County (osceola.org), and Kissimmee (kissimmee.gov) respectively. NOTE: a
   sibling work item in this same dispatch hit Municode 403 (Akamai) and Firecrawl "insufficient credits" -- check
   both fresh yourself (state may have changed / credits may have been added since), but have a fallback plan
   (zoneomics.com mirrors, direct jurisdiction PDF, WebSearch for the specific numeric standard) ready if those
   dead-end again.
2. For every value you find with a real citation: UPDATE zone_standards (INSERT if a row doesn't exist yet -- these
   9 districts likely have none) with max_density_du_acre / max_far / parking_per_1000sf, source_url,
   ordinance_section, scraped_at=now(). Do NOT touch any other osceola zoning_districts/zone_standards row -- only
   these 9 ids.
3. For anything genuinely inapplicable (not merely unresearched), write a real v_zoning_district_applicability-
   feeding row (check how that view is populated -- likely a base table, inspect via pg_get_viewdef first) with a
   real ordinance citation, not a guess.
4. Where you cannot find a real number after a genuine attempt, leave it null and report as residual -- do not
   fabricate, do not copy a value from a similarly-named district in a different jurisdiction.
5. Re-run pencil_dod_evaluate_county('osceola') and report G's real before/after. Note this session's true "before"
   for G is 75.9%% (the current live value, not the original 90.0%% -- the 90.0 baseline was already spent by the
   time this task started), so report both the original-session-start value (90.0) and the immediate-prior value
   (75.9) for full transparency in your before_json.
6. Log gold_standard_ultraloop_audit for G with claim describing the recovery attempt and real numbers moved.

${RECIPE}`,
  },
]

phase('Diagnose+Fix')
const fixResults = await pipeline(
  WORK_ITEMS,
  (item) => agent(item.prompt, {
    label: `fix:${item.key}`,
    phase: 'Diagnose+Fix',
    isolation: 'worktree',
    schema: {
      type: 'object',
      properties: {
        work_item: { type: 'string' },
        county: { type: 'string' },
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
  (result) => {
    const county = result.county
    const letters = (result.letters_touched && result.letters_touched.length) ? result.letters_touched.join('/') : '(see result)'
    const label = result.work_item || `${county}-${letters}`
    return agent(
    `Independently verify this claimed Gold Standard fix for shard-4 work item "${label}" (county "${county}", letters ${letters}). You did NOT write this fix -- be skeptical.\n\n` +
    `Claimed result: ${JSON.stringify(result)}\n\n` +
    `${RECIPE}\n\n` +
    `Your job: re-run pencil_dod_evaluate_county('${county}') yourself RIGHT NOW (fresh call, do not trust the pasted after_json), ` +
    `compare against the claimed before/after, and check specifically for: (a) denominator mismatches, (b) ghost-success (any letter now ` +
    `passing because of a placeholder/fabricated/default value rather than a real fix -- for osceola_g specifically, spot check the ` +
    `parking_per_1000sf value against the cited ordinance URL/section yourself; for osceola_i, spot-check 2-3 of the claimed STRAP ` +
    `resolutions actually resolve via gis.osceola.org and aren't reused/guessed; for nassau_cdi, verify the tier1 source row genuinely ` +
    `exists and parity_source starts with 'tier1', and that lat/long are real coordinates within Nassau County, not a placeholder; for ` +
    `bradford_bf, if a residual was claimed, confirm no fabricated sold_amount was written), (c) whether any OTHER letter for this county ` +
    `regressed as a side effect (this campaign has a documented precedent of an I-fix accidentally regressing G via a zone_code hyphenation ` +
    `mismatch -- always check the full A-J JSON, not just the targeted letters), (d) for B/C/D specifically the only valid PASS reflects ` +
    `parity_source LIKE 'tier1%%', not just parity_status being set. Also INSERT your own gold_standard_ultraloop_audit row per the RECIPE ` +
    `(ultraloop_mode='fallback'). Return { work_item, county, refuted: boolean, refutation_reason: string|null, fresh_evaluation: <the JSON you just got>, survives: boolean }.`,
      {
        label: `verify:${county}:${letters}`,
        phase: 'Verify',
        schema: {
          type: 'object',
          properties: {
            work_item: { type: 'string' },
            county: { type: 'string' },
            refuted: { type: 'boolean' },
            refutation_reason: { type: ['string', 'null'] },
            fresh_evaluation: {},
            survives: { type: 'boolean' },
          },
          required: ['refuted', 'fresh_evaluation', 'survives'],
        },
      }
    )
  }
)

return { fixResults, verified }
