# Gold Standard shard-12: suwannee — dispatch 6fe5726b, ultracode session

## Result: 8/10, no change (correctly)

| Letter | Before | After | Notes |
|---|---|---|---|
| A | PASS (fc=4 td=10) | PASS (fc=4 td=10) | No regression |
| B | FAIL (null) | FAIL (null) | Genuinely blocked, re-confirmed via 2 fresh avenues + adversarial verify |
| C | PASS 100.0 | PASS 100.0 | No regression |
| D | PASS 100.0 | PASS 100.0 | No regression |
| E | PASS 100.0 | PASS 100.0 | No regression |
| F | FAIL (null) | FAIL (null) | Genuinely blocked, re-confirmed (direct consequence of B) |
| G | PASS 100.0 | PASS 100.0 | No regression |
| H | PASS 0.1 | PASS (live) | No regression, freshness auto-refreshes |
| I | PASS 100.0 (14/14) | PASS 100.0 (14/14) | No regression |
| J | PASS 100.0 (14/14) | PASS 100.0 (14/14) | No regression |

## What happened

Direct psql access (both `aws-0-us-west-2.pooler.supabase.com` per CLAUDE.md and `db.*.supabase.co`) failed
password authentication in this session's sandbox (env `SUPABASE_DB_PASSWORD` did not authenticate against
either host/port combination tried, including the historically-correct `us-east-1` pooler region — the
region documented in this repo's own scripts is `us-east-1`, not `us-west-2`). All DB reads and writes this
session used the PostgREST REST API with the service-role key instead, which worked correctly throughout
(`multi_county_auctions`, `pencil_dod_evaluate_county` RPC, `gold_standard_ultraloop_audit` insert all
confirmed 200/201). No DDL/migration was needed this session (no verified new data to write), so this had
no impact on scope.

### B/F: fresh ultracode Workflow, 2 genuinely new avenues, 1 partially-contradicted claim, still blocked

Prior sessions (dispatch `ae041d7c`, 2026-07-19, twice; and three more sessions on 2026-07-24 per
`gold_standard_ultraloop_audit` ids 8735/8849/9579-81) already established suwannee's B/F block is
structural: 14 auctions total, all `auction_status='upcoming'` except one pre-existing `redeemed` case
(4713, not in this session's target set), and only 3 cases are past their auction date — 4666/4667 (tax
deed, 2026-07-09) and 25-CA-197 (foreclosure, 2026-07-23). Yesterday's 3rd firing (`15bb3eb1`) already swept
`myfloridacounty.com/orisearch/61`, the `suwgov.org` clerk site directly, and local-news legal-notice
search — all negative.

This session ran one Workflow (`gold-standard-suwannee-bf-fresh-avenues`, run `wf_893256f4-545`, 8 agents:
4 discover + 4 verify, ~543K tokens, 212 tool calls, ~11 min) targeting genuinely new ground plus one
re-test of `orisearch/61` at finer granularity (exact Turnstile sitekey/field enumeration, not previously
recorded):

1. **`myfloridacounty.com/orisearch/61` (Suwannee official records, Civitek/Cloudflare platform)** — the
   search form itself loads cleanly (Party Name, Instrument Type incl. explicit "TAX DEED"/"Certificate of
   Tax Deed" values, date range) but every search submission returns a Cloudflare Turnstile interstitial
   (sitekey `0x4AAAAAAA64PTBePmuGbrkR`). Confirmed dead end, reproduced independently by the refuter via a
   fresh session.
2. **Property Appraiser GIS sales history (genuinely new avenue)** — discovered the real platform is
   GrizzlyGIS at `www.suwanneepa.com/GIS/` (not the Beacon/Schneider instance referenced elsewhere on the
   site, which 403s both to curl and WebFetch — Cloudflare-blocked). Reverse-engineered the record-search
   POST flow and pulled the live Sales History table for all 3 target parcels (10591001000 / 4666,
   11016001003 / 4667, 04200620080 / 25-CA-197 "Dowdy"). None show a 2026 entry — most recent sales predate
   the auctions by years to decades. Confirmed dead end, independently reproduced verbatim by the refuter.
3. **`suwannee.realtaxdeed.com` / `suwannee.realforeclose.com` live status, real-browser rendering** — a
   Playwright-driven agent reported the rendered auction-preview page text for 4666/4667 as
   `Auction Status: Redeemed` (property owner paid off the certificate pre-sale — no auction occurred), and
   found zero auction-linked calendar cell for 25-CA-197 on the foreclosure lane at all (direct navigation
   to the case's preview URL redirects to the site's own generic error page).
4. **Clerk sale-results/docket cross-check** — a second, independent agent hit the same platform's AJAX
   status endpoint (`FNC=UPDATE`) and got a payload that also read `"B":"Redeemed"` for both AIDs
   corresponding to 4666/4667, plus re-confirmed the `suwgov.org` foreclosure-list docx is byte-identical
   (HTTP `Last-Modified` unchanged) since 2026-07-20, still schedule-only for 25-CA-197.

**Adversarial verify caught a real inconsistency, not a rubber-stamp.** The refuter assigned to claim 4
independently re-hit the exact same AJAX URL (`...FNC=UPDATE&ref=1505795,1505796`) four times with varied
headers and got an **empty** `ADATA` array every time — it could not reproduce the "Redeemed" payload at
all. This is consistent with the endpoint being session-gated (the discover agent's Playwright session had
already navigated the calendar UI and established referer/cookie state that a bare fresh AJAX call lacks),
but it means the "Redeemed" finding rests on unreproduced evidence from one methodology (rendered DOM text)
and a contradicted claim from a second (AJAX API). **Per Honesty Protocol, this was NOT written to the
database as VERIFIED.** It also would not have moved B or F even if fully confirmed — "redeemed" means no
sale occurred, which correctly keeps those cases out of `closed_sold` either way (same as the pre-existing
case 4713). Flagging as a residual for a future session with cleaner session-consistent verification, not
urgent since it does not move the scoreboard.

Case 25-CA-197 (foreclosure) remains a complete blank on every avenue tried, old and new: no calendar
listing, no updated schedule doc, no reachable official-records search, and this session additionally
confirmed Suwannee foreclosure sales are conducted courthouse-steps (per the docx's own instructions) and
are simply not tracked on the electronic RealForeclose platform at all — a structural, not temporary, gap.

**Net verdict: no actionable new evidence that changes B or F.** No CAPTCHA was solved. No sold amount,
winning bidder, or completed-sale status was written to the database.

## Live evaluation JSON — BEFORE (session start, 2026-07-25T08:1x UTC, matches dispatch brief exactly)
```json
{"A":{"pass":true,"detail":"fc=4 td=10","metric":4},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":true,"detail":"matched_clean=14","metric":100.0},"D":{"pass":true,"detail":"matched_any=14","metric":100.0},"E":{"pass":true,"detail":"parcel_linked=14","metric":100.0},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"detail":"density=100.0 far=100.0 pk1000=","metric":100.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":0.1},"I":{"pass":true,"detail":"card_complete=14 of 14","metric":100.0},"J":{"pass":true,"detail":"deal_complete=14 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"suwannee","V2_LITMUS":null,"auctions_total":14}
```

## Live evaluation JSON — AFTER (post-research, same session, 2026-07-25T08:29 UTC)
```json
{"A": {"pass": true, "detail": "fc=4 td=10", "metric": 4}, "B": {"pass": false, "detail": "verified=0 closed_sold=0", "metric": null}, "C": {"pass": true, "detail": "matched_clean=14", "metric": 100.0}, "D": {"pass": true, "detail": "matched_any=14", "metric": 100.0}, "E": {"pass": true, "detail": "parcel_linked=14", "metric": 100.0}, "F": {"pass": false, "detail": "tier1_sold=0 closed_sold=0", "metric": null}, "G": {"pass": true, "detail": "density=100.0 far=100.0 pk1000=", "metric": 100.0}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.1}, "I": {"pass": true, "detail": "card_complete=14 of 14", "metric": 100.0}, "J": {"pass": true, "detail": "deal_complete=14 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100.0}, "county": "suwannee", "V2_LITMUS": null, "auctions_total": 14}
```

Identical to the decimal. No DB writes made this session — confirmed by matching BEFORE/AFTER snapshots.

### SQL VERIFICATION
```sql
SELECT public.pencil_dod_evaluate_county('suwannee');
-- returned the AFTER JSON above, run 2026-07-25T08:29Z via REST RPC (direct psql auth
-- unavailable in this sandbox this session -- see Environment note above)

SELECT id, letter, survived, created_at FROM public.gold_standard_ultraloop_audit
  WHERE dispatch_id='6fe5726b-f750-4aab-a552-f9ad57a2ef7c' ORDER BY id;
-- id=9894, B, true, 2026-07-25T08:29:44.941101Z
-- id=9895, F, true, 2026-07-25T08:29:44.941101Z
```

## Recommendation

This is now the **6th+ consecutive session** (across 07-19, 07-24 x3, 07-25) confirming the identical
structural block for B/F. Every avenue not gated by a Cloudflare Turnstile CAPTCHA or requiring
courthouse-in-person records has now been tried, including two genuinely new ones this session (Property
Appraiser GrizzlyGIS sales history, and a finer-grained pass on the official-records Turnstile wall).

**Recommend this dispatch be closed or superseded for suwannee B/F specifically**, same as the standing
recommendation for the structurally-identical lafayette case. A/C/D/E/G/H/I/J are stable and correctly
closed at 8/10. Re-firing this dispatch unchanged will reproduce this exact result and burn session budget
with zero yield. Suwannee needs one of: (a) the 2026-08-06 batch of 7 auctions to actually close and post
results, (b) CAPTCHA-solving tooling explicitly authorized for `myfloridacounty.com`, or (c) a manual
records request to the Clerk (386-362-0500/0575) — none of which are in scope for an automated pipeline
session.

**Residual (non-blocking, does not move the scoreboard):** if a future session has time to spare, resolve
the inconsistent "Redeemed" auction_status evidence for cases 4666/4667 with a single clean Playwright
session (navigate calendar → click day cell → read rendered DOM directly, avoiding the AJAX endpoint that
proved session-fragile) and, if confirmed, update the stale `auction_status='upcoming'` field to
`'redeemed'` for data hygiene. This has zero effect on any of the 10 canon letters (none reference
`auction_status`), so it is optional cleanup, not gold-standard work.

## Ultraloop audit

Mode: `native` (Workflow tool fan-out + adversarial verify). Run: `wf_893256f4-545`. 8 agents (4 discover +
4 verify), ~543K tokens, 212 tool calls, ~11 min. 2 rows logged to `gold_standard_ultraloop_audit`
(dispatch_id `6fe5726b-f750-4aab-a552-f9ad57a2ef7c`, ids 9894-9895, letters B and F, both `survived=true`).
The adversarial layer functioned as designed: it caught and rejected an unreproduced "Redeemed" status
claim rather than letting it ship as VERIFIED.

## Fleet coordination

`git pull --rebase` run before this commit (parallel-fleet protocol — 10 other shard migrations landed on
main during this session's research window, all unrelated to suwannee). Per protocol, skipped the
fleet-wide `gold_standard_loop()` / `gold_standard_certify()` run and reported only this county's live
per-county evaluation. No other counties touched, no shared code paths modified.
