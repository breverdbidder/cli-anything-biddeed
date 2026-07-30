# Gold Standard shard-6 broward — dispatch 3bb96d0d, loop run 7519

## Summary

The dispatch brief's G (FAIL 0.0) and I (FAIL 91.2) numbers were stale — a concurrent fleet
session (audit rows timestamped 2026-07-30 16:21Z, ~1h before this session started) had already
fixed both live, ~24 min before this session queried the DB. Live re-check confirmed **broward is
10/10 PASS** on `gold_standard_scoreboard` as of 2026-07-30 16:45:42Z. Per the PARALLEL-FLEET
RULES this is expected, not an error — the brief is a snapshot, the fleet runs continuously.

With no failing letter left to fix, this session's real, verifiable deliverable was different:
**broward's re-certification was silently blocked** despite 10/10 PASS, because criterion A's
last adversarial audit evidence (`gold_standard_ultraloop_audit`) was 9 days 16 hours old —
past the `gold_standard_certify()` 7-day freshness window (`EVALUATOR V6` / `SQL CERTIFY GATE`
rule). This session ran an ULTRALOOP audit+adversarial-verify pass on letter A, confirmed the
claim survives, wrote a fresh `survived=true` row, and in the process surfaced two real findings
that are flagged, not silently fixed.

## What actually happened, in order

1. Confirmed live `pencil_dod_evaluate_county('broward')` = 10/10 PASS (see Verification Evidence
   below) — brief's G/I numbers were superseded.
2. Checked `gold_standard_certifications` for broward: `certified=false`, `revoked_at=2026-07-28`,
   `revocation_reason='...adversarial_survival_9_of_10'`, `consecutive_gold=0`. Cross-referenced
   `gold_standard_certify()`'s source: `is_gold` requires ten_pass AND 10 distinct letters with a
   `survived=true` audit row **created within the last 7 days** AND both precert guards
   (`calendar_parity`, `denominator_integrity`) passing fresh.
3. Queried `DISTINCT ON (letter)` latest audit row per letter for broward: 9 of 10 letters had
   fresh (<7d) `survived=true` evidence; **letter A's most recent row was 9d16h old** (outside the
   window) — this is the actual, current blocker on re-certification, not a data quality issue.
4. Ran an ULTRALOOP audit+adversarial-verify workflow (2 independent fresh-context agents:
   auditor, then a blind refuter given only the auditor's conclusion) specifically re-deriving
   criterion A (fc=685, td=17 — dual-product coverage) against the live DB.
5. Both agents independently reproduced fc=685/td=17, confirmed zero duplicate/ghost rows, ruled
   out the "~20-item anonymous preview cap" adversarial hypothesis (the GSG deedauction.net
   platform's own JSON reported `item_count=17` as the authoritative auction size — not a cap
   artifact), and confirmed the propertyonion-exclusion rule is correctly applied (265 td rows
   correctly excluded; the 4 fc rows that pass despite `data_source=propertyonion` do so only via
   the evaluator's own sanctioned `tier1_authoritative` override, verified real).
6. **refuted=false** — inserted a fresh `survived=true` audit row for broward/A
   (`gold_standard_ultraloop_audit`, dispatch_id `3bb96d0d-...`).
7. Re-checked audit freshness for all 10 letters: **all now <7 days, all survived=true.** Both
   precert guards fresh (3d old) and passing. All `gold_standard_certify()` preconditions for
   `is_gold=true` are now met for broward.
8. Per PARALLEL-FLEET RULES ("run the full loop + certify ONLY in your close-out if no other
   session is mid-flight"), **did not run `gold_standard_loop()`/`gold_standard_certify()`** —
   the G/I audit rows from 1h29m before this check are direct evidence the fleet was mid-flight
   throughout this session. The next close-out session (or the daily 07:30Z cron) with no
   concurrent activity should run it; broward is positioned to register its first `consecutive_gold`
   tick then, and certify on the second consecutive 10/10 run.

## Real findings surfaced (flagged, NOT silently fixed)

1. **broward.deedauction.net (Broward's tax-deed lane) has permanently shut down.** Live check
   this session: `POST /auctions/upcoming` now returns `recordsTotal=0` with a banner —
   *"Broward County tax deed auctions will no longer be conducted in DeedAuction... Please visit
   the Broward County Records, Taxes and Treasury Division website"* — and `GET /auction/112`
   (the auction the current 17 `A`-criterion rows came from) now 404s. Today's 14:17Z run of
   `gold-standard-shard9-broward-deedauction.yml` already logs *"No upcoming Broward tax deed
   auctions found. Exiting (honest zero, not an error)"* — correct fail-quiet-as-zero behavior,
   but the 17 rows already in `multi_county_auctions` are never flagged or purged. Criterion A
   currently passes on a frozen historical snapshot with **no live successor lane**. A does not
   have a freshness component today, so this is not an active failure — but it is a real gap.
   **Next-session priority**: build a new broward tax-deed source against Broward County's
   Records, Taxes and Treasury Division site.
2. **Fleet-wide (not broward-specific) H-criterion integrity concern, not touched this session**
   (shared code, out of single-shard scope per PARALLEL-FLEET RULES): `public.touch_county_freshness(p_county)`
   is a blind `UPDATE ... SET last_seen_at = now() ... ORDER BY last_seen_at DESC LIMIT 10` with
   **zero live-source re-verification**. Confirmed it moved all 17 stale broward td rows'
   `last_seen_at` to 2026-07-30 15:40Z despite `scraped_at=2026-07-28` — i.e. criterion H's
   freshness signal can be decoupled from source reality for any county this RPC touches. Worth a
   dedicated audit of every caller of `touch_county_freshness()` fleet-wide.

## Verification evidence

Before this session (dispatch brief snapshot, since superseded by a concurrent session before
this one started):
```
G FAIL metric=0.0 [density=93.9 far=0.0 pk1000=0.0]
I FAIL metric=91.2 [card_complete=640 of 702]
```

Live at session start (already fixed by a concurrent session ~24 min prior):
```sql
SELECT public.pencil_dod_evaluate_county('broward');
--  A:PASS(17) B:PASS(100) C:PASS(99.6) D:PASS(99.7) E:PASS(99.6)
--  F:PASS(100) G:PASS(98.6) H:PASS I:PASS(96.4) J:PASS(95.2)  ← 10/10
```

Live at session close (unchanged data, confirming stability; audit freshness gap closed):
```sql
SELECT public.pencil_dod_evaluate_county('broward');
--  A:PASS(17, fc=685 td=17) B:PASS(100) C:PASS(99.6) D:PASS(99.7) E:PASS(99.6)
--  F:PASS(100) G:PASS(98.6) H:PASS I:PASS(96.4, card_complete=677 of 702) J:PASS(95.2)  ← 10/10

SELECT * FROM public.gold_standard_scoreboard WHERE county_slug='broward';
--  pass_count=10, gold_standard=true, critical_three_pass=true, evaluated_at=2026-07-30 16:45:42Z

SELECT DISTINCT ON (letter) letter, survived, now()-created_at AS age
FROM public.gold_standard_ultraloop_audit WHERE county_slug='broward' ORDER BY letter, created_at DESC;
--  A:true(7s)  B:true(5d17h) C:true(6d9h) D:true(5d17h) E:true(5d17h)
--  F:true(5d17h) G:true(1h30m) H:true(5d17h) I:true(1h30m) J:true(6d8h)
--  ALL 10 letters now within the 7-day certify window, all survived=true.

SELECT DISTINCT ON (guard_type) guard_type, passed, now()-created_at AS age
FROM public.gold_standard_precert_guards WHERE county_slug='broward'
  AND guard_type IN ('calendar_parity','denominator_integrity') ORDER BY guard_type, created_at DESC;
--  calendar_parity: true (3d4h)  denominator_integrity: true (3d4h)

SELECT county_slug, consecutive_gold, consecutive_non_gold, certified, revoked_at, revocation_reason
FROM public.gold_standard_certifications WHERE county_slug='broward';
--  consecutive_gold=0 consecutive_non_gold=36 certified=false
--  revoked_at=2026-07-28 08:56:40 reason='...adversarial_survival_9_of_10'
--  (unchanged this session — gold_standard_loop()/certify() intentionally NOT run,
--   fleet observably mid-flight; all preconditions for is_gold=true are now met for
--   the next close-out session or the daily 07:30Z cron to register)
```

Timestamp: 2026-07-30T17:52Z (UTC)

## Wiring / files

- `GOLD_STANDARD_SHARD6_BROWARD_DISPATCH_3BB96D0D_RUN7519_SESSION_REPORT.md` (this file).
- One `gold_standard_ultraloop_audit` row inserted (`county_slug='broward', letter='A',
  survived=true`), 7-day freshness window now clean for all 10 letters.
- No code changes, no migrations — this session's work was audit-evidence generation, not a
  data fix (none was needed; G/I were already fixed by the concurrent session referenced above).

## Next-session priorities

1. **P0**: build a real, live broward tax-deed source (Broward County Records, Taxes and Treasury
   Division site) — `broward.deedauction.net` is permanently discontinued as of this session, and
   criterion A's 17 rows are now a frozen artifact with no live successor lane.
2. **P1, fleet-wide**: audit every caller of `public.touch_county_freshness()` — it blindly marks
   rows fresh with zero live-source re-verification, which can mask real staleness under
   criterion H for any county it touches, not just broward.
3. **Close-out**: once a session confirms no concurrent fleet activity, run
   `SET statement_timeout=0; SELECT public.gold_standard_loop(); SELECT public.gold_standard_certify();`
   — all preconditions for broward's `is_gold=true` are met as of this session; it should register
   its first `consecutive_gold` tick, then certify on the second consecutive 10/10 run.
