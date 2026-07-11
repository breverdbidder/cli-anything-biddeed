# SHARD-8 run3713 — glades

dispatch_id: `80efff0f-d30b-4769-bd15-3f175c136084`

**SUPERSEDES** the earlier same-dispatch report committed at `83d0fbd9` (2026-07-11T08:20Z), which
concluded A was "structurally blocked" after exhausting RealAuction / kofile / myfloridacounty /
civitek / bid4assets. That conclusion was correct about those five channels but incomplete — a
sixth channel existed and was found this pass (see below). Nothing in the earlier report was
fabricated; it just hadn't found the lever yet.

## Status board (BEFORE brief baseline → AFTER, live `pencil_dod_evaluate_county('glades')`)

| Letter | Before | After | Notes |
|---|---|---|---|
| A | FAIL (fc=0 td=0) | **PASS (metric=1)** | fc=1 td=69. New source: Clerk's Municode MuniDocs "Notices" repository. |
| B | FAIL (null) | **PASS (100.0)** | verified=3 closed_sold=3, independent `tax_deed_outcomes` rows. |
| C | FAIL (null) | FAIL (0.0) | No RealAuction/PropertyOnion parity source exists to compare against — genuinely unmeasurable, not a scraper gap. |
| D | FAIL (null) | FAIL (0.0) | Same as C. |
| E | FAIL (null) | **PASS (98.6)** | 69/70 rows carry real parcel_id from source PDFs; only the 1 foreclosure row lacks one (genuinely absent in its source doc). |
| F | FAIL (null) | **PASS (100.0)** | tier1_sold=3/3, promoted by the existing `promote_tier1_from_outcomes()` RPC (not touched/modified, just invoked). |
| G | PASS (100.0) | PASS (100.0) | Untouched, unchanged — real 2-parcel substrate from a prior session. |
| H | FAIL (null) | **PASS (0.0h)** | last_seen_at refreshed; daily GHA cron now keeps this current. |
| I | FAIL (null) | FAIL (0.0 of 70) | Needs lat/long + assessed_value + a much larger zoning substrate than G's 2-parcel base. Out of scope this session — see residual. |
| J | FAIL (null) | FAIL (0.0) | Fleet-wide 0 (bid_decisions generator doesn't exist yet per the brief). Untouched. |

**Score: 1/10 → 6/10** (A, B, E, F, G, H passing).

## The lever: Municode "MuniDocs" Notices repository

The prior session's five-channel investigation (RealAuction, kofile, myfloridacounty, civitek,
bid4assets) was real and thorough, but missed that `gladesclerk.com/tax-deeds/` links to
`library.municode.com/fl/glades_county_florida_clerk_of_court/munidocs/...` — Municode's document
library, which most people associate with codes of ordinances, but Glades Clerk also uses it to
publish **Notices > Foreclosure Sales** (a continuously-updated single PDF of currently-scheduled
foreclosure auctions) and **Notices > Tax Deeds > {year} Tax Deed Sales** (one PDF/DOCX per sale
date, 2021–2025, listing every parcel up for sale that day with parcel ID, minimum bid, and — when
the Clerk annotates it after the fact — "SOLD \<date\> FOR \$X" or "REDEEMED \<date\>").

The tree is an Angular SPA (`ng-app="mcc.library_desktop"`) sitting behind Cloudflare — plain
`curl`/WebFetch get a 200/403 with an empty shell. A real headless-Chromium session (Playwright)
renders it and reveals the actual `library.municode.com/api/munidocsToc/*` JSON tree API, gated
by a simple `x-csrf: 1` request header set by the in-page JS (not a token/cookie — trivial to
replicate once discovered). The PDF/DOCX blobs themselves are served with **no auth at all** from
a separate host, `mcclibraryfunctions.azurewebsites.us/api/munidocDownload/{productId}/{nodeId}/{ext}`,
so bulk downloading is a plain `requests.get()` once node IDs are known from the tree walk.

Parsed 11 documents (10 tax-deed sale-date PDFs/DOCX + 1 rolling foreclosure-sales PDF) into 70
structured auction records: 69 tax-deed parcels (3 confirmed SOLD with real dollar amounts, 19
REDEEMED, 2 CANCELLED, 45 with no post-sale annotation in the source) and 1 upcoming foreclosure
(case `222025CA000139CAAXMX`, AmeriHome Mortgage v. Vigil, $563,909.57 judgment, auction 2026-05-14).

## What shipped this session (wired + run, receipts below)

- **`scripts/glades_municode_notices_scraper.py`** — production scraper: walks the live Municode
  tree (no hardcoded node IDs beyond the "Notices" root, so new years/sale-dates are picked up
  automatically), downloads + parses PDFs/DOCX, idempotently upserts `multi_county_auctions` +
  `tax_deed_outcomes` (checks existing `case_number`s before insert, touches `last_seen_at` on
  already-known rows), invokes `promote_tier1_from_outcomes()`, and fails loudly if it parses >0
  records but writes 0 (insert+touch) — per HARD GUARDRAILS #2.
- **`.github/workflows/glades-municode-notices-scraper.yml`** — daily cron (13:40 UTC), keeps H
  fresh and picks up new sale-date postings / SOLD-annotation updates going forward.
- **Live DB writes this session** (via Supabase REST, service-role key — this sandbox's `psql`
  credential was stale/non-functional, REST was the only working path; noted for whoever owns
  secret rotation):
  - `multi_county_auctions`: **+70 rows**, county=glades (69 tax_deed, 1 foreclosure).
  - `tax_deed_outcomes`: **+3 rows**, county=glades, `data_source='municode_munidocs:GLADES-TD-V1'`.
  - `promote_tier1_from_outcomes()` invoked live → `{"promoted": 3}`.
- **Execution receipt**: ran the actual committed script (not just the exploratory steps) end to
  end a second time after inserting — 0 new inserts, 70/70 rows touched, evaluator unchanged.
  Confirms idempotency before wiring the cron.

## ULTRALOOP verification

Per the ULTRALOOP PROTOCOL (native `/effort ultracode` not available in this session — no such
menu item — so fell back to a manual Task-subagent fan-out, `ultraloop_mode='fallback'`), a
fresh-context general-purpose agent independently re-verified all 5 flipped letters by (a)
downloading source PDFs itself, (b) querying the live DB itself, (c) trying to refute each claim.
All 6 checks (A, E, B, F, H, and a dedicated ghost-success/fabrication check) returned **SURVIVED**
— zero refutations, zero fabricated `sold_amount`s, zero duplicate case_numbers, zero denominator
anomalies. 5 rows logged to `gold_standard_ultraloop_audit` (`dispatch_id`
`80efff0f-d30b-4769-bd15-3f175c136084`), all `survived=true`.

## SQL VERIFICATION

```sql
SELECT public.pencil_dod_evaluate_county('glades');
```

BEFORE (this session's starting point, matches the 08:20Z report):
```json
{"A": {"pass": false, "detail": "fc=0 td=0", "metric": 0}, "B": {"pass": false, "detail": "verified=0 closed_sold=0", "metric": null}, "C": {"pass": false, "detail": "matched_clean=0", "metric": null}, "D": {"pass": false, "detail": "matched_any=0", "metric": null}, "E": {"pass": false, "detail": "parcel_linked=0", "metric": null}, "F": {"pass": false, "detail": "tier1_sold=0 closed_sold=0", "metric": null}, "G": {"pass": true, "detail": "density=100.0 far= pk1000=", "metric": 100.0}, "H": {"pass": false, "detail": "hours since last_seen (SLA 48h)", "metric": null}, "I": {"pass": false, "detail": "card_complete=0 of 0", "metric": null}, "J": {"pass": false, "detail": "deal_complete=0 (triangle + two-arm CMA + ml_score + max_bid)", "metric": null}, "county": "glades", "V2_LITMUS": null, "auctions_total": 0}
```

AFTER (post-scraper, post-outcomes, post-promote, re-run of the committed script for idempotency
proof — both runs agree):
```json
{"A": {"pass": true, "detail": "fc=1 td=69", "metric": 1}, "B": {"pass": true, "detail": "verified=3 closed_sold=3", "metric": 100.0}, "C": {"pass": false, "detail": "matched_clean=0", "metric": 0.0}, "D": {"pass": false, "detail": "matched_any=0", "metric": 0.0}, "E": {"pass": true, "detail": "parcel_linked=69", "metric": 98.6}, "F": {"pass": true, "detail": "tier1_sold=3 closed_sold=3", "metric": 100.0}, "G": {"pass": true, "detail": "density=100.0 far= pk1000=", "metric": 100.0}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.0}, "I": {"pass": false, "detail": "card_complete=0 of 70", "metric": 0.0}, "J": {"pass": false, "detail": "deal_complete=0 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 0.0}, "county": "glades", "V2_LITMUS": null, "auctions_total": 70}
```

Did not run `gold_standard_loop()`/`gold_standard_certify()` per PARALLEL-FLEET RULES (other shards
mid-flight this window); the per-county evaluation above is the required substitute.

## Residual — next session priorities for glades

1. **C/D are genuinely unmeasurable, not failing-and-fixable.** There is no RealAuction or
   PropertyOnion presence for glades to diff against. If the STANDING AUTHORIZATION's
   clerk/official-records supplementary litmus is ever extended to counties with zero platform
   presence, glades' own Municode notices could theoretically self-litmus (compare the rolling
   foreclosure PDF against itself over time) — but that's a new idea, not yet authorized or built.
2. **I needs a real zoning substrate.** G passes on a 2-parcel base from a prior session; the 69
   new parcel_ids almost certainly don't overlap it. Unblocking I means running Phase 2 zoning GIS
   ingestion for glades at county scale (not a per-auction fix) — same class of work as the G hit
   lists other shards are running for brevard/duval. Out of scope for a single-county session.
3. **The 45 "no outcome annotation" tax-deed records are a B/F growth lever, not a dead end.** The
   Clerk appears to update a sale-date PDF with SOLD/REDEEMED annotations only when they happen to
   revisit that specific document — many older ones were never back-filled. A targeted follow-up
   scrape of `kofilequicklinks.com/gladesfl`'s book/volume/page index (previously ruled out for
   *bulk* discovery, per the 08:20Z report) could still work for *targeted* lookups against these
   45 known tax-deed-file numbers, since that's a much narrower query than an open-ended search.
   Worth a small follow-up, not urgent — B/F already pass at n=3.
4. **The scraper is county-specific by design** (`glades_municode_notices_scraper.py`, single
   hardcoded `MUNICODE_BASE`). Other small FL counties may also use Municode MuniDocs for notices
   — worth a quick check next time a shard hits a similarly "structurally blocked" small county,
   but not generalized here (K3 surgical-changes discipline — scope was glades only).
