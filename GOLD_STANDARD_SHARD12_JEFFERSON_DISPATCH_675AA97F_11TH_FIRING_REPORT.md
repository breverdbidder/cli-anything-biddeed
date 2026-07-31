# Gold Standard shard-12: jefferson — 11th firing (GUARD RE-FIRE attempt 2/3)

dispatch_id: 675aa97f-3855-4c8c-b5e8-3ae2afc96d6d (issue #17031 — same dispatch as the 9th+10th firing,
already shipped to main in commit `993705e2` / rebased in `b2e44a38`)
chat_session: architect-20260731T080000
mode: ULTRALOOP native (ultracode opt-in — Workflow fan-out: 2 finders, 2 refuters)

## Result: 8/10 unchanged (A,C,D,E,G,H,I,J live-evaluator PASS; B,F FAIL). No metric moved. Not expected to.

This is a **duplicate re-dispatch**. The GitHub Actions automated guard re-fires an issue until its
DoD is met (10/10) or a blocker comment lands — this is attempt 2/3 on issue #17031's guard cycle,
firing hours after the 9th+10th firing already exhaustively worked and closed out this exact county.
Per the redispatch protocol comment on the issue ("Do not repeat work a prior comment marks complete"),
this session did **not** re-run the full 30+ source exhaustion. Instead it did fresh live verification
+ one additional disciplined adversarial pass to confirm nothing changed and nothing was missed.

### Fresh live verification (before any new work)
`pencil_dod_evaluate_county('jefferson')`, re-run via Supabase REST RPC:
```json
{"A":{"pass":true,"metric":1,"detail":"fc=1 td=2"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100.0,"detail":"matched_clean=3"},
 "D":{"pass":true,"metric":100.0,"detail":"matched_any=3"},
 "E":{"pass":true,"metric":100.0,"detail":"parcel_linked=3"},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000="},
 "H":{"pass":true,"metric":23.0,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":true,"metric":100.0,"detail":"card_complete=3 of 3"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=3 (triangle + two-arm CMA + ml_score + max_bid)"},
 "county":"jefferson","auctions_total":3}
```
Identical to the 10th firing (only H's freshness hours ticked up, still well inside the 48h SLA — time
passing, not a metric issue). Confirmed all 8 prior `gold_standard_ultraloop_audit` rows for this
dispatch (ids 11502-11509) exist live, matching the committed migration exactly.

Confirmed `shard-jefferson-clerk-scraper.yml` cron is healthy: last scheduled run 2026-07-27
(success, 18s), next scheduled Monday runs will catch the 2026-08-19 sale results once published.

Confirmed the 3 `multi_county_auctions` rows directly: `26-TD-04`/`26-TD-05` (tax deed) both
`auction_date=2026-08-19`, `auction_status=scheduled` — **the sale has not happened yet**, so B/F
cannot resolve by construction, not by search failure. `25-CA-164` (foreclosure) `auction_status=sold`,
`sold_amount=NULL` — the confirmed, exhaustively-researched blocker from firings 1-10.

### New work this firing: ultracode adversarial fan-out (not a blind re-exhaustion)
Rather than re-running the same ~30 already-exhausted sources, 2 finder agents each took a genuinely
untried angle, then 2 independent refuter agents tried to break each finding:

**B/F finder** — checked for a distinct Landmark Web/GovOS portal (doesn't exist for this county — only
exists for Jefferson County, *Alabama*), a separate Circuit Civil case-docket search (doesn't exist
publicly; `myflcourtaccess.com` requires login, `thepublicindex.org` is a people-search product with a
paywall, not a case-docket tool), and a local legal-notice archive (`ecbpublishing.com`/Monticello News
has no search function). Also found and checked one genuinely new independent source,
`floridaparcels.com` — live page for the exact parcel (340 S Marvin St) confirmed, but its sales history
shows only a 2014 entry and owner-of-record still James Thompson; the deed transfer has not propagated
there. **No sold_amount found or fabricated.**

**Refuter (B/F)** flagged `myfloridacounty.com/orisearch/33` as a supposedly-unexploited lever. Cross-
checked against this dispatch's own 2nd and 3rd firing addenda (both already on main): that exact URL
has been tried and confirmed Turnstile-gated via Playwright form-submission attempts since the **2nd
firing**. The refuter lacked that history and produced a false positive — verified and dismissed, not a
new lever.

**D finder** independently re-investigated the 10th firing's ghost-success finding: fetched
PropertyOnion's own FL coverage directory (`propertyonion.com/coverage/Florida`) — extracted the exact
48-county list, confirmed Jefferson is absent; `propertyonion.com/coverage/Florida/Jefferson` returns
HTTP 404 (real county pages resolve at this pattern). **Refuter independently reproduced all three
checks** (48-county list, 404, SEO-stub-only guessed listing URL) and found no contradicting evidence.
Conclusion **survives**: Jefferson is structurally outside PropertyOnion's footprint (one of 19/67 FL
counties with no coverage) — a genuine source-coverage gap, not a scraper bug. `jeffersonclerk.com` is
recommended as an alternate litmus for D specific to jefferson; redefining the shared D predicate is a
fleet-wide evaluator decision outside this single-county shard's authority (unchanged from the 10th
firing's escalation — reinforced, not resolved, here).

### Verification protocol followed
- `pencil_dod_evaluate_county('jefferson')` re-run live before any new work — confirmed zero drift.
- 3 new `gold_standard_ultraloop_audit` rows inserted live via Supabase REST (ids **11694** B
  survived=true, **11695** F survived=true, **11696** D survived=false — D stays `false` per the
  10th-firing convention: it's an open escalation, not a passing claim).
- `gold_standard_loop()`/`gold_standard_certify()` not run — jefferson is not at 10/10 and this session
  did not confirm other shards are idle, per PARALLEL-FLEET RULES.

### Honesty Protocol tags
- Live evaluator state identical to the 10th firing, zero drift: **VERIFIED** (REST RPC output pasted
  above, both firings).
- No genuinely new B/F lever found this firing: **VERIFIED** (2-finder/2-refuter fan-out, evidence in
  `gold_standard_ultraloop_audit` ids 11694-11695; the one refuter-flagged candidate was cross-checked
  against committed prior-firing history and confirmed already-exhausted).
- D ghost-success finding independently reproduced with stronger evidence (48-county PropertyOnion
  coverage list, 404 on Jefferson's coverage page): **VERIFIED** (live WebFetch by 2 independent agents,
  ids 11696).
- No sold_amount fabricated on any source this firing: **VERIFIED**.

### Recommendation to fleet dispatcher (repeated, now with an 11th confirming data point)
Suspend jefferson B/F re-fires on this dispatch until 2026-08-19 passes (tax deed sale date) /
2026-08-24 (first weekly clerk-scraper cron after). 11 consecutive firings, same B/F conclusion. D
requires an architect-level decision on the shared parity/litmus predicate — not another county-scoped
re-fire. This session's incremental value was confirming zero drift and ruling out one candidate lever
(`myfloridacounty.com/orisearch/33`) as already-exhausted rather than newly viable — worth recording so
a future firing doesn't re-flag it as a fresh lead.
