# Gold Standard Shard-2: marion + baker — Session Report

- dispatch_id: `4fd52dfc-0ee3-4a4b-bb86-47995a7b5d37`
- chat_session: `architect-20260730T160000`
- loop run: 7519
- date: 2026-07-30
- ultraloop_mode: fallback (manual Task fan-out — interactive session, no `/effort ultracode` menu in this environment)

## Scope

Assigned shard: **marion** (10/10 per brief), **baker** (6/10, C/D/E/I failing).
Per PARALLEL-FLEET RULES, only these two counties were touched. No schema/data
writes were made to any other county. `gold_standard_loop()` /
`gold_standard_certify()` were **not** run fleet-wide this session — per-county
`pencil_dod_evaluate_county()` was used throughout, per the brief's guidance
for when other shards may be mid-flight.

## marion — no action needed, 10/10 confirmed live

Live-verified at session start via `pencil_dod_evaluate_county('marion')`:
all 10 letters PASS, matching the brief exactly. No marion rows were touched
this session. Freshness re-established for the ultraloop certify gate: 10
`gold_standard_ultraloop_audit` rows written (one per letter, `survived=true`,
`refuter_evidence` = the live evaluator output).

```json
{"county":"marion","auctions_total":571,
 "A":{"pass":true,"metric":252,"detail":"fc=319 td=252"},
 "B":{"pass":true,"metric":100.0,"detail":"verified=167 closed_sold=167"},
 "C":{"pass":true,"metric":96.7,"detail":"matched_clean=552"},
 "D":{"pass":true,"metric":96.7,"detail":"matched_any=552"},
 "E":{"pass":true,"metric":98.4,"detail":"parcel_linked=562"},
 "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=167 closed_sold=167"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000=100.0"},
 "H":{"pass":true,"metric":0.1,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":true,"metric":95.1,"detail":"card_complete=543 of 571"},
 "J":{"pass":true,"metric":96.7,"detail":"deal_complete=552 (triangle + two-arm CMA + ml_score + max_bid)"}}
```

## baker — C/D/E/I re-verified genuinely blocked (5th independent session,
new avenues exhausted, no fabrication)

**Baseline == current state (no change, confirmed correct not to force one):**

```json
{"county":"baker","auctions_total":15,
 "A":{"pass":true,"metric":7,"detail":"fc=7 td=8"},
 "B":{"pass":true,"metric":100.0,"detail":"verified=1 closed_sold=1"},
 "C":{"pass":false,"metric":20.0,"detail":"matched_clean=3"},
 "D":{"pass":false,"metric":20.0,"detail":"matched_any=3"},
 "E":{"pass":false,"metric":20.0,"detail":"parcel_linked=3"},
 "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=1 closed_sold=1"},
 "G":{"pass":true,"metric":100.0,"detail":"density= far=100.0 pk1000=100.0"},
 "H":{"pass":true,"metric":0.1,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":false,"metric":20.0,"detail":"card_complete=3 of 15"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=15 (triangle + two-arm CMA + ml_score + max_bid)"}}
```

Root cause (12 of 15 rows across 6 case numbers, zero parcel/address/owner
data) matches the diagnosis from 4 prior independent sessions
(2026-07-05, 2026-07-10 ×2, 2026-07-11, 2026-07-25 dispatch `0c5b222d`). This
session re-verified live and tried every new avenue those sessions flagged as
worth re-checking:

1. **Re-ran `scripts/shard8_baker_e_parcel_source_gap_diagnostic.py` live.**
   Same 3 cases (`022025CA000148CAAXMX`, `022026CA000007CAAXMX` on 08/13;
   `022026CA000018CAAXMX` on 08/20) are still on the active RealAuction
   calendar. Pulled the **raw unescaped** JSON UPDATE payload (not just the
   cleaned text) to rule out a parsing gap: the Parcel ID link is literally
   `href="http://bakerpa.com/propertydetails.php?parcel="` — empty at the
   source — and there is no owner/defendant name anywhere on the card. This
   is confirmed genuine upstream absence, not a scraper bug (contrast with
   working case `022025CA000038CAAXMX` on the same feed, which has a fully
   populated parcel link and address).
2. **bakerpa.com is back up** (HTTP 200, was HTTP 521 in the 2026-07-24/25
   sessions) — the lead those sessions flagged as worth re-checking. Checked
   both `search.html` (owner/parcel/address) and `sales.html`: neither
   supports a court-case-number search, so it remains unusable without an
   owner name, which the source doesn't have for these 6 cases.
3. **`www.bakerclerk.com/foreclosures/` and `www.bakerclerk.com/`**: prior
   sessions saw HTTP 403 via plain `curl`/WebFetch and (correctly) couldn't
   tell if that was a missing-User-Agent issue (as `baker.realforeclose.com`
   turned out to be) or a real bot wall. Tested with a real Playwright/
   Chromium browser this session: genuine Cloudflare JS challenge page
   (`title="Just a moment..."` / `"Attention Required!"`), not a UA issue.
4. **New this session — `civitekflorida.com/ocrs/county/02/`** (Baker's
   official OCRS court-case search, flagged by the 2026-07-25 session as the
   next lever): reachable and does have a **Case Search** tab that accepts a
   decomposed case number (year / court type / sequence #). Got through the
   public disclaimer click-through with Playwright. But the search form is
   gated by a **Cloudflare Turnstile human-verification checkbox** on submit.
   Did not attempt to automate past it — CAPTCHA bypass is out of scope
   regardless of the legitimate public-records purpose, so this lever is
   closed for automated sessions (would need a human to search these 6 case
   numbers manually, or a records request as noted by earlier sessions).
5. Firecrawl API key was present this session (missing in 3 of the 4 prior
   sessions) but returned **HTTP 402 insufficient credits** — a different,
   also-genuine blocker.

**Conclusion:** structural source-data + bot-protection gap, not a pipeline
bug. Logged 4 `gold_standard_ultraloop_audit` rows (`county_slug=baker`,
`letter` in C/D/E/I, `survived=false`) documenting exactly what was tried and
found, so a 6th session doesn't re-spend budget re-discovering the same dead
ends — it should start from lever #4's CAPTCHA gate (needs a human, or a
different unblocking mechanism) or a manual clerk records request.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| marion | Verify 10/10, no fix needed | Verified 10/10 live, wrote 10 freshness-audit rows | None |
| baker C/D/E/I | Fix via parcel/address discovery | Confirmed genuinely blocked after exhausting 5 avenues (2 new this session: bakerpa.com re-check, live OCRS Case Search UI reached) | No metric change — correct outcome, not a shortfall (see honesty note below) |

**Deviation log:** No baker metric moved. This is not scope creep or a missed
task — the brief's own SHIP-TO-MAIN mandate requires real, verified fixes,
and fabricating parcel/address data (or scraping past a CAPTCHA) to force a
metric up would be a Honesty Protocol violation of exactly the kind CLAUDE.md
prohibits. Session budget went into verification depth (raw-payload check,
real-browser bot-wall confirmation, reaching the actual OCRS search form)
rather than county count, per the "3 alternatives before surfacing blocker"
principle — 3 new alternatives were tried (bakerpa.com, Playwright bot-wall
check, OCRS navigation) before concluding the letters are correctly blocked.

## Verification evidence

- `python3 mgmt_sql.py "SELECT public.pencil_dod_evaluate_county('marion');"` —
  pasted above, live output.
- `python3 mgmt_sql.py "SELECT public.pencil_dod_evaluate_county('baker');"` —
  pasted above, live output, unchanged from session-start baseline.
- `python3 scripts/shard8_baker_e_parcel_source_gap_diagnostic.py` — re-run
  live, same 3-live/3-vanished split as prior sessions.
- `gold_standard_ultraloop_audit`: 14 rows inserted this session (10 marion
  `survived=true`, 4 baker `survived=false`), verified via
  `SELECT county_slug, count(*) FROM gold_standard_ultraloop_audit WHERE dispatch_id='4fd52dfc-0ee3-4a4b-bb86-47995a7b5d37' GROUP BY county_slug;`
  → `{"marion":10,"baker":4}`.

## Next-session priorities

- baker C/D/E/I: needs either (a) a human to click through the OCRS
  Turnstile and search the 6 case numbers manually, then feed
  owner/legal-description back for a bakerpa.com lookup, or (b) a formal
  records request to the Baker Clerk, or (c) wait for the 3 live cases'
  sale dates (08/13, 08/20) to pass and re-check whether the plaintiff filed
  property details closer to auction.
- No open items for marion.
