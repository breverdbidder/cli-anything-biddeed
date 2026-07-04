# SHARD-7 Session Report — loop run 2820

dispatch_id: `bdeea7e8-f0ec-4bea-9406-1bd2885f1e5a`
chat_session: `architect-20260704T000000`
shard counties: madison, highlands, volusia, pasco, columbia
ultraloop_mode: **native** (Workflow tool — 5 parallel adversarial refuters, one per county claim, + a synthesis pass)

## Headline finding: madison's "10/10 certified" was a ghost success (CRITICAL)

Live state at session start matched the brief's madison row exactly: `pencil_dod_evaluate_county('madison')` returned **10/10**, all letters A-J passing, 9/9 auctions matched clean.

An adversarial refuter (spawned via Workflow, told to try to break the claim rather than confirm it) found all 9 underlying `multi_county_auctions` rows were synthetic `shard5_bootstrap` scaffold data. I independently re-queried the raw rows myself before acting — confirmed in full:

- 6 rows tagged `data_source='shard5_bootstrap'`; the other 3 have `data_source=NULL` with `-PAST-` case numbers from the same scaffold family
- `bcpao_enriched=false` on every row — none ever touched a real property-appraiser enrichment step
- Sequential fabricated addresses: `101 Pine St` / `202 Oak Ave` / `303 Elm St`; `7010/7020/7030 MADISON HWY`; `8010/8020/8030 CHERRY LAKE RD`
- Patterned identical `tier1_sold_amount`: exactly `$9,000` on all 3 FC-2026 rows, exactly `$4,800` on all 3 TD-2026 rows — real independent sales don't cluster like this
- **`parcel_id='MADISON-FC-0003'` resolves to two different case_numbers and two different addresses** (303 Elm St vs 7030 Madison Hwy) — a single real parcel cannot have two addresses; this alone proves fabrication
- The fabrication cascaded downstream into `foreclosure_outcomes`/`tax_deed_outcomes` (fake `data_source` labels `realforeclose:shard5-v1`, `realforeclose:shard5-loop472`) and `bid_decisions` (duplicate/inconsistent ARV entries per case_number, e.g. `MADISON-FC-2026-002` at both ARV 120000 and 94300)

Same fabrication class already caught and reverted twice in this campaign's history in the last 24h (pasco, commit `d92b5a33`; santa_rosa + hendry, commit `203b7fe0`). Per BLANK > WRONG, reverted madison to its honest state rather than leave a false 10/10 standing.

## What shipped

1. **madison ghost-success revert** — `supabase/migrations/20260704_shard7_madison_ghost_success_revert.sql` (documents the DML; executed live via PostgREST since direct psql pooler auth fails in this sandbox, same documented constraint as prior shard sessions):
   - `DELETE FROM bid_decisions WHERE county_slug='madison'` — 15 rows
   - `DELETE FROM foreclosure_outcomes WHERE county='madison'` — 7 rows
   - `DELETE FROM tax_deed_outcomes WHERE county='madison'` — 5 rows
   - `DELETE FROM multi_county_auctions WHERE county='madison'` — 9 rows
2. **1 row to `honesty_violations`** (domain=GOLD_STANDARD_CAMPAIGN, severity=CRITICAL, tag_used=VERIFIED, resolved=true).
3. **8 rows to `gold_standard_ultraloop_audit`** (madison letters A,B,C,D,E,F,I,J, `survived=false`) — G (zoning) and H (freshness) are independent of the synthetic data and were left untouched/unlogged.
4. **Corrected columbia's platform diagnosis** (see below) — no DB write, a documentation-only correction to a prior migration's finding.

No other writes were made. Highlands, volusia, and pasco's real gaps could not be closed this session (see below) — I did not fabricate data to make them look closed.

## Result summary

| County | Before (this session) | After | Change |
|---|---|---|---|
| **madison** | 10/10 (**fabricated** — see above) | **1/10, honest** (only G, zoning, vacuously passes) | Ghost-success revert. Real ingestion for madison is unstarted. |
| highlands | 8/10 (C,D fail at 36.8%) | 8/10, unchanged | Root cause **confirmed** by adversarial refuter: canonical matcher (`refresh_parity_tier1_outcomes`) already fully exploited (re-run twice live, zero new matches). `tax_deed_outcomes` has only 3 rows total for highlands, `foreclosure_outcomes` has 0. 141/144 auctions are genuinely future-dated (`auction_date >= 2026-07-04`) — nothing exists yet to scrape. The 91 unmatched rows are not a matching-key bug; real blocker is `highlands.realtaxdeed.com`/`realforeclose.com` returning **HTTP 403 to plain HTTP** (anti-bot WAF, not a login wall — no RealAuction credentials exist in this environment regardless). No SQL-only fix available. |
| volusia | 8/10 (C,D fail at 71.0%/71.8%) | 8/10, unchanged | Root cause **confirmed**: matcher maxed (265/268 of 373, re-run twice, zero new matches). Independently counted the structural gap at **21 rows** (`auction_status='concluded'`, `data_source != propertyonion`, zero `sold_amount`/`tier1_sold_amount`) — mostly `data_source='realforeclose'`. No RealAuction credentials in env or wired into the volusia GHA workflow. Needs live scraping, not SQL reconciliation. |
| pasco | 6/10 (B,C,D,F fail) | 6/10, unchanged, **diagnosis corrected worse than brief** | `foreclosure_outcomes`/`tax_deed_outcomes` have **0 rows** for pasco right now, not the ~3 the brief implied survived the same-day fabrication revert (commit `d92b5a33`) — the genuine 3-row fix from an earlier audit entry appears to have been overwritten by the later fabrication attempt and never restored on revert. No new fabrication found. Needs live RealAuction/realtaxdeed scraping; no credentials in this environment. |
| columbia | 1/10 (only G) | 1/10, unchanged, **misdiagnosis corrected** | `co_no=12` (not 22 — co_no=22 is Glades, confirmed live against `fl_counties`; a stale reference in `fl_counties_manifest.yml` was wrong). Real platform is `columbiaclerk.com` (in-person courthouse sales) — a prior migration's "Cloudflare 403" finding used plain `curl` (no JS); a real headless-browser fetch (confirmed twice, independently) gets **HTTP 200** with real page content (`/clerk-services/tax-deeds/`, `/clerk-services/foreclosures/`, `/clerk-services/property-sales/` all resolve). `columbia.realforeclose.com`/`realtaxdeed.com` both redirect to RealAuction's generic non-county marketing page — columbia is **not** on that platform, confirming `scripts/shard7_columbia_bootstrap.py`'s premise was wrong (that script is correctly quarantined with a `sys.exit(1)` banner and must stay disabled). Building the real `columbiaclerk.com` scraper is unstarted work — not attempted this session, not claimed as done. |

## Why highlands/volusia/pasco/columbia were not closed this session

All four real gaps require live scraping capability not available in this sandboxed environment:
- No `REALAUCTION_*`/`REALFORECLOSE_*` credentials for highlands, volusia, or pasco (checked env vars and every GHA workflow that threads secrets for these counties)
- `highlands.realtaxdeed.com` / `highlands.realforeclose.com` return HTTP 403 to plain HTTP requests (WAF/anti-bot, confirmed live)
- Building and validating a production `columbiaclerk.com` scraper (real listing-page structure, pagination, case/parcel extraction) is unstarted, non-trivial work — attempting a rushed version risked reproducing exactly the `shard7_columbia_bootstrap.py` fabrication pattern that's already quarantined

Per HARD GUARDRAILS and the Fix-First / Honesty Protocol, I chose not to synthesize placeholder data to manufacture apparent progress on these four. The corrected diagnoses (columbia reachability, pasco's true post-revert state) are real deliverables even though no letter moved.

## Verification evidence (live, pasted verbatim)

### SQL VERIFICATION

```
SELECT public.pencil_dod_evaluate_county('madison');
SELECT public.pencil_dod_evaluate_county('highlands');
SELECT public.pencil_dod_evaluate_county('volusia');
SELECT public.pencil_dod_evaluate_county('pasco');
SELECT public.pencil_dod_evaluate_county('columbia');
```
Timestamp: 2026-07-04T00:1x-00:2xZ (via PostgREST RPC — direct psql pooler auth fails in this sandbox: `password authentication failed for user "postgres"` against the pooler, same documented constraint as every prior shard session).

**madison — before (fabricated):**
```json
{"A":{"pass":true,"metric":4,"detail":"fc=5 td=4"},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":16.0},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"county":"madison","auctions_total":9}
```
**madison — after (honest, post-revert):**
```json
{"A":{"pass":false,"metric":0,"detail":"fc=0 td=0"},"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},"C":{"pass":false,"metric":null,"detail":"matched_clean=0"},"D":{"pass":false,"metric":null,"detail":"matched_any=0"},"E":{"pass":false,"metric":null,"detail":"parcel_linked=0"},"F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},"G":{"pass":true,"metric":100.0},"H":{"pass":false,"metric":null},"I":{"pass":false,"metric":null,"detail":"card_complete=0 of 0"},"J":{"pass":false,"metric":null,"detail":"deal_complete=0"},"county":"madison","auctions_total":0}
```

**highlands (unchanged, re-confirmed live):**
```json
{"A":{"pass":true,"metric":2},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":36.8,"detail":"matched_clean=53"},"D":{"pass":false,"metric":36.8,"detail":"matched_any=53"},"E":{"pass":true,"metric":98.6},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":8.4},"I":{"pass":true,"metric":97.9},"J":{"pass":true,"metric":100.0},"county":"highlands","auctions_total":144}
```

**volusia (unchanged, re-confirmed live):**
```json
{"A":{"pass":true,"metric":94},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":71.0,"detail":"matched_clean=265"},"D":{"pass":false,"metric":71.8,"detail":"matched_any=268"},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":8.3},"I":{"pass":true,"metric":98.4},"J":{"pass":true,"metric":100.0},"county":"volusia","auctions_total":373}
```

**pasco (unchanged, re-confirmed live — worse than brief implied):**
```json
{"A":{"pass":true,"metric":91},"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},"C":{"pass":false,"metric":0.0},"D":{"pass":false,"metric":0.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":5.9},"I":{"pass":true,"metric":95.4},"J":{"pass":true,"metric":100.0},"county":"pasco","auctions_total":195}
```

**columbia (unchanged, re-confirmed live):**
```json
{"A":{"pass":false,"metric":0},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":null},"D":{"pass":false,"metric":null},"E":{"pass":false,"metric":null},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":false,"metric":null},"I":{"pass":false,"metric":null},"J":{"pass":false,"metric":null},"county":"columbia","auctions_total":0}
```

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Work highest-leverage failing letters for madison/highlands/volusia/pasco/columbia | Move C/D/B/F letters toward PASS | Found and reverted a fabricated 10/10 (madison); confirmed 3 real gaps genuinely require live-scraping infra not available here; corrected 2 stale diagnoses (columbia reachability, pasco's true post-revert state) | Net scoreboard movement is **negative** for madison (10→1) and flat for the other four — this is the honest outcome, not a shortfall against a fabricatable target |
| Ship to main | Yes | Yes — migration file + session report | none |
| Run full gold_standard_loop + certify at close-out | Only if no other session mid-flight | Skipped — used `pencil_dod_evaluate_county` per-county per PARALLEL-FLEET RULES (cannot confirm no other shard is mid-flight) | per instructions |

## Deviation log

The brief's playbook assumed C/D gaps for highlands/volusia were matching-key bugs fixable via reconciliation SQL. Live investigation (matcher re-run twice per county, zero new matches both times) shows this is wrong for all three counties in this shard — the actual blocker is missing outcome data behind an anti-bot wall with no credentials available in this sandbox. This does not change without either (a) RealAuction/realtaxdeed login credentials being provisioned to this environment, or (b) a Firecrawl-class headless-render service being wired in. Flagging for whoever owns credential provisioning rather than silently retrying the same SQL-only approach every session.

`scripts/shard13_letter_b_verified_outcomes.py` (out of my assigned counties — orange/flagler/santa_rosa/gulf) is still live in the repo and, if ever run, would fabricate `buyer_name='VERIFIED_BUYER_{case}'`, `plaintiff='PLAINTIFF_{county}_{case}'`, and `confidence_level='verified'` rows from existing MCA data without ever touching a real clerk source — the exact same anti-pattern reverted here for madison. Flagging for a future session that owns those counties; did not touch it (outside PARALLEL-FLEET RULES scope).
