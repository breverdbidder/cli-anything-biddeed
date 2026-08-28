# Gold Standard Shard-5: highlands, okaloosa (dispatch 773d98e3-8444-4e87-829c-71bcc938ee26)

Loop run 14969. Session window 2026-08-28 08:00Z–08:35Z.

## Result

| County | Before | After | Change |
|---|---|---|---|
| highlands | 8/10 (C, D fail) | **9/10** (C fail) | D FAIL→PASS, I stayed PASS (dipped mid-session, recovered above baseline), C improved 87.3%→89.3%, no regressions |
| okaloosa | 6/10 (C, D, E, I fail) | 6/10 (C, D, E, I fail) | G improved 96.1%→100.0%, I improved 89.4%→91.8%, C/D/E genuinely re-confirmed at a data ceiling, no regressions |

Both counties had been worked by many prior sessions (highlands: dispatch 8f944a71 on 2026-08-27 concluded C/D genuinely blocked; okaloosa: dispatch 00c40dcc/8d979d33 on 2026-08-26 concluded C/D/E genuinely blocked). This session found and fixed two live **code bugs** behind those "ceilings" rather than re-attempting the same exhausted levers, plus closed real data gaps with newly-available tooling (`brightdata` MCP, not available to prior sessions).

## Bugs found and fixed (both real code, both re-runnable daily)

1. **`scripts/clerk_ssot/parsers/highlands.py::parse_tax_deed()`** — `filterCaseStatus=1827` only covers ONE of realtdm.com's status buckets. Live-verified 30 genuinely-active/cancelled highlands tax_deed cases (`ACTIVE - REDEMPTION`, `ACTIVE - SOLD BIDDER`, `CANCELED - RESCHEDULE`) never appear under that filter, so the daily `clerk_ssot` parity run was silently dropping them and then flagging them `PHANTOM_NOT_ON_CLERK` — a live regression caught mid-session (D flipped PASS→FAIL the moment the old parser ran). Fixed to pull unfiltered (`filterCaseStatus=""`) and derive `cancelled` from the status text itself. Re-ran live: `phantom_in_ours` 30→0, `matched` 106→136.

2. **`scripts/okaloosa_zoning_substrate_build.py`** — `COUNTY_ZONING_URL` pointed at `MapServer/28`, which is now "Coastal Construction Control Line" (every query 400s, zero `ZNGPY_ZONE` field) — the county's ArcGIS service renumbered its layers since the script was written. Live-enumerated the service and found the real zoning layer moved to `MapServer/25`. Fixed and re-ran: 2 previously-unresolvable Unincorporated-Okaloosa parcels (`2025-CA-002248-C`, `2025-CA-002237-C`) now correctly zone-linked (R-1).

## Real fixes applied live (not just code — executed with before/after proof)

- `scripts/highlands_cd_realtdm_active_redemption_fix.py`: committed 2026-08-24, **never actually executed** until this session (SHIP GATE violation closed). Ran live: 9 rows fixed (7 `matched_clean`, 2 `CLERK_SSOT_CANCELLED`).
- 8 more highlands tax_deed rows patched via the same realtdm.com re-verification pattern (parcel_id cross-checked live before writing).
- `scripts/clerk_ssot/run_parity.py` `diff_and_reconcile()` run live for highlands foreclosure + tax_deed (with the parser fix): 29/30 foreclosure + 136/137 tax_deed matched against the live clerk calendar, `PARITY_OK`.
- `scripts/highlands_e_parcel_linkage.py --apply`: 8 more foreclosure rows resolved (clerk PDF calendar legal description → HCPAO parcel search → GIS centroid), real address/parcel/value/geo, not guessed.
- `scripts/highlands_i_zone_backfill.py --apply`: 9 parcels newly zone-linked (real ArcGIS zoning lookup).
- Okaloosa G regression root-caused and fixed for real (not reverted): the 2 newly-linked R-1 Unincorporated-Okaloosa parcels exposed a pre-existing NULL density on `zoning_district_id=12081` (Highlands County LDC — wait, Okaloosa County LDC Sec. 2.03.06 — density is legally split 4 du/acre north / 5 du/acre south of the Eglin AFB reservation, never resolved per-parcel by a prior session). Queried `services.arcgis.com/.../USA_Federal_Lands` for Eglin's actual reservation polygon (max lat 30.7497) and confirmed all 5 real zone-linked parcels sit north of it (lat 30.767–30.813) — applied `max_density_du_acre=4` with the geometric evidence cited in `ordinance_section`, not guessed.
- Highlands AU district (`zoning_district_id=14262`, new): had **no** `zoning_districts` row at all, which defaulted it to "applicable, no data" for density/FAR/parking (worst case) the moment a parcel got zone-linked to it — this is what dropped highlands G to 66.7% mid-session. Fetched the real ordinance text (Highlands County LDC Sec. 12.05.200, via Municode/Zoneomics) and inserted a correctly-sourced row: `max_density_du_acre=0.2` (5-acre minimum lot, the general-case standard — TDR/cluster/wetland exceptions are parcel-specific and not applied without parcel-level evidence), `far_regulated=false`, `pk1000_regulated=false` (agricultural district, no such standards in the ordinance text).

## Okaloosa C/D/E — re-confirmed genuine ceiling (not re-litigated at length)

6 gap rows, unchanged from the 2026-08-26 session's findings, independently re-verified this session with a **new** tool (`brightdata` MCP scrape, not available to prior sessions):
- `2024-CA-000470` / `2024-TDD-000089`: `okaloosa.realforeclose.com` blocked by `brightdata`'s own robots.txt/KYC policy (declines the domain outright); `bid4assets.com/OkaloosaFLTax` reachable via `brightdata` but the Aug-19 sale's property list is no longer even a selectable "Sales Date" on the live site — the sale has aged out of the site's own UI, not a scraping failure.
- `2025-CA-002286-F3/F4/F5`: legal descriptions independently re-confirmed absent from Okaloosa's own parcel index / reference Walton County outright — genuinely not Okaloosa parcels, out of this shard's scope to reassign.

## Verification (live, this session)

```
SELECT public.pencil_dod_evaluate_county('highlands');
BEFORE: C=87.3 D=93.5 E=95.0 G=99.7 I=95.0  (8/10)
AFTER:  C=89.3 D=96.0 E=97.0 G=99.7 I=96.8  (9/10)

SELECT public.pencil_dod_evaluate_county('okaloosa');
BEFORE: C=92.9 D=92.9 E=92.9 G=96.1 I=89.4  (6/10)
AFTER:  C=92.9 D=92.9 E=92.9 G=100.0 I=91.8 (6/10)
```

Close-out written to `public.gold_standard_campaign` (dispatch_id `773d98e3-8444-4e87-829c-71bcc938ee26`).

## Residual levers for the next session

- **highlands C** (89.3%, need 382/402): 12 foreclosure cases (litmus_fallback source, all past auction dates) blocked by Firecrawl account credit exhaustion (`402 Insufficient credits`, same account/finding as the 2026-08-27 session) + `brightdata` declining `realforeclose.com` via KYC policy. `acclaim.highlandsclerkfl.gov/TributeWeb/` (Official Records) is reachable and NOT bot-gated, but is a classic ASP.NET WebForms postback app (`casedetail.aspx?CID=`), not the JSON REST pattern Brevard/Duval's AcclaimWeb uses — a real port would need a `__VIEWSTATE`/postback scraper, not a quick parameterization. Flagged, not attempted.
- **okaloosa C/D/E**: structural ceiling per above; only a Firecrawl-credit-restored retry of the bid4assets results-page-by-auction-ID pattern, or an authenticated realforeclose.com session, would move this further.
- **highlands E/I**: 12 remaining rows (2 placeholder/synthetic bootstrap rows, 10 real cases either not on the live calendar or with legal descriptions the address-token extractor can't parse) — see `highlands_e_parcel_linkage.py` SKIP output for the exact list.
