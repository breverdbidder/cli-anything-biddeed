# Gold Standard Shard-5: osceola — session report

dispatch_id: `ac5f5206-a862-494e-a345-f6b0eb4cbd09`
chat_session: `architect-20260724T000000`
loop run: 6080

## Before (session start, live query 2026-07-23T19:30Z snapshot in brief)

```json
{"A":"PASS 5","B":"PASS 100.0","C":"PASS 100.0","D":"PASS 100.0","E":"PASS 100.0",
 "F":"PASS 100.0","G":"FAIL 0.0 [density=7.7 far= pk1000=0.0]","H":"PASS 3.8",
 "I":"FAIL 35.8 [card_complete=48 of 134]","J":"PASS 96.3"}
```
8/10. Only G and I failing.

## After (live, `SELECT public.pencil_dod_evaluate_county('osceola')`, 2026-07-24T00:26Z)

```json
{
  "A": {"pass": true, "metric": 5, "detail": "fc=5 td=129"},
  "B": {"pass": true, "metric": 100.0, "detail": "verified=40 closed_sold=40"},
  "C": {"pass": true, "metric": 100.0, "detail": "matched_clean=134"},
  "D": {"pass": true, "metric": 100.0, "detail": "matched_any=134"},
  "E": {"pass": true, "metric": 100.0, "detail": "parcel_linked=134"},
  "F": {"pass": true, "metric": 100.0, "detail": "tier1_sold=40 closed_sold=40"},
  "G": {"pass": false, "metric": 0.0, "detail": "density=97.4 far= pk1000=0.0"},
  "H": {"pass": true, "metric": 8.7, "detail": "hours since last_seen (SLA 48h)"},
  "I": {"pass": false, "metric": 78.4, "detail": "card_complete=105 of 134"},
  "J": {"pass": true, "metric": 96.3, "detail": "deal_complete=129 ..."},
  "county": "osceola", "auctions_total": 134
}
```
Still 8/10 (G, I remain FAIL) — both moved substantially, neither crossed the 95% gate this session. Real, verified progress; not a certification.

## What moved

**G (density sub-metric): 7.7% → 97.4%.** 443 PD + 1 PMUD + 1 STRPD parcels (jurisdiction 1186) were being counted as "density-applicable but missing" by default, even though a prior session (20260711t) had already live-confirmed via the Municode API that Osceola LDC Sec 3.11.1(I) makes PD/PMUD/STRPD density explicitly non-codified (set per development order, not a base-code table). That prior session correctly left the numeric value NULL but never flipped the `density_regulated` applicability flag. This session closed that gap: `UPDATE zoning_districts SET density_regulated=false, far_regulated=false WHERE jurisdiction_id=1186 AND code IN ('PD','PMUD','STRPD')`. No new research, no fabrication — just correctly applying an already-cited finding.

**G (pk1000 sub-metric): stayed 0.0%, correctly.** Researched Osceola LDC Sec 4.7.8 Table 4.7.8 (off-street parking) live via the Municode API, independently re-verified by an adversarial refuter agent (exact node ID, table rows, and exemption-note text all confirmed against a fresh HTTP 200 fetch). Finding: the table is **use-keyed, not zone-keyed** — ratios range ~2.5–25 spaces/1,000 SF depending on retail vs. restaurant vs. shopping-center vs. hotel use, with no CT- or CR-specific override anywhere in the code. Writing a single CT/CR number would mean picking one use-row and asserting it as "the" zone standard — exactly the fabrication pattern osceola's G letter has already shipped and reverted twice in this campaign. Declined. G remains honestly FAIL, bound by pk1000.

Also corrected in passing: 'CR' is **"Commercial Restricted"** (a legacy district crosswalking to current 'CN'), not "Commercial Retail" as an earlier session's naming implied — confirmed via LDC Table 3.1/3.2.

**I (card completeness): 35.8% → 78.4%** (48/134 → 105/134). Gap analysis found all 86 incomplete rows already had a real `parcel_zones` match (E/zone_code was never the blocker) — the gap was purely missing lat/long/assessed_value on `multi_county_auctions`. Of 86: 81 had real (if truncated) numeric parcel_ids; for 75 of 79 unique ones, our own `parcel_zones.tax_account` already stored the full 18-digit PARCELNO from a prior session's address-matched ingestion, letting this session do an **exact-match** GIS query (zero ambiguity) instead of the naive prefix search a first-pass agent correctly refused on (2–1,521 candidate features per 12-digit prefix — far too ambiguous to guess). One further pair was disambiguated by exact street-number match. 57 rows resolved and applied live with real AssessedVa/CurrJust and polygon-centroid lat/lon.

## Residual (honestly unresolved, not fabricated)

- **24 of 134 (I):** no full tax_account on file and no house-number-level address (21 carry only the placeholder "Osceola County, FL 34741"; 3 have a bare street name). Needs the heavier address-to-`fl_parcels` matching method a prior session used for the original 26→89 `parcel_zones` expansion — out of scope this session.
- **5 of 134 (I):** synthetic `OSC-xxxxxxxxxxxx` parcel_ids sourced from the raw `osceola_clerk_civilmortgageforeclosures_pdf` foreclosure calendar, with no address captured at ingestion. Needs a PDF-parse enrichment pass on the source document — a different pipeline task, not a GIS lookup.
- **G pk1000:** structurally blocked without per-parcel land-use data for the 9 applicable parcels (8 CT, 1 CR). If a per-parcel DOR-use-code or property-card-use signal becomes available, match each parcel to its closest Table 4.7.8 use-row individually — this also requires extending `v_zoning_gold_standard_kpi_v3`'s pk1000 join to support a per-parcel override (a view/schema change, out of scope for a PostgREST-only session; `supabase db push` / direct psql pooler auth were both unavailable this session, confirmed stale, matching prior sessions' notes).

## Method notes

- Used the Workflow tool (ULTRACODE) to fan out the letter-G research and a first-pass letter-I fix in parallel, each with an independent adversarial refuter. The refuters both confirmed real citations and, correctly, did **not** rubber-stamp a forced fix — the I-fix agent refused to guess among hundreds of ambiguous GIS matches (correct behavior), which is why the actual I gain came from a follow-up pass using our own DB's already-known full tax_account values for an exact (not fuzzy) GIS match.
- All DB writes went through Supabase PostgREST (`SUPABASE_SERVICE_ROLE_KEY`) rather than `supabase db push` / psql — the pooler auth is confirmed stale in this session's environment, consistent with prior shard sessions' notes. `zoning_districts`/`multi_county_auctions` UPDATEs are regular-table writes, fully expressible and idempotent via PostgREST; no view DDL was needed this session.
- 3 `gold_standard_ultraloop_audit` rows logged (dispatch_id `ac5f5206-a862-494e-a345-f6b0eb4cbd09`), all `survived=true`.

## Next-session priorities for osceola

1. I: address-match the 24 placeholder-address rows against `fl_parcels` (co_no=59) the way the original 26→89 `parcel_zones` expansion did, to push toward the 127/134 (95%) gate.
2. I: PDF-parse `courts.osceolaclerk.com/reports/CivilMortgageForeclosuresWeb.pdf` (or the underlying source feed) to recover addresses for the 5 `OSC-` synthetic-id rows.
3. G: if a per-parcel use-code source becomes available, build the per-parcel Table 4.7.8 pk1000 mapping described above (needs a view change).
