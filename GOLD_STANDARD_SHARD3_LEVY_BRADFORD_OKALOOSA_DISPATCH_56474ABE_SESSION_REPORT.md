# Gold Standard Shard-3 — levy / bradford / okaloosa — dispatch 56474abe

Session: architect-20260831T080000, loop run 15658. ULTRALOOP fan-out via Workflow tool
(fix → verify → adversarial-verify, one isolated git worktree per county, 9 subagents total).

## Result summary (VERIFIED via 3 independent `pencil_dod_evaluate_county` calls this session:
Fix stage, Verify stage, adversarial Refuter stage, plus a 4th manual confirmation post-merge)

| County | Before | After | Delta |
|---|---|---|---|
| levy | 9/10 (I FAIL 77.8%, card_complete=35/45) | 9/10 (I FAIL **88.9%**, card_complete=**40**/45) | **+5 rows fixed**, still short of 95% threshold |
| okaloosa | 6/10 (C/D/E/I FAIL 92.9%, 79/85) | 6/10 (unchanged) | 0 — reconfirmed structural ceiling, no fabrication |
| bradford | 8/10 (B/F FAIL, null) | 8/10 (unchanged) | 0 — 15th consecutive recheck, reconfirmed structural block |

No regressions on any of the 24 non-target letters across the three counties (independently
re-verified letter-by-letter by the adversarial refuter for each county).

## levy — Criterion I (property card completeness)

**Root cause diagnosed live this session:** 10 of 45 rows failed I. 6 tax_deed rows
(2026-4176TD…4181TD, sale 2026-11-09) were missing `property_address` entirely; all 10 were
completely absent from `parcel_zones` (not merely `zone_code IS NULL` — the parcel rows didn't
exist there at all), despite Levy's zoning substrate otherwise being loaded (G passes 100%).

**Fixed (5 of 10), sourced from FL GIO cadastral API + Levy County's own public ArcGIS zoning
FeatureServer (`2025_08_07_ZON_FLU/FeatureServer/0`, dated 2025-08-07 — not previously documented
in any prior Levy session) + `online.levyclerk.com/TaxSmartWeb`:**
- 2026-4177TD, 2026-4178TD, 2026-4179TD, 2026-4180TD: address + geo + assessed value + zone (A/RR
  or RR) backfilled.
- 2026-4181TD: same, **plus** corrected a genuine scraper transcription error — the row carried
  parcel_id `1194600000`, which turned out to be a malformed version of a *different* parcel
  (`11946-000-00`, owner TERRIE L WOOTEN, cert 4814-22) than 2026-4180TD's real parcel
  (`11944-000-00`, owners WINSTON/DONNA LEWIS). The task brief's dedup hypothesis was checked and
  disproven — these are two distinct parcels/certificates.
- Added real `zoning_districts`/`zone_standards` rows for zone codes A/RR and RR, sourced from
  Levy's 2050 FLUE (May 2026 draft) and Ordinance 2014-02 (OR BK 1322 Pg 274) — not fabricated
  defaults.

**Left blocked (5 of 10), honest residual — do not re-attempt without a new lever:**
2026-4176TD, 2025000075CAAXMX, 2026-4164TD, 2026-4169TD, 2026-4170TD (Chiefland, Williston, Cedar
Key, Bronson x2). The county's own zoning layer returns a "Muni, ROW" placeholder polygon for
these — Levy County has no zoning authority inside its 7 incorporated municipalities, so the only
per-parcel source is `qpublic.net/fl/levy`, which is KYC/login-gated (confirmed still blocked via
brightdata this session). This is a structural finding, not a tooling gap.

**Caught and self-corrected mid-session:** the new zone_code links briefly regressed G to 88.4%
(new zones lacking zone_standards rows) before the fix agent backfilled zone_standards and
restored G to 100% prior to pushing — verified by the adversarial refuter as genuinely resolved,
not just claimed.

Commit: `1c2d2bf3` — `supabase/migrations/20260831_gold_standard_shard3_levy_i_10row_zoning_addr_fix.sql`

## okaloosa — Criteria C/D/E/I (unchanged, ceiling reconfirmed)

Same 6 rows drive all four letters (matched_clean/matched_any/parcel_linked/card_complete all
79/85). Two clusters, both re-verified fresh this session with two genuinely new levers tried —
**zero DB writes made**, correctly, because nothing survived as an honest confident match:

- **Cluster 1** (2024-CA-000470, 2024-TDD-000089): no address/parcel_id at all.
  `okaloosa.realforeclose.com`/`realtaxdeed.com` still 403. New lever tried: Okaloosa Clerk's
  ClerkQuest case search — page loads, but the search form is Cloudflare-Turnstile-gated; no
  hidden JSON API found. `browser-use` (which could solve Turnstile) is not installed and, per the
  bradford finding below, is not functional in this sandbox regardless.
- **Cluster 2** (2025-CA-002286-F/F3/F4/F5, a 4-way split of one case, sale 2026-09-02): legal
  descriptions only, no parcel_id. Independently queried Okaloosa's live ArcGIS parcel layer:
  "Delaware Plantations" (F, F4) — **zero matches, subdivision does not exist** in Okaloosa's
  cadastral system. "Summer Breeze" (F3) — zero matches among 713 "BREEZ*" hits; corroborates it
  being in Miramar Beach, **Walton County**. F5's own legal text says "WALTON COUNTY" explicitly —
  independently corroborated by querying Okaloosa's real PIN township/range values (only 1N-22 and
  2S-22 appear countywide; 3N-21 appears zero times). **2 of these 4 rows are very likely not
  Okaloosa parcels at all.** No county reassignment was made (out of this shard's scope; the
  adjudicating case docket is itself Cloudflare-gated).

Commit: `5999a1cc` (docs-only, zero table writes) —
`supabase/migrations/20260831_gold_standard_shard3_okaloosa_cdei_ceiling_reconfirm.sql`

## bradford — Criteria B/F (unchanged, 15th consecutive recheck)

Fresh drift check confirmed all 4 affected cases still `auction_status='upcoming'`,
`sold_amount=NULL`, identical to the 2026-08-30 baseline. Per dispatch instructions, none of the
13 already-exhausted dead levers were re-attempted.

**The one genuinely new lever:** the `browser-use` skill, unavailable to the prior 14 sessions
(their documented blocker for civitek OCRS, which is Turnstile-gated). This session: `npx
browser-use` resolved a real v0.8.0 tool, `doctor` passed 3/5 checks (Chrome present, network OK).
`browser-use open` against civitek's OCRS failed with `"fetch failed"` after 3 consecutive
step-failures — **never even reached the Turnstile challenge**. An isolating control test against
`https://example.com` (zero bot-protection) produced the *identical* failure, proving the break is
in browser-use's own LLM-provider wiring in this sandbox (no `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`
configured for it), not Cloudflare or network egress. civitek OCRS itself is confirmed reachable
by plain `curl` (HTTP 301, DNS resolves) — the tool, not the target, is the blocker.

Net: browser-use went from "not installed" to "installed but non-functional," which is new
information but does not open a path forward this session.

Commit: `93f58a59` (docs-only, zero table writes) —
`supabase/migrations/20260831_gold_standard_shard3_bradford_bf_15th_recheck_browseruse_attempted.sql`

## ULTRALOOP adversarial audit

7 rows written to `gold_standard_ultraloop_audit` (dispatch_id `56474abe-1017-44d0-a47f-969ffa88eeba`,
`ultraloop_mode='native'`): levy/I `survived=true`; okaloosa/{C,D,E,I} and bradford/{B,F} all
`survived=false` — correctly, since the adversarial claim under test was "did this letter
genuinely improve," and for those 6 it honestly did not (no fabrication was found in any case; the
refuter explicitly distinguished "honest non-improvement" from "refuted/fabricated claim").

## Close-out

`gold_standard_campaign` (id 5428, dispatch `56474abe-...`) updated: `criteria_passed` (per-county
A–J + score), `criteria_total=10`, `exit_reason='timeout'` (work queue exhausted for all 3
counties' currently-actionable levers, not a certification), `session_end_at` set.

## Next-session priorities for this shard's counties

1. **levy I**: only lever left is the qpublic.net/fl/levy KYC gate on 5 municipal-jurisdiction
   parcels. Needs either a login credential or a different per-parcel data source for Chiefland/
   Williston/Cedar Key/Bronson-jurisdiction parcels specifically (county GIS has no zoning data
   inside municipal boundaries by design).
2. **okaloosa C/D/E/I**: needs either (a) a working browser-automation tool that can actually solve
   Cloudflare Turnstile (browser-use is a dead end in this sandbox, confirmed twice now — bradford
   and okaloosa independently), or (b) resolution of the Walton County question for F3/F5 (would
   require either Walton's own GIS or manually confirming/reassigning county on those 2 rows), or
   (c) confirming F/F4's unrecorded-plat status makes them permanently unmatched by design.
3. **bradford B/F**: next real lever is bctelegraph.com's next legal-notices issue, expected
   ~2026-09-03 — do not recheck before then unless a sale genuinely closes per live DB drift check.
   Do not re-attempt browser-use again until its LLM-provider wiring is fixed at the sandbox level
   (out of scope for a per-session recheck).
