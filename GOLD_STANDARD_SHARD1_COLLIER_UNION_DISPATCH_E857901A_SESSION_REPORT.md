# GOLD STANDARD shard-1 (collier, union) — session report

dispatch_id: `e857901a-9b66-458b-9bc7-17728a3f5dfe` · chat_session: `architect-20260810T160000` · 2026-08-10

mode: ULTRALOOP native (Workflow tool: 2 adversarial refuter subagents, fanned out after direct live diagnosis)

## Result summary

| County | Briefed | Live at session start | Live at session end | Change |
|---|---|---|---|---|
| collier | 9/10 (I failing) | 9/10 (I failing, 93.7%) | **10/10 — all PASS** | **I fixed and verified** |
| union | 8/10 (B,F failing) | 6/10 (B,C,D,F failing — undocumented regression found) | 6/10 (B,C,D,F still failing) | C/D metric recovered 33.3%→66.7%, still below 95% bar; root cause fully diagnosed and disclosed |

## collier: I FIXED (93.7% → 95.5%, card_complete 208→212 of 222)

Root cause (matches the exact diagnosis already on file from dispatch C40BB245, 2026-07-18): `scripts/gs_shard1_c40bb245_collier_i.py` is an idempotent, additive-only, already-Ariel-reviewed backfill that patches `property_address` from the FL DOR statewide cadastral FeatureServer only where the source's `PHY_ADDR1` is genuinely blank (vacant/unimproved land) and `PHY_CITY` is on a real-Collier-municipality allowlist — writing `"<CITY>, FL <ZIP>"`, never a fabricated street address. Because the script re-queries live `property_address IS NULL` rows rather than a hardcoded list, simply re-running it against today's data picked up 5 rows added to collier since the July fix that had never been processed:

- `26164` (01086400005) → NAPLES, FL 34114
- `26165` (01097520000) → NAPLES, FL 34114
- `26167` (01123320006) → NAPLES, FL 34114
- `26168` (01153280006) → NAPLES, FL 34141
- `26182` (83890360003) → EVERGLADES CITY, FL 34139

8 folios remain a confirmed, unfixable residual (zero match anywhere in the FL DOR FeatureServer, even after zero-padding variants) — left NULL per BLANK > WRONG, unchanged from the July diagnosis.

**Live verification (post-fix):**
```json
{"I": {"pass": true, "detail": "card_complete=212 of 222", "metric": 95.5}, ...all A-J pass:true, auctions_total: 222}
```

**Adversarial verify: SURVIVED.** Independent refuter re-read the script for fabrication risk, independently cross-checked the FL DOR FeatureServer for the 5 patched parcels (exact match), independently re-ran the live RPC (exact match, zero regression on any other letter), and checked no scheduled job would overwrite these values back to NULL. Full evidence in `gold_standard_ultraloop_audit` id 14275.

## union: regression found and diagnosed, not fully resolved

The brief stated union 8/10 (B,F failing). The first live check this session found **C and D also failing** (33.3%, matched_clean=1 of 3) — an undocumented regression from a 100%/matched_clean=3 reading as recent as 2026-07-31.

**Root cause:** a brand-new, separate pipeline (`scripts/clerk_ssot/run_parity.py` + `parsers/union.py`, committed today 2026-08-10 in `b1b053a4`/`6515d87b`) independently re-verifies county calendars against live clerk sites via a real Playwright-rendered fetch (unionclerk.com sits behind a Cloudflare managed challenge that 403s plain HTTP fetches — confirmed independently by this session's own `WebFetch` attempt — but the dedicated headless-browser parser gets through cleanly). It tagged a genuine clean match (`63-2024-CA-0047`) as `parity_status='PARITY_OK'` / `parity_source='union_clerk_foreclosure'` — a different convention than the legacy evaluator's `matched_clean` + `parity_source LIKE 'tier1%'` filter, so a real, good match was invisible to C/D.

**Mid-session, this was found already fixed live** (not by this session) — some other concurrent fleet session had deployed a live edit to `public.pencil_dod_evaluate_county()` recognizing `parity_status IN ('PARITY_OK','CLERK_VERIFIED')`. Confirmed via `pg_get_functiondef` over the Management API. This recovered union `matched_clean` from 1→2 (33.3%→66.7%), still short of the 95% bar.

**Process gap found, closed by a concurrent session:** at the time the adversarial refuter checked (mid-session), that live fix had no corresponding migration file anywhere in the repo (confirmed by grep — zero matches). This session drafted a byte-identical backfill migration to close the gap, but a `git pull --rebase` immediately before commit found shard-3 (lake, dispatch `77ac9cef`) had already landed the same fix on `main` as `supabase/migrations/20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql` — with a more complete root-cause writeup (documents the same regression hitting lake and, per the `run_parity.py` `PARSERS` dict, up to 9 counties total: brevard, gadsden, highlands, lake, okeechobee, st_johns, suwannee, union, wakulla). This session's draft was deleted as a duplicate rather than committed — no redundant migration added.

**Residual (unresolved, disclosed):** the 3rd union case, `63-2025-CA-0053` (auction_date 2026-08-13, only 3 days out), is independently and repeatedly (5 checks across two independent tools today) confirmed **absent** from unionclerk.com's live "Upcoming Foreclosure Sales" listing. New evidence this session (BC Telegraph legal-notice archive, a technique not in any prior audit trail) found the actual clerk-signed re-notice chain confirming August 13, 2026 is a real, current, still-pending sale — ruling out a "sale already happened" explanation. This looks like a website-side publishing gap on the clerk's own site, not a data error on our side, but it cannot be resolved from here. **This single case is the entire remaining gap**: fixing/resolving it would flip union C/D to 100%. Flagged, not silently edited or deleted — the row is untouched.

**union B/F reconfirmed genuine structural blocker** (unchanged from the 2026-08-09 adversarial confirmation, now with a 40-row audit history back to 2026-06-25): `closed_sold=0` because the tax-deed cert was redeemed (not sold) and both foreclosure cases are still genuinely upcoming. No new sale evidence found despite a fresh search attempt this session.

**Adversarial verify: SURVIVED (all sub-claims).** Full evidence in `gold_standard_ultraloop_audit` ids 14276 (C/D) and 14277 (B/F reconfirm).

## Honesty Protocol tags

- Collier I fix: **VERIFIED** (live RPC + independent refuter re-derivation + FeatureServer cross-check).
- Union C/D metric recovery (33.3%→66.7%): **VERIFIED** (live RPC before/after).
- Union C/D fleet-wide fix authorship: **CONFIRMED not this session's work** — found already live, correctly attributed.
- Union B/F structural block: **VERIFIED** (reconfirmed live, no new sale found).
- Union `63-2025-CA-0053` clerk-listing gap: **UNKNOWN / disclosed residual** — real notice confirms the sale is live and current, but why it's absent from the website listing is not determined from available tools.

## Close-out

```sql
UPDATE public.gold_standard_campaign
SET criteria_passed = '{"A":true,"B":true,"C":true,"D":true,"E":true,"F":true,"G":true,"H":true,"I":true,"J":true}'::jsonb, -- collier
    criteria_total = 10,
    exit_reason = 'collier_certified_10of10_union_partial_fix_root_caused_not_resolved',
    session_end_at = now()
WHERE dispatch_id = 'e857901a-9b66-458b-9bc7-17728a3f5dfe';
```

Note: `gold_standard_campaign` rows are single-county-shaped (`criteria_passed`) but this dispatch targets two counties; collier's fully-passing state is recorded as the primary result. Union's per-letter state (6/10: A,E,G,H,I,J pass; B,C,D,F fail) is captured in full above and in the `gold_standard_ultraloop_audit` rows, not lost.

### SQL VERIFICATION

Live query run 2026-08-10 (post-fix, post-migration-apply):
```
collier: {"A":true,"B":true,"C":true,"D":true,"E":true,"F":true,"G":true,"H":true,"I":true,"J":true} auctions_total=222
union:   {"A":true,"B":false,"C":false,"D":false,"E":true,"F":false,"G":true,"H":true,"I":true,"J":true} auctions_total=3
```
via `SELECT public.pencil_dod_evaluate_county('collier')` / `('union')`, timestamp 2026-08-10T16:5x:xxZ (UTC).

**Certification note:** per campaign rule, certification requires two consecutive daily 10/10 runs at 07:30Z, and `gold_standard_certify()` additionally requires fresh (≤7 day) `survived=true` ultraloop_audit rows for all 10 letters. Collier's I/adversarial-verify rows just landed; the other 9 letters' most recent `survived=true` rows should be checked for freshness before the next 07:30Z certify pass — not verified in this session (out of scope: no other collier letters changed, and re-running the full loop was deferred per PARALLEL-FLEET RULES since other shards were active concurrently — confirmed by the concurrent union evaluator fix discovered mid-session).

## Next-session priorities

1. **union C/D**: the entire remaining gap is one case (`63-2025-CA-0053`). If a future session gets a working method past unionclerk.com's Cloudflare challenge for a case-level lookup (or finds an alternate official source — clerk phone/email, in-person, or a court-records portal with case-level search), confirming this case's listing status would likely flip union to 8/10.
2. **union B/F**: will resolve automatically once the Aug 13, 2026 auction (3 days from this session) actually closes — `promote_tier1_from_outcomes`/existing automation should pick it up. Worth a quick recheck any session after Aug 13.
3. **Fleet-wide**: shard-3 (lake) already shipped the evaluator fix + migration (`20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql`) — the 8 other clerk_ssot counties (brevard, gadsden, highlands, okeechobee, st_johns, suwannee, union, wakulla) should each get a quick re-check for the same C/D recovery pattern seen here for union.
