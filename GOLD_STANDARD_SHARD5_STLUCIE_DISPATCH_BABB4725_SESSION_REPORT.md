# Gold Standard Shard-5: st_lucie — dispatch babb4725-9caa-4d5f-9e1e-e6453f7ca4ee

Session: architect-20260826T080000. County: st_lucie (starting 8/10, C and I failing).

## Result: st_lucie now 9/10 (I fixed, C reconfirmed structural — 7th+ session)

| Letter | Before (live) | After (live) | Change |
|---|---|---|---|
| A | PASS 120 | PASS 120 | unchanged |
| B | PASS 100.0 | PASS 100.0 | unchanged |
| C | FAIL 77.7 (matched_clean=188) | FAIL 77.7 (matched_clean=188) | unchanged — reconfirmed structural via a NEW angle (live acclaim re-scrape) |
| D | PASS 96.3 | PASS 96.3 | unchanged |
| E | PASS 96.7 (parcel_linked=234) | PASS 97.1 (parcel_linked=235) | improved (side effect of I fix) |
| F | PASS 100.0 | PASS 100.0 | unchanged |
| G | PASS 97.0 | PASS 97.1 | improved (zero regression, new zones carry real density standards) |
| H | PASS | PASS | unchanged |
| I | **FAIL 94.6** (card_complete=229/242) | **PASS 96.3** (card_complete=233/242) | **FIXED** |
| J | PASS 97.9 | PASS 97.9 | unchanged |

`auctions_total` grew 237 -> 242 since yesterday's dispatch 2ccd6cc6 close (5 new `calendar_sweep_mca_v3` rows landed between session close and this session's start), which had pushed I back into FAIL territory purely from denominator growth against a fixed numerator.

## What happened

1. **Diagnosed the fresh I gap precisely.** Since PostgREST has no ad-hoc SQL RPC, reconstructed the evaluator's LEFT JOIN (multi_county_auctions -> parcel_zones on parcel_id, checking address/geo/value/zone independently) via direct REST queries rather than trusting the brief's aggregate number blindly. Found exactly 13 failing rows, decomposed into: 8 rows with `parcel_id IS NULL`, 2 known-structural GIS-coverage-gap rows carried over from 2026-08-25 (26-137, 26-197 — not re-attempted, no new lever), and **3 new rows** (2025CA000957, 2025CA002001, 2025CA002273) that turned out to carry a parcel_id format never seen before in this county: a bare St Lucie Property Appraiser **AccountNumber** (e.g. "114487") instead of the usual dash-STRAP.

2. **Fixed 4 of the 13 rows with real, sourced data** (direct execution, not delegated — deterministic once diagnosed):
   - The 3 AccountNumber rows: resolved via `map.paslc.gov` AccountNumber lookup to real STRAP + jurisdiction + market value, then zoning via a **corrected lever** — Port St. Lucie's zoning FeatureServer has 3 layers; the layer used in every prior session (layer 0, "PZ_ZONING_SEU", 326 records) is a small non-citywide subset that produced false coverage-gap results (this explains the 26-066 "coverage gap" documented on 2026-08-25). **Layer 1 ("PZ_ZONING", 1333 records) is the actual full citywide zoning layer** and resolved both PSL points cleanly. Documented in migration `20260826_gold_standard_shard5_stlucie_babb4725_i_accountnumber_zone_fix.sql` for future st_lucie/PSL sessions.
   - Case 26-183: resolved via a live GET+POST round trip against `acclaimweb.stlucieclerk.gov/TributeWeb/` (the same tax-deed search table the existing clerk_ssot parser already scrapes) — found the case directly by case number (not name-inferred), cross-matched to `map.paslc.gov` via Owner1+Owner2 concatenation matching the clerk's owner cell text exactly. Migration `20260826_stlucie_26183_court_docket_parcel_lookup.sql`.
   - G-regression pre-checked live before every write (zone_standards / far_regulated / density_regulated columns) — zero risk confirmed both before and after (G improved 97.0 -> 97.1).

3. **Researched the remaining 8 no-parcel_id rows via a parallel Workflow fan-out** (one agent per case, ULTRALOOP Research phase). Result: 1 of 8 resolved (26-183, applied above); the other 7 are honestly, exhaustively blocked, each independently confirmed this session:
   - `2023CA002852`: the underlying asset is an **aircraft lien** (RealForeclose itself labels it `parcel_id='AIRCRAFT'`), not real property — no STRAP can exist. 6th session to independently reach this exact conclusion via different access paths.
   - `2024CA000330` / `2024CA001834`: both tied to timeshare/HOA plaintiffs ("Vistana Development", "Beach Club Property Owners' Association") — fractional timeshare interests, not discrete STRAP-bearing parcels; RealForeclose's own site labels the sibling case `parcel_id='TIMESHARE'`.
   - `2024CA000214`: genuinely a multi-parcel case (`.mlti1`/`.mlti2` sub-listings confirmed via stlucieforeclosures.com), defendant name undiscoverable through any non-authenticated route (courtcasesearch.stlucieclerk.gov CAPTCHA-gated, acclaimweb/trellis.law 403, stlucieforeclosures.com 403).
   - `2025CA002738` / `2025CC001033`: every known St Lucie docket-search route (Benchmark case search, AcclaimWeb, RealForeclose AJAX, trellis.law, Firecrawl, WebSearch) returned either a genuine image/audio CAPTCHA, a 403 WAF block, or zero indexed results. No honest path forward without solving a CAPTCHA (out of scope).
   - `26-148`: replicated the actual scraper mechanism live — confirmed it still works today for a date with prior data (08/17/2026, 22 items matched), but returns zero items for the target auction date (11/09/2026) — the county has not yet republished item lists for that date, or the specific item was pulled/redeemed since the earlier scrape that captured its date-neighbors (26-145/150/153/159, all already enriched). Genuinely not-yet-available, not a scraper defect.

   None of these were guessed at or approximated — every one carries a specific, checkable reason it cannot be resolved right now (BLANK > WRONG).

4. **C re-confirmed structural with a genuinely new angle, not just repeated prior reasoning.** Live partition of `parity_status`: `matched_clean`=123, `PARITY_OK`=65 -> updated to 63+`CLERK_VERIFIED`=2 (sum=188=C's numerator), `CLERK_SSOT_CANCELLED`=44 (real, clerk-verified cancelled sales — counts toward D but structurally excluded from C's numerator by the evaluator's own deliberate design, confirmed via a fresh read of the live function source), `matched_divergent`=1, `NULL`=9 (all genuinely pending, future auction dates). Even 100% resolution of the 9 NULL + 1 divergent rows only reaches 198/242=81.8%, short of the 230/242 (95%) bar. **New lever attempted and closed off this session**: live-re-scraped `acclaimweb.stlucieclerk.gov` today and cross-checked all 44 `CLERK_SSOT_CANCELLED` case numbers against the live cancelled flag — zero reversals, zero missing from the live feed. Rules out the one plausible remaining hypothesis (a stale cancellation that got rescheduled since the source data was captured). Not a per-county data gap — a canon-level scoring-formula question, correctly out of this dispatch's scope. 7th+ independent session to reach this conclusion.

## ULTRALOOP adversarial verification

Both the I claim and the C reconfirmation were independently re-derived by separate refuter agents (not the agents/session that made the original claims), each re-querying the live DB and live external sources rather than trusting the claiming session's output:
- **I**: `survived=true` — re-ran `pencil_dod_evaluate_county` (byte-exact match), independently re-queried `map.paslc.gov` for the 26-183 STRAP (exact match), confirmed zero regression on A/B/D/F/G/H/J, checked for duplicate/ghost `parcel_zones` rows (none found).
- **C**: `survived=true` — re-ran the live `parity_status` breakdown, read the evaluator's SQL source directly to confirm the C/D exclusion split is deliberate, and executed the new angle described above (live acclaim cross-check of all 44 cancelled cases).

Logged to `gold_standard_ultraloop_audit` ids **18291** (I) and **18292** (C).

## SQL VERIFICATION

```sql
-- BEFORE (session start, live):
-- {"I":{"pass":false,"metric":94.6,"detail":"card_complete=229 of 242"},
--  "C":{"pass":false,"metric":77.7,"detail":"matched_clean=188"},
--  "auctions_total":242}

SELECT public.pencil_dod_evaluate_county('st_lucie');
-- AFTER (2026-08-26T08:31:00Z, live):
-- {"A":{"pass":true,"metric":120,"detail":"fc=120 td=122"},
--  "B":{"pass":true,"metric":100.0,"detail":"verified=2 closed_sold=2"},
--  "C":{"pass":false,"metric":77.7,"detail":"matched_clean=188"},
--  "D":{"pass":true,"metric":96.3,"detail":"matched_any=233"},
--  "E":{"pass":true,"metric":97.1,"detail":"parcel_linked=235"},
--  "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=2 closed_sold=2"},
--  "G":{"pass":true,"metric":97.1,"detail":"density=97.1 far= pk1000="},
--  "H":{"pass":true,"metric":0.0,"detail":"hours since last_seen (SLA 48h)"},
--  "I":{"pass":true,"metric":96.3,"detail":"card_complete=233 of 242"},
--  "J":{"pass":true,"metric":97.9,"detail":"deal_complete=237 (triangle + two-arm CMA + ml_score + max_bid)"},
--  "county":"st_lucie","auctions_total":242}
```

## Migrations shipped (main, live)

- `supabase/migrations/20260826_gold_standard_shard5_stlucie_babb4725_i_accountnumber_zone_fix.sql` (commit `e0292188`)
- `supabase/migrations/20260826_stlucie_26183_court_docket_parcel_lookup.sql` (commit `8fe0e952`)

`gold_standard_campaign` row (id 5062, dispatch_id `babb4725-9caa-4d5f-9e1e-e6453f7ca4ee`) closed out with `criteria_passed` (A,B,D,E,F,G,H,I,J=true, C=false), `criteria_total=10`, `exit_reason='certified_partial_9of10'`, `session_end_at`.

## Next-session priority for st_lucie

Only C remains, and — same conclusion as the 2026-08-25 session, now independently re-verified via a genuinely new check this session — it is not a data-fixable gap under the current evaluator formula. The one remaining hypothesis worth testing (a `CLERK_SSOT_CANCELLED` row that got rescheduled/reversed) was tested live today and came back negative for all 44 rows. Recommend flagging for canon review (should `CLERK_SSOT_CANCELLED` count toward the C/matched_clean denominator, or should C's formula weight D-eligible-but-cancelled rows differently?) rather than continuing per-county C sessions on st_lucie — 7+ independent sessions have now reached the identical structural conclusion from different angles. The 8-row (now 7-row) no-parcel_id residual on I is similarly exhausted for now: re-attempt `2025CA002738`/`2025CC001033`/`2024CA000214` only if a CAPTCHA-solving or authenticated-browser capability becomes available to this pipeline; `26-148` may resolve itself automatically once the county republishes item lists closer to its 2026-11-09 auction date.
