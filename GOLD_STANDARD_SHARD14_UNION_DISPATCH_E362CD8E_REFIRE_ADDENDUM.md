# Gold Standard shard-14 — union — duplicate dispatch re-fire addendum (attempt 2/3)

dispatch_id: `e362cd8e-5af1-4231-8534-7b392313352f`
chat_session: `architect-20260731T000000`
county: **union** (8/10: A,C,D,E,G,H,I,J PASS; B,F FAIL)
guard: `GUARD RE-FIRE — attempt 2/3` on issue #16927 (DoD unmet since B/F cannot be structurally satisfied yet)

## This dispatch was a duplicate re-fire, same calendar day

The exact same dispatch_id + chat_session already shipped in full as commit
`fe2e2c62` (`GOLD_STANDARD_SHARD14_UNION_DISPATCH_E362CD8E_SESSION_REPORT.md`).
At this session's start, live `pencil_dod_evaluate_county('union')` matched
that report's final-state JSON exactly — identical 3 rows in
`multi_county_auctions`, identical `closed_sold=0`. Zero drift confirmed
before doing any new work.

Per the redispatch protocol comment on the issue ("do not repeat work a prior
comment marks complete"), I did not re-run the full DB/source investigation
already done this morning. Instead I ran one lean adversarial Workflow (3
agents) scoped specifically to find anything genuinely *new* since that
session: a fresh source-lever hunt (12 new candidate URLs tested, none of the
already-known-blocked ones re-tried), a fresh independent DB recheck, and an
adversarial refuter instructed to try to break the "nothing fixable today"
claim.

## Result: still nothing fixable. Verdict SURVIVES.

**Root cause (unchanged, re-confirmed live):** all 3 Union County rows have
`sold_amount IS NULL` — 2 foreclosures with future sale dates
(`63-2025-CA-0053` → 2026-08-13, `63-2024-CA-0047` → 2026-10-15) and 1
redeemed tax deed (`UNION-TD-CERT223`, redeemed 2026-03-12, which by FL Ch.
197 statute never produces a `sold_amount` — a permanent null, not a scraper
gap). `closed_sold=0` makes B (`verified/closed_sold`) and F
(`tier1_sold/closed_sold`) mathematically null.

**New in this session — a structural discovery, not a fix:** Union County
sales are conducted **in-person at the courthouse lobby** (55 W Main St, Lake
Butler, Thursdays 11am) rather than through any online auction platform.
Confirmed GovEase does not operate in Florida at all (statewide dead end, not
Union-specific); confirmed floridabidder.com/foreclosureauctiondata.com/
taxliens.com/LienHub/RealTDM either lack Union County coverage entirely or
403 on request; confirmed `myfloridacounty.com`'s Union County official-records
link resolves back to `unionclerk.com` (already Cloudflare-blocked) — not an
independent channel. Firecrawl re-tested this session: still HTTP 402
(insufficient credits, unchanged from this morning). No shared-vendor
backdoor found via Bradford/Baker/Columbia clerk sites (all 403 too).

**Adversarial refuter verdict: SURVIVES.** Checked date-arithmetic framing
(no bug — both sale dates are genuinely 13 and 76 days in the future),
re-tested the one lever that looked structurally different
(`myfloridacounty.com` → confirmed it's just an indirection to the blocked
host), and re-ran the DB scoping/format-mismatch checks fresh (2 coincidental
digit-substring false positives correctly ruled out: a Duval case matching
`2024-CA-0047` as a substring, and 13 unrelated Brevard tax-deed certs
matching `223` as a substring — neither is a Union County row).

## Before / after (`SELECT public.pencil_dod_evaluate_county('union')`)

Identical — no letter changed, no regression on the 8 passing letters:

```json
{"A":{"pass":true,"metric":1,"detail":"fc=2 td=1"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100,"detail":"matched_clean=3"},
 "D":{"pass":true,"metric":100,"detail":"matched_any=3"},
 "E":{"pass":true,"metric":100,"detail":"parcel_linked=3"},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100,"detail":"density=100.0 far= pk1000="},
 "H":{"pass":true,"metric":13.5,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":true,"metric":100,"detail":"card_complete=3 of 3"},
 "J":{"pass":true,"metric":100,"detail":"deal_complete=3 (triangle + two-arm CMA + ml_score + max_bid)"},
 "county":"union","auctions_total":3}
```

## Why the guard will keep re-firing, and why that's expected

B and F for union are **time-gated, not effort-gated**. No amount of
additional session time moves them until an actual sale closes
(earliest: 2026-08-13) AND a working, non-blocked channel exists to read the
result. Recommend the guard system treat union B/F as blocked-until-date
rather than re-firing on a fixed attempt counter — flagging this
recommendation for the AI Architect rather than unilaterally changing guard
behavior.

## Next-session priorities (unchanged from the original report)

1. **After 2026-08-13**: retry `union.realforeclose.com`, Civitek OCRS,
   `unionclerk.com` direct, in that order. A single success writes an
   independent-source outcome to `foreclosure_outcomes`, which
   `promote_tier1_from_outcomes()` (existing cron — do not rebuild) carries
   into both B and F automatically.
2. **If Firecrawl credits are restored** (still 0 as of this session),
   retry `unionclerk.com` via Firecrawl's JS-rendering proxy.
3. **Manual fallback** if all digital channels remain blocked past
   2026-08-13: phone verification via Union County Clerk (386-496-3711) or a
   mail/in-person record request for the Certificate of Sale — Ch. 45.031/197
   F.S. require the Clerk to issue one, it is just not exposed through any
   scrapeable feed found across two independent sessions now.
4. **After 2026-10-15**: same recheck for the second case if the first
   didn't already unblock a working method.

## Cost / time

1 background Workflow (3 agents, ~174K subagent tokens, ~3.6 min wall
clock), ~10 live WebFetch/curl probes against new candidate sources, 1
re-tested Firecrawl call (402, no charge), DB queries via Management API
(free). Well under the $10 session cap. No code shipped — per WIRING
MANDATE, shipping a scraper against zero available/reachable data would be
wiring-mandate theater, not progress.
