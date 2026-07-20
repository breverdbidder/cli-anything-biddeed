# GOLD STANDARD shard-14 escambia — session report

dispatch_id: `a7bdb48f-8748-4a1c-8539-d996dcda9e73`
chat_session: `architect-20260720T160000`
county: escambia (sole shard target)
mode: ultracode (Workflow-orchestrated research + adversarial verify for G)

## Before/after (pencil_dod_evaluate_county, VERIFIED live)

| Letter | Before | After | Status |
|---|---|---|---|
| A | PASS (43) | PASS (43) | unchanged |
| B | PASS (100.0) | PASS (100.0) | unchanged |
| **C** | **FAIL (76.2, matched_clean=259)** | **FAIL (79.4, matched_clean=270)** | **improved, still fails 95% threshold** |
| **D** | **FAIL (76.2, matched_any=259)** | **FAIL (79.4, matched_any=270)** | **improved, still fails 95% threshold** |
| E | PASS (99.7) | PASS (99.7) | unchanged |
| F | PASS (100.0) | PASS (100.0) | unchanged |
| G | FAIL (9.5) | FAIL (9.5) | unchanged — see below |
| H | PASS | PASS | unchanged |
| I | PASS (95.9) | PASS (95.9) | unchanged |
| J | PASS (97.4) | PASS (97.4) | unchanged |

Scoreboard: 7/10 → 7/10 (C/D real gains, no letter regressed).

## C/D — real fix, shipped

Gap composition at session start: 81 rows with `parity_status IS NULL` (73 tax_deed
across 5 far-future dates: 2026-08-05/09-02/10-07/11-04/12-02; 8 foreclosure across
2 near-term dates: 2026-07-28/07-29, all new since shard13's session which only had
1 foreclosure gap row).

Shard13 (2026-07-11) had probed the same 5 tax_deed dates and found zero live
overlap — correctly left undocumented as a genuine gap at the time (dates too far
out to be posted). This session re-probed live via the same AJAX harvest pattern
(`shard8_charlotte_...cd_fix.py::harvest_date_paginated`, exact `norm_case_number`
match only, no fuzzy/parcel arm):

- `escambia.realforeclose.com` 07/28 + 07/29/2026: **8/8** gap case numbers matched
  live (2025 CA 001053, 001226, 001927, 002045, 001091, 001381, 001796,
  2026 CA 000001).
- `escambia.realtaxdeed.com` 5 dates: now 60-61 items live per date (populated
  since shard13), but only **3/73** gap case numbers exact-matched (2024 TD
  001944, 003128, 005029).

11 rows promoted `matched_clean` / `parity_source=tier1_realauction_escambia_shard14_run5361`
via live REST PATCH. **Residual: 70 tax_deed rows** — live calendar has 60+ items
per date but zero exact case_number overlap. Not a matcher bug (verified: the live
listings ARE genuine escambia TD cert numbers with matching parcel_id/address
format); our calendar-sweep-sourced case numbers for those slots simply don't
correspond to what RealAuction is currently listing for the same date, most
likely because upstream TD certificates get pulled/substituted/redeemed before
the sale posts. Left `parity_status IS NULL`, honestly documented, not forced.

Shipped: `scripts/shard14_run5361_escambia_cd_fix.py`, commit `a78c2607`, pushed
to main directly (no side branch).

## G — researched, real finding, correctly did NOT ship a number

`pk1000` (parking-per-1000sf coverage) = 9.5% (2 of 21 applicable parcels have a
value), driven by 4 zoning districts with `parking_per_1000sf IS NULL`: HDMU,
HC/LI, Com (Escambia County Unincorporated) and R-NC (Pensacola).

Dispatched an ultracode Workflow: 4 independent research agents (one per
district) + 2 adversarial refuters per citation (10 agents total, 708K tokens,
~15 min). **Zero of 4 citations survived adversarial verification** — the
result is a genuine negative finding, not a stalled task:

- **New capability discovery**: the actual Escambia County Design Standards
  Manual (DSM) — which the 2026-07-11 session could not locate at any
  accessible URL — IS now fetchable at
  `https://myescambia.com/docs/default-source/upload/ldc-3-4-21-final.pdf`
  (500-page official LDC PDF, DSM is Appendix). It contains a real, concrete
  parking-demand table at **DSM Chapter 1, Article 3, Sec. 3-1.2** (also
  independently reachable via Municode's API node
  `PTIIILADECO_DESTMA_CH1EN_ART3PA_3-1PALO`), with genuine non-null ratios
  (e.g. retail = 3/1,000sf, office = 3.5/1,000sf, manufacturing/light
  industrial = 1/1,000sf, warehousing = 0.5/1,000sf, multi-family = 1.5/unit).
- **Why nothing was written**: that table is indexed **by land use**, not by
  zoning district. HDMU/HC-LI/Com each permit multiple uses with different
  ratios in the table — there is no single correct `parking_per_1000sf` value
  per district without picking a "representative use," which would be a
  modeling judgment call dressed up as ordinance fact. The research agent for
  `Com` correctly reported `found=false` rather than guess. The `HDMU`/`HC-LI`
  research agents proposed `null`/N/A (reasoning the district-level ordinance
  text has no override), but adversarial verifiers correctly refuted that
  framing: the DSM table DOES supply concrete numbers for the relevant use
  categories, so asserting "not regulated" is false — it's regulated, just not
  at the granularity our schema models (one value per district).
- `R-NC` (Pensacola, separate jurisdiction/ordinance): a candidate value
  (3.33/1,000sf, Pensacola Code Ch. 12-4 Sec. 12-4-3) was found but neither
  refuter could independently reach the primary source (Municode 403, JS-SPA
  shell with no server-rendered content, Firecrawl API returned 402
  insufficient credits) — refuted for lack of independent confirmation, not
  because it's wrong. Worth a retry next session with working Firecrawl
  credits or a different fetch path.

All 6 claims (2 survived for C/D methodology note, 4 rejected for G) logged to
`gold_standard_ultraloop_audit` per the ULTRALOOP CERTIFY GATE — G remains
correctly UNKNOWN/FAIL, not falsely marked passing.

### Next-session leads for G
1. Retry R-NC with a working Firecrawl key or a non-SPA Pensacola source
   (e.g. a direct city PDF of Ch. 12-4) — the value may be real, just
   currently unconfirmable.
2. The real fix for HDMU/HC-LI/Com is a schema question, not a research
   question: either (a) extend `zone_standards` to support use-indexed
   parking tables (bigger lift, correctly out of scope for a single-county
   surgical session), or (b) have a human/architect decide and document an
   explicit "predominant permitted use per district" mapping so a single
   representative ratio can be cited defensibly (e.g. Com → retail 3/1,000sf,
   HC/LI → light-industrial 1/1,000sf) — this is a judgment call that should
   be made deliberately, not slipped in as if it were extracted fact.

## Verification protocol executed
- `pencil_dod_evaluate_county('escambia')` run before and after the C/D fix —
  pasted above, real DB query, no rounding/estimation.
- No `gold_standard_loop()` / `gold_standard_certify()` run this session
  (per PARALLEL-FLEET RULES, other shards were mid-flight) — per-county
  evaluation only, as instructed.
- Committed and pushed directly to `main` (no side branch, no PR) — commit
  `a78c2607`.
