# SHARD-13 duplicate-dispatch session report (duval / polk / alachua / union)

dispatch_id: `8fd59111-3d32-4d9d-931b-3a259e4b1d9b`
date: 2026-07-05

## Duplicate dispatch

This exact `dispatch_id` already produced a complete session, shipped at commit
`e44eaf87` (`scripts/shard13_run3059_duval_polk_alachua_union_cd_e.py`). On arrival,
live `pencil_dod_evaluate_county` matched that session's recorded "after" state for
duval, alachua, and union exactly. **Polk had drifted independently** — from
79.4%/82.6% (C/D) to 94.97%/94.97% — via some automation between commit e44eaf87 and
this run (confirmed via `git log`: zero commits touch polk in that window; the change
is data-only, not a code deploy from this repo).

## Root cause found this session (duval)

The prior run3059 script promoted C/D via a **county-wide** exact-case-number harvest.
Re-investigating duval's residual 88 "unmatched-for-C" rows this session found they are
NOT homogeneous:

- **60 rows** are `parity_status=matched_divergent` with `parity_source LIKE 'tier1%'`
  — already tier1-sourced, but flagged as field-divergent (our record disagrees with
  the tier1 source on some field). Re-running the county-wide harvester would relabel
  these to `matched_clean` on mere calendar existence, without resolving the actual
  divergence — a ghost-success bug. **Excluded from this session's scope.**
- **28 rows** are genuinely harvest-fixable: 12 `parity_status IS NULL` (never
  checked), 14 `mca_only`, 2 `matched_clean` under a prior session's own
  ghost-relabel tag (`unverified_single_source_ghost_relabel_duval_20260703_not_tier1`
  — explicitly not tier1).
- Polk's residual 20 rows are homogeneously null/null (verified zero
  `matched_divergent` rows exist anywhere in polk), so a county-wide harvest is safe
  there.

Built a row-scoped variant of the proven AJAX harvester
(`scripts/shard13_run2_20260705_duval_polk_alachua_union_cd_e.py`): given an explicit
row-id allowlist, it only promotes rows in that list whose case_number is confirmed on
**that row's own auction_date's** live calendar — never touches `matched_divergent`
rows, never blind-promotes a whole county.

## ULTRALOOP: a real Workflow-tool defect hit and worked around

First attempt fanned harvest+verify per county through `pipeline()` with a JSON payload
passed via the Workflow tool's `args` parameter. Both harvest stages failed:
`payload.all_rows` was undefined — the `args` object did not thread through to the
script body as expected (root cause not fully diagnosed within this session's budget;
flagging as a known defect for whoever next authors a Workflow script with a large
`args` payload). The investigate-only agents in the same run (alachua, union), which
did not depend on `args`, completed normally and returned real findings.

**Worked around**: ran the harvest directly (same logic, executed via Bash rather than
inside a workflow agent), then launched a **second**, separate Workflow whose only job
was adversarial verification — 3 parallel refuter agents, each independently
re-fetching the live RealAuction/RealTaxDeed calendar for a disjoint subset of the 25
promoted duval rows, under each row's own `auction_date`. This preserves the ULTRALOOP
invariant that the verifier is never the agent that wrote the fix, even though the fix
itself was applied outside a workflow agent this session.

**Result: all 25 rows survived independent re-verification. Zero refuted.**

## Before → after (live `pencil_dod_evaluate_county`, verified this session)

```json
BEFORE:
duval:   {"A":85,"B":100.0,"C":82.3,"D":93.5,"E":100.0,"F":100.0,"G":100.0,"H":0.4,"I":96.1,"J":99.0}  (8/10)
polk:    {"A":96,"B":100.0,"C":95.0,"D":95.0,"E":100.0,"F":100.0,"G":100.0,"H":4.9,"I":100.0,"J":97.9}  (8/10, C/D FAIL at 585/616=94.97%)
alachua: {"A":3,"B":100.0,"C":70.0,"D":70.0,"E":92.5,"F":100.0,"G":100.0,"H":1.7,"I":82.5,"J":100.0}  (6/10)
union:   {"A":1,"B":null,"C":0.0,"D":0.0,"E":100.0,"F":null,"G":100.0,"H":17.3,"I":0.0,"J":0.0}  (4/10)

AFTER:
duval:   {"A":85,"B":100.0,"C":86.3,"D":97.6,"E":100.0,"F":100.0,"G":100.0,"H":0.6,"I":96.1,"J":99.0}  (9/10, D FLIPPED TO PASS)
polk:    {"A":96,"B":100.0,"C":95.0,"D":95.0,"E":100.0,"F":100.0,"G":100.0,"H":5.1,"I":100.0,"J":97.9}  (8/10, unchanged — honest negative)
alachua: {"A":3,"B":100.0,"C":70.0,"D":70.0,"E":92.5,"F":100.0,"G":100.0,"H":1.9,"I":82.5,"J":100.0}  (6/10, unchanged, zero drift)
union:   {"A":1,"B":null,"C":0.0,"D":0.0,"E":100.0,"F":null,"G":100.0,"H":17.5,"I":100.0,"J":0.0}  (5/10, I moved — SEE FLAG BELOW)
```

| county | letter | before | after | note |
|---|---|---|---|---|
| duval | D | 93.5 | 97.6 | **PASS** — 25 rows promoted, all 25 adversarially verified |
| duval | C | 82.3 | 86.3 | still FAIL — remaining gap is the 60 matched_divergent rows (different fix class) |
| polk | C/D | 94.97 | 94.97 | unchanged — 20 residual rows checked live, 0 found on calendar, genuine continuances |
| alachua | (all) | — | — | unchanged, zero drift confirmed |
| union | I | 0.0 | 100.0 | moved, but **not this session's doing** — see flag below |

## Honesty flag: union I moved without any write from this session

This session made **zero database writes to union** (the union investigate agent found
no independently-verifiable evidence for the one thing it was authorized to possibly
fix, and made no PATCH — confirmed in its returned report). Yet `pencil_dod_evaluate_county('union')`
now shows I=100.0% (3/3), up from 0.0% at session start. Direct query of
`v_zoning_gold_standard_card` confirms all 3 union parcels now have `zone_code`
populated (`R-1`, `core8_fields_present=2`, `gold_core_complete=false` — note the card
is not fully complete by the *stricter* core-8 standard, but the evaluator's I metric
only requires zone_code presence for this join). This is consistent with a concurrent
shard/cron zoning-ingestion run for union between this session's before/after
snapshots. Logged to `gold_standard_ultraloop_audit` as observed-not-attributed, per
honesty protocol — not claimed as this session's work.

## Residual gaps (unchanged from prior session, re-confirmed live, not re-litigated)

- **duval C**: 60 `matched_divergent` rows need field-level reconciliation (why does
  each row diverge from its tier1 source?), a genuinely different and bigger build than
  existence-matching. Flagging for a dedicated future session.
- **polk C/D**: 20 rows, both 2025-11-20 and 2025-12-18 tax_deed calendars, zero found
  under their own date. Genuine continuances that moved to an unprobed date, or cases
  that never appeared publicly. **Polk is 1 row away from a double-PASS (needs
  586/616)** — highest-leverage remaining target for a future session with time to do
  a wider date-range sweep or a case-detail-page lookup.
- **alachua C/D**: still capped at 28/40 by 12 future-dated rows (ghost-success
  guardrail correctly excludes them until the sale actually happens).
- **alachua I**: 4 parcel_ids (02578-003-001, 03034-020-082, 03044-100-079,
  07814-100-059) still absent from `v_zoning_gold_standard_card` for alachua — a
  zoning-ingestion coverage gap, unchanged since prior session.
- **union B/C/D/F/J**: structurally blocked — 2 genuinely upcoming foreclosures;
  UNION-TD-CERT223 tax-deed staleness (auction_status=upcoming, ~115 days past its own
  auction_date) confirmed still real but unfixable this session: unionclerk.com serves
  a Cloudflare JS challenge to curl/WebFetch (verified 403 on homepage and both
  tax-deed subpages), zero archive.org snapshots exist, and no FIRECRAWL_API_KEY is
  present in this environment to clear the challenge. Recommend flagging as a tooling
  gap (needs Firecrawl key or live browser automation) rather than retrying the same
  blocked path.

## Audit trail

6 rows logged to `gold_standard_ultraloop_audit` under dispatch_id
`8fd59111-3d32-4d9d-931b-3a259e4b1d9b` (`ultraloop_mode='fallback'`, since the native
pipeline hit the args-threading defect): duval D (survived, 25/25), duval C (survived,
25/25), polk C (survived — honest zero-result), alachua I (survived — zero-drift
reconfirmation), union B (survived — blocked-tooling reconfirmation), union I
(survived — observed-not-attributed flag).

## Files changed

- `scripts/shard13_run2_20260705_duval_polk_alachua_union_cd_e.py` — new, row-scoped
  harvester + full methodology/root-cause/results documentation for this session.
- `SHARD13_RUN2_20260705_SESSION_REPORT.md` — this file.

No schema changes this session (no migration needed — all writes were data patches to
`multi_county_auctions.parity_status`/`parity_source` via existing columns).
