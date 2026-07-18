# Gold Standard Shard-12: okeechobee, st_johns — session report

dispatch_id: 704e70a0-6459-4599-af5b-c2f31351913e
loop run: 4870 (continuation)
mode: ULTRALOOP fallback (manual Workflow fan-out — 5 parallel research/fix agents + 1 sequential
J-generator + 6 independent adversarial verifiers, all SURVIVED)

## Scoreboard (live, `pencil_dod_evaluate_county`, pasted verbatim)

### okeechobee: 8/10 -> 8/10 (G, I letters both moved substantially, neither crossed 95%)

Before (from dispatch brief, re-confirmed live at session start):
```json
{"A":10,"B":100.0,"C":100.0,"D":100.0,"E":96.3,"F":100.0,"G":0.0,"H":1.0,"I":40.7,"J":100.0}
```

After (live, this session, final):
```json
{
  "A": {"pass": true, "metric": 10, "detail": "fc=44 td=10"},
  "B": {"pass": true, "metric": 100.0, "detail": "verified=6 closed_sold=6"},
  "C": {"pass": true, "metric": 100.0, "detail": "matched_clean=54"},
  "D": {"pass": true, "metric": 100.0, "detail": "matched_any=54"},
  "E": {"pass": true, "metric": 96.3, "detail": "parcel_linked=52"},
  "F": {"pass": true, "metric": 100.0, "detail": "tier1_sold=6 closed_sold=6"},
  "G": {"pass": false, "metric": 39.1, "detail": "density=39.1 far=100.0 pk1000=50.0"},
  "H": {"pass": true, "metric": 6.7, "detail": "hours since last_seen (SLA 48h)"},
  "I": {"pass": false, "metric": 87.0, "detail": "card_complete=47 of 54"},
  "J": {"pass": true, "metric": 100.0, "detail": "deal_complete=54"}
}
```

### st_johns: 5/10 -> 9/10

Before (from dispatch brief, re-confirmed live at session start):
```json
{"A":3,"B":100.0,"C":82.2,"D":82.2,"E":88.9,"F":100.0,"G":100.0,"H":1.0,"I":73.3,"J":82.2}
```

After (live, this session, final):
```json
{
  "A": {"pass": true, "metric": 3, "detail": "fc=42 td=3"},
  "B": {"pass": true, "metric": 100.0, "detail": "verified=1 closed_sold=1"},
  "C": {"pass": true, "metric": 95.6, "detail": "matched_clean=43"},
  "D": {"pass": true, "metric": 95.6, "detail": "matched_any=43"},
  "E": {"pass": true, "metric": 97.8, "detail": "parcel_linked=44"},
  "F": {"pass": true, "metric": 100.0, "detail": "tier1_sold=1 closed_sold=1"},
  "G": {"pass": true, "metric": 100.0, "detail": "density=100.0 far=100.0 pk1000="},
  "H": {"pass": true, "metric": 0.4, "detail": "hours since last_seen (SLA 48h)"},
  "I": {"pass": false, "metric": 73.3, "detail": "card_complete=33 of 45"},
  "J": {"pass": true, "metric": 97.8, "detail": "deal_complete=44"}
}
```

Only letter I remains for st_johns to reach 10/10.

## What shipped (all adversarially SURVIVED by an independent verifier agent per ULTRALOOP)

1. **Fabrication purge (okeechobee)** — deleted 2 `parcel_zones` rows with synthetic
   `OKE-SYN-<case_number>` parcel IDs (source `shard4_run1456/okeechobee_parity_fix`, self-labeled
   "Agricultural (Okeechobee Synthetic)"). Confirmed fabricated linkage from a prior session, no FK
   dependents, safe delete.
2. **Scraper-bug purge (okeechobee)** — deleted 31 of 37 `zoning_districts` rows for jurisdiction
   943 that were actually Municode table-of-contents chapters ("Chapter 18 - CODE ENFORCEMENT",
   "APPENDIX F - MURALS...") misfiled as zoning districts, permanently deflating G's denominator.
   6 real zoning codes remain (AG, A, C, PD, RSF, RMH).
3. **Okeechobee G — Commercial + PD** (commit `4c1fbd9c`/`2f49d2af`): real Sec. 2.01.05.C FAR table
   + Sec. 7.04.02.F parking schedule values for Commercial (max_far=2.0, parking_per_1000sf=4.0);
   `far_regulated=false` override for PD after confirming via Sec. 2.04.17 that PD is genuinely
   negotiated per-project (no fixed ratio), matching the Seminole PUD-MO precedent. far 0%->100%,
   pk1000 0%->50% (residual: PD's parking still miscounts applicable — no override column exists
   for `pk1000_applicable` in the shared view; flagged, not worked around, out of this shard's scope
   since it's shared-view DDL affecting all counties).
4. **Okeechobee G — RSF/RMH density: BLOCKED, correctly not fabricated.** Real ordinance text
   (Sec. 2.04.02/2.04.05) confirms RSF/RMH density is governed by Future Land Use category (which
   varies per parcel, 1/10 acre to 18/acre), not a fixed per-zoning-code value — there is no single
   honest number to write into a one-row-per-district table. No write made.
5. **Okeechobee I — spatial zone assignment**: 25 of 29 unlinked auction parcels resolved via real
   GIS point-in-polygon (pixel-sampling `okeechobeegis.com`'s WMS tiles against each parcel's real
   surveyed boundary, since GetFeatureInfo is disabled server-side). Also caught and avoided a
   ghost-success trap: 27 of 29 worklist rows shared an identical placeholder lat/long
   (27.3815/-80.8984) traced to an earlier commit (`e1b419c4`) — these were not used. `parcel_zones`
   23->48 rows. card_complete 22/54 (40.7%) -> 47/54 (87.0%). Remaining 7-row gap: 4 parcels
   genuinely outside the county GIS zoning layer's coverage (inside city limits), 2 with no
   parcel_id at all, 1 multi-parcel case.
6. **St. Johns E/I — parcel linkage**: 4 of 5 unlinked auctions resolved to real parcel IDs via the
   St. Johns County GIS ArcGIS parcel layer and, for one stub case (CA26-0499) with no address on
   file at all, by reading the actual recorded Final Judgment PDF and cross-matching owner name +
   legal description. 1 case (CA26-0218) correctly left BLOCKED — the clerk's case-search is
   CAPTCHA-gated and no Final Judgment has been recorded yet. E: 88.9%->97.8% (PASS).
7. **St. Johns C/D — parity reconciliation**: 6 of 8 gap cases (which had `matched_clean`/
   `matched_divergent` status with zero evidence trail — no source, no confidence, no PO id)
   independently re-verified against the St. Johns GIS parcel layer and retagged
   `parity_source='tier1_official_records_v1'` per the standing supplementary-litmus authorization.
   2 cases left untouched (still no resolvable property data). C/D: 82.2%->95.6% (PASS).
8. **St. Johns J — bid_decisions backfill**: 7 of 8 gap cases had real underlying data
   (opening_bid) and got a real deal-thesis row via the existing Shapira-formula convention
   (`scripts/stjohns_j_backfill_run_letterJ_20260718.py`, matches the established
   `stjohns_j_backfill_20260710.py` pattern). 1 case (CA26-0218) has zero real property data and
   was deliberately NOT given a bid recommendation. J: 82.2%->97.8% (PASS).

## Adversarial verification summary

All 6 fix claims independently re-verified fresh against the live DB by a separate agent per
claim (never the agent that made the fix), per the ULTRALOOP protocol. **All 6 SURVIVED.** Two
minor documentation-accuracy notes were flagged (not fabrication): the ok-commercial-pd commit
message's "before" density figure was stale (cited 9.5, live figure at time of the commit was
already 39.1 due to a same-day unrelated commit landing first — the underlying DB fix itself is
real and correctly applied); and one evidence file for sj-parcels was over-cited for a case it
didn't actually contain (the GIS-based match for that case stands independently regardless).

## Residual gaps (honestly unresolved, not certified)

- **okeechobee G (39.1%)**: RSF/RMH density genuinely has no fixed value per current schema (FLU-
  varies-by-parcel structural gap); PD parking miscounts due to a shared-view formula gap with no
  override column (cross-county blast radius, out of shard scope).
- **okeechobee I (87.0%)**: 4 parcels inside city limits with no county GIS zoning coverage, 2 with
  no parcel_id, 1 multi-parcel case.
- **st_johns I (73.3%)**: not directly worked this session (E/C/D/J fixes did not by themselves
  clear the card-completeness join — the 4 newly-linked parcels still lack a zoning gold-standard
  card row and a real assessed/market value; St. Johns Property Appraiser blocks curl/WebFetch with
  Cloudflare 403). **This is the single remaining letter for st_johns to reach 10/10** — next
  session should prioritize it: (a) real assessed/market value for the 4 newly-linked St. Johns
  parcels (sjcpa.gov CAMA data, Cloudflare-blocked — may need Playwright/Firecrawl), (b) zoning
  district/parcel_zones coverage for those same parcel IDs.
- **st_johns 2 stub cases** (CA26-0499 fully resolved this session; CA26-0218 remains genuinely
  blocked pending either a recorded Final Judgment or a non-CAPTCHA lookup path).

No certification run (`gold_standard_certify`) was executed — neither county reached 10/10, so
certification does not apply this session. `gold_standard_loop()` was not run (other shards were
mid-flight per parallel-fleet rules); per-county `pencil_dod_evaluate_county` was used throughout
for verification, both by the fix agents and independently by the verifier agents.
