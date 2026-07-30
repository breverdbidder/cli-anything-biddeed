# Gold Standard shard-3: volusia, st_lucie — 3rd firing session report

dispatch_id: 8c78a8df-6a6b-473d-b3cb-ac257a1f5718
chat_session: architect-20260730T160000
mode: ULTRALOOP native (Workflow tool, ultracode opted in)
prior firings: 953bb752 (1st, volusia 7→9/10, st_lucie 6→8/10), 69edce8b (2nd, st_lucie I 93.3→94.1%, volusia G left open — "Next session: source the real Daytona Beach LDC Article 4/6 M-1 standard")

## Scope this firing

Both prior firings identified the SAME two residual gaps and could not close them
(municode 403 / Firecrawl 402 blocked ordinance research; st_lucie's remaining 7
rows suspected but not conclusively confirmed non-parcelable). This firing picked
up exactly those two next-session priorities:
1. volusia G — source real Daytona Beach M-1 FAR/parking ordinance value.
2. st_lucie E/I — adversarially re-verify (not just re-assert) the prior firing's
   "7 rows are structurally non-standard collateral" claim.

## Baseline (live, re-confirmed at session start — brief was stale)

Brief claimed volusia 10/10, st_lucie 6/10. Live `pencil_dod_evaluate_county`
at session start showed volusia **9/10** (G failing 83.3, denominator had grown
290→395 since brief snapshot) and st_lucie **8/10** (E/I failing 94.1) — matching
the 2nd firing's end state exactly, not the brief.

## Method (ultracode Workflow, 5 agents, 2 phases)

**Research phase (4 parallel agents):**
- 2 independent researchers navigated the Municode API (`api.municode.com/CodesContent?jobId=492952&productId=13509`) via distinct paths to find Daytona Beach LDC Sec. 4.4 "Industrial Base Zoning Districts" and Sec. 6.2 "Off-Street Parking and Loading" standards for M-1 ("Local Industry").
- 2 agents split the 7 st_lucie case numbers and independently re-tried to confirm or refute the prior firing's AIRCRAFT/TIMESHARE/MULTIPLE-PARCELS/placeholder classification via stlucie.realforeclose.com live AJAX + St Lucie Clerk/Property Appraiser/UniCourt/trellis.law.

**Verify phase (adversarial adjudicator, 1 agent):** independently re-fetched both cited Municode URLs itself (parsed the raw 7MB JSON response directly rather than trusting either researcher's summary), confirmed the FAR=1.0 quote verbatim, and confirmed the parking figure is genuinely a compound use-based formula, not a single per-1,000sf number.

## volusia G: FIXED, county now 10/10

**Root cause found (new — neither prior firing spotted this):** it was never actually a missing-ordinance-data problem. `parcel_zones` for parcel `533801110032` (Daytona Beach, jurisdiction_id=938) stored `zone_code='M1'` (no hyphen) while the county's real zoning_districts row uses the published code `M-1` (matching every other Daytona Beach industrial code in this dataset: M-1/M-3/M-4/M-5, all hyphenated). The join silently failed, defaulting the parcel to `far_applicable=true`/`pk1000_applicable=true` with NULL values via `COALESCE(...,true)` — exactly the same failure class the 2nd firing's st_lucie RMH-5 regression fix (commit `24b95663`) diagnosed, just not previously spotted here because everyone assumed the ordinance research itself was the blocker.

**Real values obtained (VERIFIED, adversarially cross-checked, not fabricated):**
- FAR maximum = **1.0** — Daytona Beach LDC Sec. 4.4.B.3, "Local Industry (M-1)" Intensity and Dimensional Standards table, quoted verbatim: "Floor area ratio (FAR), maximum | 1.0". Confirmed independently by both researchers via different navigation paths, and a third time by the adjudicator re-fetching the raw API response directly.
- Parking: Daytona Beach's LDC does **not** set a per-district parking figure at all (Sec. 4.4.B.4 explicitly defers to Article 6). Article 6 Table 6.2.C.1 sets parking by use type city-wide, and M-1's core uses (industrial services / manufacturing & production / warehouse & freight) share a compound formula "1.5 per 1,000 sf + 3.5 per 1,000 sf of office or retail area" — not a single number. All three agents independently flagged that forcing a single blended value into `parking_per_1000sf` would misrepresent the ordinance, so `pk1000_regulated` was set to `false` instead — the exact same honest-non-applicability pattern already used for MFR-40 (id=6529) in this same jurisdiction by a prior firing, not a new precedent.

**Migration:** `supabase/migrations/20260730e_gold_standard_shard3_volusia_g_daytona_m1_zonelink.sql` — applied live via Management API this session (3 statements: zone_code normalization, zoning_districts flags+ordinance_section, zone_standards.max_far insert).

**Live verification (before → after):**
```sql
SELECT * FROM v_zoning_gold_standard_kpi_v3 WHERE county=norm_county_key('volusia');
-- before: far_applicable=6 pct_far=83.3, pk1000_applicable=13 pct_pk1000=92.3, density pct=96.8
-- after:  far_applicable=6 pct_far=100.0, pk1000_applicable=12 pct_pk1000=100.0, density pct=97.1

SELECT public.pencil_dod_evaluate_county('volusia');
-- before: {..., G: FAIL(83.3, "density=96.8 far=83.3 pk1000=92.3"), ...} => 9/10
-- after:  {A:PASS(116) B:PASS(100) C:PASS(99.7) D:PASS(99.7) E:PASS(100) F:PASS(100)
--          G:PASS(97.1,"density=97.1 far=100.0 pk1000=100.0") H:PASS(0) I:PASS(95.7) J:PASS(100)}
-- => 10/10 ALL PASS
```

## st_lucie E/I: NOT fixed — prior firing's non-parcelable claim independently re-checked, not refuted

Ran the adversarial verify as a genuine refutation attempt (task instruction to the
agents: "default to skepticism... if you find a real parcel_id for any case, report
it — this would be a refutation"). Result: **zero refutations.**

| case_number | outcome this firing | confidence |
|---|---|---|
| 2024CA000214 | RECONFIRMED live: `Parcel ID: MULTIPLE PARCELS`, $825,148.51 judgment. WebSearch surfaced sub-listings `.mlti1`/`.mlti2` on stlucieforeclosures.com suggesting it *may* decompose into 2 discrete real parcels, but that site 403'd on every direct-fetch attempt so no actual parcel_id could be extracted. Genuinely unresolved, not fabricated. | VERIFIED (multi-parcel structure), UNRESOLVED (no usable parcel_id) |
| 2025CA002738 | RECONFIRMED live: generic `Property Appraiser` search-homepage link with no query string, $0.00 judgment — genuine placeholder, not truncated data. | VERIFIED |
| 2023CA000465 | RECONFIRMED live: same pattern, $0.00 judgment, generic placeholder link. | VERIFIED |
| 2024CA001834, 2025CC001033, 2023CA002852, 2024CA000330 | Could not independently confirm OR refute. St Lucie Clerk portal returned HTTP 500, AcclaimWeb 403, UniCourt 405, trellis.law 403 on every attempt; Firecrawl account balance is negative (402 Insufficient credits, same blocker the 1st firing hit for volusia); no browser-use/Playwright tool available in this sandbox to get past the JS/Cloudflare walls. | UNTESTED |

Per Honesty Protocol (BLANK > WRONG), **no database change was made** to any of
the 7 rows — the prior firing's classification stands as unrefuted, not as
freshly re-verified with full confidence (4 of 7 are honestly UNTESTED, not
VERIFIED, this session). st_lucie remains **8/10** (E: 94.1%, I: 94.1%, both
need 95%, i.e. 2 more of these 7 rows would need to become genuinely parcelable).

**What would actually move this:** a tool capable of rendering
stlucieforeclosures.com (Cloudflare-walled) or authenticating past the St Lucie
Clerk's search portal — e.g. `firecrawl-browser` with a funded account, or
Playwright — to resolve the `.mlti1`/`.mlti2` sub-listings on case 2024CA000214
to real parcel IDs, and to get past the 500/403/405 responses blocking the other
6 cases. Flagging Firecrawl's negative credit balance for the AI Architect — this
is now the second consecutive shard-3 firing blocked by the same exhausted
account (ARM-2 budget note: $50/mo cap referenced in the dispatch brief; worth
checking whether that cap has actually been funded).

## ULTRALOOP audit (adversarial verify, per protocol)

Inserted into `gold_standard_ultraloop_audit` (dispatch_id=8c78a8df-6a6b-473d-b3cb-ac257a1f5718, ultraloop_mode='native'):
- `volusia` / `G` / `survived=true` — adjudicator independently re-fetched both source URLs and confirmed the FAR quote verbatim + confirmed post-fix live query shows G:PASS(97.1).
- `st_lucie` / `E` / `survived=false` — the tested hypothesis ("some of the 7 rows can be shown parcelable") did not survive; 0/7 refuted, 3/7 reconfirmed non-parcelable, 4/7 access-blocked/UNTESTED. Logged as a false-positive-checked claim per protocol, not retried without new evidence.

## Verification evidence

### SQL VERIFICATION
```sql
-- volusia, 2026-07-30 (this firing)
SELECT public.pencil_dod_evaluate_county('volusia');
-- {A:PASS(116) B:PASS(100) C:PASS(99.7) D:PASS(99.7) E:PASS(100) F:PASS(100)
--  G:PASS(97.1) H:PASS(0) I:PASS(95.7) J:PASS(100)} => 10/10 ALL PASS

-- st_lucie, 2026-07-30 (this firing, unchanged from 2nd firing)
SELECT public.pencil_dod_evaluate_county('st_lucie');
-- {A:PASS(19) B:PASS(100) C:PASS(99.2) D:PASS(100) E:FAIL(94.1) F:PASS(100)
--  G:PASS(97.2) H:PASS(0) I:FAIL(94.1) J:PASS(100)} => 8/10
```

## Not run this session (per PARALLEL-FLEET RULES)

Did not run `public.gold_standard_loop()` or `public.gold_standard_certify()` —
could not confirm no other shard session was mid-flight. Per-county
`pencil_dod_evaluate_county` evaluations above are the authoritative record for
this firing. volusia's 10/10 will be picked up by the next scheduled full loop
run; per the campaign brief, certification lands automatically after the second
consecutive 10/10 daily 07:30Z run.

## Next-session priorities (this shard)

1. **st_lucie E/I is now the only open item.** Needs a JS-capable browser tool
   (funded Firecrawl account or Playwright) to resolve case `2024CA000214`'s
   `.mlti1`/`.mlti2` sub-listings and to get past the 500/403/405 walls on the
   other 6 cases. If, after a genuinely funded/tooled attempt, the remaining
   rows are conclusively confirmed non-parcelable, the next honest step is a
   canon/policy decision (flagged by the 1st firing too) on whether
   non-standard-collateral rows (aircraft/timeshare/multi-parcel/placeholder)
   should be excluded from the E/I denominator at all, rather than continuing
   to re-attempt the same 7 rows indefinitely.
2. volusia has no further known open items this shard — 10/10 live-confirmed.
