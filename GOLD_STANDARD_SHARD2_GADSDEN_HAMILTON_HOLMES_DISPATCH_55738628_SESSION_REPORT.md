# Gold Standard Shard-2: gadsden, hamilton, holmes — session report

- dispatch_id: `55738628-3d02-4817-b621-062ea5466146`
- chat_session: `architect-20260817T160000`
- loop run at launch: 12244
- session window: 2026-08-17 ~16:00Z–22:45Z
- ultraloop_mode: native (Workflow tool, one research agent + one adversarial refuter per finding)

## Starting state (live, verified via `pencil_dod_evaluate_county`)

| county | score | failing letters |
|---|---|---|
| gadsden | 9/10 | C (87.7%, matched_clean=57/65) |
| hamilton | 8/10 | C, D (81.0%, matched_clean=matched_any=17/21) |
| holmes | 6/10 | B, C, D, F (verified/tier1_sold=0; matched=11/16=68.8%) |

## Ending state

**No metric moved.** Live re-check at session close matches the starting state exactly (see `pencil_dod_evaluate_county` output pasted below). This session's contribution is deeper, adversarially-verified diagnostic evidence, not a fix — all three counties have been researched across 6–17+ prior sessions each and the remaining gaps are genuine structural/tool-boundary blockers, not engineering gaps we failed to close.

### SQL VERIFICATION (final reconfirm, 2026-08-17T22:4x UTC)

```
gadsden:  {"A":PASS(24),"B":PASS(100.0),"C":FAIL(87.7),"D":PASS(100.0),"E":PASS(100.0),"F":PASS(100.0),"G":PASS(100.0),"H":PASS(13.4),"I":PASS(100.0),"J":PASS(96.9)}
hamilton: {"A":PASS(6),"B":PASS(100.0),"C":FAIL(81.0),"D":FAIL(81.0),"E":PASS(100.0),"F":PASS(100.0),"G":PASS(100.0),"H":PASS(11.6),"I":PASS(95.2),"J":PASS(100.0)}
holmes:   {"A":PASS(6),"B":FAIL(null),"C":FAIL(68.8),"D":FAIL(68.8),"E":PASS(100.0),"F":FAIL(null),"G":PASS(100.0),"H":PASS(14.5),"I":PASS(100.0),"J":PASS(100.0)}
```

## Per-letter findings (adversarially verified — one research agent + one independent refuter per claim, per ULTRALOOP protocol)

### gadsden C — CONFIRMED blocked, fleet-scope issue (survived=true)
8 tax-deed cases (26000018TDC, 26000021TDC, 26000022TDC, 26000024TDC, 26000025TDC, 26000029TDC, 26000032TDC, 26000034TDC) are marked **"Redeemed"** on the live gadsdenclerk.com sheet. No clean sale exists to match, so by evaluator design (`supabase/migrations/20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql`) these correctly count toward D (matched_any, PASS) but are excluded from C (matched_clean). Reproduced independently via curl+regex parse of all 5 clerk sheet tabs (including the Excess-Proceeds tab, ruling out a clean-sale substitute) and via live execution of the actual production parser `scripts/clerk_ssot/parsers/gadsden.py:parse_tax_deed()`. **This is an evaluator-denominator-policy question, not a county-scraper gap — changing it is a fleet-wide decision explicitly out of scope for a single-county session.**

### hamilton C/D — CONFIRMED blocked, but diagnosis deepened one hop (survived=true after re-test)
4 residual cases (2024-CA-19, 2023-CA-41, 2021-CA-46, 2025-CA-37) still have no discoverable disposition. The workflow's adversarial refuter correctly flagged that prior sessions never tried `hamiltonclerk.com/court-search/` → Civitek OCRS (county 24), which is distinct from the already-exhausted `official-record-search/` → myfloridacounty.com party-only portal. I pursued this directly:
1. Scripted the PrimeFaces AJAX protocol (cookie jar + ViewState replay) through the "Public" access tier and disclaimer-acceptance steps — no CAPTCHA on either page.
2. Reached `civitekflorida.com/ocrs/app/search.xhtml` and confirmed it has a genuine **"Case Search" tab** distinct from the "Person Search" tab (name/DOB/SSN) that prior sessions found and gave up on.
3. `search.xhtml` renders a live **Cloudflare Turnstile widget** (sitekey `0x4AAAAAAAR0Af-5MfzdbO3p`). A scripted tab-switch AJAX POST without a solved Turnstile token threw a server-side exception (redirect to `/ocrs/errorpages/exception.xhtml`).

Per campaign guardrails, Turnstile/CAPTCHA bypass is out of bounds. This is now the precisely-mapped boundary: the Case Search tab (which almost certainly supports case-number lookup) exists and is one Turnstile solve away — future sessions should not re-walk the discovery path, only re-attempt if a sanctioned CAPTCHA-solving/human-in-loop channel becomes available. Also reconfirmed `floridapublicnotices.com` is a client-side SPA unreachable via WebFetch/WebSearch (not a Firecrawl-credits issue as previously assumed — Firecrawl is separately confirmed still exhausted at -13/1000 credits this session).

### holmes B/C/D/F — CONFIRMED still structurally blocked (survived=true)
Fresh spot-check of 2 of the 5 gap cases (TD#2023-185, TD#2023-496) against holmesclerk.com (both foreclosure and LOLA pages confirm no current listings, stamped 7/21/2026 and Feb 2026 respectively), civitekflorida.com/ocrs/county/30 (disclaimer only, Turnstile presumed to gate the search step exactly as Hamilton's does — did not proceed past disclaimer per guardrail), and 4 WebSearch queries per case. No new data. This reconfirms the 17th-session (`dispatch 3b7ed6ea`) verdict of `blocked_confirmed_dead_end` with fresh 2026-08-17 evidence. Zero PropertyOnion litmus rows exist for holmes.

## Infrastructure note
Hit a transient Supabase 521 (web server down) for ~90 seconds mid-session; recovered on retry. Not a data ceiling, noted for the record only.

## Audit trail
7 rows written to `gold_standard_ultraloop_audit` (ids 16357–16363), one per letter-claim, each with `survived=true` and refuter evidence. Session close-out written to `gold_standard_campaign` (id 4553): `exit_reason='blocked_confirmed_dead_end'`, accurate per-letter `criteria_passed` for all three counties.

## Recommendation for next session targeting this shard
Do not re-run standard discovery on any of these 7 letters without new source access. The only theoretical unblocks are: (1) a fleet-level decision on gadsden's redeemed-cert denominator policy (affects all counties with clerk-marked-redeemed tax deeds, not just gadsden), and (2) a sanctioned CAPTCHA-solving path for the two Civitek OCRS Turnstile gates (hamilton county 24, holmes county 30) — both are policy/tooling decisions above a single autonomous session's authority, not research gaps.
