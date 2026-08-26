# Gold Standard Shard-2 Session Report

**Dispatch ID:** `62855eaa-34ca-4dc6-88ee-b7cb1a2e98ed`
**Counties:** gadsden, okeechobee, alachua, calhoun, leon
**Mode:** ULTRALOOP — 5 parallel fix agents + 5 parallel adversarial-verify agents (already executed against production Supabase; this session closes the loop: computes final verified status, writes audit rows, writes migration record, session-close-out)
**Closeout run:** 2026-08-26

---

## Summary Table — Final VERIFIED Status (post adversarial-verify)

| County | Before (pass/10) | After (pass/10, verified) | Letters genuinely flipped (survived=true) | Letters refuted (claimed but survived=false) | Structurally blocked |
|---|---|---|---|---|---|
| gadsden | 9/10 | 9/10 (unchanged) | none | none | C (CLERK_SSOT_CANCELLED, 10 genuinely redeemed pre-sale rows) |
| okeechobee | 9/10 | **10/10** | I | none | none |
| alachua | 8/10 | 8/10 (unchanged) | none | none (correctly reported as still-FAIL) | E, I partially — 5 of 6 gap rows unresolvable this session (empty Clerk docid, 1 genuine multi-parcel case) |
| calhoun | 7/10 | **9/10** | D, I | none | C (CLERK_SSOT_CANCELLED, case 546 OF 2024) |
| leon | 7/10 | **9/10** | C, D, F | none | B partial — 2 rows genuinely unresolved (Akamai 403 on independent 2nd source) |

No refuted claims this session — every claim made by a fix agent was independently confirmed by its paired verify agent, including the "still failing" / "structurally blocked" claims. `survived=true` for all 11 letter-verdicts logged.

---

## Per-County Detail

### gadsden

**fix.baseline_before:**
```json
{"A":{"pass":true,"detail":"fc=25 td=41","metric":25},"B":{"pass":true,"detail":"verified=1 closed_sold=1","metric":100.0},"C":{"pass":false,"detail":"matched_clean=56","metric":84.8},"D":{"pass":true,"detail":"matched_any=66","metric":100.0},"E":{"pass":true,"detail":"parcel_linked=65","metric":98.5},"F":{"pass":true,"detail":"tier1_sold=1 closed_sold=1","metric":100.0},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":6.9},"I":{"pass":true,"detail":"card_complete=65 of 66","metric":98.5},"J":{"pass":true,"detail":"deal_complete=63 (triangle + two-arm CMA + ml_score + max_bid)","metric":95.5},"county":"gadsden","auctions_total":66}
```

**fix.baseline_after:** identical to baseline_before — no PATCH applied (investigation-only session; all 10 non-passing rows confirmed genuine, not fabricable fixes).

**verify.fresh_evaluation:**
```json
{"A":{"pass":true,"detail":"fc=25 td=41","metric":25},"B":{"pass":true,"detail":"verified=1 closed_sold=1","metric":100.0},"C":{"pass":false,"detail":"matched_clean=56","metric":84.8},"D":{"pass":true,"detail":"matched_any=66","metric":100.0},"E":{"pass":true,"detail":"parcel_linked=65","metric":98.5},"F":{"pass":true,"detail":"tier1_sold=1 closed_sold=1","metric":100.0},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":7.2},"I":{"pass":true,"detail":"card_complete=65 of 66","metric":98.5},"J":{"pass":true,"detail":"deal_complete=63 (triangle + two-arm CMA + ml_score + max_bid)","metric":95.5},"county":"gadsden","auctions_total":66,"note":"Identical to fix agent's baseline except H metric drifted 6.9->7.2 (expected time-based drift, still well within 48h SLA)"}
```

**Verdict:** C — claimed_pass=false, verified_pass=false, **survived=true**. Structurally blocked: all 10 non-matched_clean rows carry `parity_status='CLERK_SSOT_CANCELLED'` (case numbers 26000018/21/22/24/25/27/29/32/34/35 TDC), independently confirmed by the verify agent via a fresh direct curl of `https://www.gadsdenclerk.com/Tax_deeds/Tax_deeds_files/sheet001.htm` (HTTP 200) showing all 10 case numbers genuinely "Redeemed" pre-sale-date. This matches the calhoun-C precedent (`20260812_shard1_calhoun_c_diagnose_d_ssot_cancelled_fix.sql`): `CLERK_SSOT_CANCELLED` is included in D's `matched_any` but deliberately excluded from C's `matched_clean` by design. No fabrication attempted.

---

### okeechobee

**fix.baseline_before:** A=18 PASS, B=100.0 PASS, C=97.6 PASS (matched_clean=83), D=97.6 PASS, E=96.5 PASS (parcel_linked=82), F=100.0 PASS, G=100.0 PASS, H=0.0 PASS, **I=94.1 FAIL** (card_complete=80 of 85, need 81), J=100.0 PASS. auctions_total=85.

**fix.baseline_after:** A=18 PASS, B=100.0 PASS, C=98.8 PASS (matched_clean=84), D=98.8 PASS, E=97.6 PASS (parcel_linked=83), F=100.0 PASS, G=100.0 PASS, H=0.0 PASS, **I=95.3 PASS** (card_complete=81 of 85), J=100.0 PASS. auctions_total=85. **okeechobee now 10/10.**

**verify.fresh_evaluation:**
```json
{"A": {"pass": true, "metric": 18, "detail": "fc=18 td=67"}, "B": {"pass": true, "metric": 100.0, "detail": "verified=6 closed_sold=6"}, "C": {"pass": true, "metric": 98.8, "detail": "matched_clean=84"}, "D": {"pass": true, "metric": 98.8, "detail": "matched_any=84"}, "E": {"pass": true, "metric": 97.6, "detail": "parcel_linked=83"}, "F": {"pass": true, "metric": 100.0, "detail": "tier1_sold=6 closed_sold=6"}, "G": {"pass": true, "metric": 100.0, "detail": "density=100.0 far=100.0 pk1000=100.0"}, "H": {"pass": true, "metric": "0.0/0.1", "detail": "hours since last_seen (SLA 48h)"}, "I": {"pass": true, "metric": 95.3, "detail": "card_complete=81 of 85"}, "J": {"pass": true, "metric": 100.0, "detail": "deal_complete=85"}, "auctions_total": 85, "runs": "3 consecutive fresh POST calls to pencil_dod_evaluate_county, all identical, 10/10 pass"}
```

**Verdict:** I — claimed_pass=true, verified_pass=true, **survived=true**. Genuine live data fix: case `472025CA000189CAAXMX` (id `b1c0dd06-cd4d-4082-8615-bc9b29a5d287`) completed with parcel_id, address, lat/lon, market_value, assessed_value cross-verified against 3 independent primary sources (Clerk foreclosure list, court-filed Summary Judgment PDF, Property Appraiser GIS), plus a new `parcel_zones` row (zone_code=RSF) derived from a live WMS point-in-polygon sample. Verify agent independently re-fetched the row and re-confirmed all values, plus independently confirmed the zoning join now resolves. The 4 remaining gap rows were re-attempted and re-confirmed structurally blocked (parcel not on PA roll; zoning-layer coverage gap on a real highway-frontage parcel; case not yet noticed for sale on Clerk's live list; duplicate stub row out of scope) — no fabrication.

---

### alachua

**fix.baseline_before:**
```json
{"A":{"pass":true,"metric":19},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":false,"detail":"parcel_linked=79","metric":92.9},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":96.6},"H":{"pass":true,"metric":0.1},"I":{"pass":false,"detail":"card_complete=79 of 85","metric":92.9},"J":{"pass":true,"metric":100.0},"auctions_total":85}
```

**fix.baseline_after:**
```json
{"A":{"pass":true,"metric":19},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":false,"detail":"parcel_linked=80","metric":94.1},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":96.6},"H":{"pass":true,"metric":0.0},"I":{"pass":false,"detail":"card_complete=80 of 85","metric":94.1},"J":{"pass":true,"metric":100.0},"auctions_total":85}
```
E and I both moved 79→80 (92.9%→94.1%) but **remain FAIL** (need 81/85=95.3%). 1 of 6 target rows genuinely fixed; 5 remain unresolvable via free public sources this session.

**verify.fresh_evaluation:**
```json
{"A": {"pass": true, "detail": "fc=66 td=19", "metric": 19}, "B": {"pass": true, "detail": "verified=6 closed_sold=6", "metric": 100.0}, "C": {"pass": true, "detail": "matched_clean=85", "metric": 100.0}, "D": {"pass": true, "detail": "matched_any=85", "metric": 100.0}, "E": {"pass": false, "detail": "parcel_linked=80", "metric": 94.1}, "F": {"pass": true, "detail": "tier1_sold=6 closed_sold=6", "metric": 100.0}, "G": {"pass": true, "detail": "density=96.6 far= pk1000=", "metric": 96.6}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.1}, "I": {"pass": false, "detail": "card_complete=80 of 85", "metric": 94.1}, "J": {"pass": true, "detail": "deal_complete=85 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100.0}, "county": "alachua", "auctions_total": 85}
```

**Verdicts:**
- **E** — claimed_pass=false, verified_pass=false, **survived=true**. The single genuine PATCH (case `01 2025 CA 002983`, parcel `03209-010-022`) was independently re-confirmed against the ACPA/county ArcGIS layers by the verify agent — real fix, correctly still-FAIL.
- **I** — claimed_pass=false, verified_pass=false, **survived=true**. New `parcel_zones` row (id 871667, zone_code RSF-6) independently confirmed live with matching timestamp — real fix, correctly still-FAIL.
- 5 residual gap rows (`01 2025 CA 001928`, `01 2025 CA 003287` [multi-parcel], `01 2026 CA 000169`, `01 2025 CA 003919`, `01 2025 CA 002643`) independently confirmed by verify agent to be genuinely NULL/untouched — no fabrication, no ghost-fill.

---

### calhoun

**fix.baseline_before:**
```json
{"A": {"pass": true, "metric": 3}, "B": {"pass": true, "metric": 100.0}, "C": {"pass": false, "detail": "matched_clean=7", "metric": 77.8}, "D": {"pass": false, "detail": "matched_any=8", "metric": 88.9}, "E": {"pass": true, "metric": 100.0}, "F": {"pass": true, "metric": 100.0}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "metric": 10.5}, "I": {"pass": false, "detail": "card_complete=8 of 9", "metric": 88.9}, "J": {"pass": true, "metric": 100.0}, "auctions_total": 9}
```

**fix.baseline_after:**
```json
{"A": {"pass": true, "metric": 3}, "B": {"pass": true, "metric": 100.0}, "C": {"pass": false, "detail": "matched_clean=8", "metric": 88.9, "note": "STRUCTURALLY BLOCKED"}, "D": {"pass": true, "detail": "matched_any=9", "metric": 100.0}, "E": {"pass": true, "metric": 100.0}, "F": {"pass": true, "metric": 100.0}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "metric": 10.6}, "I": {"pass": true, "detail": "card_complete=9 of 9", "metric": 100.0}, "J": {"pass": true, "metric": 100.0}, "auctions_total": 9}
```
D and I flipped to PASS. calhoun now **9/10**.

**verify.fresh_evaluation:**
```json
{"A": {"pass": true, "detail": "fc=3 td=6", "metric": 3}, "B": {"pass": true, "detail": "verified=1 closed_sold=1", "metric": 100.0}, "C": {"pass": false, "detail": "matched_clean=8", "metric": 88.9}, "D": {"pass": true, "detail": "matched_any=9", "metric": 100.0}, "E": {"pass": true, "detail": "parcel_linked=9", "metric": 100.0}, "F": {"pass": true, "detail": "tier1_sold=1 closed_sold=1", "metric": 100.0}, "G": {"pass": true, "detail": "density=100.0 far=100.0 pk1000=", "metric": 100.0}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 10.7}, "I": {"pass": true, "detail": "card_complete=9 of 9", "metric": 100.0}, "J": {"pass": true, "detail": "deal_complete=9 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100.0}, "county": "calhoun", "auctions_total": 9}
```

**Verdicts:**
- **D** — claimed_pass=true, verified_pass=true, **survived=true**. Case `25-52CA` (id `ceaaa9e7-555f-49f4-ada2-fb1e44808fc1`) PATCHed to `parity_status='PARITY_OK'`. Verify agent independently re-fetched the live Calhoun Clerk WP REST foreclosures feed itself and got an exact match on case number, sale date, address, parcel, status.
- **I** — claimed_pass=true, verified_pass=true, **survived=true**. Geo/value from FL DOH statewide parcels layer 6 (JV=58826, AV_SD=43094) + new `parcel_zones` row (zone_code=SFR). Verify agent independently queried the FL DOH layer itself and got an exact match, and confirmed the new zoning join resolves.
- **C** — claimed_pass=false, verified_pass=false, **survived=true**. Structurally blocked: case `546 OF 2024` carries `parity_status='CLERK_SSOT_CANCELLED'` (2026-08-11 precedent), independently re-confirmed absent from the live Clerk taxdeeds feed by the verify agent.

---

### leon

**fix.baseline_before:** A PASS(112), **B FAIL 88.2%** (verified=15 closed_sold=17), **C FAIL 94.4%** (matched_clean=237), **D FAIL 94.4%** (matched_any=237), E PASS(98.4), **F FAIL 94.1%** (tier1_sold=16 closed_sold=17), G PASS(95.9), H PASS, I PASS(96.8), J PASS(99.2). auctions_total=251.

**fix.baseline_after:** A PASS(112), **B FAIL 88.2%** (unchanged), **C PASS 97.2%** (matched_clean=244), **D PASS 97.2%** (matched_any=244), E PASS(98.4), **F PASS 100.0%** (tier1_sold=17 closed_sold=17), G PASS(95.9), H PASS, I PASS(96.8), J PASS(99.2). auctions_total=251. **leon now 9/10, only B remains failing.**

**verify.fresh_evaluation:**
```json
{"A":{"pass":true,"metric":112},"B":{"pass":false,"detail":"verified=15 closed_sold=17","metric":88.2},"C":{"pass":true,"detail":"matched_clean=244","metric":97.2},"D":{"pass":true,"detail":"matched_any=244","metric":97.2},"E":{"pass":true,"metric":98.4},"F":{"pass":true,"detail":"tier1_sold=17 closed_sold=17","metric":100.0},"G":{"pass":true,"metric":95.9},"H":{"pass":true},"I":{"pass":true,"metric":96.8},"J":{"pass":true,"metric":99.2},"auctions_total":251}
```
Exact match to fix agent's baseline_after.

**Verdicts:**
- **C** — claimed_pass=true, verified_pass=true, **survived=true**. 7 rows PATCHed to `parity_status='matched_clean', parity_source='tier1_realforeclose_leon'` after fresh RealAuction AJAX harvest. Verify agent independently live-queried all 7 rows and confirmed the residual 7 unresolved case numbers are genuinely NULL (251=244+7 arithmetic clean).
- **D** — claimed_pass=true, verified_pass=true, **survived=true**. Same basis as C.
- **F** — claimed_pass=true, verified_pass=true, **survived=true**. Case `2026 CA 000145` PATCHed to `tier1_authoritative=true, tier1_sold_amount=100.0`. Verify agent independently confirmed the patched row and independently confirmed the fleet-wide $100/$101 plaintiff-credit-bid precedent exists in palm_beach/marion/miami_dade/volusia — not a one-off fabrication.
- **B** — claimed_pass=false, verified_pass=false, **survived=true**. 2 rows (`2025 CA 001586`, `2026 CA 000145`) genuinely unresolved — no independent 2nd-source confirmation available (Leon Clerk `cvweb.leonclerk.com` returns HTTP 403 Akamai block, RealAuction detail pages are login-gated). Verify agent independently reproduced the HTTP 403 and independently confirmed the exact 2 gap rows via `sold_amount_source`. No fabrication (correctly avoided replicating the 2026-07-10 single-source fabrication-revert precedent for this exact county).

---

## Audit Trail

11 rows inserted into `public.gold_standard_ultraloop_audit` (ids 18493–18503), one per letter-verdict, all with `survived=true`. See table for county_slug/letter/claim/refuter_evidence/survived detail.

## Migration File

A new data-fix migration file was written documenting the genuine surviving PATCH/POST operations (okeechobee I, alachua E/I, calhoun D/I, leon C/D/F) as equivalent SQL for the historical record: `supabase/migrations/20260826_gold_standard_shard2_62855eaa_gadsden_okeechobee_alachua_calhoun_leon.sql`. No SQL was written for gadsden (no-op session) or for refuted/unresolved letters (alachua's 5 residual rows, leon B's 2 residual rows, calhoun/gadsden C structural blocks) since none of those produced a real data write.
