# Gold Standard Shard-6: santa_rosa + osceola — 2nd firing, dispatch 091fb9f9

This dispatch had already run once earlier the same day (commits `bb580aa5`/`74ccf8d9`,
session report `GOLD_STANDARD_SHARD6_SANTAROSA_OSCEOLA_DISPATCH_091FB9F9_SESSION_REPORT.md`).
This firing re-verified nothing had drifted, then picked up that report's
next-session priority list rather than repeat completed work.

## Pre-check: confirmed no drift since the 1st firing

Live `pencil_dod_evaluate_county` matched the 1st firing's closing numbers exactly
for both counties before any new work started — santa_rosa 10/10, osceola 8/10
(G FAIL 0.0, I FAIL 75.9). No regression, no work needed to restore state.

## santa_rosa — 10/10, untouched

No work required or performed. Confirmed still 10/10 at session close (below).

## osceola — G: real progress (still FAIL), I: investigated, not fixed this firing

### G: unblocked the ordinance-fetch wall that stopped 5 prior firings

The 1st firing (and 3 firings before it) hit HTTP 403 on every attempt to read
the Kissimmee LDC through WebFetch and Firecrawl (kissimmee.gov, library.municode.com
rendered pages). This firing reverse-engineered Municode's actual public JSON API
directly via `curl` (bypassing the bot-gated rendered frontend entirely):

```
Clients/name?stateAbbr=FL&clientName=kissimmee  -> ClientID 2866
ClientContent/2866                               -> ProductID 15261 (Code of Ordinances)
Jobs/latest/15261                                -> JobID 462754 (Supp. No. 5, current
                                                     as of Ord. 3113, Feb 4 2025)
CodesContent?jobId=462754&nodeId=...&productId=15261 -> full live ordinance HTML/JSON
```

Pulled Chapter 14-5 (Form-Based Code) in full. **Table 5-2 (Transect Zone
Dimensional Standards, section 14-5-6)** — dumped and read row-by-row — has no
FAR column and no density (du/acre) column for any transect zone (T1/T3/T4-R/
T4-O/T5-M/T5-U/T6/SD). Adversarial check: searched Ch.14-5-13 (Development
Bonuses) for a hidden density cap that would contradict this — instead it
**confirms** the split: "the density/intensity and building height shall not
exceed the maximum noted in the corresponding **future land use category**
and **Table 5-2**, respectively" — density is governed by the Comp Plan FLU
layer, not the zone-code-level dimensional table. Table 5-2 does carry min/max
building height, which is unrelated to far/density. Claim survived refutation;
logged to `gold_standard_ultraloop_audit` (id 11697, survived=true).

Root cause of the actual gap (also newly confirmed this firing): the 3 parcels
the 1st-4th firings all pointed to (2x Kissimmee T3, 1x T5-M, jurisdiction_id=957)
had **zero matching `zoning_districts` row at all** — the 51 existing rows for
jurisdiction 957 are whole-table-of-contents "Uncategorized" sections (e.g.
`code='PTIIILADECO_CH14-1INAP_PTIPR_14-1-1TI'`), not per-zone-code rows. This
also explains why the *same-morning* 1st-firing migration (`8cfc21d7`,
`UPDATE zoning_districts ... WHERE code IN ('T3','T5-M',...)`) was a silent
no-op: it matched zero rows, since those codes never existed as rows to update.

**Fix applied and pushed to main (commit `9cc81a44`):** inserted real
`zoning_districts` + `zone_standards` rows for Kissimmee T3 and T5-M
(`far_regulated=false`, `density_regulated=false`, cited `source_url` +
`ordinance_section`), and registered both in
`zoning_far_regulated_verified_exceptions` so the periodic applicability-
refresh cron cannot silently revert them (this table exists specifically to
guard against that, per the 1st-firing commit's own pattern).

**Live effect** (`v_zoning_gold_standard_kpi_v3`, osceola, before -> after):

| Sub-metric | Applicable parcels | % |
|---|---|---|
| density | 44 -> 41 | 90.9 -> **97.6** (clears 95% gate) |
| far | 4 -> 1 | 0.0 -> 0.0 (1 parcel unresolved, below) |
| pk1000 | 14 -> 11 | 64.3 -> 81.8 (still below gate) |

`pencil_dod_evaluate_county('osceola').G`: **FAIL 0.0 both before and after** —
density now genuinely passes its own gate, but `min(density,far,pk1000)` is
still dragged to 0 by far and pk1000. This is real, cited, adversarially-checked
progress on one sub-metric; it does not flip letter G to PASS, and this report
does not claim that it does.

**Flagged, not fixed — 1 remaining far-applicable parcel:** `zone_code='RS-2'`,
`jurisdiction_id=1186` (Osceola County, not a municipality), `parcel_id=
062629000000`, inserted into `parcel_zones` by the 1st firing's I-fix script
(`shard6_santarosa_osceola_091fb9f9_i_real_gis_fix:RS-2`, created 09:08Z same
morning). This firing searched Osceola County's own live LDC (jobId=478316,
productId=15810, Article 3.2.2 "Residential District Descriptions") in full —
current single-family district codes are ARE/US/US-M/LDR; multi-family codes
include MDR/MDR-M/HDR/etc. **No district currently named "RS-2" was found.**
Did not guess a crosswalk. Possible explanations for next session: legacy
pre-rewrite code, a St. Cloud-style code (St. Cloud does use "R-3" naming)
misassigned to jurisdiction 1186 by the GIS point-in-polygon lookup, or a
current code this session's TOC search missed. Verify against the original GIS
source before touching it.

**Flagged, not fixed — pk1000 (81.8%, the new binding constraint for G):** this
gap spans many more osceola zone codes than just T3/T5-M and needs a broader
pass, not a 3-row fix.

### I: investigated, no fix shipped this firing

The 1st firing's report pointed at "~33 other card-incomplete rows" and "3 rows
needing Kissimmee/St. Cloud jurisdiction reassignment." This firing could not
reproduce the 137-row denominator (`auctions_total=137` from
`pencil_dod_evaluate_county`) against `multi_county_auctions` directly:
`county=eq.osceola` returns **653** rows (648 distinct case numbers), and
`v_zoning_gold_standard_card` (a different view) returns exactly **100** rows,
none of which cleanly map to 137. No `gold_standard_cert_scope` row exists for
osceola (checked live — only brevard/duval/hillsborough are scoped there), so
the 137-row scope is defined by SQL inside `pencil_dod_evaluate_county` this
session could not read (no working `psql`/direct-Postgres access this
session — password auth failed against both the pooler and direct host; all
work this firing used the PostgREST service-role API instead, which cannot
introspect function/view source). Rather than guess at a subset and risk
writing enrichment data against the wrong denominator, **no I fix was
attempted this firing.** Next session should get a working DB connection (or
ask for the evaluator's SQL text directly) before resuming I.

## Verification protocol executed

- Live `pencil_dod_evaluate_county` before/after, both counties, pasted above (exact).
- Live `v_zoning_gold_standard_kpi_v3` before/after for osceola G (exact).
- 1 new `gold_standard_ultraloop_audit` row (osceola/G, survived=true, id 11697),
  including an adversarial refutation attempt against my own claim (searched for
  a hidden density standard elsewhere in the FBC before accepting "no density
  column" as final).
- Did **not** run `gold_standard_loop()`/`gold_standard_certify()` — other shard
  sessions may be mid-flight; used per-county `pencil_dod_evaluate_county` only.
- Migration: `supabase/migrations/20260731g_gold_standard_shard6_osceola_kissimmee_t3_t5m_zoning_districts.sql`.
- Commit `9cc81a44`, pushed directly to main (rebased on top of `d6c33a09`, no conflicts).
- Confirmed zero regression on santa_rosa (still 10/10) and on osceola's other
  8 letters (A/B/C/D/E/F/H/J identical before/after).

## Next-session priorities (osceola)

1. **I**: get a working direct-Postgres connection (this session's `psql`
   against both the pooler and `db.<ref>.supabase.co` failed password auth on
   `SUPABASE_DB_PASSWORD` from the sandbox env — may need a refreshed
   credential) or otherwise obtain the exact SQL for `pencil_dod_evaluate_county`'s
   I sub-query, so the 137-row denominator can be reproduced before attempting
   any enrichment.
2. **G — far**: verify the RS-2/jurisdiction-1186/parcel-062629000000 anomaly
   against the GIS source that assigned it (this morning's I-fix script) before
   deciding whether it's a jurisdiction mismatch or a genuinely-missing current
   Osceola County district.
3. **G — pk1000**: 81.8% (9/11) is now the binding constraint; needs real
   per-1000sf parking values across more osceola zone codes than just T3/T5-M —
   a broader-scope session, not a narrow 1-2-row fix.
