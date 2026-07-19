# GOLD STANDARD SHARD-9 — dixie + walton — dispatch 487365d5 — 3RD FIRING ADDENDUM

Continuation of `SHARD9_DISPATCH_487365d5_DIXIE_WALTON_SESSION_REPORT.md` and
`SHARD9_DISPATCH_487365d5_DIXIE_WALTON_CONTINUATION_ADDENDUM.md` (same dispatch_id,
new firing, chat_session `architect-20260718T160000`). Both prior reports' work was
already shipped to main (commits `ed9656d4`, `7992fa84`, `f3212924`) before this
session started. Verified live on entry that DB state matched the 2nd-firing report
exactly (dixie 8/10, walton 8/10, C/D failing both counties) — no drift, no regression.

## No letter flipped this session — both counties remain at their honest ceiling

**dixie: 8/10 (unchanged).** **walton: 8/10 (unchanged).**

Both counties' C/D metrics are byte-for-byte identical to the 2026-07-18 baseline.
This session's contribution is **not a metric move** but real due-diligence work per
the ULTRALOOP PROTOCOL: independent (not trusting) re-verification of the standing
claims via a live regression-audit workflow (2 agents) + adversarial refuters (2
agents), plus one bounded follow-up research attempt on a genuinely new lever. All
findings logged as fresh `gold_standard_ultraloop_audit` rows (ids 7090-7094,
`survived=true`) to satisfy the CERTIFY GATE's 7-day freshness requirement.

## dixie C/D: structural ceiling re-confirmed independently; concrete new lever identified (not yet resolved)

**Independent re-verification (not trusting the prior session's claim):** re-queried
the FL DOR Statewide Cadastral ArcGIS FeatureServer myself for `CO_NO=15`, this time
pulling **all ~38,000 Dixie County records** via pagination (not a spot sample).
Confirmed: 0 of 38,000 `PARCEL_ID`/`PARCELNO` values match our stored parcel_id
format (`NN-NN-NN-NNNN-NNNN-NNNN`); the real DOR format is a strap scheme
(`NN NNNN-NN-*-NN`, e.g. `21 3529-02-*-11`, or a variant `NN NNNN-IR-X-N`). Zero
matches even on section-township-range prefix. This is now exhaustively confirmed,
not spot-checked. Also newly confirmed: dixieclerk.com states tax deed auctions are
**in-person only** — no online RealAuction/GovEase platform exists for Dixie, closing
that avenue definitively.

**New lever found and partially explored:** Dixie County's Civitek Online Court
Records Search (OCRS, `civitekflorida.com/ocrs/county/15/`) is live, public-tier
accessible, and had never been tried in 4+ prior sessions (those tried qPublic,
dixieclerk.com, WP search/REST/sitemap — all property-appraiser or clerk marketing
pages, not the actual circuit-court case system). Tax deed applications are filed as
real circuit-court cases; two rows already in our DB have real `15-YYYY-CA-NN` case
numbers (`15-2023-CA-57`, `15-2025-CA-46`), confirming CA is the correct court-type
code and sequence numbers run low (46, 57) for this small county.

A follow-up agent reached the live search form (disclaimer accept → Person Search /
Case Search tabs, confirmed via curl cookie-jar + JSF ViewState replay) but the
query attempt was session-killed by the server on the second AJAX step — the
ViewState token's XML shape changes depending on which UI component re-renders, and
blind curl-based replay is too fragile to complete a working query. **No disposition
data was retrieved for any of the 6 target rows this session — correctly not claimed
as fixed.**

**Honest assessment:** the ceiling is still 75.8% (25/33) this session, same as
2026-07-18. What changed is the diagnosis is now sharper and actionable: a follow-up
session with real browser automation (Playwright or a working Firecrawl balance —
this session's Firecrawl key had insufficient credits) should (a) drive Person
Search with Date-Case-Filed 08/01/2025-08/31/2025 + CA checkbox to list all Circuit
Civil filings in that window and cross-reference against the 6 parcel_ids/dates, or
(b) sweep Case Search `15-2025-CA-1` through `~150` for the same window.

**Adversarial verification: SURVIVED.** Independent refuter reproduced the ArcGIS
format-mismatch finding from scratch (own 38K-row pull, not copy of my numbers),
independently confirmed the in-person-only auction fact, and found the OCRS lever
without being told about it in advance.

## walton C/D: re-verified, genuinely still premature (1 day closer, not yet actionable)

6 rows remain unmatched, auction_date 2026-07-23/24, today is 2026-07-19 — 4-5 days
out, unchanged from the 2026-07-18 check. Refuter agent made a good-faith attempt to
independently verify (not just re-assert) via `walton.realforeclose.com` (blocked,
HTTP 403 bot wall — confirmed independently, matches this session's own earlier
attempt), `waltonclerkfl.gov` (gateway pages only, no embedded case data without an
authenticated Civitek OCRS session), and a web search for all 6 case numbers
individually (zero results anywhere). **Verdict: PLAUSIBLE, not fully CONFIRMED** —
the refuter correctly flagged that absence-of-results is consistent with, but does
not independently *prove*, "genuinely future" since the primary source (RealForeclose)
is inaccessible to automated fetch. Recommend: re-check with an authenticated
RealForeclose session or wait until after 2026-07-23/24 as originally planned. Logged
as a fresh, honestly-caveated audit row (7092/7093), not a blind re-assertion.

## walton I: non-blocking residual attempted, still open (time-sensitive, auction was tomorrow)

Case `26CA000030` (parcel_id NULL, auction_date 2026-07-20 — tomorrow at session
time) was the sole card-incomplete row (I already PASSes at 97.7%, 42/43). Attempted
via `walton.realforeclose.com` anonymous preview (403 Forbidden — same bot wall as
C/D) and Firecrawl scrape (failed: "Insufficient credits to perform this request").
Civitek OCRS for Walton requires registered-user/attorney access for its search tier
(unlike Dixie's, which has a working public tier) — confirmed via WebFetch of the
disclaimer page. No public source (web search, PropertyOnion, foreclosure
aggregators, newspaper legal-notice search) surfaced property details for this case.
**Genuinely unresolved, not fixed, not fabricated.**

## Session state at close

| County | Before this session | After this session |
|---|---|---|
| dixie | 8/10 (C,D fail 75.8%) | 8/10 (C,D fail 75.8% — unchanged, re-verified + new lever found) |
| walton | 8/10 (C,D fail 86.0%) | 8/10 (C,D fail 86.0% — unchanged, re-verified) |

## Next-session priorities

1. **dixie C/D**: pursue the Civitek OCRS lever (`civitekflorida.com/ocrs/county/15/`)
   with real browser automation (Playwright, or Firecrawl once credits are
   replenished) — either a Person Search date-range sweep (08/01/2025-08/31/2025,
   CA checkbox) or a Case Search sequence sweep (`15-2025-CA-1` through `~150`).
   Cross-reference any hits against the 6 stuck parcel_ids/dates. This is the first
   concrete, not-yet-exhausted lever in 4+ sessions.
2. **walton C/D**: re-check `realforeclose_aids` after 2026-07-23/24 (both auctions
   will have occurred by then) — with an authenticated RealForeclose session this
   time, since anonymous fetch is confirmed blocked.
3. **walton I**: case `26CA000030` (auction was 2026-07-20) — re-check post-sale;
   sold-result pages are sometimes accessible even when pre-sale previews are
   blocked. Non-blocking (I already PASS at 97.7%).
4. Firecrawl API key is out of credits — replenish before relying on it for
   RealForeclose/RealAuction scraping work.

## SQL VERIFICATION

```sql
SELECT public.pencil_dod_evaluate_county('dixie');
SELECT public.pencil_dod_evaluate_county('walton');
```
Run 2026-07-19 (UTC) via `rest/v1/rpc/pencil_dod_evaluate_county` against
`mocerqjnksmhcjzxrewo.supabase.co`, independently re-run by two separate audit agents
plus this session's own direct curl checks — all three byte-for-byte identical.

dixie: `{"A":{"pass":true,"metric":2,"detail":"fc=2 td=31"},"B":{"pass":true,"metric":100.0,"detail":"verified=12 closed_sold=12"},"C":{"pass":false,"metric":75.8,"detail":"matched_clean=25"},"D":{"pass":false,"metric":75.8,"detail":"matched_any=25"},"E":{"pass":true,"metric":100.0,"detail":"parcel_linked=33"},"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=12 closed_sold=12"},"G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000="},"H":{"pass":true,"metric":0.1,"detail":"hours since last_seen (SLA 48h)"},"I":{"pass":true,"metric":97.0,"detail":"card_complete=32 of 33"},"J":{"pass":true,"metric":97.0,"detail":"deal_complete=32"},"auctions_total":33}`

walton: `{"A":{"pass":true,"metric":6,"detail":"fc=37 td=6"},"B":{"pass":true,"metric":100.0,"detail":"verified=4 closed_sold=4"},"C":{"pass":false,"metric":86.0,"detail":"matched_clean=37"},"D":{"pass":false,"metric":86.0,"detail":"matched_any=37"},"E":{"pass":true,"metric":97.7,"detail":"parcel_linked=42"},"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=4 closed_sold=4"},"G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000="},"H":{"pass":true,"metric":9.4,"detail":"hours since last_seen (SLA 48h)"},"I":{"pass":true,"metric":97.7,"detail":"card_complete=42 of 43"},"J":{"pass":true,"metric":100.0,"detail":"deal_complete=43"},"auctions_total":43}`

ULTRALOOP audit rows this session: `gold_standard_ultraloop_audit` ids 7090-7094, all
`survived=true`, `dispatch_id='487365d5-71dc-4492-b06a-a58da6810cb8'`, `ultraloop_mode='native'`.

honesty markers: VERIFIED throughout for all live-query and live-fetch claims;
INFERRED explicitly labeled where noted (walton C/D "genuinely future" — PLAUSIBLE
not fully CONFIRMED, primary source inaccessible to automated fetch). No DB writes
were made this session — nothing was found that warranted one; a fabricated write
to manufacture a metric move would violate HARD GUARDRAIL #2 (fail-loud, no
ghost-success) and the SHIP GATE. BLANK > WRONG.

dispatch_id: `487365d5-71dc-4492-b06a-a58da6810cb8`
