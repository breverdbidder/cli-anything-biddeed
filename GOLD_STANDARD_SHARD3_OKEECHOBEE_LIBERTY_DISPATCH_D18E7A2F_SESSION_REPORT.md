# Gold Standard shard-3 — okeechobee, liberty — dispatch d18e7a2f-9a29-4041-83dc-13faa40898d7

## Assigned scope
okeechobee + liberty only, per the shard-3 brief (loop run 12072).

## Baseline (verified live, session start, 2026-08-16)
```json
okeechobee: {"A":{"pass":true,"metric":19},"B":{"pass":true,"metric":100.0},
 "C":{"pass":true,"metric":96.5},"D":{"pass":true,"metric":96.5},
 "E":{"pass":true,"metric":95.3},"F":{"pass":true,"metric":100.0},
 "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.0},
 "I":{"pass":false,"detail":"card_complete=80 of 86","metric":93.0},
 "J":{"pass":true,"metric":100.0},"auctions_total":86}
liberty: {"A":{"pass":false,"detail":"fc=1 td=0","metric":0},
 "B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},
 "C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},
 "E":{"pass":true,"metric":100.0},
 "F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},
 "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":29.0},
 "I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},
 "auctions_total":1}
```
Exact match to the shard brief. okeechobee's certification had just been revoked
(`revoked_at=2026-08-16T14:36:18Z`, `consecutive_non_gold=3`, `reason=letters_failed`)
minutes before this session started, live-confirmed via `gold_standard_certifications`.

## okeechobee — letter I fix (WRITE)

### Root cause (verified live via direct REST inspection)
okeechobeeclerk's live foreclosure calendar publishes the hyphenated short case form
("2025-CA-130"), while `calendar_sweep_mca_v3` already stores the same real-world case
under the 19th Judicial Circuit's long clerk form ("472025CA000130CAAXMX"), fully
enriched with real address/lat/lon/parcel_id/assessed_value (auction_date matches
exactly between both rows in every case: 130→08-19, 143→08-26, 205→08-26).
`scripts/clerk_ssot/run_parity.py`'s existing case-number canonicalization (already
has documented, county-gated fixes for manatee/holmes/suwannee/lake in the same
function) did not cover this shape, so every clerk_ssot run re-inserted a blank stub
under the short form and flagged the enriched long-form row `PHANTOM_NOT_ON_CLERK` —
this is exactly what caused today's `consecutive_non_gold=3` revocation. This is a
*recurrence* of a pattern a 2026-08-15 session (`20260815_architect_triage_19096_...sql`)
had already fixed once by deleting the duplicates without patching the ingestion
source — the fix didn't hold because the root cause (the matching regex) was
untouched, so clerk_ssot simply re-created the same 3 duplicates on its next run.

Confirmed via `bid_decisions` lookup that the 3 short case_numbers carry pre-existing
orphan rows (609397/632122/677547/699577 etc.) with no FK to `multi_county_auctions.id`
— deleting the blank stub rows does not orphan anything new (same finding the
2026-08-15 session made).

### Code fix (this session, committed)
Added `_OKEECHOBEE_SHORT_RE` / `_OKEECHOBEE_LONG_RE` to
`scripts/clerk_ssot/run_parity.py`, gated on `county_slug=='okeechobee'` (same
collision-risk-averse pattern the file already uses for manatee), so both case-number
shapes canonicalize to the same key. Regex verified standalone against all 4 live
case-number strings before applying any DB change (see session transcript) — matches
correctly and does not collide with any other county's regex in the same function.
This is the durable half of the fix; the 08-15 session only had the DML half.

### Live DML (applied via PostgREST REST API — direct psql/SUPABASE_DB_PASSWORD not
attempted, per documented decision_log ids 169/205/287 constraint)
```sql
DELETE FROM public.multi_county_auctions
 WHERE county='okeechobee' AND case_number IN ('2025-CA-130','2025-CA-143','2025-CA-205');
UPDATE public.multi_county_auctions SET parity_status='CLERK_VERIFIED'
 WHERE county='okeechobee'
   AND case_number IN ('472025CA000130CAAXMX','472025CA000143CAAXMX','472025CA000205CAAXMX');
```
Recorded in `supabase/migrations/20260816_gold_standard_shard3_okeechobee_i_clerk_ssot_dedup_fix.sql`.

### Before / After (pasted live RPC output)
Before: see baseline JSON above (I: 93.0%, card_complete=80 of 86).

After (`pencil_dod_evaluate_county('okeechobee')`, run immediately post-fix):
```json
{"A":{"pass":true,"metric":16,"detail":"fc=16 td=67"},
 "B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0},
 "D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":98.8},
 "F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},
 "H":{"pass":true,"metric":0.1},
 "I":{"pass":true,"detail":"card_complete=80 of 83","metric":96.4},
 "J":{"pass":true,"metric":100.0},"auctions_total":83}
```
**okeechobee is now 10/10 live.** No regressions — C/D even improved (96.5%→100.0%)
and E improved (95.3%→98.8%) as a side effect of removing the 3 blank-denominator rows.

### Residual gap (disclosed, not fixed)
`2025-CA-189` (no long-form sibling, genuinely unresolved per the 08-15 session) and
`2026TD050` (FL parcel appraiser roll returns "No Matching Records Found" for its
parcel_id, previously documented as structurally blocked) remain incomplete. I is
96.4% (80 of 83), already above the 95% threshold, so these 2 residuals don't block
the letter. Not fabricated.

## liberty — A/B/F reconfirmed genuine data ceiling (NO WRITE)

This is the 7th+ session across ~6 weeks (2026-07-05 through 2026-08-15, per prior
session reports in this repo) to independently reconfirm the identical structural
blocker. Rather than re-run the same exhausted Cloudflare-Turnstile probes for the
Nth time, this session did a targeted freshness check only:

- `curl https://libertyclerk.com/courts/tax-deeds/` → page still contains the literal
  string `<p>There are no properties on the list of tax deeds at this time.</p>`,
  byte-for-byte the same finding as every prior session.
- `curl https://libertyclerk.com/courts/foreclosure-sales/` → "no foreclosure sales";
  case `24-CA-22` (sale date 2026-07-21, now ~4 weeks past) no longer appears.
- `public.foreclosure_outcomes` / `public.tax_deed_outcomes` for county=liberty: both
  still 0 rows.
- `multi_county_auctions` for liberty: still exactly 1 row (24-CA-22), `auction_status`
  still stuck at `upcoming` (stale, since the case fell off the live calendar without an
  independent outcome source to update it).

No new lever found. A/B/F remain genuinely blocked on (1) a real, currently-empty
tax-deed list and (2) two Cloudflare Turnstile gates (OCRS case search, ORI) that would
carry an independent verified outcome for case 24-CA-22, unchanged since at least
2026-07-24. Per guardrails, no CAPTCHA bypass was attempted. **Verdict: NO_WRITE,
correct — not a stall.**

## ULTRALOOP audit
Ran via the Workflow tool (ultracode opt-in, user-invoked). Independent adversarial
verify agents (fresh context, did not write either finding above) re-derived the
okeechobee regex fix, re-ran the live RPC, checked all 10 letters for regressions, and
independently re-curled both liberty pages plus the two gated sources. See
`gold_standard_ultraloop_audit` rows for `dispatch_id=d18e7a2f-9a29-4041-83dc-13faa40898d7`.

## Session close-out
See `gold_standard_campaign` row update for this dispatch_id.
