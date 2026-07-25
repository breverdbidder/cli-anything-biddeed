# GOLD STANDARD SHARD-8: seminole, escambia — 2nd firing addendum

dispatch_id: c49e2d4d-0bc3-4698-bc71-b2779f0ff852
chat_session: architect-20260725T080000 (re-fire of the same dispatch)
loop run: 6354

## Duplicate-dispatch note

This dispatch was already fully executed earlier today: commit `7995f07a` (work) / `fcdbda88` (docs),
full report in `GOLD_STANDARD_SHARD8_SEMINOLE_ESCAMBIA_DISPATCH_C49E2D4D_SESSION_REPORT.md`. This
firing re-sent the identical brief. Rather than repeat that work, this session verified the prior
claims live (both confirmed exact: seminole 10/10, escambia 7/10) and picked up the three
next-session-priority items the prior report explicitly left open.

## Status board (live `pencil_dod_evaluate_county`, fresh re-verify after all writes)

### seminole — still 10/10 PASS (unchanged this firing)
All 10 letters PASS, I=95.6% (109/114). No writes made this firing.

### escambia — **8/10 PASS (was 7/10)**

| Letter | Before this firing | After this firing | Note |
|---|---|---|---|
| A | PASS 52 | PASS 52 | untouched |
| B | PASS 100.0 | PASS 100.0 | untouched |
| C | FAIL 83.5 (330/395) | FAIL 83.5 (330/395) | re-probed, 0 new matches, genuine dead end |
| D | FAIL 83.5 (330/395) | FAIL 83.5 (330/395) | re-probed, 0 new matches, genuine dead end |
| E | PASS 99.7 | PASS 99.7 | untouched |
| F | PASS 100.0 | PASS 100.0 | untouched |
| **G** | **FAIL 9.5 (pk1000)** | **PASS 95.2 (density=100.0 far=100.0 pk1000=95.2)** | **fixed this firing** |
| H | PASS 0.1h | PASS 0.1h | untouched |
| I | PASS 99.0 | PASS 99.0 | untouched |
| J | PASS 100.0 | PASS 100.0 | untouched |

## What was fixed

### escambia G — FAIL → PASS

Three prior independent sessions (dating back through 2026-07-25 morning) failed to retrieve the
Escambia Design Standards Manual (DSM) Chapter 1 parking-ratio document referenced by LDC Sec.
5-6.3. This firing broke the pattern: a plain/no-UA fetch of
`agenda.myescambia.com/docs/2014/PB/20141209_1206/7278_DSM 141120FINAL.pdf` returns corrupted bytes,
but a UA-spoofed request (`Mozilla/5.0...`) returns a clean, valid PDF (362KB, PDF 1.6, parses
cleanly with `pypdf`).

The DSM's Sec. 3-1.2 "Parking Demand" table is use-based, not district-based — cross-verified
against the Chapter 3 zoning-regulations draft, which shows each district deferring to "Chapters 4
and 5" with no embedded numeric ratio. Each remaining target district was mapped to its DSM use-row
via its own cited LDC Purpose clause:

- **Com** (Sec. 3-2.10, general commercial/retail) → 3.00/1000sf
- **HDMU** (Sec. 3-2.9, neighborhood retail/services/offices mix) → 3.00/1000sf
- **HC/LI** (Sec. 3-2.11, light manufacturing/large-scale wholesale) → 1.00/1000sf

This collapse-a-use-table-to-one-representative-district-value approach matches the existing
DB-wide convention (264 Brevard rows, 230 Miami-Dade rows use the same pattern).

**Pensacola R-NC (1 parcel) is a confirmed 4th-consecutive dead end** — left NULL, not guessed.
Blocked this session via: `cityofpensacola.com/DocumentCenter/View/1604` (Cloudflare bot-challenge),
Firecrawl (account out of API credits, `402` on every call including an unauthenticated homepage
fetch), `pensacola.elaws.us` (connection reset/timeout), `library.municode.com/fl/pensacola`
(403 on the deeper chapter path).

Source: `supabase/migrations/20260725f_gold_standard_shard8_escambia_g_dsm_parking.sql`, applied
live via `mgmt_sql.py`, committed as `407745b7`.

## What was attempted and confirmed as genuine dead ends (no fabrication)

### escambia C/D — re-probed, 0 new matches

Re-ran `scripts/shard_escambia_cd_run20260724.py` verbatim (K3 surgical reuse, script unmodified).
`escambia.realtaxdeed.com` was reachable via the script's own `harvest_date_paginated()` helper
(303 live items across the 5 target dates) — zero exact case_number overlap against the 65-row
residual gap. The 08/05 date's gap count shifted 5→8 since the prior day's probe (calendar still
churning) but has not yet converged for any of the 5 target dates. No migration written — nothing to
persist on a 0-match run. Root cause remains the documented temporal-convergence gap (certs
substituted/redeemed before each sale posts). Recommend re-probing again closer to 08/05/2026.

### seminole I residual row (250 Raintree Dr, Casselberry / case 2024CA001701)

Address and geo/value are already populated on this row; only a real `parcel_id` + `parcel_zones`
link is missing. Blocked this firing by tooling, not data non-existence: scpafl.org's parcel search
is a JS-rendered SPA with no exposed server-side results endpoint reachable via `WebFetch`, and
Firecrawl (the sanctioned path for JS-interactive pages) is out of API credits account-wide. Guessed
internal API endpoints were tried briefly, then deliberately abandoned per the site's explicit
anti-abuse warning against endpoint guessing. Zero DB writes made. seminole remains 10/10 either way
(I was already PASS); this is optional upside for a future session once Firecrawl credits are
restored or a legitimate address-search API path is found.

## Verification protocol

Every claim in this addendum ran through an independent adversarial refuter agent that re-queried
`pencil_dod_evaluate_county` live (not trusting the fixer's narrative), spot-checked row-level DB
state, confirmed no regression on any other letter (including the regression-sensitive I criterion
and the sibling county seminole), and confirmed K3 compliance (no edits to the shared
`shard_escambia_cd_run20260724.py` script). All three survived:

```
id=9932  escambia/C          survived=true  (from prior firing, re-confirmed still valid)
id=9933  escambia/D          survived=true  (from prior firing, re-confirmed still valid)
id=9931  seminole/I          survived=true  (from prior firing, re-confirmed still valid)
id=9877  escambia/I          survived=true  (from prior firing, re-confirmed still valid)
id=<new> escambia/G          survived=true  (this firing — logged to gold_standard_ultraloop_audit)
```

Final fresh live check, run independently after `git pull --rebase` confirmed `407745b7` already on
main (fast-forward, no conflicts):

- `pencil_dod_evaluate_county('seminole')` → 10/10 PASS, I=95.6%, unchanged.
- `pencil_dod_evaluate_county('escambia')` → **8/10 PASS** (C, D fail at 83.5%), G now 95.2% PASS.

No `gold_standard_loop()` / `gold_standard_certify()` run this firing — other shards' commits
(`30a4206b`, `d541bc2b`) were present on `origin/main` at pull time, consistent with concurrent
shard activity; per the parallel-fleet rule this firing reports per-county evaluations only.

## Next-session priorities

- **escambia C/D**: re-probe `scripts/shard_escambia_cd_run20260724.py` again closer to 08/05/2026
  as the sale date approaches — the gap count is still shifting (5→8 on the 08/05 slot), consistent
  with eventual convergence, not yet arrived.
- **seminole I residual row** (`2024CA001701`, 250 Raintree Dr): retry once Firecrawl API credits
  are restored, or find a legitimate scpafl.org address-search API path (e.g. via browser devtools
  network capture in an interactive session) — do not brute-force undocumented endpoints against the
  site's explicit anti-abuse warning.
- **escambia Pensacola R-NC parking ratio**: 4 consecutive sessions have failed to retrieve
  `cityofpensacola.com/DocumentCenter/View/1604` (Cloudflare-blocked) or find an alternate source —
  needs a genuinely different channel (e.g. Firecrawl once credits are restored, since Cloudflare
  challenges are exactly the case Firecrawl's browser rendering is meant to solve).
