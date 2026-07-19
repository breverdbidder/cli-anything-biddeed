# Gold Standard Shard-3: orange / hernando / miami_dade / okaloosa — 3rd firing addendum

dispatch_id: c366ee22-d3b0-463b-a846-62ee258772f2 (3rd re-fire of the same dispatch — see `..._SESSION_REPORT.md` and `..._CONTINUATION_ADDENDUM.md` for the first two firings)
mode: ultracode Workflow fan-out — 2 sequential build+verify workflows (okaloosa I/C/E, then okaloosa G regression fix), 6 agents total, ~595K subagent tokens, 286 tool calls

## Why this addendum exists

This is the 3rd firing of dispatch `c366ee22`. Live `pencil_dod_evaluate_county` calls at session start confirmed the 2nd firing's work was already live and unchanged: orange 10/10, hernando 10/10, miami_dade 10/10, okaloosa 7/10 (C, E, I failing). Per the ship-to-main mandate, this session picked up the 2nd firing's documented "Next-session priorities" for okaloosa — the only county not at 10/10 — and worked C/E and I to completion, which in turn caused a genuine, disclosed regression on G that this session also fixed (partially).

## Status Board (before this session -> after, live `pencil_dod_evaluate_county`)

| County | Before | After | Delta |
|---|---|---|---|
| orange | 10/10 | **10/10** | unchanged — regression check only, confirmed |
| hernando | 10/10 | **10/10** | unchanged — regression check only, confirmed |
| miami_dade | 10/10 | **10/10** | unchanged — regression check only, confirmed |
| okaloosa | 7/10 (C,E,I fail) | **9/10** (G fail) | C, D, E, I fixed; G newly regressed to 10% then partially recovered to 75.6% (still FAIL) as a disclosed side-effect of the I-fix |

### SQL VERIFICATION (fresh, this session, 2026-07-19 ~19:55 UTC, post-push on commit `bf4af1dd`)

```
SELECT public.pencil_dod_evaluate_county('orange');
 -> A321 B100 C100 D100 E99.1 F100 G98.3 H4.4 I95.1 J100  (10/10, auctions_total=855)

SELECT public.pencil_dod_evaluate_county('hernando');
 -> A13 B100 C100 D100 E100 F100 G97.2 H2.3 I95.9 J100  (10/10, auctions_total=49)

SELECT public.pencil_dod_evaluate_county('miami_dade');
 -> A81 B100 C96.6 D96.6 E96.6 F100 G99.3 H4.4 I96 J100  (10/10, auctions_total=350)

SELECT public.pencil_dod_evaluate_county('okaloosa');
 -> A13 B100 C95 D95 E95 F100 G75.6(FAIL) H0.3 I95 J100  (9/10, auctions_total=40)
```

## orange / hernando / miami_dade — regression check only, no work planned or done

Confirmed genuinely unchanged and still 10/10 live on all four letters-groups, before AND after this session's okaloosa work (checked at session start and again at session close). No regression — these three counties were never touched by either workflow (okaloosa-scoped work only), consistent with the shard rule against modifying other counties' passing letters.

## okaloosa — C/D/E/I fixed via real GIS discovery; G regressed then partially recovered

### Track 1: I (zoning substrate) — 0% FAIL -> 95% PASS

Root cause: `parcel_zones` had exactly 7 okaloosa rows, all synthetic bootstrap placeholders (`OKA-*`, `SYN-OKA-*`) that matched none of the real APN-format `parcel_id`s already on `multi_county_auctions`. Prior firings of this dispatch had flagged okaloosa I as "not a quick win, needs full zoning substrate" — this session found the actual lever: a live, no-auth Okaloosa County GIS zoning layer (`okgis.myokaloosa.com/.../Planning-Development/Zoning/MapServer/28`, field `ZNGPY_ZONE`) plus 4 municipal zoning layers (Crestview, Fort Walton Beach, Niceville, Destin) discovered live this session. Resolved jurisdiction per parcel via a real city-limits boundary layer (`Admin-Boundaries/Admin_Boundaries/MapServer/99`), shipped a new "Unincorporated Okaloosa County" jurisdictions row (id=1407) via an idempotent INSERT-only migration, and inserted 38 of 38 real parcel_zones rows with honest per-row source citations (e.g. `okaloosa_gis:planning-development/zoning:28`, `crestview_gis:zoning_and_flu_featureserver:0`). 0 unresolved.

### Track 2: C/E (residual parity/linkage) — 90% FAIL -> 95% PASS

Of the 4 rows flagged unresolved by the 2nd firing:
- `2025-CA-002043-F` ("2419 EDGEWATER DR"): root cause was a missing "S" directional in the source address (Okaloosa GIS requires "2419 S EDGEWATER DR"). Resolved to a single unambiguous GIS match (PIN `09-1S-22-0730-0005-0290`).
- `2025-CA-003450-C` (previously NULLed corrupted-caption row): recovered via a live re-scrape of the Bid4Assets auction *detail* page (not the grid), which itself only exposes "FL" as an address, but exposed a real defendant name (`Walker, Velma`) that GIS-matched unambiguously by owner name to `4320 COOPER LN, HOLT FL 32564`.
- `2024-CA-000470` and `2024-TDD-000089`: confirmed genuinely unresolvable this session — both are orphaned legacy stubs from `okaloosa.realforeclose.com` (a client-rendered Angular SPA with no static case data or discoverable REST endpoint); both `firecrawl-scrape` and `firecrawl-browser` returned "insufficient credits" this session. Left honestly NULL, not fabricated. Still counted in the denominator (38/40 = 95%, not excluded).

C and E both cross the 95% pass threshold cleanly (38 of 40, not a denominator trick).

### Adversarial verification (Track 1 + Track 2): both SURVIVED

Independent refuters re-ran `pencil_dod_evaluate_county` live (exact match to claims), independently re-queried the live GIS/Bid4Assets sources for spot-checked rows (5-of-5 and 2-of-2 exact byte-for-byte matches respectively), confirmed no PropertyOnion-sourced data, confirmed zone codes were a real distribution (not copy-pasted — 10 distinct codes across 38 rows), confirmed the new jurisdiction row is migration-backed not an ad-hoc INSERT, and confirmed the two genuinely-unresolved legacy rows are honestly still blank (identical placeholder values, not silently excluded from the denominator).

### G — disclosed regression: 100% PASS -> 10% FAIL -> 75.6% FAIL (still failing)

**This was not a pre-existing failure — it is a genuine side effect of the I-fix**, caught and disclosed rather than hidden. Before this session, `v_zoning_gold_standard_kpi_v3` for okaloosa only "saw" the 7 synthetic placeholder parcel_zones rows (all zone `R-1`, fully standards-complete), so G scored 100%. The 38 new real parcel_zones rows span 5 jurisdictions and ~14 distinct (jurisdiction, zone_code) pairs, most of which had no `zoning_districts`/`zone_standards` rows at all (especially the brand-new "Unincorporated Okaloosa County" jurisdiction, which had zero districts defined) — so the applicable-districts denominator grew sharply while real ordinance-sourced standards coverage did not, and G crashed to 10%.

A follow-up build track researched and backfilled real, ordinance-cited `zone_standards` values (Okaloosa County LDC chapters 2 and 6, and Destin's official GRMU/TCMU district factsheets) for 8 of the 14 gaps, moving G's `far` and `pk1000` sub-metrics to 100% and `density` from 40% to 75.6%. **G remains FAIL (needs >=95, at 75.6%)** — two genuine, disclosed open gaps:
- Unincorporated `R-1` (8 parcels) and `MU` (3 parcels) density is legitimately bifurcated in the ordinance itself (e.g. R-1: 4 du/acre north of Eglin AFB vs 5 south; MU: 25 du/acre inside the Urban Development Area Boundary vs 4 outside) — the current schema only supports one density value per (jurisdiction, zone_code), so this needs per-parcel point-in-polygon resolution against AFB/UDAB boundary layers, not attempted this session.
- Destin GRMU/TCMU `parking_per_1000sf`: the actual parking table (LDC Art. 8 Sec. 8.06.10) was unreachable this session (Municode 403, mirror 503, Firecrawl out of credits) — left NULL rather than guessed, per BLANK > WRONG.

Adversarial verification: **SURVIVED**, with one non-material flag. The refuter independently re-fetched every cited primary-source PDF/page (Okaloosa LDC chapters 2 & 6, both Destin factsheets) and confirmed every stored FAR/density number byte-for-byte against the source. No fabricated values anywhere — the 5 municipal districts (Crestview R-3, FWB R-1/R-2, Niceville R-1/R-2) missing `parking_per_1000sf` were correctly marked `pk1000_regulated=false` (an applicability exclusion, not an invented number), matching this repo's established non-fabrication precedent. One flagged weakness: the build track's own summary slightly overstated the rigor behind that `pk1000_regulated=false` call for the 3 *municipal* (non-unincorporated) districts — the migration's own inline comment is more honest that this was an inference from Florida-municipal-code convention, not a per-municipality primary-source verification. This is a citation-rigor nit on a non-numeric applicability flag, not a fabricated FAR/density/parking value, and does not affect any A-J score.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| orange/hernando/miami_dade | regression check only | Reconfirmed 10/10 on all three at session start AND close, zero changes | none |
| okaloosa I | build zoning substrate | 0%→95% PASS via real GIS discovery (county + 4 municipal zoning layers), 38/38 parcels resolved | none |
| okaloosa C/E | resolve 4 residual rows | 2 of 4 resolved (address-directional fix, owner-name recovery); 2 genuinely unresolvable this session (dead SPA source, no scrape credits) | both C and E crossed 95% anyway (38/40) |
| okaloosa G | not originally targeted | Regressed 100%→10% as a direct, disclosed side-effect of the I-fix; partially recovered to 75.6% via real ordinance research | new open item, disclosed immediately rather than hidden, not fully closed |

## Verification Evidence

6 agents across 2 sequential ultracode workflows, 286 tool calls, ~595K subagent tokens. Every build claim had an independent adversarial refuter that re-ran live queries and independently re-fetched cited external sources (GIS endpoints, Bid4Assets pages, ordinance PDFs) rather than trusting the builder's self-report — both verification passes returned SURVIVED. No PropertyOnion-sourced rows written anywhere. No fabricated address/parcel_id/zone_code/density/FAR/parking value — every written value traces to a live government GIS endpoint, a live Bid4Assets page, or a primary-source ordinance PDF/factsheet, with the source encoded in the row itself (`parity_source`/`source` columns) or cited in the migration. Cron jobs 109/111/115 and `gold-standard-loop-*` untouched. No `gold_standard_loop()`/`gold_standard_certify()` run this session (parallel-fleet protocol — other shards pushed to main during this session, handled via clean `git pull --rebase`). Commits on `main`: `51deffee` (okaloosa C/E), `0a7c9027` (okaloosa I), `bf4af1dd` (okaloosa G partial fix).

## Next-session priorities

1. **okaloosa G — density bifurcation**: Unincorporated `R-1` (8 parcels) and `MU` (3 parcels) need per-parcel resolution against the Eglin AFB encroachment boundary and Urban Development Area Boundary (UDAB) GIS layers (both likely present in the same `okgis.myokaloosa.com` Admin-Boundaries or Planning-Development service tree) to pick the correct one of two ordinance-specified density values per parcel — the schema-level (jurisdiction, zone_code) granularity is too coarse for these two codes specifically.
2. **okaloosa G — Destin parking**: LDC Art. 8 Sec. 8.06.10 parking table for GRMU/TCMU was unreachable this session (Municode 403, mirror 503, Firecrawl credits exhausted) — retry with working Firecrawl credits or find an alternate primary source (e.g. a cached/Wayback copy, or the city's own published parking-requirements PDF outside Municode).
3. **okaloosa C/E remaining 2 rows**: `2024-CA-000470` and `2024-TDD-000089` need their original data source re-identified — both are orphaned `okaloosa.realforeclose.com` (RealAuction SPA, no static/REST case data) stubs; would need working Firecrawl/browser-automation credits to drive the search form, or a different discovery route entirely (e.g. cross-reference against the Okaloosa Clerk's own case search).
4. **Citation-rigor nit (non-blocking)**: the G-fix migration's `pk1000_regulated=false` call for Crestview/FWB/Niceville rests on an inference about Florida-municipal-code convention rather than a per-municipality ordinance check — worth a dedicated verification pass if any future session touches parking standards for these 3 districts specifically.
