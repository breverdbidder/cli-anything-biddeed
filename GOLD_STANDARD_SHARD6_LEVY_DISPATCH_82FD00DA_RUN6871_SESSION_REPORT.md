# Gold Standard shard-6: levy — dispatch 82fd00da, loop run 6871

## Assigned scope
levy only (9/10 going in). Letter A the sole failure (`fc=0 td=29`); B–J all PASS at 100%.

## What this session found and did

1. **Diagnosed and shipped a real fix**: `shard13-levy-daily-scraper.yml`'s `h-freshness` and
   `j-bid-decisions` jobs had been failing every day for 8+ consecutive runs (2026-07-20 through
   2026-07-27 06:50Z) — HTTP 403 from the Supabase Management API because
   `secrets.SUPABASE_ACCESS_TOKEN` is stale in GitHub Actions (the same token works locally). The
   `j-bid-decisions` job's raw SQL also referenced columns (`county`, `sale_type`, `updated_at`) that
   don't exist on `bid_decisions` and would have failed even with valid auth.
   - Added two `SECURITY DEFINER` RPCs, `public.refresh_levy_freshness` and
     `public.refresh_levy_bid_decisions`, matching the real `bid_decisions` schema.
   - Switched both jobs to call the RPCs over PostgREST with `SUPABASE_URL` /
     `SUPABASE_SERVICE_ROLE_KEY` — the same auth pattern the TD scraper job in the same workflow
     already used successfully every day.
   - Applied live, committed as `96d8e827` to `main` directly (no branch, no PR, per Ship-to-Main
     mandate).
   - Re-ran the workflow: one run five minutes after the fix commit still failed (PostgREST
     schema-cache lag right after RPC creation), the next run succeeded cleanly on all 4 jobs.

2. **Re-verified letter A is still a genuine dead end, not a bug** — 7th consecutive independent
   session to reach this conclusion (prior: 2026-06-27, 07-04, 07-05, 07-11 ×2, 07-23, 07-25). Ran the
   scraper live in dry-run mode today (fresh `2026-4162` SALE case confirmed already ingested by the
   fixed daily cron), fetched levyclerk.com's foreclosure page directly, and confirmed
   `pipeline.counties` has the foreclosure lane correctly configured (not a config gap).

3. **Confirmed no regression on B–J** from the workflow-fix — `bid_decisions` join count for levy
   is still 29/29, matching J=100%.

## Adversarial verification (ULTRALOOP, native mode)

Two independent refuter agents (neither was the agent that made the fix or the original A diagnosis)
re-derived both claims from scratch today:

- **Claim 1 (GHA fix is real and live)** → **CONFIRMED.** Newest run `30284267411` (16:20:29Z), all 4
  jobs `success`; both RPCs exist in `pg_proc`; `grep SUPABASE_ACCESS_TOKEN` on the current workflow
  file returns zero matches.
- **Claim 2 (levy is 9/10, A is a genuine non-actionable gap, no regression)** → **CONFIRMED.** Fresh
  `pencil_dod_evaluate_county('levy')` matches exactly; independent `curl` of levyclerk.com shows
  "There are no foreclosure sales available at this time"; `pipeline.counties` foreclosure lane
  confirmed configured; direct `GROUP BY` on `multi_county_auctions` shows 0 foreclosure rows / 29
  tax_deed rows.

Logged to `gold_standard_ultraloop_audit` (both `survived=true`).

## SQL VERIFICATION

```sql
SELECT public.pencil_dod_evaluate_county('levy');
```
```json
{
  "county": "levy", "auctions_total": 29,
  "A": {"pass": false, "detail": "fc=0 td=29", "metric": 0},
  "B": {"pass": true, "detail": "verified=28 closed_sold=28", "metric": 100},
  "C": {"pass": true, "detail": "matched_clean=29", "metric": 100},
  "D": {"pass": true, "detail": "matched_any=29", "metric": 100},
  "E": {"pass": true, "detail": "parcel_linked=29", "metric": 100},
  "F": {"pass": true, "detail": "tier1_sold=28 closed_sold=28", "metric": 100},
  "G": {"pass": true, "detail": "density=100.0 far=100.0 pk1000=", "metric": 100},
  "H": {"pass": true, "detail": "3 hours since last_seen (SLA 48h)", "metric": 3},
  "I": {"pass": true, "detail": "card_complete=29 of 29", "metric": 100},
  "J": {"pass": true, "detail": "deal_complete=29 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100}
}
```
Timestamp: 2026-07-27T19:2x:xxZ (queried live via Supabase Management API this session).

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Fix levy A (fc=0) | Investigate/wire foreclosure lane | Confirmed (7th time) it's a genuine real-world zero, not fixable — instead found and shipped an unrelated real bug (8-day-broken daily automation) that protects future A movement | Scope shifted from "fix A" to "fix what was actually broken + honestly re-confirm A" |
| Ship to main | Direct commit, no PR | Done — `96d8e827` | None |
| Verify | pencil_dod_evaluate_county + adversarial refute | Done, both claims CONFIRMED by independent agents | None |

## Residual / next-session priority

Nothing actionable remains for levy this session. **Do not re-run the full multi-source A sweep again
soon** — it has now survived 7 independent checks across a month with zero change in the underlying
county practice (physical courthouse-lobby tax-deed auctions only; no online foreclosure listing
system exists for Levy County). Re-check only opportunistically (e.g. if `levyclerk.com`'s page text
changes, or a workflow_dispatch is manually triggered) rather than dedicating session time to it.

`gold_standard_loop()` / `gold_standard_certify()` were **not** run this session (per PARALLEL-FLEET
RULES, other shards' counties may be mid-flight); per-county `pencil_dod_evaluate_county('levy')` was
used for all verification instead.
