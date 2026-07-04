# SHARD-1 Session Report (loop run 2820) — baker, citrus, okeechobee, pinellas, bradford (2026-07-04)

dispatch_id: 3091a281-3413-4599-b39b-74174e33ba70
chat_session: architect-20260704T000000

## Summary — no letter movement this session, honestly reported (BLANK > WRONG)

Every failing letter in this shard's brief was independently re-diagnosed this session
and found to already sit at a genuine, previously-exhausted data ceiling. No safe,
non-fabricated fix was available within this session's real tool access. Per the
HONESTY PROTOCOL, this report documents the investigation and infra findings rather
than inventing progress. All 5 counties' live metrics are **unchanged** from the
dispatch brief (re-verified via `pencil_dod_evaluate_county`, pasted below).

## Ground-truth verification performed first (before touching anything)

Confirmed the live Supabase project (`mocerqjnksmhcjzxrewo`) is real and reachable:
- `SUPABASE_DB_PASSWORD` from CLAUDE.md/env **fails auth** against both the pooler
  (`aws-0-us-west-2.pooler.supabase.com:6543`) and direct host
  (`db.mocerqjnksmhcjzxrewo.supabase.co:5432`) — independently reconfirms the finding
  already documented in `migrations/run_migration.js` (stale as of 2026-07-03). No
  `supabase` CLI is installed in this sandbox either.
- The working path is `migrations/run_migration.js` (Supabase Management API,
  `SUPABASE_ACCESS_TOKEN`, no DB password needed) — verified live with `SELECT 1` and
  used for all read verification below. `rpc/exec`/`exec_sql`/`run_sql` do not exist on
  this project; PostgREST only exposes `public`/`graphql_public`/`pascal` schemas.
- All 5 counties' `gold_standard_county_status` + live `pencil_dod_evaluate_county`
  results match the dispatch brief exactly (pasted in full below) — the brief is not
  stale.

## Per-letter findings (CONFIRMED unless labeled)

**citrus / okeechobee / pinellas C+D** — CONFIRMED genuine data-coverage ceilings, not
matcher bugs. Traced the actual `refresh_parity_tier1_outcomes()` matcher logic
(case_number match first, then parcel_id; excludes PropertyOnion via
`data_source <> 'propertyonion'` per `20260702_shard5_evaluator_propertyonion_exclusion.sql`).
The matcher itself is sound and has been adversarially re-verified across many prior
sessions (citrus: `SHARD9_RUN2550`; pinellas: `SHARD13_RUN2753`; okeechobee: this
morning's `20260703_shard1_okeechobee_cd_sold_third_party_allowlist_fix.sql`, which I
confirmed **did** execute live — `2026TD020/028/029` now correctly `matched_clean`/`sold`).
The remaining gap in all three counties is independent-outcome-source coverage:
citrus/pinellas need more clerk/RealForeclose sale-result rows than exist yet; okeechobee's
remaining 13 rows are 10 civil (CA/CC) foreclosure cases blocked on **Civitek OCRS, which
is Cloudflare-Turnstile-gated on every search submission** (confirmed by a prior session's
curl + headless-Playwright attempt) — correctly not re-attempted here, since defeating a
CAPTCHA/bot-check is out of scope, and two prior sessions already reverted fabricated
"fixes" for this exact county (`20260702_shard4_okeechobee_bf_fabrication_revert.sql`,
run twice).

**pinellas B** — CONFIRMED same ceiling: 82 of 132 closed sales lack an independent
outcome record. A 2026-07-02 attempt to backfill this was caught as ghost-success
(fabricated `sold_amount` copy) and reverted. Not re-attempted without a real new source.

**bradford A/B/F** — CONFIRMED not a bug: all 4 Bradford rows are **future** auctions
(2026-07-16 through 2026-08-20), `auction_status='upcoming'`, `sold_amount=NULL`. Zero
closed sales exist yet, so B/F genuinely cannot move today. A prior session
(`20260703_shard3_bradford_real_foreclosure_ingestion_and_taxdeed_zero_confirmed.sql`)
also confirmed Bradford's tax-deed lane is genuinely empty (A's `td=0` is real, not a
scraper gap) — matches this session's live read (`fc=4 td=0`).

**bradford C/D/E/I** — attempted real public-records enrichment (parcel_id + address
for the 4 known case/defendant pairs) to unblock E/I ahead of the sales themselves.
Blocked by infra, not by data availability:
- `bradfordclerk.com` returns HTTP 403 to both `curl` and `WebFetch` (WAF/bot-block).
- `bradfordappraiser.com` search is a JS-driven GIS map with no discoverable
  owner-name query-string API (confirmed via WebFetch content analysis); a plain
  WebSearch for the 4 defendant names surfaced no indexed parcel pages.
- No Firecrawl access in this sandbox (no CLI, no `FIRECRAWL_API_KEY`, `firecrawl-py`
  not installed) — matches a prior session's identical finding for Hernando's
  LandmarkWeb (`SHARD7_RUN2346_SESSION_REPORT.md`).
- **New finding this session**: unlike what prior reports assumed, `npx playwright`
  installs successfully and `/usr/bin/chromium` **is** present in this sandbox. Real
  browser automation may be viable for JS-driven-but-not-bot-gated sites like
  `bradfordappraiser.com/GIS/` (as opposed to Civitek OCRS, which is Turnstile-gated
  and out of scope regardless). Not built this session — a from-scratch interaction
  script against an unfamiliar map UI is a real engineering task, not a quick patch,
  and I did not want to rush it and risk a wrong parcel match. Flagging as a concrete,
  scoped lead for the next session targeting bradford.

## Verification evidence (live, unchanged from brief — `pencil_dod_evaluate_county`, 2026-07-04T00:12:01Z)

```
baker:      A P(1) B P(100.0) C P(100.0) D P(100.0) E P(100.0) F P(100.0) G P(100.0) H P(8.5) I P(100.0) J P(100.0)  -- 10/10
citrus:     A P(30) B P(100.0) C F(31.6) D F(35.1) E P(100.0) F P(100.0) G P(100.0) H P(8.5) I P(96.6) J P(100.0)   -- 8/10
okeechobee: A P(10) B P(100.0) C F(50.0) D F(70.0) E P(100.0) F P(100.0) G P(100.0) H P(8.5) I P(96.7) J P(100.0)   -- 8/10
pinellas:   A P(34) B F(37.9)  C F(91.0) D F(91.0) E P(99.7)  F P(100.0) G P(100.0) H P(7.5) I P(95.2) J P(96.6)    -- 7/10
bradford:   A F(0)  B F(null)  C F(0.0)  D F(0.0)  E F(0.0)   F F(null)  G P(100.0) H P(7.5) I F(0.0)  J P(100.0)   -- 3/10
```

All values match `gold_standard_county_status` / the dispatch brief exactly. No
regressions, no gains.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Verify DB/infra access | confirm live project + write path | confirmed; psql/pooler password stale (independently reconfirmed), Management API (`run_migration.js`) works | none — this was step 1 precisely to avoid fabricating against a environment I hadn't verified |
| citrus/okeechobee/pinellas C/D | fix or advance | re-diagnosed, confirmed genuine ceilings already exhausted by prior sessions; no new fix attempted | did not chase Civitek OCRS (Turnstile-gated) or build unverified scrapers under time pressure |
| pinellas B | fix or advance | confirmed same ceiling, prior fabrication already reverted; not re-attempted | — |
| bradford A/B/F | fix | confirmed structurally blocked (0 closed sales, 0 tax deeds) — not a bug | — |
| bradford C/D/E/I | enrich via public records | blocked — clerk site 403s, appraiser site needs browser automation not built this session | new lead: playwright+chromium IS available in this sandbox (contradicts prior assumption) — scoped for next session |

## Deviation log

No code or DB changes were made this session. The single most consequential deviation
from "execute and ship" is a **negative** one: I chose not to attempt CAPTCHA-adjacent
scraping (Civitek OCRS) or a rushed, unverified browser-automation script against an
unfamiliar GIS UI, because both prior sessions on these exact counties reverted twice
for fabricating exactly this kind of forced progress. Downstream impact: this shard's
5 counties remain at their current honest scores (baker 10/10, citrus 8/10, okeechobee
8/10, pinellas 7/10, bradford 3/10) pending real new data sources.

## Not run this session (per PARALLEL-FLEET RULES)

`gold_standard_loop()` / `gold_standard_certify()` were not run — other shards are
actively committing in parallel today (dozens of same-day commits across other shard
numbers touching other counties). Verification used per-county
`pencil_dod_evaluate_county` only, pasted above.

## Concrete next-session leads

1. **Bradford E/I**: build a Playwright script against `bradfordappraiser.com/GIS/`
   (owner-name search) for the 4 known defendant names — chromium + playwright are
   confirmed available in this sandbox now, contrary to earlier assumptions.
2. **citrus/pinellas C/D, pinellas B**: need a new independent-outcome source
   (RealForeclose free-registered session credentials, or a clerk-portal integration)
   — not a SQL/matcher fix. Do not re-attempt without new data; two prior fabrication
   reverts already exist for this class of "fix" on these counties.
3. **okeechobee C/D remainder**: genuinely blocked on Civitek OCRS Cloudflare Turnstile
   — do not attempt to bypass; would need a different, non-bot-check data source for
   the 10 remaining civil foreclosure cases.
