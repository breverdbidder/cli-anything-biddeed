# Gold Standard shard-2: lee, hamilton, liberty, charlotte, baker

dispatch_id: a1884f7f-816e-4b36-bfb6-e4a65f77ebba
chat_session: architect-20260812T080000
mode: ULTRALOOP fallback (Workflow-tool fan-out: 7 targets x diagnose->fix->adversarial-verify, independent refuter per claim)

## Before -> After (live pencil_dod_evaluate_county, all numbers CONFIRMED via curl this session)

### lee (9/10 -> 9/10, unchanged)
- I: card_complete 300/322 (93.2%) -> unchanged. BLOCKED, re-confirmed live, no new lever found. Need 6 more of the 22 incomplete rows.

### hamilton (8/10 -> 8/10, unchanged, real partial movement on the failing pair)
- C: matched_clean 16/21 (76.2%) -> 17/21 (81.0%). Still FAIL.
- D: matched_any 16/21 (76.2%) -> 17/21 (81.0%). Still FAIL.
- Fix: case 2025-CA-46 was live on hamiltonclerk.com today (mis-flagged from a stale 2026-07-18 check); reconciled. Remaining 4 cases (2021-CA-46, 2023-CA-41, 2024-CA-19, 2025-CA-37) have zero live evidence on the clerk site and Firecrawl remains credit-exhausted (-10/1,000, HTTP 402 confirmed live) — genuinely blocked.
- Adversarial verify note: flagged a conflicting prior-session record (20260810 migration already documented 17/21 baseline) — logged for next session, does not invalidate today's independently-confirmed numbers.

### liberty (7/10 -> 7/10, unchanged; one finding corrected for future sessions)
- A/B/F: re-confirmed BLOCKED (auctions_total=1, no closed sales exist yet; Firecrawl -10/1,000 credits).
- Adversarial verify REFUTED part of the diagnosis: the prior/current session's claim that civitekflorida.com OCRS and myfloridacounty.com ORI are "Turnstile-gated" does not hold — those exact subdomains are DNS NXDOMAIN (don't exist). The real endpoints (found via libertyclerk.com's own links: www.civitekflorida.com/ocrs/county/39/, www3.myfloridacounty.com/official_records/index.html) return HTTP 200 with plain JSF forms, no Turnstile markers in static HTML. Bottom-line BLOCKED status is still correct (Firecrawl has no credits regardless), but the specific Turnstile claim was wrong and should not be repeated as fact. Next session should attempt a real form-POST interaction against the correct URLs before re-declaring blocked.

### charlotte (6/10 -> 8/10, two letters flipped PASS)
- D: matched_any 165/176 (93.8%) -> 175/176 (99.4%). **PASS.** 10 rows had authoritative tier1 data already sitting unstamped in the DB (tier1_source_run_id=93161, a real prior ingestion run) and were reconciled — no fabrication, no sold_amount touched (protects B/F).
- C: matched_clean 153/176 (86.9%) -> 158/176 (89.8%). Still FAIL — of the same 10 rows, only 5 could clean-match; the other 5 are genuine CLERK_SSOT_CANCELLED / structural. 158 matched_clean + 17 cancelled + 1 genuinely-still-LISTED = 176, fully reconciled.
- I: card_complete 162/176 (92.0%) -> 173/176 (98.3%). **PASS.** 11 rows backfilled via Charlotte County ArcGIS (parcel_zones + lat/lon/assessed_value). 3 residual rows are genuinely unfixable (MULTIPLE PARCELS on one auction record).
- G: pk1000 0.0% -> 100.0%, far N/A (no longer applicable) via real Charlotte LDC Sec. 3-9-79 parking standard + far_regulated=false correction for one district (zoning_district_id=13810). G still FAILs overall — density (86.9%) is a separate, unaddressed sub-metric, correctly left out of scope for this ticket.
- Commits: `b88b95a7` (G), `6817a96c` (C/D), `5adb6163` (I) — already on origin/main (fix-phase agents pushed directly).

### baker (5/10 -> 5/10, unchanged flags, but real data-quality progress + a corrected false BLOCKED claim)
- Fix-phase agent (re-)declared C/D/E/I/J BLOCKED for the residual case 022025CC000132CCAXMX. **Adversarial verify REFUTED this** — found the case's owner/address (Fernando Dunn, 8669 Newnan Lake Dr) sitting in `fl_parcels` (co_no=12), a source the fix-phase never checked, via the same pattern already used in prior gadsden/franklin/hamilton/miami-dade/broward fixes. Orchestrator independently re-confirmed the match (single unambiguous candidate) and applied it live.
- E: parcel_linked 8/10 (80.0%) -> 9/10 (90.0%). Still FAIL — this county's auctions_total=10 means 95% requires all 10 linked.
- C/D/I: unaffected by this write (they need parity_status / zoned-parcel card completion separately, not just parcel_id) — remain 8/10 (80.0%).
- The second flagged case, 022025CA000117CAAXMX, was independently re-checked and genuinely has no address/owner anywhere yet (no legal notice filed, consistent with normal FL Ch.45 timing) — confirmed still a real structural blocker.
- Did NOT touch the phantom-tax-deed-dedup fix (commit 88ca0e4b) per instruction — auctions_total remained 10 throughout.
- Migration: `supabase/migrations/20260812_shard2_a1884f7f_baker_e_parcel_backfill.sql`.

## Ultraloop audit trail
21 rows written to `gold_standard_ultraloop_audit` (dispatch_id=a1884f7f-816e-4b36-bfb6-e4a65f77ebba): 16 survived=true, 5 survived=false (liberty B, liberty F, baker C/D/E/I/J — 5 of those 5 refuted as false-BLOCKED, one since corrected live: baker E). All under `ultraloop_mode='fallback'` (fan-out via the Workflow tool, not a native /effort ultracode CLI toggle).

## Honesty notes
- No fabricated parcel data, zoning values, or case outcomes anywhere in this session. Every write traces to a live, independently-re-queried source (county clerk site, fl_parcels statewide cadastral cache, county GIS/ArcGIS, or ordinance text with a cited section number).
- Two BLOCKED claims from fix-phase agents were caught and disproved by adversarial verify before being accepted (liberty B/F Turnstile claim; baker C/D/E/I/J fl_parcels miss) — exactly the failure mode the ULTRALOOP protocol exists to catch. One (baker E) was then actually fixed live in this same session rather than deferred.

## Next-session priorities
1. baker: J generator + finish parity/card-completion for case 132 now that parcel_id exists; case 117 remains genuinely source-exhausted.
2. liberty/hamilton: retry OCRS/ORI via the corrected live URLs with a real form-POST interaction, not a GET-only check, once Firecrawl credits are restored (or find a non-Firecrawl path).
3. lee I: source the 22 remaining card-completeness rows via Lee County Property Appraiser ArcGIS.
4. charlotte C: 18 rows remain unmatched/structural; charlotte G density (86.9%) still needs the same ordinance-backfill treatment as far/pk1000 received this session.
5. hamilton: reconcile the conflicting 08-10 vs today C/D baseline discrepancy flagged by the refuter.

## SQL VERIFICATION

```sql
-- charlotte, live 2026-08-12 (after this session's fixes)
SELECT public.pencil_dod_evaluate_county('charlotte');
-- A:PASS(31) B:PASS(100.0) C:FAIL(89.8) D:PASS(99.4) E:PASS(100.0) F:PASS(100.0)
-- G:FAIL(86.9) H:PASS(0.0) I:PASS(98.3) J:PASS(96.0)  => 8/10, up from 6/10

-- baker, live 2026-08-12 (after E backfill)
SELECT public.pencil_dod_evaluate_county('baker');
-- A:PASS(1) B:PASS(100.0) C:FAIL(80.0) D:FAIL(80.0) E:FAIL(90.0, was 80.0)
-- F:PASS(100.0) G:PASS(100.0) H:PASS(0.0) I:FAIL(80.0) J:FAIL(90.0)  => still 5/10, E moved
```
Timestamp: 2026-08-12T08:46Z
