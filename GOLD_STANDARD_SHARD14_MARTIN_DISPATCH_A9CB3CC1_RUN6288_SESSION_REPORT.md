# Gold Standard shard-14 — martin (loop run 6288)

dispatch_id `a9cb3cc1-eda1-4a56-9a53-dedf15803742`, chat_session `architect-20260725T000000`.
Method: ULTRALOOP PROTOCOL, native mode — one `Workflow` fan-out of 3 independent adversarial
refuters, one of which caught a real defect that was fixed live and independently re-verified
by a follow-up agent before being counted as survived.

## Scoreboard (`pencil_dod_evaluate_county`, before → after, live-verified)

| Letter | Before | After | Note |
|---|---|---|---|
| A | PASS 1 | PASS 1 | unchanged |
| B | PASS 100.0 | PASS 100.0 | unchanged |
| C | FAIL 94.7 (36/38) | **PASS 97.4 (37/38)** | fixed |
| D | FAIL 94.7 (36/38) | **PASS 97.4 (37/38)** | fixed |
| E | FAIL 92.1 (35/38) | FAIL 92.1 (35/38) | unchanged — re-confirmed structurally blocked |
| F | PASS 100.0 | PASS 100.0 | unchanged |
| G | PASS 100.0 | PASS 100.0 | unchanged — held through I-letter zoning insert |
| H | PASS 0.0 | PASS 0.0 | unchanged (freshness) |
| I | FAIL 86.8 (33/38) | FAIL 92.1 (35/38) | real progress, not yet passing — capped by E |
| J | PASS 97.4 | PASS 97.4 | unchanged |

**6/10 → 8/10.**

Before (live, session start, matches dispatch brief exactly):
```json
{"A":{"pass":true,"metric":1,"detail":"fc=37 td=1"},"B":{"pass":true,"metric":100},
"C":{"pass":false,"metric":94.7,"detail":"matched_clean=36"},"D":{"pass":false,"metric":94.7,"detail":"matched_any=36"},
"E":{"pass":false,"metric":92.1,"detail":"parcel_linked=35"},"F":{"pass":true,"metric":100},
"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":0},
"I":{"pass":false,"metric":86.8,"detail":"card_complete=33 of 38"},
"J":{"pass":true,"metric":97.4},"county":"martin","auctions_total":38}
```

After (live, 2026-07-25):
```json
{"A":{"pass":true,"metric":1,"detail":"fc=37 td=1"},"B":{"pass":true,"metric":100},
"C":{"pass":true,"metric":97.4,"detail":"matched_clean=37"},"D":{"pass":true,"metric":97.4,"detail":"matched_any=37"},
"E":{"pass":false,"metric":92.1,"detail":"parcel_linked=35"},"F":{"pass":true,"metric":100},
"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":0},
"I":{"pass":false,"metric":92.1,"detail":"card_complete=35 of 38"},
"J":{"pass":true,"metric":97.4},"county":"martin","auctions_total":38}
```

## C/D: fixed (94.7% → 97.4%, 36/38 → 37/38)

Diagnosed the exact gap: 2 of 38 rows lacked a `tier1%`-sourced `matched_clean`/`matched_divergent`
parity status — case `25000316CAAXMX` (foreclosure, 2026-07-30, `parity_status` NULL, never
harvested) and `2024-001-TD-MARTIN` (tax_deed, 2026-08-15, `parity_status='mca_only'`).

Reused the fleet's proven AJAX RealAuction/RealTaxDeed harvester
(`scripts/shard2_run2450_ajax_realforeclose_harvest.py`), wrapped in a dispatch-scoped script
(`scripts/shard14_martin_9d22d82f_run6288_cd_e_i_fix.py` — filename typo carried the prior
dispatch's short id, functionally scoped to this dispatch's `a9cb3cc1` label; flagging rather
than silently renaming after the fact) with its own `tier1:shard14_a9cb3cc1_run6288_ajax_harvest`
label (learning from the 2026-07-18 session's caught mislabel bug — this session's label was
dispatch-scoped from the start).

- `25000316CAAXMX`: live harvest of `martin.realforeclose.com` for `AUCTIONDATE=07/30/2026`
  found the case (3 calendar items that date), promoted to `matched_clean`.
- `2024-001-TD-MARTIN`: live harvest of `martin.realtaxdeed.com` for `AUCTIONDATE=08/15/2026`
  returned 0 items — same finding as the 2026-07-18 session's attempt at this exact date. The
  sale is 3+ weeks out; tax-deed calendars appear to post later than foreclosure calendars.
  Left unmatched, not fabricated. **Residual C/D gap (1 of 38).**

**Adversarial refuter caught a real defect, fixed live, re-verified independently.** The first
refuter pass on the `25000316CAAXMX` fix returned `refuted=true`: the case appears in
`martin.realforeclose.com`'s "Closed or Canceled" bucket, and the row's own
`tier1_sale_status='CANCELED_PER_COUNTY'` field (set by a later, independent tier1 check) had
never been reconciled into `auction_status`, which was left stuck at `'upcoming'`. The refuter
found this was not a one-off — a second martin row (`25002772CCAXMX`, matched by a prior
session) had the identical stale mismatch. Fixed live: both rows' `auction_status` patched from
`'upcoming'` to `'cancelled'` (the fleet's existing canonical spelling for this field).
`parity_status='matched_clean'` was deliberately **not** reverted — the case number genuinely
matches a real, verifiable county calendar record; a canceled auction is still a real court case
correctly identified, and `parity_status` measures identity-match correctness, not
sale-schedule liveness. A second, independent follow-up agent (not the one that made the fix)
re-verified: 0 remaining martin rows with the mismatch, C/D reconfirmed PASS 97.4% live, and
explicitly endorsed the parity_status-vs-auction_status separation-of-concerns reasoning as
correct rather than a rationalization. This is exactly the failure class the ULTRALOOP protocol
exists to catch — a claim that was technically accurate but materially incomplete.

## I: real progress, not yet passing (86.8% → 92.1%, 33/38 → 35/38)

Diagnosed the exact 5-row gap: the same 3 NULL-`parcel_id` rows blocking E (structurally
unreachable, see below), plus 2 rows independently fixable this session:

**`25000442CAAXMX` (fixed):** carried a garbage `parcel_id` literal string `'Property
Appraiser'` — a known, already-documented fleet-wide AITEM-decoder parser artifact (89 rows
fleet-wide per `scripts/shard14_martin_bay_alachua_lake_cd_e_i_fix.py`'s `is_real_parcel_id()`
helper, and independently confirmed this exact failure class in `baker` county earlier the same
day per `supabase/migrations/20260725_shard2_baker_property_appraiser_purge_executed.sql`).
Repaired to the real parcel_id `19-37-41-000-000-00520-7`, verified via an exact
address/lat/lon/assessed_value match against a different martin row (`25002267CCAXMX` — the
same physical property under a separate case number, already zoned `B-1` in
`v_zoning_gold_standard_card`). Independently re-verified by an adversarial refuter (survived).

**`25000316CAAXMX` (fixed):** parcel `55-38-41-311-000-00050-0` (659 SW Glen Crest Way, Stuart)
had no lat/lon and no zoning linkage. Geocoded via the free US Census geocoder (real
government address-point data). Point-in-polygon queried against Martin County's own live
ArcGIS zoning layer
(`geoweb.martin.fl.us/arcgis/rest/services/Administrative_Areas/Administrative_Areas/MapServer/8`)
— confirmed unincorporated (empty Municipal Boundaries hit) — returned `ZONING='COR-2'`. No
existing `COR-2` district in the DB. Recovered real dimensional/setback standards from Martin
County LDR Table 3.12.1 (Dimensional Standards) and Table 3.12.2 (Structure Setbacks) via
Municode, using the Playwright-rendered access path a prior martin session documented as
working (static `WebFetch` 403s this Angular SPA; a real Chromium page load does not).
`max_density_du_acre=10.00` (Max. Res. Density column, double-checked against the adjacent Max.
Hotel Density=20.00 column to avoid a column-misread), `max_lot_coverage_pct=40`,
`min_lot_sqft=10000`, `max_height_ft=30`, `front/rear/side_setback_ft=25/20/10` (story-1 values,
matching the fleet's established convention). `far_regulated=false` and `pk1000_regulated=false`
set explicitly, backed by a full-page text search confirming zero "FAR"/"floor area
ratio"/"per 1,000" mentions anywhere on the fetched page — following the exact precedent (and
avoiding the exact regression) documented from this same county's B-1 district fix in the
2026-07-19 2nd-firing session. Inserted `zoning_districts` id 12864, `zone_standards` id 5326,
`parcel_zones` id 845382. **G reconfirmed PASS 100.0 immediately after insert, no regression.**
Independently re-verified by an adversarial refuter (survived) — every fetched value
(ArcGIS zone, Census coordinates, Municode table values, all 4 inserted-row contents)
independently reproduced exactly.

**Residual gap (3 of 38, unchanged): the same 3 NULL-`parcel_id` rows blocking E.** I is now
purely capped by E — resolves automatically if/when E's blocker clears, exactly as every prior
martin session (2026-07-18, 2026-07-19 x2) predicted and documented.

## E: re-confirmed unchanged (92.1%, 35/38) — genuinely blocked

Same 3 case numbers as every prior session (`23001555CCAXMX`, `25001632CCAXMX`,
`25001634CCAXMX`) — zero metadata beyond a generic city-level address. Per HONESTY PROTOCOL
guidance against redundant re-investigation of an already-exhaustively-documented blocker (3
prior sessions, 8+ distinct access methods: courthouse CAPTCHA, Landmark Web login wall,
RealForeclose 403, KBForeclosures no match, exact-string web search, UniCourt 405), this session
did **one** fresh, light probe rather than repeating the full investigation: re-fetched
`court.martinclerk.com/Home.aspx/Search` live — still returns the CAPTCHA form field, unchanged.
No new avenue attempted. Manual Clerk records request (`RecordRequest@martinclerk.com`,
$1/page) remains the only documented remaining path, out of scope for automated sessions.

## Honesty markers

- All C/D/E/G/I numbers above are **VERIFIED** — read live from `pencil_dod_evaluate_county`
  before every write, immediately after every write, and again at session close.
- The C/D fix's `auction_status='cancelled'` correction is a genuine, real data-integrity fix
  (synced to an already-known `tier1_sale_status` field, nothing invented) — not a workaround to
  force a pass. `parity_status` was deliberately left unchanged with reasoning independently
  endorsed by a follow-up verifier, not unilaterally decided.
- The I fix's COR-2 zone/standards values are backed by primary ordinance text fetched and
  quoted directly this session (Municode Table 3.12.1/3.12.2, via the Playwright access path),
  independently re-fetched and corroborated by an adversarial refuter using the exact same live
  sources, not trusting the claim's own numbers.
- `far_regulated`/`pk1000_regulated` were set `false` only after a full-page negative-evidence
  search (zero FAR/per-1000 mentions), matching this county's own established B-1 precedent —
  the G-regression failure mode a prior martin session self-caught is explicitly what this
  session avoided repeating.
- The garbage `parcel_id='Property Appraiser'` bug is a known, previously-documented fleet-wide
  parser artifact (independently reconfirmed the same day in `baker` county by a different
  shard) — not a new discovery, but a known-pattern fix applied correctly to this county's one
  instance.
- 1 of 3 adversarial claims was genuinely **refuted** on first pass (not silently accepted) —
  the defect was fixed live and re-verified by a second, independent agent before being written
  to the audit trail as survived. This is exactly the failure class the ULTRALOOP PROTOCOL's
  adversarial-survival-vote layer exists to catch.
- 3 `gold_standard_ultraloop_audit` rows written (ids 9721-9723, dispatch
  `a9cb3cc1-eda1-4a56-9a53-dedf15803742`), all `survived=true` (post-fix, for the C claim).
- Did not run `gold_standard_loop()`/`gold_standard_certify()` at close-out — other shards'
  commits landed on `main` during this session (confirmed via `git pull --rebase` mid-session),
  per PARALLEL-FLEET RULES. Reported per-county `pencil_dod_evaluate_county` only.

## Fleet-wide finding (flagged, not fixed beyond martin's 2 rows)

The `tier1_sale_status='CANCELED_PER_COUNTY'` vs `auction_status='upcoming'` staleness pattern
found in martin exists **fleet-wide**: a live sweep at discovery time found 43 rows across all
counties with this exact mismatch (martin's 2 were fixed this session; the other 41 belong to
other counties and were deliberately left untouched per PARALLEL-FLEET RULES — never touch
another shard's counties). This looks like a gap in whatever pipeline sets `tier1_sale_status`
not cascading to `auction_status` — worth a fleet-wide follow-up session or a small trigger/cron
addition (not cron 109/111/115, which are off-limits per HARD GUARDRAILS) rather than 40+
county-by-county manual patches.

## Next-session priorities

1. **martin E**: unchanged, confirmed structurally blocked (CAPTCHA), single fresh re-probe
   this session found no change. Manual Clerk records request is the only remaining path.
2. **martin I**: automatically resolves toward PASS the moment E's blocker clears — no further
   zoning work needed for this county (COR-2 was the last movable zoning gap).
3. **martin C/D residual (1 row)**: `2024-001-TD-MARTIN`'s tax-deed calendar (2026-08-15) still
   returns 0 live items — retry closer to the sale date; tax-deed calendars appear to post later
   than foreclosure calendars for this county.
4. **Fleet-wide `tier1_sale_status`/`auction_status` reconciliation** (41 rows outside martin):
   flagged above, out of this session's county scope.
