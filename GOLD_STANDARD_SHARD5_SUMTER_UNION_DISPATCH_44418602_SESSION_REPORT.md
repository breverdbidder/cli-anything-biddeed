# Gold Standard SHARD-5 Session Report — sumter, union

- **dispatch_id**: 44418602-2cad-48d3-b711-61b937398822
- **chat_session**: architect-20260814T160000
- **loop_run at launch**: 11435
- **counties**: sumter, union
- **mode**: ULTRALOOP (ultracode Workflow, 3 parallel extend/refute agents; fallback mode logged — native `/effort ultracode` menu not exercised, manual Task/Workflow fan-out used instead)
- **agent**: claude-sonnet-5

## Status Board (before → after, live `pencil_dod_evaluate_county`)

| County | Before | After | Change |
|---|---|---|---|
| sumter | 9/10 (I fails, 83.3%) | 9/10 (I fails, 83.3%) | Unchanged — honest negative, reconfirmed via a 3rd independent source |
| union | 6/10 (B,C,D,F fail) | 6/10 (B,C,D,F fail) | Unchanged — honest negative, one prior ambiguity resolved (see below) |

**Net: zero letters moved. Zero regressions on the 15 previously-passing letters across both counties.**

## What was done

### sumter — letter I, third independent source corroborates dead end
The 4-row gap (`J16C020`, `M06C003`, `G06H033`, `C27-268` — `property_address IS NULL` with parcel_id/geo/value already populated) was fully diagnosed and closed out as a genuine structural block in a prior session (`GOLD_STANDARD_SHARD_SUMTER_I_UNASSIGNED_LOCATION_20260813.md`, 2026-08-13): all 4 parcels show `Site Location: Unassigned Location RE` on the Sumter Property Appraiser's own qPublic record.

This session did not re-litigate that investigation. Instead, a fresh angle was authorized and run: Sumter County's **E-911 addressing point layer** (`services8.arcgis.com/.../Address_Public/FeatureServer/0`) — a genuinely distinct data channel from both the raw parcels layer and the qPublic UI already checked. Queried by exact `parcel_id` match (0 hits, query correctness sanity-checked against a known parcel) and by 150m spatial proximity (returns only neighboring parcels' address points, never the target parcel's own). Also retried the county's ArcGIS REST root (still HTTP 500, county-wide outage unresolved since 8/13) and reverse-geocoded the 4 coordinates via Census/Nominatim (results correctly rejected — every match belonged to a neighboring parcel, the exact misattribution trap the fabrication guardrail exists to prevent).

**Result: a third independent Sumter data channel now agrees with the first two.** No write made. Ceiling remains 83.3% (20/24) under current data availability, unless the evaluator's denominator is changed to exempt genuinely-unaddressable vacant/cemetery parcels — a policy decision explicitly out of a data-fix session's scope.

### union — B/C/D/F reconfirmed blocked; one real corroboration, no metric movement
Case `63-2025-CA-0053`'s DB `auction_date` (2026-08-13) passed the day before this session — exactly the "after 2026-08-13" recheck flagged as the next actionable lever by two prior sessions. This session re-ran the union clerk parser live (Playwright, Cloudflare challenge clears) and confirmed the case is still absent from `unionclerk.com`'s "Upcoming Foreclosure Sales" calendar (consistent with two prior independent checks, not a parser regression — no pagination, no hidden cards, selectors still match).

**New this session**: independently verified, word-for-word, that a real Notice of Sale for this exact case (case number, both party names, Final Judgment date, Rescheduling Order date, sale date/time/location, full property description) exists at `bctelegraph.com/legal-notices-for-5-21-26/` — the Bradford County Telegraph, a legitimate, currently-operating newspaper site with no Cloudflare gate. This resolves the ambiguity a prior session (dispatch `98f47dff`) left open when a crashed fix-agent cited this same notice without independent corroboration and the citing write was correctly reverted for being unverified. It is now VERIFIED real. Per an adversarial refuter pass run specifically against this claim: **survives** — exact match on all legally material facts, no digit-substring coincidence, site legitimacy confirmed (homepage branding, current content through 8/13/26).

This does **not** move C/D: the notice announces a June 18, 2026 sale date, since superseded by at least one further reschedule to August 13 (per our own clerk scrape from 7/3) with no subsequent notice found anywhere on bctelegraph through 8/13/26 confirming what that reschedule led to. The case remains genuinely absent from the live clerk calendar today — `parity_status='PHANTOM_NOT_ON_CLERK'` is left unchanged, matching the exact same "notice ≠ live-calendar-match" reasoning that caused the prior claim's revert. Writing `matched_clean` from a pre-sale newspaper notice would repeat that mistake.

It does not move B/F either: a Notice of Sale is a pre-sale announcement, not a sale result. A dedicated sale-result hunt this session (WebSearch across 9 queries, foreclosure aggregator sites, a fresh Telegraph sweep through the 8-13-26 issue, and a plain-fetch retry of unionclerk.com) found no sale outcome or dollar amount anywhere. Civitek OCRS (`civitekflorida.com/ocrs/county/63/`) was reached and navigated through its Public/disclaimer flow this session, but its actual case-search form is gated by a **Cloudflare Turnstile CAPTCHA** — confirmed structurally blocked, matching a previously documented Bradford County finding on the same Civitek platform. Not bypassed, per guardrail.

**Root cause reconfirmed unchanged**: Union County conducts sales in-person at the courthouse lobby with no online results-publishing portal, and its one queryable records channel (Civitek OCRS) is CAPTCHA-gated. This is a genuinely exhausted, time/channel-gated block, not an effort gap — third session in a row to reach this same conclusion, now with stronger corroborating evidence.

## Verification Protocol — before/after JSON (live-queried 2026-08-14T16:16Z)

**sumter**:
```json
before: {"A":{"pass":true,"metric":10},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":4.2},"I":{"pass":false,"metric":83.3,"detail":"card_complete=20 of 24"},"J":{"pass":true,"metric":100.0},"auctions_total":24}
after:  {"A":{"pass":true,"metric":10},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.4},"I":{"pass":false,"metric":83.3,"detail":"card_complete=20 of 24"},"J":{"pass":true,"metric":100.0},"auctions_total":24}
```
(byte-identical on the target letter — honest no-change, zero writes made)

**union**:
```json
before: {"A":{"pass":true,"metric":1},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":66.7,"detail":"matched_clean=2"},"D":{"pass":false,"metric":66.7,"detail":"matched_any=2"},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":3.4},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"auctions_total":3}
after:  {"A":{"pass":true,"metric":1},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":66.7,"detail":"matched_clean=2"},"D":{"pass":false,"metric":66.7,"detail":"matched_any=2"},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":3.6},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"auctions_total":3}
```
(byte-identical on all 4 target letters — honest no-change, zero writes made)

## ULTRALOOP audit rows

5 rows inserted into `gold_standard_ultraloop_audit` (dispatch `44418602-2cad-48d3-b711-61b937398822`, `ultraloop_mode='fallback'`): sumter/I, union/B, union/C, union/D, union/F — all `survived=true` (the "still blocked, here's the fresh independent evidence" claims survived scrutiny; no metric-moving claim was made or logged as such).

## Session close-out

`gold_standard_campaign` row (id 4385, dispatch `44418602-2cad-48d3-b711-61b937398822`) updated: `criteria_passed` = live per-county A–J snapshot above, `criteria_total=10`, `exit_reason='completed_workqueue'`, `session_end_at` stamped. Neither county reaches 10/10 this session; both remain accurately scored, no certification attempted.

## Next-session priorities (unchanged in substance from prior sessions)

1. **sumter I**: accept as permanent residual (3 independent live sources now agree) unless the evaluator's denominator is changed to exempt genuinely-unaddressable vacant/cemetery parcels, or a manual GIS-addressing-department contact becomes available. Do not re-run the same source hunt again without a genuinely new channel.
2. **union B/F**: recheck after case `63-2024-CA-0047`'s 2026-10-15 sale date passes. If Union ever gets Firecrawl credit restored, retry `unionclerk.com` for a results/surplus page one more time. Civitek OCRS is Turnstile-blocked — do not keep re-attempting without a CAPTCHA-solving capability, which is out of scope.
3. **union C/D**: same block as B/F, tied to the same case. Consider, as a policy question for the AI Architect (not a data-fix decision): whether a verified newspaper Notice of Sale should ever count toward `parity` matching for counties with no online calendar-diff channel, given the current evaluator only recognizes live clerk-calendar matches.

## Cost / time

1 background Workflow (3 agents, ~192K subagent tokens, ~4.5 min wall clock), plus direct investigation this session (Playwright Civitek OCRS navigation, direct curl/bctelegraph fetches, live pencil_dod_evaluate_county calls). Well under the $10 session cap. No code shipped this session — per WIRING MANDATE, shipping against a structurally CAPTCHA/portal-blocked channel would be wiring-mandate theater, not progress.
