# GOLD STANDARD shard-3 (gulf / hamilton / union) — dispatch `03abc256-a5ba-4078-b41f-b7f730a50901`, 2nd firing

session_date: 2026-08-03. This is a second, independent closeout firing for the same dispatch_id
(a prior firing landed as commit `96e60a71` at 08:11 UTC the same day, titled
`GOLD_STANDARD_SHARD3_GULF_HAMILTON_UNION_DISPATCH_03ABC256_SESSION_REPORT.md`). This firing ran
its own fresh-dated diligence on the 3 failing letters (gulf-I, hamilton-C/D, union-B/F)
independently, then reconciled DB state with the prior firing afterward — see "Reconciliation with
prior firing" below. Both firings independently arrived at identical final scores with no
movement, which is itself a form of cross-session verification.

## Result: zero drift, all 3 letters remain reconfirmed-blocked

```
gulf:     9/10  (I fails, card_complete=12 of 14, 85.7%)
hamilton: 8/10  (C fails matched_clean=13/21=61.9%; D fails matched_any=13/21=61.9%)
union:    8/10  (B fails verified=0 closed_sold=0; F fails tier1_sold=0 closed_sold=0 — both null metric)
```

No new lever was found for any of the 3 targets. No files were fixed, no migrations were shipped,
no scores moved. This is an honest no-op session per Honesty Protocol (BLANK > WRONG) — the prior
sessions' negative findings were independently re-derived from live DB state and fresh web checks,
not trusted from memory, and all three survived adversarial re-verification.

## What was checked

### gulf — letter I (Port St Joe zoning-district linkage)
Re-derived the failing set directly from `v_zoning_gold_standard_card` rather than trusting the
evaluator function's summary number: exactly 2 of 14 rows fail, both solely on `has_zone` — case
2025-010/parcel `05762000R` (256 AVE C) and case 2025-018/parcel `05004050R` (KNOWLES AVE). The 3
previously parcel_id-null cases (232019CA000060CAAXMX, 232024CA000072CAAXMX, 232024CC000157CCAXMX)
now resolve to parcel_ids (03501201R, 06248405R, 04276175R) via other automation and all pass
`has_zone=true` — confirming the historical shrink from 7→2 unresolved rows is real, not drift.

Four fresh checks today, all negative:
1. `cityofportstjoe.com/landdevregs.cfm` — still only the static "City Zoning Map September 26,
   2012" PDF, no interactive/georeferenced tool.
2. `gulfcountypropertyappraiser.org/gis-maps/` — new candidate not previously logged; confirmed to
   be a WordPress/GeneratePress marketing wrapper with no ArcGIS backend (404 on
   `/arcgis/rest/services`).
3. `gulfpa.com` and `qpublic.schneidercorp.com` (AppID=819) — both Cloudflare 403, same wall class
   as the already-settled civitek finding.
4. `arcgis5.roktech.net/arcgis/rest/services/gulf/GoMaps4/MapServer` — full 71-layer tree
   re-enumerated including the "Building and Planning" group (layer 27, all 20 sublayers); layer
   40 "Land Use" remains the only zoning-adjacent layer and is confirmed to be a Future-Land-Use
   classification field (Agriculture/Conservation/Industrial/Residential/Water), not a
   zoning-district-code field.

No concrete new source, endpoint, or dataset surfaced. Port St Joe's only zoning source remains the
static non-georeferenced 2012 PDF; the 2 residual parcels require the previously-documented human
action (phone call to City of Port St Joe Planning, 850-229-8261), not re-attempted.

### hamilton — letters C, D (tier1 outcome parity)
Live gap re-derived directly from `multi_county_auctions` (21 total, 13 passing, 8-row gap),
unchanged from the 2026-07-31 snapshot:
- 5 foreclosure cases (2024-CA-19, 2023-CA-41, 2025-CA-66, 2021-CA-46, 2025-CA-37) with
  `parity_status='mca_only'` — auction dates 2026-08-05 (+2d) and 2026-08-12 (+9d), still in the
  future as of today. Pre-sale rows cannot have an outcome by definition; not a bug.
- 3 tax-deed certs (HAM-TD-CERT-379/597/599) with `parity_status=NULL` — Hamilton Clerk's own
  `tax-deeds/` page today explicitly shows these three as pending (vs. explicit REDEEMED dates for
  the other 7 certs in the same Dec-4-2025 batch) — a fresher confirmation of the same blocker, not
  a resolution.

Re-checked `hamiltonclerk.com/official-record-search/` → routes only to `myfloridacounty.com`
ORI search #24, which was fetched directly and confirmed to expose only Party Name / Legal
Description / Document Type / Instrument Type / Date Range / Instrument-Book-Page fields — no
case- or cert-number field, closing this off definitively as a lever.

New fact surfaced (does not close the gap): Hamilton County has a Civitek/OCRS instance
(`civitekflorida.com/ocrs/county/24/`) with a "Public" anonymous access tier, distinct from
myfloridacounty.com. Could not confirm via WebFetch whether its search form supports case-number
lookup — the landing page only exposes the four access-tier buttons; reaching the actual search UI
requires browser automation (Playwright/browser-use), not attempted this session. Flagged as a
lead for a future session, not a resolution — it is a court-case system regardless, so it cannot
help the 3 tax-deed-cert rows, and cannot help the 5 foreclosure rows until after their sale dates.

### union — letters B, F (closed/sold verification)
Live DB re-query confirms union has exactly 3 `multi_county_auctions` rows, unchanged:
`UNION-TD-CERT223` (tax_deed, redeemed, 2026-03-12), `63-2025-CA-0053` (foreclosure, upcoming,
2026-08-13 — 10 days out), `63-2024-CA-0047` (foreclosure, upcoming, 2026-10-15). Zero rows in
`foreclosure_outcomes`/`tax_deed_outcomes` for union. B/F are a genuine denominator-zero gate
(`closed_sold=0` across all 3 rows) — no row has reached a sold/closed status yet.

Fresh curl probes today reconfirm all previously-documented blockers with no change:
`unionclerk.com/foreclosure-sales/` = 403, `unionclerk.com/tax-deed-sales/` = 403,
`union.realforeclose.com` = 403, `union.realtaxdeed.com` = 403 (Cloudflare-walled).
`civitekflorida.com/ocrs/county/63/` loads (200) but requires JS/Turnstile automation to search —
not re-attempted, consistent with prior sessions' documented conclusion. Fresh WebSearch for both
case numbers and for a LienHub/GovEase Union County tenant found nothing new; `union.lienhub.com`
does not resolve (HTTP 000). No counter-lever found.

## Migrations shipped

None. No fix was applied to gulf, hamilton, or union this session — all 3 targets were
reconfirmed-blocked, not resolved.

## ULTRALOOP audit trail

5 rows inserted into `public.gold_standard_ultraloop_audit` for dispatch
`03abc256-a5ba-4078-b41f-b7f730a50901` (`ultraloop_mode='native'`, all `survived=true`):
`gulf/I`, `hamilton/C`, `hamilton/D`, `union/B`, `union/F` (ids 12421–12425). No `survived=false`
rows — nothing was refuted this session, all 3 claims held up under independent adversarial
re-verification.

### SQL VERIFICATION

```sql
-- Audit rows inserted (dispatch 03abc256-a5ba-4078-b41f-b7f730a50901)
select id, county_slug, letter, survived, created_at
from public.gold_standard_ultraloop_audit
where dispatch_id = '03abc256-a5ba-4078-b41f-b7f730a50901'
order by id;
-- id=12421 county_slug=gulf     letter=I survived=t created_at=2026-08-03 08:17:51.82398+00
-- id=12422 county_slug=hamilton letter=C survived=t created_at=2026-08-03 08:17:51.82398+00
-- id=12423 county_slug=hamilton letter=D survived=t created_at=2026-08-03 08:17:51.82398+00
-- id=12424 county_slug=union    letter=B survived=t created_at=2026-08-03 08:17:51.82398+00
-- id=12425 county_slug=union    letter=F survived=t created_at=2026-08-03 08:17:51.82398+00

-- Final live 10-letter state, all 3 counties (pre and post this session — identical, no movement)
select public.pencil_dod_evaluate_county('gulf');
-- A pass(5) B pass(100.0) C pass(100.0) D pass(100.0) E pass(100.0) F pass(100.0)
-- G pass(100.0) H pass(24.1) I fail(85.7, "card_complete=12 of 14") J pass(100.0)
-- 9/10, auctions_total=14

select public.pencil_dod_evaluate_county('hamilton');
-- A pass(6) B pass(100.0) C fail(61.9, "matched_clean=13") D fail(61.9, "matched_any=13")
-- E pass(100.0) F pass(100.0) G pass(100.0) H pass(20.9) I pass(95.2) J pass(100.0)
-- 8/10, auctions_total=21

select public.pencil_dod_evaluate_county('union');
-- A pass(1) B fail(null, "verified=0 closed_sold=0") C pass(100.0) D pass(100.0)
-- E pass(100.0) F fail(null, "tier1_sold=0 closed_sold=0") G pass(100.0) H pass(1.7)
-- I pass(100.0) J pass(100.0)
-- 8/10, auctions_total=3
```

Timestamp UTC: 2026-08-03T08:18Z.

## Next-session priorities

1. **hamilton C/D** — re-check after 2026-08-05 and 2026-08-12 pass (the 5 foreclosure cases'
   auction dates); a real chance of outcome rows appearing then. The 3 tax-deed certs
   (379/597/599) remain blocked on Hamilton Clerk publication — do not re-litigate the
   `myfloridacounty.com` search-field limitation, it is settled. One unexplored lead: use
   browser-automation tooling (Playwright/browser-use, not WebFetch) to click through
   `civitekflorida.com/ocrs/county/24/`'s "Public" access tier and confirm whether it supports
   case-number search — even if so, only useful for the 5 foreclosure rows after their sale dates,
   not the 3 tax-deed-cert rows.
2. **union B/F** — do not re-dispatch before 2026-08-13 (case 63-2025-CA-0053's sale date) or
   until `FIRECRAWL_API_KEY` credits are restored (last attempt returned HTTP 402). Both
   `unionclerk.com` (403) and `civitekflorida.com/ocrs/county/63/` (Turnstile-blocked for search)
   are independently reconfirmed with no new avenue this session.
3. **gulf I** — the 2 residual parcels (`05762000R`, `05004050R`) require the documented human
   action (phone call to City of Port St Joe Planning, 850-229-8261). No further automated lever
   exists; all GIS/appraiser/marketing-platform avenues have now been exhausted across multiple
   sessions including two new candidates checked this session
   (`gulfcountypropertyappraiser.org/gis-maps/`, direct `qpublic.schneidercorp.com` probe).

## Reconciliation with prior firing

A prior firing for this exact dispatch_id (commit `96e60a71`, 08:11 UTC) independently reached the
same conclusion: gulf 9/10, hamilton 8/10, union 8/10, zero movement, no new lever on any of the 3
targets. Its report additionally surfaces one detail not rediscovered here — a residual hamilton-I
row (parcel `8282-000`, Town of White Springs municipal zoning unavailable online) that does not
affect the I PASS outcome (95.2% ≥ 95% threshold) but is worth carrying into a future White
Springs-specific session.

`public.gold_standard_ultraloop_audit` contains only this firing's 5 rows (ids 12421–12425) for
`dispatch_id='03abc256-a5ba-4078-b41f-b7f730a50901'` — the prior firing's report describes audit
rows being inserted via a GHA workflow (`gold-standard-shard3-gulf-hamilton-union-03abc256.yml`),
but that workflow file was removed in a follow-up commit (`f046ff06 refactor(shard3): remove
workflow file — GitHub App lacks workflows permission`) before it could run, so those rows never
landed. This firing's `gold_standard_campaign` UPDATE (session_end_at 08:19:57 UTC) is the
operative one for this dispatch_id and is consistent with — not contradictory to — the prior
firing's independently-derived criteria_passed values.

---
dispatch_id: 03abc256-a5ba-4078-b41f-b7f730a50901
