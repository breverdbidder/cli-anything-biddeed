# Gold Standard shard-6 broward — dispatch 3bb96d0d, loop run 7519, 3rd firing

## Summary

This is the third firing of dispatch `3bb96d0d` (chat_session `architect-20260730T160000`). The
brief again claimed broward G FAIL (0.0) and I FAIL (91.2) — the same stale snapshot the 2nd
firing (commit `3c302a06`) already found superseded. Live re-check confirms **broward is still
10/10 PASS**, unchanged since the 2nd firing closed at 2026-07-30T17:52Z. Per ULTRALOOP PROTOCOL,
ran a fresh audit + independent adversarial-refute workflow (not a self-check) on G and I
specifically — both **survive refutation**, zero regression, zero ghost-success.

Beyond re-verification, this firing produced one real, shippable fix: `pipeline.counties` for
broward still routed to `broward.deedauction.net` (confirmed permanently shut down — see below),
a metadata staleness the 2nd firing flagged as a P0 finding but did not act on. Corrected it to the
verified live successor platform. No auction data was fabricated or backfilled; the successor
platform's calendar is genuinely empty (real zero, not a block).

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were **not run** —
10 other CC Runner sessions were confirmed `in_progress` via `gh run list --status in_progress`
at the time of this check, i.e. the fleet is actively mid-flight.

## What happened, in order

1. Live-queried `pencil_dod_evaluate_county('broward')` directly (mgmt_sql.py) — confirmed 10/10
   PASS, identical to the 2nd firing's closing numbers. Brief's G/I FAIL figures remain stale.
2. Checked `gold_standard_certifications`: still `certified=false`, `consecutive_gold=0`,
   unchanged since the 2nd firing. Confirmed via `gh run list --status in_progress` that 9–10
   CC Runner GHA-only sessions are actively running right now — the fleet is mid-flight, so per
   PARALLEL-FLEET RULES this firing does **not** run `gold_standard_loop()`/`certify()`.
3. Launched a Workflow (ULTRALOOP audit+verify pattern): one auditor agent per targeted letter
   (G, I), each independently re-deriving the metric from live tables (not trusting the evaluator
   alone), followed by a blind adversarial refuter per claim whose only job was to try to break it.
   Both **survived** — see Verification Evidence.
4. In parallel, independently investigated criterion A's flagged P0 finding from the 2nd firing
   (broward tax-deed lane permanently dead). Confirmed live: `broward.deedauction.net
   /auctions/upcoming` still returns `recordsTotal=0` with the same shutdown banner. Fetched
   `broward.org/recordstaxestreasury` — confirms the county's own successor platform:
   `broward.realtaxdeed.com` (RealAuction), transitioned 2026-07-06, first auction scheduled
   2026-10-26, files "expected to become available for viewing in August [2026]". Live-checked
   `broward.realtaxdeed.com`: HTTP 200, now has a "Taxdeed" jump-to entry (absent as of the
   2026-07-20 investigation baked into this repo's `gold_standard_shard9_broward_deedauction_harvest.py`
   docstring) but zero CALBOX auction cells — a genuine, honest zero (nothing to harvest yet),
   not a block.
5. Checked `public.realauction_subdomains`: broward already has a correct, active row for
   `sale_type=tax_deed, platform=realtaxdeed, is_active=true` (last_verified 2026-05-24) — the
   actual `scrape-realauction-county.yml` dispatch path reads this registry, not
   `pipeline.counties`. So the stale `pipeline.counties.taxdeed_platform='deedauction'` was
   metadata drift only, not an active pipeline blocker — but it would mislead the next session
   into re-attempting a dead-domain scrape, which is exactly what happened across the 2026-06-26,
   2026-07-03, and 2026-07-20 sessions referenced in that table's own `notes` column history.
6. Shipped `supabase/migrations/20260730e_gold_standard_shard6_broward_taxdeed_platform_correction.sql`
   live: updated `pipeline.counties.taxdeed_platform`/`taxdeed_url` for broward from the dead
   `deedauction` URL to the verified live `broward.realtaxdeed.com` calendar endpoint, with a
   dated note. Applied via `mgmt_sql.py` against the live project, verified by re-select.
7. Re-ran `pencil_dod_evaluate_county('broward')` after the migration — still 10/10, unaffected
   (criterion A has no freshness component today and the metadata fix doesn't touch scored rows).

## Real findings (flagged, not silently fixed)

1. **Broward's new tax-deed platform (`broward.realtaxdeed.com`) has no listings yet.** First
   auction is scheduled 2026-10-26; files "expected to become available for viewing in August
   2026". Nothing to harvest this session — correctly left as a real zero. **Next-session
   priority**: re-check `broward.realtaxdeed.com` calendar starting ~August 2026; once CALBOX
   cells appear, port the existing `realtaxdeed`-platform harvest pattern (already used for
   dixie/alachua/sumter/clay/gadsden per `pipeline.counties`) rather than building new code.
2. **Criterion I's 25-row gap (677/702, still comfortably >95%) breaks down as**: 12 rows are
   6-digit BCPA folio stubs from case-docket scraping with no value data (would need a fresh BCPA
   lookup, not a mechanical fix); 5 rows have non-standard placeholder parcel_ids (timeshare/
   multiple-parcel bundles — need a schema-level exception, not a data fix); 3 rows have no
   parcel_id extracted from the case docket at all; **5 rows have real, valid, zone-linked BCPA
   parcel IDs and are missing only lat/long** — this is the one cheap remaining fix candidate
   (geocode 5 known addresses) but was not applied this session since I already PASSes and this
   firing's mandate was verification, not incremental point-chasing on a passing letter.
3. **Criterion G's genuinely-null far/pk1000 fields are architecturally correct, not an evaluator
   gap.** All 722 of Broward's density-applicable parcels are residential-category zoning
   districts (0 fall in commercial/industrial/mixed-use), so `v_zoning_district_applicability`
   correctly marks the FAR/parking denominator as 0-applicable for the entire county — the pass is
   legitimately density-only. `zone_standards` does carry 44 non-null `max_far` and 54 non-null
   `parking_per_1000sf` values for Broward's 133 districts; they're simply not counted because none
   of Broward's linked districts are in the applicable category bucket. Not a bug; flagged for
   awareness only.
4. **Unchanged from the 2nd firing (not re-touched, still open)**: `public.touch_county_freshness()`
   is a blind `last_seen_at` bump with zero live-source re-verification (fleet-wide concern, shared
   code, out of single-shard scope).

## Verification evidence

Live at session start (unchanged from 2nd firing's close):
```sql
SELECT public.pencil_dod_evaluate_county('broward');
--  A:PASS(17, fc=685 td=17) B:PASS(100) C:PASS(99.6) D:PASS(99.7) E:PASS(99.6)
--  F:PASS(100) G:PASS(98.6) H:PASS(0) I:PASS(96.4, card_complete=677 of 702) J:PASS(95.2) ← 10/10
```

ULTRALOOP audit + adversarial-refute workflow (2 auditors + 2 blind refuters, independent
Bash/DB access each, no shared context):
```
G — auditor: reproduced density_applicable=722/3/98.6, far_applicable=0/725/NULL,
    pk1000_applicable=0/725/NULL via v_zoning_gold_standard_kpi_v3; confirmed zone_standards
    has 44 max_far + 54 parking_per_1000sf non-null rows (data exists, just not in the
    applicable-category bucket). refuter: independently re-ran the same view query and the
    live evaluator call, got identical numbers, pulled v_zoning_district_applicability's
    actual definition and confirmed the category-gating logic matches. VERDICT: SURVIVES.
G — refuter verdict: "REFUTED: false — SURVIVES."

I — auditor: reproduced card_complete=677/702 via the evaluator's own `c` CTE against
    multi_county_auctions + v_zoning_gold_standard_card; characterized all 25 gap rows by
    root cause (12 value-stub, 5 placeholder-parcel, 3 null-parcel, 5 geo-only-missing).
    refuter: independently hand-rolled the same CTE bypassing pencil_dod_evaluate_county
    entirely, got gap=25 (exact match), confirmed no denominator/count mismatch.
    VERDICT: SURVIVES.
I — refuter verdict: "REFUTED: SURVIVES"
```

Fleet mid-flight check (why `gold_standard_loop()`/`certify()` were skipped):
```
$ gh run list --status in_progress --json workflowName,createdAt | length
10   # "CC Runner — GHA-only (no Hetzner)" runs, created ~19:20:02–19:20:16Z,
     # i.e. actively in progress at the time of this check (19:2xZ)
```

Live tax-deed platform re-check (this firing):
```
POST https://broward.deedauction.net/auctions/upcoming
--> {"recordsTotal":0,"gsgAlert":[{"content":"...Broward County tax deed auctions will no
     longer be conducted in DeedAuction. Please visit ... broward.org/recordstaxestreasury..."}]}

GET https://broward.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR
--> HTTP 200, len=24774, "Taxdeed" jump-to entry present, 0 CALBOX cells (honest zero)

SELECT county_slug, platform, sale_type, is_active, last_verified FROM realauction_subdomains
WHERE county_slug='broward' AND sale_type='tax_deed';
--> platform=realtaxdeed, is_active=true, last_verified=2026-05-24 (already correct)
```

Migration applied live (verified by re-select immediately after):
```sql
-- supabase/migrations/20260730e_gold_standard_shard6_broward_taxdeed_platform_correction.sql
UPDATE pipeline.counties SET taxdeed_platform='realtaxdeed',
  taxdeed_url='https://broward.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR', ...
WHERE county_slug='broward';
-- STATUS 201, 1 row affected

SELECT county_slug, taxdeed_platform, taxdeed_url FROM pipeline.counties WHERE county_slug='broward';
--> {"county_slug":"broward","taxdeed_platform":"realtaxdeed",
--   "taxdeed_url":"https://broward.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR"}
```

Post-migration re-check (unaffected, as expected):
```sql
SELECT public.pencil_dod_evaluate_county('broward');
--  A:PASS(17) B:PASS(100) C:PASS(99.6) D:PASS(99.7) E:PASS(99.6)
--  F:PASS(100) G:PASS(98.6) H:PASS(0) I:PASS(96.4) J:PASS(95.2) ← still 10/10
```

Timestamp: 2026-07-30T19:35Z (UTC)

## Wiring / files

- `GOLD_STANDARD_SHARD6_BROWARD_DISPATCH_3BB96D0D_RUN7519_3RD_FIRING_ADDENDUM.md` (this file).
- `supabase/migrations/20260730e_gold_standard_shard6_broward_taxdeed_platform_correction.sql` —
  applied live this session (1-row `UPDATE pipeline.counties`).
- No `gold_standard_ultraloop_audit` rows inserted this firing — the 2nd firing's G/I audit rows
  (both survived=true, ~3–4h old at this firing's start) were already within the 7-day
  certification freshness window; this firing's independent re-derivation and refutation confirms
  they remain valid, but per the audit table's own schema (one row per claim-of-improvement) there
  was no new claim to log since nothing changed.

## Next-session priorities

1. **P1**: re-check `broward.realtaxdeed.com` calendar starting ~August 2026 for the first
   CALBOX cells; once populated, harvest via the existing `realtaxdeed`-platform pattern (no new
   scraper needed — dixie/alachua/sumter/clay/gadsden already use it).
2. **P2, optional (I already PASSes)**: geocode the 5 real-parcel, geo-only-missing letter-I rows
   identified this session if a session has spare capacity — would move I from 96.4% to ~97.1%,
   not required for certification.
3. **P2, fleet-wide (not broward-specific)**: still-open from the 2nd firing — audit every caller
   of `public.touch_county_freshness()` for blind freshness bumps with no live re-verification.
4. **Close-out**: once a session confirms zero concurrent fleet activity (check
   `gh run list --status in_progress`, not just recent commits — this firing found 10 concurrent
   sessions despite over an hour of git-log silence), run
   `SET statement_timeout=0; SELECT public.gold_standard_loop(); SELECT public.gold_standard_certify();`
   — all preconditions for broward's `is_gold=true` remain met (confirmed twice now across two
   firings of this dispatch).
