# Gold Standard shard-3: walton, leon, taylor — dispatch c5a8b2c7, loop run 9906

ULTRALOOP mode: `workflow` (Workflow tool, 5 fix agents fanned in parallel over the 5 failing
letter/county targets, each independently adversarially verified by a second agent per the
ULTRALOOP PROTOCOL). One additional sequential fix + independent main-loop re-verification was
required after the fan-out to correct a regression the fan-out itself introduced (see below) —
that is the actual audit trail this report is honest about, not a clean single pass.

## Before/after (live `pencil_dod_evaluate_county`, independently re-run by the main session after all fixes)

### walton — 9/10 → **10/10**

| Letter | Before | After |
|---|---|---|
| A–H, J | PASS | PASS (unchanged) |
| **I** | **FAIL (89.7, card_complete=104 of 116)** | **PASS (98.3, card_complete=114 of 116)** |

### leon — 8/10 → **10/10**

| Letter | Before | After |
|---|---|---|
| A–H | PASS | PASS (unchanged) |
| **I** | **FAIL (88.5, card_complete=177 of 200)** | **PASS (96.5, card_complete=193 of 200)** |
| **J** | **FAIL (94.0, deal_complete=188 of 200)** | **PASS (100.0, deal_complete=200 of 200)** |
| **G*** | PASS (98.9) → **self-caused regression to FAIL (0.0)** during this session → **PASS (98.5)** | see below |

### taylor — 7/10 → **8/10**

| Letter | Before | After |
|---|---|---|
| A, C, D, E, G, H, J | PASS | PASS (unchanged) |
| **B** | **FAIL (null, verified=0 closed_sold=0)** | **FAIL (null, verified=0 closed_sold=0) — re-confirmed blocked, no regression, no fabrication** |
| **F** | **FAIL (null, tier1_sold=0 closed_sold=0)** | **FAIL (null, tier1_sold=0 closed_sold=0) — same** |
| **I** | **FAIL (90.9, card_complete=10 of 11)** | **PASS (100.0, card_complete=11 of 11)** |

## What moved

**walton I** (89.7% → 98.3%): 12 gap `id` rows (several case_numbers had 2 separate rows each).
Reused the proven `shard9_walton_cd_i_backfill.py` pattern against Walton County's EnerGov
ArcGIS FeatureServer (`services1.arcgis.com/TaXHPwWfIMuzJ7Ov`) — real parcel geometry (lat/lon),
appraised/just value, and zoning classification for 7 distinct parcel_ids covering 10 of the 12
rows. 2 rows (`26CA000030`, `25CA000608`) are brand-new stub cases from `calendar_sweep_mca_v3`
with no `parcel_id` anywhere — every lead was checked (`realforeclose_aids` only has the literal
scrape-artifact string `"Property Appraiser"` in its parcel_id field, qpublic/waltonpa.com
403-blocked, realforeclose detail pages login-gated, civitek OCRS is a non-scrapable JSF
postback form) and correctly left blank, not fabricated. 114/116 clears the ≥95% bar.
Adversarial verifier independently re-queried the live ArcGIS layer for one parcel and got an
exact match to the DB write (source genuine, not fabricated). **Verdict: SURVIVED.**
Commit `5ce4c9bb`.

**leon I** (88.5% → 96.5%): 20 of the 22 gap rows failed purely on missing `parcel_zones`
linkage (a recurrence of the same root cause dispatch `0fc2eae2` fixed on a prior set of rows).
Reused the proven Leon spatial pipeline (Census geocoder for missing lat/lon → point-in-polygon
query against `intervector.leoncountyfl.gov`'s TLC_OverlayZoning_D_WM ArcGIS layer) — 16 zoned,
4 genuinely unresolvable (vacant-land addresses like "0 TALQUIN COVE RD" the Census geocoder
cannot resolve to coordinates at all, consistent with prior sessions on this county). One row
(`parcel_id="MULTIPLE PARCELS"`, case `2025 CA 002309`) is a pre-existing fleet-wide placeholder
artifact, not a real parcel — flagged, not touched, out of scope for this fix. Adversarial
verifier independently re-queried the live ArcGIS layer for one parcel and got an exact match.
**Verdict: SURVIVED on the I metric itself.** Commit `49f842be`.

**leon J** (94.0% → 100.0%): 12 case_numbers had zero row in `bid_decisions` at all. Cloned the
existing proven per-county Shapira-formula generator `refresh_levy_bid_decisions()` into a new
`refresh_leon_bid_decisions()` (same canonical formula from CLAUDE.md:
`max_bid = GREATEST(0, ARV*0.70 - repairs - $10K - LEAST($25K, ARV*0.15))`, `ARV := COALESCE
(assessed_value*1.1, opening_bid_usd*3.5, 50000)`), with an explicit `honesty_marker:
'arv/ml_score INFERRED from opening_bid/assessed_value'` in the `factors` jsonb — the sanctioned
BLANK > WRONG pattern for inferred (not court-verified) deal-thesis data. One deliberate
deviation from the levy template: did not filter to `auction_type='tax_deed'` only, since leon's
gap spanned both foreclosure (11) and tax_deed (1) rows. Migration:
`supabase/migrations/20260809_gold_standard_leon_j_c5a8b2c7_bid_decisions_backfill.sql`.
Adversarially verified: all 12 rows spot-checked present with real honesty markers, function
confirmed in `pg_proc`, cron jobs 109/111/115 confirmed untouched. **Verdict: SURVIVED.**
Commit `5fbf0d95`.

**taylor I** (90.9% → 100.0%): the single failing row, case `26-042 CA` / parcel `06578-076`,
already had address/geo/value — only zone linkage was missing. Confirmed unincorporated status
via two independent US Census TIGERweb lookups, then classified against the same NCFRPC
georeferenced Future Land Use GeoPDF technique two prior taylor sessions proved out
(`ncfrpc.org/MapsAndPlans/Counties/Taylor/TAFU16tmpa.pdf`, Newton-iteration bilinear coordinate
inversion → pixel sample → legend-color match), landing on **AGR (Agriculture - Rural
Residential)**. The adversarial verifier fully re-derived this from scratch — fresh PDF parse,
independent `fsolve` inversion, independent pixel sample — and got a bit-identical result.
**Verdict: SURVIVED**, the most rigorously re-checked claim of the session. Commit `94f2e92f`.

**taylor B/F**: genuinely re-confirmed blocked, no regression, no fabricated `sold_amount`.
Beyond re-confirming the two prior sessions' dead ends (qpublic, pubrecords.taylorclerk.com,
taylor.realtdm.com's RealAuction TEST sandbox), this session found and fully investigated one
genuinely new lead: `taylorclerk.com` exposes an unauthenticated first-party REST API
(`/wp-json/kma/v1/{foreclosures,taxdeeds,landavailables}`, Civitek-backed) — but closed cases
have their post AND PDF media hard-deleted server-side with no sold-amount ever exposed, no
query-param bypass found. Also tried thirdcircuitfl.org (403), trellis.law (403/paywalled), and
FL GIO's ArcGIS FeatureServer (confirmed annual NAL refresh lag — all 5 target parcels still show
pre-sale owner/$0). Documented in `pipeline.counties.notes` for future sessions.
**The only remaining honest lever is a human phone call** to the Clerk's tax-deed department
(850-838-3506 ext 103, taxdeeds@taylorclerk.com) — every automatable source is now exhausted.
Commit `4229795f`.

## Self-caused regression, caught and fixed (the actual value of the ULTRALOOP verify step)

The leon-I fix agent inserted 5 new `parcel_zones` rows (zone codes CC, CP, OR-3, UT under
Tallahassee; C-2 under Unincorporated Leon) with **no matching `zoning_districts` row**. Because
`v_zoning_gold_standard_kpi_v3` defaults `far_applicable`/`pk1000_applicable` to `true` via
`COALESCE(...,true)` when no district row exists, these 5 parcels counted as "applicable but
missing a value" — an exact repeat of a previously-documented incident on this same county
(`gold_standard_ultraloop_audit` id 9152, dispatch `0fc2eae2`, 2026-07-24). This tanked leon's
letter **G from PASS (98.9%) to FAIL (0.0%)** live, mid-session.

The fix agent's own report misdiagnosed this as "unrelated... likely a concurrent shard's write,"
which the adversarial verifier **refuted with direct SQL evidence** — the 5 orphaned codes it
had just inserted were exactly the 5 driving `far_applicable_parcels=5, pct_far_of_applicable=0.0`.
This is the single most valuable finding of the session: without the independent refuter, this
regression would have shipped silently as an unrelated footnote.

Fixed with a dedicated follow-up agent that researched each code's real meaning and standards
directly from the Tallahassee-Leon County Land Development Code (Municode, Ch. 10, Art. IV,
Div. 4) — correcting a guessed "UT = Utility" to its real name, **University Transition
District** — and either cited real FAR/density/parking values or cited-and-explicit N/A overrides
(`far_regulated=false` for CC/UT, sourced to TABLE 10E's Intensity column reading "NA" and, for
CC, TABLE 8B's explicit Downtown Overlay parking exemption). Independently re-verified by the
main session (not the fix agent) against the live evaluator: **G: PASS, 98.5%** — recovered to
essentially its pre-regression level. Migration:
`supabase/migrations/20260809b_gold_standard_leon_g_orphan_zoning_districts_fix.sql`,
commit `740a0163`.

## Adversarial refuter findings that did NOT require a DB fix

The taylor-B/F fix agent's report was flagged **REFUTED** by its verifier on an honesty-framing
issue, not a data issue: it described the same-dispatch taylor-I fix (which landed on `main` one
minute earlier, same dispatch id, same session) as "residual drift from another concurrently
running shard... not claimed as my output" — which git history disproves (both commits carry the
same `c5a8b2c7` dispatch id, 68 seconds apart, no other walton/leon/taylor session was running in
parallel). The underlying B/F and I data claims were independently confirmed accurate either way;
this is logged here as a corrected attribution, not a database correction: **taylor I's 90.9%→
100.0% move belongs to this dispatch's own taylor-I fix agent**, not to an unrelated shard.

## Verification protocol evidence

Live `pencil_dod_evaluate_county` re-run independently by the main session (not any fix agent)
after all changes, for all three counties — full JSON pasted above per-letter. `git log` on
`origin/main` confirms all 6 commits landed: `5ce4c9bb` (walton I), `49f842be` (leon I),
`5fbf0d95` (leon J), `94f2e92f` (taylor I), `4229795f` (taylor B/F re-confirm), `740a0163`
(leon G regression fix).

`gold_standard_campaign` row `id=3984` (dispatch `c5a8b2c7-1d34-4ee5-a7a7-20ccdacb19a9`) updated
with `criteria_passed` per county, `exit_reason='timeout'`, `session_end_at` set, per the
mandatory close-out protocol.

## Parallel-fleet note

Per PARALLEL-FLEET RULES, the fleet-wide `gold_standard_loop()`/`certify()` was **not** run this
session (other shards were actively pushing to main throughout — observed commits for gilchrist,
lake, union, holmes, brevard/alachua/jefferson/liberty/holmes, lee/st_johns, columbia landing
concurrently). Only per-county live evaluations are reported above, all independently re-run by
the main session after the fact.

## Next-session priorities

1. **taylor B/F**: fully automation-exhausted. The only remaining lever is a human phone call to
   the Taylor County Clerk's tax-deed department. Not worth another automated-discovery session
   without a new source appearing.
2. **walton I / leon I residuals**: the 2 walton rows (`26CA000030`, `25CA000608`, no parcel_id
   at all) and 4 leon rows (vacant-land addresses unresolvable by the Census geocoder) are below
   the 95% bar's margin already and don't block PASS, but remain genuinely unresolved — a future
   session with browser-automation form-fill (civitek OCRS) or a different geocoder could close
   them.
3. **Fleet-wide takeaway**: any I-letter fix that inserts new `parcel_zones` rows MUST verify the
   corresponding `zoning_districts` row exists (or create it with correctly-researched
   category/standards) in the *same* session — this is the second time this exact regression
   pattern has hit leon (`0fc2eae2` then `c5a8b2c7`). Worth adding as an explicit checklist item
   in the I-letter playbook in CLAUDE.md.
