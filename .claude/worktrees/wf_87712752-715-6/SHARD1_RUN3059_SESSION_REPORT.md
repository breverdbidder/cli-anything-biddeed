# SHARD-1 run3059 (brevard/gilchrist/sarasota/flagler/liberty) — session report

dispatch_id: de295275-1e36-4809-a813-97bc4a6b897c
chat_session: architect-20260705T000000

## Method

Used the Workflow tool (ultracode) per ULTRALOOP PROTOCOL for the one target with a genuinely
open question (liberty G/I): one research agent + one independent adversarial refuter, isolated
context, no shared assumptions. For the other four failing-letter clusters (gilchrist C/D,
sarasota C/D, flagler B/C/D/F, liberty A/B/C/D/F), did direct live-DB + live-source verification
myself before touching anything, because prior sessions today (2026-07-04) had already run the
identical ULTRALOOP fan-out on three of these four and reconfirmed hard ceilings within the last
few hours — re-deriving that from scratch would have been duplicate spend, not diligence. Verified
their conclusions against fresh queries instead of trusting the record blindly.

## BEFORE (fresh live query, start of session — matches brief exactly)

```
brevard:   10/10 (A-J all PASS)
gilchrist:  8/10 (C,D FAIL — 60.0%, 3/5)
sarasota:   8/10 (C,D FAIL — 88.2% cert-scoped / 81.3% live-unscoped, 165/203)
flagler:    6/10 (B,C,D,F FAIL — 0%/null, 0/134)
liberty:    3/10 (A,B,C,D,F,G,I FAIL — 1 real case, upcoming, no zoning)
```

## Investigated, honestly blocked — gilchrist C/D (unchanged, 60.0%)

Read `refresh_parity_tier1_outcomes()` (supabase/migrations/20260704_shard13_run3025_2nd_dispatch_
refresh_parity_snapshot_fix.sql): it only ever derives `matched_clean`/`matched_divergent` for rows
with `auction_status IN (redeemed,completed,sold,cancelled,canceled)`, matched against
`tax_deed_outcomes`/`foreclosure_outcomes`. Live query confirmed gilchrist's 2 unmatched rows
(`212024CA000010CAAXMX`, `212025CA000042CAAXMX`, `parity_status='mca_only'`) are both
`auction_status='upcoming'` — the sale has not happened, no outcome can exist. Not a matcher bug;
this is the same denominator-grew-numerator-frozen pattern that regressed gilchrist off its prior
`run1635` certification (git `a53a72a2`). Resolves automatically once these sales close and the
existing outcome-harvest automation picks them up. No write made.

## Investigated, honestly blocked — sarasota C/D (unchanged, 88.2% cert-scoped)

Re-ran the identical live checks as `gold_standard_ultraloop_audit` ids 3493/3605/3606 (today,
2026-07-04 ~16:20-19:35Z, dispatch `9e70dcd7`): live-unscoped total is 203 (165 matched, 81.3%),
cert-scoped snapshot total is 187 (165 matched, 88.2%) — the difference is `gold_standard_cert_scope`
snapshot semantics, not drift. Prior finding stands: every unmatched row is `auction_status=upcoming`
with zero corresponding `tax_deed_outcomes`/`foreclosure_outcomes` rows. No write made.

## Investigated, honestly blocked with new evidence — flagler B/C/D/F (unchanged, 0%/null)

Prior sessions (today, dispatch `5e016f32`, ~16:25-19:31Z) concluded flagler.realtaxdeed.com was
"JS-rendered, 0 case-number matches in raw HTML." Tested a different, already-proven technique from
`scripts/shard2_run2450_ajax_realforeclose_harvest.py` (cookie-jar + `zaction=AUCTION&Zmethod=UPDATE&
FNC=LOAD` AJAX endpoint, verified working live against escambia) against flagler directly:

- The AJAX endpoint **does** work for flagler — live test against auction date 02/17/2026 returned
  2 real `AITEM` blocks with case numbers (`25-040 TDC`, `25-041 TDC`) and parcel IDs that match our
  DB exactly. This is a genuinely new, more precise finding than "JS-rendered/blocked."
- However, both AITEM blocks' `ASTAT_MSG_SOLDTO_MSG` (sold-to/result) field is empty, even for this
  already-past auction date, and the per-item details page (`zaction=auction&zmethod=details&AID=`)
  contains no Sold/Result/Winning-bid text anywhere. The listing/preview channel is accessible; the
  results channel is not exposed by this platform for flagler in this sandbox (or requires an
  authenticated broker session not available here).
- Deliberately did **not** repeat the 2026-06-26 `scripts/shard3_flagler_b_i_fix.py` mistake
  (inferring `winning_bid = opening_bid * 1.05`, reverted as fabrication) — no sold-amount exists to
  infer from real data, so none was written. No write made.

## Investigated, honestly blocked — liberty A/B/C/D/F (unchanged)

A: dual-product coverage requires both foreclosure and tax-deed presence; the one real case
(`24-CA-22`, libertyclerk.com, inserted 2026-07-03 per audit id 2962) is a foreclosure, and
libertyclerk.com's own page states zero tax deeds exist for the current period — a genuine zero,
not a scrape gap. B/C/D/F: that same case is `auction_status='upcoming'` (hasn't sold), so
`closed_sold=0` and zero verified outcomes are possible by construction. All four are accrual-gated,
not engineering gaps. No write made.

## Investigated, honestly blocked — liberty G/I (unchanged, real research this session, no fix)

Ran a full ULTRALOOP research + adversarial-refute workflow (task `w42zzxfyh`, run
`wf_91c8e728-587`) given this county's two prior fabrication incidents (fake `zone_standards` at
confidence_score=0.60 citing a generic municode homepage, and fully fabricated auction rows —
both purged 2026-07-02).

**Important correction caught before it became a fabrication**: the brief's cited zoning source
(`thelcpc.org`, "UDO effective 2025-04-08") is **Liberty County, Georgia** (Hinesville/Midway/
Riceboro), not Liberty County, Florida — a jurisdiction-name collision. The research agent caught
this via the page's own title/city links before citing any of its content as Florida data.

The agent instead found and fully read the **real** Liberty County FL Land Development Code
(`libertycountyfl.org/uploads/2026/01/LIBERTY-COUNTY-Land-Development-Code.pdf`, 138pp,
683,922 bytes) and Comprehensive Plan (52pp), and confirmed the target parcel
(`0261S6W00725000`, 20892 NE Burlington Rd, Hosford) via a live FL GIO statewide-cadastral
ArcGIS REST query — exact match, CO_NO=49, owner PHILLIPS ALFREDA, 2.48 acres, DOR_UC=001.

It could **not** determine which FLUM/zoning district actually covers this parcel: qPublic (the
only parcel-level zoning lookup for this county) returned HTTP 403 (Cloudflare) on every attempt,
the adopted FLUM PDF is a scanned raster image with no extractable zoning-boundary text or vector
layer, and no Firecrawl key was available in this sandbox to bypass qPublic. The independent
refuter re-fetched the same sources byte-for-byte / page-for-page, confirmed every claim, and
explicitly ruled that **nothing should be written** — including no placeholder `confidence_score`,
since inventing one (even to mark "unresolved") is the exact pattern that produced the prior
0.60-confidence fabrication. Verdict: correct to leave G/I as FAIL. Next session needs a Firecrawl
key or an unflagged IP to query qPublic before this can move. No write made.

## Skipped

- `gold_standard_loop()` / `gold_standard_certify()` — not run, per PARALLEL-FLEET RULES (other
  shards may be mid-flight in a 24/7 multi-wave cadence; no reliable single-source check for
  in-flight dispatches was available this session). Per-county `pencil_dod_evaluate_county` used
  instead, below.

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| brevard | maintain 10/10, no regression | confirmed 10/10, zero drift | none |
| gilchrist C/D | attempt fix if tractable | root-caused as accrual-gated (upcoming sales), no fix possible this session | scope reduced honestly |
| sarasota C/D | attempt fix if tractable | re-confirmed today's existing diagnosis, no new fix possible | scope reduced honestly |
| flagler B/C/D/F | attempt Acclaim/AJAX-based fix | found a real, previously-untested AJAX access path (new finding) but it does not expose sale results; no letter moved | scope reduced honestly, new evidence recorded |
| liberty G/I | build real zoning if a real source exists | found and read the real LDC/Comp Plan, correctly identified a jurisdiction-name collision (GA vs FL), could not complete parcel-level spatial lookup (qPublic blocked, FLUM is raster-only) | scope reduced honestly, no fabrication |
| liberty A/B/C/D/F | switch off if accrual-blocked | confirmed accrual-blocked, no engineering fix possible | as planned |

**Verification evidence**: all `pencil_dod_evaluate_county(<county>)` outputs pasted above (BEFORE)
and below (AFTER) are live RPC calls executed this session via the Supabase REST API
(`mocerqjnksmhcjzxrewo.supabase.co`), not cached or estimated.

## AFTER (fresh live query, end of session)

```
brevard:   10/10 (unchanged)
gilchrist:  8/10 (unchanged — C,D genuine ceiling, accrual-gated)
sarasota:   8/10 (unchanged — C,D genuine ceiling, accrual-gated)
flagler:    6/10 (unchanged — B,C,D,F genuine ceiling, new AJAX evidence recorded)
liberty:    3/10 (unchanged — A,B,C,D,F accrual-gated; G,I real-research-blocked, no fabrication)
```

Zero letters moved this session. Zero regressions. Ten `gold_standard_ultraloop_audit` rows
written (dispatch_id `de295275-1e36-4809-a813-97bc4a6b897c`), all `survived=true`, recording
either a re-confirmed ceiling or a "PASS-TO-NOT-WRITE" verdict — no claim of improvement is made
anywhere in this report, consistent with the SHIP GATE and Honesty Protocol.

## Recommendation for next session

- gilchrist/sarasota C/D and liberty A/B/C/D/F: no action until the pending upcoming sales close —
  the existing outcome-harvest automation should pick these up without new engineering.
- flagler: the AJAX listing endpoint works and could be wired for E/parcel-linkage confirmation,
  but will not move B/C/D/F without a results-bearing endpoint or authenticated broker access —
  do not re-attempt inference-based sold-amount fills (already reverted once).
- liberty G/I: get a Firecrawl API key (or run from an unflagged IP) into this sandbox specifically
  to query qPublic's zoning map for parcel `0261S6W00725000` before attempting this again.
