# Gold Standard Shard-1 — clay / brevard / lee / pinellas
Dispatch `f763205f-867d-483e-8efb-da32165dd254` · chat_session `architect-20260731T080000` · 2026-07-31

## Method
ULTRALOOP native workflow (Workflow tool, 8 subagents: 4 fix + 4 independent adversarial verify), each fix backed by live-DB diagnosis done up front so agents executed pre-verified SQL/lookups instead of re-deriving. Every claim got an independent refuter that ran its own fresh `pencil_dod_evaluate_county()` query and logged to `gold_standard_ultraloop_audit`.

## Scoreboard — before → after (live, pasted verbatim)

### clay — 10/10 → 10/10 (no data changed; audit-freshness only)
No letter was failing. The certify gate was at risk: audit rows for A,B,E,F,G,H were 10.5 days stale and C,D,I were 7.65 days stale (both past the 7-day certify window); only J was fresh. Re-ran `pencil_dod_evaluate_county('clay')` fresh — all 10 letters still `pass=true`, zero regression (A=75 B=100 C=96.8 D=96.8 E=99.4 F=100 G=97.8 H=0.1 I=96.8 J=98.1). Inserted 9 fresh `survived=true` audit rows (A–I) sourced from this session's live read; refuter independently re-ran the same query, spot-checked the B ratio (11 sold rows → 11 non-promoted `tax_deed_outcomes` rows, clean 100%, not the B>100% anomaly pattern) and confirmed 3 case numbers directly. **Certify-eligibility restored.**

### brevard — 9/10 → 9/10 net (one ghost-success caught and reverted)
Only I was failing (card_complete=5670 of 7221, 78.5%). Diagnosed a real, verified crosswalk: `multi_county_auctions.parcel_id` (BCPAO account) = `parcel_zones.tax_account`, `parcel_zones.parcel_id` (STRAP) = `sample_properties.parcel_id` (co_no=5) — 1261 rows were purely missing `property_address` with lat/lon/value/zone-link already present. Ran the additive UPDATE (1261 rows). **The adversarial refuter caught it as a ghost-success**: `sample_properties.address` itself held literal placeholder strings (`'UNKNOWN'` ×1260, `'CONFIDENTIAL'` ×1) for exactly these rows — the join was mechanically correct but the source field was never populated with real data. `survived=false` logged. **I reverted the UPDATE immediately** (1261 rows back to `property_address=NULL`) and re-verified live:
```
I: pass=false, card_complete=5670 of 7221, metric=78.5   (identical to pre-session state)
A/B/C/D/E/F/G/H/J: unchanged, still pass=true
```
Net effect: zero change, no fabricated data left in the DB. Logged a follow-up audit row documenting the revert. **I remains genuinely unresolved — residual for a future session**: `sample_properties` is not a reliable address source for the ~1481 brevard rows still missing address; a real fix needs either a different BCPAO field/table or a live re-scrape, not this crosswalk.

### pinellas — 7/10 → **9/10** (C and D flipped to PASS, verified)
```
before: C matched_clean=379/406=93.3% FAIL | D matched_any=379/406=93.3% FAIL
after:  C matched_clean=390/406=96.1% PASS | D matched_any=390/406=96.1% PASS
```
Root cause: 27 freshly-scraped rows had `parity_status IS NULL` (parity job hadn't reached them yet, not a matcher defect). Matched 11 of them against the independent `realforeclose_aids` litmus table (county_slug='pinellas', 697 rows) via exact normalized-case-number equality — mirrors the existing `scripts/shard2_seminole_cd_parity_backfill.py` pattern, parameterized to pinellas. Stamped `parity_status='matched_clean'`, `parity_source='tier1_realforeclose_pinellas'` (verified to start with `'tier1'`, satisfying the evaluator's `LIKE 'tier1%'` requirement — a prior 2026-06-26 pinellas migration used `parity_source='clerk_official_court_format'`, which does **not** match and never counted; this fix avoided repeating that). Refuter independently re-ran the DoD query, confirmed the exact +11 delta, confirmed parity_source tagging, and spot-checked 3 full-format case numbers against realforeclose_aids. **survived=true.** I remains FAIL (92.4%, out of scope this session, untouched).

### lee — 8/10 → 8/10 net (5 genuine parcel links written, but only +1 counted toward E)
```
before: E parcel_linked=301/322=93.5% FAIL | I card_complete=282/322=87.6% FAIL
after:  E parcel_linked=302/322=93.8% FAIL | I card_complete=282/322=87.6% FAIL (unchanged)
```
Lee has zero FL-GIO/`sample_properties` ingestion (co_no=36), so no internal crosswalk exists — this required real external lookups. Standard WebFetch against leepa.org's ASP.NET search form doesn't work (requires postback/viewstate); the agent found and used Lee County Property Appraiser's own ArcGIS REST layer (`gissvr.leepa.org/gissvr/rest/services/ParcelsWFS/MapServer/0`) directly. Of 9 addressed candidate rows: **5 confirmed** (STRAP + owner name cross-checked, one case where an incorrect STRAP from a third-party site was correctly rejected in favor of the authoritative GIS value), 4 genuinely not found/ambiguous (skipped, not guessed — one is an unaddressed condo unit, one address string not in the parcel fabric, etc.). All 5 written links are real and independently re-verified by the refuter against the same GIS source. The metric only moved +1 because 4 of the 5 fall outside the DoD's scoped denominator (`data_source='propertyonion' AND tier1_authoritative=false`). **survived=true** — genuine work, honestly still short of the 95% bar (need 306, at 302).

## Ultraloop audit ledger (dispatch f763205f)
| county | letter | survived | note |
|---|---|---|---|
| clay | A–I (9 rows) | true | audit-freshness refresh |
| brevard | I | **false** | ghost-success (placeholder addresses), reverted live |
| brevard | I (revert confirmation) | false | documents the revert + zero-net-change re-verify |
| pinellas | C | true | +11 tier1-tagged matches, verified |
| lee | E | true | 5 genuine GIS-verified parcel links, verified |

## Residuals for next session
- **brevard I**: still 78.5%, needs ~1190 more card-complete rows. `sample_properties.address` is unreliable (placeholder-filled) for the remaining gap — do not reuse this crosswalk for address; needs a different source.
- **lee E/I**: still 93.8%/87.6%. 4 more addressed candidates exist but were genuinely unresolvable this pass (ambiguous condo unit, address not in GIS fabric). Would need either fresh case-docket research for the 12 no-address rows, or a retry against leepa.org's search form via a headless-browser flow (ASP.NET postback) instead of REST probing.
- **pinellas I**: untouched, still 92.4% FAIL — next highest-leverage pinellas letter.

## Verification protocol compliance
Per-county `pencil_dod_evaluate_county()` before/after JSON pasted above for all 4 counties, all sourced from fresh live queries (not reused/estimated). No `gold_standard_loop()`/`gold_standard_certify()` run this session — cannot confirm no other shard is mid-flight, so per the parallel-fleet rule this report stops at per-county evaluation.
