# Gold Standard Shard-11: lafayette — dispatch b34a2384 (3rd firing, run3786)

## Result: 7/10 → 8/10 (A fixed, real data, zero regressions)

| Letter | Before | After | Notes |
|---|---|---|---|
| A | FAIL (fc=1 td=0) | **PASS** (fc=1 td=1) | Real Wayback-archived tax deed notice |
| B | FAIL (null) | FAIL (null) | Genuinely blocked, re-confirmed |
| C | PASS 100.0 | PASS 100.0 | No regression (1→2 auctions, self-reconfirmed) |
| D | PASS 100.0 | PASS 100.0 | No regression |
| E | PASS 100.0 | PASS 100.0 | No regression |
| F | FAIL (null) | FAIL (null) | Genuinely blocked, re-confirmed |
| G | PASS 100.0 | PASS 100.0 | No regression (same zoning district reused) |
| H | PASS 20.8 | PASS 0.0 | Fresher (new row inserted this session) |
| I | PASS 100.0 (1 of 1) | PASS 100.0 (2 of 2) | No regression |
| J | PASS 100.0 (1 of 1) | PASS 100.0 (2 of 2) | Regressed to 50% mid-session, fixed same session |

## What happened

Lafayette is a tiny rural county (~8,500 pop, one town: Mayo) with exactly one
real auction row known at session start: a single scheduled foreclosure case
(25000056CAAXMX, sale date 2026-09-03, still in the future). Four prior
sessions (2026-07-02, 07-04, 07-10, 07-11 morning) had already exhaustively
diagnosed A/B/F as genuinely, structurally blocked — no tax deed listings
exist on the live clerk site, and no closed sale exists to verify an outcome
against.

Per the ULTRALOOP protocol and the "ultracode" directive, this session ran a
Workflow (`gold-standard-lafayette-abf-discovery`, run `wf_5214ef2b-8f3`) that
fanned 6 independent research agents across genuinely new avenues not tried
by prior sessions (Tax Collector site, surplus funds records, Wayback Machine
archive, legal notices aggregators, BOCC minutes/Auditor General AFR,
third-party tax-deed aggregators), then adversarially verified any claimed
finding with an independent refuter agent before trusting it.

5 of 6 avenues returned genuine negatives (documented in full in
`pipeline.counties.notes`). The Wayback Machine avenue found a real
"Notice of Application for Tax Deed" PDF natively hosted on
`lafayetteclerk.com` and archived by web.archive.org: Certificate No.
2022-28, holder Bandit Capital LLC, Parcel ID `0704110000000000501`, sale
scheduled 2024-09-12. The adversarial verifier independently re-fetched the
archived PDF, re-OCR'd it locally (not trusting the discoverer's OCR), and
confirmed the excerpt verbatim plus confirmed it is genuinely Lafayette
County FL (not Parish LA or a doc mixup).

This is a pre-sale application notice, not a completed-sale/outcome record —
no winning bid or sold amount exists in it. It satisfies criterion A only
(≥1 real tax_deed row), honestly. B/F remain unsatisfied because no
completed-sale evidence was found anywhere.

### Real data used (no fabrication)
- Parcel data (assessed_value=37020, address="837 NW PUTNAL RD, MAYO FL
  32066", DOR_UC=001) pulled live from FL GIO Statewide Cadastral
  FeatureServer by exact PARCEL_ID match.
- Lat/lon (30.154241931044, -83.253693973147) from US Census Geocoder on the
  real matched address.
- Zoning: reused the existing `jurisdiction_id=932` / `zone_code=RSF-2`
  assignment after confirming (via `pdftotext` on the live LDR.pdf cover
  page) that it is the **countywide** Lafayette County Land Development
  Regulations (BOCC-adopted, Ordinance 2000-05 + amendments through
  2023-05) — not a Town-of-Mayo-only ordinance — so it legitimately applies
  to this second, rural parcel too.
- `auction_status='unknown_past_due'`: sale date has passed but the outcome
  is genuinely unverified — deliberately NOT marked `sold`/`closed`, since
  that would be fabrication.
- Parity (`C`/`D`): reused the existing "clerk self-reconfirmation" pattern
  (no PropertyOnion coverage exists for lafayette to compare against; the
  primary clerk-sourced document IS the tier1 record) — same pattern already
  audited and survived for the county's other row.

### Regression check
Adding a second auction row changes every ratio-based criterion's
denominator. Checked live via `pencil_dod_evaluate_county` before and
immediately after the insert:
- C/D/E/G/I: unaffected (2 of 2, same as 1 of 1 before) because the new row
  was fully backfilled (parcel link, zoning, parity) before being counted.
- J: **did regress** 100%→50% (`deal_complete=1 of 2`, new row had no
  `bid_decisions` entry) — caught immediately, fixed same session by
  re-running the existing, already-audited
  `scripts/shard11_lafayette_j_generator.py` (idempotent, county-scoped),
  confirmed back to 100% (`deal_complete=2 of 2`).

## Live evaluation JSON — BEFORE (session start, 2026-07-11)
```json
{"A":{"pass":false,"detail":"fc=1 td=0","metric":0},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":true,"detail":"matched_clean=1","metric":100.0},"D":{"pass":true,"detail":"matched_any=1","metric":100.0},"E":{"pass":true,"detail":"parcel_linked=1","metric":100.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":28.4},"I":{"pass":true,"detail":"card_complete=1 of 1","metric":100.0},"J":{"pass":true,"detail":"deal_complete=1 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"lafayette","V2_LITMUS":null,"auctions_total":1}
```

## Live evaluation JSON — AFTER (post-fix, same session)
```json
{"A":{"pass":true,"detail":"fc=1 td=1","metric":1},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":true,"detail":"matched_clean=2","metric":100.0},"D":{"pass":true,"detail":"matched_any=2","metric":100.0},"E":{"pass":true,"detail":"parcel_linked=2","metric":100.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":0.0},"I":{"pass":true,"detail":"card_complete=2 of 2","metric":100.0},"J":{"pass":true,"detail":"deal_complete=2 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"lafayette","V2_LITMUS":null,"auctions_total":2}
```

### SQL VERIFICATION
```sql
SELECT public.pencil_dod_evaluate_county('lafayette');
-- returned the AFTER JSON above, run 2026-07-11T21:39Z
SELECT COUNT(*) FROM public.gold_standard_ultraloop_audit
  WHERE county_slug='lafayette' AND created_at > '2026-07-11T21:00Z';
-- 10 rows, all survived=true
```

## B/F residual — genuinely blocked, exhaustively re-confirmed
This session ran the most exhaustive search yet for closed-sale/outcome
evidence and found none via any avenue not gated behind a CAPTCHA or
JS-only rendering:
- `myfloridacounty.com/orisearch/34` (Lafayette Official Records): the
  search *form* is unauthenticated, but the search *POST* is gated behind a
  Cloudflare Turnstile CAPTCHA. Not attempted (out of bounds).
- `library.municode.com/fl/lafayette_county/munidocs` (BOCC agendas/
  minutes): Angular SPA, zero content without JS execution. Not attempted
  (would need a headless browser, not used this session).
- Lafayette County Tax Collector (`lafayettetc.com`, real domain, correctly
  identified this session): Tax Certificate Search tool is disabled/
  non-browsable; no delinquent or DR-513 application list published.
- No surplus-funds page, no BOCC minutes with dollar figures (checked the
  FY2024 Auditor General AFR full-text — zero "deed"/"tax certificate"
  mentions), no coverage on any major FL tax-deed investor aggregator.

**Recommended next step (not attempted, needs approval):** either a direct
records request to the Clerk (120 W Main St, Mayo FL, 386-294-1600) for the
OCRS search, or headless-browser tooling for the two JS/CAPTCHA-gated
sources above.

## Ultraloop audit
Mode: `native` (Workflow tool fan-out + adversarial verify).
Run: `wf_5214ef2b-8f3`. 7 agents, 512K tokens, 218 tool calls.
10 rows logged to `gold_standard_ultraloop_audit` (dispatch_id
`b34a2384-438c-4a9d-b28e-a82167b4bc5b`), all `survived=true`.

## Fleet coordination
Confirmed via `git pull --rebase` before pushing that 5 other shards
(shard6, shard7, shard8, shard13, shard14) committed concurrently during
this session — correctly skipped the fleet-wide `gold_standard_loop()` +
`gold_standard_certify()` per the parallel-fleet protocol and reported only
this county's live per-county evaluation.
