# Gold Standard shard-3: escambia, st_lucie, lake, wakulla — dispatch 5f45a239

**Date:** 2026-08-27 (08:00Z wave)
**Method:** ULTRALOOP workflow — 5 parallel diagnose/fix agents (one per county-letter target), each followed by an independent adversarial refuter agent that re-fetched live data before accepting the claim.

## TL;DR

| County | Before (session start, live) | After (final live recheck) | Change |
|---|---|---|---|
| escambia | 10/10 | 10/10 | none needed — already fully passing (fixed by an earlier wave today) |
| st_lucie | 8/10 (C, G fail) | 8/10 (C, G fail) | no letter flipped; one fix attempt (G) refuted, not shipped |
| lake | 6/10 (C, E, G, I fail) | **7/10** (C, G, I fail) | **E: FAIL 93.5% → PASS 99.3%**, VERIFIED |
| wakulla | 6/10 (C, E, I, J fail) | **7/10** (C, I, J fail) | **E: FAIL 86.4% → PASS 100.0%**, VERIFIED, breaks a 6-session dead end |

Two letters shipped and independently adversarially confirmed live: **lake E** and **wakulla E**. Two fix attempts (**st_lucie G**, **lake G**) were built with real, cited ordinance research but **refuted by the adversarial verifier** — the writes did not durably land in the live DB — and were correctly **not** counted as passing. All four counties' **C** failures were reconfirmed as a canon-level structural cap, not a data defect (see below), consistent with a same-day cross-shard finding on three other counties.

## escambia — freshness/regression audit only (no fix needed)

Confirmed live via `pencil_dod_evaluate_county('escambia')`, twice (session start and end, identical): **10/10 PASS**, `auctions_total=496`. B had been FAIL earlier today (66.7%) per the dispatch brief and was fixed by an earlier same-day session (migration `20260827_gold_standard_escambia_b_realforeclose_verify.sql`) before this shard picked up the county — no action needed here.

**Not yet certified.** Per `gold_standard_county_status` history: Aug 25 was a clean 10/10 day; Aug 26 broke on B and stayed FAIL through 16 consecutive runs into Aug 27; B was fixed and reverified PASS at 13:30:00Z today. Certification requires two consecutive clean 10/10 days — today is the first clean day of a new streak, contingent on tomorrow (Aug 28) also going 10/10.

**Risk signal (small, not yet material):** 3 rows created in the last 48h (2025 CA 001976, 2025 CA 001880, 2026 CA 000047) have `parity_status=NULL` and no `bid_decisions`/card-completeness data yet — the same leading-indicator pattern that caused a same-day pass→fail flip on 2026-07-24 (31-row spike). At 3 rows against a ~495-row denominator this doesn't move the ratio yet, but flag for whoever next touches escambia to confirm the backfill cron catches these before volume grows.

## lake — E shipped (PASS), G attempted and refuted, I/C honestly still blocked

**E (parcel linkage): FAIL 93.5% (130/139) → PASS 99.3% (138/139).** Fixed 8 stub rows (case numbers 2026CA000560, 2023CA000367, 2025CA001590, 2025CC005329, 2025CA002454, 2025CC010839, 2025CA001729, 2025CA001082) that previously had zero data beyond a case number. Lever: authenticated against the Lake Clerk's own ShowCase court-records API (`courtrecords.lakecountyclerk.org`, no CAPTCHA on case-number search), pulled each Final Judgment/Order PDF, OCR'd the scanned image for the court-printed property address and legal description, then cross-matched against Lake County's own ArcGIS Tax Parcels layer (`gis.lakecountyfl.gov/lakegis/.../MapServer/20`) to get `parcel_id`, `assessed_value`, and a centroid for lat/lon. **Adversarially verified survived=true** — the refuter independently re-queried the same ArcGIS layer for all 8 parcel_ids and got exact address/value matches, and independently confirmed the live RPC shows E passing. This also resolves a case (`2026CA000560`, Lady Lake) an earlier session (`ARCHITECT_TRIAGE_19423`) had explicitly left as a dead end — reading the court's own judgment PDF sidestepped the Villages/Lady Lake lot-numbering ambiguity that blocked the prior lever.

**G (zoning FAR/density/parking): attempted, refuted, still FAIL 66.7%.** The fix agent researched real ordinances for Leesburg, Groveland, Clermont, Eustis, Tavares, Umatilla, and Mascotte and wrote `far_regulated`/`pk1000_regulated` flags with cited sources to 19 `zoning_districts` rows, claiming far coverage improved 94.1%→98.0%. **The adversarial refuter's independent fresh read directly contradicted this**: a live RPC recheck showed `far=94.1` (the claimed *starting* baseline, not the claimed 98.0 ending value), and 16 of the 19 named rows showed `far_regulated=NULL` on a fresh GET rather than the claimed true/false. The fix agent's own narrative had already flagged a live "concurrency finding" — values it had just verified set were observed reverting to NULL between successive GETs mid-session on the same rows. **This claim was correctly NOT shipped** (logged `survived=false` to `gold_standard_ultraloop_audit`, id 18768). Root cause is UNKNOWN — possible causes include a concurrent writer (another parallel shard/session touching the same table), a reconciliation job that resets unconfirmed manual edits, or a PostgREST/replica read-lag artifact — but the symptom (write appears to land, then reads back NULL minutes later) is reproducible and was seen independently on two different counties in this same session (see st_lucie below). **Flagging for the AI Architect: before any future session spends budget on G for lake or st_lucie, this needs to be root-caused, or all such fixes will keep silently reverting.**

**I (property card completeness): still FAIL 92.8% (129/139), honestly blocked.** The 8 newly-address/parcel-linked rows from the E fix have no `zoning_assignments` row yet (verified empty). Point-in-polygon checked against Lake's own zoning ArcGIS layer (MapServer/50): only 1 of 8 (38144 Brookside Dr, unincorporated county) is covered; the other 7 sit inside Eustis, Lady Lake, Leesburg (×2), Tavares, and Minneola — five separate municipal zoning ordinances that would need individual research, the same class of gap as the still-open G ceiling. Not fabricated to force a pass.

**C: unchanged FAIL 87.1%, canon-capped — see cross-county finding below.**

## wakulla — E shipped (PASS), breaking a 6-session dead end; I/J honestly still blocked

**E (parcel linkage): FAIL 86.4% (38/44) → PASS 100.0% (44/44).** Fixed all 6 remaining stub rows (2026-TXD-097, -117, -118, -120, -122, and 25-CA-105), which six prior sessions had left unresolved after exhausting PDF-URL guessing, the Tax Collector roll, FL GIO, and qpublic (Cloudflare-blocked). The genuinely untried lever worked: the Wakulla Clerk's **LandmarkWeb** recorded-document search (`wakullaclerk.com/LandmarkWeb`), searched by case number and defendant name, cross-confirmed against the Wakulla Tax Collector's own parcel search and the US Census geocoder. The five TXD cases turned out to be **redeemed-before-sale** (a Notice of Application for Tax Deed followed weeks later by a Release) — that's *why* no deed record existed, confirming rather than contradicting the six prior sessions' inability to find a deed. `25-CA-105` (a foreclosure case no prior session had attempted) resolved via its own Lis Pendens + Final Judgment. **Adversarially verified survived=true** — the refuter independently re-queried the Tax Collector API for all 6 property numbers and got exact address/owner/tax-bill matches, and independently confirmed `bid_decisions` is genuinely empty for all 6 cases (the disclosed J gap, not a fabrication cover-up).

**I and J: still FAIL 86.4% (38/44) each, honestly blocked, real causes identified.**
- I: for 3 of the 6 rows (TXD-117/118/120), a correct `zoning_assignments` row **already exists** from an Aug-16 bulk ingestion (confirmed via a duplicate-key conflict on re-insert) — the gap is that `v_auction_property_card`'s zoning join doesn't materialize it (`zoning_match_method` stays `'none'`), a generator/materialization bug, not a missing-data gap. Out of this dispatch's scope to repair. The other 3 rows (TXD-097, TXD-122, 25-CA-105) have zero FeatureServer PIN match at all — outside that dataset's coverage.
- J: `bid_decisions` is confirmed empty (0 rows, live-queried) for all 6 cases. Real `market_value`/`assessed_value` now exist as an ARV basis from this session's E fix, so a deal-triangle generator run could now produce real rows — but building/running that generator was explicitly out of scope for this dispatch.

**C: unchanged FAIL 84.1%, canon-capped — see below.**

## Cross-county finding: C is not fixable per-county (reconfirmed independently for all 3 failing counties this session)

This session independently reconfirmed — via direct live queries, without needing agent time — the same finding a sibling shard documented today for calhoun/manatee/taylor in `GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md`:

- **st_lucie**: 249 total rows, 201 `matched_clean`(tier1)/`PARITY_OK` + 47 `CLERK_SSOT_CANCELLED` + 1 `matched_divergent` = 201/249 = 80.7%. Removing the 48 cancelled/divergent rows from the denominator would make C = 100%.
- **lake**: 137 non-PropertyOnion rows, 18 genuinely `CLERK_SSOT_CANCELLED`. 
- **wakulla**: 44 rows, 37 `matched_clean`(tier1)+`PARITY_OK`, 7 `CLERK_SSOT_CANCELLED` = 37/44 = 84.1% exactly, matching the live evaluator.

C's canon deliberately excludes `CLERK_SSOT_CANCELLED` from its passing set (D includes it). All three of this shard's C-failing counties sit at 7.7%–19.3% cancellation rates — well above the ~5% slack the 95% threshold allows — driven entirely by genuine, correctly-classified cancellations, not data defects. **No further per-county C diagnosis is warranted for these three counties** until a canon-level decision is made (the three options are already laid out in the sibling shard's finding doc). This session did not modify `pencil_dod_evaluate_county` per explicit scope restriction.

## Guardrail compliance

- No `parcel_id`, `sold_amount`, `parity_status`, ordinance value, or `bid_decisions` row was fabricated. Every positive claim above was independently re-verified by a second agent against live sources before being counted.
- The two G fix attempts, despite real underlying ordinance research with genuine citations, were **not shipped** because their writes did not durably persist — logged as `survived=false` in `gold_standard_ultraloop_audit` (ids 18767, 18768) per the ULTRALOOP protocol's false-positive ledger, not silently discarded.
- `pencil_dod_evaluate_county` and `gold_standard_loop()` were not modified.
- `gold_standard_campaign` (dispatch `5f45a239-a0be-4a29-be81-84d1be80cea7`) checkpointed with final `criteria_passed` per county, `exit_reason='timeout'`.

## Residual / next-session priorities

1. **Root-cause the zoning_districts write-reversion**: both G attempts (st_lucie, lake) independently observed correctly-written `far_regulated` values reading back as `NULL` minutes later. Same symptom, two counties, same session — reproducible, not a one-off. Needs investigation before more G budget is spent on any county.
2. **lake I / wakulla I**: both now structurally gated by non-zoning-boolean issues — lake needs 5 municipal zoning ordinances (Eustis, Lady Lake, Leesburg, Tavares, Minneola) researched for the newly-linked parcels; wakulla needs the `v_auction_property_card` zoning-materialization gap fixed (data already exists in `zoning_assignments` for half the gap rows).
3. **wakulla J**: `bid_decisions` generator needs to run for the 6 now-address-complete cases — real ARV inputs exist, nothing blocking except running the existing deal-triangle pipeline.
4. **C canon decision**: escalate again (this is now the second same-day shard independently hitting this ceiling on 6 total counties) — recommend Ariel/AI Architect pick Option A/B/C from the sibling finding doc rather than continuing to burn per-county sessions re-confirming the same structural cap.
