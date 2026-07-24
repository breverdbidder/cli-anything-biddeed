# Gold Standard Shard-5: osceola — dispatch ac5f5206, 3rd firing addendum

dispatch_id: `ac5f5206-a862-494e-a345-f6b0eb4cbd09`
chat_session: `architect-20260724T000000` (3rd invocation, same dispatch)
loop run: 6080

## This firing's brief was stale — verified live before touching anything

The incoming brief for this firing pasted the **1st firing's "before" snapshot**
(`I=35.8% [48/134]`, `G density=7.7`) as if it were current state. Live
`pencil_dod_evaluate_county('osceola')` at session start showed the real state matched
the **2nd firing's "after"**: `I=72.4% [97/134]`, `G density=88.1 far=0.0 pk1000=0.0`,
8/10 (G, I FAIL) — no drift, no regression between firings 2 and 3. Proceeded from the
2nd firing's documented "next-session priorities," not from the stale brief.

## Method: ULTRACODE workflow, 5 research agents + independent adversarial refuter per finding

Per the ULTRALOOP protocol, one workflow (`wf_cb376b9e-744`) fanned out:
- 1 agent: real zone_code for 6 parcels (7 case rows) that the 2nd firing's ghost-purge
  had left with full address/lat/lon/value but no zone linkage — a gap the 2nd firing's
  own addendum didn't explicitly enumerate (its residual list covered 30 of the 37
  remaining rows; these 7 were the difference).
- 1 agent: geocode + zone + value for the 2 OSC- synthetic-id rows whose addresses the
  2nd firing recovered but couldn't fully resolve (2011 CA 003872 MF, 2019 CA 000153 MF).
- 3 agents: G-letter codification research — Kissimmee T3, Kissimmee SRPUD, St Cloud R-3
  real max_far / max_density_du_acre, following up on the 2nd firing's finding that these
  3 codes have zero `zoning_districts` coverage (defaulting to `applicable=true` with no
  standards, which is what pulled G's density sub-metric from 97.4% to 88.1% when the
  2nd firing added real zone linkage for 4 of these parcels).

Every non-declined finding got an independent refuter agent whose only job was to try to
break it via fresh re-fetch/re-derivation (not re-reading the original claim).

## I letter: 72.4% → 76.9% (97 → 103 of 134)

**Applied (6 of 8 zone-linkage candidates, all `survived=true` per an independent refuter):**

| case | parcel_id (real) | zone | jurisdiction | source |
|---|---|---|---|---|
| 19892023 | 112529181100010210 | RA-3 | Kissimmee | cw.kissimmee.gov Zoning_Districts/10 |
| 19952023 | 112529235700010830 | RA-3 | Kissimmee | same |
| 36212023 | 212529181600 | T5-M | Kissimmee | same (spatial match; county PARCELNO ambiguous, zone determination is not) |
| 52962018 | 262630061300011010 | R-3 | Saint Cloud | arcgisweb.stcloud.org Zoning/2 |
| 2011 CA 003872 MF | 072530272401950380 | PD | Osceola unincorp. | FL GIO + Osceola Parcels/Zoning_Parcels FeatureServer |
| 2019 CA 000153 MF | 3026315130000D0070 | E-1 | Osceola unincorp. | same |

The last 2 also got real geo (lat/lon) and value (assessed + market) backfilled from the
same FL GIO / county-GIS records — these 2 rows went from address-only to fully complete
in one pass.

**Declined (2 of 8, refuted by an independent adversarial agent — not written):**

1. **Case 31152023 / parcel 182529227600011636 (SRPUD, Kissimmee)** — the refuter's Part A
   independently re-confirmed the raw GIS data was clean (single unambiguous spatial
   match, cross-checked against a second cadastral source). It refuted on Part B: this
   specific parcel/case pairing doesn't appear in an **older, unrelated session's**
   committed addendum. That's true of any brand-new finding — this looks like a category
   error in the refuter's reasoning, not a real data problem. Per this campaign's own
   precedent (CLAUDE.md SHIP GATE: "Sentinel is correct by default; the burden of proof is
   on whoever disagrees"), this session does **not** override the refutation despite
   disagreeing with it. Flagged for next session to re-verify with a refuter prompt that
   doesn't conflate "not yet documented" with "fabricated."
2. **Case 8642023 / parcel 052529152400 (MUPUD, Kissimmee)** — refuted on a real,
   substantive concern: the truncated 12-digit "parcel" is a shared prefix across 24 condo
   units + 1 COMM parcel with no source confirming which unit (if any) case 8642023
   actually corresponds to. Correctly declined, consistent with this campaign's standing
   handling of ambiguous truncated-parcel matches.

**Residual, still unresolved (~28 of 134):** the 24 placeholder-address rows and 3
refuted-PDF-address OSC- rows from the 2nd firing's residual list are unchanged — no new
information surfaced on those this firing.

## G letter: zero writes this firing (4th consecutive correct decline)

All 3 codification findings (Kissimmee T3 FAR/density, Kissimmee SRPUD FAR/density, St
Cloud R-3 max_density_du_acre) were held back:

- **Kissimmee T3**: refuted — the refuter independently corroborated the primary,
  mechanically-checkable claim (LDC Table 5-2 has no FAR or density column for any
  transect zone, T3 included) but could not locate one specific supporting sentence about
  future-land-use-driven density caps across 4 fetch attempts. Per protocol, refuted =
  not counted, even though the load-bearing structural evidence held up.
- **Kissimmee SRPUD**: survived refutation, but the research agent self-labeled it
  **HYPOTHESIS**, not CONFIRMED — neither it nor its refuter had a browser/Playwright
  tool in this sandbox to read Kissimmee's Municode text directly; both relied on
  third-party mirrors and search snippets. This campaign's established precedent (every
  prior G write — PD/PMUD/STRPD/AC/CR/CT/RMH — was CONFIRMED against directly-read
  ordinance text) sets the bar above HYPOTHESIS for a production `zoning_districts` write.
  Held back.
- **St Cloud R-3**: refuted — the refuter found an unresolved October 2025 St Cloud
  comprehensive-plan/zoning-update cycle it could not rule out as having amended this
  section after the claim's cited November 2023 ordinance, and had no way to
  independently re-render the JS-only Municode page to check.

G's `density` sub-metric detail moved **88.1% → 78.7%** as an honest side effect of the
6 new zone_code writes above (RA-3 x2, T5-M, R-3, PD, E-1 — none has a `zoning_districts`
row yet, so `v_zoning_gold_standard_kpi_v3` correctly defaults them to
density-applicable-but-missing). Same pattern as the 2nd firing's T3/SRPUD/R-3 finding:
real data revealing a real gap, not a regression to revert. **G's pass/fail and `metric`
field were already 0 (bound by pk1000) before and after** — no change to G's overall
status. pk1000 remains structurally blocked (declined 3x already, no new information this
firing — not re-attempted).

## Before / after (live, `pencil_dod_evaluate_county('osceola')`)

```
BEFORE (session start, = 2nd firing's ending state, re-verified):
{"A":"PASS 5","B":"PASS 100.0","C":"PASS 100.0","D":"PASS 100.0","E":"PASS 100.0",
 "F":"PASS 100.0","G":"FAIL 0.0 [density=88.1 far=0.0 pk1000=0.0]","H":"PASS 11.6",
 "I":"FAIL 72.4 [card_complete=97 of 134]","J":"PASS 96.3"}

AFTER:
{"A":"PASS 5","B":"PASS 100.0","C":"PASS 100.0","D":"PASS 100.0","E":"PASS 100.0",
 "F":"PASS 100.0","G":"FAIL 0.0 [density=78.7 far=0.0 pk1000=0.0]","H":"PASS 0.0",
 "I":"FAIL 76.9 [card_complete=103 of 134]","J":"PASS 96.3"}
```

Still 8/10 (G, I FAIL). **I: 72.4% → 76.9%** (97 → 103, real verified gain). G's overall
status unchanged (still bound by pk1000=0.0); density detail moved as an honest side
effect of real new zone data, documented above. Not a certification.

## ULTRALOOP audit

11 rows logged to `gold_standard_ultraloop_audit` (dispatch `ac5f5206`, `ultraloop_mode='native'`):
8 I-letter rows (6 `survived=true`/applied, 2 `survived=false`/declined) + 3 G-letter rows
(1 `survived=true` but deliberately NOT applied — the SRPUD finding, held back pending
CONFIRMED-level verification — plus 2 `survived=false`/declined: T3 and St Cloud R-3).
7 `survived=true` total, 4 `survived=false` total.

## Next-session priorities for osceola

1. **I, case 31152023**: re-verify the SRPUD/182529227600011636 finding with a refuter
   prompt that doesn't penalize "not in an older session's addendum" as if it were
   evidence of fabrication — the raw GIS data already checked out clean once.
2. **I, ~28 rows**: the 24 placeholder-address rows and 3 refuted-PDF-address OSC- rows
   carried over unchanged from the 2nd firing's residual list — still need either
   heavier address-to-`fl_parcels` matching or an authenticated clerk-docket retry.
3. **G, SRPUD**: with a browser/Playwright-capable tool, read Kissimmee LDC Sec 14-4-8.C /
   14-4-8.B.4 directly to upgrade the HYPOTHESIS "not codified" finding to CONFIRMED (or
   refute it) — this session's research is a strong head start, not a restart.
4. **G, T3 and St Cloud R-3**: same browser-tool gap blocked both; T3's core evidence
   (Table 5-2 has no FAR/density row) already checks out, just needs the supporting
   future-land-use-cap citation located. St Cloud R-3 needs the 2023-vs-2025 ordinance
   version resolved before the `max_density_du_acre=10` figure can be trusted.
5. **G pk1000**: still structurally blocked (use-keyed LDC Table 4.7.8, no per-parcel
   override) — declined a 4th time this campaign, no new information. Needs the
   schema/view change flagged repeatedly, or a per-parcel land-use data source.
