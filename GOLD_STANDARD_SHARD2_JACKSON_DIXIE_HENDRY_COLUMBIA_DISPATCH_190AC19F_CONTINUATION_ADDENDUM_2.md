# Gold Standard shard-2 continuation addendum #2: jackson / dixie / hendry / columbia

dispatch_id: 190ac19f-8ae0-465c-be8b-ec314028eb77
chat_session: architect-20260719T160000 (3rd firing of this dispatch; the 2nd firing's next-session-priorities
list picked up directly)
mode: ultracode — one Workflow (3 investigate agents + 3 adversarial-verify agents, 6 agents total, 183 tool
uses) fanned out over columbia I, columbia A/B/F, and a minimal dixie C/D recheck; civitek CAPTCHA
reconnaissance done directly by the orchestrator first (Playwright) before scoping the workflow.

## Status Board (before this addendum -> after, live `pencil_dod_evaluate_county`)

| County | Before | After | Delta |
|---|---|---|---|
| jackson | 10/10 | 10/10 | unchanged, re-verified live only |
| dixie | 8/10 (C/D fail, 75.8%) | 8/10 (C/D fail, 75.8%) | unchanged — minimal recheck, still genuinely blocked |
| hendry | 10/10 | 10/10 | unchanged, re-verified live only |
| columbia | 6/10 (A/B/F/I fail) | 6/10 (A/B/F/I fail) | unchanged — 2 new leads fully investigated and exhausted for I; A/B/F's blocking mechanism was newly root-caused (genuine Cloudflare Turnstile CAPTCHA, not a tooling gap as the prior addendum's fixer wrongly claimed) |

### SQL VERIFICATION (fresh, this session, 2026-07-19 ~19:15-19:50 UTC)

```
POST /rest/v1/rpc/pencil_dod_evaluate_county {"p_county":"jackson"}
 -> A15 B100 C98.4 D98.4 E95.3 F100 G100 H7.3 I95.3 J100  (10/10, auctions_total=64)

POST .../rpc/pencil_dod_evaluate_county {"p_county":"dixie"}
 -> A2 B100 C75.8(FAIL) D75.8(FAIL) E100 F100 G100 H3.3 I97 J100  (8/10, auctions_total=33)

POST .../rpc/pencil_dod_evaluate_county {"p_county":"hendry"}
 -> A3 B100 C100 D100 E100 F100 G100 H3.3 I100 J100  (10/10, auctions_total=20)

POST .../rpc/pencil_dod_evaluate_county {"p_county":"columbia"}
 -> A0(FAIL) B null(FAIL) C100 D100 E100 F null(FAIL) G100 H3.1 I93.3(FAIL) J100  (6/10, auctions_total=15)
```

Note: same DB-access constraint as every prior session in this dispatch — direct `psql` auth fails against
both the pooler and direct host (`FATAL: password authentication failed`); all reads/writes went through
PostgREST with the service-role key. No schema changes attempted or needed.

Note on the task brief's numbers: the dispatch brief quoted at session start showed jackson 10/10, dixie
8/10, **hendry 7/10** (B/F/G failing), columbia 5/10. Live re-verification at session start showed hendry was
already 10/10 and columbia was 6/10 — both match the *2nd firing's* addendum exactly, confirming the task
brief was a stale snapshot from before that firing's work landed, not a regression. Reporting the live numbers
here rather than the stale brief, per Honesty Protocol (verify fresh, don't trust a snapshot).

## columbia A/B/F — root cause finally identified: genuine Cloudflare Turnstile CAPTCHA, not missing tooling

The 2nd firing's addendum flagged that its fixer wrongly claimed civitekflorida.com required a browser that
"wasn't installed," and that the refuter had caught the tooling claim as false (Playwright IS installed) but
couldn't say whether the *site itself* was actually usable. This firing drove `civitekflorida.com/ocrs/county/12`
directly with Playwright (not delegated) to settle it:

- Reached the real Case Search and Person Search forms (disclaimer → "I Agree" → tab navigation all work fine).
- Filled a real search (Year=2025, Court Type=Circuit Civil (CA), Sequence#=396 — case 2025-396-CA) and, on
  attempting to submit, the form re-rendered with a **Cloudflare Turnstile "Verify you are human" checkbox
  widget** (screenshot captured, `/tmp/before_search.png`) that must be checked before the search executes.
  The same widget appears on the Person Search tab after filling a last name and clicking Search.
- **This is a genuine, verified blocker — not a tooling gap.** Per HARD PROHIBITIONS on evading anti-automation
  protections, this session did not attempt to solve or bypass the Turnstile challenge. Confirmed the same
  Turnstile mechanism independently gates `myfloridacounty.com/orisearch/12` (has the `CERT TITLE` doctype we
  need) on actual search submission — exact sitekey `0x4AAAAAAA64PTBePmuGbrkR` reproduced twice (investigating
  agent + adversarial verifier, independently).
- `columbiaclerk.com` is now also fully HTTP 403 site-wide (`cf-mitigated: challenge` header) — a different,
  network-layer Cloudflare block, not a solvable widget, but the practical effect is identical: no content.

One new, non-blocked source was found and tested: `search.ccpafl.com` (Columbia County Property Appraiser).
Proven capable of surfacing historical Certificates of Title (2 independently-verified historical examples,
exact date/grantor/grantee/dollar-amount matches on both), but shows **no 2026 ownership transfer yet** for
any of the 4 columbia cases whose auction_date has already passed (2023-492-CA, 2025-103-CA, 2025-396-CA,
2025-499-CA). Honestly flagged as **inconclusive**, not a confirmed no-sale — Florida appraiser tax rolls
commonly lag deed recording by weeks to months, so a negative result 4–18 days post-auction proves nothing
either way. No outcome was written to `foreclosure_outcomes`.

**One misdirected lead corrected:** the investigating agent flagged `columbia.floridatax.us` (same platform
family as `dixie.floridatax.us`, which worked for dixie's tax-deed C/D problem) as a promising next step. On
inspection this is a **wrong analogy** — columbia's A metric shows `fc=15 td=0`: all 15 columbia cases are
**foreclosures**, not tax deeds. The tax collector's certificate-sale data (delinquent property tax liens)
has no bearing on judicial foreclosure sale outcomes. Flagging this explicitly so a future session does not
re-spend time chasing it.

## columbia I — 2 new sources for Fort White zoning (parcel 04023-000), both genuine dead ends, still 93.3%

1. **`fortwhitefl.com/media/1956`** — Fort White is a real incorporated FL town (est. 1884) with its own Land
   Development Code (Ordinance 174-2013) and an "Official Zoning Map" — downloaded and rendered: a genuine
   1-page vector PDF, 7 real zone-code colors (A/CG/CN/DD/I/RSF-1/RSF-2), not a placeholder. **But it has no
   embedded georeferencing, street labels, or parcel-ID labels** — a static cartographic export, not a
   queryable GIS layer. Cannot programmatically derive the zone for Amiel Ct from this file alone.
2. **`search.ccpafl.com/parcel/04023000166S33`** — the Columbia County Assessor's own live parcel record for
   this exact parcel. Confirms Tax District = `4: CITY OF FORT WHITE` (so Fort White's LDC, not county
   unincorporated zoning, is the correct legal authority — rules out chasing the county's own zoning atlas,
   which only covers unincorporated land). But the page's own "Zone" field is **empty** for this parcel —
   and independently confirmed empty on neighbor parcel 04035-000 too, proving this is a systemic gap in the
   county's own data feed, not a fetch error specific to our parcel.

No `zone_code` was fabricated. Both new sources were independently re-fetched and byte/field-matched by the
adversarial verifier — every claim SURVIVES. Remaining path (both genuinely non-automatable): manually
cross-reference the (non-georeferenced) zoning map against a labeled street map of the Fort White town core,
or call Fort White Town Hall / Planning & Development, (386) 497-2321 — the Town's own site states the
authoritative map is "located in the Town Hall."

## dixie C/D — minimal recheck only, per instructions not to re-attempt exhausted automated sources

Two quick checks: `dixietax.com` reconfirmed Cloudflare-blocked (403, Turnstile "Just a moment..." page,
byte-identical failure mode to before). `official.myfloridacounty.com` returned **NXDOMAIN** in this session
— a different failure mode than the previously-documented Turnstile gate. The adversarial verifier went
further than the investigating agent and independently confirmed via 2 external public DNS resolvers
(8.8.8.8, 1.1.1.1) that this is a genuine NXDOMAIN, not a sandbox-local DNS artifact — but that still means
the *specific* Turnstile-gate evidence could not be freshly reconfirmed today for that one host. Reported
honestly as UNTESTED/INFERRED for that sub-claim rather than forced to match. **Net: no change** — dixietax.com
alone already confirms the primary automated path remains closed. Only remaining lead: manual phone/in-person
records request (Dixie Clerk 352-498-1200 or Tax Collector 352-498-1213), non-automatable, out of scope.

## jackson / hendry — untouched, re-verified live only

Both confirmed 10/10 via fresh `pencil_dod_evaluate_county` calls at session start and end (identical). No
work performed. jackson's B/F/G audit-freshness fix from the 2nd firing (commit `84cc166f`, refreshed earlier
today) remains within the 7-day certify-gate window — no action needed this firing.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| columbia A/B/F, civitek Case Search | drive with Playwright per prior next-session-priority #1 | Root-caused to a genuine Cloudflare Turnstile CAPTCHA (screenshot evidence), confirming the site is real-but-blocked, not a tooling gap. Not bypassed (off-limits). Also found myfloridacounty.com ORI is Turnstile-gated the same way, and that columbiaclerk.com is now site-wide 403'd | none — matches next-session-priority #1 exactly, with a more precise root cause than "untried" |
| columbia I, Fort White zoning | apply any new data surfaced via civitek or another source | civitek was a dead end (blocked); found 2 different new sources instead (Fort White's own zoning map PDF, county assessor parcel page) — both real, both confirm the same structural gap (non-georeferenced map + empty appraiser Zone field) rather than yielding a usable zone_code | none on the metric — still 93.3%, genuinely blocked, now with 2 additional independently-verified dead ends closed off |
| dixie C/D | only remaining lead is manual phone/in-person | did the minimal recheck as instructed, no new automated attempt | none — as planned |

## Verification Evidence

3 new rows inserted to `gold_standard_ultraloop_audit` this firing (dispatch_id `190ac19f-8ae0-465c-be8b-ec314028eb77`,
`ultraloop_mode='native'`): columbia I (id 7342), columbia A (id 7343, covers A/B/F jointly), dixie C (id 7344,
covers C/D jointly) — all `survived=true`. Every claim was independently re-derived by a separate adversarial
agent that re-fetched the load-bearing URLs itself (exact Turnstile sitekey reproduced twice, exact historical
CT dollar amounts reproduced, exact empty-Zone-field HTML reproduced on 2 parcels, exact NXDOMAIN reproduced
via 2 external resolvers) — not just re-summarized. No PropertyOnion-sourced or `*promote*`-tagged outcome
rows written anywhere. No fabricated `zone_code` or outcome. No CAPTCHA was solved or bypassed. Cron jobs
109/111/115 and `gold-standard-loop-*` untouched. `gold_standard_loop()`/`gold_standard_certify()` NOT run
(parallel-fleet protocol — other shards' interleaved activity expected in `git log`). Migration:
`supabase/migrations/20260719d_shard2_3rd_firing_columbia_dixie_investigation_no_metric_change.sql`
(documentation-only, zero schema/DML changes to production data tables beyond the 3 audit rows above, which
were inserted directly via PostgREST as in every prior session of this dispatch).

## Next-session priorities

1. **columbia A/B/F, now genuinely exhausted for automated leads**: every direct-search path that could
   return a foreclosure sale outcome (civitek, myfloridacounty ORI, columbiaclerk.com's own record-search
   link) converges on the same Cloudflare Turnstile/bot-mitigation backend. No further automated attempt
   should be made without a genuinely new, distinct source. The `search.ccpafl.com` appraiser-roll check is
   real but lag-prone — worth a periodic re-check (not urgent) on the 4 already-past-date cases as more time
   passes, since a roll update would be unambiguous positive evidence.
2. **columbia I**: only non-automatable paths remain (manual map cross-reference or a call to Fort White Town
   Hall, (386) 497-2321). Not worth further automated session time.
3. **dixie C/D**: unchanged — manual phone/in-person only (Dixie Clerk 352-498-1200 / Tax Collector
   352-498-1213). Do not re-attempt automated sources without a genuinely new lead.
4. **Do NOT chase `columbia.floridatax.us`** as a columbia A/B/F lead — it's a tax-collector portal for
   delinquent-tax certificates, and columbia's 15 tracked cases are 100% foreclosures (`fc=15 td=0`), not
   tax deeds. The dixie-shaped analogy doesn't transfer; flagged here so it isn't re-tried.
5. **jackson, process-level** (carried over, unchanged from 2nd firing): the certify gate's 7-day rolling
   freshness requirement means passing letters can silently decertify if nobody re-touches their audit trail.
   Still worth flagging to the AI Architect as a process question, not something to build unprompted.
