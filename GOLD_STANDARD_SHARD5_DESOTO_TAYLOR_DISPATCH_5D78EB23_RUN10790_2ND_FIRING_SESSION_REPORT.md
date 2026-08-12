# Gold Standard shard-5: desoto / taylor — dispatch 5d78eb23, loop run 10790 (2nd firing)

Session: architect-20260812T080000, 2026-08-12. A concurrent session fired on this exact
same dispatch_id earlier and left an unexecuted script + migrations on main (commits
4e9a33f0/7aed3c8a/5513d7db/c1b71730) — this report picks up from there, fixes two real
production-safety bugs in that unexecuted artifact set, and does the actual live work.

## Result summary (live `pencil_dod_evaluate_county`, before = issue brief / after = this session)

| County | Before | After | Delta |
|---|---|---|---|
| desoto | 7/10 (A,B,C,D,F,G,H) | **9/10** (+E,J) | E 82.6%→95.7% PASS, J 82.6%→95.7% PASS, I 34.8%→82.6% (still FAIL, real residual gap) |
| taylor | 6/10 (A,D,E,G,H,I,J) | **7/10** (+D) | D 72.7%→100% PASS, C 45.5%→72.7% (still FAIL, structural floor) |

## Part 1 — neutralized two production-safety bugs in the concurrent session's unexecuted artifacts

`git pull --rebase` at session start surfaced 4 commits from a parallel session on this same
dispatch_id, whose own report says explicitly "I cannot query live Supabase from this runner
(no DB credentials at session time)" — `scripts/shard5_10790_desoto_taylor_fix.py` and its
migrations were committed but **never run**. Reviewing them before doing my own work surfaced
two real bugs that would have corrupted live data had a future automated run executed them
blind (per this codebase's own WIRING MANDATE culture, that report's "Next Session Priorities"
literally said "Execute this script"):

1. **`step4_taylor_cd`** would have blind-stamped ALL 11 taylor rows as `matched_clean`
   regardless of current status — including the 3 rows genuinely marked
   `CLERK_SSOT_CANCELLED` by the Aug-10 lake clerk_ssot migration's explicit design (cancelled
   sales are NOT clean matches). Disabled — see commit below.
2. The zoning-substrate migration's jurisdiction `INSERT`s used names ("DeSoto County
   Unincorporated", "City of Arcadia") that don't match DeSoto's real existing jurisdiction
   rows ("Unincorporated DeSoto County" id=1406, "Arcadia" id=829) — would have silently
   created duplicate jurisdictions with a cruder, redundant zoning substrate. Fixed the name
   mismatch, removed the redundant Arcadia section (which already has 24 real municode-sourced
   codes).

Also fixed the script's FL GIO ArcGIS org ID (pointed at a nonexistent service) and its
CO_NO fallback list (verified live this session that CO_NO=14 is Bradford, not DeSoto, in
this layer's numbering — confirmed by querying it directly and getting Lawtey, FL parcels).

Commit `f2d49c32`.

## Part 2 — taylor C/D: root cause diagnosed and fixed live

Live query showed taylor C had regressed from 100% (prior sessions) to 45.5% on the *same*
11-row denominator — not a new-rows problem. Traced it: 3 rows (23-597 CA, 25-210 CA,
26-042 CA) had `parity_status='matched_clean'` but `parity_source='taylor_clerk_foreclosure'`
— missing the `tier1:` prefix `pencil_dod_evaluate_county`'s C/D filters require (per the
20260810 lake clerk_ssot migration). Independently re-verified all 3 field-by-field against
taylorclerk.com's live first-party `kma/v1` API (sale_date + amount exact match) before
re-stamping `parity_source`. Applied live via PostgREST PATCH.

D: 72.7% → **100% PASS**. C: 45.5% → 72.7%, correctly still FAIL — the remaining 3-row gap
(25-014 CA, TDA 26-031, TDA 26-032) are legitimately clerk-cancelled/redeemed sales, which by
existing design count toward `matched_any` (D) but never `matched_clean` (C). Not a bug to
paper over.

Migration: `supabase/migrations/20260812_gold_standard_shard5_taylor_cd_tier1_prefix_fix.sql`.
Commit `f2d49c32`.

## Part 3 — desoto E/I/J: research workflow (ULTRALOOP, native mode)

Dispatched a 5-agent workflow (2 finders in parallel, 1 taylor-B/F freshness recheck, 2
independent adversarial verifiers) against desoto's remaining gaps.

**E (4 unlinked foreclosure rows):** FL GIO's broad-filter queries were unreliable again this
session (confirmed independently by both the finder and my own direct testing — exact-
PARCEL_ID lookups work, everything else times out). Pivoted to the DeSoto County Tax
Collector's live VisualGov search API. 3 of 4 resolved with owner-name cross-check against the
court defendant: 24CA457 (Forbes), 2025CA166 (Cho Chung Hing / "Hing" surname match), 26CA168
(Milazzo, strongest match — confirmed via two independent search paths). The 4th, 25CA508, was
explicitly **not** linked: the DeSoto tax roll's current owner is Benfield, not Roan (the case
defendant) — a real, independently-reconfirmed mismatch. All 4 findings SURVIVED adversarial
re-verification (the verifier independently re-ran the source queries and additionally
cross-confirmed the 3 linked parcels against FL GIO by exact PARCEL_ID). E: 82.6% → **95.7%
PASS**.

**I (11 tax-deed zone-gap rows):** 9 of 11 resolved to real Arcadia zone codes (R-1B/R-1C) via
a newly-discovered source, the CFRPC-hosted `City_of_Arcadia_Zoning` FeatureServer — 4 by exact
PARCEL_ID match, 5 by point-in-polygon spatial fallback (exact STRAP absent from the layer, but
the coordinate lands in a same-block sibling parcel's polygon, and the whole platted
subdivision is uniformly R-1B). 2 rows (26-20-TD, 26-19-TD) plus one of the newly-E-linked rows
(2025CA166) are confirmed **outside** Arcadia (TIGERweb boundary check returns empty) — genuine
unincorporated DeSoto County, whose zoning has no accessible ArcGIS REST service. Left
zone-unresolved rather than guessed. New finding for future sessions:
`desotocounty-dcms-gis.hub.arcgis.com` is DeSoto County, **Mississippi**'s GIS hub, a naming
collision, not Florida. All findings SURVIVED adversarial re-verification. I: 34.8% → **82.6%,
still FAIL** — 4 genuinely open rows (1 owner mismatch, 3 unincorporated-zoning-unknown), not
fabricated closed.

**J:** generated `bid_decisions` for the 3 newly E-linked rows, Shapira V14 formula matched
field-by-field against a live pre-existing desoto row before use. J: 82.6% → **95.7% PASS**.

## Part 4 — self-caused G regression, caught and fixed same session

Linking 11 new parcels to Arcadia zoning districts R-1B/R-1C exposed that both districts have
real, sourced `zone_standards` (min_lot_sqft, setbacks, parking, confidence 0.85, municode
Article 5) but `max_density_du_acre` was never populated. `v_zoning_district_applicability`
defaults residential districts to density-applicable=true when unset, so this dragged desoto
**G from 100% to 38.9% FAIL** live, mid-session.

Did not guess a density figure — a naive `43560/min_lot_sqft` calculation would have been
**wrong**: the existing R-1A district's real recorded density (3.0) doesn't match that formula
either (would give 4.36), proving density in this ordinance isn't lot-size-derived. Dispatched
a focused research agent to read the actual ordinance text (Arcadia ULDC Article 5, Table
5.09.01 "Residential Zoning Development Standards", `arcadia-fl.gov`). Confirmed: that table
has **no density or FAR column for single-family districts** (R-1A/R-1B/R-1C) — density caps in
Article 5 apply only to the multi-family R-3/R-4 districts via a separate table's footnotes.
This is real, sourced evidence that R-1B/R-1C are governed by lot-size/setback/height/coverage
standards alone. Set `density_regulated=false`, `far_regulated=false` on both districts live.
G confirmed restored to **100% PASS**.

Migration (documents all live PostgREST writes for E/I/J/G):
`supabase/migrations/20260812_gold_standard_shard5_desoto_eij_g_fix.sql`. Commit pending in
this session's push.

## Part 5 — taylor B/F: fresh re-check, confirmed no change

Per the exhausted-source protocol (4+ prior sessions), did a narrow fresh check only (not a
full re-discovery): live re-query of `kma/v1/foreclosures`, `kma/v1/taxdeeds`, and the
tax-deeds-surplus page. All 5 target cases (25-218 CA, TDA 26-028, TDA 26-026, 25-196 CA,
25-217 CA) remain absent from all three sources, identical to the 2026-08-09 finding. No new
lead. The only remaining honest lever is a human phone call to the Clerk's tax-deed department,
out of scope for automation.

## ULTRALOOP audit

8 rows written to `gold_standard_ultraloop_audit` (dispatch `5d78eb23-a7b7-4e6b-9710-79df9e8040df`,
`ultraloop_mode='native'`): desoto E/I/J/G (all `survived=true`), taylor D/C (`survived=true`),
taylor B/F (`survived=false` — correctly logged as no-new-evidence, not a false claim).

## SQL VERIFICATION

```
SELECT public.pencil_dod_evaluate_county('desoto');
{"A":{"pass":true,"metric":10},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":95.7,"detail":"parcel_linked=22"},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.1},"I":{"pass":false,"metric":82.6,"detail":"card_complete=19 of 23"},"J":{"pass":true,"metric":95.7,"detail":"deal_complete=22"},"auctions_total":23}

SELECT public.pencil_dod_evaluate_county('taylor');
{"A":{"pass":true,"metric":4},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":72.7,"detail":"matched_clean=8"},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":16.7},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"auctions_total":11}
```
Timestamp: 2026-08-12 ~09:20 UTC.

`gold_standard_campaign` row id=4187 (dispatch `5d78eb23-a7b7-4e6b-9710-79df9e8070df`)
closed out: `criteria_passed` set per county above, `exit_reason='timeout'`,
`session_end_at` set. Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`certify()` were
**not** run this session (cannot confirm no other shard is mid-flight); per-county
`pencil_dod_evaluate_county` is the verification of record here.

## Next-session priorities

1. **desoto I (4 rows, 82.6%→need 95.7%):** 25CA508's owner mismatch needs the actual
   court docket from desotoclerk.com (Cloudflare-gated to curl/WebFetch this session — no
   browser-automation tool was available, Firecrawl account has zero credits). The 3
   unincorporated-zoning-unknown rows (2025CA166, 26-20-TD, 26-19-TD) need either a call to
   DeSoto County Planning & Zoning (863-993-4806) or a higher-resolution copy of
   `desotobocc.com/DocumentCenter/View/1956/Zoning-Map-PDF` — the low-res version downloaded
   this session confirmed the code universe (MHP/MHS plausible by land-use pattern, DOR_UC=002
   mobile-home) but couldn't be read precisely enough at the exact coordinates to avoid a guess.
2. **taylor B/F:** fully automation-exhausted across 5 sessions now. Not worth another
   automated pass without a new source appearing — the phone-call lever is the only one left.
3. **taylor C:** structurally capped below 95% while any row is legitimately cancelled;
   monitor for new auctions that could dilute the ratio, but do not attempt to reclassify the
   3 cancelled rows.
4. **Fleet-wide takeaway (reinforcing the existing CLAUDE.md guardrail):** confirmed again this
   session that linking parcels to *existing* zoning districts can still cause a G regression if
   those districts have incomplete `zone_standards` — check density/FAR/parking values are
   actually populated for the specific districts being newly populated, not just that the
   district row exists.
