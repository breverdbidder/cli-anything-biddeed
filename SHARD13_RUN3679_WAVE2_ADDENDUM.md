# SHARD-13 Wave-2 Addendum — pasco, escambia, wakulla, madison (run 3679)

- dispatch_id: `2234fc53-6114-414f-b890-a2f60a352330` (same dispatch, second wave — see note below)
- chat_session: `architect-20260711T000000`
- date: 2026-07-11

## Duplicate-dispatch note

This `dispatch_id` + `chat_session` was re-fired identically to the brief already closed out in
`SHARD13_RUN3679_PASCO_ESCAMBIA_WAKULLA_MADISON_SESSION_REPORT.md` (commit `29b492b9`, ~6 minutes
before this wave started). Live DB was checked first and confirmed that closeout's AFTER numbers
were still accurate with zero drift. Rather than re-run identical fixes (which would double-log
claims already in `gold_standard_ultraloop_audit`), this wave worked that report's own
"next-session-priorities" queue — the 6 items it explicitly left for whoever picks up shard-13 next.

## Headline

```
county     before (wave1)         after (wave2)          delta
pasco      10/10 GOLD             10/10 GOLD              unchanged, reconfirmed live
escambia   7/10  ABEFHIJ          8/10  ABEFGHIJ           G FIXED: far 4.3%->100%, FAIL->PASS
wakulla    6/10  ACDGHJ           6/10  ACDGHJ              unchanged — research-only, no writes
madison    6/10  CDEGHJ           6/10  CDEGHJ              unchanged — I fix self-flagged not-ready,
                                                             withheld from apply
```

## Method

Ran via Workflow tool (ultracode opt-in): 5 parallel research agents against the wave-1 report's
priority queue, then a 4-way independent adversarial-sourcing verification pass (one refuter per
surviving candidate, each re-fetching primary sources itself rather than trusting the researcher's
summary), then a single serial ship agent, then an independent final live audit. All 4 stages ran
as separate agent contexts per the ULTRALOOP protocol.

## What shipped

### escambia G — FIXED, FAIL (far=4.3%) → PASS (far=100%, density=100%)

**Root cause (mechanical, verified via direct SQL, no agent needed):** `v_zoning_district_applicability`
hardcodes `pk1000_applicable = false` for every zone_code that HAS a matching `zoning_districts` row,
but the KPI view's `COALESCE(a.pk1000_applicable, true)` defaults `true` when no `zoning_districts` row
exists at all. Escambia's 22 parcels on zone_codes HDMU (12), HDR (4), Com (3), HC/LI (3) — jurisdiction
1151, Escambia Unincorporated — had no `zoning_districts` row, so they defaulted into the pk1000
denominator with zero fill, driving `pk1000=0.0%`.

**Fix:** sourced real ordinance text for all 4 codes and applied live:
- HDR (Sec. 3-2.8): live-adopted text via a Wayback Machine snapshot of elaws.us (2023-05-28).
- HDMU (3-2.9), Com (3-2.10), HC/LI (3-2.11): two independent draft BCC ordinance PDFs (2015 "BCC
  12-10-15" and 2016 "BCC 08-04-16", hosted on ordinancewatch.com) whose overlapping HDR/MDR numbers
  agree with each other and with the live 2023 codified text — real triangulation across independently
  drafted documents, not circular citation of one source.
- LDR/MDR `far_regulated`: the prior wave's claim (zoneomics.com-sourced) was correctly refuted
  (`audit id=5414`). This wave found the real answer from primary ordinance text: Escambia's LDC is an
  exception to the FL norm and genuinely regulates FAR even for low/medium-density residential — LDR
  Sec. 3-2.5(d)(2) and the live-adopted MDR Sec. 3-2.7 both explicitly state a maximum FAR. Set
  `far_regulated=true` on both, confirmed correct, not the same claim as the refuted one (different
  source, independently corroborated by two agents).

**Confidence caveats, explicitly carried into the DB record, not hidden:** HDMU/Com/HC-LI numeric
values rest on unadopted BCC agenda drafts (ordinance number blank as "2015-____"), scored at
confidence 0.70–0.75 rather than 0.90+; HDR scored 0.90 (live-adopted source). Where the ordinance
publishes two FAR figures by Future Land Use category (e.g. 1.0 base / 2.0 in MU-U), the lower/base
value was stored conservatively, with the alternate flagged in `ordinance_section` text rather than
invented into a second column. Existing LDR/MDR `zone_standards` rows (ids 4182/4183) still carry
`source_url=zoneomics.com` and were NOT touched by this fix (only `far_regulated` was set) — a
zoneomics-free `zone_standards` for LDR/MDR remains a follow-up.

Migration: `supabase/migrations/20260711080118_escambia_g_wave2.sql`. Commit `a3932fef`.

**Adversarial verification: SURVIVED.** Independent refuter re-fetched all 5 distinct source URLs
itself (byte-count and text-content matches), confirmed zero pre-existing rows for jurisdiction 1151
(no duplicate-insert risk), line-by-line checked `proposed_sql` against sourced facts (no invented
numbers), and independently confirmed via Wayback CDX that no live-adopted alternative exists for
HDMU/Com/HC-LI — validating why draft-PDF sourcing was necessary and why confidence was honestly
lowered rather than overclaimed.

### escambia C/D — rerun, 0 new matches, valid confirmed result

Reran `scripts/shard_escambia_cd_taxdeed_fix.py` against `escambia.realtaxdeed.com`'s 5 known future
sale dates. Script harvested 60–61 live records per date (site fully reachable), but 0 of the
remaining 73 unmatched tax-deed rows had a case_number match this time — consistent with the prior
run 6 minutes earlier having already promoted the only 3 matchable rows out of that pool. C/D remain
FAIL at 77.7% (unchanged). **Adversarial verification: SURVIVED** — refuter independently reran the
script itself and got byte-identical harvest counts and the same 258/258 before/after DB state.

### wakulla — FL GIO CO_NO discrepancy discovered, no fix applied (research-only)

Diagnosed why FL GIO parcel queries for Wakulla have never worked: this repo's `fl_counties` table and
`consolidation_modal.py` use `CO_NO=65` for Wakulla, but FL GIO's own ArcGIS FeatureServer uses
`CO_NO=65` for **St. Johns County** — Wakulla's real FL GIO code is **75**, confirmed by `PHY_CITY`
sampling (65 → Ponte Vedra Beach/St. Augustine; 75 → Sopchoppy, plus Crawfordville-area
township/range parcel IDs). Separately confirmed the previously-reported "CO_NO equality hangs" issue
is not Wakulla-specific — it affects the polygon `Florida_Statewide_Cadastral` layer broadly, but the
sibling `Florida_Statewide_Parcel_Centroid_Version` layer answers `CO_NO=` filters reliably with retry.
Full pagination at `CO_NO=75` returned exactly 26,319 records.

**Not applied this wave, by design:** this is a diagnostic finding, not a data fix — `proposed_sql` was
intentionally empty. Two real blockers remain even with the CO_NO fix: (1) FL GIO's township/range
`PARCEL_ID` format doesn't match this repo's dash-delimited parcel_id format, so a crosswalk or
address-geocoding step is still needed; (2) the 7 unlinked auction rows have no parcel_id, address, or
legal description at all in `multi_county_auctions` — FL GIO has no case-number-to-parcel linkage, so
this alone doesn't unblock E. `mywakullapa.com` / `qpublic.schneidercorp.com` remain Cloudflare-403 to
both WebFetch and raw curl with a browser UA. Flagged as a real, corroborated lead for the next
session that attempts E, not a completed fix. **Adversarial verification: SURVIVED** as an honest
research finding — refuter independently reproduced the CO_NO=65-vs-75 discrepancy against the live
FL GIO API and confirmed the repo's own hardcoded `65:"WAKULLA"` via source grep.

Also rechecked `wakullaclerk.org` for the 19 past-due auctions flagged in wave-1: unchanged, still
pre-sale status, ~6 minutes after the last check — expected, honest no-change result, no write.

### madison I — genuine ordinance found, ADVERSARIAL SURVIVAL != SHIP, correctly withheld

Found the real Town of Greenville, FL Land Development Code (adopted 1992) hosted directly on the
town's own site (mygreenvillefl.com — bypasses the Municode 403 the prior session hit, since Municode
is just a mirror). This resolves the *ordinance-text* half of the blocker for the 5th parcel
(`204 SW Church Ave`, jurisdiction 1044). However, the *parcel-to-district spatial assignment* is not
resolvable from this document: Greenville's Official Zoning Atlas exists only on paper at the Town
Clerk's office (no online GIS/atlas). The research agent inferred a specific district (RMDC) from
DOR_UC + lot size — the same category of inference the prior session used for the other 4 Madison
parcels — but explicitly self-labeled this one `status=partial`, `confidence=0.55`, and put
`"DO NOT RUN AS-IS"` directly in the proposed SQL's header comment, since unlike a county-scale
Agr-vs-Residential split, in-town RMDC-vs-RMD-vs-Commercial is a materially weaker inference and none
of the three was ruled out.

The adversarial verifier marked this `genuinely_sourced: true` (the ordinance text itself is real and
correctly extracted), but the **ship agent correctly treated "survived verification" and "cleared to
ship" as two different gates** — it read the finding's own self-imposed "not ready" flag and withheld
the write, logging it to `gold_standard_ultraloop_audit` as `survived=false` with full reasoning
attached, rather than auto-applying a low-confidence district assignment to a production gold-standard
table. Madison I stays at 80% (4/5), unchanged. This is the mechanism working as intended, not a
failure — recommend the next session either call the Town Clerk (850-948-2251) for atlas confirmation
or explicitly accept the RMDC inference at its stated 0.55 confidence.

## Before/after evaluator JSON (live, pasted verbatim, this wave's final independent audit)

### pasco — 10/10, reconfirmed unchanged
```json
{"A":{"pass":true,"metric":101},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":98.5},"D":{"pass":true,"metric":98.5},"E":{"pass":true,"metric":95.6},"F":{"pass":true,"metric":100},"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":0.4},"I":{"pass":true,"metric":95.6},"J":{"pass":true,"metric":99},"auctions_total":205}
```

### escambia — 8/10 (was 7/10), G newly PASS
```json
BEFORE (wave1 close): {"C":{"pass":false,"metric":77.7},"D":{"pass":false,"metric":77.7},"G":{"pass":false,"metric":0,"detail":"density=93.2 far=4.3 pk1000=0.0"}, ...else PASS}
AFTER (wave2 close):  {"C":{"pass":false,"metric":77.7},"D":{"pass":false,"metric":77.7},"G":{"pass":true,"metric":100,"detail":"density=100.0 far=100.0 pk1000="}, ...else PASS}
```
**escambia: 8/10 — G fixed. C/D remain the only failing letters, real 77.7% (verified dead-end for
current unmatched pool, needs realtaxdeed.com calendar to finalize closer to sale dates).**

### wakulla — 6/10, unchanged
```json
{"A":{"pass":true,"metric":6},"B":{"pass":false,"metric":null},"C":{"pass":true,"metric":100},"D":{"pass":true,"metric":100},"E":{"pass":false,"metric":76.7},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":1.8},"I":{"pass":false,"metric":0},"J":{"pass":true,"metric":100},"auctions_total":30}
```

### madison — 6/10, unchanged
```json
{"A":{"pass":false,"metric":0},"B":{"pass":false,"metric":null},"C":{"pass":true,"metric":100},"D":{"pass":true,"metric":100},"E":{"pass":true,"metric":100},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":0.5},"I":{"pass":false,"metric":80},"J":{"pass":true,"metric":100},"auctions_total":5}
```

## Ultraloop audit trail

5 new rows in `gold_standard_ultraloop_audit` (`dispatch_id='2234fc53-6114-414f-b890-a2f60a352330'`),
ids 5536–5540: escambia G (survived=true, applied), escambia C (survived=true, confirm-only),
escambia D (survived=true, confirm-only — split from C because the table's `letter` column is
constrained to a single character), wakulla E (survived=true, research-only), madison I
(survived=false — self-flagged not-ready, correctly withheld).

## Next-session priorities (updated)

1. **escambia C/D:** re-run `tier1_realtaxdeed_escambia` matcher again as `realtaxdeed.com` calendars
   finalize closer to each of the 5 future sale dates (73 rows still unmatched, 0 currently resolvable).
2. **escambia G/zoning cleanup (optional, low priority since G now PASSes):** LDR/MDR `zone_standards`
   rows still cite `source_url=zoneomics.com` for `max_far`/`max_density_du_acre` — could be
   re-sourced from the same primary text this wave found, for provenance cleanliness only (does not
   affect the PASS).
3. **wakulla E/I:** apply the CO_NO=75 fix (not 65) to whatever ingestion path feeds `parcel_zones`
   for Wakulla, then build a PARCEL_ID format crosswalk (township/range vs dash-delimited) or switch to
   address-geocoding; separately, the 7 unlinked auction rows have zero parcel context and will need a
   different lead (clerk case detail) regardless of the FL GIO fix. `mywakullapa.com`/`qpublic` remain
   Cloudflare-blocked — try Firecrawl browser rendering, not plain curl/WebFetch.
4. **wakulla B/F:** recheck `wakullaclerk.org` again after a longer gap (hours to days, not minutes) —
   Florida clerks post tax-deed results with a lag.
5. **madison I:** either call the Greenville Town Clerk (850-948-2251) to confirm the zoning atlas
   assignment for `204 SW Church Ave`, or explicitly accept the RMDC inference at 0.55 confidence as a
   deliberate, documented judgment call — do not auto-apply the withheld SQL as-is.
6. **madison A/B/F:** structurally nothing to do until `madisonclerk.com`'s real calendar changes.
