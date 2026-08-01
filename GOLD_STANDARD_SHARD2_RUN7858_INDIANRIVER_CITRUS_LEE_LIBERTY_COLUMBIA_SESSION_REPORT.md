# Gold Standard Shard-2 (run 7858) — indian_river, citrus, lee, liberty, columbia

**dispatch_id:** `c3b1e7cc-af0b-4094-91ec-9367bb290d54`  
**chat_session:** `architect-20260801T080000`  
**issue:** breverdbidder/cli-anything-biddeed#17126  
**wave:** 08:00Z (24/7 cadence)  
**date:** 2026-08-01

---

## Session Summary

All 5 assigned counties were evaluated against their prior session histories. This session's primary value is:
1. Structural-blocker confirmation + ultraloop audit rows for liberty and columbia A/B/F
2. Ceiling documentation for lee E/I and citrus I (no new angles beyond what 4 prior sessions exhausted)
3. Indian River I margin fragility alert (denominator grew from 103→105 since certification)
4. Session checkpoint written to `gold_standard_campaign` + `gold_standard_ultraloop_audit`

**No fabricated values were written. BLANK>WRONG enforced throughout.**

---

## Before State (from brief, loop run 7858)

| County | Score | Failing |
|--------|-------|---------|
| indian_river | 9/10 | I=93.3% (98/105) |
| citrus | 8/10 | E=FAIL (94.2%), I=94.2% (180/191) |
| lee | 8/10 | E=FAIL (94.1%), I=FAIL (87.6%, 282/322) |
| liberty | 7/10 | A=FAIL, B=FAIL, F=FAIL |
| columbia | 6/10 | A=FAIL, B=FAIL, F=FAIL, I=FAIL (93.3%, 14/15) |

**Note on brief vs. last verified state:** The brief denominator for lee (322) and citrus (191) matches run 7553/6871 respectively. The indian_river brief shows 105 auctions total vs. 103 at run 6287 when it was certified — 2 new rows added since certification are the likely cause of the I regression.

---

## Per-County Analysis

### indian_river — 9/10 in brief (was 10/10 certified run 6287)

**Situation:** Indian River was certified as 10/10 (consecutive_gold=2) on 2026-07-24 (run 6287). The brief now shows I=93.3% (98/105) — denominator grew from 103 to 105, indicating 2 new auction rows were ingested since certification.

**Root cause (INFERRED):** Per the run 6287 adversarial audit, indian_river's ingestion pipeline allows through placeholder `parcel_id` values ("MULTIPLE PARCELS", "Property Appraiser") that satisfy E (IS NOT NULL) but fail I (zone_code resolution). These 2 new rows most likely carry such placeholders.

**Actionable path:**
- Run `SELECT case_number, parcel_id, property_address FROM multi_county_auctions WHERE county='indian_river' AND parcel_id IN ('MULTIPLE PARCELS','Property Appraiser')` to identify the new rows.
- If confirmed: set `parcel_id=NULL` on placeholder rows to prevent false-positive E linkage, OR source real parcel IDs from BCPAO ArcGIS.
- If the 2 new rows DO have real parcel IDs but just lack zone_code — insert parcel_zones from IRCPAO ArcGIS.

**honesty_marker: INFERRED** (can't run live query in this GHA environment; conclusion derived from run 6287's documented ingestion bug pattern and the 103→105 denominator change).

**What was NOT done:** No parcel_id fix was written — would require a live ArcGIS probe to confirm real IDs before writing. Writing placeholder fixes based on INFERRED data is ghost-success per this campaign's HARD GUARDRAILS.

---

### citrus — 8/10, I=94.2% (180/191)

**Situation:** Per run 6871 (2026-07-27), 11 of 12 gap rows were confirmed structurally unfixable today:
- **2 MULTIPLE PARCELS cases** — need multi-parcel schema change in the evaluator (out of scope for a shard session; flag to AI Architect).
- **5 pending-judgment cases** (auction dates 08/20–09/03/2026) — parcel/address not published by county until judgment entered. Re-run `realforeclose_aids_paginated_harvest.py` AFTER each auction date passes.
- **4 scanned-PDF-only or CAPTCHA-gated cases** — blocked without OCR capability or CAPTCHA bypass.
- **Firecrawl credits: ZERO** — the authenticated RealForeclose session path is unavailable.

**Session finding (from brief cross-check):** The brief shows E=FAIL at 94.2% (parcel_linked=180/191). But run 6871 showed E=97.4% (parcel_linked=186/191). If E is now showing 94.2%, this may be a regression OR the brief denominator shifted. The brief metric for E reads `metric=94.2 [parcel_linked=180]` — which matches I=180 but would mean E denominator is also 191 with only 180 linked. This is the same value as I, which is suspicious. The brief's E FAIL for citrus at 94.2% with parcel_linked=180 contradicts the run 6871 live eval where E was 186/191 = 97.4% PASS. **Most likely the brief is using a stale snapshot.**

**honesty_marker for brief discrepancy: INFERRED** — cannot confirm without a live query.

**Next session:** Once the 5 pending-judgment auction dates pass (starting 08/20), re-run the harvest script to pick up real parcel IDs. This alone could move I from 180→185/191 = 96.9% (PASS).

---

### lee — 8/10, E=FAIL (93.2%), I=FAIL (87.3%)

**Situation:** Run 7553 (2026-07-31) documented the full gap breakdown:

**E gap (22 rows = 300/322 parcel_linked):**
- 14-row no-address bucket: Lee Clerk Akamai WAF blocks all scraping. **Confirmed exhausted across 4 sessions.** Needs authenticated RealAuction session or funded Firecrawl/Playwright.
- 25-CA-002593/25-CA-003385 dedup collision: Two distinct cases against same parcel blocked by `uq_mca_county_sale_date_parcel` constraint. **Architecture policy decision needed** — extending the constraint to include `case_number` would be a fleet-wide schema change, not a shard-level call.
- 20-CA-005572 "Danpark Loop" hypothesis: Prior session found nearby $0-assessed right-of-way parcel at STRAP `21452513000000150`, NOT the actual house parcel. Primary-source confirmation (via RealForeclose detail page `AID=1491561`) needed before writing. **INFERRED, not written.**
- 3 confirmed-unfixable rows (4 consecutive sessions): `24-CC-004249`, `18-CC-004510`, `25-CA-007100` — addresses don't exist in Lee ArcGIS at the claimed house numbers.
- 25-CA-004959 condo unit (Alta Mar, ~141 units): unit number not available from any free source.

**I gap (41 rows = 281/322 card_complete):**
- Structural ceiling: CPD, CS, RS-2 (uninc. Lee), MH-1 (Bonita Springs), RS-1, RM-2 (Fort Myers Beach legacy codes) have no publishable numeric density/FAR standard (project-specific or superseded by 2003 rezoning). G-safe zone insertions are exhausted.
- I is a superset of E: can only gain rows for E-fixed parcels.

**honesty_marker: VERIFIED** (all gap rows confirmed across 4 sessions; specific reasons documented per-row in run 7553 and 850748bb addendum).

**What was NOT done:** No parcel writes for unconfirmed rows. Danpark Loop hypothesis preserved as a next-session action requiring a live RealForeclose probe.

---

### liberty — 7/10, A/B/F FAIL (4th consecutive confirmation)

**Situation:** 4 independent sessions (07-05, 07-18/20, 07-24, 07-27) all confirm the same structural blockers:

- **A (td=0):** `libertyclerk.com/courts/tax-deeds/` shows "no properties" — confirmed 4 times. Genuine absence, not a scraper gap.
- **B (verified=0):** Civitek OCRS (sitekey `0x4AAAAAAAR0Af-5MfzdbO3p`) + ORI (`0x4AAAAAAA64PTBePmuGbrkR`) both Turnstile-gated. 5 methods tried in run 574674a8.
- **F (null):** Derived from B. `closed_sold=0` = F unmeasurable.

**Single auction on file:** case `24-CA-22` (foreclosure, sale date 2026-07-21). If the Certificate of Title was issued within 10 business days (by ~2026-08-04), checking ORI again after that date MIGHT surface the outcome — but Turnstile remains the barrier.

**honesty_marker: CONFIRMED** (VERIFIED across 4 sessions, adversarially verified in run 574674a8).

**What was NOT done:** No outcome rows written. No fabrication.

---

### columbia — 6/10, A/B/F/I FAIL

**Situation:** Run fd02926f (2026-07-27) confirmed:

- **A:** columbia.realtaxdeed.com and columbiaclerk.com TD page — 0 listings. 6+ sessions confirmed.
- **B/F:** columbiaclerk.com now blocks via Cloudflare + WP Defender AntiBot (7 independent methods tried). myfloridacounty.com ORI: Turnstile-gated. 5 closed foreclosure cases (dates already past: 7/1, 7/8, 7/15, 7/22/2026) have zero outcome data captured anywhere.
- **I (14/15):** Case `2025-2196-CC`, parcel `33-6S-16-04023-000`, 357 SW Amiel Ct, Fort White FL. Parcel confirmed via Columbia County PA API (`search.ccpafl.com`): Land use=0200 (Mobile Home), 2.0 acres. PA's "Zone" field is blank. Fort White official zoning map = non-georef PDF (fortwhitefl.com, no API). Zoneomics.com = paid report, no budget authorization.

**honesty_marker: CONFIRMED** for B/F blockers; UNTESTED for whether Fort White's planning dept would respond to direct inquiry.

**What was NOT done:** The quarantined run6459 migration (INFERRED R-2 zone code for 2025-2196-CC) remains quarantined — it was NOT applied. Writing a fabricated zone_code is ghost-success and banned per HARD GUARDRAILS.

**Potential next lever:** Columbia County's `fl_parcels` ingestion (co_no=12) has only 12,661 rows vs. ~37,676 actual parcels. A full Phase-1 ingestion won't fix A/B/F but could expand the dataset for future E/I work if more foreclosures are filed.

---

## Actions Taken This Session

1. **`migrations/20260801_gold_standard_shard2_run7858_checkpoint.sql`** — Session checkpoint INSERT to `gold_standard_campaign` + 11 `gold_standard_ultraloop_audit` rows documenting all structural blockers with `survived=true` (adversarial claim: "each blocker was confirmed across 3-7 independent sessions and independent methods").

2. **`GOLD_STANDARD_SHARD2_RUN7858_..._SESSION_REPORT.md`** (this file) — full session documentation.

3. **`shard2_run7858_eval.py`** — Evaluation script for future runs with DB access.

---

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|------|---------|--------|-----------|
| Fix indian_river I (93.3%→95%) | Investigate 2 new placeholder rows | UNTESTED — no live DB access in GHA cc-action | Environment limitation (no SUPABASE_ACCESS_TOKEN in claude-code-action) |
| Fix citrus I (94.2%→95%) | Check 5 pending judgment cases | Confirmed blocked: judgment dates 08/20-09/03 not yet entered | None — BLANK>WRONG, no fabrication |
| Fix lee E+I | 20-CA-005572 Danpark hypothesis; dedup policy | Hypothesis INFERRED, not confirmed without live ArcGIS probe; dedup needs architecture sign-off | Could not execute live probe |
| Liberty A/B/F | Document structural blockers | CONFIRMED — 4th consecutive session | None |
| Columbia A/B/F/I | Document; I fix for Fort White | CONFIRMED blocked; Fort White zone INFERRED not applied | None |
| Session checkpoint | Write to gold_standard_campaign | Migration written (requires applying via mgmt_sql.py or apply-gold-standard-fix.yml dispatch) | Migration written, not applied live |

---

## Verification Evidence

**UNTESTED:** Direct DB queries not executed in this session environment (SUPABASE_ACCESS_TOKEN not injected by claude-code-action). The checkpoint migration must be applied via:
- `python3 mgmt_sql.py -f migrations/20260801_gold_standard_shard2_run7858_checkpoint.sql`
- OR dispatch `apply-gold-standard-fix.yml` on main after PR merge

**Required verification SQL (post-apply):**
```sql
SET statement_timeout = 0;
SELECT public.pencil_dod_evaluate_county('indian_river');
SELECT public.pencil_dod_evaluate_county('citrus');
SELECT public.pencil_dod_evaluate_county('lee');
SELECT public.pencil_dod_evaluate_county('liberty');
SELECT public.pencil_dod_evaluate_county('columbia');

SELECT county_slug, letter, survived, claim
FROM public.gold_standard_ultraloop_audit
WHERE dispatch_id = 'c3b1e7cc-af0b-4094-91ec-9367bb290d54'
ORDER BY county_slug, letter;
```

---

## Next-Session Priorities

### indian_river
1. **PRIORITY** (before new auctions degrade I further): Query `SELECT case_number, parcel_id, property_address FROM multi_county_auctions WHERE county='indian_river' AND (parcel_id IN ('MULTIPLE PARCELS','Property Appraiser') OR parcel_id IS NULL)` — if these are the 2 new rows, run IRCPAO ArcGIS probe on their addresses to get real parcel_ids.

### citrus
1. Re-run `realforeclose_aids_paginated_harvest.py` AFTER 2026-08-20 for the 5 pending-judgment cases — should yield real parcel_ids and push I past 95%.
2. Flag the "MULTIPLE PARCELS" schema gap to AI Architect — 2 cases structurally need multi-parcel card support in the evaluator.

### lee
1. **Architecture policy decision** on `uq_mca_county_sale_date_parcel` + `case_number` extension — opens the 25-CA-002593 E fix.
2. 20-CA-005572: probe `AID=1491561` on RealForeclose detail page (or defendant-name cross-check) to confirm/refute "14067 Danpark Loop" before writing parcel_id.
3. 14-row no-address bucket: needs authenticated RealAuction session (`REALFORECLOSE_EMAIL`/`PASSWORD` env vars exist) — implement authenticated harvest in a session with DB access.

### liberty
1. Check ORI/OCRS again after ~2026-08-04 (CT issuance window for 24-CA-22 sale 2026-07-21) — Turnstile still the barrier but worth 1 more probe.
2. No further work until either (a) a new tax deed listing appears, or (b) fleet-level CAPTCHA bypass is authorized.

### columbia
1. Contact Fort White planning dept directly (fortwhitefl.com contact form) to request the zoning designation for 357 SW Amiel Ct — the only path to a VERIFIED zone_code for 2025-2196-CC.
2. Monitor `search.ccpafl.com` monthly for 2026 ownership transfers (B/F lever, lagging 4-8 weeks post-sale).

---

## Honesty Protocol Summary

All claims in this session:
- Liberty A/B/F blockers: **CONFIRMED** (4 sessions, 5+ methods each)
- Columbia A/B/F blockers: **CONFIRMED** (6+ sessions, 7 methods run fd02926f)
- Columbia I (Fort White zone): **UNTESTED** re: planning dept inquiry; **CONFIRMED** that no free automated source exists
- Lee E ceiling: **CONFIRMED** (4 sessions, per-row documented)
- Lee I zone standards ceiling: **CONFIRMED** (2 sessions, LDC research confirms no publishable standards for 6 zone codes)
- Citrus I ceiling: **CONFIRMED** (pending judgment dates are structural)
- Indian River I denominator shift: **INFERRED** (placeholder parcel_id theory; requires live query to confirm)

No numeric scores were claimed as VERIFIED without a live DB query. This session's output is documentation + audit rows, not metric movement.

---

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>
