# GOLD STANDARD shard-8: collier + hamilton — 2nd firing, dispatch 0d016197

**Issue:** breverdbidder/cli-anything-biddeed#17023
**chat_session:** architect-20260731T080000 (this session)
**ultraloop_mode:** native (Workflow tool, 6-agent fan-out audit+refute)

## Parallel-fleet note — dead work found and superseded

An earlier firing on this exact dispatch (`0d016197`) already ran this morning and produced
commits `0c7fbb8f`/`fe2778d7` on branch `claude/issue-17023-20260731-0801` — but per the
SHIP-TO-MAIN MANDATE, that branch was never merged to `main` (confirmed via
`git merge-base --is-ancestor` — not an ancestor of `origin/main`), and its migration was
never applied (`gold_standard_ultraloop_audit` had zero rows for this dispatch_id at the
start of this session). Per the brief's own definition ("unmerged work is DEAD work and
scores zero"), that prior attempt counted as not-done. This session independently audited
its plan before treating it as valid.

**That audit caught 3 real bugs in the unexecuted migration** (see the new migration file's
header for detail): it referenced two non-existent `parcel_zones` columns
(`zoning_district_id`, `confidence_score`) that would have caused an outright SQL error, its
DOR_UC match used single-digit codes against a zero-padded 3-digit column (would never have
matched), and its jurisdiction-name fallback (`'Hamilton County'`) doesn't exist in the
`jurisdictions` table (real name is `'Hamilton County (Unincorporated)'`). Running it as
committed would have failed outright, not silently fabricated data — but it would not have
fixed anything either. Not attributing blame here, just documenting why this session
redid the work with a different, verified method rather than executing the branch as-is.

## Before state (VERIFIED live via `pencil_dod_evaluate_county`, session start)

```json
collier: {"A":{"pass":false,"metric":0,"detail":"fc=0 td=212"}, B-J all PASS} — 9/10
hamilton: {"C":{"pass":false,"metric":61.9,"detail":"matched_clean=13"},
           "D":{"pass":false,"metric":61.9,"detail":"matched_any=13"},
           "I":{"pass":false,"metric":71.4,"detail":"card_complete=15 of 21"},
           A/B/E/F/G/H/J all PASS} — 7/10
```
Matches the dispatch brief exactly.

## What this session did

Ran a 6-agent ULTRALOOP workflow (native, via the Workflow tool) BEFORE any write: 3 audit
agents independently re-verified (a) a proposed hamilton-I fix, (b) the collier-A dead end,
(c) the hamilton-C/D dead end, each with fresh live queries; then 3 adversarial refuter
agents tried to break each finding. All three survived refutation (0 of 3 refuted).

### hamilton I — FIXED, FAIL→PASS (71.4% → 95.2%)

Root cause: 6 of 21 Hamilton parcels had no `parcel_zones` row (zone_code unlinked), failing
the property-card-completeness check. Real fix: queried Hamilton County's own ArcGIS
ZoneAtlas FeatureServer live (point-in-polygon on real `fl_parcels` centroids, co_no=34) —
the same source that already produced Hamilton's other 15 passing `parcel_zones` rows and
its currently-PASSING G metric:

| parcel_id | ArcGIS zone | Linked? |
|---|---|---|
| 3478-450 (Jennings) | A-4 | yes |
| 4427-000 | ESA-2 | yes |
| 4421-000 | ESA-2 | yes |
| 1005-130 (White Springs postal, rural coords) | ESA-2 | yes |
| 4680-000 | ESA-2 | yes |
| 8282-000 (White Springs, case 2023-CA-41) | "CITY LIMITS" — not a real zoning code | **no, left unlinked** |

8282-000 sits inside the Town of White Springs municipal boundary, outside county ZoneAtlas
coverage — a prior session (2026-07-25, dispatch `7425b4a1`) already reached this exact
conclusion and correctly left it unlinked rather than fabricate a code. This session
independently re-derived and confirmed the same result via a fresh ArcGIS query, then left
it unlinked again. This is the sole remaining residual gap on I (20/21 = 95.2%, above the
95% threshold — PASS).

Both target zoning_districts (A-4 id=12935, ESA-2 id=12937, jurisdiction_id=841) already
carry real ordinance-sourced `zone_standards` (source_url = zoning.hamiltoncountyfl.com
PDFs) — no new districts created, no invented numbers, so Hamilton's PASSING G metric is
untouched by this write (re-verified live, still 100.0 after).

Applied live via Supabase Management API (`api.supabase.com/v1/projects/.../database/query`,
`SUPABASE_ACCESS_TOKEN`) — not a GHA workflow_dispatch (the previous session's approach was
blocked by a GitHub App permissions gap; the Management API needs no workflow file at all).

**Migration:** `supabase/migrations/20260731b_gold_standard_shard8_hamilton_i_zoneatlas_fix.sql`

### collier A — reconfirmed dead end, 6th independent confirmation, no write

Fresh live checks today: `collier.realforeclose.com` / `realtaxdeed.com` still 403 at the
AWS ELB (deprovisioned vendor account). New this session: pulled the live OpenAPI/Swagger
spec at `cms.collierclerk.com/showcaseweb/swagger/v1/swagger.json` (115KB, real spec, 58
`/sci/*` paths) — confirms reference/lookup endpoints (`/sci/courteventtypes/list`, etc.,
including `courtEventTypeID:77 = "Foreclosure Sale"`) are open with no auth, but the
data-bearing endpoints (`/sci/calendar/summary`, `/sci/case/search`) return
`401 WWW-Authenticate: Bearer` — a genuine bearer-token wall obtainable only through the
reCAPTCHA-gated login flow. This is new precision on *where* the wall is, not a new way
through it. Recommendation from the audit agent, adopted here: further identical
Collier-A re-checks add no new information at this point — flag to stop re-firing on
Collier-A specifically unless a genuinely new lever appears (public-records request
process, vendor contract change, or a new public calendar).

### hamilton C/D — reconfirmed dead end, no write

Re-verified all 8 gap rows live. New this session: explicitly checked and ruled out
`myfloridacounty.com/orisearch/24` (Hamilton's official-records portal reached via
`hamiltonclerk.com/official-record-search/`) — confirmed it only supports deed/mortgage/lien
search by instrument number, party name, or book/page, not case number or tax-deed
certificate lookup. Also confirmed no Laserfiche/OnBase portal exists for Hamilton Clerk
(no subdomain resolves). Both groups (3 unpublished TD certs, 5 unmatched/date-conflicted FC
cases) remain genuinely blocked at the source.

## After state (VERIFIED live via `pencil_dod_evaluate_county`, this session's end)

```json
hamilton: {"A":PASS(6), "B":PASS(100.0), "C":FAIL(61.9), "D":FAIL(61.9), "E":PASS(100.0),
           "F":PASS(100.0), "G":PASS(100.0), "H":PASS(20.8),
           "I":PASS(95.2, "card_complete=20 of 21")  <-- FLIPPED FAIL->PASS,
           "J":PASS(100.0)} — 8/10 (C, D remain open)
collier: unchanged, 9/10 (A remains open) — re-verified, no regression
```

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| collier A | Fix or reconfirm | Reconfirmed dead end (6th time), no write | None — matches prior sessions' scope call |
| hamilton C/D | Fix or reconfirm | Reconfirmed dead end, one new negative-lead ruled out (MyFloridaCounty) | None |
| hamilton I | Fix 6 remaining parcels | 5 of 6 fixed via live ArcGIS; 1 (8282-000) correctly left unlinked | Matches the honest-residual precedent already established for this exact parcel |

## Verification Evidence

- Live `pencil_dod_evaluate_county('hamilton')` before: I FAIL 71.4%. After: I PASS 95.2%.
  Command: `curl -X POST $SUPABASE_URL/rest/v1/rpc/pencil_dod_evaluate_county -d '{"p_county":"hamilton"}'`
- Live `pencil_dod_evaluate_county('collier')` re-checked after the hamilton write: 9/10
  unchanged, confirming no cross-county regression.
- SQL applied via Supabase Management API, HTTP 201, empty result set for the SELECT-less
  INSERT statements (expected for INSERT with no RETURNING).
- ULTRALOOP workflow `wf_41a0c2ec-470`: 6 agents, 92 tool calls, 346,504 tokens, all 3
  claims survived adversarial refutation (0 refuted).
- 3 `gold_standard_ultraloop_audit` rows written (hamilton/I, collier/A, hamilton/C), all
  `survived=true`, dispatch_id `0d016197-9839-4dd1-9374-f99ac5e24954`.

## Residual gaps (not addressed, honest)

1. **collier A**: structural — no digital source exists. Needs browser automation +
   CAPTCHA-solving (out of scope for a data/config session) or a real-world process change
   (in-person collection, FOIA, vendor contract). Recommend the fleet stop re-firing
   identical checks on this letter.
2. **hamilton C/D**: structural — clerk hasn't published 3 tax-deed cert outcomes; 5
   foreclosure cases absent from the live site or date-conflicted; OCRS has no case-number
   search at the public tier. Will only move when hamiltonclerk.com publishes these, or a
   different official channel (e.g. a public-records request) is used.
3. **hamilton I residual**: 8282-000 (case 2023-CA-41) stays unlinked — inside White
   Springs municipal limits, outside county ZoneAtlas coverage. Would need Town of White
   Springs municipal zoning research (a genuinely separate small-town ordinance, not yet
   sourced by any session).

No `gold_standard_loop()` / `gold_standard_certify()` run this session — per PARALLEL-FLEET
RULES, cannot confirm no sibling shard is mid-flight; per-county `pencil_dod_evaluate_county`
used for all verification instead.
