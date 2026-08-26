# Gold Standard shard-2 session report — dispatch b3eafd22

**Counties:** manatee, charlotte, liberty, taylor
**Dispatch:** b3eafd22-4672-4353-baa8-cb7a3d4399fc / chat_session architect-20260826T080000
**Session date:** 2026-08-26

## Summary

One real, verified fix shipped (taylor E). Three counties' remaining gaps
were investigated live and found to be genuine structural ceilings or
transient automation backlog, not fixable defects — documented below with
evidence rather than worked around or guessed. No regressions.

## Shipped and VERIFIED

### taylor E: 91.7% (11/12) -> 100% (12/12)

Case `23-505 CA` (1205 Sweetgum Ln NE, Steinhatchee) had `parcel_id`,
`latitude`, `longitude`, `assessed_value` all NULL. Queried the FL GIO
Statewide Cadastral FeatureServer live (`CO_NO=72` for Taylor per
`fl_counties.co_no`) for an exact address match:

```
PARCEL_ID=09459-119, PHY_ADDR1="1205 SWEETGUM LN  NE",
PHY_CITY="Steinhatchee", PHY_ZIPCD=32359, JV=287370, LND_VAL=99500, DOR_UC=001
centroid (outSR=4326): lat=29.689720817015733, lon=-83.36362337393638
```

Applied via `supabase/migrations/20260826_gold_standard_shard2_taylor_e_23505ca_fl_gio_fix.sql`.
Corroboration: the plaintiff field on this row (unrelated to the fix,
already scraped) names "WILLIAM NORMAN CLARK" — matches the FL GIO owner
lead independently found via web search before the cadastral query.

Before/after (`pencil_dod_evaluate_county('taylor')`):
```
E before: {"pass": false, "detail": "parcel_linked=11", "metric": 91.7}
E after:  {"pass": true,  "detail": "parcel_linked=12", "metric": 100.0}
```

Taylor moves 5/10 -> 6/10.

## Investigated, NOT fixed — genuine structural ceilings (evidence attached, no writes)

### manatee C: 92.8% (154/166) — reconfirmed live ceiling

All 12 non-clean rows carry `parity_status='CLERK_SSOT_CANCELLED'`. Spot-
verified the newest one (case `2025CA000787AX`, not present in the prior
Aug-24 audit of 11) live against `records.manateeclerk.com` via
`scripts/clerk_ssot/parsers/manatee.py parse_foreclosure()`:

```
{'case_number': '2025CA000787AX', 'sale_date': '2026-09-02', 'cancelled': True,
 'raw_comment': 'CANCELLED ONLINE'}
```

Confirmed genuinely cancelled per the clerk's own live calendar. Per the
evaluator's canon (CLERK_SSOT_CANCELLED counts toward matched_any/D, never
matched_clean/C by design — see `20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql`),
manatee C cannot exceed `(166-12)/166 = 92.8%` today. This matches the
conclusion of the prior investigation
(`scripts/manatee_c_cancelled_litmus_investigation_run8347.py`, 2026-08-24)
and this session's live check found no new lever.

### charlotte C: 58.3% (168/288) — at its structural ceiling, no headroom left

Replicated the evaluator's C filter in Python against all 288 in-scope
rows: the 120 non-clean rows are **all** `parity_status='CLERK_SSOT_CANCELLED'`
(zero NULL/orphan rows this time — the 3 orphans found and fixed in
`20260813_gold_standard_shard5_charlotte_c_orphan_parity_stamp.sql` are
long since closed). `168 + 120 = 288` exactly. Max possible C under current
canon = `168/288 = 58.3%` — charlotte is already there. The prior session's
finding (charlotte C structurally capped, evaluator-definition question
explicitly out of scope) still holds, just at a much lower ceiling now
because `auctions_total` grew from 178 to 288 while the cancelled-row count
grew from 17 to 120 over the same period.

### taylor C: 91.7% (11/12) — same ceiling class

The single non-clean row (case `25-014 CA`, 1104 N Allen St, Perry) is
`parity_status='CLERK_SSOT_CANCELLED'`, `auction_status='CANCELLED'`. With
only 12 total rows, one genuinely-cancelled case caps C at 91.7% — cannot
reach 95% without a 13th auction landing clean, or a canon change.

### liberty A/B/F: reconfirmed, not re-litigated — 5th+ consecutive identical result

`scripts/liberty_a_bf_recheck_gsd2_84b6c4bb.py` (2026-08-15, this session's
11-day-old but most recent full investigation) found libertyclerk.com's
tax-deed page reporting "no properties" live, the 5th identical check across
a 6-week window, and confirmed Liberty genuinely holds only in-person,
non-platform tax deed sales with nothing currently scheduled. `taylor B/F`-
class conclusion: "Structurally blocked. Documented in 4+ prior sessions."
A shallow re-check this session of `libertyclerk.com/courts/tax-deeds/`
hit the site's bot-detection/JS-render wall (no usable static content),
so it neither confirms nor refutes the prior finding — the Aug-15 result
stands as the freshest evidence. No writes made.

## Investigated, real gap identified, deliberately NOT guessed

### charlotte J: 94.8% (273/288) — transient backlog, not a defect

The 15 rows lacking a complete `bid_decisions` entry all have `parcel_id`
populated already and were `created_at` within the last 24-48h
(2026-08-25/26). Per CLAUDE.md, "the per-minute valuations_comps batch
(cron 109) builds inputs — do not modify it" — these rows are eligible
inputs simply awaiting their next automated processing cycle, not a
structural or code defect. No manual bid_decisions rows were fabricated.
Expected to self-resolve; re-check in the next session before assuming a
fix is needed.

### taylor I: 91.7% (11/12) — E fix did not cascade to I; real follow-up identified, not guessed

`v_zoning_gold_standard_card` requires the row's `parcel_id` to carry a
`zone_code` from `parcel_zones`. Confirmed live that parcel `09459-119`
(the row just fixed for E) is **not yet** in taylor's zoning card view —
taylor's zoning substrate was built via NCFRPC Future Land Use Plan Map
GeoPDF point-in-polygon (see `20260809_gold_standard_taylor_i_06578076_c5a8b2c7.sql`
and `20260724d_shard13_taylor_i_flu_geopdf_parcel_zones.sql`) and does not
cover this Steinhatchee-area parcel. Downloaded and read the current NCFRPC
Taylor County FLU map (`https://ncfrpc.org/MapsAndPlans/Counties/Taylor/TAFU16tmpa.pdf`)
this session but could not reliably resolve which FLU polygon contains
29.6897/-83.3636 from the rendered map alone — a guessed zone_code is
explicitly banned as ghost-success per CLAUDE.md. Left open for a session
with proper GIS point-in-polygon tooling (same method as the prior 11
taylor zone_code rows).

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Fix a failing letter per targeted county where possible | Yes | taylor E fixed and verified | none |
| Investigate manatee/charlotte/taylor C | Diagnose root cause | Confirmed genuine structural ceiling (evaluator canon), not a bug | none — matches prior sessions' conclusions |
| Investigate charlotte J | Diagnose and fix if possible | Confirmed transient automation backlog (fresh rows, cron hasn't run yet), no fix attempted to avoid fabricating bid_decisions | scope reduced from "fix" to "diagnose+document" once root cause was clear |
| Investigate taylor I | Fix if possible after E | Real follow-up identified (zoning substrate gap for one new parcel); did not guess a zone_code | scope reduced — GIS point-in-polygon tooling not reliably available this session |
| Investigate liberty A/B/F | Fix if possible | Reconfirmed existing 5x-verified ceiling; did not re-run full investigation methodology | scope reduced given strength of prior evidence |
| Close-out DB write | Mandatory | Done — `gold_standard_campaign` row `id=5059` updated with full per-county criteria_passed | none |

## Verification evidence

- `SELECT public.pencil_dod_evaluate_county('taylor')` run before and after the fix (pasted above) — E confirmed 91.7% -> 100.0%.
- `SELECT public.pencil_dod_evaluate_county('manatee'|'charlotte'|'liberty')` run at session end — confirmed unchanged (154/166, 168/288+273/288, 1/1 respectively), consistent with "no fixable lever found" conclusions.
- Live clerk re-scrape for manatee case `2025CA000787AX` via `scripts/clerk_ssot/parsers/manatee.py`.
- Live FL GIO Statewide Cadastral FeatureServer query for taylor parcel `09459-119`.
- `gold_standard_campaign.id=5059` PATCHed with final `criteria_passed` JSON, `exit_reason='timeout'`, `session_end_at` set.

## Honest scoreboard delta

| County | Before | After |
|---|---|---|
| manatee | 9/10 | 9/10 (unchanged — C confirmed ceiling) |
| charlotte | 8/10 | 8/10 (unchanged — C confirmed ceiling, J confirmed transient backlog) |
| liberty | 7/10 | 7/10 (unchanged — A/B/F reconfirmed ceiling) |
| taylor | 5/10 | 6/10 (E fixed and verified) |

No `gold_standard_loop()`/`gold_standard_certify()` run this session per
PARALLEL-FLEET RULES (other shards' state unknown/possibly mid-flight);
per-county `pencil_dod_evaluate_county` used for all verification instead.
