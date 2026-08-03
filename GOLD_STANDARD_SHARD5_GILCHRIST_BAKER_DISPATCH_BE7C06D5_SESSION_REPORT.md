# Gold Standard shard-5 (gilchrist/baker), dispatch be7c06d5-73b3-45b5-9c8f-a86ce79202bf, loop run 8415

## Summary

**baker: real forward progress on C/D/I (20.0% -> 46.7% each), still FAIL (not
certified). gilchrist: unchanged, 6th independent session confirming E/I's 6
remaining cases are structurally blocked.** Ran via the ULTRALOOP protocol
(Workflow tool, native mode): 3 parallel research/fix agents, each followed by
an independent adversarial verifier before any live write. The verifier
caught a real bug in the first-pass baker C/D fix (wrong case_number format,
would have been a silent no-op) before it shipped -- corrected and
independently re-confirmed before applying.

## Live verification — before and after

```json
BAKER
BEFORE: C=20.0 (matched_clean=3/15) | D=20.0 (matched_any=3/15) | E=46.7 (parcel_linked=7/15) | I=20.0 (card_complete=3/15)
AFTER:  C=46.7 (matched_clean=7/15) | D=46.7 (matched_any=7/15) | E=46.7 (parcel_linked=7/15, unchanged) | I=46.7 (card_complete=7/15)
Still 6/10 overall (A,B,F,G,H,J pass; C,D,E,I fail). G incidentally improved
from "density=<blank>" to "density=100.0" (new AG 7.5 district populated a
previously-N/A metric) -- G remains PASS, no regression.

GILCHRIST
BEFORE: E=57.1 (parcel_linked=8/14) | I=57.1 (card_complete=8/14)
AFTER:  E=57.1 (parcel_linked=8/14, unchanged) | I=57.1 (card_complete=8/14, unchanged)
Still 8/10 (E,I fail). Zero writes -- correctly re-confirmed BLOCKED.
```

### SQL VERIFICATION
```sql
SELECT public.pencil_dod_evaluate_county('baker');
-- C: {"pass": false, "detail": "matched_clean=7", "metric": 46.7}
-- D: {"pass": false, "detail": "matched_any=7", "metric": 46.7}
-- I: {"pass": false, "detail": "card_complete=7 of 15", "metric": 46.7}
-- E: {"pass": false, "detail": "parcel_linked=7", "metric": 46.7} (unchanged)
-- Timestamp: 2026-08-03T08:20Z UTC (live REST re-query, this session)

SELECT public.pencil_dod_evaluate_county('gilchrist');
-- E: {"pass": false, "detail": "parcel_linked=8", "metric": 57.1} (unchanged)
-- I: {"pass": false, "detail": "card_complete=8 of 14", "metric": 57.1} (unchanged)
-- Timestamp: 2026-08-03T08:20Z UTC
```

## What was done

### 1. Baker C/D/I — new lever found via fresh live data check

Live DB state showed 2 baker cases (`022026CA000018CAAXMX`, `022025CA000148CAAXMX`)
had already been enriched with full parcel_id/address/geo/assessed_value by
the ordinary scraping pipeline sometime between the last session (2026-07-30)
and now — but neither `parity_status` nor a `parcel_zones` row had ever been
set for them. Prior baker sessions (5+) all focused on the *other* 4 cases
(still genuinely blocked, see below) and never flagged this gap.

**C/D fix**: independently confirmed via Baker County's own ArcGIS
`parcels_web2` FeatureServer (`services6.arcgis.com/HSWu3dhzHf7nZfIa/.../parcels_web2`
— the same authority backing bakerpa.com, which returned HTTP 521 at check
time) that PARCELNO/address/assessed_value match our DB exactly for both
cases. Set `parity_status='matched_clean'`, `parity_source='tier1_baker_realforeclose_bakerpa_v1:baker:20260803_cdgap'`.

**Caught by adversarial verification**: the first-pass proposed SQL used
`case_number = '022026CA000018'` / `'022025CA000148'` — missing the real
stored `CAAXMX` suffix. The refuter independently queried live
`multi_county_auctions` and proved this WHERE clause matches zero rows (a
silent no-op that would have shipped as a false "fixed" claim despite a
`VERIFIED` confidence label on the underlying data match). Corrected to the
real case_number values (`...CAAXMX`), re-confirmed against the live table
before executing. This is exactly the class of failure the ULTRALOOP
adversarial-verify step exists to catch.

**I fix**: both parcels were missing from `parcel_zones` entirely. Baker
County had no "Unincorporated Baker County" jurisdiction row (only Macclenny
id=920, Glen St. Mary id=982) despite 20+ other FL counties having one.
Created it (id=1664), registered zone code `AG 7.5` as a real
`zoning_districts` row (confirmed as a common code — 3553 parcels — in
Baker's live ArcGIS layer, not fabricated) with numeric standards sourced
verbatim from Baker County Code of Ordinances Sec. 24-191 (via
Zoneomics-hosted municode text; library.municode.com itself 403'd), and added
`parcel_zones` rows for both parcels (AG 7.5 for the unincorporated parcel,
`CITY` for the Macclenny parcel using the existing delegation-marker pattern
under jurisdiction_id=920). Fully survived independent adversarial
verification (field-for-field re-fetch of the ArcGIS layer and the ordinance
text).

### 2. Baker E + Gilchrist E/I — fresh recheck, new angle tried, still BLOCKED

The other 4 baker cases (`022025CA000108CAAXMX`, `022025CA000117CAAXMX`,
`022025CA000124CAAXMX`, `022026CA000007CAAXMX`) and all 6 gilchrist cases
(`212025CA000033/036/043/064/070CAAXMX`, `212026CA000004CAAXMX`) were
re-checked live. Rather than repeat the exhaustively-documented dead ends
(RealForeclose placeholder-only parcel links, qpublic/gilchristclerk/bakerclerk
403s, Civitek OCRS Turnstile gate with no case-number search field, Firecrawl
credit exhaustion), one genuinely new angle was tried: Florida-mandated legal
notice publication (`floridapublicnotices.com` and county newspaper-of-record
search). A control check proved the method works (an unrelated Gilchrist
case notice was found and indexed there), but **zero hits for any of the 10
target cases** — they are simply not yet published/indexed given several
sale dates are 1-3 months out. No data fabricated; BLANK correctly reported.

## Verification protocol compliance

- Ran `pencil_dod_evaluate_county` before and after for both counties, pasted
  above.
- 6 rows logged to `gold_standard_ultraloop_audit` (dispatch_id
  `be7c06d5-73b3-45b5-9c8f-a86ce79202bf`): baker C (survived=true), baker D
  (survived=true), baker I (survived=true), baker E (survived=false, BLOCKED),
  gilchrist E (survived=false, BLOCKED), gilchrist I (survived=false, BLOCKED).
- `gold_standard_loop()`/`gold_standard_certify()` intentionally **not** run
  per PARALLEL-FLEET RULES (other shards may be mid-flight).
- Session close-out written to `gold_standard_campaign` (dispatch_id above):
  `criteria_passed` per-county A-J booleans, `exit_reason='timeout'`,
  `session_end_at` set.
- Zero fabrication: every written value traces to a live-fetched, cited
  source (Baker ArcGIS FeatureServer, Zoneomics-hosted ordinance text); every
  BLOCKED case remains genuinely NULL, re-confirmed via direct DB re-query.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
