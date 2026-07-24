# Gold Standard Shard-1: indian_river + charlotte — Session Report

dispatch_id: `549b0e98-97ab-48f1-a6ee-193ce66bdb61`
chat_session: `architect-20260724T160000`
loop run: 6253 (brief) → live evaluation + ultraloop audit run 6287 (close-out)
date: 2026-07-24

## Executive summary

Both shard-1 target counties were **already at live 10/10 PASS** at session start — indian_river
was 10/10 in the dispatch brief itself, and charlotte had been brought to 10/10 by a prior same-day
commit (`6360259e`, "C/D/I 91.7/91.7/92.7 → 97.2/97.2/98.2"). No new fixes were required. This
session's work was exclusively **ULTRALOOP adversarial verification** of the standing PASS claims
(per the ULTRALOOP PROTOCOL certify gate) plus the mandatory close-out (loop + certify).

**Result: both counties CERTIFIED (`certified=true`, `consecutive_gold=2`).**

## Before/after — `pencil_dod_evaluate_county` (mandatory verification protocol)

### charlotte

Before (dispatch brief, loop run 6253):
```json
A PASS metric=31 | B PASS metric=100.0 | C FAIL metric=91.7 | D FAIL metric=91.7 |
E PASS metric=100.0 | F PASS metric=100.0 | G PASS metric=97.9 | H PASS metric=0.1 |
I FAIL metric=92.7 | J PASS metric=100.0   →  7/10
```

After (live query, 2026-07-24 ~16:49Z, pre-dating this session's own start — fixed by 6360259e):
```json
{
  "county": "charlotte", "auctions_total": 109,
  "A": {"pass": true, "metric": 31,  "detail": "fc=78 td=31"},
  "B": {"pass": true, "metric": 100, "detail": "verified=18 closed_sold=18"},
  "C": {"pass": true, "metric": 97.2,"detail": "matched_clean=106"},
  "D": {"pass": true, "metric": 97.2,"detail": "matched_any=106"},
  "E": {"pass": true, "metric": 100, "detail": "parcel_linked=109"},
  "F": {"pass": true, "metric": 100, "detail": "tier1_sold=18 closed_sold=18"},
  "G": {"pass": true, "metric": 98,  "detail": "density=98.0 far= pk1000="},
  "H": {"pass": true, "metric": 0.1, "detail": "hours since last_seen (SLA 48h)"},
  "I": {"pass": true, "metric": 98.2,"detail": "card_complete=107 of 109"},
  "J": {"pass": true, "metric": 100, "detail": "deal_complete=109 (...)"}
}
→ 10/10
```

### indian_river

Before (dispatch brief, loop run 6253): already 10/10, all PASS.

After (live query, 2026-07-24 ~16:49Z, unchanged):
```json
{
  "county": "indian_river", "auctions_total": 103,
  "A": {"pass": true, "metric": 37,  "detail": "fc=66 td=37"},
  "B": {"pass": true, "metric": 100, "detail": "verified=18 closed_sold=18"},
  "C": {"pass": true, "metric": 97.1,"detail": "matched_clean=100"},
  "D": {"pass": true, "metric": 97.1,"detail": "matched_any=100"},
  "E": {"pass": true, "metric": 100, "detail": "parcel_linked=103"},
  "F": {"pass": true, "metric": 100, "detail": "tier1_sold=18 closed_sold=18"},
  "G": {"pass": true, "metric": 100, "detail": "density=100.0 far= pk1000="},
  "H": {"pass": true, "metric": 0.1, "detail": "hours since last_seen (SLA 48h)"},
  "I": {"pass": true, "metric": 95.1,"detail": "card_complete=98 of 103"},
  "J": {"pass": true, "metric": 100, "detail": "deal_complete=103 (...)"}
}
→ 10/10
```

## ULTRALOOP adversarial verification (this session's actual work)

Ran a fan-out-and-synthesize workflow (18 agents: 8 find→refute pairs on the historically-risky
letters B/C/D/I across both counties, plus 2 sanity sweeps on A/E/F/G/H/J).

**8/8 find→refute pairs: PASS survives independent adversarial re-derivation from raw tables**, with
one refutation initially flagged, then personally resolved against live data:

- **charlotte B** — refuter claimed 3/18 "verified" outcomes were PropertyOnion-sourced (a hard-fail
  pattern per canon). I re-checked directly: the refuter had queried `multi_county_auctions.data_source`
  (the base auction listing's origin — legitimately `propertyonion` + `tier1_authoritative=true`, which
  the evaluator's own scope filter explicitly permits as an audited promotion) instead of the *outcome
  table's* `data_source` (what B's canon actually gates). Direct query of `foreclosure_outcomes.data_source`
  for all 3 disputed case numbers confirms genuinely independent sources
  (`realforeclose:charlotte`, `tier1:realforeclose_results_report:report18`). **Refutation overruled by
  evidence — B stands confirmed.**
- charlotte C, D, I — refuters found no defect; all numerator/denominator pairs independently
  reproduced exactly.
- indian_river B, C, D, I — refuters found no defect; all independently reproduced exactly.

All 8 corresponding rows written to `gold_standard_ultraloop_audit` (dispatch_id `549b0e98…`,
`survived=true`), satisfying the SQL certify gate's freshness requirement for those letters.

### Residual findings (non-blocking, logged for future work — not DoD violations)

1. **charlotte B data quality**: 2/18 closed auctions (`24001935CA`, `25001360CA`) have
   `sold_amount=0.0` in `multi_county_auctions` despite a matched, verified, nonzero
   `winning_bid` in `foreclosure_outcomes` ($90,100 and $108,200). The evaluator's B check only
   requires `sold_amount IS NOT NULL`, so this doesn't affect the metric, but `sold_amount`
   should be backfilled from the outcome record for accuracy elsewhere in the product.
2. **indian_river I — thin margin, priority**: 98/103 = 95.1% is exactly at the edge; one more
   incomplete row pushes it to 98/104 = 94.2% (FAIL). 2 of the 5 incomplete rows have corrupted
   placeholder strings in `parcel_id` (`"MULTIPLE PARCELS"`, `"Property Appraiser"`) rather than
   real parcel numbers — an upstream ingestion validation bug, not a one-off, likely to recur on
   new rows. Recommend a dedicated fix (reject/flag non-numeric parcel_id at ingestion) before
   this margin erodes.
3. **charlotte I data quality**: 85/109 (78%) of "complete" rows share one identical
   lat/lon pair across 82 distinct real street addresses — a geocoding fallback/centroid, not
   per-parcel geolocation. The completeness check only verifies non-null, not accuracy, so this
   doesn't affect the I metric, but is a quality gap worth a future backfill.
4. **E metric is presence-only, not resolution**: both counties' E ("parcel_linked") counts
   `parcel_id IS NOT NULL`, which is satisfied by the same placeholder strings noted in (2)/(3)
   (2-7 rows per county, well within the 95% margin so not PASS-threatening). A sweep agent's
   claim that "0/8 sampled indian_river parcel_ids resolve to a real parcel" was checked against
   a bare `parcels` table with a mismatched join and conflicts with the I-letter finding that
   98/103 parcels DO resolve through the actual zoning-linked view (`v_zoning_gold_standard_card`)
   — that broader claim is judged an artifact of the ad-hoc check, not confirmed, and is not
   logged as a defect.
5. Audit-hygiene gaps (non-blocking): charlotte C has 6/106 matched_clean rows with no
   `parity_checked_at` timestamp; indian_river C has 4/103 rows with none at all (freshest
   countywide recheck is 13 days old). No evidence of actual data drift, but audit-trail
   completeness should be backfilled from `updated_at`.

None of the above changes any letter's PASS/FAIL status. Logged here per Honesty Protocol so they
aren't silently lost.

## Close-out protocol executed

```
SELECT public.gold_standard_loop();
→ {"rows": 670, "counties": 67, "elapsed_s": 94.8, "loop_run_id": 6287}

SELECT public.gold_standard_certify();
→ {"run": 6287, "certified_now": 18, "revoked_now": 0,
   "blocked": ["broward","flagler","manatee","marion","pinellas","polk","seminole"],
   "guard_blocked": []}
```
(Verified no other session was mid-flight before running the fleet-wide loop: `pg_stat_activity`
showed zero non-idle backend connections and `gha_dispatch_log` showed zero dispatches in the
prior 3 hours.)

`gold_standard_certifications` post-loop:
```json
{"county_slug": "charlotte",     "certified": true, "consecutive_gold": 2, "last_evaluated_run_id": 6287}
{"county_slug": "indian_river",  "certified": true, "consecutive_gold": 2, "last_evaluated_run_id": 6287}
```

**Both shard-1 target counties are CERTIFIED.**

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| indian_river 10/10 | maintain | confirmed 10/10, certified | none |
| charlotte C/D/I fix | fix + verify | already fixed by prior commit 6360259e; verified only | no fix work needed this session |
| ULTRALOOP verify B/C/D/I both counties | required for certify gate | 8/8 survived (1 refutation overruled with direct evidence) | none |
| Close-out loop + certify | conditional on no mid-flight session | ran; both counties certified | none |

## Next-session priorities (none blocking, quality-of-data only)

- Backfill `sold_amount` for charlotte's 2 zero-amount-but-verified-sold rows.
- Ingestion validation: reject/flag non-numeric `parcel_id` values (`"MULTIPLE PARCELS"`,
  `"Property Appraiser"`) at scrape time — currently 2-7 rows per county slip through as
  false-positive E/I linkage.
- indian_river I margin is fragile (95.1%, 1 row from flip) — prioritize a parcel_id data-quality
  pass before new auctions land.
- charlotte I geocoding: 78% of complete rows share one fallback lat/lon — real per-parcel
  geocoding backfill would improve I data quality (not required for PASS).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
