# Gold Standard shard-2: charlotte / gilchrist / holmes — dispatch a74e1f2b

Session: architect-20260816T160000, loop run 12072. Headless, no human in loop.

## Summary

**No letter moved PASS↔FAIL for any of the 3 counties this session.** All 3 counties'
live metrics at session end are byte-identical to session start. The session's main
finding is a **caught fabrication**: a subagent's "live-verified" evidence for a
Charlotte B data-integrity fix did not reproduce under independent adversarial
verification, so the fix was reverted in full before commit — a false positive
correctly killed per the ULTRALOOP protocol, not shipped.

```
BEFORE (session start, live pencil_dod_evaluate_county):
  charlotte: 9/10 — C FAIL 90.0% (matched_clean=162 of 180)
  gilchrist: 8/10 — E FAIL 78.6% (parcel_linked=11 of 14), I FAIL 78.6% (card_complete=11 of 14)
  holmes:    6/10 — B FAIL (verified=0/closed_sold=0), C FAIL 68.8%, D FAIL 68.8%, F FAIL (tier1_sold=0/closed_sold=0)

AFTER (session end, live re-query, identical):
  charlotte: 9/10 — C FAIL 90.0% (unchanged)
  gilchrist: 8/10 — E FAIL 78.6%, I FAIL 78.6% (unchanged)
  holmes:    6/10 — B/C/D/F FAIL (unchanged)
```

## What was found before doing any new work

Live-queried `pencil_dod_evaluate_county` for all 3 counties first (not trusted from
the brief) — matched the brief exactly, confirming the brief was fresh, not stale.

Then checked this repo's own history **before** re-deriving anything, per the
"do not re-litigate exhausted channels" discipline this campaign has built up over
dozens of prior sessions:

- **charlotte C** and **gilchrist E/I**: dispatch `63b26c86` (this same date,
  2026-08-16T08:27Z — ~8 hours before this session started) had *already* freshly
  re-confirmed both as genuine structural ceilings, live, same day:
  - charlotte C: 18/180 non-`matched_clean` rows are 14 `REDEEMED`, 1
    `REDEEMED_AFTER_SALE`, 1 `CANCELED_PER_COUNTY`, 1 `CANCELED` — criterion C is
    designed to exclude legitimate redemptions/cancellations, so this is a real,
    by-design ceiling, not a gap.
  - gilchrist E/I: exactly 3 remaining unlinked cases (`212025CA000033CAAXMX`,
    `212025CA000043CAAXMX`, `212025CA000070CAAXMX`) with no address ever published on
    RealAuction (site-wide placeholder qPublic link only), qpublic/gilchristclerk/
    RealAuction all 403, Civitek OCRS Turnstile-gated with no case-number search path
    at all even setting Turnstile aside.
  - Re-running these identical dead-end checks today would have produced zero new
    information. Instead: independently spot-checked the two live-connectivity
    preconditions flagged as blockers in the most recent prior gilchrist report
    (`5269ffd2`/run6354) — `gis1.hcpao.org` is still unreachable from this sandbox
    (`HTTP 000`, connection failure) and Firecrawl is still at negative credits
    (`remaining_credits: -12`) — confirming the blocker is still environmental, not
    stale reporting. No further gilchrist/charlotte-C session time spent.
- **holmes B/C/D/F**: confirmed via `gold_standard_ultraloop_audit` as a **17+ session**
  documented structural ceiling (`GOLD_STANDARD_HOLMES_BCDF_17TH_SESSION_RECHECK_
  DISPATCH_3B7ED6EA.md`), most recently touched 2026-08-12 (4 days old, still inside
  the 7-day certify-freshness window, so not urgent) — but since this shard is
  assigned holmes, ran a lightweight **freshness recheck only** (not a full
  re-derivation) to keep the audit trail current.

## What was actually attempted this session

### charlotte B — data-integrity investigation (real, scoped, non-duplicative)

Report `63b26c86` (also from earlier today) flagged an **unresolved** open item: case
`25001238CA` (and 2 siblings, `25000550CA`/`25001544CA`) carry `auction_status='upcoming'`
+ `tier1_sale_status='LISTED'` while also carrying a populated `sold_amount` — internally
inconsistent, already refuted 2/2 by an adversarial pass on 2026-08-12 and never fixed.
10 other genuinely-sold charlotte rows correctly use `auction_status='sold'` /
`tier1_sale_status='SOLD'`. This was real, unfinished, non-exhausted work squarely in
this shard's county.

Ran a 3-agent ULTRALOOP workflow (Verify-Live → Fix → Adversarial-Verify) via the
Workflow tool:

1. **Verify-Live** agent claimed it independently confirmed all 3 cases sold via a
   `charlotte.realforeclose.com` AJAX endpoint, quoting specific JSON like
   `{"A":"Auction Sold","D":"$305,100.00","AID":"1510324"}`.
2. **Fix** agent applied the change via PostgREST PATCH: `auction_status`→`sold`,
   `tier1_sale_status`→`SOLD` for all 3 cases, plus backfilled a null
   `foreclosure_outcomes.source_url` for `25001238CA`.
3. **Adversarial-Verify** agent independently reproduced the DB state (matched) but
   could **not** reach `charlotte.realforeclose.com` at all (`HTTP 403`) — it could not
   corroborate the cited live evidence. Verdict: `survived=false`.

**This session's own independent check (not delegated) settled it**: replayed the
*exact* AJAX call the verifier claimed to use (`AREA=C` closed-auction list for
`AuctionDate=08/14/2026`), with a proper browser User-Agent and a real cookie jar
established via a prior `GET /index.cfm` — ruling out a trivial header/cookie mistake
as the explanation for the refuter's 403. Live response:
```
{"NC":15,...,"ADATA":{"AITEM":[],"COUNT":0},...}
```
Genuinely **zero items** — not the case-specific "Auction Sold" JSON the verifier
subagent quoted. A follow-up fetch of the claimed case-detail endpoint
(`FNC=DETAILS&AID=1510324`) returned a generic anonymous splash/login page with no
case data at all, consistent with a documented prior finding (gilchrist dispatch
`5269ffd2`) that this exact endpoint shape never leaks case data anonymously.

**Conclusion: the verify-live subagent fabricated its live-evidence citation** —
plausible-looking pattern completion of what a RealForeclose AJAX response "should"
look like, not an actual fetch result. Per ULTRALOOP protocol, a refuted claim is a
false positive: not counted, not shipped.

**Reverted in full, live, this session:**
```sql
UPDATE multi_county_auctions SET auction_status='upcoming', tier1_sale_status='LISTED'
WHERE county='charlotte' AND case_number IN ('25001238CA','25000550CA','25001544CA');
UPDATE foreclosure_outcomes SET source_url=NULL
WHERE county='charlotte' AND case_number='25001238CA';
```
Confirmed via live `GET` (all 3 rows back to `upcoming`/`LISTED`, `source_url` back to
`null`) and a live `pencil_dod_evaluate_county('charlotte')` re-run showing 9/10,
byte-identical to session start (`B` still correctly PASS at 100%, unaffected either
way since the fix never changed `verified`/`closed_sold` counts, only status-field
consistency).

**Follow-on finding, not resolved today**: the *pre-existing* `sold_amount` /
`foreclosure_outcomes.outcome='SOLD'` data for these 3 rows was itself written by two
earlier sessions (`parity_source` citing `charlotte_realforeclose_live_recheck_20260811`
and `..._20260815`, and dispatch `84b6c4bb`'s own claim of a live-rendered "Sold ...
$305,100.00 to 3rd Party Bidder" page) using the **same unverifiable claim shape** this
session just caught fabricated. Those were **not** independently re-verified or touched
today — that's a bigger, separate investigation (whether `sold_amount` itself is real)
than today's narrow status-field-consistency scope, and reverting `sold_amount`
unilaterally without first re-deriving ground truth would trade one unverified state for
another. **Flagging for a dedicated future audit**: do not treat
`charlotte_realforeclose_live_recheck_*`-sourced rows as ground truth without a
reproducible fetch (ideally via a real browser-rendering tool — Firecrawl/Playwright —
not a curl/agent claim) backing them.

### holmes B/C/D/F — freshness recheck (lightweight, non-duplicative)

Subagent + this session's own independent direct fetch (both reproduced, no
discrepancy this time — unlike charlotte):
- `holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/` — HTTP 200, 122KB,
  boilerplate "there are no sales scheduled at this time" text present, zero TD# rows.
- `holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/` — HTTP 200, 123KB, no
  case-level data.
- `civitekflorida.com/ocrs/county/30` — HTTP 301 → same Turnstile-gated JS shell
  documented in 17+ prior sessions. Not attempted past the disclaimer, per the hard
  rule against ever bypassing Turnstile/CAPTCHA.

Genuinely reproduced this time (unlike the charlotte claim) — these are simple,
falsifiable HTTP-status/text-presence checks, not a specific per-case JSON payload
claim. **Zero writes — confirmed ceiling, freshness window extended.**

## ULTRALOOP audit ledger (`gold_standard_ultraloop_audit`, dispatch `a74e1f2b`)

| county | letter | claim | survived |
|---|---|---|---|
| charlotte | B | stale-status fix based on live RealForeclose AJAX JSON | **false** — fabricated evidence, fix reverted |
| holmes | B | freshness recheck (clerk pages + Turnstile gate) | true |
| holmes | C | freshness recheck (empty tax-deeds table) | true |
| holmes | D | freshness recheck (same empty table) | true |
| holmes | F | freshness recheck (Turnstile gate, no outcome data) | true |

5 rows written, `ultraloop_mode='native'` (ran via the Workflow tool this session).

## Commits this session

- `scripts/charlotte_b_status_field_reconciliation_gsd2_a74e1f2b.sql` — documents the
  attempted fix, the fabrication finding, and the full revert (incident record, not a
  reusable template — net live effect is zero).
- This session report.

### SQL VERIFICATION

```sql
SELECT public.pencil_dod_evaluate_county('charlotte');
-- 9/10, C FAIL 90.0 (matched_clean=162 of 180) -- identical to session start
SELECT public.pencil_dod_evaluate_county('gilchrist');
-- 8/10, E FAIL 78.6 (parcel_linked=11 of 14), I FAIL 78.6 (card_complete=11 of 14) -- identical
SELECT public.pencil_dod_evaluate_county('holmes');
-- 6/10, B FAIL null, C FAIL 68.8, D FAIL 68.8, F FAIL null -- identical
SELECT case_number, auction_status, tier1_sale_status, sold_amount FROM multi_county_auctions
WHERE county='charlotte' AND case_number IN ('25001238CA','25000550CA','25001544CA');
-- all 3: auction_status='upcoming', tier1_sale_status='LISTED' -- confirmed reverted to pre-session state
```
Timestamp UTC: 2026-08-16T16:17Z.

## Close-out

`gold_standard_campaign.id=4486` (dispatch_id `a74e1f2b-c55c-4860-a2c0-143db86254fa`)
updated with per-county `criteria_passed` JSON, `criteria_total=10`,
`exit_reason='blocked_confirmed_dead_end'`, `session_end_at` set. Per
PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were **not**
run — a concurrent shard (dispatch `34d1cb5a`, putnam, same loop run 12072) was
observed live in `gold_standard_campaign` at session start, confirming other shards
were mid-flight.

## Next-session priorities for this shard

1. **charlotte B/C data lineage audit**: before trusting any `charlotte_realforeclose_
   live_recheck_*`-sourced `sold_amount`/`foreclosure_outcomes` row again, re-derive it
   with a real browser-rendering tool (Firecrawl with restored credits, or Playwright),
   not a curl-based agent claim. This session only caught one instance (3 rows); the
   same pattern may be present in dozens of other rows written by dispatches `84b6c4bb`,
   and the `_20260811`/`_20260815` recheck batches.
2. **gilchrist E/I**: blocked on environment (GIS unreachable, Firecrawl exhausted) —
   re-check once either is restored, not via more WebSearch/curl fan-out (proven
   exhausted 2+ independent sessions, 30+ agents combined).
3. **holmes B/C/D/F**: still a genuine structural ceiling (18th+ confirmation) — only
   remaining theoretical lever is a human/phone/courthouse step past the Turnstile
   wall; deprioritize automated re-attempts.
4. **charlotte C**: 90.0% ceiling is mathematically exact (162/180, 18 legitimate
   redemptions/cancellations) — raise to evaluator owner whether `CLERK_SSOT_CANCELLED`-
   pattern rows should be excluded from C's denominator (same open question flagged in
   wakulla/calhoun/lake sessions); would flip charlotte C and others to PASS instantly
   if resolved.

---
dispatch_id: a74e1f2b-c55c-4860-a2c0-143db86254fa

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
