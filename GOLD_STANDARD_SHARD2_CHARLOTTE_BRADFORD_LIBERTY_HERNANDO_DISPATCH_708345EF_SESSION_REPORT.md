# Gold Standard shard-2 closeout — charlotte / bradford / liberty / hernando

- **dispatch_id:** `708345ef-8ace-4339-b578-a0a9ef3f27a0`
- **gold_standard_campaign.id:** 4420
- **session_end_at:** `2026-08-15T16:15:58Z`
- **exit_reason:** `timeout` (no county hit a genuine fresh 10/10 this session)

## Summary

Four independent workstreams ran this session (one per county) plus this
mandatory closeout. All four fix reports were adversarially verified live
against fresh `pencil_dod_evaluate_county` calls, with every claimed metric
movement and every "no-change/structural-block" claim independently
reproduced — **all four verdicts: SURVIVED**. No ghost-success, no
fabrication, no metric anomalies were found across any of the four reports.

Net result: hernando moved from 7/10 to 8/10 (E/C/D cascade fix, real DB
writes). Charlotte, bradford, and liberty are unchanged from session start —
all three were confirmed via honest, evidence-backed investigation to be at
genuine structural ceilings, with zero DB writes made (correctly, per
guardrail #6 — no fabrication to force a pass).

## Per-county before/after (`pencil_dod_evaluate_county`)

### hernando (7/10 → 8/10)

**Before:**
```json
{"A":{"pass":true,"metric":13},"B":{"pass":true,"metric":100.0},
 "C":{"pass":false,"metric":72.1,"detail":"matched_clean=49"},
 "D":{"pass":false,"metric":72.1,"detail":"matched_any=49"},
 "E":{"pass":false,"metric":72.1,"detail":"parcel_linked=49"},
 "F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":97.2},"H":{"pass":true,"metric":1.0},
 "I":{"pass":false,"metric":69.1,"detail":"card_complete=47 of 68"},
 "J":{"pass":false,"metric":72.1,"detail":"deal_complete=49"},
 "county":"hernando","auctions_total":68}
```

**After (fresh, pulled at closeout):**
```json
{"A":{"pass":true,"detail":"fc=13 td=55","metric":13},"B":{"pass":true,"detail":"verified=1 closed_sold=1","metric":100.0},
 "C":{"pass":true,"detail":"matched_clean=68","metric":100.0},"D":{"pass":true,"detail":"matched_any=68","metric":100.0},
 "E":{"pass":true,"detail":"parcel_linked=68","metric":100.0},"F":{"pass":true,"detail":"tier1_sold=1 closed_sold=1","metric":100.0},
 "G":{"pass":true,"detail":"density=97.2 far= pk1000=","metric":97.2},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":0.1},
 "I":{"pass":false,"detail":"card_complete=47 of 68","metric":69.1},
 "J":{"pass":false,"detail":"deal_complete=49 (triangle + two-arm CMA + ml_score + max_bid)","metric":72.1},
 "county":"hernando","V2_LITMUS":null,"auctions_total":68}
```

**What shipped:** Re-harvested live `hernando.realtaxdeed.com` calendar (AJAX,
independent source), matched 19 null-parcel tax_deed rows by case_number,
promoted `parity_status='matched_clean'`. Joined harvested `PARCEL_KEY` values
against Hernando PA's public ArcGIS FeatureServer to resolve `parcel_id`,
`latitude`/`longitude`, `market_value`/`assessed_value` for all 19 rows.
19 live row UPDATEs. File: `scripts/hernando_e_taxdeed_ajax_arcgis_fix.py`
(commit `2f7938f9`).

**Adversarial verify:** SURVIVED (C, D, E). Zero rows remain with NULL
`parcel_id`; spot-checked rows carry real, in-county geo/appraiser data;
`zoning_assignments` confirmed 0 rows for hernando corroborating the residual.

**Residual gap (I, J — honest, not force-closed):** I blocked by a
county-wide, pre-existing gap: `zoning_assignments` has **zero rows** for
`county='hernando'` — 21 rows (the 19 newly-linked plus 2 pre-existing) can't
resolve `zoning_code`. This requires a full ZoneWise ingestion pass for
hernando, out of scope for a parcel-linkage fix. J is an independent deal-
thesis pipeline (Distress Triangle + two-arm CMA + ml_score + max_bid),
unaffected by E and never expected to move from this fix.

### charlotte (9/10, unchanged)

**Before / After (identical — no write made):**
```json
{"A":{"pass":true,"metric":31},"B":{"pass":true,"metric":100.0},
 "C":{"pass":false,"detail":"matched_clean=162","metric":90.0},
 "D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},
 "G":{"pass":true,"metric":97.6},"H":{"pass":true,"metric":1.2},"I":{"pass":true,"metric":96.1},
 "J":{"pass":true,"metric":100.0},"county":"charlotte","auctions_total":180}
```

**What shipped:** Nothing (investigation only, zero DB writes). Confirmed all
180 rows are 2 distinct `parity_status` values only: `matched_clean` (162)
and `CLERK_SSOT_CANCELLED` (18). All 18 cancelled rows carry
`tier1_authoritative=true` with real clerk-verified timestamps
(REDEEMED/CANCELED/REDEEMED_AFTER_SALE etc.) — genuine outcomes, not a
matching bug. Attempted a fresh live recheck on the one stale row
(`25000998CA`); blocked by RealForeclose 403 and Firecrawl 402 (no
Playwright available this session).

**Adversarial verify:** SURVIVED as an honest no-op report — byte-identical
before/after RPC output, clean git state, no fabricated change.

**Residual gap (C):** Structural ceiling at 90.0% (162/180). The 18 non-clean
rows are all genuine clerk-verified cancellations/redemptions — by criterion
C's own definition ("clean match proves our row is correct... no clean sale
to match against"), these cannot count as `matched_clean`. This is the 3rd
independent same-conclusion session (2026-08-11, 08-12, 08-15) — a structural
ceiling, not a fixable bug, absent new auction inventory or a shared-
evaluator-semantics policy change.

### liberty (7/10, unchanged)

**Before / After (identical — no write made):**
```json
{"A":{"pass":false,"detail":"fc=1 td=0","metric":0},
 "B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},
 "C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},
 "F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},
 "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":5.2},"I":{"pass":true,"metric":100.0},
 "J":{"pass":true,"metric":100.0},"county":"liberty","auctions_total":1}
```

**What shipped:** Nothing (investigation only, zero DB writes). Confirmed the
`shard-liberty-clerk-scraper.yml` cron + scraper wiring is correct (10+
consecutive successful daily runs). Live-fetched `libertyclerk.com` tax-deed
and foreclosure-sales pages: both literally say "no properties/sales
available at this time" (HTTP 200, verbatim quoted). Re-ran the scraper live:
0 rows parsed. Checked all known alternate tax-deed platforms
(realtaxdeed/realforeclose/bid4assets/taxsmartweb/etc.) — none provisioned
for Liberty.

**Adversarial verify:** SURVIVED. One minor non-material discrepancy noted
(bid4assets returns 403 not 404 as claimed) — does not change the diagnosis.

**Residual gap (A, B, F):** Liberty (FL's least-populous county, ~8K
residents) genuinely has zero scheduled sales on its sole authoritative
source right now. A structural/temporal gap, not a pipeline defect — will
self-resolve automatically the moment the Clerk posts a new sale. B/F are
downstream-blocked by the same condition (no closed auction to attach an
outcome to). Independently reached twice today across two separate sessions.

### bradford (8/10, unchanged)

**Before / After (identical — H's freshness clock moved, cron-driven only):**
```json
{"A":{"pass":true,"detail":"fc=4 td=1","metric":1},
 "B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},
 "C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},
 "F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},
 "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.1},"I":{"pass":true,"metric":100.0},
 "J":{"pass":true,"metric":100.0},"county":"bradford","auctions_total":5}
```

**What shipped:** Nothing (investigation only, zero DB writes). 10th
dedicated B/F session on this county. Confirmed no case has crossed a new
past-due threshold since the same-day 08:26 UTC session (`84b6c4bb`) already
ran this morning: the two 08-13 cases are still exactly 2-days-past, the new
row (`24000431CAAXMX`) is 5 days in the future. Spot-checked
`bctelegraph.com` (404, no new weekly edition) and `bradfordclerk.com`
(unchanged Cloudflare 403). File:
`scripts/bradford_bf_recheck_gsd4_41bd7ce3_10th.py` (commit `67152891`).

**Adversarial verify:** SURVIVED. Live JSON byte-identical to claimed AFTER
(only H's freshness metric differs, as disclosed). Commit contains exactly
one new file, no migration, consistent with the "zero DB writes" claim.

**Residual gap (B, F):** Genuinely blocked on real-world sale timing. Bradford
sells in-person at the courthouse steps with no online auction platform; the
only reachable secondary source (weekly newspaper) publishes pre-sale notices
only. Recommend no re-dispatch until the 08-13 cases reach the ≥7-10-day
publication-lag window (~2026-08-20/23) or a Cloudflare-Turnstile-capable
browser tool becomes available.

## Adversarial verify verdicts (all SURVIVED)

| County | Letters in scope | Verdict |
|---|---|---|
| hernando | C, D, E (fixed); I, J (confirmed unchanged) | SURVIVED |
| charlotte | C (confirmed unchanged) | SURVIVED |
| liberty | A, B, F (confirmed unchanged) | SURVIVED |
| bradford | B, F (confirmed unchanged) | SURVIVED |

## Closeout DB writes (this session)

1. `gold_standard_campaign` id=4420: PATCHed `criteria_passed` (nested
   per-county A-J booleans, matching the multi-county shape used by prior
   rows e.g. id 4422/4389/4388/4387), `criteria_total=10`,
   `exit_reason='timeout'`, `session_end_at='2026-08-15T16:15:58Z'`.
2. `gold_standard_ultraloop_audit`: 11 rows inserted (ids 15857-15867),
   `dispatch_id='708345ef-8ace-4339-b578-a0a9ef3f27a0'`,
   `ultraloop_mode='fallback'` — one row per (county, letter) actually worked
   this session (hernando C/D/E/I/J; charlotte C; liberty A/B/F; bradford
   B/F), all `survived=true`.

## Final A-J status (fresh, at closeout)

| County | A | B | C | D | E | F | G | H | I | J | Score |
|---|---|---|---|---|---|---|---|---|---|---|---|
| charlotte | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 9/10 |
| bradford | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | 8/10 |
| liberty | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | 7/10 |
| hernando | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | 8/10 |

All residual gaps are honestly documented structural/data-ceiling blocks
(missing zoning ingestion for hernando I; genuine clerk-verified
cancellations for charlotte C; zero live source listings for liberty A/B/F;
real-world sale-timing lag for bradford B/F) — none are fabricated or
force-closed.
