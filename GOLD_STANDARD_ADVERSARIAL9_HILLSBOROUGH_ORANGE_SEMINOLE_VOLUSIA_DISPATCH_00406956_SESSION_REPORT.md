# Gold Standard Adversarial-9/10: hillsborough, orange, seminole, volusia

**Dispatch:** `00406956-2df6-4aa4-9acf-331beebeeb20`
**Session:** `claude-ai-chat-2026-08-03-gs-adv-9`
**Status:** **BLOCKED** (honest) — not certified

## Objective vs. outcome

The dispatch assumed each county needed one more clean adversarial pass on its single
failing letter to flip `adversarial_ok` to true. Live re-verification (direct SQL
against `multi_county_auctions`, not a re-read of stale audit rows) found the
underlying data for all four is still genuinely broken:

| County | Letter | Surface metric | Adversarial finding |
|---|---|---|---|
| hillsborough | I | 96.6% (861/891) PASS | 740/907 lat/lon rows (81.6%) share one identical coordinate (27.9506, -82.4572 — Tampa centroid) across 8+ visibly distinct street addresses. Placeholder geocode, not real. |
| orange | I | 95.1% (791/832) PASS | 830/859 lat/lon rows (96.6%) share one identical coordinate (28.5383, -81.3792 — Orange County centroid) across distinct addresses. Same pattern. |
| seminole | F | 100% (63/63) PASS | 60/63 tier1_sold rows (95.2%) have `tier1_sold_amount == judgment_amount * 0.65` exactly — a formula, not a clerk-recorded sale price. Same bug flagged 2026-07-29, still unresolved. |
| volusia | H | 1.0h PASS (SLA 48h) | All 396 in-scope rows share one identical `last_seen_at` (2026-08-03 15:56:48.440507+00), and it dominates the per-row freshness calc for 369/396 rows. `scripts/duval_orange_h_freshness_fix.py` shows this exact bulk-PATCH pattern exists in the codebase (currently targets duval/orange). Same bug flagged 2026-07-31, still unresolved. |

## What was done

- Recorded honest `survived=false` rows in `gold_standard_ultraloop_audit` for all
  four county/letter pairs, each with full evidence in `refuter_evidence` — so
  `v_gold_cert_health` continues to correctly show `ADVERSARIAL_INCOMPLETE (9/10)`
  with **current**, not 7-day-stale, evidence.
- Logged `agent_ops_log`: `task=gold-adversarial-9-shard status=BLOCKED severity=blocker`.
- Migration: `supabase/migrations/20260803_gold_standard_adv9_hillsborough_orange_seminole_volusia_refuted.sql`
  (applied live via Management API, then committed).
- Did **not** touch `gold_standard_certifications`, did **not** force a pass.

### SQL VERIFICATION

```sql
select county_slug, adversarial_ok, letters_survived, blocker, consecutive_gold
from v_gold_cert_health
where county_slug in ('hillsborough','orange','seminole','volusia')
order by county_slug;
```
Result (2026-08-03 18:08 UTC):
```
 county_slug  | adversarial_ok | letters_survived | blocker                              | consecutive_gold
--------------+----------------+-------------------+--------------------------------------+------------------
 hillsborough | f              | 9                 | ADVERSARIAL_INCOMPLETE (9/10 survived)| 0
 orange       | f              | 9                 | ADVERSARIAL_INCOMPLETE (9/10 survived)| 0
 seminole     | f              | 9                 | ADVERSARIAL_INCOMPLETE (9/10 survived)| 0
 volusia      | f              | 9                 | ADVERSARIAL_INCOMPLETE (9/10 survived)| 0
```

## DoD status

- `adversarial_ok = true` for all 4 counties — **NOT MET** (correctly, per evidence above)
- `consecutive_gold >= 1` for all 4 — **NOT MET**
- Logged to `agent_ops_log`: task=gold-adversarial-9-shard, status=**BLOCKED** — **MET**

## Next-session priorities (real fixes, not re-tests)

1. **hillsborough + orange (I):** replace county-centroid fallback with real per-parcel
   geocoding (HCPAO/OCPA parcel GIS, same pattern used successfully elsewhere in this
   fleet, e.g. `gold_standard_shard7_flagler_i_geocode.py`).
2. **seminole (F):** source genuine clerk-recorded sale prices for the 60 formula-derived
   rows — RealForeclose auction results page or Seminole Clerk OCRS, not a judgment-based
   estimate.
3. **volusia (H):** stop bulk-PATCHing `last_seen_at`/`last_changed_at`; freshness must
   come from an actual scrape run. Also audit `scripts/duval_orange_h_freshness_fix.py`
   fleet-wide — if it's cron'd or reused elsewhere, other counties' H letters are at the
   same risk of a false-positive freshness claim.

## Non-goals (respected)

- No other counties touched.
- Did not touch biddeed Worker, Stripe, or S5.
