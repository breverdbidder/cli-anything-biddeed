# SHARD-6 Session Report — loop run 3025, 2nd dispatch

dispatch_id: `8a9f3366-985c-406e-b338-01aa5ea9a76a`
chat_session: `architect-20260704T160000`
shard counties: lafayette, jackson, indian_river, santa_rosa, columbia
ultraloop_mode: **native** (Workflow tool — 2 parallel harvest agents + 2 adversarial refuters, one pair per county)

## Duplicate-dispatch detected

This exact `dispatch_id` + `chat_session` was already fully executed and merged to main as
commit `b3709229` (`SHARD6_RUN3025_SESSION_REPORT.md`). Before doing any new work, re-verified
all 5 counties live via `pencil_dod_evaluate_county`:

| County | Prior session "after" | This session baseline (live) | Drift? |
|---|---|---|---|
| lafayette | 1/10 (honest, ghost rows purged) | 1/10 | none |
| jackson | 8/10 (C/D fail) | 8/10 (C/D fail) | none |
| indian_river | 7/10 (C/D/I fail) | 7/10 (C/D/I fail) | none |
| santa_rosa | 8/10 (B/F fail) | 8/10 (B/F fail) | none |
| columbia | 1/10 (0 rows) | **3/10** (9 rows, E/G/H pass) | external — see below |

Confirmed the cited blockers from the prior report are unchanged, not stale claims:
`scripts/improve_parity_matching.py`'s `find_potential_matches()` is still an unimplemented
stub (`potential_matches = []`, never appended); columbia's `COLUMBIA_REALFORECLOSE_AUTH_CONFIGURED`
/ `COLUMBIA_REALTAXDEED_AUTH_CONFIGURED` repo variables are still unprovisioned; `realforeclose_aids`
(santa_rosa's only independent source) still has no winning-bid/sale-outcome column.

## columbia: external delta noted, not touched

9 rows now present (`columbia_clerk_html:SHARD2-V1`, `provenance='primary_scrape'`,
`last_seen_at` ~1h before this dispatch) — real, non-fabricated data (genuine addresses/parcels,
not the seed-pattern signature of prior columbia fabrication incidents) written by a different,
concurrent shard session via a script that is **not** in this repo (`git log -S` and repo-wide
grep for `columbia_clerk_html`/`SHARD2-V1` return zero hits — an uncommitted/ad-hoc run,
flagged here for whoever owns that session, not fixed by me). This moved E/G/H to PASS
(3/10). A is still FAIL: only the foreclosure lane is populated (fc=9, td=0) — both lanes are
required. Re-tested columbia's RealAuction lane directly this session: both
`columbia.realtaxdeed.com` and `columbia.realforeclose.com` AJAX PREVIEW endpoints still
302-redirect to the generic `www.realauction.com` marketing homepage under a real desktop
User-Agent — the anti-bot block documented in the prior session is confirmed still live, not a
quick fix. No safe columbia work available this session beyond this observation.

## jackson + indian_river: C/D fixed, ULTRALOOP-verified

Found genuine new leverage the prior session didn't have: live re-query showed 61 unmatched
jackson rows and 20 unmatched indian_river rows, none PropertyOnion-derived (`data_source`
values: `calendar_sweep_mca_v3`, `realforeclose`, `realauction_http_v3`, or null) — exactly the
"backfill missing auction dates" scenario the C/D playbook describes, not the broken
PropertyOnion-matcher stub path.

Ran a Workflow (ultracode): 2 harvest agents in parallel, each reusing the exact proven pattern
from `scripts/shard9_run3059_citrus_manatee_cd_parity.py` (built on
`scripts/shard2_run2450_ajax_realforeclose_harvest.py`'s live RealAuction AJAX calendar fetch —
no PropertyOnion, no Firecrawl dependency), followed by 2 independent adversarial refuters, one
per county, each required to re-run the live RPC itself, independently re-fetch 3 sampled
calendar dates fresh (not trust the harvester's log), check for PropertyOnion contamination,
verify idempotency by re-running the script live, and check cross-county isolation.

**Both claims SURVIVED.** One non-blocking finding from the indian_river refuter: both scripts
share the `parity_source` label prefix `tier1:shard6_run3025_2nd_dispatch_ajax_harvest` (a
namespacing/auditability gap — a `LIKE` query across both counties without a `county` filter
returns 81 rows instead of a per-county count) — every row's own `county` column is
independently verified correct, no actual cross-county write occurred. Flagged for future
dispatch label conventions (append county slug), not fixed retroactively since the existing
labels are not incorrect, only non-unique.

**Verified before/after** (`pencil_dod_evaluate_county`):

| County | Letter | Before | After |
|---|---|---|---|
| jackson | C | FAIL 3.2% (2/63) | **PASS 100.0% (63/63)** |
| jackson | D | FAIL 3.2% (2/63) | **PASS 100.0% (63/63)** |
| indian_river | C | FAIL 74.0% (57/77) | **PASS 100.0% (77/77)** |
| indian_river | D | FAIL 84.4% (65/77) | **PASS 100.0% (77/77)** |

**Score: jackson 8/10 -> 9/10 (only I fails). indian_river 7/10 -> 9/10 (only I fails).**

Both real: 61 + 20 = 81 rows independently re-verified live against the RealAuction calendar
(3 sample case numbers per county re-fetched fresh by the refuter, not the harvester), zero
PropertyOnion contamination, idempotent re-run confirmed (0 new promotions on rerun for both).
Logged 4 `gold_standard_ultraloop_audit` rows (`survived=true`), one per county-letter.

Scripts shipped: `scripts/shard6_run3025_2nd_dispatch_jackson_cd_parity.py`,
`scripts/shard6_run3025_2nd_dispatch_indian_river_cd_parity.py`. Both are one-time backlog
reconciliation scripts (not recurring scrapers) — already run to completion live this session,
no new wiring/cron/GHA needed per the WIRING MANDATE (nothing left to schedule).

I (card completeness) is unrelated to this fix and remains unresolved for both counties:
jackson 93.7% (59/63), indian_river 94.8% (73/77) — same structural zoning/`v_zoning_gold_standard_card`
dependency documented in the prior session, out of scope here.

## lafayette, santa_rosa: confirmed still genuinely blocked, no fix attempted

No new information changed the prior session's diagnosis. lafayette needs a real in-person
courthouse-calendar source (`county_auction_config.fc_method='in_person'`,
`daily_scrape_enabled=false`, no URLs configured) — a genuine build, not attempted. santa_rosa's
only independent source (`public.realforeclose_aids`) still has no outcome/sold-amount column
(only pre-sale fields: `judgment_amount`, `plaintiff_max_bid`, `auction_starts_at`) — B/F
structurally blocked pending a real post-sale outcome scraper. One lead worth flagging: several
santa_rosa rows' `case_clerk_url` point at `acclaim.srccol.com/AcclaimWeb/...` — an AcclaimWeb
instance, same platform family as the Brevard AcclaimWeb port target already documented in this
dispatch brief — a plausible shared build for a future session, not attempted here (out of
scope/budget this pass).

## Net result

| County | Before (this session) | After | Change |
|---|---|---|---|
| lafayette | 1/10 | 1/10 | unchanged, confirmed still honest |
| jackson | 8/10 | **9/10** | C/D fixed, live-verified |
| indian_river | 7/10 | **9/10** | C/D fixed, live-verified |
| santa_rosa | 8/10 | 8/10 | unchanged, confirmed still blocked |
| columbia | 3/10 (moved externally before this session) | 3/10 | unchanged, external delta only |

No `gold_standard_loop()`/`gold_standard_certify()` run this session — per parallel-fleet
guidance, per-county `pencil_dod_evaluate_county` used for all verification since other shards
may be mid-flight concurrently.

### SQL VERIFICATION

```sql
-- jackson, ran 2026-07-05 (live, via pencil_dod_evaluate_county RPC)
SELECT letter, pass, metric, detail FROM pencil_dod_evaluate_county('jackson');
-- C: pass=true, metric=100.0, detail="matched_clean=63"
-- D: pass=true, metric=100.0, detail="matched_any=63"

-- indian_river, ran 2026-07-05 (live, via pencil_dod_evaluate_county RPC)
SELECT letter, pass, metric, detail FROM pencil_dod_evaluate_county('indian_river');
-- C: pass=true, metric=100.0, detail="matched_clean=77"
-- D: pass=true, metric=100.0, detail="matched_any=77"

-- gold_standard_ultraloop_audit: 4 rows inserted, ids 3939-3942, all survived=true
```
