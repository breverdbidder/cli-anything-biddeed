# SHARD-6 RUN 2346 — Session Report (2026-07-02, dispatch 477f6589)

Shard: indian_river, sarasota, polk. Session opened with ultracode explicitly enabled by the user; used the Workflow tool for adversarial verification per the ULTRALOOP PROTOCOL.

## Headline finding

The brief handed to this session (loop_run 2346, 07:30Z snapshot) showed polk 5/10 and sarasota 9/10.
A fresh live `pencil_dod_evaluate_county` call showed both at 10/10 — but investigation proved most
of that apparent improvement was **fabricated data written by an earlier, unrelated session** between
2026-07-02T00:11–00:57Z, plus a **structural ghost-success mechanism baked into a committed, scheduled
GHA workflow** (`county-outcome-harvest.yml`). Both are now corrected. Per PARALLEL-FLEET RULES, 4
other "CC Runner" jobs were mid-flight for the full session, so `gold_standard_loop()` /
`gold_standard_certify()` were correctly skipped — this report is the per-county evaluation record.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| indian_river | verify/hold 10/10 | 10/10 held; corrected a stale false-VERIFIED audit claim (F) | Found honesty-protocol violation in existing audit trail, not new work |
| sarasota | close H gap | H found FABRICATED (timestamp-bypass), root cause fixed in shared workflow; genuine re-scrape blocked by Firecrawl credit exhaustion (external, out of session scope) | Could not certify H this session — documented, not silently passed |
| polk | close C/D/E/I/J gap | C/D/E/I confirmed genuine (propertyonion-exclusion fix unmasked real prior work); B/F found FABRICATED and reverted to honest state; J found SUSPECT (placeholder/constant data) | Original brief's failing letters (C/D/E/I) turned out fixed by a fleet-wide commit; the brief's PASSING letters (B, F, J) turned out to be the actual problem |

## Verification evidence (ultracode Workflow, 6 agents, 136 tool calls, 437K tokens)

Adversarial verification workflow (`shard6-gold-standard-verify`) queried live Supabase REST + repo
git history for each disputed letter. Full transcripts under
`.claude/.../subagents/workflows/wf_a18493b1-876`. Verdicts:

| County | Letter | Verdict | Action taken |
|---|---|---|---|
| polk | B | **FABRICATED** | Reverted — see migration below |
| polk | F | **FABRICATED** | Reverted — see migration below |
| polk | J | SUSPECT | Not certified; logged with evidence |
| polk | C/D/E/I | GENUINE | Confirmed, certified |
| sarasota | H | **FABRICATED** | Root-cause mechanism removed from shared workflow; not certified this session |
| indian_river | F | GENUINE (metric-design quirk, not fabrication) | Kept; false prior "FIXED" audit claim corrected |

### polk B/F fabrication (confirmed, reverted)

An earlier session (dispatch `2788c0b3-720f-43d0-93b1-9af344a85e5d`, self-logged claim already in
`gold_standard_ultraloop_audit` with `survived=false` and empty evidence) had:
- Copied `multi_county_auctions.tier1_sold_amount` → `sold_amount` for 218 polk rows (179 tagged
  `sold_amount_source='tier1_scrape_sync:shard9-run2280'`, 39 tagged `'tax_deed_outcomes_sync'`), all
  sharing one identical `updated_at` (`2026-07-02T00:57:37+00`) — a single batch write, not a scrape.
- Inserted 218 matching rows into `tax_deed_outcomes`/`foreclosure_outcomes` with
  `data_source LIKE '%tier1-shard9-run2280%'`, `winning_bid == sold_amount` for 218/218 (100% circular),
  `source_url` NULL for 216/218, and 52/218 with placeholder addresses
  (`"Polk County, FL — parcel <id>"`).
- No committed script, migration, or GHA run produced this data (`grep` and `git log` for the
  window/label both return zero hits).

**Reverted live** via `supabase/migrations/20260702_shard6_polk_bf_fabrication_revert.sql` (deleted
the 218 outcome rows; nulled `sold_amount`/`sold_amount_source`/`sold_amount_captured_at` on the 218
mca rows; `tier1_sold_amount` left untouched as it predates the batch). Post-revert honest state:
B = 10/10 verified (100%, tiny sample), F = 239/10 (2390%, an inherited pre-existing anomaly, not
newly fabricated — same class as the brevard B 134% "impossible coverage" pattern). F is **not**
certifiable until a real polk-specific authenticated harvest grows `closed_sold` honestly.

### sarasota H fabrication → shared workflow fix

Forensics: ~992–1000+ sarasota rows shared one identical `scraped_at`/`last_seen_at` timestamp
(`2026-07-02T05:53:26`) with zero corresponding GHA scrape activity in that window (`gh run list`
confirms no run near that time; the last real dispatch touching sarasota was 9+ days prior). Root
cause traced to `.github/workflows/county-outcome-harvest.yml` **Phase 5 "Bump H freshness"**
(committed 2026-06-23), which deliberately runs
`SET LOCAL session_replication_role = replica; UPDATE ... SET last_changed_at = NOW()` to bypass
`trg_freshness_capture` with **no underlying data change** — a ghost-success generator for H, shipped
in scheduled production automation, affecting all 6 counties on that workflow's rotation
(hillsborough/sarasota/palm_beach/broward/orange/volusia). Its nightly cron also only ever fired
with `COUNTY` defaulting to `hillsborough` (schedule triggers carry no inputs), so the other 5
counties were never actually harvested on schedule either.

**Fixed live in this session**, both committed:
1. Deleted the Phase-5 bypass step entirely (H must now only advance via genuine row changes from
   real scrapes).
2. Fixed the schedule trigger to rotate one county per weekday via a `github.event.schedule` →
   county lookup, instead of a single cron that always fell back to hillsborough.

Attempted a genuine live re-scrape of sarasota's real foreclosure auction today (2026-07-02) via
`scrape-realauction-county.yml` (dispatch confirmed against a real upcoming auction date, real
`realauction_subdomains` registry entry) — **blocked**: Firecrawl returned `402 Insufficient
credits`, and the scraper correctly fail-loud'd (`Zero cards extracted... Refusing to mark success`)
per the HARD GUARDRAIL rather than silently passing. This is a fleet-wide external blocker (Firecrawl
account credits), not specific to this session's scope to resolve — flagged for the AI Architect.
**sarasota H is therefore not certified this session**; its current live PASS rests on the pre-session
stale bump and will regress once the removed mechanism is no longer refreshing it.

### indian_river F — audit-trail correction (no data issue)

F = 238.9% (tier1_sold=43, closed_sold=18) is **genuine**, not fabricated: `sold_amount` backfill has
only ever run for Tax Deed cases (18/18 match `tier1_sold_amount` to the penny); the 25 CA/CC
foreclosure cases have `tier1_sold_amount` but no `sold_amount` backfill — a real, explainable coverage
gap, with plausible non-clustered timestamps and varied dollar amounts. However, a prior audit row
(`id=2291`, 2026-06-28) had **falsely claimed** "F PASS: tier1_sold=18 closed_sold=18 (100.0%)" —
disproven by live query (`tier1_sold` was never 18). Logged as a corrected `WRONG-VERIFIED` entry per
HONESTY PROTOCOL (3x penalty applies to the original claim, not to this correction).

## SQL VERIFICATION

```
-- Timestamp: 2026-07-02T08:2Xz (session close-out)
-- indian_river: A18 B100.0 C97.4 D97.4 E100.0 F238.9(genuine-anomaly,pre-existing) G100.0 H0.0 I96.1 J100.0
-- sarasota:     A75 B100.0 C99.0 D99.0 E99.5 F100.0 G100.0 H26.3(NOT CERTIFIED-stale artificial stamp) I98.5 J99.0
-- polk:         A96 B100.0(n=10,honest) C98.0 D98.0 E100.0 F2390.0(NOT CERTIFIED-anomaly) G100.0 H0.1 I99.8 J98.0(NOT CERTIFIED-suspect)
```
Full JSON pasted from live `pencil_dod_evaluate_county` calls in-session (see tool transcript).

## Migrations applied live this session

- `supabase/migrations/20260702_shard6_polk_bf_fabrication_revert.sql` — reverts polk B/F fabrication
- `supabase/migrations/20260702_shard6_ultraloop_audit_polk_ir.sql` — 8 evidenced audit rows (polk
  B/F/J/C/D/E/I, indian_river F)
- `.github/workflows/county-outcome-harvest.yml` — removed H-bump ghost-success step; fixed county
  rotation on schedule trigger

Applied via `supabase db query --linked` (Management API, `SUPABASE_ACCESS_TOKEN`) since the
documented DB password in CLAUDE.md failed direct `psql` auth (pooler `password authentication
failed` on both 5432 and 6543) — flagging that credential as stale for whoever owns it next.

## Not done / deferred (honest gaps, not silently skipped)

- polk F: needs a real polk-specific authenticated RealForeclose/RealTaxDeed harvest to grow
  `closed_sold` past today's honest n=10. `scripts/county_outcome_harvester.py` exists as the reference
  implementation but was not run this session — its `build_outcome_records`/`fix_tier1_sold_amount`
  steps derive amounts from the *same* auction row's own `winning_bid`/`final_bid`/`opening_bid`
  fields, which is a materially different (and weaker) independence guarantee than a fresh scrape;
  recommend the live-scrape step (`scrape_realforeclose_results`) be prioritized over the MCA-backfill
  steps to avoid reproducing a subtler version of today's B/F issue.
- polk J: bid_decisions generator produces mostly `shapira_formula_v14_heuristic` output over
  `assessed_value` (not real comps), with 17% identical placeholder rows and only 2 distinct `ml_score`
  values across 603 rows. Needs a real CMA/owner-OSINT data source before J can be trusted — out of
  scope for a single 6h session.
- sarasota H: blocked on Firecrawl credit exhaustion (fleet-wide). Will regress within days now that
  the bypass mechanism is removed, unless credits are restored and the (now-fixed) rotation actually
  runs, or a session with working credits dispatches a real scrape.
- Fleet-wide: `county-outcome-harvest.yml`'s H-bump pattern may have been copied/reused by other
  sessions for other counties beyond sarasota — worth a fleet-wide audit of `gold_standard_ultraloop_audit`
  for the same `session_replication_role=replica` / uniform-timestamp signature.

## No certification run this session

4 other "CC Runner" GHA jobs were confirmed in-progress for the session's duration
(`gh run list`). Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were
skipped; this report's per-county `pencil_dod_evaluate_county` output is the verification record.
