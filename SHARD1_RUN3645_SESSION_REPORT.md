# GOLD STANDARD SHARD-1 — run3645 Session Report

dispatch_id: `ab574ee2-d287-4021-b89c-2c750cc7d6be`
chat_session: `architect-20260710T160000`
Shard counties: brevard, gadsden, orange, hamilton, jefferson
Mode: ULTRALOOP fallback (manual fan-out via the `Workflow` tool — 4 investigate/fix agents
+ adversarial refuters — not the native `/effort ultracode` CLI menu). Findings logged to
`gold_standard_ultraloop_audit` per protocol §1-4.

## Scope note (read first)

This session ran as a single bounded turn, not a literal 6-hour GHA job. Direct Postgres
access was **broken** for the entire session — `psql` to both the pooler
(`aws-0-us-west-2.pooler.supabase.com`, ports 6543/5432) and the direct host
(`db.mocerqjnksmhcjzxrewo.supabase.co:5432`) failed `password authentication failed` for
user `postgres`/`postgres.mocerqjnksmhcjzxrewo` using the current `SUPABASE_DB_PASSWORD`
secret, confirmed repeatedly. All work this session went through PostgREST
(`/rest/v1/<table>`) and existing RPCs only — no DDL, no ad-hoc SQL. **Flagging this secret
as likely stale — next session should verify/rotate it before assuming direct SQL access.**

Given that constraint, the session prioritized honest, verified small wins over fabricated
broad coverage, per this repo's own HONESTY PROTOCOL.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Verify brevard cert-readiness | Check only, no work expected (already 10/10) | Confirmed `gold_standard=true` live + fresh `survived=true` audit rows on all 10 letters within 7 days (H 5d old, J 7d old — both inside window) | None — cert-ready, did not run global `gold_standard_certify()` (parallel-fleet rule) |
| Fix jefferson (1-row county) | Investigate cascade fix across A/B/C/D/E/F/G/I/J | **Fully blocked, zero writes.** No real parcel_id sourceable (qPublic/jeffersonpa.net 403, FL GIO ArcGIS flaky on multi-clause queries); no real sale outcome sourceable (only doc available is a pre-sale notice, verified via `pdftotext`); zero zoning coverage exists for Jefferson (0 rows in `parcel_zones`/`zoning_assignments`) | Correctly reported UNKNOWN/blocked rather than guessing |
| Fix gadsden E/I | Investigate 6 missing parcel_ids + card-complete gap | **Blocked on E** (qpublic.schneidercorp.com + gadsdenpa.com 403; gadsdenclerk.com ASP.NET WebForms needs browser automation not available; FL GIO ArcGIS broad filters time out/error). **Root-caused I**: gadsden's zoning-card match is silently scoped to `sale_type='tax_deed'` only — the 16 foreclosure rows never get a card match regardless of parcel_id, a pipeline gap outside `multi_county_auctions` and outside this session's write permissions | Diagnosis-only, no write, no fabrication |
| Fix hamilton B/C/D/E/F/I | Investigate 16-row county | **Root-caused all 6, zero writes.** E: 5 rows need real parcel_id, blocked by same 403s. B/F: genuinely zero completed cash sales exist yet (7 redeemed pre-sale, 9 future/rescheduled) — structurally not-yet-measurable, confirmed via live clerk site. C/D: our own tier1 scraper already ran and correctly did not mark future/unresolved auctions as matched — forcing it would fabricate status. I: needs full address/geo/value enrichment blocked by the same access issue as E | Diagnosis-only, correctly declined to force any status |
| Diagnose + fix orange B/C/D | Diagnosis-first, fix only if small/mechanical | **Shipped a verified fix**: found 19 rows where a tier1 sold-amount refresh (2026-07-04) updated `sold_amount`/`tier1_sale_status` without re-running the parity finalization step, leaving a clean-match signature (`parity_confidence=0.98`, `parity_divergences=null`, `sold_amount==tier1_sold_amount`) unmarked. Patched those 19 rows' `parity_status`/`parity_source` only, after individually re-verifying each. C/D: 178→197 of 855 (20.8%→23.0%). Also found (but correctly left untouched, out of scope) 3,072 `propertyonion`-sourced rows mislabeled `county='orange'` that are actually Polk County — does not affect scoring since the evaluator's own denominator already excludes propertyonion rows | Fix was smaller than the full 612-row gap; remaining 638-row gap is structural (cancelled/upcoming/redeemed auctions with no completed sale to verify, or genuine PropertyOnion divergences) and correctly scoped to next session |
| Run `gold_standard_loop()`/`certify()` | Only if no other shard mid-flight | Skipped — per PARALLEL-FLEET RULES, per-county eval only | As directed |
| Adversarial verify | Refute any claimed letter-move | Orange's C/D claim independently re-verified live (RPC diff + row-level signature check + aggregate non-leakage check) — **survived=true**, logged to `gold_standard_ultraloop_audit` (ids 4635, 4636) | None |

## Before/After — live `pencil_dod_evaluate_county()`

### brevard: 10/10 (unchanged, verified cert-ready)
No work attempted — already `gold_standard=true` with fresh audit evidence on all 10 letters.

### orange: 7/10 → **7/10** (C/D moved, neither crossed PASS threshold)
```
BEFORE: {"A":true(321),"B":false(86.0),"C":false(20.8),"D":false(20.8),"E":true(99.1),"F":true(100.0),"G":true(100.0),"H":true(1.0),"I":false(93.1),"J":true(100.0)}
AFTER:  {"A":true(321),"B":false(86.0),"C":false(23.0),"D":false(23.0),"E":true(99.1),"F":true(100.0),"G":true(100.0),"H":true(1.1),"I":false(93.1),"J":true(100.0)}
```
Note: live `auctions_total` is now 855 (was 832 in the dispatch snapshot 3h earlier) and A's
`td` count rose 298→321 — routine background scraper ingestion between snapshot and session,
not a session artifact.

### gadsden: 8/10 (unchanged)
```
{"A":true(7),"B":true(100.0),"C":true(100.0),"D":true(100.0),"E":false(73.9),"F":true(100.0),"G":true(100.0),"H":true(14.7),"I":false(30.4),"J":true(100.0)}
```

### hamilton: 4/10 (unchanged)
```
{"A":true(6),"B":false(null),"C":false(43.8),"D":false(43.8),"E":false(68.8),"F":false(null),"G":true(100.0),"H":true(4.9),"I":false(6.3),"J":true(100.0)}
```

### jefferson: 1/10 (unchanged)
```
{"A":false(0),"B":false(null),"C":false(0.0),"D":false(0.0),"E":false(0.0),"F":false(null),"G":false(null),"H":true(5.9),"I":false(0.0),"J":false(0.0)}
```

## Environment finding for next session

`SUPABASE_DB_PASSWORD` does not authenticate against either the pooler or the direct
Postgres host this session (verified, repeated failures). This blocks any DDL/raw-SQL work
(zoning backfills, new tables, new RPCs) until rotated. PostgREST + existing RPCs remain
fully functional and were sufficient for this session's row-level fixes.

## Common blocker across gadsden/hamilton/jefferson E-letter work

`qpublic.schneidercorp.com` and county-specific PA sites (`gadsdenpa.com`,
`jeffersonpa.net`) return HTTP 403 to both `curl` and `WebFetch` (Cloudflare/WAF). The FL
GIO Statewide Cadastral ArcGIS FeatureServer works for exact `PARCEL_ID=` lookups (~2s) but
times out or errors on any broader filter (owner name, city, CO_NO alone) needed to resolve
legal-description-only or name-only records. Closing E for small counties likely needs
either a browser-automation path (headless browser, not available this session) through the
qPublic sites, or a working broad-filter query pattern against the statewide FeatureServer.
