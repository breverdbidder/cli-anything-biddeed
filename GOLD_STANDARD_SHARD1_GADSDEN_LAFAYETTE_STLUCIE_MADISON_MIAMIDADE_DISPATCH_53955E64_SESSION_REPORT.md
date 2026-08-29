# Gold Standard shard-1 — gadsden / lafayette / st_lucie / madison / miami_dade

**Dispatch:** `53955e64-8649-4da8-b306-15a8a09007f6` (loop run 15182, 08:00Z wave, one of 5 concurrent shard dispatches)
**Date:** 2026-08-29
**Mode:** ULTRALOOP native (Workflow tool, 6 fix agents + 6 independent adversarial refuters, 12 agents total)
**DB access:** psql/pgbouncer pooler confirmed broken in-session (`ENOIDENTIFIER`, known/documented). Used the
Supabase **Management API SQL endpoint** (`POST /v1/projects/mocerqjnksmhcjzxrewo/database/query`, service
token) for all direct SQL — a real, working, non-pgbouncer path to Postgres that this session confirmed live;
PostgREST used for simple filtered reads/RPC calls.

## Scoreboard — live `pencil_dod_evaluate_county`, before vs after (independently re-run by me, not just agent self-report)

| county | before | after | delta |
|---|---|---|---|
| gadsden | 10/10 | 10/10 | reconfirmed, audit freshness refreshed (all 10 letters re-logged `survived=true`) |
| lafayette | 9/10 (C fail 75.0%) | 9/10 (C fail 75.0%) | unchanged — canon-block reconfirmed live, no fabrication |
| st_lucie | 9/10 (C fail 80.7%) | 9/10 (C fail 80.7%) | unchanged — canon-block reconfirmed live, no fabrication |
| madison | 8/10 (B/F fail, null) | 8/10 (B/F fail, null) | unchanged — genuine data ceiling reconfirmed, no writes |
| miami_dade | 7/10 (C,D,I fail) | **9/10** (C,D,I now PASS; **G newly fails**) | **net +2** |

## gadsden — freshness/anti-reversion audit (no fix needed)

Live re-run matches the pre-session baseline exactly (A26/B100/C98.5/D100/E97/F100/G100/H/I97/J97). Gadsden has
a documented history of a scheduled scraper reverting manually-applied C fixes (see
`GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md`) — reconfirmed **no reversion in progress**.
All 10 letters had stale-enough audit evidence to warrant a refresh; re-logged 10 fresh `survived=true` rows to
`gold_standard_ultraloop_audit` (ids 19320–19329) after independent adversarial re-verification of each letter
against live data (B's sole verified outcome traced to an independently-sourced `foreclosure_outcomes` row,
not PropertyOnion-laundered; C's single `CLERK_SSOT_CANCELLED` row re-confirmed genuinely cancelled). No writes
to `multi_county_auctions`.

## lafayette C — canon-block reconfirmed (not fixed, correctly)

C fails at 75.0% (3 of 4 auctions) because 1 case (`25000056CAAXMX`) is genuinely cancelled. With `n=4`, a
single cancellation permanently caps C below 95% — this is the documented fleet-wide canon tension between C
(excludes `CLERK_SSOT_CANCELLED`) and D (includes it), not a data defect. Freshly re-scraped the live Lafayette
Clerk foreclosure-sales page this session (`lafayetteclerk.com`) and confirmed the case still shows
`Status=cancelled`, exact match to the DB. **No reclassification made.** Adversarial refuter independently
re-ran the evaluator and cross-checked the row state — survived=true, audit id 19330.

## st_lucie C — canon-block reconfirmed (not fixed, correctly)

C fails at 80.7% (201 of 249). Diagnostic breakdown of the 48-row gap: **47 rows are `CLERK_SSOT_CANCELLED`**
(live-reconfirmed via `acclaimweb.stlucieclerk.gov`, 8/8 spot-checked cases showing `REDM`/redeemed) + **1 row
is `matched_divergent`** (correctly D-eligible, not C-eligible by design). Critically, **zero rows had
`parity_status IS NULL`** — meaning the miami_dade-style "never-parity-checked" fixable lever does not exist
here; st_lucie's parity pipeline has already run against every row. Achievable ceiling is honestly 80.7%.
No reclassification made. Audit id 19304, refuter survived=true.

## madison B/F — genuine data ceiling (not fixed, correctly)

Both fail with `closed_sold=0` (evaluator requires `sold_amount IS NOT NULL`, and no madison row has it). The
one near-miss, case `24-62-CA` (plaintiff credit-bid reversion, no 3rd-party bidder), was checked against 5
independent live sources this session (Auction.com current listing, Madison Clerk foreclosure-sales page, the
May 2026 Re-Notice of Foreclosure Sale PDF, DocketAlarm case summary, myfloridacounty official records) — **no
source anywhere publishes a dollar figure** for the credit-bid amount; standard FL Ch.45 notice practice omits
judgment amounts from publication, and the deeper docket/official-records sources are paywalled or
session-token-bound and not reachable with available tools. Per the explicit guardrail against
self-referential circularity, our own `judgment_amount` was **not** copied into `sold_amount` (that would fail
B's independent-source requirement). This reconfirms a prior 2026-07-30 finding already on file
(`foreclosure_outcomes` id `2b59dc74`, `winning_bid=NULL` for the same reason). **BLANK > WRONG — no writes
made.** Audit ids 19366/19367, refuter survived=true.

## miami_dade C/D — FIXED 94.2% → 95.3% (PASS)

Root cause (fresh finding this session): `auto_parity_check_queue()` requires `auction_url IS NOT NULL`; 36
miami_dade rows had `auction_url`, `parity_status`, and `parity_source` all NULL, so they structurally never
entered the automated litmus pipeline. Backfilled `auction_url` for 7 of the 36 (2026-08-24 foreclosure
auctions) using the confirmed-working `miamidade.realforeclose.com` `AUCTIONDATE`-preview pattern, then ran a
**real** litmus check against the site's own JSON AJAX auction-grid feed (paginated 6 pages), matching
case_number + address for all 7. 6/7 matched byte-for-byte; the 7th had `address=NULL` on both sides
(genuinely missing, not fabricated). Set `parity_status='matched_clean'`,
`parity_source='tier1_miami_dade_url_backfill_v1'`. `matched_clean` moved 587→594 of 623 (94.2%→95.3%). The
remaining 29 gap rows were left untouched (still NULL) — same fix pattern applies for a future session across
the other 4 auction dates. Audit ids 19312/19313 (fix), 19377/19378 (refuter), survived=true both passes.

## miami_dade I — FIXED 91.5% → 95.7% (PASS, critical letter)

`card_complete` only requires the parcel to appear in `parcel_zones` with a non-null `zone_code` (not full
`zone_standards` — that's G's job). Of the ~53 I-gap rows, 29 already had complete address/geo/value/parcel_id
and were missing only zoning-card linkage. Discovered and used **two live, unauthenticated Miami-Dade ArcGIS
FeatureServer layers** on org `8Pc9XBTAsYuxx9Ny`:
- `ZonepolyU_gdb` (unincorporated county zoning polygons) — point-in-polygon by lat/lon, 11 real hits inserted
  under `jurisdiction_id=626` ("Miami-Dade County (Unincorporated)").
- `MunicipalZone_gdb` (newly discovered this session — countywide incorporated-municipality zoning) — 14 more
  real hits across Palmetto Bay, Doral, Miami Beach, Hialeah, Miami Gardens, Sweetwater, Miami, Coral Gables.

25 real, live-sourced `parcel_zones` rows inserted (`source` tagged `miami_dade_arcgis_zonepolyu_live_verified`
/ `miami_dade_arcgis_municipalzone_live_verified`). `card_complete` moved 570→596 of 623 (91.5%→95.7%). 2 rows
correctly deferred, not fabricated: Biscayne Park (real `ZONE=R-2` hit, but no `jurisdictions` row exists for
Biscayne Park — FK blocker, out of scope to create one this session) and Aventura (ArcGIS returned literal
`ZONE='NONE'`, a real feature match but not a usable zone code). Audit id 19332 (fix), independently
re-verified by refuter (5/25 insert ids spot-checked, both deferrals confirmed legitimate), survived=true.

### ⚠️ Side effect / new regression — miami_dade G dropped 98.8% → 50.0% (FAIL)

The 25 newly zone-code-linked parcels have no matching `zoning_districts`/`zone_standards` rows, so G's
density/FAR/parking-per-1000 coverage percentages dropped (`pk1000` now the binding constraint at 50.0%). This
was **explicitly out of scope for the I task** ("that is G's job, do not over-build") and was correctly flagged
by both the fix agent and the refuter rather than hidden. G was not one of miami_dade's 3 target-failing letters
in this dispatch's brief (it was passing at 98.8% going in) — this is a genuine, disclosed net-new regression
caused by this session's I fix, not a pre-existing issue.

**Follow-up required (flagging per the "any regression = P0" reconciliation principle):** a future miami_dade
session must backfill real, ordinance-sourced `zone_standards` (density/FAR/parking) for the ~18 zone codes
newly introduced this session (`EU-M`, `RU-4`, `RU-2`, `RU-3M`, `RU-1`, `RU-1MA`, `E-1`, `MF-1`, `RM-1`, `RDD`,
`R-1`, `RM-15`, `RS-4`, `T3-R`, `MXE`, `T3-O`, `SFR`, `T6-48A-O`) across the relevant jurisdictions, per the
same honesty-marker discipline used for the brevard G hit-list (real ordinance text only, no guessed values).
Net letter movement this session is still positive (+2: C, D, I fixed vs. −1 G regressed), but G is not
currently passing.

## Fleet-wide net result this session

10/10 (10/10 gadsden) + 9/10 (lafayette) + 9/10 (st_lucie) + 8/10 (madison) + 9/10 (miami_dade) = **45/50**
letters passing across the shard, up from an incoming 43/50. Every non-move (lafayette C, st_lucie C, madison
B/F) is a freshly live-reconfirmed canon-block or genuine data ceiling, not an unexamined gap — each carries a
`survived=true` adversarial audit row with live evidence.

## Guardrail compliance

- No `parity_status` reclassified on any genuinely-cancelled/redeemed row (lafayette, st_lucie, gadsden).
- No PropertyOnion data written into `sold_amount`/`winning_bidder`/an "independent" outcome anywhere.
- No fabricated parcel_id, zone_code, or sold_amount — every write traces to a live source queried this session
  (RealForeclose AJAX feed, Miami-Dade ArcGIS FeatureServer, Lafayette/St Lucie clerk sources).
- `pencil_dod_evaluate_county`, cron jobs 109/111/115, and the gold-standard-loop scoring jobs were not touched.
- `public.gold_standard_loop()` / `public.gold_standard_certify()` were **not** run — 4 other shard dispatches
  (`f1d54876`, `10b00370`, `6a1c7256`, `8b9aa985`) were confirmed launched at the identical 08:00:00Z timestamp,
  i.e. concurrently mid-flight, per this shard's own PARALLEL-FLEET RULES. Only per-county
  `pencil_dod_evaluate_county` calls were used for verification.
- All 6 fix claims carry independent `survived=true` adversarial refuter verdicts, each logged as a row in
  `gold_standard_ultraloop_audit` with live re-derived evidence (audit ids 19302, 19304, 19312/19313, 19320–19330,
  19332, 19366/19367, plus refuter-side inserts 19377/19378).
- `gold_standard_campaign` row (id 5289, this dispatch) closed out: `criteria_passed` per-county per-letter JSON,
  `criteria_total=10`, `exit_reason='timeout'`, `session_end_at` set.

## Next-session priorities for this shard's counties

1. **miami_dade G** — backfill real ordinance-sourced `zone_standards` for the ~18 new zone codes (see list
   above) to restore G, ideally without disturbing the newly-fixed I linkage.
2. **miami_dade C/D residual** — 29 of the original 36 auction_url-NULL rows remain unfixed (2026-08-26 tax_deed
   x6, 2026-08-31 foreclosure x19, 2026-09-01 foreclosure x2, +1 more 08/24 case); same
   backfill-URL-then-litmus-check pattern applies directly, paginating the RealForeclose/RealTaxDeed AJAX grid
   per remaining auction date.
3. **lafayette C / st_lucie C / madison B/F** — no further session time should be spent re-diagnosing these;
   all three are freshly (2026-08-29) confirmed canon-blocks/genuine ceilings with live evidence. Re-litigating
   them without new source material would be wasted effort per the ULTRALOOP false-positive ledger principle.
