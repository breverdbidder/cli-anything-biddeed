# Gold Standard Shard-12: DeSoto — Session Report (dispatch b649601a-bb02-4b45-8ff0-bacea8281794)

**Session:** 2026-07-31, chat_session architect-20260731T000000
**Assigned scope:** desoto only (8/10 — B and F failing, both `metric=null closed_sold=0`)
**Method:** ULTRALOOP — Workflow tool fan-out, one browser-driven research agent per past-due case, adversarial-verify gate for any finding

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Discover B/F outcome for 25CA632, 25CA638, 26-04-TD, 26-06-TD | Find ≥1 independently-verified sale amount via civitek OCRS + DeSoto PA | 0 found, 0 survived verify | Fully blocked — documented, not worked around |
| Write outcomes + promote to multi_county_auctions | Conditional on discovery | Not executed — no data to write | N/A (correctly skipped, no fabrication) |
| Regression check 8 passing letters | Re-run pencil_dod_evaluate_county | Ran before + after, identical | None |

## What happened

DeSoto has 8 auctions total; 4 have auction dates now in the past (25CA632, 25CA638: 2026-07-02 foreclosure; 26-04-TD: 2026-07-22, 26-06-TD: 2026-07-29 tax deed) but none carry a `sold_amount`, so `closed_sold=0` and B/F are structurally unmeasurable (not merely low — `metric=null`). This is the 4th session to work this exact blocker (2026-07-10, 07-19, 07-20, 07-31); all four have independently reached the same conclusion.

This session re-verified live (all 3 prior leads re-checked, all still negative) and added one genuinely new lead — Civitek's Online Court Records Search (civitekflorida.com/ocrs/county/14/), which none of the prior 3 sessions' notes mention. Fanned 4 subagents (one per case) via the Workflow tool, each independently trying OCRS + DeSoto Property Appraiser + any other no-login public source.

**Result: 0 of 4 found a verified outcome.** Adversarial-verify never ran because no agent claimed `found=true` to verify.

### New structural findings (persisted to `pipeline.counties.notes` and `gold_standard_ultraloop_audit`)

1. **Civitek OCRS has no tax-deed case type.** Its Case Search court-type list is fixed to 14 values (CA/CC/CF/CT/DR/GA/MM/MO/IN/CP/SC/TR/AP) — no "TD". It structurally cannot ever resolve `26-04-TD`/`26-06-TD`; it could only theoretically apply to the two foreclosure cases (`25CA632`/`25CA638`, which are CA-type).
2. **OCRS's Turnstile gate is on search submission, not the Public-access flow.** A live Playwright session reached `search.xhtml` cleanly (past the "Public" tier picker and disclaimer), then hit `cf-turnstile-response` on the actual case-number search. Same class of block as `myfloridacounty.com`, confirmed independently.
3. **DeSoto PA GIS (GrizzlyLogic) Sales History is reachable and matches parcels correctly** (confirmed exact address/owner match for 3 of 4 target parcels) but shows no 2026 deed recorded yet — the page's own "last updated" stamp for the 26-06-TD parcel is 2026-07-23, 6 days before that sale and still current as of 2026-07-31. Read as normal county recording lag, not a tooling failure.
4. **New independent source found: DeSoto County Tax Collector (VisualGov), reached via a cross-link from the Property Appraiser.** Confirms a tax-deed-application flag on the 2025 tax roll for the 26-06-TD parcel but discloses no dollar amount.
5. **`desoto.realtaxdeed.com` now returns HTTP 403** (prior sessions found it redirecting to a RealAuction marketing splash — still not a usable data source either way).

### Infra note (not desoto-specific, flagged for fleet visibility)

This session's sandbox had no `browser-use` CLI installed and `FIRECRAWL_API_KEY` returned HTTP 402 (insufficient credits). Agents fell back to raw `curl`/Playwright reverse-engineering of the target JS apps and got materially further than a pure-curl attempt (reached the live OCRS search form, confirmed the Turnstile gate's exact scope) — but this is worth fixing fleet-wide since B/F discovery across many stuck counties depends on the same tooling.

## Verification evidence

`pencil_dod_evaluate_county('desoto')`, run before and after this session — identical, confirming zero regression:

```json
{
  "A": {"pass": true,  "metric": 2,     "detail": "fc=6 td=2"},
  "B": {"pass": false, "metric": null,  "detail": "verified=0 closed_sold=0"},
  "C": {"pass": true,  "metric": 100.0, "detail": "matched_clean=8"},
  "D": {"pass": true,  "metric": 100.0, "detail": "matched_any=8"},
  "E": {"pass": true,  "metric": 100.0, "detail": "parcel_linked=8"},
  "F": {"pass": false, "metric": null,  "detail": "tier1_sold=0 closed_sold=0"},
  "G": {"pass": true,  "metric": 100.0, "detail": "density=100.0 far= pk1000="},
  "H": {"pass": true,  "metric": 0.9,   "detail": "hours since last_seen (SLA 48h)"},
  "I": {"pass": true,  "metric": 100.0, "detail": "card_complete=8 of 8"},
  "J": {"pass": true,  "metric": 100.0, "detail": "deal_complete=8 (triangle + two-arm CMA + ml_score + max_bid)"},
  "auctions_total": 8
}
```

### SQL VERIFICATION

```sql
SELECT id, dispatch_id, letter, survived, created_at
FROM gold_standard_ultraloop_audit
WHERE dispatch_id = 'b649601a-bb02-4b45-8ff0-bacea8281794';
-- id=11342 letter=B survived=false created_at=2026-07-31 00:38:22+00
-- id=11343 letter=F survived=false created_at=2026-07-31 00:38:22+00
```

Timestamp: 2026-07-31T00:38Z (UTC), run against `mocerqjnksmhcjzxrewo` via Management API.

## Honesty Protocol tags

- desoto B/F genuinely blocked: **VERIFIED** (4 independent sessions, live-reconfirmed this session, evidence pasted above).
- OCRS has no TD case type: **VERIFIED** (observed directly in the live PrimeFaces dropdown DOM).
- DeSoto PA shows no 2026 deed yet: **VERIFIED** (Sales History table + page timestamp, live).
- Recording lag is the likely resolver: **INFERRED** (normal county recording behavior, not confirmed for this specific case).

## Next-session priorities (desoto)

1. Re-check DeSoto PA Sales History for the 4 target parcels in ~2-3 weeks — deed recording lag is the most likely path to resolution.
2. Re-check DeSoto Clerk's Excess Funds List after its next monthly refresh (just advanced 6.30→7.30 dated, but still only covers sales through 2026-06-17 — needs to pass 2026-07-22 and 2026-07-29 to cover our 2 tax-deed cases).
3. If `browser-use` CLI or funded Firecrawl credits become available fleet-wide, re-attempt OCRS case search past the Turnstile gate for the 2 foreclosure cases specifically (tax-deed cases are permanently out of scope for OCRS per finding #1 above).
4. Do not re-attempt `myfloridacounty.com/orisearch/14` or a 5th blind pass at the same 2 lists — those are exhausted; only new information (recording lag resolving, or list refresh) will move this.

## Guardrail compliance

- No PropertyOnion data ingested or used as a source.
- No CAPTCHA/Turnstile bypass attempted.
- No fabricated/estimated sold_amount written.
- No regression on the 8 currently-passing letters (verified above).
- No cross-shard county touched.
