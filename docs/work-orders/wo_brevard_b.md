# WORK-ORDER — Brevard Criterion-B Verified-Outcomes Scraper (v2, corrected source model)
**Mission**: move Brevard DoD criterion **B (verified realized outcomes)** from **0.0% → ≥95%** by writing clerk/official-source REALIZED outcome rows to the independent outcome tables. B is THE moat and the upstream blocker for C, D, F, and J.

> **v2 correction (2026-06-11, live-probed):** The Brevard clerk page `foreclosure_sales.html` is a FORWARD-LOOKING CALENDAR only — columns are `case_number, case_title, comment, foreclosure_sale_date`, all dates future, `comment` only ∈ {blank, CANCELLED}. It has **NO realized-outcome fields** (no sold amount, winner, surplus, final judgment). Do NOT attempt to derive B from it. Realized foreclosure outcomes require a **two-step pull** (see §2). A v1 of this work-order incorrectly treated the calendar as the outcome source — that assumption is dead.

---

## 0. Why this is the single highest-leverage build
Live scoreboard (2026-06-11): Brevard = 2/10 gold (A, H pass). `tax_deed_outcomes` and `foreclosure_outcomes` are **empty for Brevard** — that is the literal reason B reads 0.0%. The 945 "promoted" outcomes are self-referential rows in `multi_county_auctions` and do NOT count (the scorecard filter excludes `data_source ~~* '%promote%'`). Landing B plausibly turns **B, C, D, F** green in one build, since the parity and sold-amount math finally have verified outcomes to reconcile against. Telemetry note: dispatch write-back was repaired 2026-06-11 (reconcile_gha_dispatch_log + cron), so this build's dispatches WILL be observable.

## 1. Definition of Done (from `public.pencil_dod_criteria`, letter B — do not reinterpret)
- B passes when `verified_outcomes / closed_sold ≥ 95%`.
- `verified_outcomes` = rows in `public.tax_deed_outcomes` + `public.foreclosure_outcomes` for `county ILIKE 'brevard'` whose `data_source` does **NOT** match `%promote%` (case-insensitive) and is **not** PropertyOnion-derived.
- `closed_sold` (denominator) = **6,713** (`multi_county_auctions` brevard, `sold_amount IS NOT NULL`): 4,088 tax-deed + 2,625 foreclosure.
- **Target: write ≥ 6,377 independent-source REALIZED-outcome rows** keyed by `case_number`.
- **HARD FAILS** (canon): `data_source` containing "promote"; any PropertyOnion-derived source; any row promoted from our own `multi_county_auctions`. Verifier of record = county clerk / RealTaxDeed official result ONLY. A realized outcome means an actual recorded result (sold amount + winner, or cancelled/redeemed/struck), NOT a scheduled calendar entry.

## 2. Sources — CORRECTED two-step model (foreclosure) + auth'd lane (tax-deed)

### 2A. Foreclosure (clerk, IN-PERSON Wed, Titusville) — TWO STEPS
- **Step 1 — case list**: scrape `http://vweb2.brevardclerk.us/Foreclosures/foreclosure_sales.html` for `(case_number, case_title, comment, foreclosure_sale_date)`. This yields the universe of scheduled/cancelled cases and dates. `comment=CANCELLED` → outcome='cancelled' (a valid realized outcome, write it). This page is HTTP-200 to a browser UA, ISO-8859-1, ~109 rows live.
- **Step 2 — realized result per closed case**: for each case whose sale_date has passed (and not cancelled), look up the recorded **Certificate of Sale / Certificate of Title** via Brevard **BECA Court Case Search** (`https://vmatrix1.brevardclerk.us/beca/beca_splash.cfm`). NOTE: BECA returned **HTTP 503 to a bare curl UA** during scoping — it requires a real browser session (accept disclaimer / session cookie). Build the BECA lookup with Playwright (accept splash → case search by case_number → parse Certificate of Sale for sold amount, winner, surplus). `data_source='brevardclerk_beca'` for results, `'brevardclerk_html'` for calendar-derived cancellations.

### 2B. Tax-deed (RealTaxDeed lane) — AUTH REQUIRED
- `https://brevard.realforeclose.com` (tier-1 per 2026-05-14 SSOT). **Anonymous preview caps ~20 items** — a free-registered authenticated session + the `FNC=UPDATE` diff endpoint is REQUIRED for full closed-sale results. **This lane needs RealAuction credentials** (not in repo); the launching session must supply them via GH secret. Without creds, the tax-deed half of B cannot complete. `data_source='realtaxdeed_brevard'`.

## 3. Write contract
Write to BOTH tables, matched to existing auctions by `case_number` (5,143 distinct brevard closed cases exist).

**`public.foreclosure_outcomes`** — required: `case_number, county='brevard', sale_type, auction_date, outcome, winning_bid, winner_name, winner_type, parcel_id, source_url, data_source, enriched_at=now()`. Capture `final_judgment, opening_bid, plaintiff_raw` where BECA exposes them.

**`public.tax_deed_outcomes`** — required: `case_number, county='brevard', auction_date, outcome, winning_bid, winner_name, winner_type, opening_bid, parcel_id, source_url, data_source='realtaxdeed_brevard', enriched_at=now()`. Capture `cert_number, cert_holder, assessed_value` where exposed.

`outcome` ∈ {sold, redeemed, cancelled, no_bid, struck_to_plaintiff}. Idempotent upsert on `(case_number, county, auction_date)`; re-runs must not duplicate.

## 4. Build constraints (standing canon)
- Infra: GHA + Supabase only; Hetzner ONLY if Playwright runtime > 6h (the BECA per-case loop over thousands of cases MAY exceed 6h — budget accordingly, checkpoint/resume).
- Honesty V3: every write path emits a verification query returning the row count. No ghost success. NEVER write a row without a real recorded result — a missing BECA result = leave it unwritten, not guessed. Wrong VERIFIED = 3× penalty.
- Idempotent, resumable: persist progress (per case_number) so a re-run resumes; commit or revert before budget exhaustion.
- Cost ≤ $10/session. License: MIT/Apache2/BSD/ISC only.

## 5. Acceptance (session self-verifies before closing)
```sql
SELECT round(100.0 * (
  (SELECT count(*) FROM tax_deed_outcomes  WHERE county ILIKE 'brevard' AND COALESCE(data_source,'') !~~* '%promote%')
+ (SELECT count(*) FROM foreclosure_outcomes WHERE county ILIKE 'brevard' AND COALESCE(data_source,'') !~~* '%promote%')
)::numeric / NULLIF((SELECT count(*) FROM multi_county_auctions WHERE county ILIKE 'brevard' AND sold_amount IS NOT NULL),0),1) AS pct_b;
```
PASS when `pct_b ≥ 95`. Then re-check `SELECT crit_b_pass, crit_c_pass, crit_d_pass, crit_f_pass, gold_standard_pct FROM v_pencil_brevard_dod;` and post before/after to the session's GitHub issue. Partial-credit checkpoint: report foreclosure-lane % and tax-deed-lane % separately so a creds-blocked tax-deed lane doesn't read as total failure.

## 6. Scope guard
B only. Do NOT touch G/zoning (separate work-order), do NOT refactor the v5 evaluator, do NOT widen to other counties. One county, one criterion, REAL recorded outcomes only.
