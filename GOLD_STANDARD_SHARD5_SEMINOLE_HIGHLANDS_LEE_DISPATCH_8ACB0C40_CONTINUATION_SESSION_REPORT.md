# GOLD STANDARD shard-5: seminole, highlands, lee — continuation session report

dispatch_id: `8acb0c40-fd3b-48a6-b357-fc15c79f973f`
chat_session: `architect-20260720T160000`
mode: ultracode (2 Workflow runs: zoning-research fan-out, then adversarial-verify fan-out)
firing: 2nd firing of this dispatch (prior firing: see `GOLD_STANDARD_SHARD5_SEMINOLE_HIGHLANDS_LEE_DISPATCH_8ACB0C40_SESSION_REPORT.md`, commit 53df17f3 and follow-up)

## Scoreboard: before -> after (live, `pencil_dod_evaluate_county`, re-verified after every fix)

| county | before this firing | after this firing | letters changed |
|---|---|---|---|
| seminole | 10/10 | 10/10 | none needed; adversarially re-confirmed genuinely stable (40 consecutive loop runs, ~46h, zero drift on E/G/I numerators) |
| highlands | 10/10 (evaluator) | 10/10 (evaluator), **but 2 letters flagged NOT certification-ready** | none numerically; adversarial pass found A and G are hollow/fabricated passes (pre-existing, not this firing's regression — see below) |
| lee | 6/10 (A,B,C,D,F,H PASS; E,G,I,J FAIL) | **7/10** (A,B,C,D,F,H,J PASS; E,G,I FAIL) | J 86.2%->100.0% PASS; G 20.0%->50.0% (still FAIL, real improvement); I 75.5%->77.7% (still FAIL, real improvement); E unchanged 87.4% |

## What shipped (3 commits, all live + on `main`)

1. **`c1b011be`** — `scripts/gold_standard_shard5_lee_j_generator.py` (J fix), `scripts/gold_standard_shard5_lee_ei_arcgis_backfill.py` (I fix), `supabase/migrations/20260720c_gold_standard_shard5_lee_g_reclassify_tfc_rv.sql` (G fix), and a `__main__` guard added to `.github/scripts/calendar_sweep_mca.py` (root-cause fix for the prior firing's incident, per its "next session priorities" list).
2. **`8e4e49a6`** (same push) — see above, single commit.
3. **`9998f3bc`** — `scripts/gold_standard_shard5_lee_j_stale_arv_fix.py`, remediating a real bug the adversarial-verify workflow caught in commit 1's J-generator (see Incident below).

## J: 86.2% -> 100% PASS, with a self-caught-and-fixed incident

`scripts/gold_standard_shard5_lee_j_generator.py` reused the proven county-agnostic J-generator pattern (same formula as `shard14_martin_bay_alachua_j_generator.py` and others already shipped this campaign) to fill the 44-case gap in `bid_decisions` coverage. Live median(assessed_value, market_value) for lee ($256,703, n=255) used as the documented fallback ARV only when a row has no valuation data of its own — same convention as every prior county's J-generator.

**Incident (caught by adversarial verify, not by me):** I ran this script *before* the E/I ArcGIS backfill script in the same session. 28 of the 65 newly-inserted rows had no assessed_value/market_value/opening_bid *at generation time*, so correctly fell back to the disclosed default — but the very next script in this session (the E/I backfill) then populated real ArcGIS-sourced assessed_value for several of those same case_numbers, leaving `bid_decisions.arv` stale relative to the now-better data. The refuter subagent caught this independently and flagged it as "48/65 rows carry a fabricated/templated ARV." I re-verified myself with a direct query and found 28 rows (not 48 — the refuter's count differed slightly, possibly a broader threshold) where recomputing against current data would produce a materially different ARV.

**Fix:** `scripts/gold_standard_shard5_lee_j_stale_arv_fix.py` recomputed and patched all 28 rows in place (same case_numbers, same `pipeline_run_id`, no new rows) using current live data. Re-verified: the remaining 37 fallback-valued rows all have genuinely NULL assessed/market/opening_bid — correct use of the disclosed default, not a bug. `pencil_dod_evaluate_county('lee')->J` still `pass=true, metric=100` after the fix.

**Lesson for next session:** run E/I enrichment *before* J-generation, or re-run the J-generator's recompute step after any enrichment pass in the same session, to avoid this staleness class of bug recurring.

## I: 75.5% -> 77.7% (240/318 -> 247/318 of 318, still FAIL)

`scripts/gold_standard_shard5_lee_ei_arcgis_backfill.py` queried the live Lee County ArcGIS FeatureServer (`services2.arcgis.com/LvWGAAhHwbCJ2GMP/.../Lee_County_Parcels/FeatureServer/0/query`) by STRAP for 38 targeted rows (31 missing `parcel_zones` linkage + 7 missing lat/lng despite already being zoning-linked), plus 5 address-only lookups for rows with no `parcel_id` at all.

Result: 7 rows (the already-zoning-linked-but-missing-geo set) got real lat/lng/assessed_value backfilled and are now card-complete. The other 31 got real ArcGIS zoning codes back (R1, RS-1/6/7, MH-1/2, AG-2, RM-2, CG, CPD, MPD, NC, CS across Cape Coral/Fort Myers/Bonita Springs/Lee-Unincorporated) but were **deliberately NOT linked into `parcel_zones`** because none of those (jurisdiction, code) pairs has a `zoning_districts` row yet in that specific municipality — inserting them without a real density value would have regressed G's already-passing density sub-metric (96.1%) for no I-gain this session. Adversarially verified: no fabrication, no regression, and the 31-row residual exactly matches what was documented.

**Residual (honest, not fabricated):** 31 lee rows need per-jurisdiction zoning-districts + real density-value research (Cape Coral's own LDC for 8 "R1" parcels, Fort Myers' own code for ~19, Bonita Springs for the rest) before they can be linked without risking a G regression. 5 of the original 40 E-gap rows have addresses but got zero ArcGIS address-match hits (residual, not fabricated). 35 of 40 E-gap rows have no address at all — confirmed same root cause as the prior firing: genuine RealForeclose/calendar-sweep source gap, needs a session-aware court-record lookup (Playwright/Firecrawl-browser), not attempted this firing either.

## G: 20.0% -> 50.0% (still FAIL) via real ordinance research, not denominator gaming

The prior firing explicitly flagged 5 `zoning_districts` rows (TFC2 x2, TFC-2, RV-2, MDP-3) as miscategorized `category='commercial'` with no parking value, but declined to fix it without "its own review" given the ghost-success risk of shrinking a denominator.

This firing ran an ultracode Workflow (2 independent research subagents, WebSearch+WebFetch, 66 tool calls) against Lee County LDC, City of Fort Myers, and City of Bonita Springs primary sources:

- **TFC2 (Lee Co. Unincorporated, id 11216) — CONFIRMED residential** ("Two-Family Conservation" district, LDC Ch.34 Art.VI Div.3 Subdiv.II, section headers independently corroborated).
- **TFC-2 (Bonita Springs, id 11235) — CONFIRMED residential** (city's own 2020 public notice, directly fetched, explicitly names it "Two Family Conservation").
- **TFC2 (Fort Myers, id 11234) — HYPOTHESIS residential** (absent from current Chapter 118 entirely — a legacy carryover; same regional naming precedent, but Fort Myers' own legacy text is Municode-403-blocked, not directly read).
- **RV-2 (Fort Myers, id 11233) — HYPOTHESIS not-pk1000-applicable** (Lee LDC Div.4 "Recreational Vehicle Park Districts" — per-space siting, not per-1000sf building parking — same legacy-carryover pattern).
- **MDP-3 (Fort Myers, id 11229) — UNKNOWN, left untouched.** The literal string does not appear in any indexed Fort Myers zoning source, current or legacy. The research agent's leading hypothesis is this may not even be a real ordinance section (confusable with the Live Local Act's generic "Master Development Plan" label). **No number fabricated.**

Applied via `supabase/migrations/20260720c_gold_standard_shard5_lee_g_reclassify_tfc_rv.sql`: 3 districts reclassified `category='residential'` + `pk1000_regulated=false`; 1 (RV-2) `pk1000_regulated=false` only (category left `commercial`, since it isn't cleanly residential either — a defensible middle ground). Citations logged to `zoning_gold_standard_vault`. `pk1000_applicable_parcels` 10 -> 4, numerator untouched at 2 (two unrelated real-value districts from a prior session), so pk1000 = 50.0%.

**Adversarially re-verified independently** (different search terms, direct re-fetch of Fort Myers' current district list): reproduced the same conclusions, confirmed the migration's own HYPOTHESIS-vs-CONFIRMED labeling was accurate rather than overstated, and confirmed MDP-3's 2 parcels were honestly left unresolved rather than guessed. **Verdict: CONFIRMED — genuine evidence-based correction, not metric gaming.**

**Residual:** MDP-3's 2 parcels remain genuinely open. G cannot reach PASS until either MDP-3 is resolved (needs a browser-capable fetch tool per the research agent's own notes — Municode/city GIS both blocked plain HTTP fetches) or a real parking value is sourced some other way.

## Adversarial verification findings that are NOT this session's fault — flagging for the campaign

The refuter fanned out to re-check highlands' "10/10" claim from the *prior* firing, independently of anything done this session, and found two real integrity gaps that mean **highlands should not be treated as certification-ready** despite the evaluator showing all 10 letters PASS:

- **Highlands A is built on 2 fabricated placeholder rows**: `case_number` = `HIGHLANDS-FC-2026-001`/`002` (not real court format), `property_address` = literal `"TBD HIGHLANDS FL"`, `data_source` = `realforeclose:shard5-highlands-fc-v1` (internal tooling signature, not a real scrape). This was already flagged as an open gap in the prior firing's own session report ("highlands foreclosure lane integrity... fabricated stub data from an earlier session"). Confirmed still present, still fabricated, still unaddressed.
- **Highlands G is a hollow pass**: `far_applicable_parcels=0` and `pk1000_applicable_parcels=0` for highlands — Postgres `LEAST(100.0, NULL, NULL)` silently ignores the NULLs and returns 100.0. All 175 highlands `parcel_zones` rows are residential (R-1A/R1/R4); 6 commercial `zoning_districts` exist at the ordinance layer but zero parcels are ever matched to them. Could be genuine (rural county, mostly residential/ag tax-deed inventory) or an ingestion gap — inconclusive on root cause, but the PASS is structurally hollow either way since 2 of 3 sub-metrics never get evaluated.

Both findings are logged as `survived=false` in `gold_standard_ultraloop_audit` (highlands/A, highlands/G) per the EVALUATOR V6 certify-gate rules — this should block highlands certification until a future session either replaces the 2 synthetic foreclosure rows with real scraped data, or resolves whether highlands genuinely has zero commercial-zoned parcels in its auction population.

## Adversarial verification summary (ULTRALOOP, 2 Workflow runs)

**Research workflow** (`wf_17b79f54-fe6`, 2 agents, 150K tokens, 66 tool calls): resolved the G reclassification questions above.

**Verify workflow** (`wf_e876294e-4d4`, 5 refuter agents, 325K tokens, 103 tool calls):
- `refute-lee-J`: CONFIRMED-with-caveat -> caveat fixed live (see Incident above), now fully CONFIRMED.
- `refute-lee-I`: CONFIRMED, no fabrication or regression.
- `refute-lee-G`: CONFIRMED, genuine evidence-based correction.
- `refute-highlands-10of10`: REFUTED (2 pre-existing integrity gaps, not this firing's regression).
- `refute-seminole-10of10`: CONFIRMED, genuinely stable across 40 consecutive loop runs (~46h).

6 rows logged to `gold_standard_ultraloop_audit`: lee/J, lee/I, lee/G, seminole/E = `survived=true`; highlands/A, highlands/G = `survived=false`.

## Verification protocol compliance

- Live before/after JSON pasted above and per-fix, re-queried fresh after every change (not reconstructed from memory).
- `git pull --rebase` run before every push; no conflicts.
- `SELECT public.gold_standard_loop()` / `certify()` **not run** — other shards mid-flight concurrently per PARALLEL-FLEET RULES; per-county `pencil_dod_evaluate_county` used throughout, as instructed.
- Live final check, this moment:
  ```
  lee:   {"J":{"pass":true,"metric":100},"G":{"pass":false,"metric":50},"I":{"pass":false,"metric":77.7},"E":{"pass":false,"metric":87.4}}
  ```

## Next session priorities

**lee:**
1. E: needs a session-aware court-record lookup (Playwright/Firecrawl-browser) for 35 no-address rows — plain ArcGIS/curl cannot resolve these (confirmed, 2 firings running).
2. G: MDP-3 (Fort Myers, id 11229) — try a browser-capable fetch tool against Municode/Fort Myers GIS (both are blocking plain HTTP fetches with 403, per two independent research passes now).
3. I: the 31-row residual needs per-jurisdiction zoning_districts + real density-value research (Cape Coral, Fort Myers, Bonita Springs each have their own code, not a shared Lee LDC crosswalk) before linking without risking a G regression.
4. When running multiple lee scripts in one sitting, run enrichment (E/I/geo/value) BEFORE any J-generation step, to avoid the staleness class of bug this session caught and fixed.

**highlands:**
5. Replace the 2 synthetic `HIGHLANDS-FC-2026-001`/`002` foreclosure rows with real scraped highlands.realforeclose.com data (or confirm via clerk records if highlands foreclosures truly route through a different calendar).
6. Determine whether highlands genuinely has zero commercial-zoned parcels in its auction population, or whether commercial parcel-zone assignment was simply never run for highlands' 3 jurisdictions.
