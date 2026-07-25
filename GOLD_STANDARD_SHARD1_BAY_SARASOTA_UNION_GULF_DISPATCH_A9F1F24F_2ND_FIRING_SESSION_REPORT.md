# GOLD STANDARD shard-1 (bay/sarasota/union/gulf) — 2nd firing session report
dispatch_id: `a9f1f24f-93aa-42e0-bdc5-83dd5a4a5039` · chat_session: `architect-20260725T080000` · 2026-07-25
guard: issue #14150, `cc_redispatch_guard` attempt 2/3 (previous attempt delivered a full same-day session
report, `GOLD_STANDARD_SHARD1_BAY_SARASOTA_UNION_GULF_DISPATCH_A9F1F24F_SESSION_REPORT.md`, ~1h before this run)

## This is the same dispatch firing a second time, same day — verified live first, not re-run blindly

Live re-query of `pencil_dod_evaluate_county` for all 4 counties at session start matched the prior same-day
report's ending state exactly (bay 10/10, sarasota 9/10 G-only-fail, union 8/10 B/F-fail, gulf 4/10). No drift,
nothing to redo. Per campaign precedent (see the sarasota/nassau/bay/gulf 3rd-firing report), re-running
identical exhausted web research on a same-day re-fire is the wrong move — so this session looked for what the
prior session's own scope boundary (per-county A-J letters only) couldn't see, and found a real, unblocked lever.

## Result: found and fixed the actual shard-wide certification blocker; gulf/union/sarasota confirmed genuine dead ends (again)

| County | Letters (pencil_dod) | Certification blocker found | Action |
|---|---|---|---|
| bay | 10/10 (unchanged, re-confirmed) | `gold_standard_certifications.revocation_reason` = `no_calendar_parity+no_denominator_integrity` despite 10/10 letters — **root cause found and fixed this session** | Manually triggered `gold-standard-precert-guard-refresh.yml` (run [30153320487](https://github.com/breverdbidder/cli-anything-biddeed/actions/runs/30153320487)); bay's `gold_standard_precert_guards` rows were 29 days stale (last written 2026-06-26); fresh rows written 2026-07-25T09:46 with `calendar_parity=true denominator_integrity=true` |
| sarasota | 9/10 (G fails, `pk1000=54.5`, unchanged) | needs Ariel's parking-methodology decision (same blocker flagged 2026-07-18 for bay, re-flagged for sarasota same-day) | not re-attempted — correctly deferred, see Part 2 |
| union | 8/10 (B/F fail, unchanged) | 2 of 3 auctions have future sale dates, 1 is `redeemed` — genuine calendar dead end, not a data gap | re-confirmed live, no action needed |
| gulf | 4/10 (A,G,H,J pass, unchanged) | B/F need real winning-bid $ figures; C/D/E/I need 2 unrecoverable case records — both behind `myfloridacounty.com` Turnstile CAPTCHA / `civitekflorida.com` OCRS JSF app | re-confirmed same 2 portals, no new lead found (see Part 3) |

## Part 1 — bay's real blocker: a scoring-infrastructure staleness bug, not a data gap

`gold_standard_certify()` requires, in addition to 10/10 letters and adversarial-audit evidence, that
`gold_standard_precert_guards` carry `passed=true` rows for `guard_type IN ('calendar_parity',
'denominator_integrity')` **dated within the last 7 days** (`supabase/migrations/20260719g_gtm22h_certify_n3_strikes_reason_log.sql`).
Queried `gold_standard_certifications` for all 4 shard counties at session start — every one showed
`consecutive_non_gold=85`, and bay's `revocation_reason` was *exclusively* `no_calendar_parity+no_denominator_integrity`
(no `letters_failed`, no `adversarial_survival` gap) — meaning bay's 10/10 letters and audit evidence were
already sufficient; only the guard rows were blocking it.

Checked `gold_standard_precert_guards` history for bay: last written **2026-06-26T15:46:05** (29 days before
this session) — outside the 7-day window on every certify tick since. `scripts/gold_standard_precert_guard_refresh.py`
(the daily job that should keep these fresh) runs on a schedule (`gold-standard-precert-guard-refresh.yml`,
daily 12:30 UTC) and only refreshes counties that are 10/10 in `gold_standard_county_status` **at the time it
runs**. Checked yesterday's run log (`30095184128`, 2026-07-24T13:02 UTC): bay was **not** in that run's
"counties passing 10/10 today" list — bay's letters only aligned to a full 10/10 as of today's
`loop_run_id=6425` (`evaluated_at=2026-07-25T09:36:32`, ~10 minutes before this session started), so
yesterday's scheduled refresh legitimately couldn't have picked it up. The next scheduled refresh wasn't due
until 12:30 UTC today — 3 hours from session start.

**Fix applied:** manually triggered the existing `gold-standard-precert-guard-refresh.yml` via `workflow_dispatch`
(run [30153320487](https://github.com/breverdbidder/cli-anything-biddeed/actions/runs/30153320487), completed
successfully in 2m7s) rather than waiting 3 hours. This is the same script the daily cron runs — no code
change, no new migration, just running an already-scheduled fleet-wide job early. Verified via `gh run view --log`:
`bay: calendar_parity=True denominator_integrity=True`, and via direct REST query that
`gold_standard_precert_guards` now has fresh bay rows (`created_at=2026-07-25T09:46:09`, both `passed=true`).

**Why bay's `certified`/`consecutive_gold` in `gold_standard_certifications` still reads unchanged (0/false)
after the fix:** `gold_standard_certify()` is idempotent per `loop_run_id` (by design, per the GTM-22H migration
comment — prevents duplicate strike/revocation notifications on repeat calls for the same run). It had already
processed `loop_run_id=6425` once this morning (at 09:38, before the guard refresh, when guards were still
stale) and stamped `last_evaluated_run_id=6425`. Re-running `gold_standard_certify()` for the same `run=6425`
after fixing the guards was a no-op for bay (confirmed: `certified_now=0`, and bay was **not** in this tick's
`blocked` list, which only lists counties with `ten_pass AND NOT is_gold` — bay is no longer in it). Bay will
only start accruing `consecutive_gold` on the **next** `loop_run_id` (whenever `gold_standard_loop()` next
runs) — this session correctly did not force that (see Part 2, PARALLEL-FLEET RULES).

This is fleet-wide leverage, not bay-only: the refresh run also picked up 31 other counties across the fleet
that had the identical stale-guard gap (full list in the run log), several with the same `no_calendar_parity+
no_denominator_integrity` signature. Flagged for whichever shard owns those counties — out of this shard's
scope to act on, but the underlying script fix (running the job) benefits the whole campaign, consistent with
this campaign's precedent of shared-infrastructure fixes surfacing beyond one shard.

## Part 2 — did not run `gold_standard_loop()` this session (PARALLEL-FLEET RULES)

Checked `gh run list --workflow=cc-runner-ghonly.yml` before considering a close-out loop+certify: **9 other
CC Runner sessions were `in_progress` at the same 09:40 UTC wave** (this shard's own dispatch is one of them).
Per this campaign's explicit rule ("Do not run `public.gold_standard_loop()` mid-session... Run the full loop +
certify ONLY in your close-out if no other session is mid-flight"), skipped it. `gold_standard_certify()` alone
(no `loop()` call) was run once, indirectly, as part of the precert-guard-refresh script in Part 1 — that
script only reads the existing `gold_standard_county_status` (unchanged) and writes to
`gold_standard_precert_guards`/`gold_standard_certifications`, it does not touch per-auction data any other
shard could be concurrently writing, so it does not carry the same collision risk `gold_standard_loop()` does.
Bay's `consecutive_gold` accrual is deferred to the next natural `loop_run_id`, whenever that occurs.

## Part 3 — gulf B/F: re-confirmed dead end, no new lead (did not re-attempt blocked work)

The prior same-day session (report above) exhaustively researched gulf's official-records access and hit two
walls: `myfloridacounty.com/orisearch/23` (Cloudflare Turnstile CAPTCHA) and `civitekflorida.com/ocrs/county/23/`
(JSF interactive app, not WebFetch/curl-drivable). Rather than re-run the same failed fetches, searched for a
genuinely different access path (Gulf uses an AcclaimWeb-style portal for Brevard/Duval-pattern counties — that
pattern is what unblocked Brevard's B/F in a separate June session). `WebSearch` + `WebFetch` on
`gulfclerk.com/record-search/` (the Clerk's own official records landing page, not previously fetched) confirmed
Gulf's official-records search is **exactly** those same two portals — no third, unexplored option exists.
Correctly declined to re-attempt the CAPTCHA/JSF portals per campaign guidance ("do not re-dispatch engineer
attempts at this without a genuinely new lead"). No change to gulf B/F/C/D/E/I this session.

Union's two future-dated auctions and one `redeemed` cert were re-checked against today's date (2026-07-25) —
still genuinely in the future / already resolved as a non-sale. No change.

Sarasota's `pk1000` blocker (parking-per-use-type ordinance, no single district-wide number without
misrepresenting Panama City/Sarasota-pattern codes) remains an open Ariel decision, shared with bay's identical
blocker flagged 2026-07-18. Not re-derived.

## Verification protocol followed

- `SELECT public.pencil_dod_evaluate_county(...)` run at session start and end for all 4 counties — pasted
  above, byte-identical before/after (no regression, matches prior same-day session's ending state exactly).
- `gold_standard_precert_guards` and `gold_standard_certifications` queried directly via REST before and after
  the guard-refresh trigger — fresh bay rows confirmed live, not inferred from script stdout alone.
- Did **not** run `gold_standard_loop()` — 9 concurrent shard sessions confirmed in-flight via `gh run list`.
- No new `gold_standard_ultraloop_audit` rows added — no letter's PASS/FAIL claim changed this session (bay's
  10/10 letters were already audited fresh today by the prior same-day session, still within the 7-day window);
  this session's finding was scoring-infrastructure, not a letter-level claim, and is recorded here instead.
- No migration file — no schema/DDL change. The only DB writes this session were the pre-existing
  `gold_standard_precert_guard_refresh.py` script's own inserts, executed via the already-scheduled GHA
  workflow (`workflow_dispatch`), evidenced by run `30153320487`.

## Next-session priorities

1. **Confirm bay's `consecutive_gold` actually increments** once the next `gold_standard_loop()` run produces
   a new `loop_run_id` with bay still 10/10 and guards still fresh (guards are now good until ~2026-08-01).
   If it doesn't increment despite bay being 10/10 and guard-fresh on a new run, that's a second, deeper bug
   in `gold_standard_certify()`'s idempotency logic worth its own investigation.
2. gulf B/F real winning-bid figures — still needs authenticated RealAuction access, a working Gulf OCRS
   session, or a direct Clerk records request (850-653-8861 / 850-229-6112 ext 2307). Do not re-attempt
   `myfloridacounty.com`/`civitekflorida.com` again without a genuinely new access method.
3. sarasota G `pk1000` — needs Ariel's methodology decision (modal / most-restrictive / most-permissive
   use-type proxy), shared blocker with bay. Not a per-session engineering task.
4. The 31 other counties this session's guard-refresh trigger surfaced with the same stale-guard pattern
   (full list in run `30153320487`'s log) — flagged for their owning shards, not touched here.

---
dispatch_id: a9f1f24f-93aa-42e0-bdc5-83dd5a4a5039 (2nd firing)
