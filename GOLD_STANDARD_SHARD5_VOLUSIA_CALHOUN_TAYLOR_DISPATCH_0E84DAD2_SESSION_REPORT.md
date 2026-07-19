# Gold Standard Shard-5: volusia / calhoun / taylor — session report

dispatch_id: 0e84dad2-f52e-4eea-9126-a234235c3ed6
mode: ultracode fan-out (B/F clerk-outcome verification + taylor zoning research + adversarial refute) for calhoun/taylor, then a 10-letter adversarial re-verification pass for volusia to refresh its stale (8-9 day old, partly missing) ultraloop_audit evidence ahead of the certify gate.

## Status Board (before -> after, live `pencil_dod_evaluate_county`)

| County | Before (brief) | After (live, this session) | Delta |
|---|---|---|---|
| volusia | 10/10 (scoreboard, first time today) | **10/10 mechanically, 7/10 adversarially confirmed** | No metric changed. Adversarial audit found G is a likely ghost-success (see P0 below); E and F left genuinely unresolved. Audit table now honestly reflects this instead of a blanket pass. |
| calhoun | 7/10 (B/F fail) | **7/10, unchanged** | B/F genuinely blocked this session — see below. No fabricated data written. |
| taylor | 6/10 (A/B/F/I fail) | **6/10, unchanged** (A already flipped to PASS between brief and session start, unrelated to this session) | B/F/C/D/I/J all investigated; all genuinely blocked or already correctly failing. No fabricated data written. |

All numbers are from live `public.pencil_dod_evaluate_county(<county>)` calls run fresh at session close (2026-07-19 ~18:15 UTC), pasted verbatim.

### SQL VERIFICATION (fresh, this session, 2026-07-19 ~18:15 UTC)

```
SELECT public.pencil_dod_evaluate_county('volusia');
 -> A94 B100 C98.1 D98.9 E100 F100 G100 H2.7 I98.4 J100  (10/10 mechanical, auctions_total=373)

SELECT public.pencil_dod_evaluate_county('calhoun');
 -> A2(fc=2 td=5) B FAIL(verified=0 closed_sold=0) C100 D100 E100 F FAIL(tier1_sold=0 closed_sold=0) G100 H2.8 I100 J100  (7/10, auctions_total=7)

SELECT public.pencil_dod_evaluate_county('taylor');
 -> A4(fc=5 td=4) B FAIL(0/0) C55.6(FAIL, matched_clean=5 of 9) D55.6(FAIL) E100 F FAIL(0/0) G100 H2.0 I22.2(FAIL, card_complete=2 of 9) J55.6(FAIL)  (6/10, auctions_total=9)
```

## calhoun — B/F investigated, genuinely blocked, no fabrication

Live data showed exactly one past-due case with no recorded outcome: tax deed `171 OF 2023` (scheduled 2026-07-09, still `auction_status=upcoming`, no `tax_deed_outcomes` row). Dispatched an independent verify agent against `calhounclerk.com`. Result: `found=false`, evidence = the county's "Lands Available for Taxes" page explicitly states "There are no properties on the list of lands available at this time" — meaning the tax deed has not yet resolved to a recorded sale/no-sale outcome that's publicly postable. No result page exists to scrape. Reported UNKNOWN, not written to `tax_deed_outcomes`. B and F remain FAIL honestly (0/0 closed_sold — structurally not-yet-measurable for this 7-auction county, not a scraper bug).

## taylor — B/F/C/D/I all investigated, genuinely blocked, no fabrication

- **B/F**: 2 past-due foreclosures (`25-218 CA` 2026-07-16, `23-597 CA` 2026-07-14) checked against `taylorclerk.com/foreclosure-sales/` and the official records portal (`pubrecords.taylorclerk.com`, returned HTTP 403). Neither case appears on the current active-sales list (rolled off after their date) and no sale-results archive with bid amounts is published anywhere reachable. Reported UNKNOWN. B/F remain FAIL honestly.
- **C/D**: Root cause identified and CONFIRMED live: `propertyonion_listings` has **zero** rows for Taylor County (fips 12123) of any type — the PropertyOnion-coverage-gap scenario pre-authorized in CLAUDE.md ("C/D LITMUS FALLBACK"). Separately, of taylor's 9 auction rows, 4 tax-deed rows (`TDA 26-026/028/031/032`) carry `parity_status='matched_clean'` with `parity_checked_at=NULL` — a defaulted-but-never-actually-checked value, not a real litmus match (this is the direct cause of the 55.6% metric: 5 genuinely-checked rows out of 9 total). Attempted to independently verify those 4 against the clerk's `taxdeeds/{slug}/` detail pages: all 4 URLs **soft-404 (redirect to homepage)** — the stored `source_url`s do not resolve. The clerk's "Active Tax Deed Sales" listing page is JS-rendered client-side (confirmed via raw curl, WebFetch, and a $0-credit Firecrawl attempt — all returned no case data). Did not fabricate a `parity_checked_at` stamp without being able to independently confirm content. C/D remain FAIL honestly; standing authorization to adopt clerk-direct litmus is confirmed applicable but blocked on tooling (needs Firecrawl credits or a WAF-capable browser session next time).
- **I**: Root cause CONFIRMED: `v_zoning_gold_standard_card` only has 2 of 9 taylor parcels (the 2 inside City of Perry, zone RSF-2). Dispatched a dedicated research agent for the other 7 (unincorporated Taylor County). Findings: unincorporated Taylor County *does* publish a real 9-district Land Development Code (chapter 42) with citable district-standard PDFs (useful for **G**, not I) — but **no parcel-level GIS lookup exists**: `qpublic.net/fl/taylor/` is Cloudflare-WAF-blocked (403) from this sandbox, no ArcGIS `MapServer`/`FeatureServer` exists for Taylor County zoning (two web-search leads were false positives for Taylor County WV and Taylor MI), and FL GIO's statewide cadastral layer only carries `DOR_UC` tax-use codes, not zoning. All 7 parcels correctly reported `zone_code=UNKNOWN` rather than guessed. I remains FAIL honestly (22.2%, unchanged).
- **J**: unchanged (55.6%), tracks 1:1 with the C/D denominator gap — not independently addressed.

## volusia — adversarial re-verification surfaced a P0 finding, audit refreshed honestly (not a blanket pass)

Volusia hit 10/10 on the live scoreboard for the *first time* today (2026-07-19T13:30 UTC) but its `gold_standard_ultraloop_audit` evidence was 8-9 days stale for 6 letters and **entirely missing for C, G, H, I** — meaning it could not pass the SQL certify gate regardless of the scoreboard. Ran a 10-agent independent re-verification pass (one per letter, each told to query the live DB itself and default to `survived=false` on any anomaly or unreproducible number).

**Result: 7 of 10 letters cleanly confirmed (A, B, C, D, H, I, J). 3 were not counted as survived:**

- **G — P0 FINDING, likely fleet-wide ghost-success.** `v_zoning_gold_standard_kpi_v3` for volusia shows `pct_density_of_applicable=100.0` but `pct_far_of_applicable` and `pct_pk1000_of_applicable` are both `NULL` (0 of 432 parcels have FAR/parking marked applicable at all — not passing, *unevaluated*). Postgres `LEAST()` silently skips `NULL` arguments, so `LEAST(100.0, NULL, NULL) = 100.0` — the evaluator reports a clean 100% pass using only the density dimension, masking that FAR and parking coverage are completely absent. `zoning_assignments` (the parcel-level zone_code table) has **zero rows for volusia** under either county name or `co_no=64`. This is the same class of bug flagged in CLAUDE.md's brevard G-diagnosis note, but manifesting as a false PASS instead of an honest FAIL — **worth checking across every other county currently showing G=PASS**, since `LEAST()`-over-NULL is a shared evaluator behavior, not a volusia-specific data issue. Not patched this session (shared `pencil_dod_evaluate_county`/`v_zoning_gold_standard_kpi_v3` function, explicitly out of shard scope per guardrail #4 — "do not modify... gold-standard-loop-* scoring jobs" and the parallel-fleet shared-code-path caution). Flagged here for the next available cross-shard/infra session.
- **E** — unresolved, not disproven. The evaluator scopes its 100% figure to a 373-row operational subset, but raw `multi_county_auctions` has 3999 rows for volusia, of which only 9.3% carry a non-null `parcel_id` table-wide. Could not confirm whether the 373-row scope is an intentional current-cycle filter (consistent with letter A's confirmed, legitimate filter pattern) or a metric-inflation artifact. Needs a follow-up read of the evaluator's actual denominator logic.
- **F** — unresolved, not disproven. Could not independently reconstruct the claimed `tier1_sold=175/175` universe from any of 10+ raw-table filter hypotheses (best candidates landed at 115-127). Direction (high tier1 coverage) is plausible but the exact figure and scope are unconfirmed.
- Also disclosed (non-blocking): `gold_standard_county_status` holds a stale snapshot for I (290/290 @ 13:30 UTC) that disagrees with the live evaluator (367/373, ~4.5h later) — same PASS conclusion either way, flagged as a cache/consistency issue.

10 rows inserted to `gold_standard_ultraloop_audit` (dispatch `0e84dad2-f52e-4eea-9126-a234235c3ed6`, ids 7293-7302): **survived=true for A/B/C/D/H/I/J, survived=false for E/F/G**. Per the existing SQL certify gate design ("populate the audit table as you verify or certification blocks — fail closed, by design"), volusia will correctly **not** be certify-eligible from this audit even though the scoreboard shows 10/10 mechanically — that gate is working as intended and needed no override.

No `gold_standard_loop()` or `gold_standard_certify()` run this session (parallel-fleet protocol respected — other shards may be mid-flight). No PropertyOnion-sourced data written anywhere. No fabricated case outcomes, addresses, parcel IDs, or zone codes in any of the three counties.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| calhoun B/F | verify + backfill past-due outcome | Investigated 1 past-due case; genuinely no postable result exists yet | Honestly capped, not fabricated |
| taylor B/F | verify + backfill 2 past-due outcomes | Investigated both; no result archive reachable | Honestly capped, not fabricated |
| taylor C/D | reconcile parity | Root cause confirmed (PO zero-coverage + 4 never-checked TDA rows); fix blocked by JS-rendered clerk page + zero Firecrawl credits | Root-caused but not fixed; flagged for next session with tooling needs specified |
| taylor I | zoning substrate for 7 parcels | Confirmed unincorporated TC ordinance exists (useful for future G work) but no parcel-level GIS lookup exists (qPublic WAF-blocked, no ArcGIS layer) | Honestly capped at UNKNOWN for all 7, not guessed |
| volusia | not originally scoped as "fix" work (already 10/10) | Ran adversarial audit refresh instead; found G is a likely false-positive (P0) | Net-new finding, escalated rather than silently certified |

## Verification Evidence

- 10 audit rows written this session (`gold_standard_ultraloop_audit` ids 7293-7302, dispatch `0e84dad2-f52e-4eea-9126-a234235c3ed6`) — see per-letter breakdown above.
- Zero DB writes to `multi_county_auctions`, `foreclosure_outcomes`, or `tax_deed_outcomes` for calhoun/taylor this session — every lead investigated dead-ended honestly (JS-rendered pages, WAF blocks, no posted results yet, zero Firecrawl credits), and per Honesty Protocol blank beats wrong.
- No code/migration changes this session — this was a pure diagnosis + adversarial-audit session. No files besides this report were touched.

## Next-session priorities

1. **Cross-shard/infra escalation (highest leverage): audit `v_zoning_gold_standard_kpi_v3` / `pencil_dod_evaluate_county`'s G computation for the `LEAST()`-over-NULL ghost-success pattern across every county currently reporting G=PASS**, not just volusia. This could be inflating certification readiness fleet-wide. Requires touching shared scoring infra — needs an infra-scoped session, not a county shard.
2. taylor C/D/I: unblock by either (a) topping up Firecrawl credits to render `taylorclerk.com`'s JS tax-deed listing and confirm the 4 TDA rows against real content, or (b) a Playwright/`firecrawl-browser` session that can pass qPublic's Cloudflare WAF challenge to get parcel-level zoning for the 7 unincorporated parcels.
3. calhoun/taylor B/F: no action available until the underlying clerk auctions actually resolve and post results — revisit after their next scheduled sale dates pass (calhoun's next tax deed batch: 2026-08-13; taylor's next: 2026-07-20/07-23/07-30).
4. volusia E/F: resolve whether the evaluator's 373-row operational-subset scope is intentional (read the actual SQL function body via psql/Supabase CLI migration history, not just REST inference) before either letter can be marked cleanly survived.
