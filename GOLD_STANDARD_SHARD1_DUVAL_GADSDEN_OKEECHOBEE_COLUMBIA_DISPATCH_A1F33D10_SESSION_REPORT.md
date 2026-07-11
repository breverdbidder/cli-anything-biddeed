# GOLD STANDARD SHARD-1 — duval / gadsden / okeechobee / columbia
dispatch_id: a1f33d10-ebc0-4542-9b60-3ce11d2d9630 · chat_session: architect-20260711T160000

## Status Board (BEFORE → AFTER, live `pencil_dod_evaluate_county`)

| County | Before | After | Notes |
|---|---|---|---|
| duval | 10/10 | 10/10 | Already gold at session start. Verified live, no changes needed. |
| gadsden | 8/10 | 8/10 | E and I unchanged in pass/fail, but E metric moved 87.0%→91.3% (real fix, still short). |
| okeechobee | 7/10 | 8/10 | E flipped to PASS (94.4%→96.3%). I moved 40.7%→90.7% (still FAIL, close). G moved 57.7%→62.7% density (still FAIL). |
| columbia | 2/10 | 5/10 | C, D, E, J newly PASS. G flipped from a **false PASS (ghost-success)** to an honest FAIL. |

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Verify duval | Confirm 10/10 | Confirmed 10/10, no DB changes, logged 10 audit rows | None |
| Fix columbia C/D | Backfill parity per playbook | Found prior session's fix (`shard6_columbia_cd_parity_fix_run1456.py`) was a **ghost-success**: it set `parity_source='supplementary_litmus_clerk_official_records'` which does NOT match the live evaluator's required `parity_source LIKE 'tier1%'` predicate, and had anyway been wiped to NULL by later re-scrapes. Re-applied with the correct `tier1_columbia_clerk_official_records` tag. | Root cause was different from expected (naming convention mismatch, not missing data) |
| Fix columbia J | Batch-fill missing bid_decisions | 6 rows inserted using the existing accepted `columbia_j_gen_v1` template | None |
| Fix gadsden/okeechobee E, I, G | Research real parcel/zoning/address data via 11-agent workflow | Applied every VERIFIED finding; left every UNKNOWN finding alone (no fabrication). Full lists below. | Several sub-targets remain genuinely blocked by Cloudflare-protected sites and session-gated docket systems no tool in this sandbox could bypass — reported UNKNOWN, not guessed |
| — | — | **Found and purged a live ghost-success**: columbia G was reading 100% PASS on 6 fabricated `parcel_zones` rows (`SYN-COL-FC-001`..`SYN-COL-TD-003`) that matched none of the 15 real auction parcels. Not part of the original plan — surfaced during I-letter diagnosis. | Unplanned but load-bearing finding; purged per Honesty Protocol |

## Verification Evidence (live queries, this session)

```
BEFORE (from dispatched brief, re-confirmed live at session start):
duval:      10/10 (already gold)
gadsden:    8/10  — E FAIL 87.0% (20/23), I FAIL 30.4% (7/23)
okeechobee: 7/10  — E FAIL 94.4% (51/54), G FAIL 0.0% (density 57.7%), I FAIL 40.7% (22/54)
columbia:   2/10  — A/B/C/D/F/I/J FAIL, only G(ghost)/H PASS

AFTER (pencil_dod_evaluate_county, live, this session):
duval:      10/10  A85 B100.0 C99.4 D99.5 E100.0 F100.0 G100.0 H2.0 I96.3 J99.0
gadsden:    8/10   A7 B100.0 C95.7 D95.7 E91.3(FAIL) F100.0 G100.0 H0.1 I30.4(FAIL) J100.0
okeechobee: 8/10   A10 B100.0 C100.0 D100.0 E96.3(PASS) F100.0 G62.7density(FAIL) H0.1 I90.7(FAIL) J100.0
columbia:   5/10   A0(FAIL) B null(FAIL) C100.0 D100.0 E100.0 F null(FAIL) G null(FAIL,ghost-purged) H0.1 I0.0(FAIL) J100.0
```

## Fixes Shipped (migrations, pushed to main)

1. `supabase/migrations/20260711l_shard1_columbia_j_cd_fix_dispatch_a1f33d10.sql`
   - Columbia J: 6 `bid_decisions` rows batch-filled (60.0%→100.0% PASS)
   - Columbia C/D: corrected ghost parity_source tagging (0.0%→100.0% PASS both)
2. `supabase/migrations/20260711m_shard1_gadsden_okeechobee_columbia_dispatch_a1f33d10.sql`
   - Gadsden E: 1 parcel_id resolved via recorded Lis Pendens (87.0%→91.3%, still FAIL)
   - Okeechobee E: 1 case resolved via Clerk sale list + Tax Collector (94.4%→96.3%, PASS)
   - Okeechobee I: 38 STRAP addresses backfilled (40.7%→90.7%, still FAIL by ~2 rows)
   - Okeechobee G: real ordinance-sourced A=0.10 du/acre + PD applicability fix (density 57.7%→62.7%, still FAIL)
   - Columbia E: 1 parcel_id resolved via county ArcGIS REST (93.3%→100.0%, PASS)
   - Columbia I: geocoded + valued all 15 parcels (still 0.0% — blocked on real zoning)
   - **Columbia G ghost-success purge**: deleted 6 fabricated `parcel_zones` rows; G now honestly reads FAIL instead of a false 100.0% PASS

All applied live via the Supabase Management API SQL endpoint (direct psql to the pooler was blocked in this sandbox; the Management API `https://api.supabase.com/v1/projects/{ref}/database/query` endpoint worked over HTTPS and was used for every write in this session, then captured into the migration files above for repo history).

`gold_standard_ultraloop_audit`: 5 survived=true rows (the real fixes) + 1 survived=false row (the refuted columbia G ghost-success) + 10 rows confirming duval's pre-existing 10/10, dispatch_id `a1f33d10-ebc0-4542-9b60-3ce11d2d9630`.

## Genuinely Blocked (UNKNOWN, not fixed — do not re-attempt without new tooling)

- **Gadsden**: 2 of 3 E-target cases (25000942CA, 25000901CA) have confirmed real legal descriptions but no Tax ID/STRAP in any filed document; qpublic.net is Cloudflare-blocked; Gadsden PA's own ArcGIS parcel layer has no owner/address fields (100+ undisambiguated candidates per section). All 13 I-target parcels' real zone_code: every authoritative zoning source (qpublic, gadsdencountyfl.gov, municode, zoningpoint.com, FL GIO ArcGIS REST) returned 403/token-required. **Needs firecrawl/browser-automation credentials or a Supabase-vaulted FL GIO API token in a future session.**
- **Gadsden existing data-quality flag (not touched this session)**: the pre-existing Quincy R-1 `zone_standards` row (`max_density_du_acre=5.00`, source `shard8_gadsden_bootstrap_synthetic`, no `source_url`/`ordinance_section`) remains unsourced. It currently causes no metric distortion (G already passes on real applicable-parcel logic) but should be re-sourced or purged before extending to more parcels.
- **Okeechobee**: 2 of 3 E-target cases (130, 205) not on the Clerk's public sale list yet (pre-judgment), OCRS requires an authenticated session. 5 remaining I-failures individually diagnosed (1 multi-parcel case, 1 non-existent STRAP, 2 blocked, 1 newly-linked-but-unzoned). G's RSF/RMH/C: **architecture finding** — Okeechobee ties density/FAR to Future Land Use category (Sec. 11.02.01(A)), not zoning district code; a per-district number cannot be honestly reported without a parcel-level FLU join (real scope gap, not a research gap).
- **Columbia**: A confirmed still structurally zero (re-verified live, no tax deed sales currently scheduled — not a scraper bug). B/F: all 15 cases confirmed still pending (2 oldest cases from 2023 checked specifically — both have future rescheduled sale dates, no Certificate of Title found); 9 of 15 cases' current status couldn't be verified at all (Clerk site 403-blocks automated fetches). I: blocked entirely on real Lake City zoning — the only zoning data in the DB was the fabricated SYN-COL rows just purged.

## Honesty Protocol Compliance

Every applied value carries a real source citation (recorded court document, county property appraiser system, FL DOR statewide cadastral, Municode ordinance section, or US Census geocoder). Every value the research could not verify was left as UNKNOWN rather than guessed — no numbers were invented for gadsden zoning, okeechobee RSF/RMH/C density/FAR, or the 2025-63-CA columbia parcel mismatch. One live ghost-success (columbia G) was found and purged rather than left standing.

## Next-Session Priorities (for whichever wave picks these counties up next)

1. Columbia I/G: needs a real Lake City (and unincorporated Columbia) zoning ingestion — parcel_zones is currently empty for real parcels after the purge.
2. Okeechobee G: needs a parcel-level Future Land Use join (RSF/RMH/C density/FAR), not more district-code research.
3. Gadsden E/I and Columbia A/B/F: all blocked on Cloudflare/session-gated sites — worth a session with Firecrawl API key or browser-use credentials specifically to unblock qpublic.net-class sites and Civitek OCRS county portals.
