# Gold Standard SHARD-9 — union, escambia — Session Report

dispatch_id: `1a7d03e0-6c1f-4240-822d-185fd0fe77dd`
chat_session: `architect-20260724T080000`
date: 2026-07-24
mode: ultracode Workflow (fan-out diagnose+fix → adversarial verify per letter)

## Headline

- **escambia: 5/10 → 7/10.** Letters I and J moved to PASS. C/D gained real ground
  (77.7% → 81.6%) but remains FAIL — residual is genuinely blocked, not a bug.
- **union: 8/10 (unchanged).** B/F re-verified as genuinely data-blocked (only 3
  auctions total, earliest close 2026-08-13, zero closed/sold). Nothing to fix.

## First finding: yesterday's escambia fix never shipped

Before doing any new work, live-queried `pencil_dod_evaluate_county` for both
counties and found the numbers matched the issue brief exactly. Investigating why
escambia hadn't moved since the 2026-07-23 shard-3 session (which claimed C/D and I
gains) revealed the entire session's commit (`1ba5e1ba`, "SHARD-3
escambia/union/marion run 6046") was sitting on an **unmerged side branch**
(`claude/issue-13504-20260723-1601`) — exactly the anti-pattern the SHIP-TO-MAIN
MANDATE exists to prevent. The work was real but dead.

Recovered it via `git cherry-pick` onto `main`, then found and fixed two bugs that
would have made it a no-op even if it had shipped:
1. The migration's `INSERT ... ON CONFLICT (parcel_id, jurisdiction_id) DO NOTHING`
   referenced a unique constraint that doesn't exist on `parcel_zones` (the only
   unique constraint there is `(tax_account, jurisdiction_id)`) — this would have
   thrown and rolled back the whole statement.
2. A `RAISE NOTICE '%%'` format-string bug (too many parameters).

Fixed both, applied live: escambia I moved 89.6% → 90.1% before the deeper ultracode
pass below even started.

## Union — verification only (no code)

```
before: {"A":true,"B":false,"C":true,"D":true,"E":true,"F":false,"G":true,"H":true,"I":true,"J":true,"auctions_total":3}
after:  {"A":true,"B":false,"C":true,"D":true,"E":true,"F":false,"G":true,"H":true,"I":true,"J":true,"auctions_total":3}
```

Queried live: union has exactly 3 auctions — 2 upcoming foreclosures (earliest close
2026-08-13, 20 days out) and 1 redeemed tax deed (not a sale). Zero closed_sold rows
exist for B/F to measure against. Logged fresh `gold_standard_ultraloop_audit` rows
(ids 9089, 9090, survived=true) re-confirming this per the EVALUATOR V6 7-day
evidence-freshness rule. No code change possible until an auction actually closes.

## Escambia — ultracode fan-out (3 letters × diagnose-fix → adversarial verify)

### C / D — 77.7% → 81.6% (still FAIL)

- 14 rows fixed via a live RealAuction/RealTaxDeed AJAX re-harvest
  (`scripts/shard_escambia_cd_run20260724.py`).
- Found and fixed a real bug in every prior session's gap-query pattern: PostgREST's
  `data_source=neq.propertyonion` filter silently drops rows where `data_source IS
  NULL` (three-valued SQL logic) — 16 of the true 80 gap rows were invisible to every
  previous fix attempt (shard13, shard14, run6046) because of this.
- Residual 67 tax-deed rows (5 future sale dates: 08/05, 09/02, 10/07, 11/04, 12/02)
  confirmed **genuinely blocked**: live harvest shows 60-61 items posted per date on
  RealAuction right now, but zero exact-match our calendar-sweep cert numbers —
  proven stable via an idempotent re-run immediately after promotion (0 new matches).
  Same root cause independently documented by shard13 (07-11) and shard14 (07-20).

### I — 90.1% → 99.2% (PASS)

- 33 rows geocoded via the free US Census geocoder
  (`scripts/shard_escambia_i_geocode_backfill_20260724.py`).
- 16 rows backfilled into `parcel_zones` using the established most-common-zone
  INFERRED pattern (`migrations/20260724_shard_escambia_i_parcel_zones_backfill.sql`,
  zone_code=`R-1`, verified non-null `parking_per_1000sf` so it cannot regress G).
- 3 rows remain structurally blocked (placeholder/NULL parcel_id, no address source).

### J — 90.9% → 100% (PASS)

- All 33 gap rows had **zero** `bid_decisions` coverage (not partial — newer auction
  rows added after the 2026-07-10 backfill ran). Extended the existing generator
  pattern (`scripts/escambia_j_backfill_20260724.py`) — zero fabricated values, ARV
  from real tax-roll `assessed_value`, INFERRED-tagged per Honesty Protocol.

### Adversarial verification

All three claims were independently re-derived by a separate refuter agent per
letter (different context, told to default to REFUTED on any doubt) — all
**survived**. Refuters independently re-ran the live RPC, hand-reproduced the
evaluator's SQL, spot-checked underlying rows for fabrication/PropertyOnion
contamination/anomalous >100% metrics, and in the C/D case independently re-ran a
live RealAuction harvest themselves to confirm the "genuinely blocked" 67-row
residual. One narrative imprecision was found and adjudicated (13 of 14 C/D "fixed"
rows were newly-inserted-then-matched rather than pre-existing-then-patched) and
traced to a pre-existing, repo-wide `updated_at` tracking quirk unrelated to this
session's correctness — not fabrication.

`gold_standard_ultraloop_audit` rows: 9134, 9135 (C/D), 9141, 9146 (I), 9151 (J),
9091 (G re-confirmation) — all `survived=true`, dispatch_id
`1a7d03e0-6c1f-4240-822d-185fd0fe77dd`.

### Escambia G — not re-attempted (documented, blocked)

pk1000=9.5%, unchanged. Root cause (4 districts with parking regulated by land-use
table, not by district) was legitimately exhausted across shard-14's dual-firing
ultracode research (4/4 candidate citations refuted for guessing a single
representative value) and reconfirmed in the recovered run6046 session. This
requires an **architect decision** (schema extension for use-indexed parking, or an
explicit representative-use mapping) — re-running research would not find anything
new. Logged a fresh re-confirmation row (id 9091) rather than re-deriving from
scratch.

## Final live verification (pasted, not estimated)

```
union    (2026-07-24T08:4x UTC): A✓ B✗ C✓ D✓ E✓ F✗ G✓ H✓ I✓ J✓  — 8/10 (unchanged)
escambia (2026-07-24T08:4x UTC): A✓ B✓ C✗ D✗ E✓ F✓ G✗ H✓ I✓ J✓  — 7/10 (was 5/10)
```

## Wiring

Created `.github/workflows/gold-standard-shard9-escambia-run6148.yml` (daily
13:30 UTC cron) to re-run the C/D harvest, I geocode/parcel_zones backfill, and J
generator — all three scripts are idempotent gap-finders, safe to re-run daily as
new auction rows land and the 5 pending tax-deed sale dates approach.

## Verification protocol executed

- `pencil_dod_evaluate_county` run live before and after every fix, for both
  counties — all pasted above, no rounding/estimation.
- No `gold_standard_loop()` / `gold_standard_certify()` run this session per
  PARALLEL-FLEET RULES (other shards observed pushing to main concurrently
  during this session — rebased twice).
- Committed and pushed directly to `main` throughout, no side branches, no PRs:
  commits `83ee3943` (cherry-pick recovery), `002dfe3b` (migration bugfix),
  `472fb616` (C/D/I/J ultracode fixes), `fdd6a946` (cron wiring).

## Next-session priorities

1. Escambia C/D: 67-row residual will only close as the 5 pending tax-deed sale
   dates arrive and RealAuction's cert list converges — the daily cron will pick
   up any new matches automatically; no manual work needed unless dates pass
   without matching (then re-diagnose).
2. Escambia G: needs an architect decision (not more research) — see shard14 and
   this session's audit rows for the exhausted candidate options.
3. Union B/F: blocked until 2026-08-13 at the earliest. Re-check after that date.
