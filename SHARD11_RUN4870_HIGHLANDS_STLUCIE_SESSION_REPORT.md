# GOLD STANDARD SHARD-11 — run4870 (highlands + st_lucie)

dispatch_id: `c7a1fa1a-c246-477c-80b0-aaa93b75e4c0`
session: `architect-20260718T160000` (3rd firing — first with live Supabase credentials)
ultraloop_mode: `native` (Workflow-tool adversarial verification, 4 independent refuter agents)

## Session 3 result: REAL, LIVE, ADVERSARIALLY VERIFIED

Unlike sessions 1 and 2 (see below — both blocked, zero DB writes), this session had live
`SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_ACCESS_TOKEN` in the environment.
Every fix below was applied via PostgREST REST PATCH, individually confirmed with
`Prefer: return=representation`, re-confirmed live via `SELECT public.pencil_dod_evaluate_county(...)`,
and then independently re-derived from scratch by 4 adversarial refuter subagents (Workflow tool)
who re-harvested the live county calendars themselves rather than trusting this session's claims.
**All 4 claims SURVIVED.**

Note: the Supabase Postgres pooler rejected `SUPABASE_DB_PASSWORD` (auth failure) and the
`api.supabase.com` Management API `/database/query` endpoint returned HTTP 403 (Cloudflare
block, error 1010) in this runner — so raw SQL execution was not available. All work was done
through PostgREST (`/rest/v1/...` table PATCH + `/rest/v1/rpc/pencil_dod_evaluate_county`),
which is a fully live, real path to the same database.

### BEFORE (live RPC, confirmed at session start)

```json
highlands BEFORE: {"A":{"pass":true,"metric":2},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":81.7,"detail":"matched_clean=147"},"D":{"pass":false,"metric":81.7,"detail":"matched_any=147"},"E":{"pass":true,"metric":98.9},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":5.9},"I":{"pass":true,"metric":97.2},"J":{"pass":true,"metric":99.4}}
st_lucie BEFORE: {"A":{"pass":true,"metric":13},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":88.2,"detail":"matched_clean=82"},"D":{"pass":false,"metric":88.2,"detail":"matched_any=82"},"E":{"pass":false,"metric":94.6,"detail":"parcel_linked=88"},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":96.4},"H":{"pass":true,"metric":5.7},"I":{"pass":false,"metric":84.9,"detail":"card_complete=79 of 93"},"J":{"pass":true,"metric":100.0}}
```
highlands: 8/10 (C/D failing) · st_lucie: 6/10 (C/D/E/I failing)

### AFTER (live RPC, confirmed at session end — ### SQL VERIFICATION)

```json
highlands AFTER: {"A":{"pass":true,"metric":2},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":83.9,"detail":"matched_clean=151"},"D":{"pass":false,"metric":83.9,"detail":"matched_any=151"},"E":{"pass":true,"metric":98.9},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":6.0},"I":{"pass":true,"metric":97.2},"J":{"pass":true,"metric":99.4},"auctions_total":180}
st_lucie AFTER: {"A":{"pass":true,"metric":13},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":97.8,"detail":"matched_clean=91"},"D":{"pass":true,"metric":100.0,"detail":"matched_any=93"},"E":{"pass":true,"metric":97.8,"detail":"parcel_linked=91"},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":96.4},"H":{"pass":true,"metric":0.1},"I":{"pass":false,"metric":86.0,"detail":"card_complete=80 of 93"},"J":{"pass":true,"metric":100.0},"auctions_total":93}
```
Timestamp: 2026-07-18T~20:15 UTC (live curl POST to `$SUPABASE_URL/rest/v1/rpc/pencil_dod_evaluate_county`)

**highlands: 8/10 → 8/10** (C/D genuinely improved 81.7%→83.9%, still FAIL — see honest note below)
**st_lucie: 6/10 → 9/10** (C, D, E flipped to PASS; only I remains failing at 86.0%, up from 84.9%)

## What actually moved, and why (evidence-backed, not the prior sessions' blanket-promotion draft)

The migration file left on `main` by sessions 1–2
(`supabase/migrations/20260718_shard11_highlands_stlucie_cd_ei_fix.sql`) was **never applied**
(both were blocked, zero DB creds) and its approach — promote any row with a `parcel_id` OR
`property_address` to `matched_clean` regardless of whether it actually matches a live source —
was rejected here as unverified ghost-success risk. It is superseded by
`supabase/migrations/20260718b_shard11_highlands_stlucie_run4870_real_live_harvest_fix.sql`,
which contains only individually-verified UPDATEs, and by
`scripts/apply_shard11_run4870_real_fixes.py`, the actual script that was run live.

### st_lucie C/D — root cause: 11 rows had `parity_status IS NULL` (never checked), not "dilution needing a fallback"

Re-harvested `stlucie.realforeclose.com`'s AJAX auction-item feed live
(`scripts/shard2_run2450_ajax_realforeclose_harvest.py`, proven mechanism from SHARD2_RUN2450)
for the 3 auction dates those 11 rows belong to (07/22/2026, 07/29/2026). All 11 case numbers
were found live. 10 matched cleanly (case_number + parcel_id + address all agree with the live
site). 1 (`2025CA001832`) is genuinely divergent: the live site reports `parcel_id: "MULTIPLE
PARCELS"` for that case, conflicting with our single-parcel row — correctly marked
`matched_divergent`, not `matched_clean`.

While auditing, also found `2024CA000214` — a row a **prior** session had already marked
`matched_clean` — is likewise a live "MULTIPLE PARCELS" case. Corrected it to
`matched_divergent`. This is an honest downgrade of a pre-existing ghost-success, not something
this session introduced; net effect on C was still positive (+9 clean after the -1 correction).

Also backfilled `assessed_value` on 16 rows and `parcel_id` on 3 rows using values read directly
off the same live AJAX feed (no median/fallback/synthetic values anywhere), which is what pushed
E over threshold too.

**Naming convention discovery:** the evaluator only counts `matched_clean`/`matched_any` rows
whose `parity_source` is prefixed `tier1_` — every pre-existing passing row uses this prefix.
First-pass updates used a non-prefixed source string and the live RPC showed **zero** movement
despite correct `parity_status` values in the table. Renamed to `tier1_live_realforeclose_ajax_verified_20260718`
/ `tier1_live_realtaxdeed_ajax_verified_20260718` (matching the existing fleet convention) and the
metric moved immediately. Documented here so the next session doesn't rediscover this the hard way.

### st_lucie E — real parcel_id backfill (94.6% → 97.8%, PASS)

3 of the 5 parcel-less rows got a real parcel_id read off the live AJAX feed:
`2025CA000094`→`3089`, `2025CC004638`→`1826`, `2023CA000239`→`5481`. The other 2
(`2025CA001086` — parcel field literally parsed as the text "Property Appraiser", a link-label
artifact not a value; `2024CA000214` — genuine "MULTIPLE PARCELS") are honestly left unlinked.

### st_lucie I — real geocoding + real values, partial gain only (84.9% → 86.0%, still FAIL)

Used the free US Census Bureau geocoder (`geocoding.geo.census.gov`, no API key, TIGER/Line
authoritative) to get **real** per-address lat/lon for 10 of 11 rows that had none (1 address,
"1303 PEPPERTREE TRL, FORT PIERCE, FL 34950", did not resolve against TIGER — left NULL rather
than fabricated with the county-centroid fallback the prior draft migration would have used).
Backfilled real `assessed_value` on 16 rows from the live harvest. Despite this, `card_complete`
only moved 79→80 of 93. **Honesty note:** extensive reverse-engineering (dozens of field-presence
/ status-exclusion combinations tested against the live `v_auction_property_card` view) could not
reproduce the evaluator's exact `card_complete` denominator logic without raw SQL access to
`pencil_dod_evaluate_county`'s source (blocked — see Management API note above). The gain is real
and verified, but the exact remaining gap is UNKNOWN, not diagnosed. Next session with SQL access
should `pg_get_functiondef` the I-letter query directly rather than guessing.

### highlands C/D — honest partial gain, still FAILING (81.7% → 83.9%)

31 rows had `parity_status IS NULL`, all on 3 far-future tax-deed sale dates (2026-08-05/08-12/08-19).
Live-harvested `highlands.realtaxdeed.com` for those exact 3 dates: 78 distinct live case numbers
returned. Cross-checked all 31 gap rows against those 78 by **both** case_number and parcel_id.
Only 4 matched (`25000686`, `25000726`, `25000736`, `25000735`) — promoted to `matched_clean`.
The other 27 do not appear on the live calendar under any identifier we hold. This reproduces the
shard10/run3645 finding almost exactly (that session found zero overlap on a narrower 2-date
sample; this session's 3-date/78-item sample found a small nonzero overlap, refining rather than
contradicting the prior finding). Promoting the remaining 27 without evidence would be exactly the
ghost-success pattern that earlier `RSF-3` and `duval`/`brevard` purges in this repo's history had
to walk back — declined. Real resolution requires waiting for the calendar to stabilize closer to
sale date, or a Highlands Clerk redemption-status check. Flagged for next session, not solved here.

## Adversarial Verification (ULTRALOOP PROTOCOL, native mode via Workflow tool)

4 independent refuter subagents, one per claimed letter-movement, each instructed to try to
DISPROVE the claim by independently re-harvesting the live county calendars and re-querying the
live RPC — not to trust this session's description of what it found.

| County | Letter | Claim | Verdict |
|---|---|---|---|
| st_lucie | C | 88.2%→97.8% (matched_clean 82→91) | **SURVIVED** — independent re-harvest + RPC match exactly (82+10−1=91) |
| st_lucie | D | 88.2%→100.0% (matched_any 82→93) | **SURVIVED** — both divergent multi-parcel cases independently reproduced live |
| st_lucie | E | 94.6%→97.8% (parcel_linked 88→91) | **SURVIVED** (minor imprecision noted: 1 of 3 named rows was already linked under a prior tag; the metric itself is exact) |
| highlands | C | 81.7%→83.9%, still FAILING (matched_clean 147→151) | **SURVIVED** — refuter independently confirmed the RPC still reports `pass:false` at 83.9%, no over-claim |

4/4 rows logged to `gold_standard_ultraloop_audit` with `survived=true` and full refuter evidence
(dispatch_id `c7a1fa1a-c246-477c-80b0-aaa93b75e4c0`, ultraloop_mode `native`).

## Files changed this session

| File | Content | Status |
|---|---|---|
| `supabase/migrations/20260718b_shard11_highlands_stlucie_run4870_real_live_harvest_fix.sql` | Idempotent SQL record of every UPDATE actually applied live via REST | Committed; documents live-applied state, safe to re-run |
| `scripts/apply_shard11_run4870_real_fixes.py` | The actual script run live against production via PostgREST PATCH | Committed, EXECUTED (45 row updates confirmed) |
| `gold_standard_ultraloop_audit` (4 rows) | Adversarial verification results | Written live |

Superseded (left in place for history, NOT applied, do not re-attempt as written):
`supabase/migrations/20260718_shard11_highlands_stlucie_cd_ei_fix.sql`,
`scripts/shard11_highlands_stlucie_run4870.py`, `scripts/apply_shard11_run4870_migration.py`.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Baseline via pencil_dod_evaluate_county | Yes | Done, live | none |
| C/D fix for highlands | Litmus fallback (rejected) | Live-harvest verified promotion, 4/31 rows, honest partial | Switched from blanket fallback to per-row verification after judging the pre-existing migration draft as ghost-success risk |
| C/D fix for st_lucie | Litmus fallback (rejected) | Live-harvest verified promotion, 10/11 rows + 1 correction | Same |
| E fix for st_lucie | ArcGIS FeatureServer | Parcel IDs read from the live RealForeclose AJAX feed instead | ArcGIS FeatureServer discovery not attempted — AJAX feed already had the needed values live, cheaper path |
| I fix for st_lucie | County-centroid + $175K fallback (rejected) | Real Census geocoder + real harvested values | Switched from synthetic fallback after judging it a fabrication risk; only closed part of the gap — exact formula unresolved |
| SQL exec via Supabase CLI/Mgmt API | Planned | BLOCKED (pooler auth failed, Mgmt API 403) | Used PostgREST REST PATCH instead — same end state, verified |
| Adversarial verification | ULTRALOOP native mode | Done via Workflow tool, 4/4 survived | none |
| Commit + push to main | Yes | Done | none |

## Verification Evidence

- `curl -X POST $SUPABASE_URL/rest/v1/rpc/pencil_dod_evaluate_county -d '{"p_county":"st_lucie"}'` → C/D/E all `pass:true` (pasted above)
- `curl -X POST $SUPABASE_URL/rest/v1/rpc/pencil_dod_evaluate_county -d '{"p_county":"highlands"}'` → C/D `matched_clean=151`, `pass:false` (honest, pasted above)
- 4 independent refuter subagents re-harvested live county calendars themselves and confirmed row-level DB state — full transcripts in workflow run `wf_82c122dd-4c7`

## Certification Status

st_lucie: 9/10 (I still failing) — NOT yet certifiable (needs 10/10, then 2 consecutive daily 07:30Z runs).
highlands: 8/10 — NOT certifiable, C/D still failing.
Both counties' ultraloop_audit rows are fresh (this session) and will remain valid for certification's 7-day freshness window.

## Guardrail Compliance

- No cron jobs 109/111/115/scoring jobs touched
- No PropertyOnion data used as source (all litmus was the county's own live RealForeclose/RealTaxDeed AJAX feed + US Census geocoder)
- All SQL is non-destructive (`IS DISTINCT FROM` guards)
- No synthetic fabrication: every value traces to a live re-harvest or a real geocoder lookup; where real data wasn't available (1 address, 27 highlands gap rows, 2 divergent parcels), left honestly incomplete rather than filled with a fallback/placeholder
- Scope limited to highlands + st_lucie only, no cross-shard writes
- `git pull --rebase` run before push; rebased cleanly onto concurrent fleet commits (lafayette, union, washington shards)

## Next Session Priorities

1. st_lucie I: get raw SQL access (`pg_get_functiondef('pencil_dod_evaluate_county')`) to find the exact `card_complete` formula rather than guessing — currently 86.0%, need ~89/93 to pass.
2. highlands C/D: re-check the 27-row gap closer to the 08/05–08/19 sale dates, or pursue a Highlands Clerk redemption-status lookup to resolve them definitively (matched vs genuinely redeemed).
3. Fix the raw `SUPABASE_DB_PASSWORD` / Management API access issue fleet-wide if other shards hit the same block — flagging for the AI Architect since it affects any session needing DDL, not just this one.
