# GOLD STANDARD shard10 — citrus/seminole/lee/gulf — run3679 continuation

dispatch_id: `0a47f574-b17a-4d24-98c7-8ee032514f17`
session date: 2026-07-11 (03:15Z-03:46Z)

## Headline finding: this brief's baseline was stale

The dispatched brief's per-county metrics (citrus 9/10, seminole 8/10) reflect state
*before* an earlier wave of this same run3679 dispatch, which shipped directly to main
today at 00:31Z/01:58Z (commits `5730f17a`, `7542b46a`). Live `pencil_dod_evaluate_county`
was queried at session start and confirmed the real current state before any work began.

## Access note (for future sessions in this sandbox)

Direct `psql`/`psycopg2` connections (pooler and direct host, both ports) failed with
`password authentication failed` despite `SUPABASE_DB_PASSWORD` matching the CLAUDE.md
documented value — likely a stale password or wire-protocol egress restriction in this
sandbox. Two working alternatives were used instead, both HTTPS:
- **Reads**: PostgREST `POST {SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county` with
  the service role key.
- **Writes/DDL**: Supabase **Management API**
  `POST https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query` with
  `SUPABASE_ACCESS_TOKEN` (Bearer). No `exec_sql`/`exec` PostgREST RPC exists live (tried
  and got PGRST202 for `exec_sql`, `exec`, `run_sql`, and 5 other common names) — the
  Management API is the actual live write path, matching what the prior run3679 migration
  file's own comment says it used.

## BEFORE (live, confirmed at session start)

```json
citrus:   {"A":P,"B":P,"C":P,"D":P,"E":P,"F":P,"G":P,"H":P,"I":P,"J":P}  -- 10/10, already gold
seminole: {"A":P,"B":P,"C":P,"D":P,"E":P,"F":P,"G":P,"H":P,"I":P,"J":P}  -- 10/10, already gold
lee: {"A":true,"B":true,"C":false(91.9),"D":false(91.9),"E":false(93.8),"F":true,"G":true,"H":true,"I":false(89.7),"J":true} -- 7/10
gulf: {"A":true,"B":false,"C":false,"D":false,"E":false(78.6),"F":false,"G":true,"H":true,"I":false(28.6),"J":false(35.7 -- FABRICATED, see below)} -- 3/10
```

## Work done

### 1. citrus + seminole: confirmed already 10/10 — no action taken
No duplicate work performed. Verified live via `pencil_dod_evaluate_county`.

### 2. gulf J: purged 5 fabricated `bid_decisions` rows (ghost-success)

**CONFIRMED** (query evidence, not inference): the 5 `bid_decisions` rows backing gulf's
J=35.7% PASS-contribution were byte-identical across 5 *different* case numbers — same
`arv=109250.00`, `max_bid=35087.50`, `ml_score=0.7785`, `factors.distress_owner='unknown'`,
`factors.distress_location='gulf_county'`, and the *exact same* `created_at` timestamp to
the microsecond (`2026-06-19 11:12:22.865111+00`). This is a templated placeholder fill,
not real per-property Shapira/CMA output, and if left in place risks surfacing a fabricated
$35,087.50 max-bid recommendation against a real auction. Deleted live; shipped as
`supabase/migrations/20260711b_gold_standard_shard10_gulf_j_ghost_success_purge_run3679.sql`.
Logged to `gold_standard_ultraloop_audit` id=5294.

```
BEFORE: J deal_complete=5, metric=35.7   (false PASS-contributing)
AFTER:  J deal_complete=0, metric=0.0    (honest; needs a real generator run, not attempted
                                           this session -- see Deferred below)
```

### 3. lee E-letter (17-row gap) + gulf E-letter (3-row gap): researched, ZERO fixes applied

A 14-agent ULTRALOOP workflow (7 research + 7 adversarial-verify, real WebFetch/WebSearch
against LeePA/gis.leegov.com ArcGIS/Gulf Clerk/qPublic, 329 tool calls, 850K tokens) was run
against the 4 lee rows confirmed by the prior session to have real addresses, plus gulf's
3 address-less case numbers.

**Result: 6 of 7 targets are genuine "not found"** — real access dead-ends (LeePA's
ASP.NET search form doesn't render via WebFetch, Lee Clerk / Gulf Clerk / RealAuction /
qPublic all return 403 or require login, Lee's older ArcGIS REST endpoints are decommissioned)
confirmed independently by both the research and verify agents against Lee County's live
ArcGIS Parcels FeatureServer and other real sources. No addresses/parcels were guessed or
interpolated from nearby numbers.

**The 1 "found" candidate was REFUTED, not applied**: lee case `20-CA-005572` →
`parcel_id 21452513000000150` (14067 Danpark Loop, owner Spiegel — matches our `fl_parcels`
row exactly on address+owner+STRAP-encoded lot number). The adversarial verifier confirmed
the *address* independently via a second live fetch (floridaparcels.com), but could **not**
independently confirm the *case-to-parcel linkage* — the only source tying case
`20-CA-005572` to that address was an uncorroborated WebSearch summary, and WebSearch was
independently caught fabricating a fact (a wrong county name) elsewhere in the same
investigation. Per the adversarial default (any doubt → refute) and BLANK > WRONG, this was
**not written to the database**. lee E remains 93.8% (256/273), unchanged.

All 7 findings logged to `gold_standard_ultraloop_audit` ids 5374–5380 (6 survived=true,
1 survived=false).

## AFTER (live, confirmed at session end, 2026-07-11T03:46:27Z)

```json
citrus:   10/10 (unchanged, already gold)
seminole: 10/10 (unchanged, already gold)
lee: {"A":true,"B":true,"C":false(91.9),"D":false(91.9),"E":false(93.8),"F":true,"G":true,"H":true,"I":false(89.7),"J":true} -- 7/10, unchanged
gulf: {"A":true,"B":false,"C":false,"D":false,"E":false(78.6),"F":false,"G":true,"H":true,"I":false(28.6),"J":false(0.0 -- now HONEST)} -- 3/10, J corrected from a false PASS-contributing state
```

No letter flipped PASS this session. The concrete gain is a corrected (not inflated)
scoreboard for gulf, plus 7 rigorously-verified dead-ends for lee/gulf E that save a future
session from re-treading the same ground.

## Deferred (documented, not attempted — reasoning below)

- **lee C/D (251/273, need 260)**: requires re-harvesting stale RealForeclose AJAX calendar
  dates near their original auction week, or an authenticated RealForeclose session — a
  bigger scrape task than this session's remaining research budget allowed. Documented by
  the prior session too (`scripts/gold_standard_shard10_lee_cd_e_i_ajax_harvest_run3679.py`).
- **lee I (245/273, need 260)**: the dominant driver among already-parcel-linked rows is
  **missing `parcel_zones` coverage** (11 real STRAPs like `25-46-22-T1-00600.0120` have zero
  zoning row at all — a genuine ingestion gap, not a data-entry fix) plus 9 rows missing geo
  and 1 "MULTIPLE PARCEL" case that is structurally ambiguous (5+ distinct zone matches — no
  single correct answer). Real fix requires extending Lee's ArcGIS zoning spatial join, not a
  quick SQL patch — guessing a zone code here would repeat exactly the ghost-success pattern
  just purged from gulf J.
- **gulf B/C/D/F/I/J (real generator work)**: gulf has only 14 auctions total; genuinely
  building verified-outcome scraping, parity matching, and a real (non-templated) Shapira/CMA
  bid_decisions generator for 9 new tax-deed rows is out of scope for what could be
  responsibly verified this session. Deliberately not extending the ghost-success pattern
  with more of the same.
- **lee/gulf E remaining rows**: leeclerk.org, gulf gulfclerk.com, RealAuction, and qPublic
  are all either login-gated or bot-blocked (403) to unauthenticated fetch tools in this
  sandbox. A future session with an authenticated RealForeclose session
  (`REALFORECLOSE_EMAIL`/`PASSWORD` per the prior session's notes) or Firecrawl access could
  likely resolve several of these.

## SQL VERIFICATION

```sql
-- gulf, confirming the purge (executed 2026-07-11T03:41Z via Management API)
SELECT case_number, arv, max_bid FROM bid_decisions
WHERE case_number IN ('232019CA000060CAAXMX','232024CA000042CAAXMX','232024CA000072CAAXMX','232024CC000157CCAXMX','232025CA000037CAAXMX');
-- returns 0 rows (confirmed purged)

SELECT public.pencil_dod_evaluate_county('gulf');
-- J: {"pass": false, "detail": "deal_complete=0 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 0.0}
```
Timestamp: 2026-07-11T03:46:27Z

## PARALLEL-FLEET compliance

Per brief instructions, `public.gold_standard_loop()` / `certify()` were NOT run this
session (cannot confirm no other shard session is mid-flight); per-county
`pencil_dod_evaluate_county` evaluations above are the reported evidence instead.
