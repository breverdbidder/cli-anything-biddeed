# Gold Standard shard-13: lafayette — dispatch b34a2384 re-fire, 8th consecutive session

## Result: 8/10, no change (correctly)

| Letter | Before | After | Notes |
|---|---|---|---|
| A | PASS (fc=1 td=1) | PASS (fc=1 td=1) | Unchanged. Dispatch brief text was stale (listed old `fc=1 td=0` from before the prior session's real fix). |
| B | FAIL (null) | FAIL (null) | Genuinely blocked, re-confirmed via 3 fresh avenues (2 workflow + 1 direct) |
| C | PASS 100.0 | PASS 100.0 | No regression |
| D | PASS 100.0 | PASS 100.0 | No regression |
| E | PASS 100.0 | PASS 100.0 | No regression |
| F | FAIL (null) | FAIL (null) | Genuinely blocked, same root cause as B (closed_sold=0) |
| G | PASS 100.0 | PASS 100.0 | No regression |
| H | PASS 2.7→2.9 | PASS 2.9 | Fresher (no writes; recomputes off existing last_seen) |
| I | PASS 100.0 (2/2) | PASS 100.0 (2/2) | No regression |
| J | PASS 100.0 (2/2) | PASS 100.0 (2/2) | No regression |

## What happened

This is the **8th consecutive session** against effectively the same B/F blocker (dispatch
`b34a2384` was already worked twice before — original firing, a duplicate-firing addendum — then
a related dispatch `e440836a` did a 7th session with 2 more avenues). A live
`pencil_dod_evaluate_county('lafayette')` check at session start confirmed the county unchanged at
**8/10** (A,C,D,E,G,H,I,J pass; B,F fail, `auctions_total=2`), matching every prior report exactly.

Rather than re-running any of the **10 already-exhausted avenues** documented across the 6 prior
session reports (RealAuction subdomain probes, the original Wayback tax-deed notice, Municode's
Angular SPA JSON API, myfloridacounty.com/orisearch Turnstile CAPTCHA, Civitek Florida OCRS
Turnstile CAPTCHA, the Tax Collector site, the FY2024 Auditor General AFR, third-party tax-deed
aggregators, Beacon/Schneider property-appraiser record card, and the FL unclaimed-property/surplus
channel), this session pursued **3 genuinely new avenues**: one direct manual check, plus one
ultracode Workflow (`wf_fc840b555-022`, per the ULTRALOOP protocol) fanning out 2 more avenues with
adversarial verification.

### Avenue 11 (direct, this session) — later Wayback snapshot comparison of the notice PDF

The prior session's fix for criterion A pulled a single Wayback snapshot (2025-08-03) of
`taxdeed-notices-revised-1.pdf`, which is a **pre-sale** application notice for Certificate 2022-28
scheduled for 2024-09-12 — containing no outcome data by construction. This session queried the
Wayback CDX API for the full snapshot history of `lafayetteclerk.com` tax-deed-related PDFs and found
an **earlier-uploaded, differently-named revision** (`taxdeed-notices-revised.pdf`, snapshot
2024-11-25 — ~2.5 months *after* the scheduled sale date) that had not been examined before.

Downloaded and rendered both the 2024-11-25 and 2025-08-03 snapshots to PNG (both are scanned-image
PDFs, no text layer — confirmed via `pdftotext` returning empty output) and visually inspected every
page. Finding (**VERIFIED**, screenshots taken):
- The 2024-11-25 snapshot lists 4 certificates. One (Cert 2022-321) carries a hand-stamped red
  **"CANCELLED"** overlay — proving the clerk does actively mark this specific PDF when a certificate
  is redeemed/withdrawn before sale.
- Certificate 2022-28 (our target, Bandit Capital LLC / parcel 07-04-11-0000-0000-00501) carries
  **no such stamp** in either the 2024-11-25 or 2025-08-03 snapshot — the two are otherwise
  byte-near-identical (258,128 vs 258,805 bytes, same 4 pages, same content).
- The **live** `lafayetteclerk.com/departments-services/clerk-services/tax-deeds/` page today
  (2026-07-12, re-fetched fresh) reads "There are no properties on the list of tax deeds at this
  time" and no longer even links this PDF.

**Verdict: dead end, but an honest one.** The absence of a "CANCELLED" stamp is not evidence the sale
completed — it's equally consistent with the clerk simply never updating this specific document after
July 2024 (the PDF is stale/orphaned, unlinked from the live page, yet still web-accessible). No
sale result, bidder, or dollar amount is present on any page. This closes off the "check a later
archival snapshot" hypothesis cleanly: confirmed genuinely no update ever occurred to this source.

### Avenue 12 (workflow) — BOCC meeting minutes for the Sept 12, 2024 sale date

The tax deed sale notice states the sale occurs "in the County Commissioners meeting room" —
hypothesis: Board of County Commissioners minutes/agendas for that date might independently document
the sale result. **Dead end (adversarially verified):** Lafayette County's only "Agendas & Minutes"
link resolves to Municode's **MunidocsNEXT ordinance-library SPA** (`library.municode.com`), not a
meetings/agenda calendar — confirmed by both the discoverer and an independent verifier fetching the
identical 403/blank-shell response. Municode's separate dedicated Meetings product
(`meetings.municode.com/lafayette_county`) returns a literal 404 "Friendly Error Page," indicating the
county isn't even provisioned on that product. No Granicus/CivicPlus/BoardDocs/eScribe presence found
via web search. No accessible BOCC minutes archive exists for this county at all — genuine access
barrier (JS SPA + no working API + no minutes product), not a confirmed negative on content, but no
sale result is retrievable regardless.

### Avenue 13 (workflow) — Florida's statutory public-notices portal (floridapublicnotices.com)

Distinct from the generic "third-party tax-deed aggregators" already ruled out — this is the FL
Statute 50.0211-mandated official legal-notice portal, which sometimes carries post-sale "Notice of
Surplus Funds" filings. **Dead end (adversarially verified):** zero relevant hits across 7 search
query variants (`site:floridapublicnotices.com` + Lafayette/Bandit Capital/2022-28/Feldscher
combinations, plus general web searches for excess-proceeds/surplus-funds language). The 2 candidate
hits that did surface (`/notices/11586011`, `/notices/11018775`) were independently fetched by both
agents and confirmed to be unrelated notices (a Broward foreclosure case and a Seminole County tax
deed, respectively) — false positives correctly rejected, not miscounted as evidence.

All 3 avenues were independently adversarially re-verified (a second agent, or in avenue 11's case
direct re-fetch + visual re-inspection by me, re-checked every claim rather than trusting it blind).
**Net verdict: no actionable new evidence for either letter.** No CAPTCHA was solved, no sold amount,
winning bidder, or completed-sale status was fabricated.

## Live evaluation JSON — BEFORE (session start, 2026-07-12T00:2xZ)
```json
{"A":{"pass":true,"detail":"fc=1 td=1","metric":1},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":true,"detail":"matched_clean=2","metric":100},"D":{"pass":true,"detail":"matched_any=2","metric":100},"E":{"pass":true,"detail":"parcel_linked=2","metric":100},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":2.7},"I":{"pass":true,"detail":"card_complete=2 of 2","metric":100},"J":{"pass":true,"detail":"deal_complete=2 (triangle + two-arm CMA + ml_score + max_bid)","metric":100},"county":"lafayette","V2_LITMUS":null,"auctions_total":2}
```

## Live evaluation JSON — AFTER (post-research, same session)
```json
{"A":{"pass":true,"detail":"fc=1 td=1","metric":1},"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},"C":{"pass":true,"detail":"matched_clean=2","metric":100},"D":{"pass":true,"detail":"matched_any=2","metric":100},"E":{"pass":true,"detail":"parcel_linked=2","metric":100},"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},"G":{"pass":true,"detail":"density=100.0 far= pk1000=","metric":100},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":2.9},"I":{"pass":true,"detail":"card_complete=2 of 2","metric":100},"J":{"pass":true,"detail":"deal_complete=2 (triangle + two-arm CMA + ml_score + max_bid)","metric":100},"county":"lafayette","V2_LITMUS":null,"auctions_total":2}
```

Identical apart from H's freshness clock (no writes occurred this session — no fix was warranted; a
negative research result is not a bug to patch).

### SQL VERIFICATION
```sql
SELECT public.pencil_dod_evaluate_county('lafayette');
-- returned the AFTER JSON above, run 2026-07-12T00:31Z via Supabase Management API
-- (direct psql auth unavailable in this sandbox -- same environment constraint documented
-- in the prior e440836a session report)

INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES (...) RETURNING id, letter, survived, created_at;
-- id=6199, B, true, 2026-07-12 00:31:27.750188+00
-- id=6200, F, true, 2026-07-12 00:31:27.750188+00
```

## Recommendation

This is now the **8th consecutive session** confirming the identical structural block for B/F,
across **13 total distinct research avenues** (3 new this session: later-Wayback-snapshot
comparison, BOCC minutes, and Florida's statutory public-notices portal). Every avenue not gated by
a Cloudflare Turnstile CAPTCHA, a hard WAF/bot-management block, or a JS-only SPA with no working API
has now been tried and independently adversarially re-verified as a clean negative. The remaining
paths — (a) headless-browser + CAPTCHA-solving tooling, or (b) a direct phone/mail records request to
the Clerk (386-294-1600) or Property Appraiser (386-294-1991) — remain out of scope for an automated
pipeline session under current repo policy.

**Recommend this dispatch be closed or superseded for lafayette B/F specifically**, exactly as the
prior (e440836a) session recommended. A/C/D/E/G/H/I/J are stable and correctly closed at 8/10.
Re-firing this dispatch unchanged will reproduce this exact result and burn session budget with zero
yield; if lafayette needs revisiting, it should be scoped as an explicit CAPTCHA-tooling-authorization
or manual-records-request task, not another automated research pass.

## Ultraloop audit

Mode: `native` (Workflow tool fan-out + adversarial verify, per this session's ultracode directive).
Run: `wf_fc840b55-022`. 4 agents (2 discover + 2 verify), ~214K tokens, 62 tool calls, ~2.9 min, plus
1 avenue (later-Wayback-snapshot comparison) done directly by the main session with screenshot
evidence. 2 rows logged to `gold_standard_ultraloop_audit` (dispatch_id
`b34a2384-438c-4a9d-b28e-a82167b4bc5b`, ids 6199-6200, letters B and F, both `survived=true`).

## Fleet coordination

`git pull --rebase` run before this commit (parallel-fleet protocol — shard14/putnam and a
shard12/glades migration landed concurrently during this session, no overlap with lafayette). Per
protocol, skipped the fleet-wide `gold_standard_loop()` / `gold_standard_certify()` run and reported
only this county's live per-county evaluation. No other counties touched, no shared code paths
modified.
