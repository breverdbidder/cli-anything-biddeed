export const meta = {
  name: 'gold-standard-shard1-run6148',
  description: 'Gold Standard shard-1 (franklin/lee/seminole/columbia, loop run 6148): franklin audit-refresh, lee E/I clerk-block workaround, seminole C/D/I new-row enrichment, columbia parcel_id persistence repair, adversarially verify',
  phases: [
    { title: 'Diagnose+Fix', detail: 'one agent per county, worktree-isolated' },
    { title: 'Verify', detail: 'independent refuter per county claim' },
  ],
}

const DISPATCH_ID = 'ecb6f64b-26ab-4147-86a9-8b5baedd69cc'

const COUNTIES = [
  {
    slug: 'franklin',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now, matches the brief exactly):
10/10 -- ALL LETTERS PASS. A=4(fc=4 td=5), B=100.0(verified=4 closed_sold=4), C=100.0(9 of 9), D=100.0(9 of 9),
E=100.0(9 of 9), F=100.0(4 of 4), G=100.0(density=100 far=100), H=0.2h, I=100.0(9 of 9), J=100.0(9 of 9).
auctions_total=9.

YOUR JOB IS NOT TO "FIX" ANYTHING -- there is nothing failing. VERIFIED live via a direct gold_standard_ultraloop_audit
query just now: franklin HAS fresh (within 7 days) audit rows for A, B, C, D, E, F, H. It is MISSING fresh rows for
G, I, J -- that gap is your entire deliverable.

PRIOR CONTEXT on what G/I/J currently rest on (from a research pass just completed, read the referenced session
log/commits yourself before writing anything -- do not just trust this summary):
- I rests on 9 parcel_zones rows keyed by exact multi_county_auctions.parcel_id string match, with zone codes
  INFERRED from Franklin's real 22-code official zone list crosswalked via each parcel's already-scraped
  property_type -- NOT independently verified against a live per-parcel authority (every live source tried at the
  time timed out or 403/500'd: FL GIO ArcGIS, fl_parcels cache mislabeled Citrus data, qpublic 403, gis.arpc.org
  500). Plus one Nominatim-geocoded lat/lon patch (case 2025-CC-000015). See
  .claude/session-logs/2026-07-10-franklin-letter-i-zoning.yml for the full derivation.
- G was passing 20% (1-2 of the zone_standards rows populated) as of that same 2026-07-10 session, but is now
  100% live -- it was evidently fixed by a LATER session not captured in the commits reviewed (65bbd042, 14e4701b,
  a827e14b, 77143d3f, 05867de6, 690c26fb do not mention touching G directly). Find which commit actually landed
  the G fix (search git log/blame on zone_standards rows for franklin's 9-10 parcel_zones) so you can cite real
  evidence in your audit row rather than just re-asserting the live number.
- J has no dedicated franklin commit in the reviewed set; it appears to ride the same bid_decisions/deal-generator
  pattern used fleet-wide, stable and untouched.
- B/F were fixed for real in 690c26fb (2026-07-20) via real recorded tax-deed instruments (OR Book 1449),
  independent of the frozen franklinclerk.com feed, and 65bbd042 (2026-07-24, today) re-confirmed byte-identical
  10/10 with zero drift as the 7th consecutive independent check -- so this county has a strong track record of
  holding; treat any surprise regression on G/I/J as a real signal, not noise.

Your job, in priority order: (1) re-verify each of the 10 letters fresh against pencil_dod_evaluate_county (paste
the literal JSON), (2) for G, I, J specifically: find and cite the real evidence each currently rests on (the
actual zone_standards/parcel_zones/bid_decisions rows, not just the aggregate %), do a short adversarial sanity
check (is I's INFERRED zone-crosswalk still the best available, or has a live per-parcel source appeared since
2026-07-10 worth trying once cheaply? spot-check 2-3 of the 9 parcel_zones rows are real, non-placeholder; for J,
confirm bid_decisions rows have real arv/max_bid/ml_score, not zeros), (3) INSERT one gold_standard_ultraloop_audit
row for G, I, J (mandatory) with survived=true and real refuter_evidence, unless you find a genuine live problem --
in which case fix it for real (small, surgical) before logging, or log survived=false with the honest reason if it
can't be fixed this pass. Optionally add fresh confirmation rows for A-F/H too if time allows, but G/I/J are the
actual deliverable. Do not spend more than a small fraction of a normal session's budget here -- this county is in
maintenance mode.`,
  },
  {
    slug: 'lee',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now, matches the brief exactly): 8/10.
Failing: E=88.2(parcel_linked=283 of 321), I=83.5(card_complete=268 of 321). Passing: A=40(fc=281 td=40),
B=100.0(verified=20 closed_sold=20), C=99.1(318 of 321), D=99.1(318 of 321), F=100.0(20 of 20), G=100.0, H=0.1h,
J=99.1(318 of 321). auctions_total=321.

VERIFIED live via a direct gold_standard_ultraloop_audit query just now: lee has fresh (within 7 days) audit rows
for C, D, E, G, I, J (E and I rows are dated 2026-07-23 -- a session THREE DAYS AGO already investigated these
same two failing letters and logged them as verified real residuals, not false passes -- read that work before
repeating it). It is MISSING fresh rows for A, B, F, H (all currently passing but unaudited) -- backfilling those
4 is real, low-cost work you should do regardless of what happens with E/I.

THE EXACT E/I GAP, FULLY SIZED (from a research pass just completed against the 2026-07-23 audit row and
scripts/gold_standard_shard12_lee_ei_backfill.py -- read that script and the audit row yourself, do not re-derive
from scratch):
- E: 38 unlinked rows (283 of 321 linked). Composition as of 3 days ago: 34 case-number-only rows blocked by Lee
  Clerk 403/Akamai WAF protection AND Firecrawl at zero credits (both confirmed blocked that session), plus 4
  genuinely ambiguous/non-matching ArcGIS SITEADDR rows correctly left unresolved (BLANK > WRONG). 3 new auction
  rows have arrived since (321 vs 318 three days ago) -- re-baseline live, do not assume the exact same 38 rows.
- I: NOT purely gated on E. Two independent mechanisms per the backfill script: (a) rows lacking parcel_id entirely
  (subset of the E gap, since card-complete requires parcel_id), and (b) rows that already HAVE real parcel_id +
  address/geo/value but lack a parcel_zones join for a known zone code (a zone-link gap, separate from E). The
  2026-07-23 session moved I from 247->270 (of 318 then) via live ArcGIS STRAP->ZONING lookups with a
  known-zone-code guard to avoid regressing G. Some rows were left as skipped_unmatched (zoning code with no
  zoning_districts precedent yet) -- exact count not logged, check the script's skip log if it exists.
- UNTRIED AVENUE (this is your one new lever, worth exactly one real attempt): the 34 Clerk-blocked E rows have
  only been tried against the Lee Clerk site directly (403/Akamai) and Firecrawl (zero credits, re-verify
  live before assuming still zero). NOT yet tried: pulling the case detail from lee.realforeclose.com or
  leeclerk.org's RealTaxDeed-equivalent case-detail page instead of the Clerk's own site -- RealAuction case pages
  often surface the property address directly (same pattern used successfully for martin in shard-1 run5361).
  Try this once for a sample of the 34 rows; if it works, batch it; if it doesn't, report the block honestly and
  move on -- do not re-hit the same 403'd Clerk endpoint expecting a different result.
- FRAGILITY WARNING (VERIFIED from commit d416248d "restore lee C/D after incidental live sweep grew denominator"):
  lee's auctions_total grows from routine calendar sweeps, silently diluting E/I/C/D percentages even with zero
  new failures. Re-baseline auctions_total live before diagnosing; do not assume last session's row set is current.

Your job: (1) backfill the 4 missing fresh audit rows for A, B, F, H (quick, real sanity checks, not rubber
stamps), (2) attempt the untried RealAuction/RealTaxDeed case-detail avenue for a sample of the 34 Clerk-blocked E
rows, batch it if it works, (3) if E rows resolve, check whether the corresponding I rows follow for free per the
I<=E dependency, (4) re-run the ArcGIS STRAP->ZONING lookup for any newly-parcel-linked rows still missing a zone
join, (5) log fresh gold_standard_ultraloop_audit rows for whatever you touch (mandatory for E and I regardless of
outcome). Do not fabricate parcel_id/address for genuinely unresolvable rows -- partial progress (some of 38/34
rows) is real progress, report exactly which.`,
  },
  {
    slug: 'seminole',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now, matches the brief exactly): 7/10.
Failing: C=94.6(matched_clean=105 of 111), D=94.6(matched_any=105 of 111), I=90.1(card_complete=100 of 111).
Passing: A=12(fc=99 td=12), B=100.0(verified=63 closed_sold=63), E=100.0(111 of 111), F=96.8(61 of 63),
G=97.1(density=97.1), H=0.1h, J=96.4(107 of 111). auctions_total=111.

VERIFIED live via a direct gold_standard_ultraloop_audit query just now: seminole HAS fresh (within 7 days, dated
2026-07-18) audit rows for ALL 10 letters -- the audit-freshness gate is technically satisfied, but a research pass
just completed found the underlying claims are STALE relative to the current live numbers (see below), so treat
this as needing real re-work, then a real re-log, not a rubber-stamp refresh.

ROOT CAUSE, FULLY DIAGNOSED (VERIFIED from the 2026-07-18 gold_standard_ultraloop_audit rows -- read them yourself,
POST https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query body {"query": "SELECT letter, claim,
survived, refuter_evidence, created_at FROM public.gold_standard_ultraloop_audit WHERE county_slug='seminole' ORDER
BY created_at DESC LIMIT 15;"} with Authorization: Bearer $SUPABASE_ACCESS_TOKEN):
- C/D are NOT a PropertyOnion-coverage problem (unlike the pattern flagged elsewhere in this campaign for
  brevard/duval) -- root cause both times has been RealForeclose/RealTaxDeed AJAX calendar coverage gaps on
  FRESHLY-ADDED auction rows. The 2026-07-18 session raised C/D from 94.3%->100% (105/105) by AJAX-harvesting 6
  unmatched rows against the live calendar -- survived=true, the DATA fix was real. But that session's
  commit/migration claim was ITSELF FABRICATED: the audit row's refuter flagged an invalid-length commit SHA not
  found on origin/main and a migration file that does not exist in the repo -- the fix was applied via a live
  PATCH only, never persisted to git. auctions_total has since grown 105->111 (6 new rows arrived unmatched, same
  failure shape, not a reversion of the old fix). YOU MUST: (a) redo the same AJAX-harvest method for the ~6 new
  unmatched rows, (b) THIS TIME actually write and commit a real migration file (or if you patch live via REST/
  Management API, still write the migration file to the repo per the RECIPE's rule -- the missing-commit gap is
  the specific honesty defect to close), verify the git commit SHA you cite actually exists on origin/main before
  claiming it.
- I: last firing raised 91.4%->97.1% (96->102 of 105) by pulling Property Record Card PDFs from
  parceldetails.scpafl.org/ParcelPdf.ashx (bypassing 3 previously-blocked GIS endpoints) and cross-verifying zone
  codes against Tax District rather than postal address (address was misleading for 3/6 parcels). survived=true,
  fully verified at the time. Remaining gap THEN was 3 rows, two with null parcel_id and one with a literal
  placeholder harvested as "parcel_id" (values like "MULTIPLE PARCELS" / "ALCOHOLIC LICENSE" / "Property
  Appraiser" -- genuinely not real property records, correctly left unresolved). Current live gap is 11 of 111 --
  the denominator grew from 105->111 same as C/D, so INFERRED (not yet confirmed) the additional ~8 rows are new,
  not-yet-enriched cases needing the same PRC-PDF/tax-district treatment, not the old 3 genuinely-blocked ones
  resurfacing. Re-baseline live and confirm which before assuming.

Your job: (1) re-baseline live -- identify the specific new rows behind the 105->111 (C/D) and 102->111-ish (I,
accounting for the 3 already-known-blocked) denominator growth, (2) redo the AJAX-calendar-harvest for the new
unmatched C/D rows, (3) redo the PRC-PDF/tax-district pull for the new I rows, (4) this time COMMIT a real
migration file and verify the commit SHA exists on origin/main before citing it in your audit row -- do not repeat
the fabricated-commit defect from 2026-07-18, (5) log fresh gold_standard_ultraloop_audit rows for C, D, I with
real evidence tying back to this session's actual git history. Leave the 3 genuinely-placeholder-parcel_id rows
from the prior firing alone -- they are a correctly-identified residual, not a bug to re-chase.`,
  },
  {
    slug: 'columbia',
    context: `Baseline (VERIFIED live via pencil_dod_evaluate_county just now, matches the brief exactly): 5/10.
Failing: A=0(fc=15 td=0), B=null(verified=0 closed_sold=0), E=93.3(parcel_linked=14 of 15), F=null(tier1_sold=0
closed_sold=0), I=80.0(card_complete=12 of 15). Passing: C=100.0(15 of 15), D=100.0(15 of 15), G=100.0, H=0.2h,
J=100.0(15 of 15). auctions_total=15.

VERIFIED live via a direct gold_standard_ultraloop_audit query just now: columbia HAS fresh (within 7 days, dated
2026-07-19) audit rows for A, B, E, F, I -- all five FAILING letters are already documented as investigated
residuals (survived=true meaning "verified as correctly-blocked/regressed-with-known-cause", not a false pass). It
is MISSING fresh rows for C, D, G, H, J (all currently passing but unaudited) -- backfill those 5 regardless.

A/B/F ROOT CAUSE (VERIFIED, 3rd firing commit b3f2eca6, 2026-07-19 19:40 -- exhausted, do not re-litigate without a
genuinely new avenue): civitekflorida.com Case/Person Search requires solving a live Cloudflare Turnstile CAPTCHA
before any query executes (screenshot-confirmed); myfloridacounty.com ORI is the same family; columbiaclerk.com is
now site-wide 403 (cf-mitigated:challenge); the dixie-style tax-deed-site fallback does not apply (columbia is
100% foreclosure, no tax-deed lane); search.ccpafl.com was tried and is inconclusive (appraiser-roll lag, not a
disposition source). An earlier session's "Playwright not installed" excuse was independently disproven (Playwright
1.61.0 was present and could load the OCRS page) but the CAPTCHA itself still blocks the flow regardless of
tooling -- this is a genuine, tooling-independent block. The only remaining untried lever is a CAPTCHA-solving
service, which is NOT pre-authorized (ARM-2's $50/mo budget is scoped to retail-comps APIs for criterion J, not
CAPTCHA solving) -- do NOT purchase or wire one without asking; just re-confirm the block is still live (one
cheap check) and log it honestly.

E/I -- THIS IS A REAL, FIXABLE REGRESSION, NOT A NEW BLOCK (VERIFIED via direct row query + migration file just
now -- this is your primary deliverable): case 2025-249-CA and case 2025-63-CA were both targeted by migration
20260719_shard2_columbia_ei_gis_zone_and_parcel_fix.sql (2026-07-19 16:42), which CLAIMED to write
parcel_id='28-1S-17-04576-002' for 2025-249-CA and to disambiguate 2025-63-CA's malformed dual value
("00130-000 AND 00130-001") down to the real single parcel 00130-000. Neither write is live right now:
2025-249-CA's parcel_id is currently NULL, and 2025-63-CA's parcel_id is still the malformed dual string. The
separately-run assessed_value/market_value backfill (commit 05dec1ff, same day) DID persist correctly (38120/
108541 for 2025-249-CA, 32966/446650 for 2025-63-CA are live right now) -- so this is specifically a parcel_id
write that silently failed or was overwritten by migration ordering, not a broader data problem. Fixing these two
parcel_id values for real (verify the write actually commits, re-query immediately after to confirm, don't just
trust the UPDATE returning success) should flip E back to 100% (15 of 15) and move I from 80%->93.3%+ since the
assessed/market values are already in place and parcel_id was the last missing card field for both rows. The third
gap row, 2025-2196-CC (Fort White), is a genuinely, separately blocked residual (VERIFIED: 0 zoning/parcel features
across 3 different GIS layers, query mechanism validated against a known-good neighbor parcel, no Fort White-
specific data source exists) -- leave it alone, it is correctly unresolved, not a bug.

Your job, in priority order: (1) re-apply the parcel_id writes for 2025-249-CA (28-1S-17-04576-002) and 2025-63-CA
(disambiguate to 00130-000, confirm 00130-001 really doesn't exist as a separate parcel before dropping it) via a
direct REST PATCH or Management API UPDATE, and IMMEDIATELY re-query to confirm the value actually persisted before
claiming success -- this is the exact honesty gap that caused the regression, do not repeat it, (2) re-run
pencil_dod_evaluate_county to confirm E and I actually moved, (3) do a cheap live re-check that the Cloudflare
Turnstile block on A/B/F is still real (one attempt, not a full re-investigation) and log it honestly if still
blocked, (4) backfill the 5 missing fresh audit rows for C, D, G, H, J, (5) log fresh gold_standard_ultraloop_audit
rows for E, I (and A/B/F if you did the recheck) with real before/after evidence. Write a migration file for this
fix and, unlike 2026-07-19, verify the exact commit SHA you cite exists on origin/main before claiming it in your
report.`,
  },
]

const RECIPE = `
Environment (already available, do not ask for credentials):
- REST API reads/writes: GET/PATCH \${SUPABASE_URL}/rest/v1/<table>?... with headers
  apikey: $SUPABASE_SERVICE_ROLE_KEY, Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY
  (pipeline.counties is in the "pipeline" schema, not exposed via the default REST root -- use the Management API
  SQL endpoint below to query it, or add Accept-Profile: pipeline / Content-Profile: pipeline headers if the REST
  root has PostgREST schema exposure configured for it; verify which works live rather than assuming.)
- Live arbitrary SQL (verified working this session): POST
  https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query
  headers Authorization: Bearer $SUPABASE_ACCESS_TOKEN, Content-Type: application/json
  body {"query": "<sql>"} -- run "SET statement_timeout = 0;" first in the same query string for anything heavy.
  Build this JSON with a real JSON encoder (e.g. python3 -c "import json; ..." writing to a temp file, then curl
  --data-binary @file) rather than hand-quoting shell strings -- nested quotes in SQL break naive shell quoting.
  Direct psql/psycopg2 pooler connections FAIL (password auth failed against both
  aws-0-us-west-2.pooler.supabase.com and db.mocerqjnksmhcjzxrewo.supabase.co, reconfirmed repeatedly) -- do not
  waste time on that path, use the Management API / REST above exclusively.
  CRITICAL LESSON FROM THIS SHARD'S RESEARCH: an UPDATE/migration that "returns success" is NOT proof it persisted
  -- seminole's 2026-07-18 commit-SHA claim and columbia's 2025-249-CA parcel_id write both looked complete at the
  time but did not survive (fabricated commit / silently-lost write). ALWAYS re-query the exact row/commit
  immediately after writing, with a fresh SELECT or git show, before claiming success anywhere in your report.
- pencil_dod_evaluate_county RPC: POST \${SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county
  headers apikey/Authorization as above, body {"p_county": "<slug>"} -- this is your before/after proof. The
  live function definition computes every letter from multi_county_auctions filtered to lower(county)=<slug> AND
  (data_source <> 'propertyonion' OR tier1_authoritative=true) -- PropertyOnion-sourced rows are excluded from the
  denominator entirely unless explicitly marked tier1_authoritative. C/D specifically require parity_source LIKE
  'tier1%%' in addition to parity_status. B only passes in the 95-105%% band, not just >=95%%. G =
  LEAST(density,far,pk1000) computed from v_zoning_gold_standard_kpi_v3, gated by v_zoning_district_applicability.
- gh CLI is authenticated (repo, workflow scopes) for git operations. Repo root is the current working directory.
  Schema changes MUST go through a migration file under supabase/migrations/<date>_shard1_<county>_<purpose>.sql,
  committed to git -- even when you patch live via the Management API, still write and commit the migration file
  for the historical record, and VERIFY the commit landed (git log / gh api on origin/main) before citing a SHA.
  Simple data backfills (UPDATE/PATCH on existing columns, no schema change) don't need a migration file -- just
  do the REST PATCH or Management API UPDATE and note the exact SQL/endpoint used, and re-query to confirm.

ULTRALOOP audit logging (mandatory per campaign protocol): for every letter you claim moved (or claim you
verified as correctly-passing/correctly-blocked/residual), INSERT one row into public.gold_standard_ultraloop_audit:
  columns: dispatch_id (uuid '${DISPATCH_ID}'), ultraloop_mode ('fallback' -- this session used manual Task
  subagent fan-out via the Workflow tool, not native /effort ultracode), county_slug, letter, claim (short text of
  what you claim), refuter_evidence (jsonb -- for the FIX agent, put your own before/after evidence; for the VERIFY
  agent, put your refutation attempt and what you found), survived (boolean -- true only if the claim held up
  under adversarial check). Use the REST endpoint: POST \${SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit with
  the service-role headers above. Do this as part of your normal work, not as an afterthought.

Hard rules (from the campaign brief -- follow exactly):
- You own ONLY your assigned county. Never touch another shard's counties, their rows, or their county-specific
  files (this dispatch is franklin/lee/seminole/columbia ONLY -- other shards run in parallel today on different
  counties, e.g. gadsden, highlands, st_lucie, okaloosa, suwannee, osceola, santa_rosa -- do not touch those).
- PropertyOnion is litmus/comparison ONLY -- never write po_* derived values in as if they were verified/independent.
- Fail-loud invariant: if a fix attempt finds zero real data, report it as a blocked/residual gap. NEVER fabricate
  case numbers, parcel IDs, sale amounts, coordinates, ordinance values, or timestamps to make a metric look
  better. This project has a documented history of exactly this failure mode (gulf B/F fabrication, purged;
  seminole's 2026-07-18 fabricated commit SHA is a milder version of the same defect) -- do not repeat it in any
  form, including "close enough" placeholder values, INFERRED citations standing in for real ones, or claiming a
  write persisted without re-querying to confirm.
- Every claim you return must be tagged VERIFIED (you ran the query/request and are pasting real output), UNTESTED,
  or INFERRED (say why).
- Before finishing: call pencil_dod_evaluate_county for your county and paste the FULL before (already given
  above, or re-verify fresh if you suspect drift) and after JSON. If a letter did not move, say so plainly.
- git commit any file you create/modify with a clear message, county-scoped, and 'git pull --rebase origin main'
  before pushing (other shards may be pushing concurrently to shared paths -- you are isolated in a worktree so
  conflicts should be rare, but rebase defensively anyway). Push directly to main -- no branches, no PRs. Verify
  your commit SHA actually exists on origin/main after pushing before citing it anywhere.
- Do NOT run public.gold_standard_loop() or gold_standard_certify() -- other shards may be mid-session. Do NOT
  modify cron jobs 109, 111, 115, or any gold-standard-loop-* scoring job.
- Budget yourself: this is ONE bounded pass, not a 6-hour campaign in itself. If a true fix requires building a
  brand-new scraper from scratch, do NOT build it in this pass -- size the gap precisely, report it as a
  scoped-out residual, and ship whatever smaller, real, verifiable improvement IS achievable via SQL/REST/live
  lookups alone (data backfill, wiring an existing-but-unrun pipeline, honesty corrections, persistence repairs).

Return a structured report: { county, letters_touched: [...], fix_summary, sql_or_endpoints_used: [...],
before_json, after_json, residual_gaps: [...], honesty_notes: [...] }.
`

phase('Diagnose+Fix')
const fixResults = await pipeline(
  COUNTIES,
  (county) => agent(
    `You are working Gold Standard shard-1, county "${county.slug}", inside the cli-anything-biddeed repo (already checked out, on main).\n\n${county.context}\n\n${RECIPE}`,
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
    `compare against the claimed before/after, and check specifically for: (a) denominator mismatches (does ` +
    `"auctions_total" / "closed_sold" match what you independently query?), (b) ghost-success (any letter now ` +
    `passing because of a placeholder/fabricated value rather than a real fix), (c) whether any claimed git commit ` +
    `ACTUALLY EXISTS on origin/main (this shard's own research found a fabricated commit SHA and a silently-lost ` +
    `parcel_id write in prior sessions for these exact counties -- run 'git log origin/main --oneline | grep <sha>' ` +
    `or gh api equivalent, and re-query the specific rows claimed as fixed, don't just trust the after_json), (d) ` +
    `whether any OTHER letter for this county regressed as a side effect, (e) for B specifically, the only valid ` +
    `pass band is 95-105%% -- flag anything outside that even if the raw pass/fail bit says true. ` +
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
