# GOLD STANDARD SHARD-1: clay, okeechobee, desoto, bradford — session report

dispatch_id: 42aac1fb-a62d-48d7-9c93-e292496337d5
chat_session: architect-20260719T160000
date: 2026-07-19
mode: ultracode (Workflow tool, fallback ultraloop_mode — native `/effort ultracode` menu not invoked, manual fan-out used instead)

## Status Board

| County | Before | After | Certified this session? |
|---|---|---|---|
| clay | 10/10 | 10/10 | Already gold before this session — no work needed |
| okeechobee | 9/10 (I fails) | 9/10 (I fails) | No — see residual |
| desoto | 7/10 (B/F/I fail) | 7/10 (B/F/I fail) | No — see residual |
| bradford | 6/10 (E/B/F/I fail) | 6/10 (E/B/F/I fail) | No — see residual |

**No letter flipped pass/fail this session.** This is reported honestly per the HONESTY PROTOCOL and SHIP GATE — real, verified data-quality fixes were shipped (2 migrations, live on main), but none were sufficient on their own to cross a pass threshold. Every blocker below is a genuine external-source access limitation (Cloudflare bot protection, login-gated court records portals, JS-only GIS viewers, a RealAuction tenant that doesn't exist for this county), not a swallowed failure or a fabrication.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| clay | Confirm 10/10, no fix | Confirmed 10/10 live, untouched | None |
| okeechobee I | Fix 4 gap rows to push card_complete ≥95% | Investigated all 4; 1 fixed (real parcel_id), 3 genuinely BLOCKED; fixed row still fails zoning-link join | Fix applied but insufficient — I stayed at 92.6 |
| desoto B/F | Backfill sold_amount for 2 past-due sales via RealForeclose | RealForeclose has no DeSoto tenant (platform mismatch, not a login/scrape failure); DeSoto Clerk's PDF-only disclosure has no matching cases/fields | Full scope deviation — original planned method (adapt santa_rosa RealForeclose script) does not apply to this county |
| desoto I | Backfill zoning for 2 parcels | 4 GIS sources checked; only match was a stale 2013 Arcadia-only FeatureServer with zero hits for these parcels | Blocked, no write |
| bradford E | Find parcel for 1 orphan case | Full case details (plaintiff, legal description) recovered via BC Telegraph legal notice, but no parcel_id/address resolvable from any accessible source | Partial research success, no DB write possible |
| bradford I | Enrich geo/value for 4 parcels | All 4 verified and applied (migration a801c9d1) | Succeeded, but letter still fails — bradford's zoning substrate (parcel_zones) is fake placeholder data with synthetic IDs, unrelated to real parcels |
| bradford B/F | Backfill 1 sale result | BLOCKED — bradfordclerk.com Cloudflare-403, OCRS login-gated, Firecrawl out of credits | No write |

## Verification Evidence

Live query run independently by the orchestrating session (not just the workflow's self-report), immediately after both migrations were pulled from `origin/main`:

```
SET statement_timeout = 0;
SELECT county, jsonb_pretty(public.pencil_dod_evaluate_county(county))
FROM (VALUES ('clay'),('okeechobee'),('desoto'),('bradford')) AS t(county);
```

Run at 2026-07-19T~16:47Z UTC. Results (unchanged from session-open baseline on every letter, confirming no regression and no false-positive credit):

- **clay**: A✓ B✓(100.0) C✓ D✓ E✓ F✓(100.0) G✓(97.6) H✓ I✓(100.0) J✓(100.0) — 10/10
- **okeechobee**: A✓ B✓(100.0) C✓ D✓ E✓(96.3) F✓(100.0) G✓(100.0) H✓ **I✗(92.6, card_complete=50 of 54)** J✓(100.0)
- **desoto**: A✓ **B✗(null, verified=0 closed_sold=0)** C✓ D✓ E✓(100.0) **F✗(null, tier1_sold=0 closed_sold=0)** G✓(100.0) H✓ **I✗(75.0, card_complete=6 of 8)** J✓(100.0)
- **bradford**: A✓ **B✗(null, verified=0 closed_sold=0)** C✓ D✓ **E✗(80.0, parcel_linked=4)** **F✗(null, tier1_sold=0 closed_sold=0)** G✓(100.0) H✓ **I✗(0.0, card_complete=0 of 5)** J✓(100.0)

## What Shipped (real, live, on main)

1. `migrations/20260719_gold_standard_shard1_okeechobee_i_fix.sql` (commit `b82591e4`) — replaced the literal placeholder string `'MULTIPLE PARCELS'` with the real, clerk-notice-verified lead parcel `1-05-37-35-0060-00640-0170` for case 472025CA000225CAAXMX. Genuine data-quality fix; did not flip letter I because that parcel still has no zoning-district linkage (Basswood Inc. Unit No. 6 subdivision has zero `parcel_zones` coverage).
2. `migrations/20260719_gold_standard_shard1_bradford_i_geo_value_backfill.sql` (commit `a801c9d1`) — backfilled verified lat/lon (EPSG:2238→WGS84 transform from bradfordappraiser.com GIS) and 2025-certified assessed/market values for all 4 real Bradford parcels with a parcel_id. Did not flip letter I because Bradford's only 3 `parcel_zones` rows are pre-existing fake bootstrap data (`BRADFORD-PARCEL-0001/2/3`, source=`shard5_bootstrap_run338`) tied to synthetic IDs that match none of the real parcels.

Both migrations were adversarially re-verified by an independent refuter agent that re-ran `pencil_dod_evaluate_county` live and checked the outcomes tables directly for contamination (PropertyOnion / `%promote%` data_source) — none found; both survived=true.

## Residual Gaps (next session priorities)

1. **Browser automation is the actual blocker for 5 of 7 open items.** okeechobee's 3 remaining gap cases, desoto's zoning lookup, and bradford's E/B/F cases all dead-end at either a Cloudflare bot challenge (bradfordclerk.com), a login-gated OCRS portal (Civitek, both Bradford and Okeechobee), or a JS-only GIS viewer that renders attribute data client-side (desotopa.com, okeechobeepa.com's tax-deed portal). None of these are solvable with curl/WebFetch/WebSearch. Firecrawl is confirmed out of credits (insufficient credits error, live-tested this session) so it cannot serve as the workaround either. **Recommendation: restore Firecrawl credits or grant a real browser-automation tool (Playwright/browser-use) to the next session before re-attempting these.**
2. **DeSoto is not on RealForeclose** — the shard brief's playbook assumption (reuse the santa_rosa RealForeclose script) does not hold for this county. DeSoto Clerk publishes foreclosure info as static PDFs with no per-case winning-bid field. B/F for desoto need either a different, yet-undiscovered results source, or manual confirmation that these two 2026-07-02 auctions actually produced a recorded sale.
3. **Bradford's zoning substrate is fake.** `parcel_zones` for bradford (3 rows) is placeholder/bootstrap data unrelated to any real parcel. This blocks I regardless of how much geo/value enrichment happens on the auction rows. Needs a real Phase-4-style ordinance scrape (Starke jurisdiction_id 844, Brooker 987) to close.
4. **Okeechobee's Basswood Inc. Unit No. 6 subdivision has zero zoning coverage** — same shape of gap as #3, smaller scope (2 parcels, 1 case).
5. Two Okeechobee cases (472025CA000130CAAXMX, 472025CA000205CAAXMX) and one Bradford case (25000439CAAXMX) have no discoverable parcel at all through automated means — flagged for human/phone follow-up with the respective Property Appraiser/Clerk offices.

## Honesty Protocol Compliance

- No claim in this report is asserted as VERIFIED without a live query or fetched source cited above.
- Every BLOCKED item states specifically what was tried and why it failed (platform mismatch, Cloudflare, login gate, stale/wrong-county data, JS-rendered attributes) rather than a vague "couldn't find it."
- Zero fabricated parcel_ids, addresses, coordinates, or dollar amounts were written. Where research came back BLOCKED, no compensating guess was substituted (BLANK > WRONG).
- `gold_standard_ultraloop_audit` was populated with one adversarial-refuter row per county+letter claim this session (survived=true on all 7 — every claim matched live DB reality on inspection).
