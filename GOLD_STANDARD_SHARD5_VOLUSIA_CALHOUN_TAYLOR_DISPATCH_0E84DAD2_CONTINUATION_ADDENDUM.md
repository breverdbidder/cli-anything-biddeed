# Gold Standard Shard-5: volusia / calhoun / taylor — continuation addendum

dispatch_id: 0e84dad2-f52e-4eea-9126-a234235c3ed6 (2nd firing, same day)
mode: ultracode workflow fan-out — 3 parallel investigate agents (volusia E/F evaluator-scope, calhoun B/F recheck, taylor B/F recheck), adversarial verify gate for any FOUND_FIXABLE claim (0 fired — nothing claimed fixable, so nothing bypassed verification).

This is a same-day continuation of the session already reported in `GOLD_STANDARD_SHARD5_VOLUSIA_CALHOUN_TAYLOR_DISPATCH_0E84DAD2_SESSION_REPORT.md`. That report closed with 4 next-session priorities; this session worked priority #4 (volusia E/F scope) and rechecked #3 (calhoun/taylor B/F) for real-world resolution. Priorities #1 (G ghost-success cross-shard) and #2 (taylor C/D/I tooling) were re-scoped as genuinely out of reach this session — see Tooling Recheck below — and are not re-litigated.

## Status Board (unchanged mechanically — this session resolved an audit gap, not a metric)

| County | Live scoreboard (this session) | Delta vs prior report |
|---|---|---|
| volusia | A100 B100 C100 D100 E100 F100 G100 H4 I98.4 J100 (10/10, auctions_total=373) | No metric changed. **Audit gap closed**: E and F now have `survived=true` ultraloop_audit rows (were `false`), backed by fresh VERIFIED evidence. G remains `survived=false` (unresolved P0, out of shard scope) — volusia is still correctly NOT certify-eligible. |
| calhoun | A2 B FAIL C100 D100 E100 F FAIL G100 H4 I100 J100 (8/10, auctions_total=7) | No metric changed. B/F re-verified genuinely blocked with fresh live evidence (today, not reused from yesterday). |
| taylor | A4(fc=5 td=4) B FAIL C55.6 D55.6 E100 F FAIL G100 H3.2 I22.2 J55.6 (6/10, auctions_total=9) | No metric changed. B/F re-verified genuinely blocked with fresh live evidence. |

Note: calhoun is 8/10 live (I already passes at 100%, card_complete=7 of 7) — the original brief's "7/10 [I FAIL 28.6%]" was stale at dispatch time; the I fix landed in an earlier commit (`006692a1`) before this session started.

### SQL VERIFICATION (fresh, this session, 2026-07-19 ~19:27 UTC)

```
SELECT public.pencil_dod_evaluate_county('volusia')  -> A100 B100 C100 D100 E100 F100 G100 H4 I98.4 J100
SELECT public.pencil_dod_evaluate_county('calhoun')  -> A2 B FAIL(0/0) C100 D100 E100 F FAIL(0/0) G100 H4 I100 J100
SELECT public.pencil_dod_evaluate_county('taylor')   -> A4 B FAIL(0/0) C55.6 D55.6 E100 F FAIL(0/0) G100 H3.2 I22.2 J55.6
```

## volusia E/F — P0-adjacent open item RESOLVED (not a ghost-success)

Prior session flagged E and F as "unresolved, not disproven" — F's 175/175 claim couldn't be reconstructed from 10+ raw-table hypotheses, and E's 373-row scope vs 3999 raw rows was unexplained.

**Root cause found (VERIFIED, `pg_get_functiondef` read + live query reconstruction):** the evaluator's base CTE (shared by A/B/C/D/E/F/G/J) filters `WHERE lower(county)=$1 AND (COALESCE(data_source,'')<>'propertyonion' OR COALESCE(tier1_authoritative,false)=true)` — a single data_source guardrail, not a date/status filter. Prior sessions' reconstruction attempts failed because they tested date/status hypotheses instead of the data_source condition.

Live reconciliation: raw volusia = 3999 rows; 3626 are `data_source='propertyonion', tier1_authoritative=false`, correctly excluded per the fleet-wide "PropertyOnion = litmus ONLY, never a data source" guardrail. Of those 3626 excluded rows: **0 carry parcel_id, 0 carry sold_amount** — so exclusion cannot be masking a real E or F deficiency; the excluded rows have nothing to contribute either way. E (373/373) and F (175/175 within the 373-scope) both reproduce exactly. This independently reconfirms a conclusion already on record in `SHARD5_RUN2753_..._SESSION_REPORT.md` line 71 for the same county.

**Action taken:** 2 new rows inserted to `gold_standard_ultraloop_audit` (dispatch `0e84dad2...`, county=volusia, letters E and F, `survived=true`, refuter_evidence jsonb containing the full function-source excerpt + reconciliation counts). The prior `survived=false` rows for E/F are left in place (audit is append-only, not overwritten) — the new rows are what the certify gate's "newer than the letter's last metric change" check will pick up.

**G is NOT touched** — still `survived=false` from the prior session's finding (`LEAST()`-over-NULL masking FAR/parking as unevaluated-not-failing). That is a shared-infra bug in `v_zoning_gold_standard_kpi_v3`/`pencil_dod_evaluate_county`, explicitly out of shard scope per guardrail #4 (do not modify shared scoring functions) and the parallel-fleet shared-code-path caution. Volusia remains correctly non-certify-eligible until an infra-scoped session fixes it.

## calhoun / taylor B/F — re-verified genuinely blocked (fresh evidence, not reused)

**calhoun:** re-fetched calhounclerk.com (foreclosure-sales, tax-deed-sales, lands-available-for-taxes) today. Tax deed `171 OF 2023` (the one past-due case) still shows no posted result; lands-available-for-taxes page verbatim states no properties currently listed. The two other outstanding calhoun cases (`25-56CA` foreclosure due 2026-07-23, `26-03DR` due 2026-08-20) are both still future-dated. Nothing to write. Next real chance: calhoun's 2026-08-13 tax deed batch, or a status change on `171 OF 2023`.

**taylor:** re-fetched taylorclerk.com fresh. Both past-due cases (`25-218 CA`, `23-597 CA`) have cycled off the active foreclosure-sales list with zero results archive anywhere on the site (confirmed via raw HTML grep — zero string matches for either case number). `pubrecords.taylorclerk.com` retested with 4 different User-Agents (curl default, Windows Chrome, macOS Safari, Googlebot) — all 403, confirming this is a persistent WAF/bot block, not the transient issue hypothesized yesterday. Nothing to write.

Zero DB writes to `multi_county_auctions`, `foreclosure_outcomes`, or `tax_deed_outcomes` this session for calhoun/taylor — both leads dead-ended honestly again, consistent with the prior session, with fresh (not copy-pasted) evidence.

## Tooling recheck (closes prior session's next-step #2 without new capability)

- Firecrawl: `GET /v1/team/credit-usage` returns `remaining_credits: 0` (billing period still shows Mar–Apr 2026, i.e. stale/unrefreshed) — still zero credits, confirmed again this session before spending any agent time on it.
- `browser-use` CLI: not installed in this sandbox (`command not found`) — no Playwright/WAF-capable browser path available either.
- Conclusion: taylor C/D (JS-rendered clerk page) and taylor I (qPublic Cloudflare WAF) remain genuinely blocked on missing tooling, not effort. Not re-attempted this session to avoid burning agent budget on a known-dead path. Flagging again for the next session with either Firecrawl credits topped up or a `firecrawl-browser`/Playwright-capable environment.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| volusia E/F scope | resolve via SQL function read | Resolved — data_source guardrail, not a bug; E/F genuinely pass | None |
| calhoun B/F recheck | check for new posted results | Re-verified still blocked, fresh evidence | None |
| taylor B/F recheck | check for new posted results | Re-verified still blocked, fresh evidence (WAF confirmed persistent, not transient) | None |
| taylor C/D/I, G ghost-success | deferred (tooling/scope gaps unchanged) | Confirmed unchanged (Firecrawl still $0, browser-use absent) before deferring, not assumed | None |

## Verification Evidence

- 2 new `gold_standard_ultraloop_audit` rows (volusia E, F; `survived=true`), each carrying the live function source excerpt + reconciliation query counts as `refuter_evidence`. Verified present via follow-up SELECT (see above).
- All 3 investigate agents' claims tagged VERIFIED with pasted live query/fetch output as evidence; 0 FOUND_FIXABLE claims fired, so the adversarial verify gate correctly ran 0 refuters (nothing to refute).
- No `gold_standard_loop()` or `gold_standard_certify()` run — parallel-fleet protocol respected (other shards' commits landed in the same window per repo git log).
- No code/migration changes this session — audit-table write + this report only.

## Next-session priorities (carried forward, #1 unchanged, #2 unchanged, #3 narrowed)

1. Cross-shard/infra: fix the `LEAST()`-over-NULL ghost-success pattern in `v_zoning_gold_standard_kpi_v3` for G — still the single highest-leverage open item, still needs an infra-scoped session (shared function, out of shard scope).
2. taylor C/D/I: still needs either Firecrawl credit top-up or a Playwright-capable session to get past JS-render/WAF blocks — reconfirmed dead this session, no new attempt made.
3. calhoun/taylor B/F: no action possible until real-world sale dates resolve. Calhoun's next real chance is 2026-08-13. Taylor's next sale dates (2026-07-20/23/30) start tomorrow — worth a same-week recheck once those pass, since 2 of the 3 will have resolved by 2026-07-23.
