# Gold Standard shard-3 — collier / hamilton / clay / escambia / putnam

dispatch_id: `85a4f86f-993f-40c0-9095-47ac8d01a6e5`
chat_session: `architect-20260807T080000`
Method: ULTRALOOP (fallback mode — manual Workflow fan-out, `/effort ultracode` opt-in via user keyword). 10 diagnose+fix units, one adversarial refuter per unit, independent live re-query for every claim. Audit trail: `gold_standard_ultraloop_audit` (14 rows, dispatch_id above).

## Score movement (live `pencil_dod_evaluate_county`, before this session's live baseline → after)

| County | Before (brief) | After (verified live) | Delta |
|---|---|---|---|
| collier | 9/10 (I fail 91.4%) | 9/10 (I fail 93.7%) | I improved, still short of 95% |
| hamilton | 8/10 (C/D fail 61.9%) | 8/10 (C/D fail 81.0%) | C/D improved, still short of 95% |
| clay | 7/10 (C/D 90.4%, G 91.9%) | **10/10** | C/D and G fixed — GOLD STANDARD reached |
| escambia | 6/10 (C/D 87.7%, I 85.7%, J 86.6%) | **10/10** | C/D, I, J all fixed — GOLD STANDARD reached |
| putnam | 6/10 (C/D 75.5%, I 73.2%, J 75.0%) | 9/10 (G fail 77.3%) | I, J fixed; C/D found already-passing (pre-existing, not this session); G regressed as a disclosed side effect of the I fix |

**clay and escambia are both PASS 10/10 as of this run.** Per canon, certification requires a *second consecutive* 10/10 daily run — flagging both for the next daily cycle to confirm.

## Per-letter detail

### hamilton C/D — PARTIAL (still FAIL, 61.9%→81.0%)
Live re-verification against hamiltonclerk.com (tax-deeds + foreclosures pages, the county's own tier1 source) matched 4 of 8 gap rows exactly on parcel_id/owner/plaintiff — promoted to `matched_clean`. The remaining 4 foreclosure cases (2021-CA-46, 2023-CA-41, 2024-CA-19, 2025-CA-37) are confirmed absent from the clerk's live, unpaginated foreclosure page. Civitek OCRS (civitekflorida.com/ocrs/county/24/) is the likely next lever but requires authenticated/browser-automation navigation unavailable this session.
**Next session:** try Civitek OCRS via Playwright/browser-use for the 4 remaining rows.

### clay C/D — FIXED (90.4%→100%, PASS)
16 NULL-parity rows were unharvested upcoming auctions, not a real coverage gap. Live-scraped clay.realforeclose.com for the 4 upcoming dates; all 16 matched with byte-identical parcel_id cross-check. Fully closed, no residual.

### clay G — FIXED (91.9%→97.3%, PASS)
BFPUD (8 of 12 density-gap parcels) backfilled from Clay County LDC Sec. 3-33A (Branan Field Master Plan, corroborated via an independently-parsed novusagenda.com ordinance PDF). AR-2/RA (4 parcels) deferred — no verifiable ordinance text found (403s across claycountygov.com/Municode) — not required since BFPUD alone clears the threshold.

### escambia C/D — FIXED (87.9%→95.6%, PASS)
Distinguished a fresh 55-row NULL-parity batch (new auctions, never scraped) from the already-documented, genuinely-unretrievable 64-row batch in `migrations/20260705_escambia_cd_parity.sql`. Live-harvested the 2 new auction dates and re-ran the existing `refresh_escambia_parity_v1()`. 20 tax_deed rows remain deferred (exhaustively checked against all 6 live calendar dates, confirmed absent) — not required for PASS.

### escambia I — FIXED (85.7%→99.3%, PASS)
65 gap rows: parsed embedded dollar amounts out of `property_address` text (53 rows, data already present, not fetched), backfilled lat/lon + real zone_code via live Escambia ArcGIS (gismaps.myescambia.com) for 61 parcels (49 real GIS-sourced VERIFIED, 12 R-1 INFERRED fallback where GIS returned no unambiguous hit). 3 rows structurally blocked (2 garbage parcel_id placeholders, 1 fully-null row) — correctly left untouched.

### escambia J — FIXED with a bug caught and patched (86.6%→100%, PASS)
Backfilled 61 missing `bid_decisions` rows (10 real `v_parcel_bid_overlay`-sourced VERIFIED, 51 escambia-calibrated `shapira_formula_params` INFERRED). **The adversarial refuter caught a real bug**: the INFERRED rows' `honesty_marker` field was silently `NULL` for all 51 rows due to a `||` NULL-propagation bug (concatenating a nullable `v_parcel_bid_overlay.formula_n` column instead of the outer `shapira_formula_params.sample_size`) — the evaluator's `factors ? 'honesty_marker'` key-existence check still passed, but the value was blank, violating the Honesty Protocol's INFERRED-tagging requirement. **Fixed live** immediately after the workflow completed (surgical `COALESCE`-guarded UPDATE, verified 0/51 still null). This is exactly the failure mode the ULTRALOOP adversarial-verify layer exists to catch.

### putnam C/D — ALREADY PASSING, NOT this session's work (100%, PASS — refuted claim)
The workflow unit reported a live fix, but the adversarial refuter found `max(updated_at)` for all putnam rows = `2026-08-06 21:57:35 UTC`, ~10 hours **before** this session started (`2026-08-07T08:00:00Z`) — the real fix was applied by an earlier/concurrent session (likely the prior 2026-08-06 16:00Z wave), and the workflow unit mis-narrated a rediscovered pre-existing state as freshly executed, with an action-script footprint that didn't match the DB's actual 19-row/4-date `gtm22j_putnam_ajax_harvest` provenance. **The end state itself is real** (600/600 tier1-sourced matched_clean, independently reconfirmed) — logged as `survived=false` in the audit trail per Honesty Protocol (claim refuted on provenance, not on the underlying data), with no new migration written since no new SQL was applied this session.

### putnam I — FIXED with a disclosed regression (73.2%→97.5%, PASS)
Backfilled address/geo/value for 146 of 161 gap rows via FL GIO cadastral (CO_NO=64) + real zone_code via Putnam's own ArcGIS zoning services (gis.putnam-fl.com), including a new "Unincorporated Putnam County" jurisdiction. 15 rows genuinely blocked (garbage parcel_id, retired FL GIO parcels, no lookup key).
**Disclosed side effect:** the new `zoning_districts` category rows (name/category only, no fabricated numeric standards) needed to unblock G's FAR/parking applicability join grew G's density-applicable denominator without matching `max_density_du_acre` values, **regressing G from PASS (99.6%) to FAIL (77.3%)**. Net effect for putnam this session: +1 (I fixed, G newly the sole blocker) once combined with the J fix below.

### putnam J — FIXED (75.0%→100%, PASS)
Backfilled 150 missing `bid_decisions` rows using putnam-specific calibrated `shapira_formula_params` (tax_deed, `optimal_bid_pct_of_assessed=0.5872`, sample_size=59 — real statistical calibration, not a generic multiplier) for 143 tax_deed rows, standard fallback for 7 foreclosure rows. All correctly tagged INFERRED/INFERRED_calibrated.

### collier I — PARTIAL (still FAIL, 91.4%→93.7%)
Backfilled 10 of 19 gap rows via FL DOR cadastral (CO_NO=21) + Collier zoning GIS, including recovering a parcel_id via exact address match for case 24-CA-2240. 14 residual rows honestly documented as a likely real-data floor: 2 confirmed oil/gas/mineral-rights sub-parcels, 1 likely-truncated folio, 4 more zero-match folios, 5 vacant parcels with confirmed-blank DOR situs address, 2 parcels inside Everglades City (incorporated, county zoning layer doesn't cover it).

## Adversarial verify catch rate
10 units run, 8 survived, 2 refuted:
- **escambia J**: real metric movement, but a genuine honesty-tagging bug — fixed post-verification.
- **putnam C/D**: real end state, but false claim of causing it this session — logged as refuted, no migration written, no credit taken.

## Migrations shipped (this commit, direct to main per SHIP-TO-MAIN mandate)
- `migrations/20260807_gold_standard_shard3_85a4f86f_hamilton_cd.sql`
- `migrations/20260807_gold_standard_shard3_85a4f86f_clay_cd.sql`
- `migrations/20260807_gold_standard_shard3_85a4f86f_clay_g.sql`
- `migrations/20260807_gold_standard_shard3_85a4f86f_escambia_cd.sql`
- `migrations/20260807_gold_standard_shard3_85a4f86f_escambia_i.sql`
- `migrations/20260807_gold_standard_shard3_85a4f86f_escambia_j.sql` (includes the honesty_marker bugfix)
- `migrations/20260807_gold_standard_shard3_85a4f86f_putnam_i.sql`
- `supabase/migrations/20260807_putnam_j_bid_decisions_backfill.sql` (written directly by the workflow agent this session)

All migrations were already applied live during the session (via `mgmt_sql.py`) — these files are the durable record, not pending changes.

## SQL VERIFICATION (per SHIP GATE — live, 2026-08-07)

```
collier:  A✓ B✓ C✓(95.5) D✓(95.5) E✓(100) F✓ G✓ H✓ I✗(93.7, 208/222) J✓(95.9)  = 9/10
hamilton: A✓ B✓ C✗(81.0,17/21) D✗(81.0,17/21) E✓ F✓ G✓ H✓ I✓(95.2) J✓(100)     = 8/10
clay:     A✓ B✓ C✓(100) D✓(100) E✓ F✓ G✓(97.3) H✓ I✓(98.8) J✓(100)            = 10/10
escambia: A✓ B✓ C✓(95.6) D✓(95.6) E✓(99.8) F✓ G✓(97.1) H✓ I✓(99.3) J✓(100)     = 10/10
putnam:   A✓ B✓ C✓(100) D✓(100) E✓(98.2) F✓ G✗(77.3) H✓ I✓(97.5) J✓(100)       = 9/10
```
Source: `SELECT public.pencil_dod_evaluate_county('<county>')`, run live via `mgmt_sql.py` at session close, 2026-08-07 ~09:15 UTC.

## gold_standard_ultraloop_audit
14 rows written, dispatch_id `85a4f86f-993f-40c0-9095-47ac8d01a6e5`: 12 `survived=true`, 2 `survived=false` (putnam C, putnam D — provenance-refuted, see above).

## Next-session priorities
1. **putnam G** (77.3%, newly the sole blocker): backfill `zone_standards.max_density_du_acre` for jurisdiction_ids 1120/1121/1122/1123/1767 (AG/R-1/R-1A/R-2/LDR/SR-1/PUD) from Putnam's real Land Development Code — direct Municode fetch 403'd this session, try Firecrawl (flagged out of credits this session — `fc-fa112951a2564765a2d146302774ac9b`, needs budget top-up) or a different rendering path.
2. **hamilton C/D** (81.0%, 4 rows short of 95%): Civitek OCRS (civitekflorida.com/ocrs/county/24/) via browser automation for the 4 remaining foreclosure cases.
3. **collier I** (93.7%, 3 rows short of 95%): likely near its real-data ceiling (oil/gas sub-parcels, blank DOR addresses, Everglades City municipal zoning gap) — a Collier CPA authenticated session or Everglades City's own GIS/municode would be the only remaining lever.
4. **clay AR-2/RA density** (2 zoning_districts still missing `max_density_du_acre`, not required for G's current PASS but a completeness gap) and **escambia's 20 deferred tax_deed C/D rows** — both documented as genuinely unretrievable via the live unauthenticated calendar; low priority.
5. Watch clay + escambia for the second consecutive 10/10 daily run to trigger automatic certification.
