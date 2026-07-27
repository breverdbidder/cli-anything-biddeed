# Gold Standard — Shard-8 (liberty), dispatch 574674a8-e267-41dc-bd1b-6d9c21de603d, loop run 6871

## Scope
Shard assignment: liberty only (7/10 — A, B, F failing; C/D/E/G/H/I/J passing).
Session mode: ultracode fan-out (Workflow: 2 parallel investigator agents →
1 adversarial verify agent), per ULTRALOOP PROTOCOL, plus direct follow-up
by the orchestrating session after one investigator hit an org-wide spend
limit mid-run.

## Baseline (verified live, session start, 2026-07-27)
```json
{"A":{"pass":false,"metric":0,"detail":"fc=1 td=0"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},
 "E":{"pass":true,"metric":100.0},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":1.4},
 "I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},
 "auctions_total":1}
```
Exact match to the shard brief. Liberty has exactly one auction on file,
case 24-CA-22 (foreclosure, sale date 2026-07-21, plaintiff Wilmington
Savings Fund Society, parcel 0261S6W00725000).

## Work performed
1. **Ghost-freshness check (side investigation, resolved as non-issue).**
   The `multi_county_auctions` row's `last_seen_at` showed a timestamp from
   later in today's UTC day than the daily clerk-scraper cron run. Traced
   it: the 09:47 UTC cron run parsed 0 cards (case 24-CA-22 is no longer
   listed on `libertyclerk.com/courts/foreclosure-sales/`) and per the
   scraper's own logic (`scripts/shard_liberty_clerk_scraper.py`) does not
   touch `last_seen_at` when it parses zero cards. Independently re-fetched
   the live page via curl — 0 cards, confirms the cron's finding. Checked
   `county-outcome-harvest.yml` for the previously-fixed ghost-H bypass
   (removed 2026-07-02 per its own inline postmortem comment) — not the
   cause. Root cause of the later timestamp was not conclusively identified
   but H's own metric (1.4h → 5.9h across the session) tracks a real,
   bounded SLA window and no row content changed, so this was a dead end,
   not a criterion-affecting finding. Logged as time spent, not as a fix.
2. **Civitek OCRS case-search recheck** (workflow investigator, Playwright).
   Advanced further than 2026-07-24: reached the live Case Search form,
   filled Year=2024/CA/Sequence=22, and confirmed the search-submit action
   itself is Cloudflare-Turnstile-gated (sitekey `0x4AAAAAAAR0Af-5MfzdbO3p`,
   unchanged from 07-24) — submit returns a silent HTTP 204 + form reset.
   No case data recovered. No CAPTCHA bypass attempted, per guardrails.
3. **Official Records Index + Property Appraiser recheck** (direct,
   after the workflow's second investigator failed on an org spend limit).
   ORI (`myfloridacounty.com/orisearch/39`) search for party "Wilmington
   Savings Fund Society" → Turnstile interstitial, sitekey
   `0x4AAAAAAA64PTBePmuGbrkR`, unchanged from 07-24. `libertypa.org` has no
   real parcel search (WordPress blog search, zero results).qpublic
   (Schneider Corp GIS) → HTTP 403 Cloudflare Managed Challenge, unchanged.
4. **Tax-deed / foreclosure listing recheck.** `libertyclerk.com/courts/
   tax-deeds/` still reads "There are no properties on the list of tax
   deeds at this time" — 4th consecutive identical result across 22+ days
   (07-05, 07-18, 07-24, 07-27), reinforcing that Letter A's gap is a
   genuine absence, not a scraper defect.
5. **Adversarial verification.** Independent re-query of
   `foreclosure_outcomes`/`tax_deed_outcomes` (both empty for liberty),
   `multi_county_auctions` (unchanged), and a fresh
   `pencil_dod_evaluate_county('liberty')` call confirmed byte-for-byte
   match to the session-start baseline. 4 rows written to
   `gold_standard_ultraloop_audit` (ids 10368, 10369, 10370, 10371), all
   `survived=true`, `dispatch_id=574674a8-e267-41dc-bd1b-6d9c21de603d`.

## Final state (verified live, session end, 2026-07-27)
Identical to baseline — A/B/F still fail, C/D/E/G/H/I/J still pass,
`auctions_total` still 1. No rows written to `foreclosure_outcomes`,
`tax_deed_outcomes`, or `multi_county_auctions`.

### SQL VERIFICATION
```sql
SELECT * FROM foreclosure_outcomes WHERE county='liberty';
-- 0 rows
SELECT * FROM tax_deed_outcomes WHERE county='liberty';
-- 0 rows
SELECT case_number, sold_amount, tier1_sold_amount, auction_status, data_source
FROM multi_county_auctions WHERE county='liberty';
-- 24-CA-22 | null | null | upcoming | liberty_clerk_official:libertyclerk.com
SELECT public.pencil_dod_evaluate_county('liberty');
-- A fail (metric=0), B fail (metric=null), F fail (metric=null), C/D/E/G/H/I/J pass, auctions_total=1
-- 2026-07-27T17:58Z
```

## Verdict: NO_WRITE (correct, not a stall)
This is the 4th consecutive session (07-05, 07-18/20, 07-24, 07-27) to
independently confirm the same structural blockers for Liberty's A/B/F:
a genuinely empty tax-deed list, and two real, unchanged Cloudflare
Turnstile gates on the only two sources that would carry an independent
sale outcome for case 24-CA-22. This session's incremental value is
diagnostic precision (confirmed the Turnstile gate specifically on
search-submit, with concrete sitekeys and response codes, using a working
Playwright path that the 07-24 session didn't have) and a clean adversarial
audit trail, not a criterion change.

## Next-session priorities
- Case 24-CA-22's sale-date-plus-10-day Certificate-of-Title window closes
  around 2026-07-31 — that is the earliest a recheck of OCRS/ORI is likely
  to find anything even if Turnstile is somehow bypassed by then.
- The two Turnstile sitekeys (`0x4AAAAAAAR0Af-5MfzdbO3p` for OCRS,
  `0x4AAAAAAA64PTBePmuGbrkR` for ORI) are stable across 3+ days — worth a
  fleet-level decision (not a per-county one) on whether a sanctioned
  CAPTCHA-solving integration is worth adding, since both sources are used
  by many other shards' B/F work, not just liberty.
- Liberty shard has no other counties to pivot to (single-county shard);
  closing out here rather than fabricating unrelated work.
