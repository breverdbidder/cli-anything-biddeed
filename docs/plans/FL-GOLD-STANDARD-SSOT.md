# FL GOLD STANDARD — SSOT (A–J, ALL 67 COUNTIES)

**Status date:** 2026-06-09 | **Author:** Claude (AI Architect)
**SSOT:** table `public.pencil_dod_criteria` (database) is the single source of truth for criterion definitions. THIS supersedes any divergent letter definitions in prior docs (incl. the I/J sections of DUVAL-GOLD-STANDARD-DEFINITION-OF-DONE.md, which predate canon consolidation).

## Canon A–J (every FL county must achieve ALL TEN)
| | Criterion | PASS threshold |
|--|--|--|
| A | dual_product_coverage | foreclosure AND tax_deed auctions present |
| B | verified_realized_outcomes ⭐ | ≥95% of closed auctions have an outcome from an INDEPENDENT clerk source (data_source NOT PropertyOnion-derived) |
| C | parity_clean | ≥95% parity_status='matched_clean' |
| D | parity_any | ≥95% matched_clean or matched_divergent |
| E | parcel_linkage | ≥95% auctions linked to parcel_id |
| F | tier1_authoritative_sold | ≥95% of closed have tier1_sold_amount |
| G | zoning | ≥95% on min(density, FAR, pk1000) per v_zoning_gold_standard_kpi_v3 |
| H | freshness | newest activity timestamp ≤48h |
| I | property_card_complete ⭐ | ≥95% with address + geo + value + zoned parcel |
| J | shapira_deal_thesis ⭐ | ≥95% with bid_decisions row: arv + max_bid + ml_score + Shapira Triangle factors + two-arm CMA |

⭐ = critical three (B, I, J). `critical_three_pass` is tracked separately on the scoreboard.

## Loop architecture (v5, set-based)
- `public.gold_standard_loop()` — evaluates ALL 67 counties from ~6 sequential scans (one MCA pass with deal-thesis join folded in; second pass for card candidates; one scan each of outcomes, zoning KPI, zoning card membership). Replaces v4 per-county evaluation (~335 random-read index scans) which exceeded the 2-min statement timeout under I/O contention from the per-minute valuations_comps batch (cron 109).
- Snapshots per-letter PASS/FAIL + metric + detail into `gold_standard_county_status` keyed by `loop_run_id` (seq `gold_standard_loop_run_seq`).
- `gold_standard_scoreboard` view — latest run pivoted per county: a_dual_product … j_deal_thesis, pass_count, gold_standard (10/10), critical_three_pass.
- `public.pencil_dod_evaluate_county(text)` — ad-hoc single-county audit, identical canon logic.
- Cron job 115 `gold-standard-loop`, daily 07:30Z (after the 05:30Z scrape cycle); command sets `statement_timeout=0` first so I/O contention can never abort the run (incident lesson: a timed-out txn also rolled back its own self-unschedule, creating a retry storm).

## Baseline — loop run 1, 2026-06-09 22:08Z (52s)
- 67/67 counties scored. **Gold: 0. Critical-three: 0.** Best county: charlotte (3/10).
- Duval: A PASS (fc/td both present) · B 74.5% · C 14.3% · D 44.2% · E 82.8% · F 3.2% · G no zoning KPI · H PASS (1.3h) · I blocked on zoning coverage · J 0%.
- Brevard: A PASS · B 0 verified independent outcomes (the known Gap B) · C 27.9% · D 44.4% · E 65.4% · F 1.5% · G 48.9% · H PASS (21.9h) · I 24.8% · J 0%.

## How to read it
```sql
select * from gold_standard_scoreboard order by pass_count desc;          -- league table
select * from gold_standard_county_status where county_slug='brevard'
  and loop_run_id=(select max(loop_run_id) from gold_standard_county_status); -- letter detail
select public.pencil_dod_evaluate_county('duval');                        -- ad-hoc audit
```

## Fleet priorities from baseline
1. **B everywhere** — independent verified outcomes (clerk-source scrapers); Brevard from-scratch verified-results scraper remains the flagship gap.
2. **F** — tier1 sold-amount verification only just restored (incident 01); accrues daily from the 05:30Z cycle.
3. **G/I** — zoning coverage expansion (Duval currently zero KPI rows).
4. **J** — bid_decisions generation at scale (valuations_comps batch is building inputs; 21 qualifying rows today).
