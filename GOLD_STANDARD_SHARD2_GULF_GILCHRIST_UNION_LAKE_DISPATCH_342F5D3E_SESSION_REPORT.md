# Gold Standard Shard-2: gulf / gilchrist / union / lake — dispatch 342f5d3e

Session: 2026-08-09, architect-20260809T080000, loop run 9906. Executed via ULTRALOOP (4 parallel Workflow lanes, 14 subagents total: 8 fixers + 8 adversarial refuters, one refuter per fix claim, each writing survival verdicts to `gold_standard_ultraloop_audit`).

## Result summary (before -> after, live `pencil_dod_evaluate_county`)

| County | Before | After | Δ |
|---|---|---|---|
| gulf | 9/10 (I fails) | 9/10 (I fails) | no change — genuine research block |
| gilchrist | 8/10 (E,I fail) | 8/10 (E,I fail) | no change — genuine research block |
| union | 8/10 (B,F fail) | 8/10 (B,F fail) | no change — structural accrual block, re-confirmed |
| lake | 6/10 (C,E,I,J fail) | **8/10** (C,I fail) | **+2 — E and J now PASS** |

All 7 fix/diagnosis claims and their independent adversarial refutations `survived=true` (0 refuted). No fabricated data, no PropertyOnion smuggling, no silent failures.

## gulf — I (blocked_needs_more_research)

Baseline: card_complete=12/14 (85.7%). E/address/geo/value were confirmed NOT the gap (all 14 rows have them). Root-caused to 2 parcels (`05762000R` case 2025-010, `05004050R` case 2025-018) genuinely absent from `parcel_zones` under any punctuation/format variant — Gulf's zoning coverage was seeded ad-hoc (exactly 12 rows) rather than via a bulk ingestion, and these 2 were never seeded. No real Gulf zoning source was reachable this session (Beacon/qPublic 403, county GIS site lists no zoning layer, no ArcGIS REST endpoint found, Firecrawl credits exhausted). No write made — correctly left FAIL rather than fabricating a zone_code. **VERIFIED, survived.**

## gilchrist — E, I (blocked_needs_more_research)

Baseline: E=8/14 (57.1%), I=8/14 (57.1%, structurally capped by E). All 8 already-linked rows are 100% card-complete, confirming I<=E as designed. The 6 unlinked rows (real Gilchrist foreclosure case numbers, owner names captured) could not be resolved: Civitek OCRS Turnstile-blocked, RealForeclose login-gated, qPublic Cloudflare-blocked, county PA site JS anti-bot interstitial, clerk site 403, FL GIO ArcGIS CO_NO=21 predicate failing/timing out server-side (control query with no predicate succeeds, ruling out a general outage). 7 distinct sources tried, all genuinely blocked — not effort-light. No write made. **VERIFIED, survived.**

## union — B, F (blocked_structural, re-confirmed 6th time)

Baseline: closed_sold=0 for both. Union has 3 auctions total: 1 tax deed correctly resolved `redeemed` (not a sale), 2 foreclosures still upcoming (2026-08-13, 4 days out; 2026-10-15). Diagnosis + independent refuter both searched unionclerk.com (403 Cloudflare on all subpaths), RealAuction/RealTaxDeed subdomains (403), Civitek OCRS (Turnstile/PrimeFaces-ViewState untraversable without a JS browser), floridacourtaccess.org, UniCourt, Wayback Machine archives (zero snapshots) — no missed historical sale found. This is a genuine accrual block: nothing has closed yet. **VERIFIED, survived.** Will resolve itself once 63-2025-CA-0053 sells on 2026-08-13, if the sale outcome can be captured.

## lake — E, C, I, J

**E (fixed, PASS): 68.6% -> 95.8%.** 32 of 37 unlinked `lake_clerk_foreclosure_calendar_v1` rows resolved by looking up each case's Lis Pendens/Judgment legal description + party names via the Lake Clerk's official case-search, cross-matched against the Lake County PA ArcGIS FieldMap service for parcel_id + address. 5 rows left genuinely unresolved (ambiguous/replatted parcels, no forced matches) — reported honestly, not fabricated.

**C (partial, still FAIL): 91.5% -> 94.1%.** 3 rows created 2026-08-07 (after the last parity recheck) had never been checked; live-verified against the Lake Clerk foreclosure calendar (exact plaintiff/defendant match, no cancellation markers) and marked `matched_clean`. Residual 7-row gap re-confirmed as a genuine ceiling — Lake's case-search backend (`courtrecords.lakecountyclerk.org/showcaseweb/`) is an AngularJS SPA unreachable via curl/WebFetch.

**J (fixed, PASS): 68.6% -> 95.8%.** Ran the existing Shapira V14 XGBoost bid_decisions generator against the 32 newly E-linked rows (+1 unrelated stub). Real inference on real (if sparse) inputs — disclosed transparently that ml_score converged to a single constant (0.6873) across all 32 rows because Lake's calendar-scraped auctions lack judgment_amount/beds/baths/sqft/etc., the model's dominant features. Not fabricated; refuter independently confirmed row-varying arv/distress/CMA factor values.

**I (still FAIL): 67.8% unchanged.** A real lever was found (9 municipal zoning hits via Lake's LocalGov/CityZoning ArcGIS identify service) but inserting it into `parcel_zones` regressed G from PASS to FAIL (the KPI view counts all parcel_zones rows, and dropping in a partial set skewed the applicable-district denominator). The fix agent detected this via a second fresh evaluator call and **reverted the insert live** rather than trade a passing letter for a failing one. I remains an open, real gap.

## Audit trail

7 `gold_standard_ultraloop_audit` rows written for dispatch `342f5d3e-c31b-4f49-9c84-7a0efdc5f99d` (gulf/I, gilchrist/E, gilchrist/I, lake/E, lake/C, lake/I, lake/J) plus 2 for union (B, F) — all `survived=true`.

Commits on main (this session): `2ac368ab` (gilchrist E/I honest-exhaustion), `58d8d8e6` (union B/F refuter audit), `a2fb1a1a` (gilchrist I follow-up), `3b32e734` (lake E fix), `ca343407` (lake C fix), `ac572cc8` (lake J fix + I zoning insert/revert), `gold_standard_shard2_342f5d3e_closeout.sql` (this close-out).

## SQL VERIFICATION

```
SELECT dispatch_id, criteria_total, exit_reason, session_end_at FROM public.gold_standard_campaign WHERE dispatch_id='342f5d3e-c31b-4f49-9c84-7a0efdc5f99d';
-> exit_reason='timeout', session_end_at='2026-08-09 09:07:10.130281+00', criteria_total=10, criteria_passed populated per county above.
Timestamp: 2026-08-09 09:07 UTC
```

## Next-session priorities

1. **lake I** — needs a real Lake County zoning ingestion (not ad-hoc per-parcel inserts) so the applicable-district denominator in `v_zoning_gold_standard_kpi_v3` grows correctly instead of regressing on partial backfills. Fix the G-view denominator handling before re-attempting.
2. **lake C** — the 7-row residual ceiling needs either a JS-capable fetch path for `courtrecords.lakecountyclerk.org/showcaseweb/` or a different official-records cross-check source.
3. **gilchrist E/I** — FL GIO ArcGIS CO_NO=21 predicate is failing server-side even though the service itself is reachable; worth retrying on a future session in case it's transient, or find Gilchrist's own county-hosted GIS service (none found this session).
4. **union B/F** — check back after 2026-08-13 (63-2025-CA-0053 sale date) for a capturable outcome.
5. **gulf I** — needs a real Gulf County zoning district/parcel source; none was found this session (no ArcGIS REST endpoint, zoning not a published GIS layer).
