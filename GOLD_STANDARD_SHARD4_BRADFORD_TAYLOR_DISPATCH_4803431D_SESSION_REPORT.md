# Gold Standard SHARD-4: bradford / taylor

dispatch_id: `4803431d-9183-4636-9b30-31dfcb06e726`
chat_session: `architect-20260818T160000`
ultraloop_mode: `native` (Workflow tool fan-out: 3 research agents; 0 adversarial refuters needed — zero positive claims were produced)

## Summary

Ran the ULTRALOOP protocol against the shard's only failing letters: bradford B/F, taylor B/C/F. This is an
**honest zero-movement session**: no letter flipped, no DB writes were made, and no fabricated data entered the
pipeline. Every claim below carries a live confidence label and cited evidence.

- **bradford B/F**: per the county's standing note in `pipeline.counties.notes` ("An 8th session should skip
  straight to still-blocked... unless a human-outreach flag has been set" — no such flag exists), this session
  did **not** repeat the exhausted lever list (bradfordclerk.com Cloudflare 403, Civitek OCRS, myfloridacounty
  ORI Turnstile, Box.com). Instead it ran a single lightweight freshness ping: Cloudflare posture unchanged
  (still `cf-mitigated: challenge`), and a fresh WebSearch/WebFetch pass over the 3 open past-due cases found
  nothing new beyond a BC Telegraph pre-sale notice reprint already known. This is now the **11th+ confirmed
  reconfirm** of the same ceiling; no further autonomous lever exists short of the human-outreach escalation
  flagged in prior sessions.
- **taylor B/F**: the one genuinely untried lever this cycle — `taylor.realtdm.com` (the county's tax-deed
  platform, never checked in any prior session for cases TDA 26-026/26-028) — was investigated with real
  Playwright browser automation, not just curl. Finding: `taylor.realtdm.com` self-identifies as a **TEST
  instance** ("realTDM : TEST - Case Search" / "Test Clerk", vs. `lee.realtdm.com`'s correctly-branded "realTDM
  : Lee" used as a control), and a brute-force scan of case IDs 1–2000 (step 25) plus a coarse scan to 90000 via
  the direct `/public/cases/getCase/caseid/<N>` pattern (verified working against real data on
  `lee.realtdm.com`, caseid 69470 = confirmed SOLD) found **zero existing case records on the Taylor instance**.
  taylorclerk.com's own live tax-deed JSON feed only carries TDA 26-031/26-032 (both `redeemed`, Aug 17 sale) —
  TDA 26-026/028 have already rolled off with no outcome recorded. Perry Newspapers' weekly legal-notice archive
  confirms both cases existed (applicant FIG 20 LLC, certs #1118/#949, July 20 2026 11am sale) but only
  publishes pre-sale notices, never results. Genuinely blocked, not a repeat of prior evidence.
- **taylor C**: confirmed the 90.9% (10/11) result is a **correct structural ceiling, not a bug** — the one
  non-matching row (case 25-014 CA, `CLERK_SSOT_CANCELLED`) is legitimately cancelled per live
  taylorclerk.com re-check today, and this repo has an explicit precedent
  (`supabase/migrations/20260812_shard1_calhoun_c_diagnose_d_ssot_cancelled_fix.sql`) rejecting relabeling a
  genuinely-cancelled case into `matched_clean` as fabrication. No forced fix attempted.

**No county moved this session.** bradford remains 8/10 (B, F failing). taylor remains 7/10 (B, C, F failing).

## Before / After (live `pencil_dod_evaluate_county`, identical — zero DB writes made)

### bradford (8/10 PASS, unchanged)
| Letter | Before | After | Note |
|---|---|---|---|
| B | FAIL null (verified=0 closed_sold=0) | FAIL null (unchanged) | Reconfirmed BLOCKED — Cloudflare 403 unchanged, no new public mention for the 3 open cases |
| F | FAIL null (tier1_sold=0 closed_sold=0) | FAIL null (unchanged) | Same root cause as B |
| A, C–E, G–J | PASS | PASS (unchanged) | |

### taylor (7/10 PASS, unchanged)
| Letter | Before | After | Note |
|---|---|---|---|
| B | FAIL null (verified=0 closed_sold=0) | FAIL null (unchanged) | New lever (realtdm.com) exhausted — TEST instance, zero real case data; taylorclerk.com feed and Perry Newspapers checked, pre-sale-only |
| C | FAIL 90.9 (matched_clean=10) | FAIL 90.9 (unchanged, correctly) | Confirmed structural ceiling — case 25-014 CA is a genuine cancellation, relabeling would be fabrication per calhoun precedent |
| F | FAIL null (tier1_sold=0 closed_sold=0) | FAIL null (unchanged) | Same root cause as B |
| A, D, E, G–J | PASS | PASS (unchanged) | |

## Research detail (ULTRALOOP fan-out, 3 agents, 94 tool calls, 242.5K tokens)

1. **taylor_realtdm_taxdeed** (TDA 26-026, TDA 26-028): Playwright-driven real form submission on
   `taylor.realtdm.com/public/cases/List` (parcel search R09208-000 / R07503-000, wildcard case search) →
   "NO CASES FOUND". Control test against `lee.realtdm.com` (known-real production instance) confirmed the
   direct-caseid-URL technique works on real data, then the same technique brute-force-scanned Taylor's instance
   with zero hits — the instance is a test/staging deployment with no live case data. taylorclerk.com live feed
   and 3 weeks of Perry Newspapers legal notices checked; pre-sale notices only, no outcomes. Confidence: UNTESTED
   (no positive claim — genuinely could not locate outcome data).
2. **taylor_c_structural_check** (case 25-014 CA): live-fetched taylorclerk.com foreclosure-sales page today,
   confirmed absence (consistent with real cancellation); no alternate independent source shows a clean match.
   Confidence: VERIFIED — structural ceiling holds.
3. **bradford_bf_lightweight_recheck** (3 open cases): single Cloudflare HEAD check + WebSearch/WebFetch pass,
   per the standing no-re-derive instruction. No new information. Confidence: VERIFIED — still blocked.

Zero positive findings were produced, so the Verify phase (adversarial refuters) had nothing to check — this is
by design: a workflow that finds nothing does not manufacture something to verify.

## Close-out

```sql
UPDATE public.gold_standard_campaign
SET criteria_passed = '{"bradford":{"A":true,"B":false,"C":true,"D":true,"E":true,"F":false,"G":true,"H":true,"I":true,"J":true},
                         "taylor":{"A":true,"B":false,"C":false,"D":true,"E":true,"F":false,"G":true,"H":true,"I":true,"J":true}}'::jsonb,
    criteria_total = 10, exit_reason = 'timeout', session_end_at = now()
WHERE dispatch_id = '4803431d-9183-4636-9b30-31dfcb06e726';
-- applied live 2026-08-18T16:53:41Z, row id 4621
```

Both letters on both counties remain genuine data ceilings this cycle. bradford B/F needs the human-outreach
escalation already flagged in dispatch 41bd7ce3's notes (phone/records-request to the Clerk or a surplus-funds
attorney of record — outside autonomous scope). taylor B/F has now exhausted every known online source
(clerk WP site, RealTDM, Perry Newspapers, Wayback Machine) and likely needs the same escalation. taylor C is
correctly capped by a real cancellation and should not be targeted again absent a genuinely new lever.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
