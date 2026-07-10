# GOLD STANDARD SHARD-1 — run3534 Session Report

dispatch_id: `1f71eee0-d919-4a62-826e-1daf17eb627b`
chat_session: `architect-20260710T080000`
Shard counties: brevard, broward, nassau, suwannee, sumter
Mode: ULTRALOOP fallback (manual fan-out — `/effort ultracode` menu not available in this
session's harness; findings still logged to `gold_standard_ultraloop_audit` per protocol §1).

## Scope note (read first)

This session ran as a single bounded turn, not a literal 6-hour GHA job. Rather than
attempt shallow work across all 50 (county×letter) cells, it went deep on a small number
of genuinely verifiable fixes and stopped rather than fabricate progress on the rest.
**Honesty over coverage**, per this repo's own HONESTY PROTOCOL and the repeated
ghost-success incidents in its git history (nassau, santa_rosa, pasco — see below, suwannee
is now added to that list).

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Diagnose all 5 counties live | Yes | Yes (via `pencil_dod_evaluate_county` REST RPC + `supabase db query --linked` direct SQL) | None |
| Fix brevard highest-leverage gap | Investigate | **Shipped**: C 94.9%→95.0%, brevard now live 10/10 | Faster than expected — was a mislabeling, not new data collection |
| Fix suwannee | Investigate C/D/I gaps | **Found and reverted a ghost-success incident instead** (2 fully fabricated FC rows backing B/F) | Scope changed: this was higher priority than the originally-targeted C/D/I gaps once found |
| Fix sumter | Investigate C/D/E/I/J | Backfilled real TD case_number (7/7 rows, verified via live clerk fetch); FC gap row left UNTESTED (genuinely no data published) | Groundwork only — did not flip a letter, reported honestly |
| Fix broward A/I | Investigate | Diagnosed I gap composition; attempted real BCPA lookup, found parcel/address mismatch, **stopped without writing** | Did not ship a fix — data integrity risk outweighed the metric gain |
| Fix nassau C | Investigate 1-row gap | Diagnosed: remaining 2 non-passing rows stem from the already-known nassau B/F fabrication revert (source unrecoverable) — not safely fixable this session | No fix shipped, correctly left as-is |
| Run `gold_standard_loop()` / `certify()` | Only if no other shard mid-flight | Skipped — PARALLEL-FLEET RULES; per-county eval only | As directed |

## Before/After — live `pencil_dod_evaluate_county()`

### brevard: 9/10 → **10/10**
```
BEFORE: {"A":true(906),"B":true(98.6),"C":false(94.9),"D":true(95.4),"E":true(99.2),"F":true(98.9),"G":true(99.7),"H":true(4.4),"I":true(96.3),"J":true(99.5)}
AFTER:  {"A":true(906),"B":true(98.6),"C":true(95.0),"D":true(95.5),"E":true(99.2),"F":true(98.9),"G":true(99.7),"H":true(4.6),"I":true(96.3),"J":true(99.5)}
```
Fix: 8 rows' `parity_source` renamed `realforeclose_aids_patch` → `tier1_realforeclose`
(migration `supabase/migrations/20260710_shard1_run3534_brevard_c_tier1_prefix_fix.sql`).
These were already genuine matches from `realforeclose_aids_to_mca_patch()` against the
independent `realforeclose_aids` table — the same relabel was already applied to
martin/pasco/gulf in `20260628_parity_source_tier1_prefix_17counties.sql` but missed
brevard. No underlying match data changed, only a label correcting an evaluator
`LIKE 'tier1%'` miss. **Not yet certified** — certify gate requires fresh `survived=true`
audit rows for all 10 letters within 7 days; only C has a fresh row from this session.

### broward: 8/10 (unchanged)
```
{"A":false(0, fc=635 td=0),"B":true(100),"C":true(99.1),"D":true(99.4),"E":true(99.5),"F":true(100),"G":true(98.9),"H":true(1.8),"I":false(91.3, 580/635),"J":true(97.6)}
```
No fix shipped. A requires a real tax-deed lane (broward currently has zero TD rows —
bigger scraper-build task, not attempted this session). I gap (55 rows) diagnosed:
9 missing address, 24 missing geo, 28 missing value, 27 missing zoning-card linkage
(overlapping). Attempted a real Broward Property Appraiser (BCPA) lookup for the 3
resolvable full-folio rows; folio `514120150370` returned address "10000 SW 9 Court,
Pembroke Pines" via BCPA's live RecInfo page, but our row for that folio has
"6466 NW 80 TER" — a genuine parcel_id/address mismatch. Writing the BCPA value would
have attached a dollar figure to what may be the wrong property, so **no write was made**.
Flagging this mismatch for the next session rather than guessing.

### nassau: 7/10 (unchanged)
```
{"A":true(5),"B":false(null),"C":false(94.1, 32/34),"D":true(100),"E":true(97.1),"F":false(null),"G":true(100),"H":true(1.5),"I":true(97.1),"J":true(100)}
```
No fix shipped. The 2 non-clean rows carry
`parity_source='tier1_bf_fabrication_revert_shard12_20260704_original_source_not_recoverable'`
— the residue of the prior nassau B/F fabrication revert
(`scripts/shard12_run2753_nassau_bf_fabrication_revert.py`), whose original source could
not be recovered. Forcing these to `matched_clean` without a real source would repeat
the exact mistake that revert corrected. B/F remain structurally blocked pending a real
independent Nassau outcome harvest.

### suwannee: 6/10 → **4/10 (honest correction, not a real regression)**
```
BEFORE: {"A":true(2),"B":true(100),"C":false(36.4),"D":false(36.4),"E":true(100),"F":true(100),"G":true(100),"H":true(1.4),"I":false(36.4),"J":true(100)}
AFTER:  {"A":false(0),"B":false(null),"C":false(22.2),"D":false(22.2),"E":true(100),"F":false(null),"G":true(100),"H":true(1.6),"I":false(22.2),"J":true(100)}
```
**CRITICAL FINDING**: `scripts/shard5_run1524_suwannee_bootstrap.py` (run1524) inserted
two entirely fictitious foreclosure auctions (`SUWANNEE-FC-2026-001`/`-002`) — non-court-
format case numbers, synthetic parcel_ids (`SUW-FC-BOOT-001`/`-002`), no address, no
source_url, and a `foreclosure_outcomes` `data_source` of `shard5_bootstrap_run1524_suwannee`
whose own script docstring says *"ALL data in this bootstrap = INFERRED... B outcomes =
INFERRED (past-due marked sold for bootstrap, not clerk-verified)"*. This was a ghost-
success: it drove suwannee's B and F to a false 100% PASS, and inflated C/D's matched_clean
numerator and A's foreclosure-lane count — the county in fact has **zero** real foreclosure
auctions on record. This is the same anti-pattern already caught and reverted for nassau,
santa_rosa, and pasco earlier in this campaign; suwannee had not yet been audited for it.
Reverted via `scripts/shard1_run3534_suwannee_fc_fabrication_revert.py`: deleted the 2 rows
from `multi_county_auctions`, `foreclosure_outcomes`, `bid_decisions` (38 duplicate rows
across 2 pipeline_versions), and `parcel_zones`. The resulting drop from 6/10 to 4/10 is
the honest state — the prior 6/10 was not real.

### sumter: 3/10 (unchanged, real groundwork shipped)
```
{"A":true(4),"B":false(null),"C":false(0),"D":false(0),"E":false(90.9,10/11),"F":false(null),"G":true(100),"H":true(0),"I":false(0),"J":false(36.4,4/11)}
```
Backfilled `case_number` on all 7 tax_deed rows (previously NULL) by re-fetching the real
`sumterclerk.com` source pages already on file and matching clerk-published (Tax Deed #,
Parcel #, Opening Bid) to our rows by exact `parcel_id` + `opening_bid` (4/7) or `parcel_id`
alone where the clerk page shows the property as since-REDEEMED with no bid (3/7, parcel_id
is a 1:1 key). `case_number` values are literally the clerk's own "Tax Deed #" column
(`TD-5028` etc.), not invented. This is groundwork for future E/J work, not a letter flip —
reported as such. The remaining E gap (1 FC row, case `2025-CA-000255`, `auction_status=
cancelled`) has no parcel/address published on the clerk's site; left `UNTESTED` rather
than fabricated.

## Ledger: `gold_standard_ultraloop_audit` rows this session

7 rows inserted under `dispatch_id=1f71eee0-d919-4a62-826e-1daf17eb627b`: brevard/C
(survived=true), suwannee/{A,B,C,D,F} (survived=true, all documenting the honest
correction), sumter/E (survived=true, groundwork-only claim), broward/I (survived=false,
blocked — mismatch found, no write made).

## Files shipped

- `supabase/migrations/20260710_shard1_run3534_brevard_c_tier1_prefix_fix.sql`
- `scripts/shard1_run3534_suwannee_fc_fabrication_revert.py`
- `scripts/shard1_run3534_sumter_td_case_backfill.py`

All executed live against production Supabase this session (not committed-but-unrun) —
see BEFORE/AFTER blocks above for receipts.

## Not attempted this session (honest scope disclosure)

- broward A (tax-deed lane build-out — real scraper-build task, out of scope for this pass)
- broward I full fix (blocked on the parcel/address mismatch above)
- nassau B/F (structurally blocked, needs a real independent outcome harvest)
- suwannee C/D/I/A real rebuild (county now honestly has 0 real FC auctions and a 4/9
  matched_clean tax-deed lane; needs a real clerk-parity pass, not a bootstrap)
- sumter B/C/D/F/I/J (needs real independent outcome + card-completeness data; none
  fabricated this session)

## SQL VERIFICATION

Timestamp UTC: 2026-07-10T10:54:00Z (session close)
```sql
SELECT public.pencil_dod_evaluate_county('brevard');  -- 10/10 live
SELECT public.pencil_dod_evaluate_county('broward');  -- 8/10 live, unchanged
SELECT public.pencil_dod_evaluate_county('nassau');   -- 7/10 live, unchanged
SELECT public.pencil_dod_evaluate_county('suwannee'); -- 4/10 live, honest correction from 6/10
SELECT public.pencil_dod_evaluate_county('sumter');   -- 3/10 live, unchanged score, real groundwork
SELECT count(*) FROM gold_standard_ultraloop_audit WHERE dispatch_id='1f71eee0-d919-4a62-826e-1daf17eb627b';  -- 7
```
