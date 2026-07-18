# GOLD STANDARD SHARD-3 — SECOND CONTINUATION (SEMINOLE 10/10)
Dispatch: `26f01b9b-e405-422e-9908-229f26e0ae5a` · chat_session `architect-20260718T160000` · 2026-07-18

This is a further same-day continuation, picking up the first continuation's
(`..._CONTINUATION_ADDENDUM.md`, commit `36827a12`) "next-session priorities"
list, which left seminole at 9/10 (I failing) and marion/franklin/liberty
re-confirmed blocked for a third time.

Per this dispatch's ULTRALOOP protocol, the seminole claim below was put
through an independent adversarial verifier (fresh context, `/effort
ultracode` Workflow fan-out, `ultraloop_mode='fallback'` since native
ultracode workflow mode was not offered in this session) before being
written up. **Verdict: SURVIVES** — full refuter reasoning in
`gold_standard_ultraloop_audit` and quoted below.

## Live before/after (`pencil_dod_evaluate_county`, this continuation)

### seminole — **9/10 → 10/10, real improvement (I fixed, adversarially verified)**
```
before: A=P(11) B=P(100.0) C=P(100.0) D=P(100.0) E=P(98.1) F=P(100.0)
        G=P(96.9) H=P I=F(91.4, 96/105) J=P(100.0)
after:  A=P(11) B=P(100.0) C=P(100.0) D=P(100.0) E=P(98.1) F=P(100.0)
        G=P(97.1) H=P(4.0) I=P(97.1, 102/105) J=P(100.0)  =>  10 of 10 PASS
```
Migration: `supabase/migrations/20260718n_gold_standard_shard3_seminole_i_parcel_zones_scpafl_recordcard_run26f01b9b.sql`
(checked in, commit `5a9edd9a`).

### marion, franklin, liberty — unchanged, re-confirmed genuinely blocked (4th session)
```
marion:   9/10 (G FAIL, density=100.0 far=100.0 pk1000=0.0)
franklin: 8/10 (B/F FAIL, closed_sold=0)
liberty:  7/10 (A/B/F FAIL, fc=1 td=0, closed_sold=0)
```

## What was fixed (seminole I)

Root cause (unchanged from the first continuation's diagnosis): 6 real-parcel
auction rows had no `parcel_zones` coverage, and all 3 previously-tried GIS
endpoints for Seminole County are dead from this sandbox (`gis.scpafl.org`
connection reset, `seminolearcgis.seminolecountyfl.gov:6443` timeout, and a
same-name-collision Pinellas FeatureServer).

**New working avenue found this session**: the Seminole County Property
Appraiser's own record-card PDF export,
`https://parceldetails.scpafl.org/ParcelPdf.ashx?PID=<parcel_id_no_dashes>`
— a distinct host from the blocked GIS servers, returns HTTP 200 /
`application/pdf`. Fetched all 6 target parcels' cards, extracted the
`Zoning` field verbatim via `pypdf`, and cross-checked jurisdiction via the
card's `Tax District` field (not the mailing address — 3 of the 6 parcels
carry a Winter Park / Lake Mary / Altamonte Springs postal address that the
Tax District field proves is actually Casselberry or unincorporated Seminole
County, a mailing-address false lead of exactly the kind this dispatch's
prior sessions already warned about with the Pinellas name collision).

| parcel_id | postal city (misleading) | Tax District (real) | jurisdiction | zone_code |
|---|---|---|---|---|
| 36-20-29-508-0X00-0220 | Longwood | 01-COUNTY-TX DIST 1 | Unincorporated (636) | R-1AA |
| 34-21-30-530-0000-1110 | Winter Park | C1-CASSELBERRY | Casselberry (850) | RMF-13 |
| 36-19-30-524-0600-0010 | Sanford | S1-SANFORD | Sanford (904) | SR-1 |
| 26-19-30-504-0000-0010 | Sanford | S1-SANFORD | Sanford (904) | MR-2 |
| 36-19-29-5NH-0000-0230 | Lake Mary | 01-COUNTY-TX DIST 1 | Unincorporated (636) | PD |
| 08-21-29-508-0A00-0020 | Altamonte Springs | 01-COUNTY-TX DIST 1 | Unincorporated (636) | R-1A |

All 6 zone codes matched **exactly**, byte-for-byte, to `zoning_districts`
rows that already existed for the correct jurisdiction (sourced in prior
sessions from real GIS/ordinance data) — no new districts or standards
fabricated, only a `parcel_zones` link.

HONESTY MARKER: VERIFIED — zone_code and jurisdiction both sourced directly
from the county property appraiser's official record card for this exact
parcel_id.

3 of the original 9 gap rows remain incomplete, left honestly incomplete
(not fabricated): 2 rows have `parcel_id IS NULL` entirely, 1 carries a
`SYN-SEM-<case_number>` synthetic placeholder. 102/105 (97.1%) still clears
the 95% bar without them.

## Adversarial verification (independent refuter, fresh context)

Verdict: **SURVIVES**. The refuter did not just re-read my citations — it
independently re-derived the result from different sources:
- Queried `parcel_zones` and called `pencil_dod_evaluate_county('seminole')`
  live itself (didn't trust my pasted numbers).
- Pulled the evaluator function's actual SQL via `pg_get_functiondef` and
  hand-recomputed the card_complete/card_rows arithmetic.
- Independently verified the two Sanford zone codes against **Sanford's own
  live ArcGIS Zoning MapServer** (`gis.sanfordfl.gov/server/rest/services/
  Zoning/MapServer`), queried by parcel lat/lon — confirmed `ZONECODE=SR1`
  and `ZONECODE=MR2` exactly, and confirmed Sanford's own GIS truncates to
  "SR1" with no dash/suffix, ruling out the SR-1 vs SR-1A vs SR-1AA
  ambiguity concern.
- Independently verified all 4 non-Sanford jurisdiction assignments against
  **FDOT's statewide City Limits layer** (an entirely different source from
  the Tax District field or the record-card PDFs) — all 4 matched.
- Checked for duplicate-row / denominator-gaming risk — none found.

Residual caveats noted by the refuter (non-blocking): could not
independently re-verify the 3 unincorporated zone codes (R-1AA/PD/R-1A)
against a live unincorporated-Seminole zoning GIS layer (none reachable in
the session), and could not re-fetch the source PDFs itself (used
independent corroborating sources instead, which it assessed as an
equal-or-stronger verification method).

Audit rows: `gold_standard_ultraloop_audit` now has `survived=true` rows for
all 10 letters (A/B/F/H/J re-confirmed unchanged-PASS this session; C/D/E/G/I
already covered by earlier same-day sessions) within the certify gate's
7-day window.

## Marion G — 4th consecutive confirmed-blocked session, with a new structural finding

Independent fresh-context retry (new angles only — did not repeat the 3
previously-blocked paths):
- `library.municode.com` direct section permalink → still HTTP 403
- `marioncounty-fl.elaws.us` (with/without `www.`, http/https) → still
  ECONNRESET / HTTP 503 on all variants
- `marionfl.org`'s own LDC landing page → HTTP 403
- Two previously-untried PDFs (`marionfl.org/Home/ShowDocument?id=5855`,
  `tranzon.com/.../dg904_zoning_13561.pdf`) → both Article 4 (use tables,
  dimensional standards), not Article 6 parking — same wrong-document
  category as before
- Wayback Machine → tool-level blocked for this agent, could not attempt

**New finding, worth carrying forward**: the dispatch brief's framing of
"B-2 General Business district" is itself a misnomer for Marion County.
Verified via `pa.marion.fl.us`'s zoning glossary and LDC §4.2.18's own
title: Marion's B-2 is named **"Community Business,"** not "General
Business" (there is no district named "General Business" in Marion's code
at all — B-4 is Regional Business, B-5 is Heavy Business). This likely
explains why earlier sessions' searches for "B-2 General Business" kept
surfacing wrong-county or generic-template documents.

Further (INFERRED from search snippets only, not confirmed against table
text): Marion's Table 6.11-5 ("Minimum Off-Street Parking Requirements for
Nonresidential Land Use") appears organized **by land-use type**, not by
zoning district — meaning there may be no single "B-2 parking ratio" at
all; the applicable ratio would depend on which of B-2's ~200+ permitted
uses occupies the specific site. If this holds, the metric itself needs
re-scoping before another session spends budget hunting for a number that
doesn't exist in the form the brief assumes.

No number fabricated or estimated in either case.

## Franklin + Liberty B/F — not re-checked this continuation

Per this dispatch's own explicit guidance ("Do not re-check again until a
materially new signal exists") and the third consecutive identical
confirmation already on record (07-10, 07-11, 07-18 earlier today) — no
budget spent here this continuation.

## SQL VERIFICATION

```sql
-- seminole, live via rpc/pencil_dod_evaluate_county, 2026-07-18T19:35Z:
SELECT public.pencil_dod_evaluate_county('seminole');
-- I: {"pass": true, "detail": "card_complete=102 of 105", "metric": 97.1}
-- Full row: A=P(11) B=P(100.0) C=P(100.0) D=P(100.0) E=P(98.1) F=P(100.0)
--           G=P(97.1) H=P(4.0) I=P(97.1) J=P(100.0)  =>  10 of 10 PASS

SELECT public.pencil_dod_evaluate_county('marion');
-- G: {"pass": false, "detail": "density=100.0 far=100.0 pk1000=0.0", "metric": 0.0}
-- 9 of 10 PASS (G only failure) — unchanged, 4th confirmation

SELECT public.pencil_dod_evaluate_county('franklin');
-- 8 of 10 PASS (B, F FAIL, closed_sold=0) — unchanged, not re-checked

SELECT public.pencil_dod_evaluate_county('liberty');
-- 7 of 10 PASS (A, B, F FAIL) — unchanged, not re-checked
```

## Certification status

Seminole is live 10/10 as of this continuation's writes. Per this
campaign's rules, "a county is NOT done until gold_standard_scoreboard
shows 10/10; certification lands automatically after the second consecutive
10/10 daily 07:30Z run" — this continuation did not manually run
`gold_standard_loop()`/`gold_standard_certify()` (PARALLEL-FLEET RULES:
other shards' commits landed on `origin/main` during this session,
confirming concurrent activity; the scheduled loop/cert cron will pick up
this write on its next automatic pass). `gold_standard_ultraloop_audit` is
fully populated for all 10 letters to satisfy the SQL certify gate whenever
that automatic run occurs.

## Next-session priorities (this shard)

1. Marion G: **re-scope the ask** before another session burns budget —
   confirm whether Table 6.11-5 is genuinely use-keyed (not
   district-keyed) by finally getting eyes on the actual table (Firecrawl
   credit restore, a different network egress, or a direct call to Marion
   County Growth Services 352-438-2600 per two sessions' now-standing
   recommendation), and if so, define what "the B-2 parking ratio" should
   even mean for this metric before searching for a number again.
2. Franklin/Liberty B/F: still accrual-blocked, do not re-check without a
   new signal (a new `auction_date` passing, or a clerk `modified`
   timestamp updating).
3. Liberty A: still structurally blocked (no online tax-deed tenant for
   Liberty County); lowest-leverage item in this shard.
4. Seminole: fully PASS. No further shard-3 action needed unless a
   regression is detected on a future run.
