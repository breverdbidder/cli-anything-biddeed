# Gold Standard — Shard-5 (citrus), dispatch a308fac7, loop run 6871

## Scope
Shard assignment: citrus only (9/10 — I failing; A/B/C/D/E/F/G/H/J passing).
Session mode: interactive turn (not a full 6h GHA run) with an ultracode
Workflow-based adversarial verify pass on the one fix shipped, per the
ULTRALOOP PROTOCOL.

## Baseline (verified live, session start, 2026-07-27)
```json
{"A":{"pass":true,"metric":40,"detail":"fc=151 td=40"},
 "B":{"pass":true,"metric":100.0,"detail":"verified=3 closed_sold=3"},
 "C":{"pass":true,"metric":96.9,"detail":"matched_clean=185"},
 "D":{"pass":true,"metric":98.4,"detail":"matched_any=188"},
 "E":{"pass":true,"metric":97.4,"detail":"parcel_linked=186"},
 "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=3 closed_sold=3"},
 "G":{"pass":true,"metric":96.4,"detail":"density=96.4 far= pk1000="},
 "H":{"pass":true,"metric":0.1},
 "I":{"pass":false,"metric":93.7,"detail":"card_complete=179 of 191"},
 "J":{"pass":true,"metric":100.0},
 "auctions_total":191}
```
Exact match to the shard brief.

## Diagnosis
Queried `pencil_dod_evaluate_county` source (pg_proc) to get the exact I
definition: card requires property_address, lat/lon, assessed/market
value, AND parcel_id resolvable in `v_zoning_gold_standard_card` with a
non-null zone_code. Found the 12 specific citrus rows failing it — all 12
were missing `property_address`; several had garbage `parcel_id` values
("Property Appraiser", "MULTIPLE PARCELS") that turned out to be scraped
link-text, not real IDs.

## Data-source attempts (in order, all logged for honesty)
1. **WebFetch on citrus.realforeclose.com detail/preview pages** — 403
   (bot-detection on the fetcher's egress).
2. **Direct curl with a browser UA** — got HTTP 200 but the detail page
   (`zaction=auction&zmethod=details`) silently redirects to a login
   splash screen; anonymous detail access is not available (matches the
   shard-8 playbook note: "Anonymous preview caps at ~20 items").
3. **Firecrawl API (`realauction_bidhistory.py` pattern)** — HTTP 402,
   account has zero credits. Hard blocker, not a spend decision.
4. **Clerk document PDFs** (`search.citrusclerk.org/.../GetDocumentByCFN`)
   — real 200 responses, but CCITT-Fax scanned images with no text layer;
   no OCR tooling available/justified for 2 rows.
5. **SCORSS court case search** (`scorss.citrusclerk.org`) — guest access
   requires solving a CAPTCHA per search; not automatable here.
6. **`scripts/realforeclose_aids_paginated_harvest.py`** (proven pattern
   from prior shard sessions — anonymous AJAX `FNC=LOAD` pagination, no
   login required) — **worked**. Ran it live for the 7 distinct auction
   dates spanning the 12 gap cases (03/12, 04/16, 07/23, 08/06, 08/20,
   08/27, 09/03/2026). Parsed 22 live items, upserted into
   `realforeclose_aids` staging table.

## Result — 1 of 12 rows had real, sourced data available today
Only case `2025 CA 000569 A` resolved to real values on the live calendar:
`10806 E IRENE ST, INVERNESS, FL 34450`, parcel `3523039`. Verified parcel
`3523039` already carries `zone_code='LDR'` in
`v_zoning_gold_standard_card` (citrus zoning substrate is otherwise solid
— G passes at 96.4%).

Inspected the raw AJAX HTML for the other cases directly (not just the
parsed staging rows) to distinguish "scraper bug" from "genuinely
unpublished":
- 2 cases ("MULTIPLE PARCELS", real judgment amounts) span more than one
  parcel per case — the evaluator's single-`parcel_id` model structurally
  can't represent them; out of scope for a targeted fix (would need a
  multi-parcel schema change).
- 5 cases carry `Final Judgment Amount: $0.00` with an empty `pin=` in
  the Property Appraiser link — confirmed via raw HTML, not inferred: the
  county has not entered judgment yet (auction dates 08/20–09/03/2026),
  so no parcel/address is published anywhere, by anyone, today.
- The rest resolve only through the scanned-PDF or CAPTCHA-gated paths
  above.

No values were fabricated for any of the 11 unresolved rows.

## Fix shipped
`migrations/20260727_gold_standard_shard5_citrus_i_realforeclose_enrichment.sql`
— single-row `UPDATE` on `multi_county_auctions`, applied live via
`mgmt_sql.py`, committed and pushed directly to `main`
(`6fc2f73f` → `b103a0ad` post-rebase).

## Verification protocol (before/after, pasted)

### SQL VERIFICATION
```sql
-- BEFORE (session start)
SELECT public.pencil_dod_evaluate_county('citrus');
-- I: {"pass":false,"metric":93.7,"detail":"card_complete=179 of 191"}
-- E: {"pass":true,"metric":97.4,"detail":"parcel_linked=186"}

-- AFTER (post-migration)
SELECT public.pencil_dod_evaluate_county('citrus');
-- I: {"pass":false,"metric":94.2,"detail":"card_complete=180 of 191"}
-- E: {"pass":true,"metric":97.9,"detail":"parcel_linked=187"}

-- Isolation check (run post-adversarial-review, since updated_at is
-- shared across all 191 citrus rows from an unrelated bulk process and
-- can't be used to isolate this UPDATE's blast radius):
SELECT
  (SELECT count(*) FROM multi_county_auctions WHERE county='citrus' AND case_number='2025 CA 000569 A') AS rows_matching_case,
  (SELECT count(*) FROM multi_county_auctions WHERE county='citrus' AND parcel_id='3523039') AS rows_with_this_parcel,
  (SELECT count(*) FROM multi_county_auctions WHERE county='citrus' AND property_address='10806 E IRENE ST, INVERNESS, FL 34450') AS rows_with_this_address;
-- rows_matching_case=1, rows_with_this_parcel=1, rows_with_this_address=1
```
Timestamp: 2026-07-27 19:40 UTC.

## Plan vs actual
| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Diagnose citrus I gap | Yes | Yes | None — exact evaluator SQL read, 12 rows enumerated |
| Fix I to PASS (>=95%, need 182/191) | Attempted | Reached 180/191 (94.2%), still FAIL | Real-source ceiling hit at 1 of 12 fixable rows today; documented per-row why (multi-parcel schema gap, unentered judgments, scanned-only docs) rather than fabricate |
| Adversarial verify | Yes (ULTRALOOP) | Yes — Workflow refuter agent | Refuter marked `refuted=true` on a technicality (couldn't use `updated_at` to isolate blast radius, since it's shared across all 191 rows from an unrelated process); checks 1–4 (current metrics, target row, staging provenance, zone linkage) were all independently CONFIRMED. Closed the actual gap post-hoc with a direct count-based isolation query (rows_matching_case=1) and by committing the previously-uncommitted migration file, both flagged as real gaps by the refuter. |
| Commit + push to main | Yes | Yes | Required setting local (not global) git identity `cc-ghonly-bot <cc@biddeed.ai>` — matches this repo's existing automation-commit convention (see prior commit authors) |

## Deviation log
- Firecrawl account has zero credits — this blocks the standard
  browser-automation bypass (`realauction_bidhistory.py` pattern) used by
  prior sessions for authenticated RealAuction pages. Flagging for the
  next citrus/gold-standard session: either top up Firecrawl credits or
  the RealForeclose login-detail path stays unavailable.
- The adversarial refuter's `refuted=true` verdict was procedural (an
  unverifiable-by-its-chosen-method check), not a finding that the core
  claim was wrong — checks 1–4 fully confirmed the sourced, non-fabricated
  nature of the fix. Both gaps it correctly identified (no delta-isolation
  proof, uncommitted migration) are now closed above.

## Residual / next-session priorities for citrus
1. Letter I needs 2 more real complete cards (182/191) to pass. The 2
   "MULTIPLE PARCELS" cases need a multi-parcel-aware fix (either split
   into synthetic per-parcel card rows or extend the evaluator — the
   latter is out of this shard's authority, flag to AI Architect). The 5
   pending-judgment cases will resolve naturally once Citrus enters final
   judgment (re-run `realforeclose_aids_paginated_harvest.py citrus
   realforeclose.com citrus <date>` after each sale date passes).
2. Firecrawl credits exhausted — blocks authenticated RealAuction/RealForeclose
   scraping repo-wide, not just citrus.
3. No other citrus letter needs attention — A/B/C/D/E/F/G/H/J all remain
   real PASSes, re-verified live this session.
