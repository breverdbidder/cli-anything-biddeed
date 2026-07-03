# SHARD-14 Session Report — loop run 2753 (2nd dispatch, same run label)

dispatch_id: `84da506f-e01d-444f-8e53-2f9304c29599`
chat_session: `architect-20260703T160000`
shard counties: hendry, santa_rosa, alachua, liberty
ultraloop_mode: **native** (Workflow tool — 1 adversarial refuter; verdict `survived=true` x2, logged as C and D rows)

## Duplicate-dispatch finding (read first)

This exact brief — same `dispatch_id`, same `chat_session` — was **already fully executed** in a prior session and committed to main: `SHARD14_RUN2753_SESSION_REPORT.md` (commit `d442d27d`). Live DB verification at the start of this session (`pencil_dod_evaluate_county` for all 4 counties) returned numbers **identical** to that report's "After" state — confirming no other work had touched these counties since, and that this dispatch is a replay, not new work.

Rather than fabricate redundant "progress" or silently re-do the same investigation, this session read the prior report's **deferred/flagged item** — the one concrete, unexecuted lever it had identified but not run — and executed it for real:

> "santa_rosa C/D: needs the existing AJAX `realforeclose_aids` harvest mechanism run against `santarosa.realtaxdeed.com` (not `.realforeclose.com`, which is already fully harvested) — same code path, different subdomain, ~14 real tax-deed rows would land."

## Result summary

| County | Before | After | Change |
|---|---|---|---|
| **santa_rosa** | 8/10 (C 69.8%, D 69.8% fail) | **8/10, C/D 92.1%** (still fail — 95% threshold — but real, verified gain) | **C: 69.8%→92.1%, D: 69.8%→92.1%** (matched_clean/matched_any: 44→58 of 63). Live AJAX harvest of `santarosa.realtaxdeed.com`, 14 real tax-deed cases matched via existing `refresh_shard2_cd_tier1_v1()` matcher. |
| hendry | 8/10 (C, D fail) | 8/10 (C, D fail) | No change — re-confirmed live, matches prior session's structural-blocker finding exactly (only 1 of 19 hendry auctions has an independent outcome record). No new lever found. |
| alachua | 6/10 (C, D, E, I fail) | 6/10 (C, D, E, I fail) | No change — re-confirmed live, matches prior session's finding (6 remaining NULL-parcel_id rows have no usable identifying data). No new lever found. |
| liberty | 3/10 (E, H, J) | 3/10 (E, H, J) | No change — E fix already shipped by the prior session (`dc7cd372`), re-confirmed live. G/I remain genuinely blocked (needs real ordinance-sourced zoning data, not fabrication). |

## What shipped

1. **santa_rosa C/D real gain** (no migration needed — reused existing infra, zero new code):
   - Ran `scripts/shard2_run2450_ajax_realforeclose_harvest.py` live against `santarosa.realtaxdeed.com` for auction dates `07/13/2026`, `07/27/2026`, `08/03/2026` (the 3 dates covering all 14 unmatched real santa_rosa tax-deed case numbers). The script was already fully parameterized for this (`platform_domain` arg) from a prior shard's work — confirmed via direct code read, no edits made.
   - Result: 20 AITEM blocks parsed, 20 upserted into `realforeclose_aids` (`county_slug='santa_rosa'`, `auction_type='TAXDEED'`) — 14 targeted + 6 harmless surplus (future cases not yet in `multi_county_auctions`).
   - Invoked existing `public.refresh_shard2_cd_tier1_v1()` matcher (no changes) — reported `santa_rosa_realforeclose_aids_match rows_affected=14`.
   - Live re-check: `pencil_dod_evaluate_county('santa_rosa')` — C/D moved from 69.8% (44/63) to 92.1% (58/63).

2. **Wiring fix** (`.github/workflows/shard2-ajax-realforeclose-harvest.yml`, new file): the harvester script had **zero** scheduled executor anywhere in the repo — it was a pure manual/one-off script from a prior shard. Per the WIRING MANDATE, added a daily (09:30Z) GHA workflow that dynamically queries `multi_county_auctions` for unmatched pinellas/santa_rosa auction dates, re-runs the harvester for both `realforeclose.com` and `realtaxdeed.com`, then re-invokes the matcher — so this gain stays current as new tax-deed cases get listed, without requiring another manual session to rediscover this lever.

3. **Not done, deliberately:** the 5 remaining unmatched santa_rosa rows are known-synthetic seed data (`SANTA-ROSA-FC/TD-2026-00X`, fake case numbers). The prior session flagged these "for Ariel to purge" — this session did **not** delete them (destructive action on production data, explicitly deferred to Ariel per the prior report's own framing, not something to auto-execute). This is why C/D still reads FAIL at 92.1% rather than 100% — the remaining gap is fully accounted for and requires a human decision, not more scraping.

## Verification evidence (live, pasted verbatim)

### SQL VERIFICATION
```
SELECT public.pencil_dod_evaluate_county('santa_rosa');
```
Timestamp: 2026-07-03T17:4x:xxZ (via PostgREST RPC — direct psql pooler auth fails in this sandbox, same constraint documented by every prior shard session today)

**Before:**
```json
{"A":{"pass":true,"metric":16,"detail":"fc=47 td=16"},"B":{"pass":true,"metric":100.0,"detail":"verified=5 closed_sold=5"},"C":{"pass":false,"metric":69.8,"detail":"matched_clean=44"},"D":{"pass":false,"metric":69.8,"detail":"matched_any=44"},"E":{"pass":true,"metric":100.0,"detail":"parcel_linked=63"},"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=5 closed_sold=5"},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":2.0},"I":{"pass":true,"metric":100.0,"detail":"card_complete=63 of 63"},"J":{"pass":true,"metric":100.0,"detail":"deal_complete=63 of 63"},"county":"santa_rosa","auctions_total":63}
```

**After:**
```json
{"A":{"pass":true,"metric":16,"detail":"fc=47 td=16"},"B":{"pass":true,"metric":100.0,"detail":"verified=5 closed_sold=5"},"C":{"pass":false,"metric":92.1,"detail":"matched_clean=58"},"D":{"pass":false,"metric":92.1,"detail":"matched_any=58"},"E":{"pass":true,"metric":100.0,"detail":"parcel_linked=63"},"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=5 closed_sold=5"},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":2.0},"I":{"pass":true,"metric":100.0,"detail":"card_complete=63 of 63"},"J":{"pass":true,"metric":100.0,"detail":"deal_complete=63 of 63"},"county":"santa_rosa","auctions_total":63}
```

hendry (unchanged, re-confirmed live):
```json
{"A":{"pass":true,"metric":2},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":5.3},"D":{"pass":false,"metric":5.3},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0}}
```

alachua (unchanged, re-confirmed live):
```json
{"A":{"pass":true,"metric":3},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":35.0},"D":{"pass":false,"metric":35.0},"E":{"pass":false,"metric":85.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true},"I":{"pass":false,"metric":82.5},"J":{"pass":true,"metric":100.0}}
```

liberty (unchanged, re-confirmed live — E already shipped by prior session):
```json
{"A":{"pass":false,"metric":0},"B":{"pass":false},"C":{"pass":false,"metric":0.0},"D":{"pass":false,"metric":0.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false},"G":{"pass":false},"H":{"pass":true,"metric":1.5},"I":{"pass":false,"metric":0.0},"J":{"pass":true,"metric":100.0}}
```

`gold_standard_loop()`/`gold_standard_certify()` were **not** run — per PARALLEL-FLEET RULES, other shard sessions were mid-flight today (commit `06f36caf`, SHARD-6, landed minutes before this session started).

### ULTRALOOP adversarial verification

Independent refuter agent (Workflow tool, cold DB re-derivation, did not reuse this session's numbers): **`survived=true`** for both C and D. Logged as `gold_standard_ultraloop_audit` rows id=3155 (letter C) and id=3156 (letter D), dispatch_id `84da506f-e01d-444f-8e53-2f9304c29599`.

Refuter's independent computation: 58/63 = 92.1% (exact match). Refuter additionally verified: (1) `realforeclose_aids` is genuinely independently-sourced (real clerk/appraiser URLs, `first_seen_at` timestamps confirming a fresh scrape, not derived from `multi_county_auctions`); (2) all 14 claimed case numbers are present and correctly matched; (3) 5 matched rows with sentinel-string `parcel_id` ("Property Appraiser", "MULTIPLE PARCELS") initially looked suspicious against the matcher's own documented false-positive class, but each independently verified via case_number match — legitimate; (4) the 5 known-synthetic seed rows correctly remain unmatched, exactly accounting for the 63−58=5 gap; (5) the live RPC and the refuter's raw-row computation agree exactly.

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Recon | Check whether this dispatch duplicates prior work | Found exact-match `dispatch_id`/`chat_session` in committed history; confirmed via live DB that state was unchanged | None — this check is why no redundant work was attempted |
| santa_rosa C/D | Execute prior session's deferred lever (AJAX harvest against `.realtaxdeed.com`) | Executed exactly as scoped; real, verified gain (69.8%→92.1%) | None |
| Wiring | Not originally planned | Added `.github/workflows/shard2-ajax-realforeclose-harvest.yml` since the harvester had zero executor — required by WIRING MANDATE | Positive deviation — closes a durability gap so this doesn't need rediscovery |
| hendry/alachua/liberty | Re-verify for any new levers | No new levers found; all three remain genuinely blocked exactly as the prior session documented | None |
| ULTRALOOP verify | Adversarial refuter per claimed letter move | Ran for both C and D; `survived=true` both | None |

## Deferred / flagged for next session

- **santa_rosa 5 synthetic seed rows** (`SANTA-ROSA-FC/TD-2026-00X`): still flagged for Ariel to review/purge. Once purged, santa_rosa C/D would read 58/58 = 100% (currently the only thing blocking santa_rosa from a PASS on C/D).
- **hendry C/D**: structural — needs genuine new independent outcome records (18 of 19 auctions have never closed with a verifiable outcome). No matcher/SQL fix will move this.
- **alachua E (6 remaining rows) / I**: needs court case-document retrieval (docket/complaint) to find owner name or legal description — no usable identifying data exists today.
- **liberty G/I**: needs real ordinance-sourced zoning data for unincorporated Liberty County. Do not synthesize zone_standards values — HARD GUARDRAIL.
- **New `.github/workflows/shard2-ajax-realforeclose-harvest.yml`**: first scheduled run is 09:30Z tomorrow — verify it runs clean before relying on it further.
