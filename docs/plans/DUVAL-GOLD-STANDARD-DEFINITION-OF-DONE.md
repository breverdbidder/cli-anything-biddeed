# DUVAL GOLD STANDARD — DEFINITION OF DONE (A–J)

**Status date:** 2026-06-09 | **Author:** Claude (AI Architect) | **Approved scope:** PENCIL Duval-first
**Companion:** BREVARD-GOLD-STANDARD-DEFINITION-OF-DONE.md (A–H). This doc extends the framework to A–J and is self-contained for Duval.
**Context:** PENCIL INCIDENT 01 (issue #7496) resolved 2026-06-09 — fleet-wide silent writeback outage since ~2026-05-27. Four stacked defects fixed; fail-loud invariant now enforced. Criteria E/F encode the incident's lessons permanently.

Gold standard = ALL TEN criteria PASS simultaneously and hold for 7 consecutive cron days.

---

## A. Auction Coverage (both sale types)
**Definition:** Every auction published on duval.realforeclose.com and duval.realtaxdeed.com for dates within [today-7, today+60] exists in `multi_county_auctions` (foreclosure AND tax_deed).
**Measure:** scraped card count vs MCA row count per (sale_type, auction_date); gap = 0.
**Threshold:** 100% for 7 consecutive days.
**Status 2026-06-09:** PARTIAL — foreclosure lane restored today (7/7 on 2026-06-09); tax_deed lane subject to known RealAuction anonymous-preview cap (~20 items); authenticated-session scraping is the path to full-list coverage.

## B. Verified Tax-Deed Outcomes Depth
**Definition:** Realized tax-deed outcomes (sold amount, sold-to, timestamp) verified from RealAuction source, NOT PropertyOnion-inferred.
**Measure:** count of tax_deed_outcomes where county=duval.
**Threshold:** >= 6,500 and net-growing weekly.
**Status 2026-06-09:** PASS — 6,952.

## C. Verified Foreclosure Outcomes Depth
**Definition:** Realized foreclosure outcomes verified from RealForeclose tier1 truth (SOLD with amount, CANCELED, REDEEMED).
**Measure:** count of duval foreclosure rows with tier1_authoritative and terminal tier1_sale_status; plus foreclosure_outcomes rows.
**Threshold:** >= 500 verified outcomes accrued.
**Status 2026-06-09:** FAIL (accruing) — 0 historical; accrual began TODAY (first 2 SOLD + 3 CANCELED + 1 REDEEMED landed 20:28Z). At ~7 cards/auction-day, expect ~150-200/month.

## D. Freshness
**Definition:** Every Duval auction date within +/-7 days has tier1_verified_at within 24h.
**Measure:** max(now() - tier1_verified_at) over active window <= 24h; no row stale > 48h.
**Threshold:** 7 consecutive cron days.
**Status 2026-06-09:** PASS today (last verify 20:28Z) — clock starts on consecutive-day proof.

## E. Pipeline Integrity — Fail-Loud Invariant (INCIDENT 01 LESSON)
**Definition:** Zero silent drops: no run may report status=success with rows_in>0 AND rows_inserted=0. Every insert failure surfaces the real DB error into scrape_runs.error_message.
**Measure:** count of duval scrape_runs with status=success, rows_in>0, rows_inserted=0 over rolling 30 days = 0.
**Threshold:** 0 over rolling 30 days.
**Status 2026-06-09:** ENFORCED (scraper raises RuntimeError; deployed to scrape_realauction_county.py and parity-court-scraper.yml). Rolling window starts today. Known partial-insert gap: runs with 0 < inserted < parsed pass as success; extend fail-loud to partials if recurrence observed (watch: palm_beach 06-11, 2/3).

## F. Identity-Field Hygiene
**Definition:** No markdown/link pollution in case_number, parcel_id, certificate, address fields anywhere in the chain (tier1_card_raw, tier1_today, multi_county_auctions).
**Measure:** counts of values matching '^[[:space:]]*[[' = 0 in all three tables; biddeed.strip_md_link() active at ingestion; case_number_no_markdown CHECK retained as last line of defense.
**Threshold:** 0, permanently.
**Status 2026-06-09:** PASS — one-time scrub completed (0 remaining), normalizer live, conflict-path refresh deployed.

## G. Parity vs Litmus
**Definition:** Row-count parity with PropertyOnion (litmus-only, never a data source) for same county/date/sale_type.
**Measure:** abs(MCA count - PO count) <= 1 per auction date, sampled weekly.
**Threshold:** 4 consecutive weekly samples.
**Status 2026-06-09:** UNVERIFIED post-fix — first litmus sample due this week.

## H. Calibration Loop Operational
**Definition:** Weekly Duval recalibration cron active; every realized outcome scored into pencil_calibration within 7 days of realization.
**Measure:** cron job 111 active; max(scored_at) <= 7 days old; unscored-outcome backlog = 0.
**Threshold:** continuous.
**Status 2026-06-09:** PASS — cron 111 active, 890 Duval calibration rows, last scored 2026-06-08.

## I. Predictive Performance (NEW — Duval-specific)
**Definition:** Rolling 90-day bid_ceiling_within rate on Duval predictions, post-recalibration with fresh tier1 truth flowing (criterion C feeding H).
**Measure:** avg(bid_ceiling_within) from pencil_calibration, county=duval, scored_at in last 90 days.
**Threshold:** >= 0.50 (in-sample ceiling was 0.5795; holdout floor 0.331 = temporal drift confirmed; rolling recalibration is the moat).
**Status 2026-06-09:** FAIL — 0.331. Expected to lift as C accrues fresh foreclosure truth into H.

## J. PENCIL Report Readiness (NEW — end-to-end)
**Definition:** pencil-grounding Edge Function produces Duval feasibility reports grounded EXCLUSIVELY in verified data (A-F) with calibration disclosure (H-I); zero PropertyOnion-inferred fields in client-facing output; CAN-SPAM lead funnel attached.
**Measure:** report generation succeeds for >= 95% of upcoming Duval auctions; grounding audit shows 0 inferred-source fields.
**Threshold:** 7 consecutive days at >= 95%.
**Status 2026-06-09:** BLOCKED on C (outcome depth) and I (performance gate). Infrastructure deployed.

---

## Scoreboard 2026-06-09
| | Criterion | Status |
|--|--|--|
| A | Coverage | PARTIAL (tax_deed auth-session pending) |
| B | Tax-deed outcomes 6,952 | PASS |
| C | Foreclosure outcomes | FAIL — accruing (started today) |
| D | Freshness | PASS (day 1 of 7) |
| E | Fail-loud invariant | PASS — enforced (day 1 of 30) |
| F | Hygiene | PASS |
| G | Parity litmus | UNVERIFIED |
| H | Calibration loop | PASS |
| I | Ceiling-within >= 0.50 | FAIL — 0.331 |
| J | PENCIL reports | BLOCKED on C, I |

**Critical path:** C -> I -> J. C is pure time-accrual now that the pipeline writes truth. Accelerators: historical foreclosure-outcomes backscrape (authenticated sessions, FNC=UPDATE diff endpoint) to compress C from months to weeks.
