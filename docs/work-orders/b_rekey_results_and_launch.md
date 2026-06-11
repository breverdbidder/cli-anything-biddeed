# Brevard B — Step 1 Results + Outcome-Pull Launch (2026-06-11)
Companion to `b_strategy.md`. Step 1 (re-key crosswalk) is DONE. This file records the result and the precise launch for the outcome pull (Steps 2–3).

## Step 1 result — `public.brevard_case_rekey` (built + applied)
Bridged the two non-overlapping parcel keyspaces (PO spaced-folio ↔ real numeric-account) via `fl_parcels.addr_key`.

| Lane | re-keyed cases | of which closed-sold |
|---|---|---|
| foreclosure | 121 | 98 |
| tax_deed | 43 | 43 |
| **total** | **164** | **141** |

**Honest read:** 141 closed-sold re-keyed ≈ 2% of the 6,713 B denominator. The crosswalk matched ~everything matchable; the ceiling is the tiny real-keyed corpus (~1,150 rows, mostly *upcoming* not closed). **Re-keying is NOT the bottleneck — the missing historical real-source outcomes are.** The crosswalk is now a standing bridge: every new real outcome auto-links to its PO counterpart by address.

## What gates B now (only the outcome pull remains)
All Claude-side prep is done: crosswalk built, outcome-table contract defined, verification SQL written, source access identified. The remaining work is a credentialed scrape session pulling realized outcomes from the legitimate sources, which then flow through this crosswalk into the outcome tables.

## Verified outcome-pull infrastructure (already active in repo)
From `gha_workflow_catalog`, all `state=active`:
- **`parity-court-scraper.yml`** (id 276397805) — "PARITY Court Scraper (Firecrawl) v2" → foreclosure / Acclaim Certificate-of-Title lane. Firecrawl backend clears the Acclaim/BECA 503.
- **`scrape-brevardclerk.yml`** (id 276879830) — "Brevard Clerk Tax Deed Scraper".
- **`rl-outcome-collector.yml`** (id 257558951) — "RL Outcome Collector — Daily Post-Auction" → realized-outcome writer.
- Tax-deed auth lane: `scrape-realauction-county.yml` (id 277027525) with RealAuction creds (already in GH secrets) + Firecrawl (`scraping_proxy_backend=firecrawl`).

## PRECISE LAUNCH (server-side dispatch canon — PAT read in-DB, never in context)
Foreclosure / Acclaim outcome pull (Firecrawl-backed):
```sql
select public.fire_workflow_dispatch(
  'breverdbidder/cli-anything-biddeed',
  'parity-court-scraper.yml',
  'main',
  jsonb_build_object('county','brevard','mode','outcomes',
                     'doc_type','certificate_of_title','since','2024-01-01')
);
```
Tax-deed / RealTaxDeed outcome pull (authed):
```sql
select public.fire_workflow_dispatch(
  'breverdbidder/cli-anything-biddeed',
  'scrape-realauction-county.yml',
  'main',
  jsonb_build_object('county','brevard','sale_type','tax_deed','mode','outcomes','fnc','UPDATE')
);
```
Equivalent CLI (if launching from a residential/dev machine instead of in-DB):
```bash
gh workflow run parity-court-scraper.yml      -R breverdbidder/cli-anything-biddeed -f county=brevard -f mode=outcomes -f doc_type=certificate_of_title -f since=2024-01-01
gh workflow run scrape-realauction-county.yml -R breverdbidder/cli-anything-biddeed -f county=brevard -f sale_type=tax_deed -f mode=outcomes -f fnc=UPDATE
```

## After the pull — verify B (self-check)
```sql
SELECT round(100.0 * (
  (SELECT count(*) FROM tax_deed_outcomes   WHERE county ILIKE 'brevard' AND COALESCE(data_source,'') !~~* '%promote%')
+ (SELECT count(*) FROM foreclosure_outcomes WHERE county ILIKE 'brevard' AND COALESCE(data_source,'') !~~* '%promote%')
)::numeric / NULLIF((SELECT count(*) FROM multi_county_auctions WHERE county ILIKE 'brevard' AND sold_amount IS NOT NULL),0),1) AS pct_b;
SELECT crit_b_pass, crit_c_pass, crit_d_pass, crit_f_pass, gold_standard_pct FROM v_pencil_brevard_dod;
```

## Guardrails (unchanged)
- Outcome rows MUST carry an independent `data_source` (never `%promote%`, never PropertyOnion) — HARD FAIL otherwise.
- Never write a row without a real recorded result. Missing = unwritten.
- Each new real outcome links to its PO row via `brevard_case_rekey` (address bridge) — do not re-key by guessing.
