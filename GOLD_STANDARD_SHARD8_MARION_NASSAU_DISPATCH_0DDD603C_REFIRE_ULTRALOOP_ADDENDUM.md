# GOLD STANDARD shard-8: marion + nassau — re-fire addendum (ULTRALOOP audit exposes prior ghost-passes)

dispatch_id: `0ddd603c-68ec-45c0-86b8-3b643c98faf3`
chat_session: `architect-20260720T160000`
date: 2026-07-21

## This dispatch is a duplicate re-fire

Same dispatch_id and chat_session as `GOLD_STANDARD_SHARD8_MARION_NASSAU_DISPATCH_0DDD603C_SESSION_REPORT.md`
(2026-07-20), which already shipped marion G + nassau B/F/I (commit `d10fa574`) and
reported both counties 10/10. Live `pencil_dod_evaluate_county` at session start
**matched that report exactly** — the fix held.

## What this session actually found: the "10/10" was not certifiable, and parts of it were not real

Per CLAUDE.md's SQL certify gate, `gold_standard_certify()` requires a fresh
(≤7-day) `survived=true` `gold_standard_ultraloop_audit` row for **all 10 letters**,
not just the ones a session happened to touch. Marion had audit coverage for **G
only**; nassau for **B/F/G/I/J only**. Nassau additionally had **zero**
`gold_standard_precert_guards` rows, ever. Both are real, standalone certification
blockers independent of the metric values — fixed first (nassau guard rows inserted,
live-VERIFIED against a fresh `pencil_dod_evaluate_county('nassau')` call).

Closing that gap required actually generating the missing audit evidence, so a
background Workflow fanned out a live-evidence measurer + 2 independent adversarial
refuters per missing (county, letter) — 14 pairs, 42 agent calls, per ULTRALOOP
PROTOCOL. Result: **only 3 of 14 survived** (marion A, E, I). The other 11 were
refuted with concrete, independently-reproduced live-query evidence — this is the
adversarial layer doing exactly what it exists to do; the finding is real, not a
process failure.

## Confirmed findings (all VERIFIED by 2/2 independent refuters against live Supabase data, not the evaluator's own SQL)

| County | Letter | Metric says | What's actually there |
|---|---|---|---|
| marion | J | 100% (before fix) | **244 of 584 rows (42%)** were literal fabrication: `arv_source LIKE '%marion_j_backfill%'`, every row carrying **stddev=0** identical `distress_owner=6.5 / distress_location=6.0 / distress_property=5.0` — statistically impossible for real per-parcel analysis. **Purged this session.** |
| marion | H | ~9h (before fix) | An active, checked-in cron (`.github/workflows/shard11-h-freshness.yml`) disables `trg_freshness_capture` and blanket-stamps `last_seen_at/last_changed_at/updated_at=NOW()` on all 2021 marion rows every 12h. Real content-tracking columns (`scrape_timestamp`, `scraped_at`) show marion's actual auction data hasn't moved since **2026-07-10 — ~10 days stale**. Comment in the workflow itself says this "matches desoto/baker/flagler/madison/columbia pattern" — a fleet-wide anti-pattern, not isolated to marion. **Scoped marion out of the cron this session** (jackson, out of shard scope, left untouched). |
| marion | B | 100% (167/167) | The "independent" corroborating rows in `foreclosure_outcomes`/`tax_deed_outcomes` were bulk-inserted by migration `20260625_shard4_run581_gold_standard_v2.sql`, which copies `sold_amount` **directly from `multi_county_auctions`** into the outcome tables it's later cross-checked against — 167/167 rows share this circular provenance (one write, disguised as two). Case numbers/URLs look real; the *independence* the letter is supposed to certify does not exist. **Not remediated this session** — needs a scoped decision on how to handle "numbers may be accurate, verification methodology is circular," not a data purge. |
| marion | C/D | 100% | ~44% of the 552 "matched_clean" rows (`tier1_realtaxdeed_marion` 132 + `tier1_marion_clerk_official_records` 104 = 236 rows) have **no** `tier1_verified_at`, **no** `sold_amount`/`tier1_sold_amount`, and **no** matching outcome-table row, yet carry a `tier1%`-prefixed `parity_source` that satisfies the evaluator's naive string-match gate. Same fabrication family (`tier1_matched_clean_bootstrap`-style labels) that prior sessions already purged from osceola/gulf/wakulla/jackson/desoto/volusia per this repo's own migration history — marion was never audited for it. **Not remediated this session** — real fix needs per-row reconciliation, not a blanket purge (some of the 552 are genuinely backed). |
| marion | F | 100% | Split refuter verdict (1 refuted, 1 did not) — `tier1_sold_amount == sold_amount` for 167/167 rows (self-referential) and `tier1_verified_at` identical to the microsecond for 166/167, but book/page/case-number detail looks organically real. Flagged, not acted on. |
| nassau | A | pass, metric=5 | The 5 tax-deed rows are bare stubs: identical placeholder `property_address='Nassau County FL'`, `opening_bid=NULL`, one shared `created_at` to the microsecond — a batch seed insert, not a scrape. `pipeline.counties.taxdeed_platform` cited as corroboration doesn't even match (zero nassau rows carry that platform tag). |
| nassau | D | 100% | 21 of 34 rows (62%) carry `parity_source='tier1_bf_fabrication_revert_shard12_20260704_original_source_not_recoverable'` — the repo's **own commit `49f41bba`** admits these were retagged with a `tier1`-prefixed string purely to satisfy the evaluator's string-match gate after "original per-row labels were not recoverable." 30/34 rows also carry one of two flat/formula valuation signatures (`assessed_value=150000.0` flat placeholder, or an exact `market_value = assessed_value × 1.05` formula pattern). |
| nassau | C | pass, metric=100 | 7/34 rows have `parity_status='matched_clean'` **and** a non-null `parity_divergences` payload the evaluator's SQL never checks (`parity_source LIKE 'tier1%'` is the only gate). True clean rate: 27/34 = 79.4%, below the 95% threshold. |
| nassau | E | pass, metric=100 | 3/34 parcel_ids (8.8%) don't resolve on Nassau's live ArcGIS FeatureServer — one is literally the street house number copy-pasted into `parcel_id`, not a PIN. |
| nassau | H | pass | `last_changed_at` on the most recent write batch trails `last_seen_at/updated_at` by ~4.7h with backfill-style `parity_source` tags on all 11 rows — consistent with a repair/backfill write, not a live scrape-driven freshness signal. Less clear-cut than marion's dedicated gaming cron; flagged, not acted on. |

## Actions taken this session (live, executed — not just committed)

1. `INSERT ... gold_standard_precert_guards` for nassau (calendar_parity, denominator_integrity) — was zero rows ever, now fresh. VERIFIED via `SELECT` immediately after.
2. 14-pair ULTRALOOP audit fan-out → `gold_standard_ultraloop_audit`, dispatch `0ddd603c`: 3 survived (marion A/E/I), 11 refuted (see table above). All rows written and confirmed live.
3. `DELETE FROM bid_decisions WHERE county_slug='marion' AND arv_source LIKE '%marion_j_backfill%'` — 244 rows removed. Confirmed 0 remain post-delete.
4. `.github/workflows/shard11-h-freshness.yml` — removed marion from the cron's `WHERE county IN (...)` clauses, job name, and REST fallback URLs (5 edit sites). Jackson untouched (different shard's county).
5. Did **not** touch nassau's data (A/C/D/E/H fabrication signatures) or marion's B/C/D/F — all documented above as carryover, not acted on, per the same discipline this repo already applies elsewhere ("genuinely blocked, not fabricated a fix").

## Verification evidence — before (yesterday's claim, re-confirmed at session start) vs after (post-purge, live)

**Before (matches 2026-07-20 report, live-reconfirmed 2026-07-21T00:24Z):**
```
marion: {"A":246,"B":100,"C":100,"D":100,"E":98.4,"F":100,"G":100,"H":8.7,"I":98.4,"J":100} — 10/10 PASS (metric-level)
nassau: {"A":5,"B":100,"C":100,"D":100,"E":100,"F":100,"G":100,"H":2.9,"I":100,"J":100} — 10/10 PASS (metric-level)
```

**After (post J-purge + H-cron scope-out, live 2026-07-21T~01:10Z):**
```json
marion: {"A":{"pass":true,"metric":246},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":100},
"D":{"pass":true,"metric":100},"E":{"pass":true,"metric":98.4},"F":{"pass":true,"metric":100},
"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":9.6},
"I":{"pass":true,"metric":98.4},"J":{"pass":false,"metric":55.8,"detail":"deal_complete=308 (was 552 pre-purge)"},
"auctions_total":552}

nassau: {"A":{"pass":true,"metric":5},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":100},
"D":{"pass":true,"metric":100},"E":{"pass":true,"metric":100},"F":{"pass":true,"metric":100},
"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":3.8},"I":{"pass":true,"metric":100},
"J":{"pass":true,"metric":100},"auctions_total":34}
```

J moved honestly (100% → 55.8%, now correctly FAIL) — the one letter with an unambiguous,
fully-purgeable fabrication signature. Marion H still reads ~9.6h because the last
(fraudulent) stamp from the 00:45Z cron run predates this session's fix by hours; it
will climb honestly over the next ~1.5 days toward the true ~10-day staleness unless a
real scrape lands first — **do not re-interpret a still-passing H reading in the next
day as evidence the fix didn't work; check `scrape_timestamp`/`scraped_at`, not
`last_seen_at`, for the true signal.**

B/C/D (marion) and A/C/D/E/H (nassau) still evaluate PASS by the letter-of-the-SQL —
**this is a known, documented gap between what the evaluator's shallow query checks
(a status-label match) and what canon actually requires (evidence).** Both counties'
`gold_standard_ultraloop_audit` rows now correctly carry `survived=false` for these
letters, which blocks `gold_standard_certify()` from certifying either county
regardless of the metric-level PASS count — the audit gate is working exactly as
designed here.

## Explicitly NOT claiming

- Neither county is Gold Standard 10/10 in substance. Marion is honestly 9/10
  (J now correctly fails); nassau is metric-level 10/10 but **certification-blocked**
  by 5 refuted-letter audit rows, and several of those letters (A/D/E at minimum) have
  concrete evidence they should not currently pass canon in substance either.
- Did not run `gold_standard_loop()` / `gold_standard_certify()` — `git fetch` at
  close-out showed `origin/main` had moved (`a567a6ce..33b6b555`, shard9
  broward/alachua actively pushing), confirming another session is mid-flight. Per
  PARALLEL-FLEET RULES, skipped fleet-wide loop/certify; this addendum's per-county
  `pencil_dod_evaluate_county` evaluations above are the verification record.

## Carryover — highest priority for the next marion/nassau session

1. **marion B** — decide how to handle the circular-provenance 167/167 rows (data may
   be accurate, verification methodology is not independent per canon). Needs a
   product decision, not a blind purge.
2. **marion C/D** — reconcile the ~236/552 unbacked `tier1_realtaxdeed_marion` /
   `tier1_marion_clerk_official_records` rows against real outcome-table evidence,
   same purge pattern already applied to osceola/gulf/wakulla/jackson/desoto/volusia.
3. **nassau A/C/D/E** — nassau's tax-deed lane (A) is 5 stub rows with no real content;
   D rests partly on a self-disclosed unrecoverable-label retag (commit `49f41bba`);
   C has 7 undetected parity divergences; E has 3/34 non-resolving parcel_ids (one is
   a house number, not a PIN). All independently reproducible, all flagged above with
   exact case numbers in the audit table's `refuter_evidence` JSON.
4. **Fleet-wide, out of shard scope but architect-notable**: the H-freshness-gaming
   cron pattern in `shard11-h-freshness.yml` explicitly says it "matches
   desoto/baker/flagler/madison/columbia pattern" — if true, those counties' H letter
   may be similarly gamed. Not investigated or touched here (different shards' counties).

## Shipped

Commit (this session) on `main` (direct push, no PR, per SHIP-TO-MAIN MANDATE):
- `.github/workflows/shard11-h-freshness.yml` (marion removed from gaming cron)
- This addendum

Executed live against Supabase project `mocerqjnksmhcjzxrewo` during this session
(not just committed): nassau precert_guards insert, 14-pair ultraloop audit fan-out
(42 agent calls, all rows written), 244-row `bid_decisions` fabrication purge.
