# SHARD-4 2nd pass — washington, highlands, volusia, okaloosa, columbia

dispatch_id: `7b631590-6fdc-4e43-acef-8082c3c778d1`

## Duplicate-dispatch note

This dispatch_id is **identical** to the one already completed and committed in `32914d63`
(`SHARD4_RUN3059_..._SESSION_REPORT.md`). The brief's per-county numbers (e.g. okaloosa "6/10
PASS") reflect that session's **pre-fix snapshot**, not current live state — okaloosa's ghost
rows were already purged (now honestly 1/10). Re-verified all 5 counties live before doing
anything so as not to redo completed work or act on stale numbers.

## Environment correction (matters for future sessions)

The prior session's report claimed no live-scrape capability in this sandbox. That's only true
for **bare curl with no User-Agent** — RealAuction/RealTaxDeed WAFs return 403 to a bare
request but HTTP 200 to a standard desktop User-Agent. `highlands.realtaxdeed.com` and
`volusia.realtaxdeed.com`/`realforeclose.com` are reachable and were used this session.
`columbiaclerk.com` (Cloudflare challenge) and okaloosa's two RealAuction subdomains
(unprovisioned tenant, redirect to the generic realauction.com splash) remain genuinely
blocked — re-confirmed live, no change. `FIRECRAWL_API_KEY` is still absent from this runner.
Direct `psql` still fails (password auth) — Management API (`SUPABASE_ACCESS_TOKEN`) and
PostgREST (`SUPABASE_URL`+`SUPABASE_SERVICE_ROLE_KEY`) both work and were used for all DB I/O.

## highlands — C/D backfilled: 2.1% → 12.5% (still FAIL, real progress)

Before: `{"C":2.1,"D":2.1}` (matched_clean/any=3 of 144)
After: `{"C":12.5,"D":12.5}` (matched_clean/any=18 of 144)

Reused `scripts/shard2_run2450_ajax_realforeclose_harvest.py`'s `harvest_date()` against
`highlands.realtaxdeed.com` for `07/01/2026` (the exact 15-case gap the prior session
identified and logged as a concrete next step). Live calendar returned 19 items; all 15
target case numbers matched exactly. New script:
`scripts/shard4_run3059_2nd_pass_highlands_volusia_cd_parity.py`.

**ULTRALOOP adversarial verify: SURVIVED.** Independent refuter re-harvested the same date
from scratch, independently confirmed all 15 case numbers present, confirmed
`county='highlands'` exact (no contamination), confirmed 0 propertyonion-sourced rows in the
promoted set, confirmed the promoted-row count (15) matches exactly with no duplicates.

Residual 126/144 unmatched rows remain genuinely future-dated (per prior session's finding);
ceiling without further live scraping is unchanged.

## volusia — C/D backfilled: 71.0/71.8% → 76.4/77.2% (still FAIL, real progress; 1 defect found+fixed)

Before: `{"C":71.0,"D":71.8}` (265/268 of 373)
After: `{"C":76.4,"D":77.2}` (285/288 of 373)

Harvested 17 auction dates (5 tax_deed + 12 foreclosure) covering the 21-row gap the prior
session logged. 20 of 21 target cases matched and promoted; 1 (`10172-22`, expected
2026-06-09) genuinely does not appear on that date's live calendar (24 items, checked) —
correctly left unpromoted, not fabricated. One row from the future-dated (`2026-07-06`,
tomorrow relative to this session) `2025 22437 COCI` case was intentionally excluded — it's
labeled `auction_status='concluded'` despite an auction_date that hasn't happened yet, a
data-quality anomaly flagged but not touched (out of this fix's scope).

**ULTRALOOP adversarial verify: found a real defect, fixed it.** The refuter caught that row
`12446-19` (own `auction_date='2026-06-23'`) got stamped with the `2026-06-09` batch's
`parity_source` label — my script's `exact_match_and_promote()` queried all of a county's rows
by case_number with **no auction_date filter**, so a case_number match from a different date's
calendar batch could mislabel a row's provenance (same defect class already documented as a
KNOWN DEFECT in `scripts/shard9_run3059_citrus_manatee_cd_parity.py`, now hit again). The
underlying match itself is real (`12446-19` genuinely exists on the live RealTaxDeed calendar
for `2026-06-23`, independently re-confirmed by the refuter) — only the date label was wrong.
Fixed: corrected the row's `parity_source` to the right date via direct UPDATE, and patched
`exact_match_and_promote()` to accept an `auction_date` parameter and filter the candidate-row
query by it, closing the defect for future reuse. Re-verified the corrected row live.

Both the original refuted claim and the corrected/re-verified claim are logged to
`gold_standard_ultraloop_audit` (`survived=false` then `survived=true`) — nothing was quietly
overwritten.

## washington — MAJOR FINDING: "10/10" is largely ghost-success-inflated, not genuinely passing

The prior session left washington untouched as "10/10, clean." Its `gold_standard_ultraloop_audit`
evidence for letters A/E/G/H/J was **9+ days stale** (>7-day certify-gate window), so this
session refreshed it with 5 independent adversarial refuters. Result:

| Letter | Evaluator says | Refuter verdict | Why |
|---|---|---|---|
| A | PASS (fc=12 td=19) | **SURVIVED** | Genuine — real platform config, real mixed sold/pending activity, no placeholder pattern |
| E | PASS (100%, 31/31 parcel_linked) | **REFUTED** | 26/31 rows `parcel_id='00000000'` (placeholder sentinel), 4/31 fake pseudo-IDs with the same fake prefix, 1/31 literally the string `'Property Appraiser'` (scrape-label garbage, not a parcel ID). 0/31 `bcpao_enriched=true`. The non-null check passes technically; real parcel linkage is ~0%. |
| G | PASS (density=100.0) | **REFUTED** | All 5 `parcel_zones` rows resolve to one district literally named `'Single Family Residential (Shard1 Synthetic)'`, `source_url=NULL`, joined against the same placeholder parcel_ids. Identical 1-synthetic-district pattern found in **20 other counties fleet-wide** (Broward, Calhoun, Columbia, Escambia, Gilchrist, Glades, Hamilton, Lafayette, Lake, Marion, Monroe, Orange, Palm Beach, Pinellas, Sarasota, Seminole, St. Lucie, Sumter, Taylor, Volusia) — systemic seeding artifact, not washington-unique, but real zoning intelligence is missing. |
| H | PASS (0.1h) | **REFUTED (metric untrustworthy, verdict coincidentally right)** | The 0.1h reading comes from a single ghost-heartbeat row (`scraped_at` touched at query-instant, `last_changed_at`/`created_at` frozen 5 weeks, `update_count=0`) while 30/31 rows are 23.7h–2280h stale. The honest signal (`last_seen_at`, uniform across all 31 rows, 19.1h) does genuinely pass the 48h SLA on its own — so today's PASS is correct by luck, not because the logged metric is trustworthy. |
| J | PASS (96.8%, 30/31 deal_complete) | **REFUTED** | Same ghost-success signature as okaloosa's purged rows: 100% of the 30 "complete" rows carry `honesty_marker='INFERRED'`, 19/30 share one identical placeholder resale value ($50,000), and **all 30 rows share an identical `created_at` timestamp** and `pipeline_version='shard1-washington-loop472-j-gen-v1'` — bulk-bootstrapped in one instant, not computed per-property. |

**This is not a washington-only problem** — the refuters flagged the same synthetic-zoning-district
pattern in 20 other counties. It means several counties' G scores and possibly E/J scores fleet-wide
are resting on the same class of placeholder data this campaign has repeatedly purged elsewhere
(gilchrist, charlotte, wakolla, desoto, miami_dade per the prior session's cross-references, now
+washington, +okaloosa already purged).

**Action taken this session:** logged all 5 verdicts (1 survived, 4 refuted) to
`gold_standard_ultraloop_audit` with full refuter evidence — this correctly **blocks** washington
from certifying on stale/fake evidence per the SQL CERTIFY GATE, even though the raw evaluator
still shows 10/10. Did NOT attempt to fix E/G/J's underlying data this session — a real fix needs
(a) a genuine BCPAO-equivalent parcel-appraiser lookup for Washington County to replace the
`00000000` placeholders, (b) a real Chipley/Washington County zoning ordinance scrape to replace
the synthetic district, (c) a real per-property CMA generator run for the 30 bid_decisions rows —
each a bounded but non-trivial build, left as next-session work rather than rushed.

## okaloosa — 1/10, re-confirmed unchanged, still infra-blocked

`{"A":false(0),...,"G":true(100, fleet-wide view artifact)}` — matches the prior session's
post-purge state exactly, no drift. Re-curled both RealAuction subdomains this session with a
proper desktop UA (ruling out the "bare curl 403" false negative that affected the highlands/
volusia read): both still 302-redirect to the generic realauction.com marketing splash
(unprovisioned tenant). No new capability, not re-touched.

## columbia — 1/10, re-confirmed unchanged, still infra-blocked

`{"A":false(0 td, 9 fc already linked),...}` — unchanged. `columbiaclerk.com` still returns
HTTP 403 (Cloudflare challenge) even with a proper desktop UA. No `FIRECRAWL_API_KEY` available
to route around it. Not re-attempted with the same tool set a 5th time.

## Cross-shard / fleet-wide finding (NOT acted on — outside this shard's scope)

The washington G refuter's synthetic-zoning-district finding spans 20 counties outside this
shard (listed above). Flagging for the owning architect/session — this is the same class of
gold-standard-inflating placeholder data as the ghost-success rows already purged in okaloosa,
gilchrist, charlotte, wakulla, desoto, miami_dade, and now washington's E/G/J.

The fleet-wide `auction_status='upcoming' AND auction_date < CURRENT_DATE` staleness bug
(76,758 rows across 15+ counties including volusia=2,631) was also noticed while checking
highlands' "why is a 4-days-past auction still upcoming" question. Not fixed — shared status-
transition logic (cron jobs 102 `daily_status_reconcile_all`, 313 `platform-status-hourly`),
way outside this shard's 5-county scope, flagged only.

## Verification evidence

- `gold_standard_ultraloop_audit`: 17 new rows this session, `dispatch_id='7b631590-...'`,
  `ultraloop_mode='native'` — highlands C/D (2 rows, survived=true), volusia C/D (6 rows: 2
  survived=true corrected claims + 2 survived=false original-defect claims, x2 for C and D),
  washington A/E/G/H/J (5 rows: 1 survived=true, 4 survived=false).
- Before/after `pencil_dod_evaluate_county` JSON pasted above for highlands and volusia.
- Both fix promotions applied live via PostgREST (`SUPABASE_SERVICE_ROLE_KEY`), re-verified via
  the Management API afterward.
- Confirmed via live query: only `county IN ('highlands','volusia')` rows carry this session's
  `parity_source` label — no cross-shard writes.
- Did not run `public.gold_standard_loop()` or `gold_standard_certify()` — per PARALLEL-FLEET
  RULES (other shards may be mid-flight).
- No cron jobs 109/111/115 or scoring jobs touched.

## Deviation log

- Did not blindly re-execute the brief's stated per-county numbers (stale snapshot from before
  the already-completed prior session) — verified live state first, found the brief describes
  a state that no longer exists (okaloosa in particular).
- Planned only a mechanical re-check of highlands/volusia; deviated to shipping a real, bounded
  C/D backfill once live-scrape reachability was confirmed (contradicting the prior session's
  blanket "no capability" note) — this was the two counties' single largest-leverage action
  available and matched their own logged next-steps exactly.
- The volusia backfill script had a genuine defect (date-mismatched provenance label on 1 of 20
  promoted rows) — caught by the ULTRALOOP refuter, fixed live, and the script itself patched so
  it doesn't recur on reuse.
- Did not attempt to fix washington's E/G/J ghost-success findings this session — scoped as a
  separate, non-trivial build (real parcel appraiser lookup + real zoning scrape + real CMA
  generation), logged for the next session rather than rushed or faked.
- Did not touch okaloosa/columbia (confirmed still infra-blocked) or the cross-shard 20-county
  synthetic-zoning and fleet-wide stale-status findings (outside this shard's 5-county scope).
