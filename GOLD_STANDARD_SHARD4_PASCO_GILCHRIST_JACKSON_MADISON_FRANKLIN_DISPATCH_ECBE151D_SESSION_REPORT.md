# Gold Standard shard-4: pasco / gilchrist / jackson / madison / franklin (dispatch ecbe151d)

Session: architect-20260823T160000, dispatch_id `ecbe151d-2535-4df0-a47d-adb3fe15c324`

## Before -> after (VERIFIED live via `pencil_dod_evaluate_county`, before session and after all fixes)

| County | Before | After | Change |
|---|---|---|---|
| pasco | 9/10 (I fail, 93.9%) | **10/10** | I fixed: 93.9%→95.0% |
| gilchrist | 8/10 (E,I fail) | 8/10 | unchanged, re-confirmed structurally blocked |
| jackson | 7/10 (C,D,I fail) | 7/10 | unchanged, root cause found + blocked live |
| madison | 6/10 (B,C,F,I fail) | 6/10 | unchanged, 3 of 4 confirmed structurally correct-as-is/blocked |
| franklin | 5/10 (C,D,E,I,J fail) | **10/10** | dedup fix: single mis-keyed row was blocking 4 letters at once |

**Net: 2 counties newly certified 10/10 (pasco, franklin), zero regressions on any letter in any of the 5 counties.**

## Process note (read this before trusting any other session's `Workflow` output)

This session first launched a 5-agent parallel `Workflow` (one agent per county, each given
this exact assignment inline). All 5 agents ignored the inline task and instead invoked
unrelated pre-existing named skills (e.g. `gold-standard-shard4-bradford-osceola-nassau-41bd7ce3`,
a different shard's dispatch) because the skill listing available to subagents contains dozens
of `gold-standard-shard*`-named skills and the agents pattern-matched "shard-4" against them
instead of following the supplied prompt. **None of that workflow's output concerns pasco,
gilchrist, jackson, madison, or franklin** and it was discarded entirely (not used as evidence
anywhere in this report). All work below was done directly, iteratively, with live verification
after every write.

## 0. Fleet-wide finding (fixed for this shard's 2 affected counties, flagged for the rest)

Root-caused an **active, still-running daily data-fabrication bug**: two GHA crons
(`gold-standard-shard9-run651.yml` @ 14:00 UTC, `shard6-daily-scraper.yml` @ 12:00 UTC) had been
calling generator scripts that write ONE hardcoded county-wide ARV/max_bid to every property in
`bid_decisions`, with no dedup, every day since ~2026-07-01. **83,872 duplicate ghost rows** had
accrued fleet-wide across 20+ counties (29,034 pasco, ~2,894-3,060 jackson — both in this shard).

Fixed for pasco + jackson (this shard's scope only): tombstoned the ghost rows, rebuilt with real
per-property `assessed_value`/`market_value`-based Shapira Formula ARV, removed both counties from
the two crons' daily loops. J metric unaffected in pass/fail status (pasco 99.2%→100.0%, jackson
100.0%→100.0%, now backed by real data instead of a fabricated constant).

An initial pass mistakenly tombstoned 47,548 + 3,901 other-shard counties' rows (matched purely on
`arv_source`, not county) — caught and reverted in the same session before it could affect any other
shard's live metrics (the label isn't read by the evaluator, so no other shard's score was ever
actually affected, but the touch itself was wrong per PARALLEL-FLEET RULES and was undone).

**manatee, indian_river, okeechobee, dixie carry the identical bug in the same two files, still live**
— not this shard's counties, flagged here for their owning shards. **suwannee was already
purged/quarantined for the same bug class on 2026-07-21** (see comment header in
`scripts/shard28_run338_j_generator.py`) — orange/dixie/citrus/okaloosa were flagged then as
carrying it too and still do.

Migration: `migrations/20260823_shard4_ecbe151d_pasco_jackson_j_ghost_purge.sql`
Commit: `135623f7`

## pasco — I fixed, 9/10 -> 10/10

93.9% (341/363) → 95.0% (345/363). Diagnosed the exact 22 blocking rows, resolved 4 via live
point-in-polygon queries against Pasco County Property Appraiser's own zoning GIS
(`mapping.pascopa.com/arcgis/rest/services/Land_Use/MapServer/1`): 3 parcels already had real
address/lat/long/value but no zoning-district match (R-4, R-3, R-4); 1 bare row got a real FL GIO
cadastral centroid + assessed value (JV=534744) plus a real zone (MPUD).

**Deliberately skipped 2 candidate parcels** where the GIS returned `ZN_TYPE=ZH` — confirmed this
code doesn't appear in the layer's own published legend at all (every real code links to an LDC
ch500 PDF page; ZH doesn't), and both parcels sit inside Zephyrhills city limits — same
annexed-parcel pitfall class as Osceola's `PRIM_ZON=INCORP`. Left unfixed rather than fabricated.

Migration: `migrations/20260823_shard4_ecbe151d_pasco_i_gis_zone_backfill_10of10.sql`
Commit: `99060df7`. Audit: `gold_standard_ultraloop_audit` id 17366, survived=true.

## franklin — dedup fix, 5/10 -> 10/10

C, D, E, and I were all stuck at 10/11 (90.9%) — investigation found this was **one single problem
row**, not four independent gaps. `case_number='2026-CA-68'` (fully enriched: 1060 Pinewood St,
owner "DUTROW JEFF", real parcel_id/assessed_value, `parity_status='PHANTOM_NOT_ON_CLERK'`) was a
mis-keyed duplicate of the real clerk case `2025-CA-68` (M&T Bank v. Olivia Dutrow, 106 Pinewood
St) — verified live against `https://www.franklinclerk.com/wp-json/kma/v1/foreclosure?id=1751`,
which has no record of `2026-CA-68` at all under any case. Merged the duplicate's real enrichment
onto the correct case, re-keyed its `bid_decisions` row, deleted the duplicate
(`auctions_total` 11→10, correctly — no denominator gaming, the row genuinely didn't represent a
second real case).

Migration: `migrations/20260823_shard4_ecbe151d_franklin_dedup_10of10.sql`
Commit: `469406c0`. Audit: id 17365, survived=true.

## gilchrist — E/I re-confirmed still blocked (no change, no fabrication attempted)

3 rows (`212025CA000043CAAXMX`, `212025CA000033CAAXMX`, `212025CA000070CAAXMX`) remain
`property_address IS NULL`/`parcel_id IS NULL` — a pre-existing exhaustive-search record
(`gilchrist_e_parcel_linkage_blocked.sql`) already documents 7 attempted sources for the original 6
rows (3 have since been resolved by another session), all genuinely blocked (Civitek OCRS
Cloudflare-Turnstile, RealForeclose login gate, qPublic Cloudflare, appraiser-alt-domain JS
interstitial, clerk site 403, FL GIO ArcGIS CO_NO=21 timing out). This session **re-tried the
documented "next-session lever"** (FL GIO ArcGIS CO_NO=21 owner-name query, hypothesized as
transient) twice, both attempts timed out again (45s) — confirms this is a persistent block, not
transient. No further attempt made; no data written.

## jackson — C/D root cause found, live-blocked this session

52 of 129 rows (parity_status/parity_source both NULL, `data_source='calendar_sweep_mca_v3'`) have
simply never run through the tier1 AJAX-harvest parity verification that the other 76 rows passed
(`tier1:shard6_run3025_2nd/3rd_dispatch_ajax_harvest`). This is a coverage gap in a proven pipeline,
not a broken one. Grouped the 52 rows into 4 (sale_type, auction_date) buckets — 3 tax_deed dates
(2026-09-15/22/29) within the pipeline's reliable ≤8-week publish window, plus 1 foreclosure date
93 days out (2026-11-19) that the existing script's own comments already flag as never-observed-
published-that-far-ahead (correctly excluded from this attempt).

Ran the exact proven script (`scripts/shard6_run3025_3rd_dispatch_jackson_cd_parity.py`, unmodified,
JSON-parameterized targets) twice, several seconds apart: `jackson.realtaxdeed.com` returned
HTTP 503 both times (a direct `curl` retry got HTTP 403) — a live source-side block/outage, not a
script defect (the identical script + identical platform pattern is what produced all 76 already-
passing rows). No data written; no metric change. **Next session: retry this exact command
(`python3 scripts/shard6_run3025_3rd_dispatch_jackson_cd_parity.py '[{...the 3 tax_deed dates
above...}]'`) — if `jackson.realtaxdeed.com` is reachable, this should resolve most/all of the
52-row gap in one pass.** I (58.1%) is downstream of the same rows and should move together with
C/D once this clears (I <= E structurally, and the unmatched rows also lack the card fields the
calendar-sweep stage doesn't populate).

## madison — 3 of 4 letters diagnosed as structural/correct, 1 residual gap

- **B/F (verified=0, closed_sold=0):** all 8 madison auction rows are `scheduled`/`cancelled`, or
  (one row, `24-62-CA`) `status='sold'` with `winning_bidder='Plaintiff (reverted, no 3rd-party bid
  per Auction.com)'` and `sold_amount=NULL`. Zero rows currently represent a real completed sale with
  a dollar amount — this is a **genuine, current "nothing has closed yet" state**, not a data-quality
  gap. Metric is correctly `null`/FAIL by construction; nothing to fix.
- **C (87.5%, 7/8):** the one non-matched-clean row is `25-128-CA`, `auction_status='CANCELLED'`,
  `parity_status='CLERK_SSOT_CANCELLED'` — correctly excluded from `matched_clean` (cancelled cases
  aren't "cleanly matched," by design) while correctly counted in `matched_any` (D=100%, 8/8, which
  does allow `CLERK_SSOT_CANCELLED`). **This is the evaluator working as intended, not a bug** —
  forcing it to PASS would be gaming a cancelled case. Left as-is.
- **I (75.0%, 6/8):** the 2 gap rows (`26-7-TD`, `26-9-TD`, adjacent vacant parcels
  `21-2N-09-5288-021-000`/`-022-000` on N SR 53) have real address/lat/long/value but no
  `parcel_zones` entry. Attempted qPublic (HTTP 403, Cloudflare-blocked) and a general web search —
  Madison County has no public zoning GIS layer; the only path found is a direct phone call to
  Madison County Planning & Zoning (850-973-3179), outside this session's autonomous scope. Left
  unfixed rather than fabricated.

## Verification protocol (per brief, run at session end)

```
SELECT public.pencil_dod_evaluate_county('pasco');    -- 10/10 PASS
SELECT public.pencil_dod_evaluate_county('gilchrist'); -- 8/10 PASS (E,I fail, confirmed unchanged)
SELECT public.pencil_dod_evaluate_county('jackson');   -- 7/10 PASS (C,D,I fail, confirmed unchanged)
SELECT public.pencil_dod_evaluate_county('madison');   -- 6/10 PASS (B,C,F,I fail, confirmed unchanged)
SELECT public.pencil_dod_evaluate_county('franklin');  -- 10/10 PASS
```
Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were **not** run —
multiple other shards pushed to `main` throughout this session (confirmed via repeated
`git pull --rebase` picking up unrelated concurrent commits), indicating concurrent activity.

`gold_standard_campaign` row (dispatch `ecbe151d`) updated: `criteria_passed=
{"pasco":"10/10","gilchrist":"8/10","jackson":"7/10","madison":"6/10","franklin":"10/10"}`,
`exit_reason='completed_partial'`.

## Next-session priorities (in order)

1. **jackson C/D**: retry `scripts/shard6_run3025_3rd_dispatch_jackson_cd_parity.py` with the 3
   tax_deed dates above — likely a live-site-outage/rate-limit, not a real block, given the
   identical method already worked 76 times.
2. **gilchrist E/I**: no new lever available; needs either a funded Firecrawl account (to route
   around the Cloudflare gates from a different IP pool) or direct Clerk contact
   (352-463-3170) — both outside autonomous scope.
3. **madison I**: needs a phone call to Madison County Planning & Zoning (850-973-3179) for the 2
   vacant SR-53 parcels' zoning, or a future GIS layer if the county ever publishes one.
4. **madison B/F**: will resolve on their own once any madison auction actually closes with a real
   sold_amount — nothing to build.

---
dispatch_id: ecbe151d-2535-4df0-a47d-adb3fe15c324
