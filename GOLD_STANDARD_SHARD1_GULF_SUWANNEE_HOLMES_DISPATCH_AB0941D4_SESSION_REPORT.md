# GOLD STANDARD shard-1 (gulf, suwannee, holmes) — dispatch `ab0941d4-64a2-43a5-ac1a-1b88d98112ff`, loop run 7726

chat_session: `architect-20260731T160000`

## Result: zero drift on all 3 counties — exhaustive negative finding, no fabrication

```sql
SET statement_timeout = 0;
select public.pencil_dod_evaluate_county('gulf');
-- A pass(5) B pass(100.0) C pass(100.0) D pass(100.0) E pass(100.0) F pass(100.0)
-- G pass(100.0) H pass(23.9/23.6) I fail(85.7, "card_complete=12 of 14") J pass(100.0)
-- 9/10, auctions_total=14, IDENTICAL before and after

select public.pencil_dod_evaluate_county('suwannee');
-- A pass(4) B fail(null, "verified=0 closed_sold=0") C pass(100.0) D pass(100.0) E pass(100.0)
-- F fail(null, "tier1_sold=0 closed_sold=0") G pass(100.0) H pass(~0.1) I pass(100.0) J pass(100.0)
-- 8/10, auctions_total=14, IDENTICAL before and after

select public.pencil_dod_evaluate_county('holmes');
-- A pass(3) B fail(null) C fail(61.5, "matched_clean=8") D fail(61.5, "matched_any=8")
-- E pass(100.0) F fail(null) G pass(100.0) H pass(~7) I pass(100.0) J pass(100.0)
-- 6/10, auctions_total=13, IDENTICAL before and after
```

Live at session start matched the brief's snapshot exactly on all 30 A-J metrics across the 3 counties
(confirmed via fresh `pencil_dod_evaluate_county` queries before any research began).

## ULTRALOOP fan-out — mode: native, 3 parallel Discover agents + conditional Verify

Per the ULTRALOOP protocol (`docs/ULTRALOOP-SSOT.md`) and this session's ultracode opt-in, ran a Workflow
(persisted at `.claude/workflows/gold-standard-gulf-suwannee-holmes-ab0941d4.js`) fanning one research agent
per county's failing letter(s), each briefed on the exact leads already exhausted by 4-6 prior sessions per
letter and instructed to spend effort ONLY on genuinely new avenues, with live DB/web access and an explicit
instruction never to fabricate a write.

### gulf — letter I (card_complete=12 of 14, 85.7%, threshold 95%)

4th firing on this exact letter. Checked 4 new avenues live:
1. FL GIO statewide cadastral FeatureServer — confirmed no zoning field exists for either target parcel
   (`05762000R`, `05004050R`), only `DOR_UC="000"` (vacant use-code, not a zoning district).
2. `gulfcountypropertyappraiser.org` — confirmed to be an **unofficial** third-party WordPress marketing
   site (published Nov 2025), same dead-end category as previously-checked Zoneomics/Regrid. The real
   official site is `gulfpa.com`, Cloudflare-bot-gated (403). Its real backend, Schneider Corp's
   Beacon/qPublic (`beacon.schneidercorp.com` / `qpublic.schneidercorp.com`), is live and current
   ("last updated July 26, 2026") but also Cloudflare-challenge-gated — a genuinely new, plausible lead
   this session's tools (Firecrawl at `remaining_credits=-3`, no browser-use install) could not get past.
3. Live ArcGIS point-in-polygon query confirmed both target parcels sit inside the Port St Joe **municipal**
   polygon, not unincorporated Gulf County — so the FLU-spatial-intersect method already used for
   unincorporated-Gulf parcels structurally does not apply here.
4. Enumerated the full 60+-layer `arcgis5.roktech.net/gulf/GoMaps4/MapServer` layer list — confirmed no
   dedicated zoning-district layer exists.

**`found_new_lever=false`, CONFIRMED.** No fabricated zone_code proposed. Recommend a future firing once
Firecrawl credits reset or a browser-use/Cloudflare-passing tool is available, targeting Beacon/qPublic
specifically — this supersedes the prior "phone-call-only" conclusion with a more precise technical target.

### suwannee — letters B/F (closed_sold=0 for all 4 past-due cases)

Live authenticated Playwright session (reusing `scripts/suwannee_outcome_harvester.py`'s login flow) pulled
the **full item-detail text**, not just the DAYLIST status word, for tax-deed cases 4666 and 4667
(07/09/2026 auction date):

```
Auction Status: Redeemed
Auction Type: TAXDEED
Case #: 4666
Certificate #: 2023-2312
Opening Bid: $37,060.11
Parcel ID: 10591001000
```

Both cases are genuinely **Redeemed**, not Sold — resolving the 2026-07-25 harvester run's ambiguous "shows
sold" note (that was a misread of the results-grid segment). This also resolves a standing doubt from a
2026-07-20 session: 4666/4667 are the platform's internal case IDs, not fabricated identifiers — the
Clerk's real Certificate Numbers are 2023-2312 / 2023-2428 (matching the county's TD#YYYY-#### convention).

The 2 foreclosure cases (25-CA-197, 25-CA-170) are now past their sale dates but have no reachable
disposition source: `suwgov.org`'s Foreclosure Sale List docx was never refreshed post-sale-date (confirmed
via `Last-Modified` header), and `myfloridacounty.com` ORI search (county=61) is Cloudflare-Turnstile-gated
on the actual search POST (confirmed live, not forced past).

**`found_new_lever=false`, CONFIRMED.** No sold_amount fabricated. B/F correctly remain FAIL — this is
genuine county reality (redemption + no online disposition source), not a pipeline gap.

### holmes — letters B/C/D/F (5 rolled-off tax-deed cases: TD#2023-225/496/185/584, TD#2020-589)

Tried the one lead flagged repeatedly across 4 prior sessions as untried (blocked only by lack of a live
browser or Firecrawl credits, not confirmed dead): `myfloridacounty.com/orisearch/30` — live Playwright
submission for all 5 target owner names hit a Cloudflare Turnstile wall (sitekey
`0x4AAAAAAA64PTBePmuGbrkR`). Also discovered and tried a genuinely new lead not in any prior session: a
"SEARCH COURT RECORDS" link on `holmesclerk.com` itself, pointing to `civitekflorida.com/ocrs/county/30`
(Civitek Official Records Search) — reached a live search form but it is also Turnstile-gated (sitekey
`0x4AAAAAAAR0Af-5MfzdbO3p`), and its Case Search tab is structurally inapplicable to `TD#` identifiers even
if reachable (requires Year+CourtType+Sequence#, a circuit-civil schema, not a Clerk-administrative tax-deed
schema). `holmesclerk.com`'s tax-deeds page re-checked fresh: now shows "there are no sales scheduled at
this time" (changed since 2026-07-10), confirming the rolloff is permanent — still no disposition page.

**`found_new_lever=false`, CONFIRMED.** No writes made. B/C/D/F remain FAIL. Logged 4 fresh
`gold_standard_ultraloop_audit` rows (survived=true) carrying this session's new civitek-OCRS evidence, since
the prior holmes audit rows were 6 days old and approaching the 7-day certify-gate freshness window.

## Why no fix was shipped this firing

Zero of the 3 research streams surfaced a usable lever — all 3 hit either a confirmed-dead platform, a
structurally-absent disposition source, or a live Cloudflare Turnstile wall that was correctly not forced
past. Per HARD GUARDRAILS (no fabrication) and the Honesty Protocol (BLANK > WRONG), no DB write was made
to `multi_county_auctions`, `tax_deed_outcomes`, `foreclosure_outcomes`, or `bid_decisions` this session.
Since no positive claim was made, no Verify-phase refuter agents were needed (nothing to refute) — consistent
with the gulf 3rd-firing precedent of skipping Verify when Discover surfaces nothing new.

## Verification protocol followed

- Live `pencil_dod_evaluate_county` for all 3 counties queried at session start AND after research (VERIFIED
  identical both times, not assumed).
- 3-agent ULTRALOOP Discover fan-out, each with its own live DB/web verification, isolated context.
- `gold_standard_ultraloop_audit` checked for freshness on all 6 failing letters; gulf-I and suwannee-B/F
  already had same-day survived=true rows from an independent session; 4 fresh holmes rows added.
- Mandatory close-out `UPDATE gold_standard_campaign` applied live and re-selected to confirm the write.

### SQL VERIFICATION

```sql
-- Close-out record (applied via Supabase Management API, 2026-07-31T16:19:04Z UTC):
SELECT dispatch_id, target_counties, criteria_passed, exit_reason, session_end_at
FROM public.gold_standard_campaign
WHERE dispatch_id = 'ab0941d4-64a2-43a5-ac1a-1b88d98112ff';
-- {"dispatch_id":"ab0941d4-...","target_counties":["gulf","suwannee","holmes"],
--  "criteria_passed":{"gulf":{"A":true,...,"I":false,"J":true},
--                      "suwannee":{"A":true,"B":false,...,"F":false,...},
--                      "holmes":{"A":true,"B":false,"C":false,"D":false,...,"F":false,...}},
--  "exit_reason":"blocked_confirmed_dead_end","session_end_at":"2026-07-31 16:19:04.209319+00"}
```

Timestamp UTC: 2026-07-31T16:20Z.

---
dispatch_id: ab0941d4-64a2-43a5-ac1a-1b88d98112ff
