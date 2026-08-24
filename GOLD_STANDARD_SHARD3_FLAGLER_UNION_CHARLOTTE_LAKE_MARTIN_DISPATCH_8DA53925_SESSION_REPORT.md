# Gold Standard Shard-3: flagler / union / charlotte / lake / martin (dispatch `8da53925-d806-441f-98c7-db90845f68e6`)

## Status: 5 counties worked in parallel, adversarially verified. flagler 10/10; union, charlotte 9/10; martin 8/10; lake 6/10.

This is the mandatory close-out for shard-3. All work below was performed by parallel
fix+verify sub-agent pairs earlier in this session; this report performs a **fresh, final,
independent** `pencil_dod_evaluate_county` re-check per county (Step 1 of the close-out
protocol) before writing anything to `gold_standard_campaign`. Numbers below are pasted
raw from live `curl` output, not reused from the sub-agent transcripts.

---

## flagler — 10/10 (up from 9/10 at session start)

### Session-start baseline (from orchestrator brief, precomputed before this session)
```
A PASS metric=57   [fc=57 td=106]
B PASS metric=100.0 [verified=7 closed_sold=7]
C PASS metric=95.7 [matched_clean=156]
D PASS metric=97.5 [matched_any=159]
E PASS metric=97.5 [parcel_linked=159]
F PASS metric=100.0 [tier1_sold=7 closed_sold=7]
G PASS metric=97.5 [density=97.5 far= pk1000=]
H PASS metric=0.0  [hours since last_seen]
I FAIL metric=93.9 [card_complete=153 of 163]
J PASS metric=100.0 [deal_complete=163]
```
9/10 — only I failing.

### FINAL fresh live re-check (this close-out session, VERIFIED)
```json
{"A": {"pass": true, "detail": "fc=57 td=106", "metric": 57}, "B": {"pass": true, "detail": "verified=7 closed_sold=7", "metric": 100.0}, "C": {"pass": true, "detail": "matched_clean=158", "metric": 96.9}, "D": {"pass": true, "detail": "matched_any=161", "metric": 98.8}, "E": {"pass": true, "detail": "parcel_linked=159", "metric": 97.5}, "F": {"pass": true, "detail": "tier1_sold=7 closed_sold=7", "metric": 100.0}, "G": {"pass": true, "detail": "density=97.5 far= pk1000=", "metric": 97.5}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.0}, "I": {"pass": true, "detail": "card_complete=155 of 163", "metric": 95.1}, "J": {"pass": true, "detail": "deal_complete=163 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100.0}, "county": "flagler", "V2_LITMUS": null, "auctions_total": 163}
```
**10/10, all PASS.**

### Per-letter table

| Letter | Fixed/Blocked | Action | Rows | Before -> After | Marker | Evidence | Commit |
|---|---|---|---|---|---|---|---|
| I | FIXED | Live ArcGIS point-in-polygon zoning lookup (PalmCoastFL_Zoning FeatureServer, jurisdiction_id=966) -> `parcel_zones` INSERT for 2 of 6 zone-link-only gap parcels | 2 (`07-11-31-7010-00130-0150`->SFR-3 id=868952; `07-11-31-5531-00000-0040`->SFR-1 id=868953) | 93.9% (153/163) FAIL -> 95.1% (155/163) PASS | VERIFIED | services1.arcgis.com/tpnsCwhQRDqwL3mq/.../PalmCoastFL_Zoning/FeatureServer/0/query, exact point-in-polygon hit, single feature | `209b02a2` |
| C | FIXED | realforeclose.com AJAX calendar litmus confirmed exact parcel_id match, stamped `matched_clean` w/ tier1% source | 1 (2025 CA 000305) | 95.7% -> 96.9% PASS | VERIFIED | flagler.realforeclose.com AJAX 09/18/2026 calendar | `209b02a2` |
| D | FIXED | Same litmus run, 1 more row | 1 (2024 CC 000997) | 97.5% -> 98.8% PASS | VERIFIED | flagler.realforeclose.com AJAX 10/02/2026 calendar | `209b02a2` |
| I (residual) | BLOCKED (honest, non-fabricated) | Fresh live recheck of 4 remaining gap parcels — reconfirmed genuinely blocked | 0 written | n/a | VERIFIED (of the blockage) | flaglerpa.com HTTP 302/403, qpublic.schneidercorp.com HTTP 403 (no public search API); ArcGIS 800m buffer returns 3-6 conflicting zone codes | n/a |

Residuals left honestly unfixed (no fabrication): case `78713ea7` (no parcel_id/address, fake-placeholder lat/lon documented since 2026-08-16); cases `c1b495e8`, `6307e8ab` (no parcel_id/address, county-appraiser endpoints 403/302); parcels `10-12-30-0850-01700-0040`, `20-10-31-3050-00080-0050`, `20-10-31-0300-00150-0000` (zero or conflicting ArcGIS zoning features).

**Adversarial verify:** CONFIRMED all 4 claims. Independently re-fetched RPC (exact match), spot-checked `parcel_zones` rows 868952/868953 by id, independently confirmed the ArcGIS FeatureServer is live, independently confirmed the 3 no-parcel-id residual cases are genuinely null (no silent fabrication). I's 95.1% margin is thin (155 vs 154.85 needed) but real. No B-anomaly found. 4 fix-agent audit rows (17576-17579) + 4 verifier audit rows (17697-17700) written, all `survived:true` except one honestly-logged non-mover.

---

## union — 9/10 (unchanged this session; already fixed to 9/10 in a prior session ~16h earlier)

### Session-start baseline
Prior commit `50da1ecd` (same lineage, ~16h before this session) had already fixed D
66.7%->100% via a real court order. Session-start live state carried into this session
was already 9/10 (only C failing by structural design).

### FINAL fresh live re-check (this close-out session, VERIFIED)
```json
{"A": {"pass": true, "detail": "fc=2 td=1", "metric": 1}, "B": {"pass": true, "detail": "verified=1 closed_sold=1", "metric": 100.0}, "C": {"pass": false, "detail": "matched_clean=2", "metric": 66.7}, "D": {"pass": true, "detail": "matched_any=3", "metric": 100.0}, "E": {"pass": true, "detail": "parcel_linked=3", "metric": 100.0}, "F": {"pass": true, "detail": "tier1_sold=1 closed_sold=1", "metric": 100.0}, "G": {"pass": true, "detail": "density=100.0 far= pk1000=", "metric": 100.0}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 3.1}, "I": {"pass": true, "detail": "card_complete=3 of 3", "metric": 100.0}, "J": {"pass": true, "detail": "deal_complete=3 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100.0}, "county": "union", "V2_LITMUS": null, "auctions_total": 3}
```
**9/10 — only C failing, confirmed structural ceiling.**

### Per-letter table

| Letter | Fixed/Blocked | Action | Rows | Before -> After | Marker | Evidence | Commit |
|---|---|---|---|---|---|---|---|
| C | BLOCKED (structural, evaluator-by-design) | Fresh live re-check only; confirmed prior classification (`CLERK_SSOT_CANCELLED` on case 63-2025-CA-0053) is stable and evaluator-correct; searched for new angle (auction date now past, no superseding clerk activity) — found none | 0 | 66.7% FAIL (unchanged, reconfirmed) | VERIFIED | `multi_county_auctions` row citing Inst-20260001913 (vacate order) and Inst-20260000062 (final judgment); parcel_id 31-05-18-00-000-0101-2, address 9534 NW 44th Lane | n/a (no changes) |
| A,B,D,E,F,G,H,I,J | PASS, unchanged | No action needed — already passing, out of scope | 0 | unchanged | VERIFIED | live RPC re-check for all 9 | n/a |

**Adversarial verify:** CONFIRMED. C's structural-ceiling math independently recomputed from scratch: denominator=3, only 3/3=100% crosses 95%; the vacated/cancelled row structurally cannot become `matched_clean` since no sale occurred. No B-anomaly (1/1, sane ratio). J independently spot-checked across all 3 `bid_decisions` rows (broader than fix-agent's single-case check) — all populated. 1 fix-agent audit row (17575) + 10 verifier audit rows (17675-17684), all `survived:true`.

---

## charlotte — 9/10 (up from 7/10 at session start)

### Session-start baseline
Charlotte started this session at **7/10** (I and D both failing, in addition to C).

### FINAL fresh live re-check (this close-out session, VERIFIED)
```json
{"A": {"pass": true, "detail": "fc=205 td=31", "metric": 31}, "B": {"pass": true, "detail": "verified=22 closed_sold=22", "metric": 100.0}, "C": {"pass": false, "detail": "matched_clean=168", "metric": 71.2}, "D": {"pass": true, "detail": "matched_any=235", "metric": 99.6}, "E": {"pass": true, "detail": "parcel_linked=236", "metric": 100.0}, "F": {"pass": true, "detail": "tier1_sold=22 closed_sold=22", "metric": 100.0}, "G": {"pass": true, "detail": "density=98.2 far= pk1000=100.0", "metric": 98.2}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.0}, "I": {"pass": true, "detail": "card_complete=232 of 236", "metric": 98.3}, "J": {"pass": true, "detail": "deal_complete=236 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100.0}, "county": "charlotte", "V2_LITMUS": null, "auctions_total": 236}
```
**9/10 — only C failing, confirmed structural ceiling.**

### Per-letter table

| Letter | Fixed/Blocked | Action | Rows | Before -> After | Marker | Evidence | Commit |
|---|---|---|---|---|---|---|---|
| I | FIXED | Zone-link + geo + assessed_value + property_address backfill from live Charlotte County ArcGIS "Ownership" layer (agis3.charlottecountyfl.gov MapServer/27) + 6 new `zoning_districts` rows for jurisdiction 813 (RE1, RMF12, RMF15, MMF7.5, MHP, BOZD) verified against official CCGIS zoning legend PDF | 6 zoning_districts + 59 parcel_zones inserted, 48 auction rows patched | 73.3% (173/236) FAIL -> 98.3% (232/236) PASS | VERIFIED | agis3.charlottecountyfl.gov MapServer/27; charlottecountyfl.gov CC zoning-districts PDF | `01e923a8` |
| D | FIXED | Parity-stamped 55 rows already holding real, authoritative `tier1_sale_status`/`tier1_sold_amount` from ingestion runs (never stamped): 6 SOLD->matched_clean, 49 REDEEMED/CANCELED_PER_COUNTY->CLERK_SSOT_CANCELLED | 55 patched | 76.3% (180/236) FAIL -> 99.6% (235/236) PASS | VERIFIED | live DB tier1_* fields | `01e923a8` |
| C | BLOCKED (structural) | Fresh live re-check post-D-fix. Reconfirmed structural ceiling: 67/236 rows genuinely cancelled/redeemed, correctly excluded from `matched_clean` by evaluator design. Spot-checked sample for mislabeling, found none | 0 | 68.6% -> 71.2% (gain only from D's newly-stamped SOLD rows), still FAIL | VERIFIED | live count query: matched_clean=168, CLERK_SSOT_CANCELLED=67, null=1 | `01e923a8` (documented, no data change) |

Residual I gap (4 rows, honestly unfixed): 3 "MULTIPLE PARCELS" foreclosure cases with no single parcel_id (25000748CA, 25001710CA, 25002081CC); 1 row (26-0143) resolves to Punta Gorda's own NR-10 municipal code, deliberately not linked under the county's jurisdiction 813 umbrella to avoid misattribution.

**Adversarial verify:** CONFIRMED all 3 claims. Spot-checked `parcel_zones` id=869033 citation URL (real, queryable, not fabricated); confirmed exactly 59 rows carry the session's source tag; confirmed the 6 new `zoning_districts` rows have `far_regulated`/`density_regulated`/`pk1000_regulated` explicitly false (G-side-effect guard as claimed). D: spot-checked 10 most-recently-updated rows, 9/10 correctly stamped, 1 legitimately untouched (in-progress). C: independently recomputed — even in the impossible best case (1 null row resolves clean), ceiling = 71.6%, still 23.6 points below the 95% bar. No B-anomaly (22/22, sane ratio). 3 fix-agent audit rows (17585-17587) + 3 verifier audit rows (17707-17709), all `survived:true`.

---

## lake — 6/10 (net improvement: I moved closer to threshold, G net positive despite a self-caused mid-session regression that was root-caused and repaired same-session)

### Session-start baseline
```
6/10 passing (A, B, D, F, H, J)
I FAIL 87.6% (120/137)
G FAIL/marginal (pre-session state, not separately snapshotted before this session's writes)
E FAIL 93.4%
C FAIL 88.3%
```

### FINAL fresh live re-check (this close-out session, VERIFIED)
```json
{"A": {"pass": true, "detail": "fc=126 td=11", "metric": 11}, "B": {"pass": true, "detail": "verified=8 closed_sold=8", "metric": 100.0}, "C": {"pass": false, "detail": "matched_clean=121", "metric": 88.3}, "D": {"pass": true, "detail": "matched_any=137", "metric": 100.0}, "E": {"pass": false, "detail": "parcel_linked=128", "metric": 93.4}, "F": {"pass": true, "detail": "tier1_sold=8 closed_sold=8", "metric": 100.0}, "G": {"pass": false, "detail": "density=95.3 far=94.1 pk1000=100.0", "metric": 94.1}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.3}, "I": {"pass": false, "detail": "card_complete=125 of 137", "metric": 91.2}, "J": {"pass": true, "detail": "deal_complete=137 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100.0}, "county": "lake", "V2_LITMUS": {"role": "tertiary_crosscheck", "source": "propertyonion", "status": "ok", "priority": 3, "match_pct": null, "our_count": 98, "sale_type": "foreclosure", "fetched_at": "2026-07-24T08:34:50.337547+00:00", "source_count": 2048}, "auctions_total": 137}
```
**6/10 — A, B, D, F, H, J pass; C, E, G, I fail.**

### Per-letter table

| Letter | Fixed/Blocked | Action | Rows | Before -> After | Marker | Evidence | Commit |
|---|---|---|---|---|---|---|---|
| I | IMPROVED (still FAIL) | Inserted 5 real `parcel_zones` rows via live ArcGIS point-in-polygon (gis.lakecountyfl.gov MapServer/50) for zone_link-only gap rows | 5 written / 8 attempted | 87.6% (120/137) -> 91.2% (125/137), still FAIL | VERIFIED | gis.lakecountyfl.gov live responses (zone codes A, R-7, PUD x2, R-4) | `4e38ae8a` |
| G | FIXED net-positive (with self-caused mid-session regression, repaired) | Root-caused a self-caused regression from the I fix (new R-4 zone with no `zoning_districts` row -> NULL applicability defaults). Created missing district row, set regulated-flags to match sibling Lake residential districts, added density figure | 1 zoning_districts + 1 zone_standards row | 93.8% -> regressed to 66.7% mid-session -> repaired to 94.1%, still FAIL (marginal) | VERIFIED (flags/before-after); INFERRED (density=4.00 du/acre, secondary source zoneomics.com, confidence 0.6 — Municode 403'd, Firecrawl zero credits) | gis.lakecountyfl.gov queries + zoneomics.com Table 3.02.06 | `4e38ae8a` |
| E | BLOCKED (fresh re-check, no new lever) | Re-tried 6 already-exhausted rows + 3 genuinely new rows (BOYD, MAMMON, LMG HOME RENOVATIONS LLC) via lakecopropappr.com owner-search and live clerk calendar | 0 written / 9 attempted | 93.4% unchanged, still FAIL | VERIFIED (all searches genuinely zero/no-match) | lakecopropappr.com live search results, foreclosurecalendar.lakecountyclerkfl.gov | `4e38ae8a` |
| C | BLOCKED (structural ceiling reconfirmed) | Reran docket-recheck script against all 16 `CLERK_SSOT_CANCELLED` rows (fresh 22-day window). Caught and correctly declined a script false-positive (2016CA002108, NULL `parity_checked_at`) after manual review confirmed docket's latest entry is still CANCELLED | 0 written / 16 rechecked | 88.3% unchanged, still FAIL | VERIFIED | courtrecords.lakecountyclerk.org docket API, DB status cross-check | `4e38ae8a` |

Not touched: A, B, D, F, H, J (already passing, out of scope).

**Adversarial verify:** CONFIRMED I (spot-checked 2 of 5 parcel_zones inserts by id, zone codes match exactly). CONFIRMED G (zoning_districts id=14166 exists with density_regulated=true; noted one minor documentation slip — commit text says far_regulated "set to false" but live value is NULL, matching all 6 sibling residential districts' normal state, not a scoring bug). BLOCKED_CONFIRMED E (independently pulled both new named cases, confirmed parcel_id=null live for both — no silently-fabricated parcel_id inflating the metric). BLOCKED_CONFIRMED C (121+16=137, fully reconciles denominator, no unexplained gap; same lever run in 4+ prior lake sessions with same conclusion). No B-anomaly (8/8 both B and F). 4 fix-agent audit rows (17621, 17622, 17633, 17656) + 4 verifier audit rows (17717-17720), all `survived` per their individual claim (movers=true, blocked reconfirmations logged honestly).

---

## martin — 8/10 (up from 6/10 at session start)

### Session-start baseline (orchestrator's precomputed snapshot — later found stale, see below)
```
Orchestrator baseline: C/D FAIL 59.4%, I FAIL 58%
```
**Important finding (documented honestly by the fix agent):** the orchestrator's
precomputed baseline was already stale by the time live investigation began — C/D/I had
independently moved to C/D PASS 95.7%, I FAIL 92.8% due to concurrent shard/pipeline
activity between the snapshot and session start. All deltas below are measured from the
live pre-write state actually observed, not the stale orchestrator snapshot.

### FINAL fresh live re-check (this close-out session, VERIFIED)
```json
{"A": {"pass": true, "detail": "fc=44 td=25", "metric": 25}, "B": {"pass": true, "detail": "verified=1 closed_sold=1", "metric": 100.0}, "C": {"pass": true, "detail": "matched_clean=68", "metric": 98.6}, "D": {"pass": true, "detail": "matched_any=68", "metric": 98.6}, "E": {"pass": false, "detail": "parcel_linked=64", "metric": 92.8}, "F": {"pass": true, "detail": "tier1_sold=1 closed_sold=1", "metric": 100.0}, "G": {"pass": true, "detail": "density=100.0 far= pk1000=", "metric": 100.0}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.0}, "I": {"pass": false, "detail": "card_complete=64 of 69", "metric": 92.8}, "J": {"pass": true, "detail": "deal_complete=69 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100.0}, "county": "martin", "V2_LITMUS": null, "auctions_total": 69}
```
**8/10 — A, B, C, D, F, G, H, J pass; E, I fail on the same structural ceiling.**

### Per-letter table

| Letter | Fixed/Blocked | Action | Rows | Before -> After | Marker | Evidence | Commit |
|---|---|---|---|---|---|---|---|
| C | FIXED | Stamped 2 unmatched_any foreclosure rows (25001144CAAXMX, 25001177CAAXMX) `matched_clean` after confirming both live on martin.realforeclose.com's 09/29/2026 calendar via AJAX harvester | 2 | 95.7% (66/69) -> 98.6% (68/69) PASS | VERIFIED | martin.realforeclose.com AJAX PREVIEW/UPDATE, AUCTIONDATE=09/29/2026 | `342e3bd6` |
| D | FIXED | Same 2-row fix (matched_any includes matched_clean) | 2 | 95.7% -> 98.6% PASS | VERIFIED | same as C | `342e3bd6` |
| E | BLOCKED (structural, reconfirmed 6th+ session) | 3 known NON_REAL_PROPERTY rows unchanged; 2 genuinely new rows also blocked — RealForeclose shows only a placeholder Parcel ID, court.martinclerk.com login-walled, vw.martinclerk.com DNS-unresolvable | 0 | 92.8% (64/69) unchanged, FAIL | VERIFIED | live AJAX harvest placeholder parcel_id; clerk search 200-login-page-only; LandmarkWeb DNS fail | `342e3bd6` (docs only) |
| I | BLOCKED (same ceiling as E) | Parcel_id gate blocks zone_link before it's reachable | 0 | 92.8% (64/69) unchanged, FAIL | VERIFIED | same as E | `342e3bd6` (docs only) |
| J | FIXED | Ran existing proven generator (`scripts/shard14_martin_bay_alachua_j_generator.py`) to batch-fill 21 case_numbers with zero bid_decisions rows | 28 inserted | 69.6% (48/69) -> 100.0% (69/69) PASS | VERIFIED | script stdout: "28 rows inserted" | `342e3bd6` |

**Adversarial verify:** CONFIRMED C/D/J. Independently re-executed the AJAX harvester live (not reused output) against martin.realforeclose.com — confirmed both cases on the 09/29/2026 calendar. Independently queried `bid_decisions` fresh: confirmed 28 rows sharing the same pre-commit timestamp. BLOCKED_CONFIRMED E/I: independently confirmed `vw.martinclerk.com` genuinely NXDOMAIN, `court.martinclerk.com` genuinely redirects to a login gate, and both new rows show literal placeholder parcel_id via a fresh independent script run. One minor phrasing imprecision flagged (fix agent said "5-row ceiling" but only 2 additional clean rows are needed to cross the 95% bar for E/I) — does not change the FAIL verdict. No B-anomaly (1/1). 5 fix-agent audit rows (17712-17716) + 5 verifier audit rows (17747-17751); C/D/J `survived:true`, E/I `survived:false` (reconfirmed-blocked, no metric movement — logged honestly as valuable non-movers, not failures).

---

## Shard-3 rollup

| County | Session-start | Final (this close-out) | Delta | Failing letters |
|---|---|---|---|---|
| flagler | 9/10 | **10/10** | +1 | none |
| union | 9/10 | 9/10 | 0 (already fixed pre-session) | C (structural) |
| charlotte | 7/10 | **9/10** | +2 | C (structural) |
| lake | 6/10 | 6/10 | 0 net letters, but I/G metrics improved | C, E, G, I |
| martin | 6/10 | **8/10** | +2 | E, I (structural) |

Not all 5 counties are 10/10 live -> `exit_reason` = `"timeout"` per instructions (only
`"certified"` if all 5 reach 10/10).

## gold_standard_campaign PATCH — proof

Request: `PATCH $SUPABASE_URL/rest/v1/gold_standard_campaign?id=eq.4927`

Body:
```json
{
  "criteria_passed": {
    "flagler": {"A": true, "B": true, "C": true, "D": true, "E": true, "F": true, "G": true, "H": true, "I": true, "J": true},
    "union": {"A": true, "B": true, "C": false, "D": true, "E": true, "F": true, "G": true, "H": true, "I": true, "J": true},
    "charlotte": {"A": true, "B": true, "C": false, "D": true, "E": true, "F": true, "G": true, "H": true, "I": true, "J": true},
    "lake": {"A": true, "B": true, "C": false, "D": true, "E": false, "F": true, "G": false, "H": true, "I": false, "J": true},
    "martin": {"A": true, "B": true, "C": true, "D": true, "E": false, "F": true, "G": true, "H": true, "I": false, "J": true}
  },
  "criteria_total": 10,
  "exit_reason": "timeout",
  "session_end_at": "2026-08-24T08:47:43Z"
}
```

Response: **HTTP 200**
```json
[{"id":4927,"launched_at":"2026-08-24T08:00:00.366808+00:00","dispatch_id":"8da53925-d806-441f-98c7-db90845f68e6","target_counties":["flagler","union","charlotte","lake","martin"],"brief_excerpt":"SHARD-3: YOUR ASSIGNED SHARD (work ONLY these counties) — loop run 13909:...","loop_run_at_launch":13909,"criteria_passed":{"lake": {"A": true, "B": true, "C": false, "D": true, "E": false, "F": true, "G": false, "H": true, "I": false, "J": true}, "union": {"A": true, "B": true, "C": false, "D": true, "E": true, "F": true, "G": true, "H": true, "I": true, "J": true}, "martin": {"A": true, "B": true, "C": true, "D": true, "E": false, "F": true, "G": true, "H": true, "I": false, "J": true}, "flagler": {"A": true, "B": true, "C": true, "D": true, "E": true, "F": true, "G": true, "H": true, "I": true, "J": true}, "charlotte": {"A": true, "B": true, "C": false, "D": true, "E": true, "F": true, "G": true, "H": true, "I": true, "J": true}},"criteria_total":10,"exit_reason":"timeout","session_end_at":"2026-08-24T08:47:43+00:00"}]
```

Note: `criteria_passed` was `{}` on the existing row (no prior single-county convention to
match), so per-county nesting was used as instructed.

## Note on cron/scoring-job boundaries

Per instructions, `public.gold_standard_loop()` and `public.gold_standard_certify()` were
**not** invoked this session — other shards may be mid-flight concurrently. Cron jobs 109,
111, 115 and the `gold_standard_loop-*` scoring jobs, plus `pencil_dod_evaluate_county`
itself, were not modified. `PropertyOnion` (`data_source='propertyonion'`, visible in
lake's `V2_LITMUS` block) was read-only litmus context, never written to as a source of
truth.

## Files/commits referenced this session (all already on `main`, working tree clean)

- `209b02a2` — flagler I zone-link + C/D litmus fix
- `50da1ecd` — union D parity fix (prior session, ~16h before this session)
- `01e923a8` — charlotte I zone-link/geo/value backfill + D parity stamp
- `4e38ae8a` — lake I zone-link 8-row gap fix
- `342e3bd6` — martin C/D AJAX litmus + J bid_decisions batch-fill

All `gold_standard_ultraloop_audit` rows referenced above (fix-agent + verifier, ids
17575-17579, 17585-17587, 17621-17720 range, 17747-17751) were written during the parallel
fix+verify phase preceding this close-out.
