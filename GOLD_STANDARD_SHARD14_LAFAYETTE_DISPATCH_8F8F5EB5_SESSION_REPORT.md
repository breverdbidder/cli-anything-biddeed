# Gold Standard Shard-14: lafayette — dispatch 8f8f5eb5, H root-cause fix

## Result: 7/10 → 8/10

| Letter | Before | After | Notes |
|---|---|---|---|
| A | PASS (fc=1 td=1) | PASS (fc=1 td=1) | Unchanged |
| B | FAIL (null) | FAIL (null) | Genuinely blocked — see below, not re-researched |
| C | PASS 100.0 | PASS 100.0 | No regression |
| D | PASS 100.0 | PASS 100.0 | No regression |
| E | PASS 100.0 | PASS 100.0 | No regression |
| F | FAIL (null) | FAIL (null) | Genuinely blocked — see below, not re-researched |
| G | PASS 100.0 | PASS 100.0 | No regression |
| **H** | **FAIL 124.0→131.7** | **PASS 0.0** | **Fixed this session — root cause below** |
| I | PASS 100.0 | PASS 100.0 | No regression |
| J | PASS 100.0 | PASS 100.0 | No regression |

## What happened

The dispatch brief listed lafayette at 7/10 with H newly FAILing at 124h (vs. 48h SLA), a
regression from the 8/10 baseline (A,C,D,E,G,H,I,J pass) established across the prior **8
consecutive sessions** of work on this county (dispatches `b34a2384`×3, `e440836a`, culminating in
an 8th session report recommending closure on B/F specifically).

A live `pencil_dod_evaluate_county('lafayette')` check confirmed 131.7h at session start — worse
than the brief's snapshot, consistent with the staleness clock still running.

### Root cause (VERIFIED)

`.github/workflows/lafayette-clerk-harvest.yml` (cron `50 5 * * *`, 05:50 UTC daily) has run
**successfully every day since 2026-07-12** (`gh run list` confirms 7 consecutive green runs). But
`scripts/lafayette_clerk_harvest.py`'s upsert payload never included `last_seen_at` (or
`scraped_at`/`scrape_timestamp`), so PostgREST's `merge-duplicates` upsert left those columns
untouched on every run where the row already existed. The county's 2 rows had been frozen at their
original insert timestamps (foreclosure case `25000056CAAXMX`: 2026-07-10T16:42:59Z; tax_deed
`TD-2022-28`: 2026-07-11T21:38:27Z) for 6-8 days despite the "successful" cron — a scraper that runs
and reports success while silently never refreshing freshness.

The repo already has the correct convention for this exact pattern in
`scripts/glades_municode_notices_scraper.py` (small-county clerk scraper that explicitly sets
`last_seen_at`/`scraped_at`/`scrape_timestamp` = now() on every row it re-confirms). Applied the
identical minimal fix to `lafayette_clerk_harvest.py`: added `now_iso` and set it on both the
foreclosure and tax_deed row dicts.

### Fix verified live (not just committed)

1. Ran `python3 scripts/lafayette_clerk_harvest.py` live this session — exit 0, upserted 1 row
   (`25000056CAAXMX`, the only card currently on the live foreclosure page; tax_deed page still
   genuinely reads "no properties," as it has since 2026-07-10).
2. Confirmed via direct REST query: `last_seen_at` for that case updated to
   `2026-07-18T21:07:24.176398+00:00`.
3. Re-ran `pencil_dod_evaluate_county('lafayette')` — H flipped to `{pass:true, metric:0.0}`, all
   other 9 letters unchanged.
4. Confirmed the GHA cron invokes this same script unmodified, so tomorrow's 05:50 UTC run inherits
   the fix automatically — this is a durable root-cause fix, not a one-off manual timestamp patch.

### Adversarial verification (ULTRALOOP, native mode)

Per the ULTRALOOP protocol, ran one `Workflow` (`wf_306b8531-5a3`, 2 agents: refuter + logger) to
independently try to break the claim before logging it. The refuter re-derived every fact from live
commands rather than trusting my numbers — re-read the diff, independently queried
`multi_county_auctions` and the evaluator RPC, cross-checked all 9 other letters against the
documented 8-session baseline for regressions, and confirmed the on_conflict target
(`county,case_number,sale_type`) produced an in-place UPDATE (single row, `created_at` unchanged,
`last_seen_at` bumped) rather than a silent duplicate insert.

**Verdict: `survived=true`.** The refuter also surfaced an honest, disclosed residual risk (not a
defect in this fix): `TD-2022-28` is 167.5h stale and will never be touched again since it's off the
live tax-deed page permanently — H currently passes only because it's `MAX(...)` across county rows
and the foreclosure row's daily refresh rescues the county-wide metric. This is the evaluator's
existing, Ariel-authorized design (H stays live-scored, not scope-frozen), not something this diff
introduced. **Future risk flagged for whoever next touches lafayette:** once the foreclosure case's
September 2026 sale date passes and it drops off the live page, there will be no fresh row left to
rescue the `MAX`, and H will fail again with no rescue mechanism unless a new auction is scraped or
this is revisited.

### B/F — deliberately NOT re-researched this session

B and F (`verified=0 closed_sold=0`, both structurally blocked) have now been independently
adversarially reconfirmed across **8 consecutive prior sessions** spanning **13 distinct research
avenues** — RealAuction/realforeclose probes, Wayback Machine (multiple snapshot generations),
Municode Angular SPA, myfloridacounty.com Turnstile CAPTCHA, Civitek Florida OCRS Turnstile CAPTCHA,
Lafayette Tax Collector site, FY2024 Auditor General AFR, third-party tax-deed aggregators,
Beacon/Schneider property-appraiser (Cloudflare bot-block), FL unclaimed-property portal (WAF
rejection), BOCC minutes (no accessible archive/product), and floridapublicnotices.com (zero
relevant hits). The most recent (8th) session report explicitly recommended: *"Recommend this
dispatch be closed or superseded for lafayette B/F specifically... Re-firing this dispatch unchanged
will reproduce this exact result and burn session budget with zero yield."*

Spending this session's budget re-running exhausted avenues would duplicate prior work and violate
the repo's own honesty-protocol guidance against manufacturing busywork. This session's only
genuinely new signal (H's regression) has been root-caused, fixed, and adversarially verified. No
other counties are in this shard's assignment, so the session closes here rather than drifting into
another shard's territory.

## Live evaluation JSON — BEFORE (session start)
```json
{"A":{"pass":true,"detail":"fc=1 td=1","metric":1},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":true,"detail":"matched_clean=2","metric":100.0},"D":{"pass":true,"detail":"matched_any=2","metric":100.0},"E":{"pass":true,"detail":"parcel_linked=2","metric":100.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":false,"detail":"hours since last_seen (SLA 48h)","metric":131.7},"I":{"pass":true,"detail":"card_complete=2 of 2","metric":100.0},"J":{"pass":true,"detail":"deal_complete=2 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"lafayette","V2_LITMUS":null,"auctions_total":2}
```

## Live evaluation JSON — AFTER (post-fix, same session)
```json
{"A":{"pass":true,"detail":"fc=1 td=1","metric":1},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":true,"detail":"matched_clean=2","metric":100.0},"D":{"pass":true,"detail":"matched_any=2","metric":100.0},"E":{"pass":true,"detail":"parcel_linked=2","metric":100.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":0.0},"I":{"pass":true,"detail":"card_complete=2 of 2","metric":100.0},"J":{"pass":true,"detail":"deal_complete=2 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"lafayette","V2_LITMUS":null,"auctions_total":2}
```

### SQL VERIFICATION
```sql
SELECT public.pencil_dod_evaluate_county('lafayette');
-- returned the AFTER JSON above, run 2026-07-18T21:08Z via Supabase REST RPC
-- (direct psql pooler auth unavailable in this sandbox, same constraint as prior sessions;
-- REST RPC against mocerqjnksmhcjzxrewo.supabase.co is authoritative and live)

SELECT case_number, sale_type, last_seen_at, scraped_at
FROM multi_county_auctions WHERE county = 'lafayette';
-- 25000056CAAXMX | foreclosure | 2026-07-18T21:07:24.176398+00:00 | 2026-07-18T21:07:24.176398+00:00
-- TD-2022-28      | tax_deed    | 2026-07-11T21:38:27.378306+00:00 | 2026-07-11T21:38:27.378306+00:00
-- (tax_deed row unchanged, expected -- not present on live page this cycle)

-- Audit row (id=6766, confirmed persisted via GET-by-id round-trip):
-- INSERT INTO public.gold_standard_ultraloop_audit
--   (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
-- VALUES ('8f8f5eb5-2b8a-42eb-a2d8-29b756bf4c2f','native','lafayette','H', ..., ..., true)
-- RETURNING id=6766, created_at=2026-07-18T21:10:55.659991+00:00
```

## Ultraloop audit

Mode: `native` (Workflow tool, per this session's ultracode directive). Run: `wf_306b8531-5a3`. 2
agents (1 refuter + 1 logger), ~112K tokens, 31 tool calls, ~2.7 min. 1 row logged to
`gold_standard_ultraloop_audit` (id 6766, county `lafayette`, letter `H`, `survived=true`).

## Fleet coordination

`git stash` + `git pull --rebase origin main` run before this commit (parallel-fleet protocol —
picked up an unrelated shard-11/highlands/st_lucie report update from another concurrent session,
no overlap with lafayette). Per protocol, skipped the fleet-wide `gold_standard_loop()` /
`gold_standard_certify()` run since other shards are concurrently active; reported only this
county's live per-county evaluation. Only `scripts/lafayette_clerk_harvest.py` touched — no other
counties' rows, files, or shared code paths modified.

## Recommendation

lafayette is stable at 8/10 with H now durably fixed at the root cause (cron will keep it fresh
going forward). B/F remain the sole blockers, exhaustively researched across 8 sessions / 13
avenues with an existing standing recommendation to close or re-scope as a manual-records-request /
CAPTCHA-tooling task rather than continue automated research passes. One disclosed future risk:
H could regress again after the foreclosure case's Sept 2026 sale date passes, if no new auction
has been scraped by then to keep the `MAX(last_seen_at)` fresh — worth a lightweight staleness
check by whoever next touches this county, not an immediate action.
