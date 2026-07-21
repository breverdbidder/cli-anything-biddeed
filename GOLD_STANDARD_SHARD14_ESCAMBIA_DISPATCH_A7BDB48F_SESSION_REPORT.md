# GOLD STANDARD shard-14 escambia — session report

dispatch_id: `a7bdb48f-8748-4a1c-8539-d996dcda9e73`
chat_session: `architect-20260720T160000`
county: escambia (sole shard target)
mode: ultracode (Workflow-orchestrated research + adversarial verify for G)

**NOTE: this dispatch fired twice** (commit `a78c2607` on 2026-07-20 21:22Z, then
a second firing ~3.5h later, same dispatch_id/chat_session). The second firing
verified the first firing's shipped state live (matched it exactly), then
continued from its documented "next-session leads" rather than repeating
completed work. Both firings' before/after are recorded below as one
continuous session.

## Before/after (pencil_dod_evaluate_county, VERIFIED live)

| Letter | Firing 1 start | Firing 1 end | Firing 2 end | Status |
|---|---|---|---|---|
| A | PASS (43) | PASS (43) | PASS (43) | unchanged |
| B | PASS (100.0) | PASS (100.0) | PASS (100.0) | unchanged |
| **C** | **FAIL (76.2, matched_clean=259)** | **FAIL (79.4, matched_clean=270)** | **FAIL (80.6, matched_clean=274)** | **improved twice, still fails 95% threshold** |
| **D** | **FAIL (76.2, matched_any=259)** | **FAIL (79.4, matched_any=270)** | **FAIL (80.6, matched_any=274)** | **improved twice, still fails 95% threshold** |
| E | PASS (99.7) | PASS (99.7) | PASS (99.7) | unchanged |
| F | PASS (100.0) | PASS (100.0) | PASS (100.0) | unchanged |
| G | FAIL (9.5) | FAIL (9.5) | FAIL (9.5) | unchanged — see below |
| H | PASS | PASS | PASS | unchanged |
| I | PASS (95.9) | PASS (95.9) | PASS (95.9) | unchanged |
| J | PASS (97.4) | PASS (97.4) | PASS (97.4) | unchanged |

Scoreboard: 7/10 → 7/10 → 7/10 (C/D real gains both firings, no letter regressed).

## Firing 2 — C/D residual re-probe (real gain)

Re-ran the idempotent `scripts/shard14_run5361_escambia_cd_fix.py` against the
live RealAuction calendar ~3.5h after firing 1. The `08/05/2026` tax_deed slot
had grown from 60 to 61 live items since the last probe; 4 new exact
case_number matches appeared that were not present before (2024 TD
002003/002039/001979/004747). Promoted `matched_clean` live via REST PATCH.
C/D moved 79.4% → 80.6% (270 → 274). No new migration file needed (data-only
change via the existing idempotent script, same pattern as firing 1). Logged
to `gold_standard_ultraloop_audit` ids 8170/8171 (survived=true).

Residual: 66 tax_deed rows remain genuinely unmatched — same root cause as
firing 1 (RealAuction's live TD certificate list for these far-future dates
diverges from our calendar-sweep source; likely upstream substitution/
redemption before the sale posts, not a matcher bug).

## Firing 2 — G R-NC retry (real finding, correctly did not ship a number)

Firing 1 left an explicit next-session lead: retry the R-NC (Pensacola)
citation with a working fetch path (Firecrawl credits or non-SPA source).
Dispatched a 1-research-agent ultracode Workflow using WebFetch directly
(no Firecrawl dependency). Result: **still no primary source reachable**
(Municode 403, cityofpensacola.com 403 on every path tried, Wayback Machine
blocked outright by the WebFetch tool implementation itself) — refuted for
lack of independent confirmation, consistent with firing 1.

**New structural finding** (upgrades the diagnosis, doesn't resolve it): a
WebSearch surfaced Zoneomics (secondary source, not treated as confirmed) show
Pensacola LDC Sec. 12-3-7(5)b (the R-NC district's own regulations) contains
**no numeric parking ratio at all** — it cross-references Chapter 12-4, which
is organized **by land use** (bank 1/300sf, general retail 1/300sf =
3.33/1,000sf, restaurant 1/100sf, ~80 categories) in Sec. 12-4-1(2), not by
zoning district. Sec. 12-4-3 — the section firing 1's candidate actually cited
— is titled "Parking Lots" and covers physical design standards (stall
dimensions, surfacing), not ratio numbers. The original 3.33/1,000sf figure
appears to be a real code value (general retail use) misattributed to the
wrong section and reframed as a district-wide ratio that does not exist in
Pensacola's code.

This means **R-NC has the identical structural problem as HDMU/HC-LI/Com**
(unincorporated county, DSM Ch.1 Art.3 Sec.3-1.2): Escambia's
`zone_standards.parking_per_1000sf` schema models one value per **district**,
but both governing ordinances (Pensacola LDC and county DSM) regulate parking
by **land use**, not district. There is no single defensible per-district
value for any of the 4 remaining pk1000-blocking districts (R-NC, HDMU,
HC/LI, Com) without a "representative use" judgment call — a schema/
architecture decision, not something further research can resolve. Logged to
`gold_standard_ultraloop_audit` id 8177 (survived=false, refuted).

**This closes out the "retry R-NC" lead as exhausted** — the residual
next-session work for G is now purely the architectural question from firing
1's report (extend `zone_standards` for use-indexed parking, or have a human
deliberately document a representative-use mapping per district), not further
citation-hunting.

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

### Next-session leads for G (superseded by firing 2 — see below)
1. ~~Retry R-NC with a working Firecrawl key or a non-SPA Pensacola source~~
   — **done in firing 2, exhausted.** WebFetch also hit 403 on every direct
   path and Wayback is blocked by the tool itself; the underlying finding is
   now that R-NC has no district-level ratio to find at all (see firing 2
   section above).
2. The real fix for R-NC **and** HDMU/HC-LI/Com is a schema question, not a
   research question: either (a) extend `zone_standards` to support
   use-indexed parking tables (bigger lift, correctly out of scope for a
   single-county surgical session), or (b) have a human/architect decide and
   document an explicit "predominant permitted use per district" mapping so
   a single representative ratio can be cited defensibly (e.g. Com → retail
   3/1,000sf, HC/LI → light-industrial 1/1,000sf, R-NC → general retail
   3.33/1,000sf per the now-located Sec. 12-4-1(2) table) — this is a
   judgment call that should be made deliberately by the architect, not
   slipped in as if it were extracted fact. **All 4 remaining districts now
   have this same one blocker; no further per-district research is left to
   do without that decision.**

## Verification protocol executed
- `pencil_dod_evaluate_county('escambia')` run before and after each fix in
  both firings — pasted above, real DB query, no rounding/estimation.
- No `gold_standard_loop()` / `gold_standard_certify()` run this session
  (per PARALLEL-FLEET RULES, other shards were mid-flight) — per-county
  evaluation only, as instructed.
- Firing 1: committed and pushed directly to `main` — commit `a78c2607`.
- Firing 2: C/D promotion applied live via REST PATCH using the existing
  idempotent script (no code change, no new migration needed); this report
  update committed and pushed directly to `main` — no side branch, no PR.
- All firing-2 claims logged to `gold_standard_ultraloop_audit`
  (ids 8170, 8171 survived=true for C/D; id 8177 survived=false for the
  refuted G R-NC retry) per the ULTRALOOP CERTIFY GATE.
