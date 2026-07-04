# SHARD-10 Session Report (loop run 2820) — sarasota, jackson, flagler, calhoun (2026-07-04)

dispatch_id: 15feed48-11f6-4bff-ba37-5343402442a5
chat_session: architect-20260704T000000

## Summary — no letter flipped this session, honestly reported (BLANK > WRONG)

Every failing letter in this shard's brief was independently re-diagnosed live against
the production Supabase DB (`mocerqjnksmhcjzxrewo`, direct SQL access via the
Management API using `SUPABASE_ACCESS_TOKEN` — RealAuction (`*.realforeclose.com`,
`*.realtaxdeed.com`) is **not reachable from this sandbox's network** — confirmed via
curl and WebFetch, both return HTTP 403, matching the "datacenter IP block" behavior
already documented in `scripts/county_outcome_harvester.py`). All four root causes are
genuine data-collection gaps, not matcher bugs, and each claim survived an independent
adversarial refutation pass (workflow `wf_2ffc70d3-61d`, 7 subagents, logged to
`gold_standard_ultraloop_audit` under this dispatch_id). One piece of real, verified
infrastructure progress shipped: clerk official-records discovery for jackson and
calhoun. No SQL migration was applied — this session made no schema changes.

## Live before/after (`pencil_dod_evaluate_county`, identical — nothing moved)

```
sarasota : A✓75 B✓100.0 C✗81.3 D✗81.3 E✓99.5 F✓100.0 G✓100.0 H✓11.8 I✓98.5 J✓99.0  (8/10)
jackson  : A✓14 B✓100.0 C✗3.2  D✗3.2  E✓95.2 F✓100.0 G✓100.0 H✓2.7  I✓95.2 J✓100.0 (8/10)
flagler  : A✓37 B✗null C✗0.0  D✗0.0  E✓99.3 F✗null  G✓100.0 H✓10.9 I✓97.8 J✓100.0 (6/10)
calhoun  : A✗0  B✗null C✗0.0  D✗0.0  E✓100.0 F✗null G✓100.0 H✓11.9 I✓100.0 J✓100.0 (5/10)
```

**Discrepancy vs the brief, disclosed:** the brief listed sarasota 10/10 and flagler
C=91.0/D=100.0 (PASS). Both are stale. Sarasota's denominator grew from 187→203
auctions since the brief was written (new upcoming auctions added), dropping C/D from
97.3/99.5 to 81.3/81.3 — a real, ongoing "growing denominator" effect, not a bug I
introduced. Flagler's C/D collapsed from 91.0/100.0 to 0.0/0.0 via a bulk update that
touched all 134 flagler rows at `2026-07-04 01:53:53 UTC` — **before this session
started** (I made zero writes to flagler before discovering this). I could not find an
attributing log entry (`gold_standard_ultraloop_audit`, `gha_dispatch_log`,
`gold_standard_decisions`, `ci_analysis_jobs` all empty for that window), but the
result is honest: 0 rows exist in `tax_deed_outcomes`/`foreclosure_outcomes` for
flagler, so 0.0%/0.0% is the correct value. This is consistent with the fabrication
pattern already caught and reverted for flagler B/F on 2026-07-03 10:33 (see
`gold_standard_ultraloop_audit`) — whatever process did this made the data **more**
honest, not less. Flagging per Sentinel-agreement: I did not dismiss this, I traced it
to its logical conclusion (real outcome-table counts) before writing anything.

## Root-cause findings (all CONFIRMED via live SQL, all survived adversarial refutation)

**sarasota C/D (81.3%, FAIL)** — genuine ceiling, not a matcher bug. All 165
currently-terminal auctions (78 completed + 70 redeemed + 17 cancelled) are already
`parity_status='matched_clean'` with a real `tier1_*` source (123 rows from
`tax_deed_outcomes`, 42 from `foreclosure_outcomes` — every outcome row that exists is
already matched, confirmed by re-running `refresh_parity_tier1_outcomes('sarasota')`
live: 0 new matches). The 38-row shortfall (203 total − 165 matched) is entirely
`auction_status='upcoming'` rows, **all 38 already past their `auction_date`**
(stale, range 2025-05-21..2026-07-02) — the status-flip/outcome-scrape pipeline has
stalled on them, not a matching defect. Refuter found this stale-past-due-`upcoming`
pattern is fleet-wide (broward 9,327 / miami_dade 9,162 / sarasota 1,132 such rows
county-wide), which supports rather than undermines the diagnosis. Real fix requires
new outcome data for these 38 cases — i.e. scraping (blocked from this network) or a
clerk-records harvest (see Discovery section below).

**jackson C/D (3.2%, FAIL)** — same shape, smaller scale. Only 2 rows exist in
`foreclosure_outcomes`+`tax_deed_outcomes` for the entire county, both already matched.
The other 61 auctions are `upcoming` with zero independent outcome data; 19 of the 61
are already past their `auction_date` (stale).

**flagler B/F (null, FAIL)** — zero rows in `multi_county_auctions` for flagler have
`sold_amount` populated, including all 30 terminal (23 sold + 7 completed) auctions.
Zero rows exist in either outcome table for flagler. `clerk_harvest_queue` has zero
flagler rows ever queued — outcome harvesting has genuinely never run for this county.
Not a parity/join bug; a real data-collection gap.

**calhoun A (fc=1, td=0, FAIL)** — `pipeline.counties.taxdeed_platform` and
`taxdeed_url` are both `NULL` for calhoun; the tax-deed lane was never configured,
while `foreclosure_platform='realforeclose'` with a working URL is. Total MCA rows for
calhoun = 1 (a single future foreclosure auction, 2026-07-23, still `upcoming`).
`realauction_subdomains` already has a discovered `calhoun.realtaxdeed.com` row
(is_active=true, http_status=200 as of 2026-05-24) — so the **subdomain is known and
was reachable in the past**; this session confirmed it now returns HTTP 403 from this
sandbox (blocked, consistent with the RealAuction network block above). Configuring
`pipeline.counties.taxdeed_platform='realtaxdeed'` / `taxdeed_url` would be a
legitimate, low-risk config fix (playbook item "A: configure BOTH lanes"), but doing so
without a working scrape path behind it would not move the A metric (which counts real
`tax_deed` rows in MCA, not config presence) — deferred rather than done for
appearance's sake.

## Genuine progress shipped this session (verified live, re-checked independently)

Clerk official-records discovery for jackson and calhoun (unlike RealAuction, these
plain county-clerk WordPress sites are reachable from this network) — updated
`public.clerk_official_records_subdomains` honestly:

```sql
SELECT county_slug, base_url, fqdn, search_url, is_active, http_status, honesty_marker
FROM clerk_official_records_subdomains WHERE county_slug IN ('sarasota','jackson','flagler','calhoun');
```
```
calhoun  | https://calhounclerk.com          | calhounclerk.com     | https://www.myfloridacounty.com/orisearch/07 | true  | 200 | VERIFIED
flagler  | null                              | null                 | null                                          | false | null| UNKNOWN  (unchanged — genuinely blocked)
jackson  | https://www.jacksonclerk.com      | www.jacksonclerk.com | https://www.myfloridacounty.com/orisearch/32 | true  | 200 | VERIFIED
sarasota | https://www.sarasotaclerk.com/... | www.sarasotaclerk.com| (unchanged, already VERIFIED 2026-06-11)     | true  | 200 | VERIFIED
```

Both `orisearch` URLs independently re-verified by me (not just trusted from the
subagent) with a fresh `curl` — both return HTTP 200. Flagler's clerk site
(`flaglerclerk.com`) is blocked by a Kasada-backed Cloudflare bot-management layer
(`ki-edge` header, `__cf_bm` cookie) — 403 even with a full browser User-Agent, on
every path tried (`/`, `/official-records`, `/public-search`) and DNS variant
(`.us` doesn't resolve, `.gov` aliases the same blocked host) — left honestly as
`UNKNOWN`, not fabricated. One incidental finding worth flagging for a future scraping
session: `flagler.realtaxdeed.com` returns 403 with a bare curl User-Agent but **200
with a browser User-Agent** (`server: Realforeclose/1b`) — it is UA-gated, not fully
network-blocked, which may matter for GHA-runner-based harvest attempts later.

This discovery work does not itself move any letter (it's infrastructure for a future
harvest step, not outcome data), and is reported as such — not claimed as a B/F/C/D
gain.

## Defect found in shared infrastructure (not touched this session — out of shard scope)

`scripts/county_outcome_harvester.py::fix_parity_status()` (used by the 6-county
`county-outcome-harvest.yml` workflow, which already includes sarasota in its weekly
rotation) sets `parity_status='matched_clean'` for **any** row with a non-null
`parcel_id`, regardless of whether any real outcome record exists — this is a much
weaker signal than the canonical `refresh_parity_tier1_outcomes()` matcher (case/parcel
join against real outcome tables) and would inflate C for `upcoming` (non-terminal)
auctions that happen to have a parcel_id linked, which is exactly the "ghost success"
pattern already reverted for other counties in this campaign (flagler 2026-07-03,
nassau 2026-07-04). Confirmed via live query it has **not** yet corrupted sarasota's
numbers (all 165 `matched_clean` rows trace to real `tier1_*` sources, not the
parcel_id heuristic) — flagging this as a live risk for the next scheduled run of that
workflow (sarasota is due next Monday per its cron), not fixing it here since it's
shared code touching 5 other counties outside this shard's authorization
(hillsborough, palm_beach, broward, orange, volusia).

## Verification protocol

- `gold_standard_ultraloop_audit`: 7 rows inserted under this dispatch_id
  (sarasota C/D, jackson C/D, flagler B/F, calhoun A), all `survived=true` — each claim
  independently re-derived and adversarially refuted by a separate subagent with its
  own live SQL access, `ultraloop_mode='native'`.
- Did not run `gold_standard_loop()` / `gold_standard_certify()` — per parallel-fleet
  rules, other shards were mid-flight (confirmed via fresh `gold_standard_ultraloop_audit`
  rows for osceola/gulf/levy/franklin/nassau at 2026-07-04 00:21–03:30 UTC, unrelated
  counties). Ran `pencil_dod_evaluate_county` per-county only, as instructed.
- No migration files added; no `multi_county_auctions`/`tax_deed_outcomes`/
  `foreclosure_outcomes` rows touched. The only writes this session: 1
  `clerk_official_records_subdomains` UPDATE (calhoun, jackson already updated by the
  discovery subagent, independently re-verified) and 7 `gold_standard_ultraloop_audit`
  INSERTs.

## Residual finding for a future session (not investigated further — flagged only)

Criterion J (`bid_decisions`) shows PASS for all four counties, but `ml_score`
cardinality is suspiciously low for the smaller counties: jackson has only 2 distinct
`ml_score` values across 526 `bid_decisions` rows (0.50 or 0.72), calhoun has 1 distinct
value across 2 rows (0.72). Sarasota looks healthy (59 distinct values across 201 rows,
range 0.10–0.92). This wasn't in scope for this shard's failing letters and J currently
PASSes canon, so no revert was attempted — but the low-cardinality pattern in
jackson/calhoun warrants a dedicated J-audit given this campaign's history of
low-effort/templated data passing structural checks without being genuinely
differentiated per property.

## Next steps for tomorrow's session

1. Sarasota/jackson: the 38 + 19 stale past-due `upcoming` auctions need real outcome
   data. RealAuction scraping is blocked from this sandbox network; try a GHA-runner
   dispatch of the existing `county-outcome-harvest.yml` (sarasota is already a listed
   county) but **first patch or bypass `fix_parity_status()`** (see defect above) or the
   run will fabricate C/D gains via the parcel_id heuristic.
2. Flagler: no clerk site reachable from this network (Kasada-blocked); the
   `flagler.realtaxdeed.com` UA-gating finding may let a GHA runner with a browser UA
   succeed where this session couldn't — worth a real scrape attempt.
3. Calhoun: consider configuring `pipeline.counties.taxdeed_platform='realtaxdeed'`
   /`taxdeed_url` now that the subdomain is confirmed known
   (`realauction_subdomains`), but only alongside an actual scrape/ingestion run —
   config alone won't move A.
4. Jackson/calhoun clerk ORI portals (`myfloridacounty.com/orisearch/32` and `/07`) are
   now VERIFIED and ready for a document-search harvest build (Certificates of Title,
   Lis Pendens) if a future session wants to pursue the clerk-records path for B/F/C/D
   instead of/alongside RealAuction scraping.
