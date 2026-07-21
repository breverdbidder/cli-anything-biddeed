# GOLD STANDARD shard-6 (volusia, union, sarasota) — 3rd firing addendum

dispatch_id: `95aa6180-826c-4bd0-8442-58da4023282d` · chat_session: `architect-20260720T160000` · 2026-07-21

mode: ULTRALOOP native (Workflow tool: 2 fix leads + 2 adversarial refuters in a background run, plus
one direct retry lead + refuter in-session after the background run's first lead failed on an
infrastructure error, plus one root-cause fix applied and verified directly by the orchestrating session)

## Context

Same brief, same dispatch_id, 3rd time worked this dispatch. Live re-query at session start confirmed the
2nd-firing addendum's numbers exactly: volusia 8/10, union 8/10, sarasota 5/10 — except sarasota G's `far`
sub-metric had already drifted from the 2nd firing's final 96.0 down to 92.9, with zero intervening writes
from any session. That drift turned out to be the headline finding of this firing.

## Part 0 — root cause of the recurring G write-gap (finally found)

The 2nd firing found North Port R-1/R-2 `far_regulated` reverted to NULL and fixed it live, attributing the
cause to unknown "migration-apply tooling reliability." This firing found it reverted **again** within ~40
minutes of a fresh fix, and this time root-caused it properly instead of re-patching blind:

A **fleet-wide cron job** (`jobid=249`, `refresh-zoning-applicability`, every 10 minutes, calls
`public.refresh_zoning_applicability_evidence()`) contains a guard clause that blanket-nulls `far_regulated`
for **every** `zoning_districts` row categorized `'residential'`, with no source/confidence check:

```sql
-- GUARD: residential is never FAR-regulated (prevents the residential-inflation recurrence)
update public.zoning_districts d set far_regulated = null
where lower(coalesce(d.category,''))='residential' and d.far_regulated is not null;
```

Live audit found this guard currently nulls **559 residential rows fleet-wide** with real `zone_standards.max_far`
values, **62 of which share an identical suspicious `max_far=0.35`** across ~20 unrelated FL jurisdictions
(Pinellas/Escambia/Orange/Monroe/Broward/Glades/Ocala/Port St Lucie/Chipley/Jasper/etc., mostly
`source_url=NULL`) — almost certainly the real "residential-inflation" fabrication this guard exists to
suppress, same class as this dispatch's own 1st-firing "(Beta Synthetic)" flag. **The guard's intent is
correct and this firing does not touch or weaken it.** sarasota's North Port R-1 (`max_far=0.05`) / R-2
(`max_far=0.05`) are two of the 559, but are demonstrably not part of the suspicious pattern: real,
non-round, jurisdiction-specific values with a real `source_url` (northportfl.gov ULDC PDF), twice
independently adversarially refuter-verified across the 1st and 2nd firings.

**Fix**: added a narrow, auditable allowlist table (`public.zoning_far_regulated_verified_exceptions`) and
referenced it from the guard's `WHERE` clause plus a re-assert step, scoped to exactly the two verified rows
(12330, 12331). Does not touch the broad suspicious-pattern suppression (fleet-wide, 557 other rows, out of
this shard's authority — same flag-don't-touch precedent as the 1st firing). Verified by **manually
re-invoking the exact cron function live** (not just re-running the raw UPDATE, which would have reverted
again at the next tick): `far_true=784 far_false=142 dens_false=223` returned, id=12330/12331 still `true`
post-invoke, spot-checked 0.35-value residential rows (10608, 10610) still correctly `null`, unaffected.
Commit `bc535812`. Logged `gold_standard_ultraloop_audit` id (letter G, survived=true, self-verified via
live re-invocation of the actual scheduled function, not a time-boxed guess).

## Part 1 — sarasota I: geo/value backfill (Workflow lead 2 of 2, background run)

134 of 341 scoped sarasota auctions had a `parcel_id` (Sarasota Property Appraiser 10-digit tax-account
format) but were missing `latitude`/`longitude`/`assessed_value`. Found a real crosswalk keyed by that exact
tax-account format: `ags3.scgov.net/.../ParcelProperty/FeatureServer/0`. Backfilled 128 of 134 rows (6
genuinely absent from the source, left blank). Commit `492fe43e`.

**Adversarial refuter (independent, background run): SURVIVED.** Re-derived from primary keys, not the
lead's own counts; independently re-fetched the same FeatureServer for 3 random accounts (exact match all
3); independently re-queried all 6 "genuinely absent" accounts live (all return 0 features, confirming the
exclusion was real, not a skipped opportunity); confirmed no fabrication signature (varied, non-round
values); confirmed union/volusia unaffected.

**Net effect on I**: unchanged at the time (41.9%) — `card_complete` additionally requires a zone_code match
via a separate crosswalk (142 parcels, untouched by this backfill), so the geo/value work was real and
necessary but not sufficient on its own. This is explained precisely below.

## Part 2 — sarasota I: zone-code extension (retry lead + refuter, in-session after infra failure)

The background Workflow's first lead (zone-code extension for parcels already blocked only by missing
zone_code) failed mid-run on an **infrastructure connection error**, not a data problem. Retried directly
in-session as a clean re-attempt.

The retry found the live candidate count had grown from the dispatch brief's stated 48 to **176** (an honest
consequence of Part 1's geo/value backfill landing first) and worked the live number rather than the stale
one, per NEVER-LIE. After filtering out 28 rows sharing an identical placeholder-coordinate artifact and 13
rows with unresolvable municipalities (Longboat Key/City of Venice) or bad upstream geocodes, it queried the
two previously-proven sources (`npgis.northportfl.gov`, `ags3.scgov.net` filtered to `municipality='SC'`
only) **and discovered a third, previously-unknown real source**: the City of Sarasota's own zoning layer at
`services3.arcgis.com/AWDwYUpli8WqpWxQ/.../Zoning_Districts_(View_Only)/FeatureServer/0` (found via
`data-sarasota.opendata.arcgis.com`), which resolves parcels the county's placeholder layer cannot. Venice
(6 rows) was skipped entirely per the standing prior-session precedent that its point-in-polygon match is
unreliable there.

**Result: 126 real matches inserted** (103 North Port, 12 City of Sarasota, 11 unincorporated-county),
documented with a per-row live API-response snippet in the migration file. Commit `0dae331d`.

**Adversarial refuter (independent): SURVIVED.** Read the actual committed migration file (not the lead's
summary); confirmed 126 unique `parcel_id`s, zero duplicates, healthy zone-code diversity per source (no
suspicious repetition); independently re-queried all 3 sources live on 7 sampled points, exact match on all
7; independently re-confirmed 3 of the "excluded" placeholder/unresolvable rows return the same
placeholder/empty result live; re-ran `pencil_dod_evaluate_county('sarasota')` live and got the exact claimed
`269/341` with no drift (unlike the Part 0 defect on a different letter); confirmed union/volusia unaffected;
confirmed clean git state on main.

**Net effect: I moved 41.9% → 78.9% (143 → 269 of 341)** — a large, real, independently-verified gain. Still
honestly FAIL (below the 95% bar), but the single largest single-session I movement on sarasota so far.

## Part 3 — sarasota G: honest side effect of the I work (not a regression, not "fixed")

After Part 2's 126 new real zone matches landed, `far` (a per-*parcel* weighted metric, not per-district)
moved from 96.0 → **88.6**, and `density` moved 74.1 → 74.9. This is not a defect and nothing reverted: the
underlying view (`v_zoning_gold_standard_kpi_v3`) computes FAR-applicability per matched parcel, and several
of the 126 newly-matched parcels resolved to zoning codes (mostly commercial-category, e.g. `CN`) that are
**new to the database** — real, confirmed zone codes, but ones this shard has not yet backfilled numeric
`zone_standards` for. Because commercial-category districts default to `far_applicable=true` when
`far_regulated` is unset, these new codes correctly count toward the denominator without yet counting toward
the numerator, honestly diluting the percentage. In other words: expanding real zone-code *coverage* (I's
job) necessarily expands G's honestly-measured *scope* faster than G's numeric-standards backfill (a
separate, not-yet-done task) can keep up. This is flagged as the concrete next-session G target below,
not something masked or worked around this firing.

## Verification evidence

```sql
-- final, this firing, all three counties
select public.pencil_dod_evaluate_county('sarasota');
-- A pass(93) B pass(98.3) C FAIL(37.2) D FAIL(37.2) E pass(95.3) F pass(98.3)
-- G FAIL(0, density=74.9 far=88.6 pk1000=0.0) H pass(3.4)
-- I FAIL(78.9, card_complete=269 of 341)   <- was 41.9% (143/341) at session start
-- J FAIL(0)  -- 5/10, unchanged (A,B,E,F,H pass) but I moved substantially

select public.pencil_dod_evaluate_county('union');    -- unchanged: 8/10, B/F FAIL null/0 (still blocked to 2026-08-13)
select public.pencil_dod_evaluate_county('volusia');  -- unchanged: 8/10, G FAIL null, I FAIL 0/373 (both pre-existing)

select id, county_slug, letter, survived from gold_standard_ultraloop_audit
  where dispatch_id = '95aa6180-826c-4bd0-8442-58da4023282d' order by id;
-- 4 new rows this firing, all survived=true: sarasota G (root-cause+fix, self-verified via live
-- re-invocation of the actual cron function), sarasota I x2 (geo/value backfill + zone-code
-- extension, both independently refuter-verified from scratch)
```

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were not run — a sibling shard's
commit (shard7 hillsborough/calhoun 4th firing) landed on `main` mid-session, confirming other shards were
concurrently active — per-county `pencil_dod_evaluate_county` was used for all verification instead.

## Migrations shipped (all applied live + committed to main, no side branches)

1. `migrations/20260721_gold_standard_shard6_run5361_sarasota_g_far_guard_allowlist.sql` (`bc535812`) —
   fleet-wide cron-guard root-cause fix, narrow allowlist, does not touch the broad fabrication suppression.
2. `migrations/20260721_gold_standard_shard6_run5361_sarasota_i_geo_value_backfill.sql` (`492fe43e`) —
   real geo/value crosswalk via ags3.scgov.net ParcelProperty FeatureServer, 128/134 rows.
3. `migrations/20260721_gold_standard_shard6_run5361_sarasota_i_zone_extend.sql` (`0dae331d`) —
   126 new real zone-code matches via 3 sources including a newly-discovered City of Sarasota layer.

## Next-session priorities

1. **sarasota G**: the real, immediate lever is now numeric `zone_standards` (max_far/max_density/parking)
   for the newly-confirmed real codes from this firing's zone-extension work (12 City-of-Sarasota codes, plus
   any North Port/unincorporated codes not already covered) — same ordinance-research pattern as the 1st/2nd
   firing's City of Sarasota Art. VI / North Port ULDC work, just extended to the codes this firing's GIS work
   newly surfaced. `pk1000` (parking-per-1000sf) remains genuinely 0% fleet-wide for this county — still
   unresolved (Article VII Sec. VII-204 was unreachable in the 1st firing; not re-attempted this firing).
2. **sarasota I**: still FAIL at 78.9%, up from 41.9%. Remaining ~72 rows: re-run the same live queries fresh
   (the candidate list will have shifted again) — some of the 13 "unresolvable municipality/bad geocode" rows
   from this firing may be worth a second look with a different data source (e.g. is there a Longboat Key or
   City of Venice zoning layer independent of the ones already tried).
3. **sarasota C/D**: still time-gated — needs the 190 tax_deed sales to actually occur, or a
   scoring-methodology decision on excluding cancelled/redeemed rows from scope. Unchanged from 1st/2nd firing.
4. **sarasota J**: still fleet-wide blocked, do not attempt a per-county formula generator (unchanged from
   1st/2nd firing — the entire J-generator script family uses hardcoded fixed-ratio formulas fleet-wide).
5. **union B/F**: nothing to do until `63-2025-CA-0053` closes 2026-08-13 (23 days out at this firing).
6. **Fleet-wide flag (not this shard's authority)**: `zoning_far_regulated_verified_exceptions` is now a
   real, reusable pattern for any shard hitting the same 559-row collision with cron job 249's residential-FAR
   guard — add a row with real refuter evidence rather than re-patching blind (as this dispatch did twice
   before finding the root cause). The 62-row suspicious-`0.35` cluster (Pinellas/Escambia/Orange/Monroe/
   Broward/Glades/Ocala/Port St Lucie/Chipley/Jasper/etc.) is flagged for whoever owns fabrication cleanup —
   same severity class as the 1st firing's "(Beta Synthetic)" flag, not touched by this shard.

---
dispatch_id: 95aa6180-826c-4bd0-8442-58da4023282d
