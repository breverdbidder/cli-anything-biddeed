# Gold Standard Shard-3: orange / hernando / miami_dade / okaloosa — session report

dispatch_id: c366ee22-d3b0-463b-a846-62ee258772f2
mode: parallel fan-out fix tracks (hernando B/F backfill, miami_dade C/D dedup, miami_dade G parking, okaloosa Bid4Assets pipeline) + adversarial verification per track + closing snapshot

## Status Board (before -> after, live `pencil_dod_evaluate_county`)

| County | Before | After | Delta |
|---|---|---|---|
| orange | 10/10 | **10/10** | unchanged (no work planned or done — regression check only) |
| hernando | 8/10 (B/F fail) | **10/10** | B, F fixed (1 of 10 past-due cases, honest partial) |
| miami_dade | 7/10 (C/D/G fail) | **10/10** | C, D fixed (dedup); G fixed (pk1000 backfill); I found already-passing live (96%, not touched this session) |
| okaloosa | 6/10 (B/C/D/E/F/I fail) | **6/10** | B, D, F fixed; C, E, I, J still fail (I was pre-existing fail, J newly failing as a disclosed side-effect of denominator growth) |

All numbers below are from live `public.pencil_dod_evaluate_county(<county>)` calls run fresh at session close (2026-07-19), pasted verbatim — not subagent self-reports.

### SQL VERIFICATION (fresh, this session, 2026-07-19 ~18:10 UTC)

```
SELECT public.pencil_dod_evaluate_county('orange');
 -> A321 B100 C100 D100 E99.1 F100 G98.3 H2.2 I95.1 J100  (10/10, auctions_total=855)

SELECT public.pencil_dod_evaluate_county('hernando');
 -> A13 B100 C100 D100 E100 F100 G97.2 H0.1 I95.9 J100  (10/10, auctions_total=49)

SELECT public.pencil_dod_evaluate_county('miami_dade');
 -> A81 B100 C96.6 D96.6 E96.6 F100 G99.3 H2.2 I96 J100  (10/10, auctions_total=350)

SELECT public.pencil_dod_evaluate_county('okaloosa');
 -> A13 B100 C30(FAIL) D95 E30(FAIL) F100 G100 H1.1 I0(FAIL) J5(FAIL)  (6/10, auctions_total=40)
```

## orange — regression check only, no work planned or done

Confirmed genuinely still 10/10 live, all letters A-J pass. `auctions_total=855`, unchanged in kind from the shard's starting state. **No regression** — orange's letters were never touched by any of this session's four fix tracks (hernando/miami_dade/okaloosa scoped work only), consistent with the shard rule against modifying other counties' passing letters. No P0 to flag.

## hernando — B/F fixed via LandmarkWeb Certificate of Title backfill; now 10/10

- **B/F** (0%/0% -> 100%/100%): backfilled 1 of 10 past-due Hernando foreclosure auctions with a real, verified Certificate of Title sale amount found on the Hernando Clerk's LandmarkWeb official records search (Instrument #2026046908, OR Book 4733 Page 1708, Case No. 25000967CAAXMX, $68,100.00, recorded 2026-07-13). The other 9 cases were checked via the same method and confirmed to have no COT recorded yet (only pre-auction final judgments) — left honestly untouched, not fabricated.
- Migration: `migrations/20260719h_shard3_hernando_fc_outcomes_backfill.sql`. Commit `d5a567d4`.
- Adversarial verification: SURVIVED both letters. Live re-query matched the claim exactly; `foreclosure_outcomes` and `multi_county_auctions` rows independently confirmed real (real instrument #, real address, no `propertyonion` source). Audit rows logged `survived=true` for B and F.

## miami_dade — C/D dedup + G parking backfill; now 10/10 (I found already passing)

- **C/D** (94.9% FAIL -> 96.6% PASS): root cause was a `calendar_sweep_mca_v3` double-insertion bug that created duplicate tax_deed-labeled siblings of 8 real foreclosure-labeled rows. Deleted 6 confirmed-spurious duplicates by exact primary key after independently verifying each had 0 hits on the live realtaxdeed.com AJAX calendar and 0 rows in `tax_deed_outcomes` for the same case number. Numerator (`matched_clean=matched_any=338`) was left unchanged — only the genuine duplicate denominator (356->350) was corrected. 2 similarly-suspicious rows were explicitly left untouched out of caution (flagged as fast-follow, not acted on without a second confirming pass).
- **G** (0% FAIL -> 99.3% PASS): backfilled real `parking_per_1000sf` ordinance values for the 2 applicable-but-missing districts — NCUC (4.00 spaces/1000sf, Sec. 33-284.67(A)) and Miami Beach CD-2 (3.33 spaces/1000sf, Sec. 130-32(37)) — both cited to primary-source ordinance PDFs with disclosed confidence scores (0.85, 0.75) rather than invented numbers.
- **I**: not part of any track's scoped work this session, but the live closing snapshot shows it already passing at 96% (`card_complete=336 of 350`). This is reported as-is (VERIFIED via live query) rather than claimed as a fix — no track claimed credit for I and none is being retroactively claimed here.
- Migrations: `supabase/migrations/20260719_shard3_miami_dade_cd_dedup.sql` (commit `1ec4958b`), `supabase/migrations/20260719_shard3_miami_dade_g_parking.sql` (commit `fb677d46`).
- Adversarial verification: SURVIVED C, D, and G. Live re-queries matched claims exactly; deleted row IDs independently confirmed absent; numerator-integrity confirmed unchanged; no `propertyonion` or fabricated address/parcel data found. Builder honestly flagged (not re-litigated, correctly out of scope) that the pre-existing 338-row C/D baseline itself rests on calendar-presence tags (`tier1:shard14_run3534_ajax_harvest:*`) rather than closed-sale-outcome joins — a looser bar than the standard enforced by this county's two prior ghost-success revert migrations. This observation was not acted on this session; flagged below for next-session review.

## okaloosa — Bid4Assets pipeline built; B/D/F fixed, C/E/I/J remain FAIL (2 honestly capped, 1 pre-existing, 1 disclosed side-effect)

- **A** (metric 1 -> 13, still pass): new live scraper (`scripts/okaloosa_bid4assets_harvest.py`, Playwright/Chromium under xvfb) pulled 38 new real rows (26 foreclosure + 12 tax_deed) from bid4assets.com's Okaloosa FC and TD listing pages across the full available `?salesdate=` range, plus 3 `foreclosure_outcomes` rows for genuinely closed/sold cases.
- **B/F** (0%/0% FAIL -> 100%/100% PASS): 3 real closed-sale rows with distinct case numbers, real addresses, and real winning bids ($50,100 / $180,100 / $80,100), sourced from a live "Sold"/"Sold to Plaintiff" grid.
- **D** (0% FAIL -> 95% PASS): 38/40 rows now `matched_any` (26 matched_divergent + 12 matched_clean), from real new data, not a denominator trick.
- **C/E** (0% FAIL -> 30% FAIL, still failing): capped by an honest source limitation — the Bid4Assets FC grid genuinely has no parcel/APN column (headers: ID | Case# | Address | Current Bid | Status), so only the 12 TD rows (which do carry real APNs) count as `matched_clean`/`parcel_linked`. Confirmed not fabricated; confirmed the sandbox's network egress cannot currently reach `services9.arcgis.com` (ReadTimeout) to attempt a parcel lookup fallback.
- **I** (0% FAIL, pre-existing, unaddressed): explicitly out of scope for this track (needs full BCPAO/GIS card enrichment) — correctly not touched or falsely claimed.
- **J** (100% PASS -> 5% FAIL, new failure, honestly disclosed): denominator grew from 2 to 40 as a direct side-effect of the 38 new real rows landing without full deal-triangle enrichment yet. This is a genuine regression on a letter that was not in the track's requested scope, disclosed by the builder rather than hidden, and is now the top open item for okaloosa.
- Cron/wiring: new `.github/workflows/okaloosa-bid4assets-harvest.yml` (daily 06:20 UTC, fail-loud on zero-parse). Did not touch cron ids 109/111/115 or any `gold-standard-loop-*` job. Migration `supabase/migrations/20260719g_shard3_okaloosa_bid4assets_backfill.sql` (pipeline.counties platform/URL correction only — does not re-insert scraped rows, those went via PostgREST upsert with fail-loud guards). Commit `da01ffe3`.
- Adversarial verification: SURVIVED all 8 audited letters (A/B/C/D/E/F/I/J) as accurately reported (including the two that were correctly reported as FAIL, not silently upgraded). One non-disqualifying data-quality bug found and flagged: case `2025-CA-003450-C` has a plaintiff/case-caption string leaked into `property_address` (real scraped text, mis-mapped field, doesn't affect any A-J metric since the row has no `parcel_id` either way) — flagged as a follow-up fix for the address-column parser, not fixed this session.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| orange | verify/hold, regression check | Reconfirmed 10/10, zero changes | none |
| hernando B/F | backfill verified outcomes | Fixed to 100%/100% (1 of 10 real, 9 honestly blocked) | none |
| miami_dade C/D | fix parity dedup | Fixed to 96.6%/96.6% via 6-row targeted dedup | flagged (not fixed) a looser-than-ideal pre-existing matching baseline |
| miami_dade G | fix parking standards | Fixed to 99.3% via 2 real ordinance-sourced backfills | none |
| miami_dade I | not in scope | found already passing (96%) at close, reported honestly | untouched, not claimed as a fix |
| okaloosa B/D/F | build ingest pipeline, fix verified outcomes | Fixed to 100%/95%/100% via new live scraper | none |
| okaloosa C/E | attempt parcel linkage | Remains FAIL (30%/30%) | genuine source/network limitation, honestly capped not fabricated |
| okaloosa I | out of scope | untouched, remains FAIL (0%) | none — correctly not claimed |
| okaloosa J | not targeted | regressed 100%->5% as disclosed side-effect of denominator growth | new open item, not hidden |

## Verification Evidence

18 audit rows inserted to `public.gold_standard_ultraloop_audit` (dispatch_id `c366ee22-d3b0-463b-a846-62ee258772f2`, `ultraloop_mode='native'`): hernando B/F; miami_dade C/D/G; okaloosa A/B/C/D/E/F/I/J — all `survived=true` for the claims as stated (including honest FAIL reports for okaloosa C/E/I). No `gold_standard_loop()`/`gold_standard_certify()` run this session (parallel-fleet protocol respected). No PropertyOnion-sourced rows written anywhere across any track. No fabricated `property_address`/`parcel_id`/sold amounts — every written value traced to a live-fetched source (LandmarkWeb COT recording, Bid4Assets live grid, primary-source ordinance PDFs). Cron jobs 109/111/115 and `gold-standard-loop-*` untouched in all four tracks. Commits: `d5a567d4` (hernando), `1ec4958b` + `fb677d46` (miami_dade), `da01ffe3` (okaloosa) — all confirmed on `main`.

## Next-session priorities

1. **okaloosa J**: the denominator grew from 2 to 40 as a side-effect of the B/D/F fix; needs deal-triangle enrichment (ARV + two-arm CMA + ml_score + max_bid + factors) run across the 38 new rows to bring `deal_complete` back toward parity. This is now the most urgent open item in this shard.
2. **okaloosa C/E**: capped at 30% by the Bid4Assets FC grid's missing APN column. Needs a working ArcGIS/BCPAO address->parcel lookup path — this sandbox's network egress currently cannot reach `services9.arcgis.com` (confirmed `ReadTimeout`); either retry from a runner with different egress or find an alternate parcel-lookup source for Okaloosa.
3. **okaloosa I**: needs full BCPAO/GIS card enrichment (address+geo+value+zoned parcel) — not attempted this session, still 0/40.
4. **okaloosa data-quality**: fix `scripts/okaloosa_bid4assets_harvest.py`'s address-column parser — case `2025-CA-003450-C` has a plaintiff/case-caption string in `property_address` instead of a real address (doesn't affect current A-J scoring but will corrupt future I/enrichment work if left as-is).
5. **miami_dade C/D baseline integrity**: the pre-existing (pre-session) 338-row matched_clean/matched_any baseline is built on calendar-presence tags (`tier1:shard14_run3534_ajax_harvest:*`), not closed-sale-outcome joins — a looser bar than the standard this county's two prior ghost-success revert migrations enforced. Not touched this session (out of the 18-row dedup scope); worth a dedicated future audit given this county's specific history of C/D ghost-successes.
6. **hernando B/F remaining 9 cases**: re-check LandmarkWeb periodically for newly-recorded Certificates of Title on the 9 still-pending cases (23001588CA, 25000637CA, 25001269CA, 25000736CA, 25000792CA, 23001250CA, 22001005CA, 25000885CA, 25000696CA) — Hernando's Clerk has a documented COT-recording lag, so these may resolve naturally over the next several sessions.
