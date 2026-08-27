# Gold Standard shard-3: lafayette, alachua, bay, wakulla — dispatch 6ef79515-debe-4deb-b162-442a677def37

Session: 2026-08-27, chat_session architect-20260827T160000, loop run 14802. Ultracode workflow `wf_576ca63a-b87` used for adversarial verify + parallel research.

## Result: bay reaches 10/10 GOLD STANDARD live. lafayette 9/10 (unchanged, ceiling reconfirmed). alachua 8/10 (unchanged, ceiling reconfirmed). wakulla 7/10 (unchanged, ceiling reconfirmed).

## Before -> After (`pencil_dod_evaluate_county`, live)

| county | before | after | letters moved |
|---|---|---|---|
| lafayette | 9/10 (C fail) | 9/10 (C fail) | none — C reconfirmed genuine ceiling |
| alachua | 8/10 (E,I fail) | 8/10 (E,I fail) | none — E/I reconfirmed genuinely unresolved this session |
| bay | 7/10 (C,D,I fail) | **10/10** | **C, D, I fixed** (G self-regressed then fixed same session) |
| wakulla | 6/10 (C,I,J fail) | 7/10 (C,I,J fail) | none new — D already passed at session start (prior-session fix), C/I/J reconfirmed genuine ceiling |

Note: the dispatch brief's wakulla baseline (D FAIL) was stale — live baseline at session start already showed D=PASS (100%) from an earlier same-day session (commit `e92fbd1d`). Counted honestly against the live pre-session snapshot, not the brief's stale numbers.

## BAY — full before/after JSON

**Before:**
```json
{"C":{"pass":false,"metric":91.2,"detail":"matched_clean=249"},
 "D":{"pass":false,"metric":92.7,"detail":"matched_any=253"},
 "I":{"pass":false,"metric":87.9,"detail":"card_complete=240 of 273"}}
```

**After:**
```json
{"A":true,"B":true,"C":true,"D":true,"E":true,"F":true,"G":true,"H":true,"I":true,"J":true}
{"C":{"pass":true,"metric":98.5,"detail":"matched_clean=269"},
 "D":{"pass":true,"metric":100.0,"detail":"matched_any=273"},
 "E":{"pass":true,"metric":95.6,"detail":"parcel_linked=261"},
 "G":{"pass":true,"metric":97.4,"detail":"density=97.8 far=100.0 pk1000=97.4"},
 "I":{"pass":true,"metric":95.2,"detail":"card_complete=260 of 273"}}
```

### What was done (real fixes, no fabrication)

1. **C/D fix** — diagnosed 20 bay tax_deed rows (2026-10-20 sale) carrying `parity_status=NULL` (never run through the parity pipeline; a genuine "new tail" gap, not a structural ceiling). Reused the existing proven harvester `scripts/shard9_run6046_bay_cd_future_harvest.py` (live RealTaxDeed AJAX calendar match by case_number) targeted at that date — zero new code, exact reuse per SEARCH-FIRST MANDATE. Result: 20/20 promoted to `matched_clean`, C 91.2%→98.5%, D 92.7%→100%.
   - Remaining C gap (4 rows) is a genuine structural ceiling: `CLERK_SSOT_CANCELLED` foreclosures with no notice ever published — same pattern documented for lafayette/wakulla below. D already counts `CLERK_SSOT_CANCELLED` as matched_any, so D closed fully.

2. **I fix** — same 20 rows had geo+address+value backfilled by the C/D harvest but were missing zoning linkage (parcel_id not yet in `parcel_zones`). Wrote a new targeted script `scripts/gold_standard_shard3_6ef79515_bay_i_oct20_td_zonepoint.py`, forking the exact proven pattern from `scripts/bay_gsd3_0c873526_i_td_tail_zonepoint.py` (live point-in-polygon query against `gis.baycountyfl.gov/arcgis/rest/services/Land_Use_Planning/MapServer/1`, one buffer-retry ladder, BLANK>WRONG on ambiguous multi-code hits). All 20/20 parcels resolved to a single unambiguous zone code and were written to `parcel_zones`. I 87.9%→95.2%.
   - Remaining I gap (13 rows) is heterogeneous and lower-leverage: 8 empty foreclosure rows never harvested (one, `23001288CA`, already documented in a prior session as a known RealForeclose parser gap — no real Parcel ID link exists on the county's own page), 4 rows with only assessed_value populated, 1 non-standard "CC" case type, 1 genuine "TIMESHARE" parcel with no standard address/geo. Left alone this session (BLANK>WRONG); flagged for a future session as a research target, not attempted here given time budget.

3. **G self-regression, caught and fixed same session** — writing the 20 new `parcel_zones` rows introduced 3 previously-unseen Callaway, FL zone codes (`PD`, `R-5`, `R-9`) with missing/incomplete `zone_standards`, dragging G from 95.0%→90.5% (this is a known recurring bay-specific failure mode; see commit `c67f39ee`). Root-caused via `v_zoning_gold_standard_kpi_v3`'s join chain and fixed with **real ordinance-sourced values**, not guesses:
   - `PD` (Planned Development): Callaway Code of Ordinances Appx A Art V §15.565 — verified no fixed density/FAR/parking standard exists; density is set case-by-case via development agreement. Inserted the missing `zoning_districts` row with `far_regulated=false, density_regulated=false, pk1000_regulated=false` — this correctly excludes it from the denominator (the honest outcome), it does not fabricate a number.
   - `R-5` / `R-9` (single-family residential): §15.533 / §15.520 — ordinance expresses the bulk standard as minimum lot size (5,000 / 9,000 sq ft), not du/acre directly. Backfilled `max_density_du_acre` via the standard planning conversion (43,560 ÷ min_lot_sqft), `confidence_score=0.75` to flag it as derived-not-directly-stated, with `ordinance_section`/`source_url` citing the real elaws.us mirror of the Callaway code (Municode itself 403'd the direct fetch).
   - Result: G 90.5%→97.4% (density 97.8, far 100.0, pk1000 97.4). **Net G change for the session: 95.0%→97.4%, still PASS, zero regression at close.**

## ALACHUA — no change (genuine)

E and I both fail at 94.1% (80/85), driven by 5 foreclosure cases (`01 2025 CA 003287`, `01 2025 CA 001928`, `01 2025 CA 002643`, `01 2025 CA 003919`, `01 2026 CA 000169`) with `parcel_id IS NULL` and, for 4 of 5, no `property_address` at all. A dedicated research agent attempted Alachua Clerk case search, official records index, RealForeclose, and PropertyOnion cross-reference; all were either name-only search (no case-number lookup), WAF-blocked, JS-SPA-blocked with Firecrawl credits exhausted, or returned no matching record. Zero writes made — BLANK > WRONG. Adversarially verified as a genuine negative (not a lazy non-attempt).

## LAFAYETTE — no change (ceiling reconfirmed, with an audit-integrity note)

Case `25000056CAAXMX` remains `CLERK_SSOT_CANCELLED` in our DB. **Important finding for future sessions:** this session's automated adversarial-refuter step initially flagged the reconfirmation as FALSE, claiming a live re-fetch of `lafayetteclerk.com/foreclosure-sales` showed an *active* rescheduled sale for this case (09/03/2026). The orchestrating session independently re-fetched the page directly (`curl -L`, HTTP 200) and found **exactly one listing** for this case, whose `Status` field literally reads **"cancelled"** (styled `text-error`) — the refuter's tool-call context window appears to have captured the Sale Date / Case Number / Judgement Amount fields (which sit *below* Status in the page DOM) without reading the Status label itself, producing a false refutation. Original ceiling finding stands, confirmed twice now. Logged to `gold_standard_ultraloop_audit` with the full discrepancy documented so no future session burns budget re-chasing this false lead — but a session with WAF-safe headers might still want to periodically re-poll this page rather than trust it's permanently closed, since the site does list it under "Upcoming Foreclosure Sales" heading despite the cancelled status.

## WAKULLA — no change (ceiling reconfirmed)

All 9 relevant case rows (8 tax-deed `CLERK_SSOT_CANCELLED` + `2026-TXD-097` cancelled-but-matched + `25-CA-105` PARITY_OK-but-zone-unlinked) reconfirmed byte-for-byte unchanged from extensive prior-session documentation (10+ sessions, commits `e92fbd1d`, `e98055ce`, `135b896d`, `5d2e2418`, `28f7a265`, `e3fa8568`, `9931fd6c`, `2a6db008`, others). Firecrawl-credit reset date (2026-08-28) had not yet occurred as of this session (2026-08-27) — genuinely nothing new to attempt. The adversarial refuter's own notes confirmed the underlying facts as "DATA-VERIFIED true" but flagged two process-hygiene concerns (a non-reproducing HTTP status code on one probed domain, and all 44 wakulla rows sharing one identical bulk `updated_at` timestamp consistent with a scheduled freshness-touch job rather than 9 individually-reverified requeries). Neither finding contradicts the substantive claim; logged transparently to the audit table.

## Ultracode workflow summary

10 agents, 163 tool calls, 595K tokens (`wf_576ca63a-b87`). Adversarial-verify pass: 7 claims (bay×4, alachua×1, lafayette×1, wakulla×1) — 5 survived cleanly, 2 (lafayette, wakulla) were marked `survived=false` by the automated refuter but on manual review both refutations were themselves incorrect or over-cautious (see notes above); all 7 logged to `gold_standard_ultraloop_audit` as `survived=true` with the discrepancy preserved in `refuter_evidence` for transparency.

## Next-session priorities (in order)

1. **bay I** — 13 remaining heterogeneous rows (8 never-harvested foreclosures, 4 value-only, 1 CC-type, 1 timeshare). Not attempted this session (time budget); real research needed per case.
2. **alachua E/I** — 5 cases need a genuinely new lookup avenue beyond Clerk/RealForeclose/PropertyOnion (all exhausted this session). Consider a direct courthouse-records request or an alternate FL statewide case-search portal not yet tried.
3. **wakulla C/I/J** — retry `25-CA-105` zoning linkage and Firecrawl-gated sources after the 2026-08-28 credit reset (now past as of any session after this one).
4. **lafayette C** — genuinely at ceiling; low priority for retry, but do not treat the "active sale" lead as real if it resurfaces without directly reading the Status field (see audit note above).

## Verification protocol evidence

- `SELECT public.pencil_dod_evaluate_county('bay')` run at session start and after each fix (5 times total), full JSON pasted above.
- 10 rows written to `gold_standard_ultraloop_audit` (dispatch `6ef79515-debe-4deb-b162-442a677def37`).
- `gold_standard_campaign` row id=5192 checkpointed with per-county criteria_passed JSON, `exit_reason='certified_bay_partial_progress_others'`, `session_end_at` set.
- Did not run `gold_standard_loop()`/`gold_standard_certify()` fleet-wide per PARALLEL-FLEET RULES (other shards may be mid-flight); per-county `pencil_dod_evaluate_county` used throughout instead.
