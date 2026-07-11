# Gold Standard shard-13 — lee — session report

dispatch_id: `61454491-3b8a-4b0c-8c92-1f17041cc821`
chat_session: `architect-20260711T160000`
county: **lee** (loop run 3786 assignment: A,B,F,G,H,J PASS; C,D,E,I FAIL)

## Outcome: net regression on I, caught and mostly remediated. C/D unchanged (honest zero). No fleet certification contaminated.

This session used a background Workflow (3 parallel fix agents + 4 adversarial
per-letter refuters) to attack lee's four failing letters. The refuter layer did
its job — it caught a real regression that the fix agents' own self-report missed
— but the regression was only partially recovered before session close. Reporting
this in full per the campaign's evidence-before-claims mandate rather than
rounding it up to a win.

## Before / after (`SELECT public.pencil_dod_evaluate_county('lee')`)

| Letter | Baseline (session start) | After fix agents (pre-verify) | Final (post-remediation) |
|---|---|---|---|
| A | PASS 38 (fc=235 td=38) | unchanged | unchanged |
| B | PASS 100.0 | unchanged | unchanged |
| C | FAIL 91.9 (matched_clean=251/273) | FAIL 91.9 (unchanged) | **FAIL 91.9 (unchanged)** |
| D | FAIL 91.9 (matched_any=251/273) | FAIL 91.9 (unchanged) | **FAIL 91.9 (unchanged)** |
| E | FAIL 93.8 (parcel_linked=256/273) | FAIL 93.4 (255/273) | **FAIL 93.4 (255/273)** |
| F | PASS 100.0 | unchanged | unchanged |
| G | PASS 97.8 (density=97.8) | **FAIL 0** (far=25.0 pk1000=0.0), then agent "reverted" to PASS 97.4 | **PASS 97.5** (density=97.5, far/pk1000 N/A again) |
| H | PASS 5.8h | unchanged | unchanged |
| I | FAIL 89.7 (card_complete=245/273) | **FAIL 73.3** (200/273, after mis-scoped revert) | **FAIL 79.5** (217/273, partially recovered) |
| J | PASS 100.0 | unchanged | unchanged |

Final live state (2026-07-11, this session):
```json
{"A":{"pass":true,"metric":38},"B":{"pass":true,"metric":100},
 "C":{"pass":false,"metric":91.9,"detail":"matched_clean=251"},
 "D":{"pass":false,"metric":91.9,"detail":"matched_any=251"},
 "E":{"pass":false,"metric":93.4,"detail":"parcel_linked=255"},
 "F":{"pass":true,"metric":100},
 "G":{"pass":true,"metric":97.5,"detail":"density=97.5 far= pk1000="},
 "H":{"pass":true,"metric":0.3},
 "I":{"pass":false,"metric":79.5,"detail":"card_complete=217 of 273"},
 "J":{"pass":true,"metric":100},"auctions_total":273}
```

## C/D: genuine, honest zero (no regression, no gain)

Reused `scripts/gold_standard_shard10_lee_cd_e_i_ajax_harvest_run3679.py` verbatim
against the 22 `parity_status='mca_only'` rows (8 on 2026-06-25, 5 on 2026-07-09,
9 on 2026-07-30 — all sourced from a 2026-06-27 clerk-calendar supplementary
backfill that never went through a genuine RealAuction match). Re-harvested all
three dates live: RealForeclose returned real, populated calendars (34/40/27
items) but **none of the 22 target case numbers appeared on them**, including the
07-09 and 07-30 dates expected to be current/live. Fail-loud, zero fabricated
matches, zero DB writes. HYPOTHESIS (not verified): the clerk-calendar backfill's
`auction_date` may not match the date RealAuction currently shows for these cases
(reschedule/cancellation). Residual: needs either a date-correction pass or an
alternate tier1 source — out of scope this session.

## E: honest -0.4pt (ghost-row correction, not a regression)

One row (`25-CA-001853`) had the literal garbage string `'MULTIPLE PARCEL'` as its
`parcel_id` — not a real STRAP, and confirmed to be spuriously matching unrelated
garbage `parcel_zones` rows from other counties via a coincidental literal-string
join. Nulling it (correct behavior) dropped `has_parcel` from the previously
overstated 256 to the honest 255. No replacement parcel was found for this case
this session (see "hard remainder" below) — flagged, not fabricated.

## I: the incident — what happened, what was caught, what was recovered

The E/I fix agent ran the proven `scripts/lee_enrich_shard14.py` (unmodified) plus
an ad hoc "pass 2" ArcGIS zone-insert for 188 additional STRAPs. That insert
tripped a genuine G regression (new commercial/mixed-use zone codes with no
`zone_standards` FAR/parking data). The agent correctly detected this and
reverted — but the revert command,
`DELETE FROM parcel_zones WHERE source IN ('lee_shard13_run3786_pass2', 'lee_arcgis_2026_shard14', 'lee_arcgis_2026_shard14_addr')`,
was scoped by source-tag name only. `lee_arcgis_2026_shard14` was **also** the
source tag used by the original historical backfill that built lee's G criterion
to 97.8% in a prior session — so the revert deleted 45 legitimate, pre-existing
`parcel_zones` rows along with the 159 bad ones it meant to remove.

This was caught by the adversarial verify phase (both E and I refuters
independently found the metric moved the wrong direction and correctly refused to
certify — **zero false rows were written to `gold_standard_ultraloop_audit`**,
confirmed by direct query post-session).

**Remediation performed live in the main session after the workflow completed:**
1. Re-derived the exact 45-row candidate set (real-parcel lee canon rows missing
   a `parcel_zones` match, excluding the 10 case numbers already known pre-session
   to be a *different*, never-zoned gap) — count matched the deleted total exactly.
2. Re-queried the same Lee County ArcGIS Parcels FeatureServer
   (`services2.arcgis.com/.../Lee_County_Parcels/FeatureServer/0`) for all 45
   STRAPs — 45/45 matched with real zoning.
3. Inserting all 45 reproduced the G regression (far=25.0, pk1000=0.0 — FAIL),
   because 34 of the 45 landed in jurisdiction_id 929/815/914 (Fort
   Myers/Cape Coral/Bonita Springs), not jid=630 (unincorporated) — a
   wrong-jurisdiction-filter blind spot in this session's own pre-fix diagnostic
   query (only checked jid=630 plus a copy-paste list of *other counties'*
   jurisdiction IDs, never Lee's actual municipal jids: 815/914/912/929/942).
4. Root cause isolated via `zoning_districts.far_regulated`/`density_regulated`:
   jid=630 has every code explicitly `far_regulated=false` (a previously-vetted
   convention). The jid=929/815/914 codes (seeded by an earlier, unrelated
   backfill `lee_arcgis_2026_shard8`) mostly have these flags `NULL`, which
   `v_zoning_district_applicability` treats as "applicable, data missing" once a
   real parcel references them.
5. Kept only: the 11 rows that landed in jid=630 (confirmed-safe, confirmed
   original population), plus 6 more in jid=929/914 whose `zoning_districts` row
   already had an **explicit** `far_regulated=false AND density_regulated=false`
   (TFC-2 ×2, MDP-3 ×2, RV-2 ×1, TFC2 ×1 — verified via direct query, not
   inferred). Deleted the remaining 28 (all NULL-flagged jid=929/815 codes)
   rather than guess at their FAR/parking regulation status.

**Net result: G fully protected (PASS, 97.5% — 0.3pt below original 97.8% due to
the smaller-but-safe 17-of-45 restore vs the original unknown composition). I
recovered from the crashed 73.3% to 79.5% (217/273) — still 10.2pt below the true
89.7% pre-session baseline.** This session closes with I net-worse than it
started, despite the recovery effort. Not rounding this up.

## E hard remainder (12 rows, unresolved)

12 lee foreclosure rows have both `parcel_id` and `property_address` NULL with no
identifying data on the row (no owner/plaintiff/legal description stored). All
three investigated resolution paths dead-ended on a genuine, verified blocker:
Lee Clerk official records (`leeclerk.org`, `matrix.leeclerk.org`) is behind an
Akamai WAF that blocks plain HTTP fetch; 4 of the 12 have a stored RealForeclose
AID that resolves to a bidder-login-gated splash page (auth wall); no public
case-number search endpoint exists on `lee.realforeclose.com`. No fabricated data
written. Needs either RealAuction bidder credentials or a Playwright pass that can
clear the WAF's JS challenge.

## Residual / next-session priorities for lee

1. **G/I lever (real, scoped, safe path forward):** the 28 excluded `parcel_zones`
   rows (jid=929 Fort Myers: RM-2, RPD, PUD, RS-6, RS-7, MH-1, MH-2, NC, CG, AG-2;
   jid=815 Cape Coral: C, R-1B) need real Fort Myers / Cape Coral / Bonita Springs
   municipal LDC research to correctly set `far_regulated`/`density_regulated`
   (most likely `false` for the residential codes following the county-wide
   convention, but **not verified against each city's actual ordinance text — do
   not guess**). Once set and verified safe, re-insert the same 28 STRAPs
   (captured in this session's tool transcript) to recover the remaining ~10pt of
   I. This is a legitimate G-hardening task too (jid=929/815/914 currently have
   zero FAR/parking-safe zone coverage at all).
2. C/D: confirm/correct the true RealAuction `auction_date` for the 21 remaining
   `mca_only` rows (2026-06-25/07-09/07-30 batches) before re-harvesting, or find
   an alternate tier1 source.
3. E hard remainder: 12 rows need either RealAuction bidder credentials or a
   headless-browser pass against the Lee Clerk's WAF.

## Process note

The adversarial verify layer (independent per-letter refuters, skeptical-by-default,
required live re-derivation rather than trusting fix-agent self-reports) worked
exactly as designed — it caught a regression the fix agent's own "G restored to
PASS" self-report had incorrectly framed as a clean recovery. `gold_standard_ultraloop_audit`
confirms zero false-positive rows were written for lee this session. The gap this
report is flagging is that the *verify* layer caught the problem, but full
*recovery* to the original baseline required additional manual forensic work
(reconstructing the deleted 45-row set, bisecting by jurisdiction and
`far_regulated`/`density_regulated` flags) that went beyond the workflow's
original scope — worth building into the fix-agent playbook: **never `DELETE ... WHERE source = X` without a `created_at` time bound**, since source tags get
reused across sessions/years and are not a safe proxy for "rows I just inserted."
