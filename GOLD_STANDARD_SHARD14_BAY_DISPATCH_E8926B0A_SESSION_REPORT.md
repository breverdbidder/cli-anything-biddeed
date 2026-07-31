# GOLD STANDARD shard-14 (bay) — dispatch e8926b0a-9997-471b-82f3-00a092c1eb19

Session: architect-20260731T080000. Assigned shard: bay only (7/10 at dispatch: A,B,E,F,G,H,J PASS; C,D,I FAIL).

## Result: bay is 10/10 live (pencil_dod_evaluate_county), all three targeted letters flipped to PASS, zero regression on the other 7.

## BEFORE (dispatch brief, re-confirmed live at session start)
```
A PASS 64          B PASS 100.0        C FAIL 93.2 (matched_clean=178)
D FAIL 93.2 (matched_any=178)          E PASS 98.4         F PASS 100.0
G PASS 97.0                            H PASS 0.1           I FAIL 94.2 (card_complete=180 of 191)
J PASS 100.0
```

## AFTER (live, adversarially re-verified)
```
A PASS 64          B PASS 100.0        C PASS 100.0 (matched_clean=191)
D PASS 100.0 (matched_any=191)         E PASS 98.4          F PASS 100.0
G PASS 97.0                            H PASS 0.1            I PASS 97.4 (card_complete=186 of 191)
J PASS 100.0
```

## C/D — root cause and fix
All 13 failing rows were upcoming tax-deed cases for auction_date=2026-09-01, the one calendar date the existing per-date AJAX harvest cadence hadn't reached yet (last harvested date was 2026-08-25). Ran the existing, proven `scripts/shard9_run6046_bay_cd_future_harvest.py` against `bay.realtaxdeed.com` for that single date — 13/13 calendar items matched by case_number, `parity_status='matched_clean'`, `parity_source='tier1:shard9_run6046_bay_ajax_harvest:tax_deed:2026-09-01'`. No new script written; existing tooling was simply pointed at the one unharvested date.

## I — root cause and fix
11 failing rows, broken into three buckets:
1. **7 tax-deed rows** with real addresses/parcel_ids but missing lat/long and/or zoning link. Ran the existing, proven `scripts/gold_standard_shard9_bay_run6253_i_fix.py` (gis.baycountyfl.gov TEST_Parcels + Land_Use_Planning MapServer, live). Result: 6/6 geocoded (lat/long backfilled from real parcel polygon centroids), 5/6 got a real `parcel_zones` row from the same GIS source. Case 2026-4014TD (402 Magnolia St, parcel 25539-020-000) returned `Zoning=See FLU` with an ambiguous jurisdiction — left incomplete, BLANK > WRONG.
2. **1 tax-deed row** (case 2026-0831TD, 202 3rd St, Mexico Beach, parcel `04875-080-0000`) already had full address/geo/value but was zoning-unlinked. Root cause: a prior 2026-07-29 bay session had already GIS-verified the real zoning (RG, Mexico Beach) and written it to `parcel_zones` — but keyed to the *correct* parcel_id spelling (`04875-080-000`, no trailing zero) while `multi_county_auctions` carries the county's own malformed extra-zero spelling (`04875-080-0000`), so the join never matched. First attempt: patched `multi_county_auctions.parcel_id` to the correct spelling. **This was caught and refuted live by an independent ULTRALOOP verifier** — a live bay scraper cron re-touched that exact row at 2026-07-31T08:25:00Z and reverted the patch, silently dropping I back to 185/191 (96.9%). Corrected fix: instead of fighting the recurring scraper, inserted a second `parcel_zones` row aliasing the scraper-persistent malformed spelling to the same real, GIS-sourced `zone_code=RG` — the join is now spelling-invariant regardless of which form the scraper writes on future cycles. Re-verified independently by a second agent (not the fixer, per protocol): confirmed durable, no double-counting in `v_zoning_gold_standard_kpi_v3` (G unchanged), zero regression on A-J.
3. **4 foreclosure rows** (23001239CA, 25000412CA, 25001176CA, 26000161CA) — already exhaustively researched in a prior session (`scripts/gold_standard_shard4_bay_i_tail_case_clerk_ocr_fix.py`, 2026-07-23 clerk-record OCR of the recorded judgments): metes-and-bounds tracts or timeshare fractional-interest unit-weeks with no assessable street address or standalone parcel per the county's own recorded judgment. Genuinely blocked, not re-investigated this session (settled/exhausted per prior evidence).

Remaining I gap (191-186=5): case 2026-4014TD (ambiguous zoning) + the 4 structurally-blocked foreclosure cases above.

## ULTRALOOP adversarial verification
4 rows logged to `gold_standard_ultraloop_audit` (dispatch_id e8926b0a-9997-471b-82f3-00a092c1eb19, mode=fallback — manual Task fan-out, `/effort ultracode` not available this session):
- C: survived=true — independent re-harvest of the live 2026-09-01 calendar produced a byte-for-byte identical 13-case set.
- D: survived=true — matched_divergent=0, no duplicate parcel_id/coordinate fabrication signature.
- I (original claim): **survived=false** — caught the scraper-clobber described above before it was reported as shipped.
- I (corrected claim): survived=true — independent second verifier confirmed the alias fix live, durable, no regression.

This is the exact failure mode ULTRALOOP exists to catch: a technically-correct one-time DB patch that a live, frequently-firing scraper (H freshness = 0.1h, i.e. scraped within the last several minutes) silently reverts. Flagging for future bay/other-county sessions: **any one-off patch to a column a scraper actively owns (parcel_id, address, etc.) should be treated as non-durable unless verified to survive at least one subsequent scrape cycle, or fixed on the stable side of the join instead.**

## Verification protocol
```sql
SELECT public.pencil_dod_evaluate_county('bay');
```
Live output pasted above (AFTER block), re-run after the corrected I fix and independently re-confirmed by a separate verifier agent.

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were **not** run this session (other shards' sessions may be mid-flight concurrently) — `gold_standard_scoreboard` still reflects the prior 07:30Z loop run (7/10) as of this writing and will pick up bay's 10/10 on the next scheduled loop. Certification requires two consecutive 10/10 daily 07:30Z runs plus fresh (≤7-day) survived=true ultraloop_audit rows for all 10 letters — this session supplies fresh rows for C/D/I; the other 7 letters' most recent survived=true rows (if any) should be checked for staleness before certification is claimed.

## No regressions
A/B/E/F/G/H/J metrics identical before/after (A=64, B=100.0, E=98.4, F=100.0, G=97.0, H PASS, J=100.0), confirmed in both adversarial passes.

## Cost
DB reads via Management API (mgmt_sql.py) + 2 existing Python scripts re-run + 1 SQL INSERT (parcel_zones alias row) + 1 Workflow (3 refuter agents) + 1 follow-up verifier agent. No new scripts written, no schema changes, no paid API spend.
