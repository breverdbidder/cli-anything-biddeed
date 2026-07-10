# SHARD-7 Session Report — run 2346

dispatch_id: `010a05ae-e4f8-488a-954f-6d0497384f23`
chat_session: `architect-20260702T080000`
counties: levy, bay, hernando

## Status Board

| County | Start (brief) | End (verified live) | Notes |
|---|---|---|---|
| levy | 10/10 | **10/10** | Already certified going into session; re-verified, unchanged. |
| bay | 8/10 | **10/10 raw / NOT certifiable** | Raw PASS on all 10, but ULTRALOOP refuter found B, G, J do NOT survive scrutiny (see Audit Flag below). Do not certify. |
| hernando | 3/10 | **6/10** | A, C, D, G, H, J pass. B, E, F, I still fail — real progress on E and I this session, B/F genuinely blocked. |

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Confirm levy/bay status | Verify live | Both raw 10/10 confirmed via `pencil_dod_evaluate_county` | Bay's raw PASS turned out to hide 3 refuted letters (see below) — not caught until I read the existing ULTRALOOP audit ledger |
| Hernando B/F (sale results) | Build scraper, capture 3 past-due FC cases | **Blocked** — real independent-source path exists (LandmarkWeb) but requires session-aware form submission (ASP.NET MVC array-indexed POST) that failed with HTTP 500 on both the recon agent's attempt and my own direct replication. No browser-automation tool (Playwright/firecrawl-browser) was provisioned in this sandbox (no `firecrawl` CLI, no `FIRECRAWL_API_KEY`, no `playwright` package). | Full miss — needs infra follow-up |
| Hernando E (6 unresolved parcels) | Resolve via legitimate case-name lookup | 3/6 resolved (TaxSmart jqGrid direct-endpoint bypass, cross-verified against FL GIO). 3/6 (civil "CA" cases) blocked by the same LandmarkWeb/Civitek session-state problem as B/F. | Partial — 73.9% → 87.0% |
| Hernando I (zoning card) | Expand substrate for 6 FC parcels | 3/7 resolved with real GIS zone codes + ordinance-cited standards. 4/7 blocked: 3 parcels are `PDP(SF)` and the county's own GIS layer has `ZONE_NOTES="NO CASE NUMBER"` (no traceable ordinance); 1 parcel (`AR2`) has a real source (`hernandocounty.elaws.us`) that returned HTTP 503 all session, with Municode itself bot-blocking (403). | Partial — 30.4% → 43.5% |

## Verification Evidence (before/after JSON)

**Levy** — unchanged, still 10/10 (all letters PASS at 100%, see prior session).

**Bay** — raw evaluator output, unchanged by this session (no bay writes made):
```json
{"A":35,"B":100.0,"C":97.6,"D":98.8,"E":100.0,"F":100.0,"G":98.7,"H":1.9,"I":96.3,"J":100.0}
```
All 10 PASS. **But** see Audit Flag below — this number is misleading.

**Hernando** — before (session start) / after (this session's writes):
```
B: closed_sold=0, verified=0        -> unchanged (0 closed auctions exist; genuinely unmeasurable, not a data gap)
E: parcel_linked=17/23 (73.9%)      -> parcel_linked=20/23 (87.0%)
F: closed_sold=0, tier1_sold=0      -> unchanged (same root cause as B)
I: card_complete=7/23 (30.4%)       -> card_complete=10/23 (43.5%)
```
Confirmed via `SELECT public.pencil_dod_evaluate_county('hernando')` before and after each write. Two ULTRALOOP audit rows logged (`gold_standard_ultraloop_audit` ids 2633, 2634, both `survived=true`) documenting the exact query evidence for the E and I moves.

## AUDIT FLAG — bay B/G/J do not survive refutation (found via existing ULTRALOOP ledger, not newly run this session)

While confirming bay's status I read `gold_standard_ultraloop_audit` and found a same-day (2026-07-02, ~08:24-08:28Z) refutation pass had already run against bay, independent of this session. Three letters that show raw PASS are **refuted**:

- **B** (verified=6/closed_sold=6=100%): the `closed_sold` denominator is tautological — it only counts rows that *already* have a tier1-verified `sold_amount`. 10 additional `auction_status='concluded'` bay auctions carry PropertyOnion-sourced `po_sold_amount` evidence of a completed sale but are excluded from the denominator entirely (flagged `needs_source_rescrape=true`). True ratio against the plausible closed-sold population (16) is 37.5%, not 100%. **Not fixed by today's fleet-wide `pencil_dod_b_scope_fix`/`pencil_dod_f_scope_fix` migrations** (commits `6e5b42d5`, and shard-3's later F fix) — those fixed a different bug class (unbounded numerator from historical outcome-table imports), not this denominator-undercounting issue.
- **G** (density=98.7%, FAR/pk1000 blank): `v_zoning_gold_standard_kpi_v3` marks `far_applicable_parcels=0` for bay (100% of parcels flagged FAR-not-applicable), but a direct query of `v_zoning_gold_standard_card` shows 62/79 bay parcels actually have a non-null `max_far` — the applicability classifier is broken and is silently masking a real ~78% coverage gap via `LEAST(density, NULL, NULL)` dropping both NULL legs instead of counting them.
- **J** (deal_complete=82/82=100%): 45 of 82 (54.9%) bay `bid_decisions` rows share a byte-for-byte identical templated `factors` payload (arv=$50,000, max_bid=$0.00, hardcoded distress scores) across distinct tax-deed cases — a generic fallback stamped when real CMA data wasn't available, not per-property analysis. Technically satisfies J's literal non-null/key-presence definition, but doesn't satisfy what J is meant to certify. The same `arv=50000`/template pattern appears in 15+ other shard scripts across the codebase — this is very likely a **fleet-wide** pattern, not bay-specific.

I did **not** attempt to fix any of these three. B and G are shared evaluator/view logic — touching them mid-fleet-session risks flipping other shards' in-flight before/after comparisons, and the guardrails explicitly warn against modifying shared scoring infrastructure without extreme care (see shard-3's own B/F fixes today, which did full fleet blast-radius checks before shipping). J's fix would require either building real per-property CMA for 45 tax-deed cases (multi-day scope) or changing the shared J-generator's fallback behavior (also fleet-wide). **Recommendation for whichever session picks this up next**: treat bay as NOT certifiable until B/G/J are re-verified true-PASS, and treat the B-denominator and G-classifier bugs as fleet-wide defects worth a dedicated session (likely affecting many "10/10" counties the same way pinellas's F was just found to be 100% fake).

## Close-out protocol

Per PARALLEL-FLEET RULES, `gold_standard_loop()` / `gold_standard_certify()` were **not** run this session — the fleet log shows other shards actively committing in parallel (9 migrations landed from other shards during this session, including two shared-evaluator fixes). Verification for all three counties instead used per-county `pencil_dod_evaluate_county` calls, pasted above.

## Infra gap flagged for follow-up

Hernando's B/F and the remaining 3 E cases all terminate at the same wall: Hernando Clerk's official-records/case-search tools (`LandmarkWeb`, `Civitek OCRS`) are session/JS-driven ASP.NET applications that reject a replicated-cookie HTTP session (500 error on the actual search POST) and this sandbox had no browser-automation tool available (`firecrawl` CLI absent, no `FIRECRAWL_API_KEY`, `playwright` not installed). The **TaxSmart** platform (tax-deed only) was successfully reverse-engineered via its underlying jqGrid AJAX endpoint (`/TaxSmart/Home/GridSearchData`) without needing a browser at all — that trick does not carry over to LandmarkWeb, which serializes its search forms through a different (still-undiscovered) payload shape. Next session targeting hernando (or any county needing LandmarkWeb-style official-records data) should either provision a browser-automation tool or budget time to fully reverse-engineer the LandmarkWeb POST payload.
