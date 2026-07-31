# GOLD STANDARD shard-7 (wakulla, union) — session report

dispatch_id: `bc1624fe-01f3-407f-b3c8-b20b7b8fda62` · chat_session: `architect-20260731T080000` · loop run 7622 · 2026-07-31

mode: ULTRALOOP native (Workflow tool: 8 audit agents + 8 adversarial refuters on union's stale letters, 16 subagents total)

## Zero drift, confirmed live before and after

Both counties matched the brief's opening numbers exactly, before any work:

- **wakulla: 10/10** (A,B,C,D,E,F,G,H,I,J all PASS)
- **union: 8/10** (A,C,D,E,G,H,I,J PASS; B,F FAIL)

No writes were made to `multi_county_auctions`, `bid_decisions`, or any auction-data table this session — only
`gold_standard_ultraloop_audit` rows. Re-verification after the session shows byte-identical metrics to the
brief on both counties. This was an audit/verification session, not a fix session, because neither county had
an actionable fix available today (see below).

## Wakulla: no action needed

All 10 letters already carry `survived=true` audit rows younger than the 7-day certification window
(A/B/C/D/F/G/H at 7-8h old, C/J at 6.3h, E/I at 134h — all well under 168h). Nothing was stale, so nothing
was touched. Wakulla remains eligible for the automated 10/10-consecutive-day certification path.

## Union B/F: reconfirmed structurally blocked, not re-investigated

`multi_county_auctions` for union has exactly 3 rows, unchanged from the brief:
- `63-2025-CA-0053` — foreclosure, upcoming, sale date 2026-08-13
- `63-2024-CA-0047` — foreclosure, upcoming, sale date 2026-10-15
- `UNION-TD-CERT223` — tax deed, **redeemed** (not sold — `sold_amount` correctly null)

`closed_sold=0` fleet-wide for union today, so B and F are mathematically `NULL`, not fixable by any scraper
until an actual sale occurs. This exact question was independently re-investigated **earlier today** by a
concurrent session (dispatch `e362cd8e`, logged in `pipeline.counties.notes` for union) via Playwright:
Civitek OCRS Turnstile silently rejects automated search submission, `unionclerk.com` and
`union.realforeclose.com` are both Cloudflare-blocked, and Firecrawl returned HTTP 402 (insufficient
credits). This session independently re-tested the Firecrawl lever live — **still HTTP 402** — and did not
re-run the browser-automation checks, since re-deriving an already-adversarially-verified same-day conclusion
would waste session budget for zero new information. **No further union B/F work should be attempted before
2026-08-13** (earliest possible sale close) or until Firecrawl credits are restored.

## Union ULTRALOOP audit-freshness refresh (the actual work this session)

Union's 8 passing letters had `survived=true` audit rows 20-33 days old (499-800h), well past the 7-day
certification freshness gate — a live risk once B/F eventually clear, since `gold_standard_certify` requires
fresh survived rows for **all 10** letters. Ran a Workflow fan-out: one audit agent + one independent
adversarial refuter per letter (A,C,D,E,G,H,I,J), each running live SQL via the Management API, no shared
queries between auditor and refuter.

**6 of 8 survived, re-logged as fresh audit rows (dispatch `bc1624fe`, `native` mode):**
- A, C, D, E, H — refuters independently reproduced the passing metrics from different angles (dup-check,
  PropertyOnion-masquerade check, ghost-parcel-id check, timestamp re-derivation). No issues found.
- **I** — the workflow's refuter initially reported `survived=false`, comparing against
  `v_zoning_gold_standard_card.gold_core_complete` (an unrelated stricter 8-field flag) and `market_value`
  alone. This was **the wrong criterion**. I pulled the live `pencil_dod_evaluate_county` function
  definition (`pg_get_functiondef`) and reproduced its actual I-condition verbatim — `property_address` +
  `COALESCE(latitude, po_latitude)` + `COALESCE(longitude, po_longitude)` + `COALESCE(assessed_value,
  market_value)` + parcel_id matched to a zone_code-populated `v_zoning_gold_standard_card` row — against all
  3 union rows directly. All 3 satisfy every field (assessed_value is populated on all 3 even though
  market_value is null; the evaluator's `COALESCE` covers this, the refuter's check did not). The original
  claim was correct; the refuter was wrong. Logged `survived=true` with the corrected evidence.

**2 of 8 genuinely refuted — NOT certified, flagged as open findings:**
- **G** — mechanically passes (density=100.0) but the underlying `zone_code` source is self-flagged
  `union_i_realparcel_backfill_run3025_4th_ZONECODE_UNVERIFIED`, and `zone_standards.parking_per_1000sf=2.00`
  exists for the R-1 district while `pk1000_applicable=false` auto-derivation hides it from the metric
  denominator entirely instead of measuring it. This is a ghost-pass risk on the applicability-flag logic
  (the same failure class as the Orlando R-3B false-applicability bug from a prior shard-5 orange session).
  Not fixed this session — it's a shared-view issue affecting the fleet, out of proportion for a
  union-scoped session, and needs a dedicated zoning-substrate audit.
- **J** — mechanically passes (`deal_complete=3 of 3`, factor keys present) but I independently confirmed via
  direct query against `bid_decisions` that **both CMA arms derive from the same single `assessed_value`
  scalar**: `cma_distressed.sources=["assessed_value_proxy"]`, `cma_resale.sources=["market_value_proxy"]` —
  but `market_value` is `NULL` on all 3 union rows, so the "resale" arm silently falls back to the same
  assessed value with a different multiplier (~0.87 / ~1.12). `ml_score` is a flat hardcoded `0.5200` across
  all 3 rows, not a per-property score. This is **exactly** the failure mode `pencil_dod_criteria.rationale`
  for J explicitly names and bans: *"A single-ARV CMA hides the thesis."* The evaluator only checks that the
  `factors` JSONB has the required keys, not that `cma_distressed`/`cma_resale` come from independent
  sources. Since J's generator is documented as county-agnostic, **this is very likely a fleet-wide
  ghost-success**, not union-specific — flagging prominently below as the highest-priority carry-forward
  finding from this session.

## SQL VERIFICATION

```sql
-- BEFORE (matches brief exactly) and AFTER (this session, 2026-07-31) -- identical, zero drift:
select public.pencil_dod_evaluate_county('wakulla');
-- wakulla: A pass(6) B pass(100.0) C pass(100.0) D pass(100.0) E pass(96.7) F pass(100.0)
--          G pass(100.0) H pass(1.9) I pass(96.7) J pass(100.0)  -- 10/10, unchanged

select public.pencil_dod_evaluate_county('union');
-- union: A pass(1) B fail(null) C pass(100.0) D pass(100.0) E pass(100.0) F fail(null)
--        G pass(100.0) H pass(1.9) I pass(100.0) J pass(100.0)  -- 8/10, unchanged

select county_slug, letter, survived, created_at from gold_standard_ultraloop_audit
  where dispatch_id = 'bc1624fe-01f3-407f-b3c8-b20b7b8fda62' order by letter;
-- 8 rows: A,C,D,E,H,I survived=true (fresh); G,J survived=false (genuine refutations, false-positive ledger)
```

Per PARALLEL-FLEET RULES, `gold_standard_loop()` / `gold_standard_certify()` were **not** run this session
(other shards may be mid-flight concurrently on the same 08:00Z wave) — per-county
`pencil_dod_evaluate_county` was used for all verification instead.

## Migrations shipped

None. Zero writes to any auction, parcel, zoning, or bid_decisions table. Only `INSERT` to
`gold_standard_ultraloop_audit` (8 rows, this dispatch_id). No `Do not [regression]` risk introduced.

## Next-session priorities (carried forward)

1. **J single-ARV ghost-success (HIGH PRIORITY, likely fleet-wide)** — `bid_decisions` rows across counties
   using the same county-agnostic J generator should be sampled for the same `assessed_value_proxy` /
   `market_value_proxy` pattern with a flat `ml_score`. If widespread, this is a B>100%-anomaly-caliber issue:
   J is currently passing mechanically fleet-wide while violating its own documented rationale. Needs a
   dedicated session to rebuild the CMA-arm sourcing against real independent comps (HUD/HomeHarvest/Zillow/
   Redfin/Realtor.com per the rationale) before any J-dependent certification should be trusted.
2. **G applicability-flag ghost-pass pattern** — union's `pk1000_applicable=false` masking a real
   `parking_per_1000sf` standard is the same failure class as the prior Orlando R-3B false-applicability bug.
   Worth a fleet-wide audit of `v_zoning_district_applicability` derivation logic, not just union.
3. **union B/F** — nothing to do until a real auction closes (earliest 2026-08-13) or Firecrawl credits are
   restored. Do not re-run the OCRS/unionclerk.com/realforeclose.com investigation again without new access
   or a new date — it was independently confirmed blocked twice today (dispatch `e362cd8e` and this session).
4. **wakulla** — stable at 10/10 with fresh audits fleet-wide; on track for automated certification once the
   second consecutive 10/10 07:30Z run lands.

---
dispatch_id: bc1624fe-01f3-407f-b3c8-b20b7b8fda62
