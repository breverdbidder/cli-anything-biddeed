# Gold Standard Shard-5: bradford / manatee / baker — Session Report

- dispatch_id: `66eb9c40-b05f-49b1-a8fa-33c8138bdd7f`
- chat_session: `architect-20260808T080000`
- loop run: 9764
- date: 2026-08-08
- issue: breverdbidder/cli-anything-biddeed#18355
- ultraloop_mode: fallback (manual subagent pattern — no `/effort ultracode` in this runner)

## Scope

Assigned shard: **bradford** (8/10, B/F fail), **manatee** (7/10, C/D/I fail), **baker** (5/10, C/D/E/I/J fail).
Per PARALLEL-FLEET RULES, only these three counties were touched.
`gold_standard_loop()`/`gold_standard_certify()` were **not** run fleet-wide this session —
per-county `pencil_dod_evaluate_county()` used throughout, per the brief's guidance for
when other shards may be mid-flight.

## Prior State Summary (from session reports, cross-referenced with brief)

| County | Brief | Most Recent Session Report | State Interpretation |
|--------|-------|--------------------------|---------------------|
| bradford | 8/10 (B/F fail) | 96a9bc5d, 2026-07-31: B/F unchanged, 6 sessions exhausted | 8/10 structural block confirmed |
| manatee | 7/10 (C/D=86.9%, I=84.1%) | e6951fe0, 2026-07-24: 10/10 (86 rows). 0c5b222d, 2026-07-25: still 10/10 | Brief shows 107 rows — ~21 new rows added, metrics regressed |
| baker | 5/10 (C/D/E/I=64.7%, J=88.2%) | be7c06d5, 2026-08-03: 6/10 (7/15=46.7%). 61cdbda5, 2026-08-01: CAPTCHA block confirmed | Brief shows 17 rows (was 15) — 2 new rows, 4 more enriched. J now failing on 2 rows |

## bradford — STRUCTURALLY BLOCKED, ultraloop logged

**B/F FAIL: verified=0, closed_sold=0.** Single case `25000457CAAXMX`, sale date 2026-07-16.

This is the **6th+ consecutive independent session** confirming every automated source exhausted:
- `bradford.realforeclose.com`: no post-sale outcome data published
- `bradford.realtaxdeed.com`: sale not listed here (foreclosure case)
- Bradford County Clerk website: Cloudflare WAF (403)
- BC Telegraph archive: searched through 2026-07-30, no case coverage found
- `myflcourtaccess.com`: portal type verification, not outcome data
- Surplus-funds aggregator sites: no listing for this case
- Legal notices (`floridapublicnotices.com`): case not published/indexed
- `bradfordclerk.com/foreclosures/`: HTTP 403 WAF (multiple agents confirmed)

**Action this session:** None beyond logging ultraloop audit rows (bradford/B, bradford/F both `survived=true` — the "B/F is structurally blocked" claim is correct and verifiable).

**Next-session lever:** Human outreach only. Phone or records request to Bradford County Clerk of Courts for the outcome of case 25000457CAAXMX. No further automated sessions should target bradford B/F until that outreach result is available.

## manatee — C/D/I enrichment via RealForeclose AJAX + ArcGIS

### Root cause (INFERRED from brief vs. session report delta)
manatee was 10/10 at 86 auctions as of 2026-07-24 (dispatch e6951fe0, verified).
The brief shows 107 auctions, with C/D=86.9% (93/107) and I=84.1% (90/107).
This implies ~21 new auction rows were ingested between July 24 and August 8, of which
most lack `parity_status` and `parcel_zones`/`latitude`.

### Fix applied

**C/D:** The session executor (`scripts/gold_standard_shard5_run9764_bradford_manatee_baker.py`)
probes `manatee.realforeclose.com` AJAX calendar for each auction_date with unmatched rows.
For each row whose normalized case_number matches an item on the live calendar, stamps
`parity_status='matched_clean'`, `parity_source='tier1_realforeclose_manatee:shard5_run9764:...'`.

This is the same evidentiary tier as the 83 already-matched manatee rows (calendar listing
on the official RealAuction platform for that county = tier1 match), consistent with the
methodology validated in sessions e6951fe0 and 0c5b222d.

**E:** For rows with `property_address` but no `parcel_id`, queries Manatee County's
`GIS_PARCELS` ArcGIS FeatureServer (`services1.arcgis.com/t03WDvnSR7gSDOB2/...`) by
street address match. Requires single-feature result (no ambiguous multi-match writes).

**I:** For rows with `parcel_id` but missing `latitude`/`longitude`, queries the same
ArcGIS endpoint by `PARCEL_ID` to backfill lat/lon. This is the same methodology
from dispatch `e6951fe0`'s I fix (verified to work for manatee ArcGIS).

### Expected outcome
UNTESTED (executor runs via GHA after this commit). If the new rows appear on the
realforeclose calendar (likely, given they came from the same scraping pipeline that
ingests calendar rows), C/D should recover toward 95%+. If the new rows have
property addresses, E/I backfill via ArcGIS will follow.

### Residual (known still-blocked, per prior sessions)
3 rows identified in session e6951fe0 remain blocked (no parcel reachable via any source):
- `412019CA003996CAAXMA`: lat/lon is a stale auction-system default, not real
- `412024CA000409CAAXMA`: address doesn't match any Manatee GIS parcel
- `412025CA001790CAAXMA`: auth-walled on all public sources

These 3 rows have been researched 2+ times. Not retried this session (I=96.5% was fine
without them when manatee was 86-row; now they contribute to the I gap at 107 rows, but
the primary fix targets the new rows which are more likely to yield real data).

## baker — ArcGIS probe + bid_decisions generation

### State at session start (INFERRED from brief)
Baker went from 7/15=46.7% (dispatch be7c06d5, 2026-08-03) to 11/17=64.7% (current brief).
This means:
- 2 new rows were added since Aug 3 (15→17 total)
- 4 rows moved from unmatched→matched (from 7 to 11) — likely from a scraper run
- J moved from 100% to 88.2% (15/17): the 2 new rows lack bid_decisions

### Fix applied

**J:** Generator runs for any baker rows missing `bid_decisions`. Uses Shapira formula
(ARV = assessed_value × 1.10, max_bid = ARV×0.70 - repairs($15K) - $10K - min($25K, 15%×ARV),
ml_score=0.58 for Baker rural proxy, 5 required factor keys). BLANK>WRONG: rows without
assessed/market_value are skipped.

**E/I:** Baker County ArcGIS `parcels_web2` FeatureServer
(`services6.arcgis.com/HSWu3dhzHf7nZfIa/.../parcels_web2`) probed for the 2 new rows
that may have property_address but no parcel_id. Single-match requirement enforced.

### Still-blocked (confirmed by 4+ independent sessions)
4 cases (`022025CA000108CAAXMX`, `022025CA000117CAAXMX`, `022025CA000124CAAXMX`,
`022026CA000007CAAXMX`):
- `civitekflorida.com/ocrs/county/02/`: Cloudflare Turnstile checkbox CAPTCHA
- `bakerclerk.com`: Cloudflare JS challenge
- `bakerpa.com`: up (HTTP 200) but requires owner_name to search; source has none
- `baker.realforeclose.com`: parcel_id link is literally `href="...?parcel="` (empty at source)

Ceiling without CAPTCHA bypass: 8 of 17 rows (4 cases × 2 sale_type rows) remain
permanently unresolvable by current tools → max achievable C/D/E = (17-8)/17 = 52.9%
(still FAIL under 95% threshold). **baker cannot reach 10/10 without either:**
1. Baker County populating parcel data at the source, or
2. CAPTCHA bypass capability, or
3. Additional new auctions with parcel data bringing the denominator high enough

## Artifacts shipped

1. `scripts/gold_standard_shard5_run9764_bradford_manatee_baker.py` — session executor
2. `.github/workflows/gold-standard-shard5-run9764-bradford-manatee-baker.yml` — GHA wiring
3. `migrations/20260808_gold_standard_shard5_run9764_bradford_manatee_baker.sql` — verification queries + notes
4. This session report

## Verification Protocol

The GHA workflow (`gold-standard-shard5-run9764-bradford-manatee-baker.yml`) executes:
1. `pencil_dod_evaluate_county` for all 3 counties (BEFORE)
2. Session executor script (enrichment + bid_decisions generation)
3. `pencil_dod_evaluate_county` for all 3 counties (AFTER)
4. `gold_standard_campaign` close-out (`criteria_passed`, `exit_reason`, `session_end_at`)
5. Ultraloop audit rows for all touched letters

The executor script itself logs `gold_standard_ultraloop_audit` rows before/after
each county's work — verifiable via:
```sql
SELECT county_slug, letter, survived, created_at, claim
FROM gold_standard_ultraloop_audit
WHERE dispatch_id = '66eb9c40-b05f-49b1-a8fa-33c8138bdd7f'
ORDER BY county_slug, letter, created_at;
```

## Plan vs Actual (HONEST — workflow not yet run at time of writing)

| County | Letter | Planned | Actual | Status |
|--------|--------|---------|--------|--------|
| bradford | B/F | Log structural block, ultraloop audit | Script ships this via REST | UNTESTED |
| manatee | C/D | RealForeclose AJAX match for new rows | Script probes AJAX calendar | UNTESTED |
| manatee | E/I | ArcGIS parcel/lat-lon backfill | Script queries GIS_PARCELS | UNTESTED |
| baker | J | bid_decisions for 2 missing rows | Script generates with Shapira formula | UNTESTED |
| baker | E | ArcGIS parcels_web2 probe | Script queries Baker ArcGIS | UNTESTED |

UNTESTED is always acceptable per HONESTY PROTOCOL. The GHA workflow is the execution
receipt — results will be visible in the GHA run log. The before/after JSON from
`pencil_dod_evaluate_county` will be the SQL VERIFICATION for this session.

## Next-Session Priorities

1. **manatee**: If C/D/I reach 95%+ from this session's enrichment, confirm 10/10 and
   let the 2-consecutive-day certify gate proceed. If not, check which new rows remain
   unmatched and probe for additional AJAX dates.

2. **baker**: J should recover if new rows have assessed_value. C/D/E/I ceiling remains
   52.9% due to CAPTCHA block — no further automated sessions should target these letters
   until the block is resolved.

3. **bradford**: No automated action until Bradford Clerk human outreach is complete.
   B/F cannot move without an independent verified outcome source.

dispatch_id: 66eb9c40-b05f-49b1-a8fa-33c8138bdd7f
