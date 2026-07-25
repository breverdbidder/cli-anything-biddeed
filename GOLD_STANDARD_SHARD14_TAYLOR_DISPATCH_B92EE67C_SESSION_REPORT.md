# Gold Standard shard-14 taylor — dispatch b92ee67c, loop run 6354

## Before/after (live `pencil_dod_evaluate_county('taylor')`)

| Letter | Before | After | Change |
|---|---|---|---|
| A | PASS (4) | PASS (4) | unchanged |
| B | FAIL (null, verified=0 closed_sold=0) | FAIL (null, verified=0 closed_sold=0) | unchanged — 4th independent session to reconfirm, broadest evidence yet |
| C | PASS (100.0) | PASS (100.0) | unchanged |
| D | PASS (100.0) | PASS (100.0) | unchanged |
| E | PASS (100.0) | PASS (100.0) | unchanged |
| F | FAIL (null, tier1_sold=0 closed_sold=0) | FAIL (null, tier1_sold=0 closed_sold=0) | unchanged — coupled to B |
| G | PASS (100.0) | PASS (100.0) | unchanged |
| H | PASS (6.8) | PASS (8.4) | unchanged (freshness drift) |
| I | FAIL (88.9, card_complete=8 of 9) | FAIL (88.9, card_complete=8 of 9) | unchanged — residual re-confirmed with corrected methodology |
| J | PASS (100.0) | PASS (100.0) | unchanged |

**7/10 → 7/10.** No letter flipped. This is an honest plateau — a 00:00Z wave session (dispatch `4c2cb537`) had already re-confirmed the same blockers ~8 hours before this dispatch. Per PARALLEL-FLEET RULES no redundant re-attempts were made on already-exhausted avenues; this session instead went broader (new sources not previously checked) and deeper (root-caused a mechanism, not just re-confirmed a symptom). The session's highest-value output is a fleet-wide infrastructure finding, detailed below.

## Method: ULTRALOOP (native Workflow tool)

Ran the native `Workflow` tool directly (`ultraloop_mode='native'`). Phase 1 fanned 3 parallel research agents (Taylor B/F: court-docket/aggregator sweep; Taylor B/F: Wayback Machine sweep; fleet-wide FL GIO CO_NO-offset scope check). Phase 2 ran one independent adversarial refuter per claim with zero visibility into the other agents' tool-call history. One of the three claims was refuted and is logged as a false positive, not counted — see below.

## Top finding this session: FL GIO Statewide Cadastral CO_NO is offset +10 from `fl_counties.co_no`, fleet-wide

While re-investigating parcel `05026-000` (the sole I-letter residual), direct queries against the FL GIO Statewide Cadastral ArcGIS FeatureServer using `fl_counties.co_no=62` (Taylor) returned zero rows even for parcels **known to exist** (e.g. `02959-200`, our own case `25-014 CA`). Testing `CO_NO=72` instead returned an exact match: `PHY_ADDR1='1104 ALLEN ST N'`, `PHY_CITY='Perry'` — identical to our DB's `property_address='1104 N Allen Street, Perry, Florida 32347'`.

This is the same pattern SHARD14 RUN2753 (2026-07-03) found for Liberty County (`fl_counties.co_no=39` vs the real FL-GIO value `49`) — at the time treated as an isolated anomaly. This session's refuter independently reproduced the **same exact +10 offset** on 5 more counties, each verified against a real, DB-known `parcel_id`:

| County | `fl_counties.co_no` | Works at `co_no+10` | Works at unmodified `co_no` |
|---|---|---|---|
| Taylor | 62 | YES (72) — exact address match | NO (0 rows) |
| Liberty | 39 | YES (49) — prior-session finding, cited | NO |
| Bay | 3 | YES (13) — exact address match | NO (0 rows) |
| Hendry | 26 | YES (36) — exact address match | NO (0 rows) |
| Santa Rosa | 57 | YES (67) — exact address match | NO (0 rows) |
| Brevard | 5 | YES (15) — exact address matches | NO — hard `HTTP 400` |
| Gadsden | 20 | YES (30) — exact address match | NO (0 rows) |

7/7 counties tested this offset, 7/7 confirmed. This is a **strongly supported hypothesis for all 67 counties**, not (yet) a proven fact — only ~10% were directly tested with a real, format-matching `parcel_id`. Marion was attempted but its `multi_county_auctions.parcel_id` format (short internal numeric IDs) doesn't match FL GIO's raw `PARCEL_ID` field at all, an inconclusive/format-mismatch result, not a counterexample.

**Why this matters beyond taylor:** `scripts/ingest_county.py` — described in this repo's `CLAUDE.md` as the "PROVEN" reference pipeline for county parcel ingestion — queries this exact FL GIO layer with `WHERE CO_NO = {co_no}` using `fl_counties.co_no` **unmodified** (line 121/151, `co_no = county["co_no"]` at line 201). Live `fl_counties` data corroborates the likely impact: **65 of 67 counties currently show `total_parcels = 0`**; the only two with real counts (Brevard 351,424; Duval 160,000) both had dedicated, county-specific ingestion work documented elsewhere in this repo's history, not a generic `--county <n>` run. This correlation is consistent with the offset bug causing every generic run of this script to silently return zero parcels — `INFERRED`, not `VERIFIED`, since `total_parcels=0` could in principle have other causes (script simply never invoked for those counties). No code was changed this session: the blast radius (every county's E/I linkage playbook explicitly directs future sessions to "link parcel_id via the county property appraiser ArcGIS FeatureServer") and the fact that many concurrent shard sessions may be mid-flight against this same script make a same-session fix too risky without dedicated, coordinated testing. **Flagging for the AI Architect as the single highest-leverage fix available to the fleet** — a working CO_NO mapping could unblock E/I for a large fraction of the 60+ counties currently failing those letters for lack of a workable parcel source.

## B/F: re-confirmed genuinely blocked, broader evidence than any prior taylor session

Checked and eliminated, all independently re-verified by an adversarial refuter:
- **jud3.flcourts.org** (Third Judicial Circuit): confirmed **dead**, not just unreachable — TLS handshake failure (alert 552) on HTTPS, Cloudflare edge error 1001 (DNS resolution failure at the edge, origin unroutable) on HTTP. No public docket-search tool exists independent of the Clerk's own (blocked) systems for this circuit.
- **myfloridacounty.com**: traced precisely — its Taylor County dropdown embeds a dead link (`taylorclerk.com/PublicInquiry/Search.aspx?Type=Name` → `HTTP 404`, WordPress, zero redirects), not the real `pubrecords.taylorclerk.com` subdomain. Even corrected, that subdomain is the same Cloudflare-Turnstile-gated portal already confirmed blocked via curl **and** a real headless Chromium browser (`Just a moment...` managed challenge, `challenges.cloudflare.com` iframe) this session.
- **auction.com**: Taylor County page returns explicit "No results found" for all target addresses.
- **foreclosure.com**, **qpublic.net/fl/taylor**, **qpublic.schneidercorp.com** (the actual Property Appraiser records system): all `HTTP 403`, same bot-block signature as the clerk portal.
- **Wayback Machine**: CDX-checked for the real auction-date window (2026-07-16 → 2026-07-25) — zero snapshots of the clerk pages or per-case PDFs in that window.
- **taylorclerk.com case PDFs**: confirmed each of the 4 cases whose auction dates have now passed (25-218 CA, 25-196 CA, TDA 26-026, TDA 26-028) had its case PDF return `HTTP 404` within days of the auction date — a real, near-zero capture window, not a hypothetical one.

No sold amount, winning bid, or Certificate of Sale exists anywhere this session's tooling could reach, for any of the 4 now-past-due cases. Nothing fabricated.

## Refuted claim (logged, not counted, per ULTRALOOP protocol)

One research agent claimed the 25-196-CA case PDF had **zero** Wayback Machine snapshots, ever, and was fully unrecoverable. The adversarial refuter found this overstated: a broader (still narrow — one additional, year-agnostic path-prefix) CDX query surfaced a real archive at `https://web.archive.org/web/20260417063427/https://taylorclerk.com/uploads/2026/03/25-196-CA.pdf` (HTTP 200, 582,284 bytes, independently re-fetched). It's a genuine **pre-sale** Notice of Foreclosure Sale (Case 2025-CA-000196, judgment $148,064.49, sale then-scheduled 2026-05-12, since rescheduled to 2026-07-23) — real data, but no winning bid or sold amount, so it does **not** move B or F. Per the ULTRALOOP protocol this is logged in `gold_standard_ultraloop_audit` as `survived=false` — a false-positive ledger entry so no future session trusts the stronger ("unrecoverable, ever") version of the claim, while also not wasting time re-deriving the real archived Notice.

## I residual: re-confirmed with corrected methodology, higher confidence than before

Two prior taylor sessions attributed FL GIO's failure to resolve parcel `05026-000` to a network-egress timeout on filtered queries, leaving genuine ambiguity ("maybe it exists but we can't reach it"). With the CO_NO offset corrected (`CO_NO=72`), exact-`PARCEL_ID` queries return in ~0.2–0.3s — **not** a timeout — and are conclusively empty for `05026-000`. This session additionally enumerated all 29 neighboring parcel IDs in the same block (`05012-000` through `05040-000`, the Belair Sub/Belair Manor/Belair Addition cluster) by exact match: all are real, all correctly cluster on Buffalo Dr / Kennedy St / Mays St / Belair St addresses matching the court judgment's legal description ("Lot 101, Belair Manor Subdivision"), and none is a misfiled or off-by-one variant of `05026-000` or address "101 Buffalo Drive". This upgrades the finding from *inconclusive* to *confirmed genuine gap in the current FL GIO snapshot* — the parcel does not exist in any form this session's tooling could find.

`card_complete` for this row remains blocked on three simultaneous missing fields — `latitude`/`longitude`, `assessed_value`/`market_value`, and zone linkage — none obtainable without the parcel existing in a real, citable source. Per **BLANK > WRONG**, none of these three was fabricated. Metric unchanged: 88.9% (8 of 9).

## Verification protocol evidence

```sql
SELECT public.pencil_dod_evaluate_county('taylor');
-- {"A":{"metric":4,"pass":true},"B":{"metric":null,"pass":false,"detail":"verified=0 closed_sold=0"},
--  "C":{"metric":100.0,"pass":true},"D":{"metric":100.0,"pass":true},"E":{"metric":100.0,"pass":true},
--  "F":{"metric":null,"pass":false,"detail":"tier1_sold=0 closed_sold=0"},"G":{"metric":100.0,"pass":true},
--  "H":{"metric":8.4,"pass":true},"I":{"metric":88.9,"pass":false,"detail":"card_complete=8 of 9"},
--  "J":{"metric":100.0,"pass":true},"county":"taylor","auctions_total":9}
-- Captured 2026-07-25, post-session. Identical to pre-session capture (no regression from
-- concurrent shard work landed via `git pull --rebase`; ~19 other migrations from other shards
-- pulled cleanly before this session's writes).
```

Adversarial audit trail: 3 rows in `gold_standard_ultraloop_audit`, dispatch_id `b92ee67c-93e0-4831-816a-d2cad6d4933b` — letter B (`survived=true`), letter I / CO_NO-offset finding (`survived=true`), letter I / Wayback overclaim (`survived=false`, logged as false-positive per protocol).

## Parallel-fleet note

Per PARALLEL-FLEET RULES, the fleet-wide `gold_standard_loop()`/`gold_standard_certify()` was **not** run this session — `git log` shows ~19 migrations from other concurrently-running shards landed during this session's runtime (walton, escambia, seminole, lee, liberty, okaloosa, alachua, hendry, bradford, hamilton, collier, marion/dixie/baker). Only this county's live per-county evaluation is reported above.

## Next-session priorities for taylor

1. **B/F**: no further avenue identified this session. Every channel this session's tooling (curl, real headless Chromium, WebFetch/WebSearch-based agents, Wayback CDX) could reach is now documented as exhausted. A future session should not re-check jud3.flcourts.org, myfloridacounty.com, auction.com, foreclosure.com, qpublic/schneidercorp, or Wayback Machine for these specific cases without new evidence that one of them has changed. The only remaining plausible lever is a service that can actually solve a Cloudflare Turnstile managed challenge (not just render JS) — a genuine capability gap, not a research gap.
2. **I residual**: parcel `05026-000` is now confirmed absent from the FL GIO snapshot with high confidence (not just an unreachable-query artifact). The only remaining path is the original recorded court filing's metes-and-bounds description resolved by a human/GIS professional, or a prior-year FL GIO NAL snapshot in case the parcel existed before being dropped from the roll — neither obtainable by this session's tooling.
3. **Fleet-wide (not taylor-specific, flagged for the AI Architect)**: verify and fix the FL GIO CO_NO+10 offset in `scripts/ingest_county.py` and any other script/pipeline that queries the FL GIO Statewide Cadastral layer using `fl_counties.co_no` directly. Given 65 of 67 counties currently show `total_parcels=0`, this is plausibly the single highest-leverage unblock available across the whole Gold Standard campaign for E/I letters — worth a dedicated, carefully-tested session rather than a same-session patch given the number of concurrent shards potentially depending on current script behavior.

---
dispatch_id: b92ee67c-93e0-4831-816a-d2cad6d4933b
chat_session: architect-20260725T080000
