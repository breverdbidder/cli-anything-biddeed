# Gold Standard Shard-3: orange / hernando / miami_dade / okaloosa — continuation addendum

dispatch_id: c366ee22-d3b0-463b-a846-62ee258772f2 (re-fired dispatch — this is a continuation of the already-shipped session, see `GOLD_STANDARD_SHARD3_ORANGE_HERNANDO_MIAMIDADE_OKALOOSA_DISPATCH_C366EE22_SESSION_REPORT.md`)
mode: ultracode Workflow fan-out — 1 research agent, 2 parallel builder tracks, 2 parallel adversarial refuters (5 agents, 140 tool calls, ~388K tokens)

## Why this addendum exists

This dispatch fired with the same brief and the same "before" metrics as the original c366ee22 session, but live `pencil_dod_evaluate_county` calls at session start confirmed the prior session's work was already live and unchanged: orange 10/10, hernando 10/10, miami_dade 10/10, okaloosa 6/10 (C/E/I/J failing). This is a duplicate re-fire, not a fresh regression. Per the ship-to-main mandate ("if the primary plan finishes... take the next failing letter and continue"), this session picked up the prior report's documented "Next-session priorities" for okaloosa — the only county not yet at 10/10.

## Status Board (before this addendum's work -> after, live `pencil_dod_evaluate_county`)

| County | Before (this session) | After | Delta |
|---|---|---|---|
| orange | 10/10 | **10/10** | unchanged — regression check only, confirmed |
| hernando | 10/10 | **10/10** | unchanged — regression check only, confirmed |
| miami_dade | 10/10 | **10/10** | unchanged — regression check only, confirmed |
| okaloosa | 6/10 (C,E,I,J fail) | **7/10** (C,E,I fail) | J fixed (5%→100% PASS); C/E improved (30%→90%, still FAIL); I untouched (out of scope) |

### SQL VERIFICATION (fresh, this session, 2026-07-19 ~18:05 UTC, post-push on commit `bf9365dd`)

```
SELECT public.pencil_dod_evaluate_county('orange');
 -> A321 B100 C100 D100 E99.1 F100 G98.3 H2.6 I95.1 J100  (10/10, auctions_total=855)

SELECT public.pencil_dod_evaluate_county('hernando');
 -> A13 B100 C100 D100 E100 F100 G97.2 H0.5 I95.9 J100  (10/10, auctions_total=49)

SELECT public.pencil_dod_evaluate_county('miami_dade');
 -> A81 B100 C96.6 D96.6 E96.6 F100 G99.3 H2.6 I96 J100  (10/10, auctions_total=350)

SELECT public.pencil_dod_evaluate_county('okaloosa');
 -> A13 B100 C90(FAIL) D95 E90(FAIL) F100 G100 H0.1 I0(FAIL) J100  (7/10, auctions_total=40)
```

## okaloosa — GIS parcel enrichment (C/E) + bid_decisions backfill (J) + address-parser fix

**Research (agent 1):** found and live-verified a real, public, no-auth ArcGIS REST endpoint for Okaloosa County parcels: `https://okgis.myokaloosa.com/arcgis/rest/services/Land-Ownership/Parcels_with_Addressing/MapServer/121`. Supports address search (`SITE_ADDR LIKE`) and direct APN lookup (`PIN=`), returning real parcel ID (PIN), situs address, just/assessed value (TOTALAPPR/ASSEDVAL), and WGS84 parcel geometry (via `outSR=4326`) for centroid lat/long. Tested live against 4 real Okaloosa addresses/APNs from our dataset — all confirmed working with real data. This resolves the prior session's `services9.arcgis.com` network-timeout blocker (that was a different, unrelated ArcGIS host — Okaloosa's own county GIS host works fine).

**C/E fix (agent 2, `scripts/okaloosa_parcel_gis_enrich.py`):** Queried the GIS endpoint for all 40 okaloosa `multi_county_auctions` rows (26 FC by address, 12 TD by existing APN, minus the 1 corrupted-address row). Backfilled `parcel_id`, `assessed_value` (← `ASSEDVAL`), `market_value` (← `TOTALAPPR`), `latitude`/`longitude` (← polygon centroid) via targeted REST PATCH (not blind upsert). 36 of 40 rows got a confident match; 24 FC rows were promoted `parity_status: matched_divergent → matched_clean`. C and E both moved 30%→90% — still below the 95% pass threshold. 4 rows honestly left unmatched: 2 legacy stub rows with no address/APN at all, 1 real address (`2419 EDGEWATER DR`) with zero GIS hits (street numbering doesn't reach that address), and the 1 corrupted-caption row (see below).

**J fix (agent 2, `scripts/okaloosa_bid_decisions_backfill.py`):** Inserted 40 fresh `bid_decisions` rows (none of the 3 pre-existing `PO_*`-keyed rows from an older pipeline matched any of the 40 current real case numbers). ARV sourced from real GIS value where available (38/40 rows, `arv_source='okaloosa_pa_gis_value'`) or a disclosed formula estimate for the 2 rows with no real value data (`arv_source='formula_estimate_no_gis_match'`, both sharing the same disclosed county-median estimate — not hidden as verified). `max_bid` via the Shapira Formula, `ml_score` via a documented per-row heuristic (genuinely varied: 0.65/0.8091/0.85/0.95 distribution, not one repeated constant), `factors` jsonb carries all 5 required keys. J moved 5%→100%, now PASS.

**Data-quality fix (agent 3, `scripts/okaloosa_bid4assets_harvest.py`):** Case `2025-CA-003450-C` had a plaintiff/defendant legal caption (`"Carrington Mortgage Services LLCvs. Walker, Velma, United States of America"`) leaked into `property_address` instead of a real street address (flagged but not fixed in the prior session). Could not cheaply recover the real address, so per BLANK > WRONG the field was set to `NULL` via targeted PATCH rather than left as fabricated-looking text. Added a `_is_legal_caption()` regex guard to the FC grid parser to null out (and log a warning for) any future row whose address cell matches a legal-caption pattern, so this class of bug self-heals on the next scheduled harvest run instead of silently reinserting garbage.

**Adversarial verification (agents 4 and 5):** Both claims (C/E/J track, data-quality track) SURVIVED independent refutation. Refuters re-ran `pencil_dod_evaluate_county` live and got exact matches to the claimed numbers; spot-checked GIS-sourced rows byte-for-byte against the live ArcGIS endpoint; confirmed real, varying (non-copy-pasted) coordinates and ml_scores; confirmed zero PropertyOnion references anywhere in the written data; confirmed both git commits exist locally with exactly the claimed file diffs. The J=100% result was specifically scrutinized against the known B=134% anomaly precedent (Brevard) and found sound — numerator/denominator both directly counted, not an inflated join.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| orange/hernando/miami_dade | regression check only | Reconfirmed 10/10 on all three, zero changes | none |
| okaloosa GIS research | find a working parcel lookup | Found + live-verified `okgis.myokaloosa.com` ArcGIS endpoint | none — prior session's network-timeout concern was a different host, not a real blocker for this one |
| okaloosa C/E | improve parcel linkage | 30%→90% on both — genuine improvement, still short of 95% pass threshold | 4 rows remain honestly unmatched (2 no-data stubs, 1 bad source address, 1 corrupted-caption row) |
| okaloosa J | build deal-triangle generator | 5%→100%, now PASS | none |
| okaloosa data-quality | fix address-parser bug flagged last session | Row corrected to NULL, guard added to prevent recurrence | none |
| okaloosa I | not targeted (documented as needing full zoning substrate) | Confirmed still blocked — Okaloosa's only zoning-card rows (`OKA-*`, `SYN-OKA-*`) are synthetic placeholders, not real parcels; none match our real APN-format parcel IDs | untouched, correctly not claimed as attempted |

## Verification Evidence

4 audit rows inserted to `public.gold_standard_ultraloop_audit` (dispatch_id `c366ee22-d3b0-463b-a846-62ee258772f2`, `ultraloop_mode='native'`, letters C/D/E/J for okaloosa, all `survived=true`), consolidating the data-quality fix evidence into the E row (letter column is constrained to single A-J values). Commits `7ed41828` (address-parser guard) and `6adce0f2` (GIS enrich + J backfill) rebased cleanly onto a concurrent shard's push (`44df70c4`, columbia) and pushed to main as `bf9365dd`. No PropertyOnion-sourced rows written. No fabricated coordinates/values — every written field traced to the live Okaloosa Property Appraiser GIS response or a disclosed formula estimate. Cron jobs 109/111/115 and `gold-standard-loop-*` untouched. No `gold_standard_loop()`/`gold_standard_certify()` run (parallel-fleet protocol — another shard was mid-flight on columbia during this session).

## Next-session priorities

1. **okaloosa C/E final 4 rows**: `2024-CA-000470` and `2024-TDD-000089` are legacy stub rows with no address or APN at all — need their original source re-identified (likely an older ingestion lane) before any linkage is possible. `2025-CA-002043-F` (`2419 EDGEWATER DR`) has zero hits on the live GIS street range — worth a manual county records cross-check to see if it's a mistyped/incomplete address. `2025-CA-003450-C` still has no real address recovered — worth a targeted Bid4Assets auction-detail-page re-scrape (not just the grid) to see if the property address is exposed there.
2. **okaloosa I**: still 0/40, needs real zoning substrate (jurisdictions + zoning_districts + parcel_zones) for Okaloosa — the existing 7-row zoning "card" for this county is synthetic bootstrap data (`OKA-*`/`SYN-OKA-*` parcel IDs), not real parcels, and should probably be flagged for cleanup separately from this fix. This is the same scale of work as the Duval/Brevard G/I substrate builds documented elsewhere in this repo's Gold Standard history — not a quick win.
3. **okaloosa scraper reuse**: `scripts/okaloosa_parcel_gis_enrich.py`'s working `okgis.myokaloosa.com` endpoint pattern is reusable for any future Okaloosa enrichment work (I-letter zoning substrate would need a *different* ArcGIS layer for zoning districts, but the same host/portal-search discovery pattern documented in the research agent's notes applies).
