# Gold Standard Shard-2: nassau + st_johns — Session Report

- dispatch_id: `ffe1aa89-758e-42a2-8ac2-73ceeee9d290`
- chat_session: `architect-20260724T000000`
- loop run: 6080
- date: 2026-07-24

## Scope

Assigned shard: **nassau** (10/10 per brief) and **st_johns** (5/10 per brief:
C/D/E/I/J failing). Per PARALLEL-FLEET RULES, only these two counties were
touched. `gold_standard_loop()`/`gold_standard_certify()` were **not** run
full-fleet this session — other shards were mid-flight (confirmed via
concurrent pushes to main during this session: `aea1dbf6`, `eaf5732d`), so
per-county `pencil_dod_evaluate_county()` was used instead, as instructed.

## nassau — no action needed

Live-verified at session start and again at close: **10/10 PASS**, unaffected
by this session's writes (no nassau rows were touched).

```json
BEFORE == AFTER (unchanged):
{"county":"nassau","auctions_total":34,
 "A":{"pass":true,"metric":5,"detail":"fc=29 td=5"},
 "B":{"pass":true,"metric":100.0,"detail":"verified=11 closed_sold=11"},
 "C":{"pass":true,"metric":100.0,"detail":"matched_clean=34"},
 "D":{"pass":true,"metric":100.0,"detail":"matched_any=34"},
 "E":{"pass":true,"metric":100.0,"detail":"parcel_linked=34"},
 "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=11 closed_sold=11"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far= pk1000="},
 "H":{"pass":true,"metric":7.6,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":true,"metric":100.0,"detail":"card_complete=34 of 34"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=34 (triangle + two-arm CMA + ml_score + max_bid)"}}
```

## st_johns — before / after

```json
BEFORE (session start):
{"county":"st_johns","auctions_total":50,
 "A":{"pass":true,"metric":3,"detail":"fc=47 td=3"},
 "B":{"pass":true,"metric":100.0,"detail":"verified=1 closed_sold=1"},
 "C":{"pass":false,"metric":86.0,"detail":"matched_clean=43"},
 "D":{"pass":false,"metric":86.0,"detail":"matched_any=43"},
 "E":{"pass":false,"metric":92.0,"detail":"parcel_linked=46"},
 "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=1 closed_sold=1"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000="},
 "H":{"pass":true,"metric":8.3,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":false,"metric":88.0,"detail":"card_complete=44 of 50"},
 "J":{"pass":false,"metric":88.0,"detail":"deal_complete=44 (triangle + two-arm CMA + ml_score + max_bid)"}}

AFTER (session end):
{"county":"st_johns","auctions_total":50,
 "A":{"pass":true,"metric":3,"detail":"fc=47 td=3"},
 "B":{"pass":true,"metric":100.0,"detail":"verified=1 closed_sold=1"},
 "C":{"pass":false,"metric":92.0,"detail":"matched_clean=46"},
 "D":{"pass":false,"metric":92.0,"detail":"matched_any=46"},
 "E":{"pass":false,"metric":92.0,"detail":"parcel_linked=46"},
 "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=1 closed_sold=1"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000="},
 "H":{"pass":true,"metric":8.6,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":false,"metric":92.0,"detail":"card_complete=46 of 50"},
 "J":{"pass":false,"metric":92.0,"detail":"deal_complete=46 (triangle + two-arm CMA + ml_score + max_bid)"}}
```

Letter-count is still 5/10 (C, D, E, I, J remain FAIL — all above the 95%
threshold gap needs 48/50, currently 46/50), but every failing metric moved:
C/D 86.0%→92.0%, E/I 88-92%→92.0% (E stayed flat since it was already 92%
pre-session; I moved), J 88.0%→92.0%. **All five now share the exact same
4-row denominator gap** (see Structural Blocker below) — closing that one
gap flips all five letters simultaneously.

## Root cause fixed (shared code, benefits all counties)

`scripts/county_outcome_harvester.py`'s `fix_parity_status()` PATCHed
`parity_status` to `matched_clean`/`matched_divergent` via REST but never
stamped `parity_source`. The evaluator requires `parity_source LIKE 'tier1%'`
for C/D credit, so any county this harvester touches was silently
undercounting C/D. Fixed to stamp `parity_source` on every write going
forward (commit `3edf3832`).

## What was fixed this session

1. **C/D (43→46 matched)**: 3 st_johns rows (CA26-0218, CA26-0499, CA25-1404)
   already had real parcel_id + property_address but `parity_source=NULL`
   from the harvester bug above — promoted to `matched_clean` with a real
   source tag. Migration:
   `supabase/migrations/20260724_gold_standard_shard2_stjohns_cd_parity_source_backfill.sql`.
2. **I (44→46 card-complete)**: parcels `0733220860` (742 Pullman Cir) and
   `0263350890` (201 Rambling Brook Trl) were entirely absent from
   `parcel_zones` (a coverage gap — G already passes on st_johns's existing
   coverage). Both `zone_code=PUD` **VERIFIED** live via St. Johns County's
   official ArcGIS REST GIS (`gis.sjcfl.us`), point-in-polygon against each
   parcel's real geometry, independently re-confirmed by an adversarial
   refuter agent before the write. Migration:
   `supabase/migrations/20260724_gold_standard_shard2_stjohns_i_parcel_zones_backfill.sql`.
3. **J (44→46 deal-complete)**: same 2 newly-unblocked cases (CA26-0218,
   CA25-1404) — ran `scripts/stjohns_j_backfill_run6080_shard2.py` (same
   Shapira-formula contract as the 2026-07-18 st_johns J backfill) to
   populate `bid_decisions`.

## Structural blocker (documented, not fabricated)

4 st_johns cases have **zero** real data beyond the case number:
`CA22-1233`, `CA25-1470`, `CC25-0048`, `CC25-2919`. An 8-agent research +
adversarial-verify workflow (ULTRALOOP PROTOCOL) confirmed all four are
genuinely unfindable via public sources this session:
- St. Johns Clerk's civil case docket search (`apps.stjohnsclerk.com/Benchmark`)
  is CAPTCHA-gated (hCaptcha sitekey confirmed in page source) — cannot be
  queried by automated fetch.
- The Clerk's official-records portal (`Landmark`) and the foreclosure
  auction calendar (`saintjohns.realforeclose.com`) both return HTTP 403 to
  non-browser requests.
- General web search for all four case numbers (plus common format
  variants) returned zero indexed results anywhere, including legal
  aggregators (UniCourt, Trellis.law).

No property address or parcel ID was written for these 4 cases —
generating a bid recommendation, zoning match, or parity claim for a
property we know nothing about would be a fabricated ghost-success, banned
by this project's Honesty Protocol. BLANK > WRONG. This is the same
structural-blocker pattern already documented for Martin County's E gap in
prior sessions (CAPTCHA/login/bot-block across every available public
source, only remaining path being a paid manual clerk record request —
out of session scope).

**Next-session priority if st_johns is reassigned**: the only path past
these 4 cases is a manual/paid clerk record request
(`RecordRequest@stjohnsclerk.com` or equivalent), or a browser-automation
tool capable of solving the hCaptcha challenge — neither is in scope for an
autonomous session. If a browser-automation tool becomes available,
re-attempt the Benchmark case search directly.

## Verification evidence

- `pencil_dod_evaluate_county('nassau')` — run at session start and end,
  identical, pasted above.
- `pencil_dod_evaluate_county('st_johns')` — run at session start, after
  each fix (parity_source backfill, parcel_zones backfill, J generator),
  and at session end; before/after pasted above.
- All DB writes executed live via the Supabase Management API
  (`api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query`) and
  the PostgREST REST API — not files-only. Row counts and content
  confirmed via each migration's own checkpoint `SELECT`.

## Commits (pushed directly to main, no side branches)

1. `3edf3832` — harvester root-cause fix + C/D parity_source backfill (3 rows)
2. `ebab0bb5` — I zoning backfill (2 parcels) + J generator (2 cases)

Both required `git pull --rebase` before push due to concurrent shard
activity on main (other sessions' commits: `aea1dbf6`, `eaf5732d`) — no
conflicts, per PARALLEL-FLEET RULES.
