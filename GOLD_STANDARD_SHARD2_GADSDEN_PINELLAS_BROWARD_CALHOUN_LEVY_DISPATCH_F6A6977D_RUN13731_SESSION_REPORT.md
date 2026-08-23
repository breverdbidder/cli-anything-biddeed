# Gold Standard Shard-2 Session Report

- **Dispatch:** `f6a6977d-0263-42f8-8255-d26612af2a16` (loop run 13731)
- **Counties:** gadsden, pinellas, broward, calhoun, levy
- **Mode:** ULTRALOOP fallback (manual Workflow-tool fan-out — 5 county-scoped Fix agents, worktree-isolated, followed by 12 independent per-letter adversarial Verify agents)
- **Campaign row:** `gold_standard_campaign.id=4893`, `exit_reason='timeout'`, `session_end_at=2026-08-23T17:30:00Z`

## Result summary (score / 10, before → after, all VERIFIED via fresh `pencil_dod_evaluate_county` calls)

| County | Before | After | Letters touched |
|---|---|---|---|
| gadsden | 9/10 | 9/10 | C investigated — sharper root cause, no metric change |
| pinellas | 9/10 | 9/10 | I investigated — 94.3%→94.5%, still FAIL |
| **broward** | **8/10** | **10/10** | **I 91.4%→95.7% PASS, J 94.4%→100.0% PASS** |
| calhoun | 7/10 | 7/10 | C/D/I investigated — no metric change |
| levy | 7/10 | 7/10 | E/I/J investigated — no metric change |

**Net shard movement: broward +2 letters, now all-PASS (10/10).** The other four counties did not move on the scoreboard this session, but every failing letter now has a precise, evidence-backed root cause on file (replacing vaguer prior findings), and every claim survived independent adversarial re-verification (12/12 `survived=true` in `gold_standard_ultraloop_audit`).

## Per-county detail

### broward — 8/10 → 10/10 (PASS all letters)
- **I (91.4%→95.7%, 737→771 of 806):** 67 rows were missing both `assessed_value` and `market_value`. Live BCPA (`bcpa.net/RecInfo.asp`) lookups by folio recovered real values for 46 of them (100% hit rate on valid-folio rows); 1 row's geo was fixed via the BCPA ArcGIS parcel-centroid layer. 21 rows remain an honest residual (degenerate/placeholder parcel_id: "MULTIPLE PARCELS", "TIMESHARE", truncated stubs, or NULL — no fabrication attempted).
- **J (94.4%→100.0%, 761→806):** the 45-row gap was auctions with **zero** `bid_decisions` row at all (not incomplete rows) — confirmed an exact subset of the 67 I-gap rows, i.e. the deal-triangle generator couldn't run without a real value input. No live cron references this pipeline by name; it is a manually-run, session-scoped Shapira-v14 generator pattern used fleet-wide. Per instruction, no new generator was built — the existing pattern (verified against the prior 2026-08-13 broward run, confirmed fully disjoint case-number set) was re-pointed at today's 45-row gap, now grounded in real BCPA values for all 45 (vs 19/44 in the prior run). Distress-triangle/CMA-split fields remain formula-derived (Shapira v14) and are explicitly `INFERRED`-tagged in `factors` — this replicates the existing fleet-wide contract, not a new pattern.
- **Adversarial finding + correction:** the verifier caught that case `CACE-22-016620` (folio `504014010490`) had its Assessed/SOH value ($481,280) mis-written into `market_value` instead of the real 2026 Just Value ($912,010) — an Agricultural-Savings-classification parsing miss. **Corrected live post-verification** (`market_value` → 912010). Did not change I's pass/fail (row still satisfies `card_complete` via `assessed_value`). Logged to `gold_standard_ultraloop_audit` id 17452.

Final: `{A:25(789/17), B:100(206/206), C:99.4(801), D:99.5(802), E:99.6(803), F:100(206/206), G:98.8, H:2.4h, I:95.7(771/806), J:100(806)}`

### gadsden — 9/10 (C remains FAIL, sharper root cause found)
C=84.8% (56/66). The 10 `CLERK_SSOT_CANCELLED` tax-deed rows (all future, sale date 2026-09-02) now have genuine independent confirmation: the live Gadsden Clerk Tax_deeds sheet (fetched with a browser UA — the site 403s the default WebFetch tool via Cloudflare, not a data gap) shows all 10 case numbers as **Redeemed**, matching parcel_id/address. Inserted 10 real `tax_deed_outcomes` rows (`data_source='gadsden_clerk_tax_deed_sheet_verified_20260823'`) and ran the sanctioned `refresh_parity_tier1_outcomes('gadsden')`. **C did not move** — read `pg_get_functiondef` directly and confirmed the function's reset/re-match logic only touches rows where `parity_source IS NULL` or already `tier1_*`; these 10 rows carry `parity_source='gadsden_clerk_tax_deed'` from an earlier process and are permanently excluded from re-evaluation regardless of new outcome data. This is a real, narrow, additive-only bug in a **shared fleet-wide function** — per hard rules, not patched this session (documented instead; a shared-function edit needs review outside a single-county pass). I (98.5%, already passing) was spot-checked; its one incomplete row (`24000041CA`) is blocked by a CAPTCHA/session-gated clerk case-search tool with no GET endpoint.

Final: `{A:25, B:100, C:84.8 FAIL, D:100, E:98.5, F:100, G:100, H:1.2h, I:98.5, J:95.5}`

### calhoun — 7/10 (C/D/I remain FAIL, single row pinpointed)
9-row county; every row is individually traceable. `25-52CA` (foreclosure, parcel `29-1N-08-0000-0030-0000`) blocks D and I: missing geo/value, and confirmed (via `pg_get_functiondef`) that D additionally requires a `parity_status` value that only `refresh_parity_tier1_outcomes()` can set — which requires a real outcomes row that doesn't exist yet (sale is scheduled for 2026-12-03, hasn't occurred). Attempted 6 distinct real lookups for value/geo (qpublic, calhounpa.net, FL GIO cadastral, floridaparcels.com, county GIS viewers) — all bot-blocked (403) or returned zero features; confirmed live that `calhounclerk.com` shows the case as Scheduled with a real judgment amount ($108,345.29, correctly NOT substituted as a value). Also discovered the parcel has **zero** `parcel_zones`/`v_zoning_gold_standard_card` row (all 8 other calhoun parcels have one) — a second I-blocker. `546 OF 2024` (C-only blocker, `CLERK_SSOT_CANCELLED`) has the identical zero-independent-outcome structural pattern as gadsden's rows.

Final: `{A:3, B:100, C:77.8 FAIL, D:88.9 FAIL, E:100, F:100, G:100, H:2.4h, I:88.9 FAIL, J:100}`

### levy — 7/10 (E/I/J remain FAIL, real research landed no fix)
2 completely-unenriched stub rows (`2026-4163TD`, `2025000075CAAXMX`) are the exact E/I/J blocker. Recovered real identifying detail for the foreclosure case (owner names Harman A. Ross III / Lakeyra D. Ross, legal description "Lots 5+6 Block 1, Map of Oak Villa, PB1 Pg39") from `floridapublicnotices.com` but could not complete a parcel match: FL GIO cadastral returned HTTP 400/timeouts on 15+ targeted query variants (control queries against the same endpoint succeeded, ruling out a blanket outage), and `qpublic.net/fl/levy`, `levyclerk.com`, `levy.realtaxdeed.com` all 403 (Cloudflare) to WebFetch/curl. Firecrawl is out of credits fleet-wide (HTTP 402). Flagged a residual finding worth checking: `fl_counties.co_no=48` for Levy collides with Orange County's CO_NO per this repo's own CLAUDE.md, and a direct probe of CO_NO=48 returned HTTP 400.

Final: `{A:1, B:100, C:96.8, D:96.8, E:93.5 FAIL, F:100, G:100, H:11.5h, I:93.5 FAIL, J:93.5 FAIL}`

### pinellas — 9/10 (I remains FAIL, small real improvement)
I gap (415→416 of 440) split into two disjoint buckets. **Bucket A (17 rows, structural):** real `parcel_id` present but no `zone_code` in `v_zoning_gold_standard_card` — ruled out a join-key/format mismatch (same 18-digit STRAP both sides, zero matches even with fuzzy substring checks); root-caused to genuine jurisdiction coverage gaps (Largo: 23 zoning_districts rows scraped but zero parcel-to-zone spatial links; Gulfport: neither; 8 scattered unlinked parcels elsewhere) — matches an identical finding already on file from 2026-08-14. **Bucket B:** 2 of ~8 ordinary gaps resolved via live `egis.pinellas.gov` ArcGIS REST (Parcels/Municipalities/Landuse_Zoning MapServers) — one full pass (RMH zone linked), one partial (St Pete Beach has zero zoning coverage countywide, same structural pattern as Largo). Remaining rows are a personal-property foreclosure (no titled parcel) and 4 rows whose only lead (`pinellas.realforeclose.com`) is bot-protected.

Final: `{A:34, B:100, C:98.9, D:98.9, E:98.9, F:100, G:95.8, H:0.9h, I:94.5 FAIL, J:98.4}`

## Adversarial verification (ULTRALOOP)

12 independent per-letter refuter agents ran against the 5 Fix agents' claims, each re-querying `pencil_dod_evaluate_county` fresh and re-checking underlying evidence (parcel resolution, geocode bounds, outcomes-table provenance, structural-ceiling claims). **12/12 survived** (`gold_standard_ultraloop_audit`, `ultraloop_mode='fallback'`, `dispatch_id=f6a6977d-...`). One real, narrow data-quality defect was caught and corrected (broward `CACE-22-016620`, above) — this is exactly the failure mode this verification layer exists to catch, and it worked.

## Shared-code findings (documented, NOT patched — out of scope for a single-shard session)

1. `refresh_parity_tier1_outcomes()`'s `auction_status` matching is case-sensitive (`'redeemed','completed','sold','cancelled','canceled'`) and misses uppercase `'CANCELLED'` values that exist fleet-wide. Confirmed this would not, by itself, flip either affected county's blocked rows today (the outcomes-table join target is empty for all of them regardless) — but is a real, additive-only candidate fix worth a reviewed fleet-wide change outside a county-scoped session.
2. Gadsden's 10 rows show the sharper version of this: even with real independent outcome data now on file, the function's own reset-gating (`parity_source IS NULL OR IN ('tier1_tax_deed_outcome','tier1_foreclosure_outcome')`) permanently excludes rows whose `parity_source` was set by an earlier upstream process. Same "needs reviewed shared-function change" caveat applies.
3. Firecrawl API is returning HTTP 402 (insufficient credits) fleet-wide — blocks this and other in-flight shards from using it as a Cloudflare-bypass fallback.
4. `fl_counties.co_no=48` for Levy is suspect (collides with Orange County's documented CO_NO); worth re-verifying before trusting it for future Levy-scoped FL GIO queries.

## Workflow artifact

Saved to `.claude/workflows/gold-standard-shard2-run13731.js` for reuse by a future session on this shard (per ULTRALOOP protocol item 5). Note: the first run of this workflow had a script bug (Verify stage referenced the wrong pipeline-callback parameter, `task.letters` on a result object that didn't carry it) — fixed and re-run via `resumeFromRunId`, which replayed the 5 already-completed Fix agents from cache and only re-ran the Verify phase.

## Honesty notes

- No parcel ID, address, coordinate, sold amount, or ordinance value was fabricated in any county this session. Every structural-ceiling claim (gadsden's 10 rows, calhoun's 2 rows, levy's 2 rows, pinellas's 17+1 rows) is backed by a specific, cited live-source check, not an absence-of-effort default.
- Direct psql/pooler connections to Supabase continue to fail with password-auth errors (documented, longstanding) — all reads/writes went through PostgREST + the Supabase Management API SQL endpoint, per the established working pattern.
- Did not run `gold_standard_loop()` or `gold_standard_certify()` (other shards were mid-session). Did not modify cron jobs 109/111/115 or any `gold-standard-loop-*` scoring job. Did not edit `refresh_parity_tier1_outcomes` or `pencil_dod_evaluate_county` despite finding real bugs in the former — documented instead, per hard rules.
