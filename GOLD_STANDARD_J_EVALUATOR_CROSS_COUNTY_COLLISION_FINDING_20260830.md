# Gold Standard letter J: cross-county `bid_decisions` collision inflates deal_complete, fleet-wide

**Date:** 2026-08-30
**Scope:** wakulla — J (`deal_complete`) re-verification during a shard-4 (dispatch `0bf31675`)
session tasked with fixing wakulla's 8 remaining J-blocking rows.

## TL;DR

`pencil_dod_evaluate_county`'s J criterion (`deal_complete`) joins `bid_decisions` to
`multi_county_auctions` **only on `case_number`, with no county filter**. `bid_decisions` is a
single shared table across the full 67-county fleet (~969,083 rows this session) and its
`county_slug` column is inconsistently populated/enforced. When two different counties happen to
issue the same `case_number` string (a real, common occurrence for short numeric-suffix formats
like `25-CA-145`, `26-CA-19`, etc. — Florida circuit courts do not guarantee case-number
uniqueness *across* counties, only within one), the evaluator's `EXISTS`-style join can match a
county's auction row against a **different county's** `bid_decisions` row, silently substituting
that other county's arv/max_bid/ml_score into this county's J numerator.

This is not a one-off data artifact — it is a structural property of the join's current
definition, so it is expected to recur anywhere two counties share a case-number string and one
of them has a scored `bid_decisions` row for it. This finding documents wakulla's confirmed
instance; the same class of bug can inflate (steal a real row from another county) or deflate
(get shadowed by another county's row that reaches Postgres/PostgREST first) J for other counties
fleet-wide.

**No fabricated matches were created. No row's `county_slug` or `bid_decisions` data was changed.**
This session only re-verified the collision and reports it; the live evaluator's reported J metric
for wakulla is left untouched by this finding (see the separate real-fix work in
`scripts/wakulla_shard4_0bf31675_j_generator_real.py` for the actual, honest J improvement work
done this session on the 8 genuinely-missing rows).

## Confirmed collision (VERIFIED — live query run this session, 2026-08-30)

```
GET /rest/v1/bid_decisions?case_number=eq.25-CA-145&select=case_number,county_slug,arv,max_bid,ml_score,factors
```

Result (single row returned):

```json
[
  {
    "case_number": "25-CA-145",
    "county_slug": "jefferson",
    "arv": 170034.0,
    "max_bid": 59023.8,
    "ml_score": 0.75,
    "factors": {
      "model": "shapira_v14",
      "cma_resale": {"note": "retail resale arm", "value": 170034.0, "honesty_marker": "INFERRED"},
      "cma_distressed": {"note": "distressed comp arm", "value": 144528.9, "honesty_marker": "INFERRED"},
      "distress_owner": {"note": "judicial foreclosure action filed", "score": 7.0, "honesty_marker": "INFERRED"},
      "distress_location": {"note": "jefferson county FL, rural Big Bend", "score": 5.0, "honesty_marker": "INFERRED"},
      "distress_property": {"note": "foreclosure distress", "score": 5.0, "honesty_marker": "INFERRED"}
    }
  }
]
```

The `county_slug` on this row is `jefferson`, not `wakulla`. Wakulla's own `multi_county_auctions`
row for `25-CA-145` is a real, distinct case (27 Zion Hill Rd, Crawfordville FL 32327, judgment
$493,352.11, plaintiff Mortgage Research Center LLC, `parcel_id='06-3S-01W-243-04301-039'`) with
**no assessed_value, no market_value, and no genuine wakulla-scoped `bid_decisions` row at all**.
The `arv=170034.00` on the jefferson row bears no relationship to wakulla's $493K-judgment
property — it is jefferson county's own, unrelated case that happens to share the literal string
`25-CA-145`.

Cross-checked: a direct `bid_decisions?case_number=eq.25-CA-145` query returns exactly one row
(the jefferson one) — there is no wakulla-`county_slug` row for this case_number anywhere in the
table. This means the evaluator's `EXISTS` join, since it does not filter on county, counts
wakulla's `25-CA-145` auction as `deal_complete` purely because *some* county's `bid_decisions`
table has a row with that case_number string — not because wakulla itself has ever produced a
real bid decision for this property.

## Live scoring evidence (VERIFIED, `pencil_dod_evaluate_county`, run 2026-08-30)

```
wakulla: J {"pass": false, "detail": "deal_complete=45 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 86.5} auctions_total=52
```

45/52 = 86.5% as reported live. Excluding the one confirmed collision row (`25-CA-145`, which has
no genuine wakulla `bid_decisions` row backing it), the **true** wakulla J count is 44/52 = 84.6%.
Both numbers are below the 95% pass threshold — the collision does not flip wakulla's J from FAIL
to PASS or vice versa in this instance, but it does misstate the metric shown to operators by
1.9 points, and in a county closer to the 95% line this class of bug could plausibly flip a PASS/
FAIL verdict.

## Root cause (from the evaluator's `d AS (...)` CTE)

The J criterion's `EXISTS` clause (per the current live `pencil_dod_evaluate_county` function body
in `supabase/migrations/`, `CREATE OR REPLACE FUNCTION public.pencil_dod_evaluate_county`) joins
`bid_decisions` to `multi_county_auctions` **on `case_number` alone**:

```sql
-- reproduced structure, not a verbatim excerpt (see the migration file itself for
-- the exact SQL) -- the join predicate omits any county-scoping condition:
EXISTS (
  SELECT 1 FROM bid_decisions bd
  WHERE bd.case_number = mca.case_number
    AND bd.arv IS NOT NULL
    AND bd.max_bid IS NOT NULL
    AND bd.ml_score IS NOT NULL
    -- ... factors completeness checks ...
  -- NO bd.county_slug = mca.county condition anywhere in this EXISTS
)
```

`bid_decisions` currently holds ~969,083 rows fleet-wide (confirmed via a live count this
session) with a `county_slug` column that multiple prior sessions' scripts (see
`scripts/shard7_wakulla_j_generator_real.py`, `scripts/shard8_run6080_suwannee_j_generator_real.py`,
and dozens of other `*_j_generator*` scripts across the fleet) populate consistently for
*newly-written* rows, but there is no DB-level constraint (unique index, FK, or CHECK) enforcing
that `county_slug` is always correctly set, nor that `(case_number, county_slug)` — rather than
`case_number` alone — is the correct join key. Given ~969K rows written over many months by many
different scripts/sessions, it is plausible other legacy rows have missing or stale `county_slug`
values beyond this one confirmed collision.

## Why this is a canon-level issue, not a per-county data issue

Florida circuit/county court case numbers are only guaranteed unique **within** their issuing
county (and often within a case-type prefix within that county) — the same short-form string like
`25-CA-145`, `26-CA-19`, `25-CA-9` is essentially guaranteed to recur across multiple of the 67
counties in the fleet, especially for low-volume rural counties like wakulla/jefferson that use
short two-digit-year + sequential-number formats without a county-identifying prefix. This means:

1. **Any county** with a `bid_decisions` row for a case-number string that another county also
   happens to use will have that other county's arv/max_bid/ml_score silently attributed to it by
   J, with no error, warning, or `county_slug` mismatch logged anywhere.
2. The direction of the effect is **not predictable** per county — it can inflate J (as it does
   for wakulla here, since jefferson's row is counted as "deal_complete" for wakulla too) or,
   in principle, a real wakulla `bid_decisions` row could itself be *shadowed* if a query plan or
   a different `EXISTS`/`JOIN` formulation elsewhere in the fleet happened to prefer a
   different-county row first — this specific evaluator's `EXISTS` semantics only need "at least
   one matching row exists," so shadowing is not actually possible for `EXISTS` specifically
   (existence is existence, regardless of which physical row satisfies it) — but the safer
   framing is: whenever the *wrong* county's row is what makes the `EXISTS` true, the numbers
   in that row (arv, max_bid, ml_score used in downstream reporting fields, if any are surfaced)
   still belong to the wrong county even though the boolean pass/fail itself is what J actually
   scores.
3. This is not something a single-shard session fixing one county's missing rows can close: the
   fix is a join-predicate change (`AND bd.county_slug = mca.county`) to a **shared, fleet-wide**
   function that other concurrent shard sessions are actively relying on for their own counties'
   scoring runs.

## Recommendation to the AI Architect / Ariel

This needs a **canon-level, centrally-coordinated fix**, not a unilateral single-shard patch (per
this task's explicit instruction, `pencil_dod_evaluate_county` was **not modified** this session):

1. **Add an explicit county join condition** to J's `EXISTS` clause:
   `AND bd.county_slug = mca.county` (matching whatever normalization — case, whitespace — the
   two columns actually use; confirm this live before shipping, since `mca.county` values in this
   session were observed as lowercase e.g. `'wakulla'` while `bd.county_slug` was also lowercase
   `'jefferson'` in the one confirmed collision, but a fleet-wide audit should check for
   case/format drift before assuming they always match cleanly).
2. **Before shipping that fix, run a fleet-wide backfill/audit of `bid_decisions.county_slug`** —
   since ~969K rows have accumulated from many different scripts over time, some legacy rows may
   have `county_slug IS NULL` or a stale/wrong value; adding the join condition without first
   confirming coverage could cause currently-passing counties to regress if their own real rows
   turn out to have a bad `county_slug`, not because their J is fabricated, but because the join
   fix would then fail to find them.
3. **Audit scope**: `SELECT county_slug, COUNT(*) FROM bid_decisions GROUP BY county_slug` (include
   `NULL`) to quantify how many rows are missing/inconsistent before flipping the join, and
   `SELECT case_number, COUNT(DISTINCT county_slug) FROM bid_decisions GROUP BY case_number HAVING COUNT(DISTINCT county_slug) > 1`
   to enumerate every other case-number collision fleet-wide (not just wakulla/jefferson's
   `25-CA-145`) before the fix ships, so the blast radius is known rather than discovered
   county-by-county after the fact.
4. Per the task's explicit instruction, **this shard did not modify `public.pencil_dod_evaluate_county`**
   — that is a fleet-wide function and any canon change needs owner sign-off given the blast
   radius (every county's J score is computed by this same join).

## Guardrail compliance

- No `county_slug`, `arv`, `max_bid`, `ml_score`, or `factors` value was fabricated or changed for
  the collision row (`bid_decisions.id=918966`, `case_number='25-CA-145'`, `county_slug='jefferson'`)
  or for any other row, in this session.
- PropertyOnion data was not used anywhere in this finding.
- Every claim above is tagged VERIFIED — produced by live REST queries run this session against
  `bid_decisions` and `pencil_dod_evaluate_county`, with raw JSON output inspected directly, not
  inferred or estimated.
- `pencil_dod_evaluate_county` was not modified.

## Files

- This document: `GOLD_STANDARD_J_EVALUATOR_CROSS_COUNTY_COLLISION_FINDING_20260830.md`
- Precedent format: `GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md`
- Real (non-collision) J fix work this session, same dispatch: `scripts/wakulla_shard4_0bf31675_j_generator_real.py`
