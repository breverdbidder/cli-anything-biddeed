# Gold Standard shard-2 — lafayette / st_johns / jefferson / wakulla

**Dispatch:** `b992b7ec-8438-4121-8601-e10a84424016` (chat_session `architect-20260831T080000`, 08:00Z wave, one of 5 concurrent shard dispatches confirmed via `gh run list` — 5 `CC Runner — GHA-only` jobs in_progress since 2026-08-31T08:01:01Z)
**Mode:** ULTRALOOP native (Workflow tool), 7 fix agents + 7 independent adversarial refuters, 14 agents total, ~959K tokens, 244 tool calls, ~17 min wall clock

## Result: no metric movement on any of the 4 counties. Every failing letter was re-verified live this session and is a confirmed genuine data ceiling or canon-block, not a fixable gap.

| county | before | after | delta |
|---|---|---|---|
| lafayette | 9/10 (C fail 75.0%) | 9/10 (C fail 75.0%) | unchanged — canon-block reconfirmed (13th+ time), zero writes to the scored fields |
| st_johns | 9/10 (C fail 95.0% displayed / 94.958% actual) | 9/10 (unchanged) | unchanged — razor-edge canon-block reconfirmed, all 6 gap rows live-reverified post yesterday's parser fix |
| jefferson | 8/10 (B/F fail, null) | 8/10 (unchanged) | unchanged — 13th consecutive confirmation of clerk-side publication-latency ceiling |
| wakulla | 6/10 (C/E/I/J fail) | 6/10 (unchanged) | unchanged — all 4 failing letters share the same 4 redeemed-pre-publication tax-deed cases as the root blocker, reconfirmed live |

This is an honest zero-metric-movement session. Every one of the 4 counties' failing letters had already been worked repeatedly by prior sessions (jefferson B/F: 13 firings; lafayette C: reconfirmed 2026-08-29; wakulla C/E/I/J: worked as recently as 2026-08-29/30; st_johns C: touched by a parser fix 2026-08-30). This session's job was to find a genuinely new lever on each, not rubber-stamp the prior state — every claim below carries a fresh live re-derivation from this session plus an independent adversarial refuter re-derivation, not a copy of a prior report.

## lafayette C — canon-block reconfirmed (light check, per 2026-08-29's explicit "do not re-litigate" guidance)

Case `25000056CAAXMX` is the sole cancelled auction of 4 total; canon excludes cancelled rows from `matched_clean`, permanently capping C at 75.0% with `n=4`. Fresh live fetch of `lafayetteclerk.com` this session found the case byte-identical to the 2026-08-29 finding (status=cancelled, same parcel/parties/sale-date). No write made. Audit id `19839`, `survived=true`.

## st_johns C — razor-edge canon-block reconfirmed, high scrutiny given yesterday's parser bug

C sits at 113/119 = 94.958% (displays as "95.0" but fails the unrounded ≥95% comparison — one more clean row would flip it PASS). Given commit `890189cc` (2026-08-30) had just fixed a real status-handling bug in `scripts/clerk_ssot/parsers/st_johns.py`, this was the highest-leverage target in the shard — a single mis-classified row would cross the threshold. All 6 `CLERK_SSOT_CANCELLED` gap rows (TD26-0034/0031/0038/0024/0059/0078, including both future-dated ones) were independently re-derived against the live `apps.stjohnsclerk.com/TaxSmart` grid this session (fresh session cookie, POST search, `GridSearchData` per status). All 6 parcel_ids matched the DB exactly and all 6 are genuinely REDEEMED/CANCELLED on the live clerk system right now — the 890189cc fix is working correctly and did not introduce a new false-cancellation. No write made. Audit id `19840`, `survived=true`.

## jefferson B/F — 13th firing, genuine ceiling reconfirmed + one real side-fix landed

Full 406-item `jeffersonclerk.com` WP media-library sweep (no filename filter) plus direct re-fetch of both live clerk pages found zero new content since the 12th firing's 2026-08-28T16:10Z checkpoint — newest site-wide upload is still `Charlie-Kirk-Proclamation.pdf` (2026-08-21), unrelated. No sold-outcome data exists anywhere for `26-TD-04`, `26-TD-05`, or `25-CA-145`. Audit ids `19841` (B), `19842` (F), both `survived=false` (an honest negative result, matching the agent's own self-score — no positive claim was made that could "survive").

**Side-fix landed:** the adversarial refuter independently caught that `25-CA-145`'s live `FORECLOSURE-SALES.pdf` (already downloaded by this session's own fix agent) plainly states `Final Judgement amount: $183,049.87`, while the DB row's `judgment_amount` was still `NULL` — a real, low-risk enrichment gap unrelated to the sold-outcome question. Backfilled `judgment_amount=183049.87` on `multi_county_auctions` (case `25-CA-145`, county `jefferson`) — this is a genuinely-sourced, non-outcome field (distinct from `sold_amount`/`winning_bidder`, does not touch B/F scoring) confirmed via the exact same live PDF fetch. `HTTP 200`, row confirmed post-write.

## wakulla C/E/I/J — all 4 failing letters trace to the same 4 rows (or a documented seam)

Live diagnosis this session (independent of the fix agents' own claims) established the exact shape of the gap before dispatching fixers:

- **C** (41/52=78.8%): 11 `CLERK_SSOT_CANCELLED` rows, canon-excluded from `matched_clean` by design (same structural pattern as lafayette/gadsden). Spot-checked the Oct-21 batch (`2026-TXD-124/125/126/127`) live against `wakullaclerk.org` — confirmed "Redeemed" status with no document link, vs. "For Sale" + PDF link for the surrounding case numbers. Genuine canon-block, not a bug.
- **E** (48/52=92.3%) and the 4-row half of **I** (47/52=90.4%): the same 4 cases (`2026-TXD-124/125/126/127`) are bare skeleton rows — `owner_name`, `legal_description`, `cert_number`, `plaintiff` all `NULL` in the DB, and confirmed via 5 independent live sources this session (wakullaclerk.org, wakullaclerk.com/LandmarkWeb, myfloridacounty.com, qpublic, mywakullapa.com/wakullacountypropertyappraiser.org) that no case-to-parcel index exists anywhere for a redeemed-before-publication tax-deed case in Wakulla — these cases never reached the advertised-for-sale stage, so the Clerk's CMS never generated a document with a parcel_id. This matches and independently reproduces a prior session's dedicated probe script (`scripts/wakulla_shard4_0bf31675_e_txd124_127_parcel_probe.py`).
- **I**'s 5th gap row (`25-CA-9`, parcel `00-00-075-262-10242-B02`) has real parcel_id/address/geo but sits in a genuine unmapped seam between Wakulla's zoning ArcGIS polygons — both live FeatureServers (`Zoning_Map/FeatureServer/30` and the legacy `ZoningWakulla/FeatureServer/0`) return zero features at the exact point; an envelope query around the point independently found 7 conflicting neighboring zone codes (RSU2/RR1/RR2/C2/AG/CO/C4), confirming there is no single correct answer to infer, only a guess. Not written.
- **J** (48/52=92.3%, needs 50/52): gap is the same 4 TXD rows as E — no parcel_id/value data exists to build a non-fabricated CMA/ARV, so no `bid_decisions` row can be honestly generated. Separately confirmed this session that the 2026-08-30 cross-county collision case (`25-CA-145`, shared with jefferson, documented in `GOLD_STANDARD_J_EVALUATOR_CROSS_COUNTY_COLLISION_FINDING_20260830.md`) now has a genuine wakulla-`county_slug` `bid_decisions` row of its own (arv=$277,716) — it is no longer a bare collision artifact, though the underlying join-predicate bug in `pencil_dod_evaluate_county` (no `county_slug` filter) remains unfixed fleet-wide per that finding's recommendation (canon-level change, owner sign-off required, out of this shard's scope).

Audit ids `19843` (C), `19844` (E), `19845` (I), `19846` (J), all `survived=true`.

## Adversarial verification summary

7 independent refuter agents ran against all 7 fix-agent claims. 6 of 7 returned `survived=true` (canon-blocks/ceilings reconfirmed with independently-reproduced live evidence, no fabrication, no anomalous ratios, no circular sourcing). The 7th (jefferson B/F) returned `survived=false` by design — the claim itself was a negative/no-change result, not a positive fix, so there was nothing to "survive"; the refuter's own independent re-derivation matched the claim exactly and additionally surfaced the judgment_amount enrichment gap that this session then fixed.

No fabricated `parcel_id`, `zone_code`, `sold_amount`, or `bid_decisions` row was created anywhere this session. No PropertyOnion data was used as a source for any claim.

## SQL VERIFICATION

```sql
-- pencil_dod_evaluate_county, live REST RPC, 2026-08-31 ~08:30Z, run twice (before workflow, after all writes) — identical both times for all 4 counties except the jefferson judgment_amount field (not DoD-scored):
-- lafayette:  A1 B100 C75.0(FAIL) D100 E100 F100 G100 H2.6 I100 J100  -> 9/10
-- st_johns:   A55 B100 C95.0(FAIL,94.958 actual) D100 E100 F100 G100 H0.0 I100 J99.2 -> 9/10
-- jefferson:  A2 B null(FAIL) C100 D100 E100 F null(FAIL) G100 H0.0 I100 J100 -> 8/10
-- wakulla:    A12 B100 C78.8(FAIL) D100 E92.3(FAIL) F100 G95.0 H2.9 I90.4(FAIL) J92.3(FAIL) -> 6/10

-- gold_standard_ultraloop_audit: 8 fresh rows inserted this session under the correct
-- dispatch_id (prior agent writes for lafayette/jefferson had mistakenly copied stale
-- dispatch_ids from historical report context they'd read — corrected here):
-- ids 19839 (lafayette C, survived=true), 19840 (st_johns C, survived=true),
--     19841 (jefferson B, survived=false), 19842 (jefferson F, survived=false),
--     19843 (wakulla C, survived=true), 19844 (wakulla E, survived=true),
--     19845 (wakulla I, survived=true), 19846 (wakulla J, survived=true)

-- multi_county_auctions: one field backfilled, county=jefferson, case_number=25-CA-145:
--   judgment_amount: null -> 183049.87 (source: live jeffersonclerk.com FORECLOSURE-SALES.pdf,
--   "Final Judgement amount: $183,049.87", confirmed via HTTP 200 PATCH + representation readback)
--   Timestamp: 2026-08-31T08:26:49Z. Does not affect any A-J scoring (not sold_amount/winning_bidder).
```

## Fleet coordination / guardrail compliance

- Confirmed via `gh run list --status in_progress` that 5 `CC Runner — GHA-only` jobs were mid-flight (the full 08:00Z wave, this dispatch being one of them) — per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were **not** run this session (fleet-wide functions, unsafe to run while other shards are actively scoring). Only per-county `pencil_dod_evaluate_county` calls were used.
- Touched only this shard's 4 counties' rows (`multi_county_auctions` — 1 field on 1 jefferson row; `gold_standard_ultraloop_audit` — 8 new rows scoped to these 4 counties). No other shard's counties, cron jobs (109/111/115/gold-standard-loop-*), or `pencil_dod_evaluate_county` function body were touched.
- No `parity_status` reclassified anywhere — every canon-block (lafayette C, st_johns C ×6, wakulla C ×11) was independently re-verified as genuinely cancelled/redeemed against its live clerk/GIS source this session, not assumed from a prior report.
- `gold_standard_campaign` close-out row updated per the mandatory session close-out protocol (see below).

## Recommendation to fleet dispatcher

All 4 counties in this shard have now had every currently-failing letter checked with fresh live evidence this session, on top of an already-extensive prior history (jefferson B/F: 13 firings; wakulla C/E/I/J: 3+ dedicated sessions in the last 3 days; lafayette C and st_johns C: both re-verified within the last 24-48h). Every remaining gap is one of:
1. A **canon-level design tension** (C excludes cancelled/redeemed rows by construction — lafayette, st_johns, wakulla all hit this at different severities depending on denominator size), not fixable at the per-county data layer.
2. A **genuine source-side data absence** (jefferson: clerk hasn't published outcomes yet; wakulla E/I/J: 4 cases redeemed before the Clerk's CMS ever generated a public document, so no parcel_id exists to discover) — not fixable without the source publishing, or without a working interactive browser-automation tool (Landmark Web's case-number search requires JS-driven form submission; `browser-use` was not installed and Firecrawl returned "Insufficient credits" this session).

**Do not re-fire routine per-letter re-diagnosis on these 4 counties** until one of: (a) the source data actually changes (jefferson clerk publishes results; a new wakulla auction resolves), (b) a working browser-automation tool becomes available in-session (unlocks Wakulla LandmarkWeb + the lafayette `lafayettepa.com` GIS deep-link noted in the 2026-07-19 report), or (c) a canon-level decision is made on the CLERK_SSOT_CANCELLED-vs-matched_clean tension (would require owner sign-off, affects multiple counties fleet-wide, same class of change as the still-open J cross-county collision join-predicate fix documented 2026-08-30).
