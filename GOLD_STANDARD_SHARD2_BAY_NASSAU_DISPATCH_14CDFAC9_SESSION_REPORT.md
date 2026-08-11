# GOLD STANDARD shard-2 (bay, nassau) — dispatch 14cdfac9 session report

dispatch_id: `14cdfac9-eede-4f87-8950-e0b2f361f664` · chat_session: `architect-20260811T160000` · 2026-08-11
mode: ULTRALOOP native (Workflow tool, 7 adversarial refuter agents)

## Result: both counties 10/10 live, adversarially verified

Started at bay 8/10 (A,B,C,D,F,G,H,J pass; E,I fail) and nassau 6/10 (A,B,F,G,H,J pass; C,D,E,I fail).
Ended at **bay 10/10** and **nassau 10/10**, both confirmed via a fresh `pencil_dod_evaluate_county` call
after every change, and via an independent adversarial verification pass (see Part 2).

### Status board (BEFORE -> AFTER, live `pencil_dod_evaluate_county`)

| County | Letter | Before | After | Fix |
|---|---|---|---|---|
| bay | E | FAIL 90.5% (201/222) | PASS 97.3% (216/222) | RealForeclose PREVIEW backfill, 21 calendar-sweep gap rows -> 15 real parcel_id matches; 6 genuinely carry "Parcel ID: Property Appraiser"/"TIMESHARE" at source, left NULL |
| bay | I | FAIL 87.8% (195/222) | PASS 96.4% (214/222) | Reused existing `scripts/gold_standard_shard9_bay_run6253_i_fix.py` (Bay County ArcGIS geo+zone backfill) |
| bay | G | PASS 97.7% -> FAIL 94.6% (side effect of I fix) | PASS 97.2% | New AG-2/GC-2 zone codes had no `zoning_districts` row (defaulted applicable+missing on all 3 metrics); added ordinance-cited `zone_standards` (Bay Co. LDR Ch.9 Table 9.1 for AG-2 density=0.05 du/acre; Panama City ULDC Table 104-1 for GC-2 FAR=3.0). GC-2 parking left NULL (standing BLOCKED methodology item from dispatch 9f070f2b, not resolved here) |
| nassau | E | FAIL 80.9% (38/47) | PASS 100% (47/47) | RealTaxDeed PREVIEW backfill, 9 rows, matched via embedded 6-digit case sequence |
| nassau | C | FAIL 93.6% (44/47) | PASS 100% (47/47) | 2 rows mislabeled `PHANTOM_NOT_ON_CLERK` in a 2026-07-04 revert live-reconfirmed real (nassau.realtaxdeed.com, status "Redeemed"); 1 never-parity-checked row live-confirmed (nassauclerk.realforeclose.com) |
| nassau | D | FAIL 93.6% (44/47) | PASS 100% (47/47) | same 3-row fix as C |
| nassau | I | FAIL 80.9% (38/47) | PASS 100% then honestly **95.7%** (45/47) post fabrication-purge | Nassau PA ArcGIS (maps.ncpafl.com MapServer/144) geo+zone backfill, 9 rows |
| nassau | G | PASS 100% -> FAIL 0.0% (side effect of I fix) | PASS 97.4% | New "RSF-2" zone code (GIS label) had no `zoning_districts` row; added district row with `category='Residential'` only — no numeric value fabricated (could not confirm RSF-2 maps to ordinance code "RS-2") |

## Part 1 — mechanism behind the two G regressions

Both G regressions share one root cause: `v_zoning_gold_standard_kpi_v3` joins `parcel_zones` to
`zoning_districts` by `(jurisdiction_id, code)`. When a newly-linked zone code has no matching
`zoning_districts` row, `v_zoning_district_applicability` returns NULL for that parcel, and the KPI view's
`COALESCE(a.far_applicable, true)` / `COALESCE(a.pk1000_applicable, true)` / `COALESCE(a.density_applicable,
true)` default **all three** metrics to "applicable" — with no `zone_standards` value to match, every
newly-linked parcel with an unmatched zone code silently drags down density/far/pk1000 simultaneously. This
is a real trap for any future I-letter zoning backfill: **always check the new zone code resolves to an
existing `zoning_districts` row (or add one) before declaring I fixed**, or G will regress in the same
session.

## Part 2 — ULTRALOOP adversarial verification (7 claims, 1 refuted, then fixed)

Ran via `Workflow` (ultracode opt-in): 7 independent refuter agents, one per claim, each re-running live SQL
and live web/ArcGIS fetches from scratch (not trusting this session's own numbers). 470K tokens, 140 tool
calls, ~8 min wall-clock.

**6/7 survived on the first pass** (bay E, bay I, bay G, nassau C/D, nassau I, nassau G). **1 was refuted**:
nassau E's supporting evidence trail contained a fabrication finding — the refuter discovered that 15 nassau
rows (7 predating this session, created 2026-07-01 with real RealForeclose source_urls; 8 of this session's
9 calendar-sweep backfill rows) all carried an **identical** `assessed_value=320000` / `market_value=336000.0`
pair across 15 completely distinct properties. This session's own E-fix script never wrote those fields for
the affected rows (confirmed: its payload only ever included `parcel_id`/`property_address` for cases
011-018), so this was pre-existing fabricated/templated placeholder data, not something introduced this
session — but it was directly propping up part of nassau's I-letter pass (`card_complete` requires a
non-null assessed/market value).

**Investigated and fixed live, same session** (`scripts/shard2_nassau_run14cdfac9_fabricated_value_purge.py`):
queried the Nassau County PA ArcGIS layer (`maps.ncpafl.com/ncflpa_arcgis/.../MapServer/144`, fields
`JUSTVAL`/`FASMP_ASSD_VALUE_NS`) for all 15 affected parcel_ids. Real per-parcel values ranged $4,500 to
$937,155 — nothing close to a repeated $320K/$336K, confirming fabrication rather than coincidence. 13 of 15
rows got real values written; 2 condo-unit PINs (`00-00-31-101G-0001-2169`, `00-00-31-141K-0406-0000`)
returned no match in that ArcGIS layer and were set to `NULL` rather than left fabricated (BLANK > WRONG).
nassau I recomputed honestly at **95.7% (45/47)**, still above the 95% gate — no county dropped below 10/10
as a result of the honest correction.

All 8 claims (7 original + amended evidence) logged to `public.gold_standard_ultraloop_audit` for the
CERTIFY GATE's evidence requirement.

## Part 3 — session close-out

```sql
UPDATE public.gold_standard_campaign
SET criteria_passed = '{"A":true,"B":true,"C":true,"D":true,"E":true,"F":true,"G":true,"H":true,"I":true,"J":true}'::jsonb,
    criteria_total = 10, exit_reason = 'certified', session_end_at = now()
WHERE dispatch_id = '14cdfac9-eede-4f87-8950-e0b2f361f664';
```
Applied live (row id=4151, target_counties=[bay,nassau]).

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` (fleet-wide) were **not** run this
session since other shards were concurrently active (evidenced by unrelated commits landing on `main` via
`git pull --rebase` mid-session: gadsden dispatch cefc3fb1, washington dispatch a3eafa08, baker dispatch
14cbae1a). Per-county `pencil_dod_evaluate_county` was used for all verification instead, matching the
brief's explicit instruction. Fleet-wide certification (second consecutive 10/10 at the daily 07:30Z run) is
left to the scoring infrastructure.

## Next-session priorities

1. If another session touches bay/nassau zoning again: check new zone codes resolve to a `zoning_districts`
   row FIRST, to avoid repeating the G-regression pattern documented in Part 1.
2. bay G's `pk1000` sub-metric for GC-2 (Panama City) is still genuinely unresolved (parking-per-use-type
   methodology question, flagged BLOCKED since dispatch 9f070f2b 3rd firing) — do not force a number without
   Ariel's methodology decision.
3. The fabrication-signature sweep this session was scoped to nassau only (found via this session's own E/I
   claim). Given this campaign's repeated history of finding the same templated-placeholder pattern in other
   counties, a fleet-wide sweep for `assessed_value`/`market_value` pairs repeated identically across many
   distinct case numbers (not just this exact $320K/$336K pair) would likely surface more of the same —
   flagged for a future dedicated audit session, out of this shard's scope.

---
dispatch_id: 14cdfac9-eede-4f87-8950-e0b2f361f664
