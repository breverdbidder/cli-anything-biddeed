# Gold Standard shard-12: jefferson — run 7622 session report (9th + 10th firing)

dispatch_id: 675aa97f-3855-4c8c-b5e8-3ae2afc96d6d
issue: #17031

## Result: jefferson unchanged at 8/10 (A,C,E,G,H,I,J PASS; B,F FAIL). D flagged as a ghost-success this firing — live evaluator still returns PASS, but is no longer certification-ready pending architect review. BLANK > WRONG.

### Two independent investigations converged on this dispatch
This issue was worked twice in parallel this dispatch:
1. **`claude[bot]` GitHub Action auto-dispatch** produced a 9th-firing diagnosis + migration, but left
   it stranded on branch `claude/issue-17031-20260731-0801` — never merged to main. This is the exact
   "stranded branch" failure mode already found once before (6th firing, issue #12859: a shipped B/F
   parser was dead on main for weeks because its branch was never merged). Per SHIP-TO-MAIN MANDATE
   (side branches score zero), this session merged that content into main rather than leaving it
   stranded again (commit reconciled: `f475a3c1003db6ced5b9b9b4472855251934df0c`).
2. **This interactive session** ran an independent native ULTRALOOP fan-out (2 finders hunting fresh
   B/F leads) + a 4-letter regression audit (C/D/E/I) via the Workflow tool, arriving at a convergent
   B/F conclusion plus one new finding — a D regression — the stranded branch did not check.

### Starting / current state (live, `pencil_dod_evaluate_county('jefferson')`)
```json
{"A":{"pass":true,"metric":1,"detail":"fc=1 td=2"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100.0,"detail":"matched_clean=3"},
 "D":{"pass":true,"metric":100.0,"detail":"matched_any=3"},
 "E":{"pass":true,"metric":100.0,"detail":"parcel_linked=3"},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000="},
 "H":{"pass":true,"metric":"~21","detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":true,"metric":100.0,"detail":"card_complete=3 of 3"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=3 (triangle + two-arm CMA + ml_score + max_bid)"},
 "county":"jefferson","auctions_total":3}
```
No metric moved this session (expected — see diagnosis below). D's live PASS is now flagged as
suspect pending architect-level review (see D section).

### B/F diagnosis (confirmed live, unchanged root cause)
3 MCA rows total for jefferson:

| case_number | sale_type   | auction_date | sold_amount |
|-------------|-------------|--------------|-------------|
| 25-CA-164   | foreclosure | 2026-06-25 (past) | NULL |
| 26-TD-04    | tax_deed    | 2026-08-19 (future) | NULL |
| 26-TD-05    | tax_deed    | 2026-08-19 (future) | NULL |

`closed_sold = count(*) FILTER (WHERE sold_amount IS NOT NULL) = 0`, so both B and F evaluate to
`null/0` via `NULLIF`. The only closed case (25-CA-164) has never had its sold amount published by
any public source, independent or otherwise, across **10 firings now** and **24+ distinct sources**:

Newly checked this session (beyond the 20-source list from firings 1–9), all negative:
- **Jefferson County Tax Collector** (`jeffersoncountytaxcollector.com`) — a genuinely different,
  live, unblocked vendor (not Civitek/MyFloridaCounty/qpublic). Queried live, matched the exact
  parcel and owner (Thompson, 340 S Marvin St) — but its schema has zero deed/sale/consideration
  fields. Reachable, structurally incapable.
- **Jefferson PA's full ArcGIS org** (`services5.arcgis.com/vFMp1Ly1q6rKKp0o`) — pulled the complete
  `Parcels_Jefferson_FL` layer schema (not just the zoning layer used for E/G). No sale-price, deed,
  OR book/page, or grantor/grantee fields exist anywhere in it.
- **archive.org Wayback Machine** — zero snapshots exist for `jeffersonclerk.com` at all; the one
  `civitekflorida.com/ocrs/county/33/` snapshot found predates the sale date (2026-05-19 vs sale
  2026-06-25), so even an accessible historical version couldn't show a post-sale result.
- **FLCLERKS.com** (Florida Association of Court Clerks statewide portal) — confirmed to be a pure
  pointer to MyFloridaCounty.com, no independent backend.
- **2nd Judicial Circuit shared CMS** (`2ndcircuit.leoncountyfl.gov`) — no case-search tool at all,
  only administrative order timelines.
- **FL GIO cadastral SALE_PRC1/SALE_YR1** direct field check — both `0`, confirming the DOR roll has
  no recorded sale for this parcel (stale, annual-refresh, predates the 2026-06-25 sale).

No dollar amount was found or fabricated. The structural finding from the 3rd firing stands
unrefuted: FL Stat 45.031 makes the pre-sale notice and post-sale certificate of title legally
distinct documents, and no Big Bend county newspaper/legal-notice channel republishes post-sale
results — this rules out the entire notice-aggregator channel on principle, not just for this site.

**Auto-resolution remains correctly wired**: `shard-jefferson-clerk-scraper.yml` (weekly Monday
08:30 UTC) will parse and write a verified outcome the moment the clerk publishes a results PDF
for either tax-deed case after the 2026-08-19 sale. Confirmed healthy — last run 2026-07-27, found
nothing (as expected), no regression.

### D: REGRESSION FOUND this session (ghost-success)
The regression audit (run independently of the B/F hunt, in parallel, via a dedicated subagent)
found that **D=PASS (matched_any=3) is not backed by real cross-source corroboration**:

- `po_listings` has **zero rows** for jefferson (checked both `county_slug=eq.jefferson` and
  `county_name=eq.Jefferson`) — there is no PropertyOnion litmus data to compare against for this
  county at all (too small/rural for PO coverage).
- `parity_po_id`, `parity_confidence`, `parity_checked_at`, `tier1_verified_at`,
  `tier1_source_run_id` are **all NULL** on all 3 jefferson rows.
- D currently passes purely because `parity_status='matched_clean'/'matched_divergent'` AND
  `parity_source LIKE 'tier1%'` — and `parity_source` here is a static text label
  (`tier1:jeffersonclerk_..._pdf_scrape+fl_gio_cadastral_corroboration_<date>`) applied at
  ingestion time, not a record of an actual comparison.
- **Fleet-wide sanity check** (run live this firing, not scoped to jefferson): of 19,127 rows
  fleet-wide with `parity_status='matched_clean'`, only 2,445 (12.8%) have a real `parity_po_id`
  link. **87.2% pass D by text-label convention alone**, including all 3 jefferson rows.

This is a **systemic D-criterion definition gap**, not jefferson-specific — correcting it means
either redefining the shared evaluator predicate or auditing fleet-wide parity data, both out of
scope for a single-county shard session (PARALLEL-FLEET RULES: never touch shared code paths or
other counties' data unilaterally). **Not corrected this session — escalated only.**

Note: C was independently regression-checked too and held up — its agent cross-verified actual
field values (owner, address, dollar amounts) across 3 independent sources (clerk PDF text
extraction, DB row, live FL GIO/DOR cadastral) rather than relying on the parity_source label,
and every value matched exactly. C's PASS is real. D's is not — the distinction is that D's
predicate can be satisfied by the label alone with zero underlying comparison, while this
session's C spot-check happened to find genuine independent corroboration anyway.

E and I were also regression-checked and confirmed genuinely real (parcel_ids independently
resolve to correct FL GIO cadastral owner/address records; card fields are non-placeholder and
correctly zone-linked).

### Verification protocol
- `pencil_dod_evaluate_county('jefferson')` re-run live via Supabase REST RPC — unchanged (8/10,
  same as brief).
- 8 fresh `gold_standard_ultraloop_audit` rows logged live this session (ids 11502–11509): 2 rows
  merging the stranded branch's B/F findings (`ultraloop_mode=fallback`), 2 rows for this session's
  own B/F fan-out (`ultraloop_mode=native`), 3 rows for the C/E/I regression confirmations
  (survived=true), and 1 row for the D ghost-success finding (**survived=false**).
- Per ULTRALOOP protocol point 6, jefferson's D now requires a fresh `survived=true` row before it
  can count toward certification — the live evaluator will keep reporting PASS until the shared
  predicate or fleet-wide parity data is corrected, but the cert gate is designed to catch exactly
  this case via the audit table, not the live evaluator alone.
- `gold_standard_loop()`/`gold_standard_certify()` NOT run — other shards were mid-flight
  (dozens of concurrent `claude/issue-*` branches observed), per PARALLEL-FLEET RULES this session
  used per-county evaluation only.

### Honesty Protocol tags
- jefferson 8/10 live-evaluator state unchanged: **VERIFIED** (REST RPC re-run this session).
- 6 new B/F sources checked this session, all negative, no fabrication: **VERIFIED** (live
  fetches/queries, evidence in audit rows 11504–11505).
- D ghost-success (0 real po_listings corroboration, 87.2% fleet-wide text-label-only rate):
  **VERIFIED** (live REST queries against `po_listings` and `multi_county_auctions` this session).
- C/E/I regression-confirmed genuinely real: **VERIFIED** (independent cross-source field matches).
- Auto-resolution cron healthy, next actionable window 2026-08-24: **VERIFIED**/**INFERRED**
  respectively (cron run history VERIFIED; publication timing on the clerk's side is INFERRED).

### Stranded-branch sweep
Merged `claude/issue-17031-20260731-0801` into main this session (its content was accurate and
convergent with this session's independent findings). Did **not** sweep other stranded
`claude/issue-*` branches observed in the repo (dozens exist, spanning many other shards/counties)
— out of scope per PARALLEL-FLEET RULES (jefferson-only). Flagging for the fleet dispatcher: the
stranded-branch pattern recurred on this exact dispatch after already being identified and fixed
once (6th firing / issue #12859), suggesting the underlying GitHub Action branch-creation behavior
needs a structural fix (e.g. auto-merge-to-main on the `claude[bot]` workflow itself), not another
one-off manual merge next time it happens.

### FLEET DISPATCHER RECOMMENDATION
**Stop re-firing jefferson B/F until 2026-08-19 passes.** This is the 10th firing with an
identical B/F conclusion; each re-fire burns session budget for zero possible metric movement.
Next productive B/F session: **2026-08-24** (or sooner if the clerk publishes results ahead of
schedule and the weekly scraper catches it). **D requires an architect-level decision** on the
shared parity-corroboration criterion, not another county-scoped re-fire — recommend routing this
finding to whichever process handles fleet-wide evaluator/schema changes.
