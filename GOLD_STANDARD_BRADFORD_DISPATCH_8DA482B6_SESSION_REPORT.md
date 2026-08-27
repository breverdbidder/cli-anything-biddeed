# Gold Standard — bradford (letters B, F) — dispatch 8da482b6

dispatch_id: 8da482b6-8cff-45ea-9950-4e8fed552f37 · session 2026-08-27

## Live state (pencil_dod_evaluate_county, before and after — unchanged)

```json
{"A":{"pass":true,"metric":1,"detail":"fc=4 td=1"},"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},"C":{"pass":true,"metric":100.0,"detail":"matched_clean=5"},"D":{"pass":true,"metric":100.0,"detail":"matched_any=5"},"E":{"pass":true,"metric":100.0,"detail":"parcel_linked=5"},"F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":1.6},"I":{"pass":true,"metric":100.0,"detail":"card_complete=5 of 5"},"J":{"pass":true,"metric":100.0,"detail":"deal_complete=5"},"auctions_total":5}
```

8/10. B and F remain null/FAIL — 0 of 5 bradford rows have `sold_amount`.

## Prior-session history read before starting

This is at least the **10th documented session** to work bradford B/F, not the 6-7 estimated
in the dispatch brief. Read in full before starting:
- `GOLD_STANDARD_SHARD1_BREVARD_GULF_BRADFORD_SANTAROSA_PINELLAS_DISPATCH_3CE988AC_SESSION_REPORT.md`
  (2026-08-14) — explicitly declared case `25000457CAAXMX` dead, "stop re-trying it."
- `GOLD_STANDARD_SHARD4_BRADFORD_CALHOUN_UNION_DISPATCH_8389B490_SESSION_REPORT.md`
  (2026-08-13) — 9th consecutive reconfirm, 3 case-specific checks beyond 8 prior generic sweeps.
- `.claude/workflows/gold-standard-shard6-bradford-run7177-f68d2ec5.js` +
  `supabase/migrations/20260729_gold_standard_shard6_bradford_bf_5th_reconfirm_civitek_turnstile.sql`
  (2026-07-29) — civitekflorida.com OCRS reached a real JSF search form but is Turnstile-gated
  on the search action itself; Box.com "FORECLOSURE SALE LIST" link is unreachable (parent page
  Cloudflare-blocked even via Firecrawl's browser-rendering engine, HTTP 408 every attempt).

Confirmed-dead list (do not re-try, per accumulated history): bradfordclerk.com (Cloudflare
403/challenge, static and rendered), Firecrawl static + browser-rendered scrape of same,
bctelegraph.com legal notices (now checked through every issue up to and including 2026-08-27),
surplusindex.com (404), Wayback Machine (only captures the challenge page), bradford.realforeclose.com
(not a RealAuction client), officialrecords.bradfordclerk.com (DNS failure), myfloridacounty.com
ORI (Turnstile), gz.floridapa.com (unrelated CGI), records.bradfordco.org/PSI (login wall),
civitekflorida.com/ocrs (Turnstile on search action), Box.com sale-list link (unreachable),
bradfordappraiser.com GIS parcel detail (403 to non-interactive access).

## What this session tried (genuinely new angles per dispatch instructions)

1. **bctelegraph.com legal notices through today's issue** (2026-08-27) — new check; prior
   sessions had only confirmed through 7-23-26/7-30-26. Fetched the 8-20-26 and 8-27-26 issues
   directly. Neither contains a Certificate of Title, Certificate of Disbursements, or any
   post-sale/surplus notice for any of the 4 overdue case numbers (`25000457CAAXMX`,
   `25000439CAAXMX`, `25000487CAAXMX`, `24000431CAAXMX`). Only pre-sale/other-case notices found.
2. **floridapublicnotices.com** — confirmed this is a client-rendered SPA (static fetch returns
   a 301/no body); the rendered search UI only filters by county/newspaper/date range, not by
   case number, and the newspaper of record for Bradford is BC Telegraph — already checked
   directly and exhaustively above. This source is redundant with the BC Telegraph check, not
   a new independent lever.
3. **bradfordappraiser.com** — homepage loads (200) but its GIS/parcel-record search
   (`bradfordappraiser.com/GIS/` → Schneider/qPublic backend) returns 403 to non-interactive
   access, consistent with every prior session's finding on this source.
4. **WebSearch for each of the 4 case numbers / party names directly** — surfaced only the
   already-known pre-sale Final Judgment notices (BC Telegraph 7-9-26 for case 487, 7-30-26
   context for case 439); no sale-result content indexed anywhere for any of the 4 cases.

## Conclusion: NO_CHANGE

Zero rows written to `multi_county_auctions`, `foreclosure_outcomes`, or `tax_deed_outcomes`.
This is a genuine, well-documented structural ceiling: Bradford has no working RealAuction lane,
its clerk site and OCRS portal are both bot-blocked (Cloudflare / Turnstile) to any
non-interactive session, its Property Appraiser GIS is 403-blocked, and its paper of record
(BC Telegraph) has published zero post-sale notices for any of the 4 overdue cases as of
2026-08-27. B and F remain undefined (0/0), not merely failing.

2 rows inserted into `gold_standard_ultraloop_audit` (ids 18652–18653, dispatch
`8da482b6-8cff-45ea-9950-4e8fed552f37`, letters B/F, `survived=true`, `ultraloop_mode='fallback'`)
to keep the certification-freshness audit trail current and to record the newly-exhausted BC
Telegraph date range and the floridapublicnotices.com redundancy finding for the next session.

## Recommendation for future sessions

Do not keep polling generically. The only remaining lever that could genuinely move this is a
human-solvable Turnstile session against civitekflorida.com/ocrs/county/04/ (the anonymous OCRS
search reaches a real docket search form and is the single most promising un-exhausted path,
per the 2026-07-29 finding) — this requires a human-in-the-loop browser step, which no prior
automated session (including this one) is authorized to attempt per the CAPTCHA-bypass
prohibition. Absent that, continue the passive BC Telegraph poll on future issues only.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
