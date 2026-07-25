# Gold Standard shard-13 taylor — dispatch 4c2cb537, loop run 6288

## Before/after (live `pencil_dod_evaluate_county('taylor')`)

| Letter | Before | After | Change |
|---|---|---|---|
| A | PASS (4) | PASS (4) | unchanged |
| B | FAIL (null, verified=0 closed_sold=0) | FAIL (null, verified=0 closed_sold=0) | unchanged — reconfirmed blocked, 3rd independent same-day/session check |
| C | PASS (100.0) | PASS (100.0) | unchanged |
| D | PASS (100.0) | PASS (100.0) | unchanged |
| E | PASS (100.0) | PASS (100.0) | unchanged |
| F | FAIL (null, tier1_sold=0 closed_sold=0) | FAIL (null, tier1_sold=0 closed_sold=0) | unchanged — coupled to B (same closed_sold=0 denominator) |
| G | PASS (100.0) | PASS (100.0) | unchanged |
| H | PASS (4.0 → 9.1) | PASS (9.1) | unchanged (freshness, expected drift) |
| I | FAIL (88.9, card_complete=8 of 9) | FAIL (88.9, card_complete=8 of 9) | unchanged metric — see below for real, sourced, non-metric-moving progress |
| J | PASS (100.0) | PASS (100.0) | unchanged |

**7/10 → 7/10.** No letter flipped this session. This is an honest plateau, not idling: every remaining avenue for B, F, and I that this session's tooling could reach was tried, tested, and — where it failed — the failure mode was independently confirmed rather than assumed.

## Method: ULTRALOOP (native Workflow tool)

Ran `/effort` was not invoked (headless dispatch); used the native `Workflow` tool directly per the fallback path in the ULTRALOOP PROTOCOL, `ultraloop_mode='native'`. Phase 1 fanned two parallel research agents (Taylor B/F official-records discovery; Taylor I residual parcel research). Phase 2 fanned one independent adversarial refuter per claim, with zero visibility into the other agent's tool-call history — each refuter re-fetched primary sources from scratch. I then personally re-verified the refuters' own findings with a third, independent pass (direct curl/httpx from the main session) before writing anything live, since one refuter's technical diagnosis (why an ArcGIS query failed) itself turned out to be wrong on a sub-point — see below.

## What was checked for B/F (3-deep verification, all confirmed blocked)

1. **`pubrecords.taylorclerk.com/PublicInquiry/Search.aspx`** — Taylor's actual local official-records platform (CDS/nScribe "PublicInquiry" software, confirmed via a live, unblocked sibling instance on the same software at `gadsdenclerk.com`, whose doc-type dropdown includes exactly the types needed: `TD`, `CT`, `CS`, etc.). Returns Cloudflare interactive-challenge `403` (`cf-mitigated: challenge`) on every fetch — reproduced independently 4 times this session (2 workflow agents, 1 refuter, 1 direct curl from the main session with a standard browser UA). Genuinely blocked, not a dead link.
2. **`myfloridacounty.com/official_records/`** (statewide portal, a lead the refuter flagged as never-investigated) — checked directly this session. Its own Taylor County dropdown entry resolves to the *exact same* `pubrecords.taylorclerk.com` URL. Confirms there is no separate statewide bypass; same Cloudflare wall.
3. **`taylorclerk.com/departments/tax-deeds-surplus/`** — real, populated table (a refuter finding the original researcher missed), but dated "as of 2025-02-19" and covers TDA cases only through the low 20-0XX range. Does not contain TDA 26-026 or any other 2026 case. Confirmed stale/out-of-scope, not a live source.
4. **`taylorclerk.com/departments/foreclosure-sales/`** — live "Active Foreclosure Sales" listing. 25-196 CA and 25-218 CA (both past their auction dates as of this session) are **absent** — confirmed by direct fetch+grep. Only still-scheduled 23-597 CA appears (Status: scheduled). Confirms the prior-session finding that closed cases are removed with no result ever exposed on this page.
5. **`qpublic.net/fl/taylor/`** — also Cloudflare `403 cf-mitigated:challenge`, re-checked fresh this session.
6. **`taylor.realtdm.com`** — remains a RealAuction TEST sandbox tenant per `pipeline.counties.notes` (unchanged prior finding).
7. **Firecrawl workaround** — `FIRECRAWL_API_KEY` is present but returned `HTTP 402 insufficient credits` on a live test this session against the Cloudflare-gated URL. A real workaround (top up credits, or a headless-browser tool), not something this session can resolve without a spend decision.

No sold_amount/winning_bid data exists anywhere accessible to write for B/F this session. Nothing fabricated.

## What moved for I (real, sourced, but does not flip the metric)

Case 23-597 CA (parcel_id `05026-000`) previously carried a placeholder address (`"TAYLOR COUNTY, FL"`) and a latitude/longitude that a prior session had shown resolves to an *unrelated* parcel (05706-500, a City of Perry road right-of-way).

This session independently fetched the primary recorded **Summary Final Judgment of Foreclosure** (Taylor County Official Records Book 928, Page 452-458, Instrument 250006203, recorded 2025-11-14) via `taylorclerk.com/uploads/2026/07/23-597-CA.pdf`, and cross-checked it against two more independent sources (a Re-Notice of Sale filed 2026-07-21, and the live `foreclosure-sales` listing, which shows Judgment $92,079.12 — matches our DB exactly). All three agree on:

- **Real address:** 101 Buffalo Drive, Perry, FL 32348
- **Legal description:** Lot 101, Belair Manor Subdivision, an unrecorded subdivision of a portion of the E 1/2 of SW 1/4 of SW 1/4 of Section 26, Township 4 South, Range 7 East, Taylor County, Florida

Applied live via `supabase/migrations/20260725_gold_standard_shard13_taylor_i_address_verified.sql`: `property_address`, `city`, `zip`, `legal_description` updated; the confirmed-wrong `latitude`/`longitude` nulled per BLANK > WRONG rather than left as a silently-incorrect coordinate.

**This does not move the I metric.** The evaluator's `card_complete` formula requires `parcel_id` to resolve to a `zone_code`-linked row in `v_zoning_gold_standard_card`. The court judgment documents use metes-and-bounds/lot-in-unrecorded-subdivision language only — no parcel number is stated anywhere in any of the three documents fetched. `parcel_id = '05026-000'` itself remains **unresolved**, and was deliberately left untouched (removing it would regress E from 100% to 88.9%, an unrelated and unjustified regression).

### Why the parcel_id couldn't be resolved this session (root-caused, not just retried)

FL GIO Statewide Cadastral ArcGIS FeatureServer **filtered** `/query` calls (`WHERE CO_NO=62 AND ...`) time out from this sandbox's network egress. This was independently confirmed three separate times: by both original workflow agents, and by a third, fully independent test run in the main session itself (`httpx`, 45s timeout, clean `ReadTimeout`). Unfiltered/metadata calls against the same endpoint succeed (`HTTP 200`) — so this is a real, narrow, environmental egress limitation on filtered queries, not a code bug, a quoting bug, or a dead endpoint. One refuter agent's specific technical diagnosis (claiming quote-mangling caused `400` errors, and a separate claim of `HTTP 000` total network blockage) was itself independently falsified in this session's third pass — worth flagging since it shows the value of the extra verification layer: even a refuter's stated root cause needs checking, not just its bottom-line verdict.

## Adversarial audit trail

2 rows in `gold_standard_ultraloop_audit`, both `survived=true`, `dispatch_id = 4c2cb537-516e-441e-b381-3f9a7d906ef6` (letters B, I). Each row's `refuter_evidence` records the specific independent checks (Cloudflare header dumps, page-content greps, Firecrawl 402 response, PDF cross-reads, ArcGIS timeout repro) that back the `survived=true` verdict — these are re-confirmations of prior-session conclusions with new evidence and newly-ruled-out avenues, not novel passing claims, so no certification-gate implications.

## Verification protocol evidence

```sql
SELECT public.pencil_dod_evaluate_county('taylor');
-- I: {"pass": false, "detail": "card_complete=8 of 9", "metric": 88.9}   -- unchanged
-- B: {"pass": false, "detail": "verified=0 closed_sold=0", "metric": null}  -- unchanged
-- F: {"pass": false, "detail": "tier1_sold=0 closed_sold=0", "metric": null}  -- unchanged
-- all other letters unchanged, no regressions
```

## Honest residual / next-session priorities for taylor

1. **B/F**: genuinely blocked pending one of — (a) a real headless-browser tool with JS execution to clear the Cloudflare Turnstile challenge on `pubrecords.taylorclerk.com/PublicInquiry`, (b) a Firecrawl credit top-up (a spend decision, out of this session's scope) and retry with `waitFor` high enough to auto-solve the challenge, or (c) locating a genuinely different, not-yet-found source. All Taylor-adjacent leads (MyFloridaCounty, qpublic, RealTDM, tax-deed surplus page, foreclosure-sales listing) are now exhausted and documented — a future session should not re-spend a cycle re-checking these same six, already dead, avenues.
2. **I residual (parcel 05026-000)**: needs either a working (non-timing-out) path to FL GIO's ArcGIS `/query` endpoint with a `CO_NO`+attribute filter (this sandbox's filtered-query timeout is worth escalating as an infra issue, since it blocks any future session's attribute-based parcel lookups statewide, not just Taylor), or direct access to the Taylor County Property Appraiser's own search backend (`taylorcountypropertyappraiser.org` — confirmed to be a dynamic JS search form, not GET-able via plain HTTP fetch tools).

## Parallel-fleet note

Per PARALLEL-FLEET RULES, the fleet-wide `gold_standard_loop()`/`certify()` was **not** run this session — only this county's live per-county evaluation is reported above.
