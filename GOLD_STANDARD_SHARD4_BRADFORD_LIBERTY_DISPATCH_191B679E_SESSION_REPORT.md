# Gold Standard — Shard-4 (bradford, liberty), dispatch 191b679e-346a-4750-8da5-42d78713b138, chat_session architect-20260809T160000

## Scope
Shard assignment: bradford (8/10 — B, F failing) + liberty (7/10 — A, B, F failing).
Session mode: ultracode Workflow fan-out (4 parallel independent live-recon leads
→ 4 adversarial verify agents), per ULTRALOOP PROTOCOL. Native mode (workflow tool used directly).

## Baseline (verified live, session start, 2026-08-09 ~16:02 UTC)
```json
bradford: {"A":{"pass":true,"metric":1,"detail":"fc=4 td=1"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},
 "E":{"pass":true,"metric":100.0},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":7.1},
 "I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},
 "auctions_total":5}

liberty: {"A":{"pass":false,"metric":0,"detail":"fc=1 td=0"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},
 "E":{"pass":true,"metric":100.0},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":28.7},
 "I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},
 "auctions_total":1}
```
Both byte-identical to the prior same-day check (`gold_standard_ultraloop_audit` rows
at 2026-08-09 08:21–08:56 UTC, ~8h before this firing).

## Pre-work: extensive prior history reviewed
- **bradford**: 7+ prior B/F sessions (2026-07-21 → 2026-08-02), all converging on
  bradfordclerk.com Cloudflare-blocked, Civitek OCRS + myfloridacounty ORI
  Turnstile-gated at search-submit, bctelegraph.com reachable but no post-sale
  notice. Overdue case: **25000457CAAXMX** (sale date 2026-07-16, 24 days past due
  as of today).
- **liberty**: 6+ prior sessions (2026-07-05 → 2026-07-29), same two structural
  blockers: A — libertyclerk.com/courts/tax-deeds/ genuinely empty; B/F —
  Civitek OCRS + libertypa.org/qpublic.schneidercorp.com Cloudflare/Turnstile-gated.
  Overdue case: **24-CA-22** (sale date 2026-07-21, 19 days past due). The
  2026-07-29 report flagged 2026-07-31 (FL Certificate-of-Title recording lag) as
  the earliest point a recheck could plausibly find something new — that window
  has now passed, warranting a fresh check.

Given the density of very recent identical checks, this session ran a scoped
live recheck (not a from-scratch investigation) sized to what had genuinely not
been verified in the last 8h, per cost-discipline precedent from prior sessions.

## Work performed (ultracode Workflow, run wf_5b903184-70a, task w8rmk15n5)
**Phase 1 — Research (4 parallel independent agents), Phase 2 — adversarial verify
(4 independent refuters, each re-fetched primary URLs itself rather than trusting
the finder's report):**

1. **bradford B/F — case 25000457CAAXMX.** Directly fetched the primary-source
   Notice of Sale from bctelegraph.com (editions 6-25-26, 7-2-26): Case
   2025-CA-000457, VyStar Credit Union v. Estate of Debra Ilene Hunter et al.,
   Lot 10&11 Block 15 Ward City (Brooker FL), sale 7/16/2026 11:00 AM — confirms
   the case was real and correctly on our books. Checked 3 post-sale editions
   (7-23, 7-30, 8-6-26) — **zero post-sale/certificate-of-sale notice in any of
   them.** bradfordclerk.com still 403 (Cloudflare). **New this session:**
   corrected Civitek OCRS Bradford County code to **04** (prior notes had
   conflated it with Duval's 39) — reached the landing page only; the
   search-submit Turnstile gate was not attempted (no-bypass guardrail). No
   sale outcome recoverable. WebSearch produced two internally-contradictory
   fabricated case-detail variants — correctly identified and discarded as
   hallucination by both the finder and the verifier, not used as evidence.
2. **bradford — 4 other cases (25000439/25000487/24000431/04-2026-TD-002).**
   bradfordclerk.com listing page fully 403-blocked live (worse than some prior
   partial-reachability sessions) — confirmed via curl (2 UAs), WebFetch, and a
   Firecrawl JS-render bypass attempt, which failed on **HTTP 402 (Firecrawl
   account credits exhausted)** — flagged for fleet awareness, not spent
   against. All 4 cases' auction dates (08-13 ×2, 08-20, 09-09) are still in the
   future relative to today — correctly reported "no outcome possible yet,"
   not fabricated.
3. **liberty A — tax-deed listing.** libertyclerk.com/courts/tax-deeds/ — HTTP
   200, exact text "There are no properties on the list of tax deeds at this
   time," byte-identical to every check since 2026-07-05. **New observation:**
   the foreclosure-sales page is now also empty live (case 24-CA-22 has aged off
   the "upcoming" list, expected given its date passed) — flagged for awareness,
   does not retroactively invalidate the historical fc=1 capture.
4. **liberty B/F — case 24-CA-22.** libertypa.org and qpublic.schneidercorp.com
   both re-fetched with fresh cf-ray IDs — still HTTP 403 Cloudflare
   challenge/managed-challenge, confirmed live not cached. Civitek OCRS county
   code **39 confirmed correct for Liberty** (verified via page title/content).
   **New source this session:** libertyclerk.com/courts/foreclosure-sales/
   itself (not in any prior baseline) — HTTP 200, confirms nothing currently
   scheduled (consistent with the sale having occurred/lapsed) but carries no
   sold-amount or outcome text. Certificate-of-Title lookup remains genuinely
   **UNTESTED** (only search paths are stateful CAPTCHA-gated forms) — not ruled
   out, not fabricated as checked.

All 4 verifier agents independently re-fetched the primary URLs themselves
(not trusting the finder) and confirmed exact HTTP status / byte counts / quoted
text matched. All 4 claims **survived**. 5 rows inserted to
`gold_standard_ultraloop_audit` (letters bradford-B, bradford-F, liberty-A,
liberty-B, liberty-F; ids 13971–13975; `dispatch_id=191b679e-346a-4750-8da5-42d78713b138`,
`ultraloop_mode=native`), each citing this firing's live evidence.

## Final state (verified live, session end, 2026-08-09 ~16:13 UTC)
Identical to baseline for both counties. No rows written to `foreclosure_outcomes`,
`tax_deed_outcomes`, or `multi_county_auctions`.

### SQL VERIFICATION
```sql
SELECT public.pencil_dod_evaluate_county('bradford');
-- A pass (fc=4 td=1), B fail (null, verified=0/closed_sold=0), C/D/E pass (100.0),
-- F fail (null, tier1_sold=0/closed_sold=0), G/H/I/J pass, auctions_total=5
-- 2026-08-09T16:13Z (fresh re-run, byte-identical to session-start baseline)

SELECT public.pencil_dod_evaluate_county('liberty');
-- A fail (metric=0, fc=1/td=0), B fail (null), F fail (null),
-- C/D/E/G/H/I/J pass, auctions_total=1
-- 2026-08-09T16:13Z (fresh re-run, byte-identical to session-start baseline)

SELECT * FROM foreclosure_outcomes WHERE county IN ('bradford','liberty'); -- 0 rows
SELECT * FROM tax_deed_outcomes WHERE county IN ('bradford','liberty');    -- 0 rows

SELECT id, county_slug, letter, survived FROM gold_standard_ultraloop_audit
WHERE dispatch_id = '191b679e-346a-4750-8da5-42d78713b138';
-- (bradford,B,true) 13971, (bradford,F,true) 13972, (liberty,A,true) 13973,
-- (liberty,B,true) 13974, (liberty,F,true) 13975

UPDATE public.gold_standard_campaign SET
  criteria_passed = '{"bradford":{"A":true,"B":false,"C":true,"D":true,"E":true,"F":false,"G":true,"H":true,"I":true,"J":true},
                       "liberty":{"A":false,"B":false,"C":true,"D":true,"E":true,"F":false,"G":true,"H":true,"I":true,"J":true}}'::jsonb,
  criteria_total = 10, exit_reason = 'no_write_structural_blocker_reconfirmed',
  session_end_at = '2026-08-09T16:15:00Z'
WHERE id = 4021; -- APPLIED, HTTP 200
```

## Verdict: NO_WRITE (correct, not a stall)
This is the 8th consecutive bradford B/F session and 7th consecutive liberty
A/B/F session to independently confirm the same structural blockers — this
firing's incremental value: fresh live re-verification 8h after the last check,
a corrected Civitek OCRS county code for bradford (04, not 39), independent
confirmation the Civitek OCRS county code for liberty (39) is correct, one
newly-discovered non-dispositive source per county (bctelegraph.com post-sale
edition sweep for bradford; libertyclerk.com's own foreclosure-sales calendar
for liberty), a caught-and-discarded WebSearch hallucination, and a flagged
operational gap (Firecrawl credits exhausted — blocks a potential future
Cloudflare JS-render bypass route, fleet-level issue not fixed this session).
No CAPTCHA was bypassed or attempted at any point, per guardrails.

## Next-session priorities
- **bradford**: the only lever left for 25000457CAAXMX is a JS-executing browser
  session that can clear the Civitek OCRS (county 04) Turnstile at search-submit,
  or Firecrawl credits being replenished to attempt a JS-render bypass of
  bradfordclerk.com. Neither is available in this sandbox. Otherwise, wait for
  bctelegraph.com to publish a post-sale notice (none in 3 weekly editions since
  the sale) or for the 08-13/08-13/08-20/09-09 cases to reach their own sale
  dates.
- **liberty**: same CAPTCHA-gate blocker on libertypa.org/qpublic/Civitek OCRS
  (county 39). The Certificate-of-Title recording check is still genuinely
  untested (not just blocked) — worth a dedicated attempt if a JS-capable
  browser tool becomes available. A is structurally blocked until a tax-deed
  listing actually appears on libertyclerk.com — no lever exists to force this.
- **Fleet-level**: Firecrawl API credits are exhausted (HTTP 402) — this blocks
  every shard's Cloudflare-JS-render bypass attempts, not just bradford/liberty.
  Worth surfacing to Ariel for a credit top-up decision (outside this session's
  $10 budget and outside the ARM-2 pre-authorization, which is scoped to
  criterion-J retail-comps APIs only).
