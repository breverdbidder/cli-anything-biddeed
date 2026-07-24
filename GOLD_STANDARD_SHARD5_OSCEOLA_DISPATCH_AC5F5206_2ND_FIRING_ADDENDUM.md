# Gold Standard Shard-5: osceola — dispatch ac5f5206, 2nd firing addendum

dispatch_id: `ac5f5206-a862-494e-a345-f6b0eb4cbd09`
chat_session: `architect-20260724T000000` (2nd invocation, same dispatch)
loop run: 6080

This dispatch already ran once today (commits `478c781b`/`529decfb`/`6d302230`, session report
`GOLD_STANDARD_SHARD5_OSCEOLA_DISPATCH_AC5F5206_SESSION_REPORT.md`). This addendum documents the
2nd firing, which used the ULTRACODE workflow tool per the ULTRALOOP protocol.

## Live state at start of this firing (re-verified, no drift from the 1st firing's "after")

```json
{"A":"PASS 5","B":"PASS 100.0","C":"PASS 100.0","D":"PASS 100.0","E":"PASS 100.0",
 "F":"PASS 100.0","G":"FAIL 0.0 [density=97.4 far= pk1000=0.0]","H":"PASS 8.7-10.1",
 "I":"FAIL 78.4 [card_complete=105 of 134]","J":"PASS 96.3"}
```

## Finding 1: ghost-success purge (honesty correction, not new fabrication)

The reported I=78.4% (105/134) rested in part on a data-integrity bug from an **earlier,
different session** (2026-07-20T06:03:59Z, unrelated to today's dispatch): 407 `parcel_zones`
rows tagged `shard4_run5153_osceola_i_default:INCORP_or_nomatch` — a blanket `PD` zone-code
default that `scripts/shard4_run5153_osceola_i_enrichment.py`'s own docstring explicitly flags
as fabrication risk and claims (as of 2026-07-19T16:40Z) was "verified NOT executed." It was
executed the next day anyway.

Live re-query of `gis.osceola.org`'s Zoning_Parcels layer (the same source that script uses)
reconfirmed 0 of 21 sampled affected parcels resolve to `PD` — they return `PRIM_ZON='INCORP'`,
meaning they sit inside a municipality (Kissimmee/St. Cloud), not unincorporated jurisdiction
1186 where `PD` would apply. **12 of the reported 105 "complete" I rows rested on this fake
linkage.**

Purged. G unaffected (all 407 rows were already `density_regulated=false`/`far_regulated=false`
per today's 1st firing's own fix — verified before/after, density stayed 97.4%).

```
True I baseline: 78.4% (105/134) -> 69.4% (93/134)
```

## Finding 2: real fixes via ULTRACODE workflow (wf_0b9ac007-46a), adversarially verified

Purging surfaced 36 real-parcel-id rows still blocking I. Of these, 5 had full, unambiguous
18-digit-style parcel IDs (the other ~31 are genuinely truncated/ambiguous and were already
correctly declined by prior sessions — not re-attempted). Fanned out two research agents
(Kissimmee zoning, St. Cloud zoning) plus a PDF-parse agent for 5 synthetic-ID rows, each
finding independently adversarially re-verified by a dedicated refuter agent before any write.

**4 of 5 zoning findings survived** (single, unambiguous real zone code from the correct
municipal GIS authority — Osceola County's own unincorporated-only layer correctly returns
`INCORP` for all of these, so the county layer is not authoritative here):

| parcel_id | case | zone | source |
|---|---|---|---|
| 192529124700010570 | 33562023 | SRPUD | Kissimmee ArcGIS Zoning_Districts/10 |
| 22252900U001240000 | 46102019 | T3 | Kissimmee ArcGIS Zoning_Districts/10 |
| 2225291050000J0015 | 37132023 | T3 | Kissimmee ArcGIS Zoning_Districts/10 |
| 262630061300011440 | 46572023 | R-3 | St. Cloud's own ArcGIS Zoning FeatureServer |

**1 of 5 declined**: parcel 192529000002250000 (case 38582021, Buckley Dr) genuinely straddles
3 Kissimmee districts (AI/RA-1/OS) per exact polygon intersection on both of its disjoint
narrow-strip rings — writing a single code would be a guess. Left correctly unresolved.

Geo + assessed/market value backfilled for all 4 via FL GIO exact `PARCEL_ID` match (real data,
COALESCE-guarded so nothing pre-existing was overwritten).

**2 of 5 PDF-address findings survived** (clerk docket itself was auth-gated and couldn't be
independently re-fetched byte-for-byte, but each survived on independent 2-3 point corroboration
from an unrelated source — FL property appraiser owner+address+legal-description match, or
independent legal-notice + listing cross-check):

| case | address | corroboration |
|---|---|---|
| 2011 CA 003872 MF | 403 Sea Willow Drive, Kissimmee FL 34743 | legal-notice + listing sites, legal description match |
| 2019 CA 000153 MF | 4899 Sparrow Dr, Saint Cloud FL 34772 | FL property appraiser: owner name + address + subdivision 3-point match |

**3 of 5 PDF-address findings refuted** (docket auth-gated, no independent source could
reproduce the case-number-to-address linkage) — not written: 2025 CA 001061 MF, 2025 CA 001721
MF, 2025 CA 002509 MF. These 2 address writes alone didn't move I (still missing geo/value/zone
for those synthetic-ID rows) but are real, usable progress for a future session's address-match
pass.

## After (live, `SELECT public.pencil_dod_evaluate_county('osceola')`)

```json
{
  "A": {"pass": true, "metric": 5, "detail": "fc=5 td=129"},
  "B": {"pass": true, "metric": 100.0, "detail": "verified=40 closed_sold=40"},
  "C": {"pass": true, "metric": 100.0, "detail": "matched_clean=134"},
  "D": {"pass": true, "metric": 100.0, "detail": "matched_any=134"},
  "E": {"pass": true, "metric": 100.0, "detail": "parcel_linked=134"},
  "F": {"pass": true, "metric": 100.0, "detail": "tier1_sold=40 closed_sold=40"},
  "G": {"pass": false, "metric": 0.0, "detail": "density=88.1 far=0.0 pk1000=0.0"},
  "H": {"pass": true, "metric": 10.8, "detail": "hours since last_seen (SLA 48h)"},
  "I": {"pass": false, "metric": 72.4, "detail": "card_complete=97 of 134"},
  "J": {"pass": true, "metric": 96.3, "detail": "deal_complete=129 ..."},
  "county": "osceola", "auctions_total": 134
}
```
8/10 (G, I FAIL). **I: true 69.4% -> 72.4% this firing** (105->93 corrected, then 93->97 real
gain). Not a certification.

## Honest side effect: G detail regression, pass/fail unchanged

Adding real T3/SRPUD/R-3 zoning coverage exposed that Kissimmee's `zoning_districts` table has
**zero real per-district density/FAR/parking standards** (its 49 existing rows are Municode
table-of-contents navigation artifacts — chapter/section titles, not zone codes like R-1/C-2)
and St. Cloud's `zoning_districts` table is empty. This moved G's density sub-metric 97.4% ->
88.1% and revealed FAR at 0.0% (previously unmeasured/null, since 0 applicable parcels existed
before). **G's overall pass/fail and reported "metric" field were already 0 either way** — bound
by `pk1000=0.0` before and after — so this is a detail-level regression only, not a pass/fail
regression, and not something to revert (the underlying data is real; the gap it reveals is
real and correctly surfaced).

**G pk1000 re-confirmed structurally blocked** (3rd time this campaign): Osceola LDC Table
4.7.8 off-street parking is use-keyed (retail/restaurant/hotel/etc.), not zone-keyed, with no
CT/CR-specific override. Writing one number per zone would be fabrication. Declined.

## Residual (honestly unresolved, not fabricated)

1. **I, ~26 rows**: truncated 12-digit-or-shorter parcel IDs with no unambiguous GIS match
   (2-1,500+ candidate features per prefix search) — re-confirmed ambiguous this session,
   consistent with 2 prior sessions' identical finding. Needs a different disambiguation method
   (e.g. cross-referencing the clerk's original source PDF/legal description) to resolve.
2. **I, 3 rows**: PDF-address claims that couldn't be independently corroborated this session
   (2025 CA 001061/001721/002509 MF) — docket portal is auth-gated; retry with an authenticated
   session or a different source next time.
3. **I, 1 row**: parcel 192529000002250000 is a genuine multi-district straddle (AI/RA-1/OS) —
   needs a policy decision (e.g. "primary/dominant use" convention) before it can carry a single
   zone_code, not a data problem.
4. **G density/FAR, new gap**: Kissimmee (957) and St. Cloud (894) `zoning_districts` need real
   per-code density/FAR/parking standards ingested from municipal ordinance text (Kissimmee LDC
   Ch. 14-4/14-5 SmartCode for T3/SRPUD; St. Cloud UDC for R-3) — currently 0% coverage for both
   jurisdictions beyond the 4 zone_code rows added this session.
5. **G pk1000**: structurally blocked per-parcel use-code mapping, same as 1st firing's finding —
   needs a schema/view change to support per-parcel override, out of scope for a PostgREST/Mgmt-API-only session.

## Method notes

- Used the Workflow tool (ULTRACODE) for the letter-I research: 3 parallel research agents
  (Kissimmee zoning, St. Cloud zoning, PDF-parse), each finding independently adversarially
  verified by a dedicated refuter agent before any DB write. 4/5 zoning findings and 2/5 PDF
  findings survived; the rest were correctly declined.
- All DB writes went through the Supabase Management API (`mgmt_sql.py`) rather than
  `supabase db push` / psql pooler — pooler auth confirmed stale again this session (`password
  authentication failed`), consistent with prior sessions' notes.
- 10 `gold_standard_ultraloop_audit` rows logged this firing (dispatch_id
  `ac5f5206-a862-494e-a345-f6b0eb4cbd09`) covering the letter-I research: 6 `survived=true` (4
  zoning fixes + 2 address fixes) and 4 `survived=false` (1 multi-district-straddle correctly
  declined + 3 address claims that couldn't be independently corroborated). The ghost-purge
  correction itself was logged separately earlier in the session as an additional row.

## Next-session priorities for osceola

1. I: cross-reference the ~26 truncated-parcel-id rows against the original clerk source PDF's
   legal descriptions (not GIS prefix search, which is confirmed ambiguous) to disambiguate.
2. I: retry the 3 refuted PDF-address cases with an authenticated clerk-docket session.
3. I: decide a convention for multi-district-straddle parcels (192529000002250000) — e.g. use
   the plurality-area zone with an explicit `multi_zone=true` flag, if the schema supports it.
4. G: ingest real per-code density/FAR/parking standards for Kissimmee T3/SRPUD and St. Cloud
   R-3 from municipal ordinance text — now that real zone_code linkage exists for these 4 rows,
   this is the fastest path to G gain.
5. G pk1000: still needs the per-parcel use-code schema/view change flagged twice before.
