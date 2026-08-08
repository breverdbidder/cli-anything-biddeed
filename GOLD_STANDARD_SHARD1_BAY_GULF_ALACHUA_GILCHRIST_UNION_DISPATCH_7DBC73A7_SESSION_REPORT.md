# Gold Standard Shard-1 Session Report

**Dispatch:** `7dbc73a7-f66c-45c8-9340-479dc6eabf73` (chat_session `architect-20260808T080000`)
**Shard:** bay, gulf, alachua, gilchrist, union
**Mode:** ULTRALOOP via Workflow tool fan-out (5 fixer agents → 5 independent adversarial refuter agents, one per county/letter claim)
**Session date:** 2026-08-08

## Result summary

| County | Before | After | Letter(s) worked | Outcome |
|---|---|---|---|---|
| bay | 9/10 (G fail) | **10/10** | G | **FIXED, VERIFIED** |
| gulf | 9/10 (I fail) | 9/10 | I | Structurally blocked (verified) |
| alachua | 8/10 (E,I fail) | 8/10 | E, I | Structurally blocked (verified) |
| gilchrist | 8/10 (E,I fail) | 8/10 | E, I | Structurally blocked (verified) |
| union | 8/10 (B,F fail) | 8/10 | B, F | Structurally blocked (verified) |

All claims above carry an independently-run `pencil_dod_evaluate_county` result from a separate refuter agent (not the fixer) — see `gold_standard_ultraloop_audit` for the 8 logged rows (all `survived=true`), and `supabase/migrations/20260808a_gold_standard_shard1_7dbc73a7_bay_g_union_bf.sql` for the only two real writes made this session.

## bay — G FIXED (94.4% → 100.0% pk1000; county now 10/10)

Root cause: only 36 pk1000-applicable parcels in bay; 2 gaps kept it below the 95% threshold.

1. Panama City "NG" (Neighborhood General) district (`zoning_districts.id=7270`) had `parking_per_1000sf=NULL`. Backfilled to **1.25** from Panama City Unified Land Development Code, Ch. 104 §104-36.2 Table 104-36.2.C (non-residential = 1 space/800sf GFA). Source: https://panamacity.gov/DocumentCenter/View/6503/NG-Zone_ULDC
2. Parcel `03198-000-000` in Unincorporated Bay County carried `zone_code='AG-1'` with no matching `zoning_districts` row (silent join failure). Inserted the real AG-1 (General Agriculture) district + `zone_standards` row sourced from Bay County LDR Ch. 9 §905 Table 9.1 (min lot 10 acres, max density 0.10 du/acre, max height 50ft, max coverage 25%). This ordinance has no parking column for AG-1 — correctly left `parking_per_1000sf=NULL` and confirmed excluded from the pk1000 denominator via `v_zoning_district_applicability` rather than fabricating a number. Source: https://baycountyfl.gov/DocumentCenter/View/602/Chapter-09-Land-Development-Regulations-PDF

**Live re-verification (independent refuter agent):** `pencil_dod_evaluate_county('bay')` → G pass=true, metric=97.7 (density=97.7 far=100.0 pk1000=100.0), full A-J eval all `pass:true`. Refuter independently downloaded and text-extracted both source PDFs and confirmed the written values match the ordinance text exactly. No regression on any other letter.

## gulf — I still failing (85.7%, 12/14), genuinely blocked

Two parcels (`05762000R` / 256 Ave C, `05004050R` / Knowles Ave, both Port St. Joe) have zero rows in `parcel_zones`. No authoritative Gulf County zoning source (GIS layer, qpublic zoning field, or ordinance map) could be located for either parcel this session. No write was made — reported honestly as blocked rather than guessing a zone code. Refuter independently confirmed zero new `parcel_zones`/`zone_standards` rows for jurisdiction 952 and that the metric is unchanged.

## alachua — E/I still failing (93.0%/87.3%), genuinely blocked

5 pending-sale foreclosure cases (`01 2025 CA 003287`, `01 2025 CA 001928`, `01 2025 CA 002643`, `01 2025 CA 003919`, `01 2024 CC 005935`) have no property address or parcel_id in source data. Alachua Clerk's eCourts portal returned 403/JS-gated responses to every research attempt this session. No write made. I is structurally downstream of E for these same 5 rows. Refuter independently confirmed all 5 case numbers still have `parcel_id IS NULL` and no new writes occurred.

## gilchrist — E/I still failing (57.1%/57.1%), genuinely blocked

6 unlinked cases (`212025CA000064/033/070/043/036CAAXMX`, `212026CA000004CAAXMX`) were traced to `gilchrist.realforeclose.com`: the refuter independently re-built and ran an AJAX harvest against the live site and confirmed the source itself only populates the property-address/parcel-id fields once a sale is finalized — pre-finalization the parcel-link field is a static, non-functional qPublic placeholder with an empty key parameter. This is a genuine data-availability gap in the upstream source, not a scraper bug. No write made.

## union — B/F still failing (null/null), genuinely blocked

All 3 union auctions: 2 foreclosures with genuinely future auction dates (2026-08-13, 2026-10-15) and 1 tax deed (`UNION-TD-CERT223`, auction_date 2026-03-12) confirmed via `unionclerk.com` to be `auction_status='redeemed'` — the certificate was redeemed by the owner, not sold. Recorded an honest `tax_deed_outcomes` row (`outcome='redeemed'`, `winning_bid=NULL`, no fabricated sale amount) for audit completeness. `closed_sold=0` for union is mathematically correct given these 3 rows; B and F cannot move until a union case actually closes with a real sale.

## Close-out

- `gold_standard_campaign` (dispatch `7dbc73a7-...`, row id 3881): `criteria_passed` set per-county (bay 10/10, gulf 9/10, alachua 8/10, gilchrist 8/10, union 8/10), `exit_reason='targets_worked_structural_blockers_remain'`, `session_end_at` set.
- `gold_standard_ultraloop_audit`: 8 rows inserted (bay/G, gulf/I, alachua/E, alachua/I, gilchrist/E, gilchrist/I, union/B, union/F), all `survived=true`, `ultraloop_mode='native'`.
- Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were **not** run fleet-wide this session (no reliable signal that no other shard was mid-flight); only per-county `pencil_dod_evaluate_county` was used, as instructed by the fallback rule.

## Next-session priorities for this shard

1. **gulf I** — needs a working Gulf County zoning data source (GIS/ordinance) for the 2 remaining parcels; none found this session.
2. **alachua E/I** — needs an alternate route around the Alachua Clerk's 403/JS-gated eCourts portal (e.g. a headless-browser approach, or a different public-records mirror) for the 5 case numbers.
3. **gilchrist E/I** — the 6 cases are upstream-source-blocked (realforeclose.com only populates post-finalization); revisit after their scheduled auction dates pass, or find an alternate Gilchrist Clerk source.
4. **union B/F** — will only move if the two upcoming foreclosures (2026-08-13, 2026-10-15) close with a sale; nothing actionable until then.
