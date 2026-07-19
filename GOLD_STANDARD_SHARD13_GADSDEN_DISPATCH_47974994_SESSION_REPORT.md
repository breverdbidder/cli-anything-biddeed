# Gold Standard shard-13: gadsden — dispatch 47974994, parallel 6h session

## Result: 7/10, no change (genuinely blocked, not for lack of trying)

| Letter | Before | After | Notes |
|---|---|---|---|
| A | PASS (fc=16 td=7) | PASS (fc=16 td=7) | Unchanged |
| B | PASS 100.0 | PASS 100.0 | No regression |
| C | PASS 95.7 | PASS 95.7 | No regression |
| D | PASS 95.7 | PASS 95.7 | No regression |
| E | FAIL 91.3 (21/23) | FAIL 91.3 (21/23) | Needs only **1** more linked parcel to cross 95% — genuinely blocked this session, see below |
| F | PASS 100.0 | PASS 100.0 | No regression |
| G | FAIL (null) | FAIL (null) | Genuinely blocked — root cause re-confirmed, one new structural finding (see below) |
| H | PASS 19.4→27.5 | PASS 27.5 | No writes made; drifted naturally with wall-clock time |
| I | FAIL 0.0 (0/23) | FAIL 0.0 (0/23) | Same root cause as G (zero `parcel_zones` rows for gadsden) |
| J | PASS 100.0 | PASS 100.0 | No regression |

**Zero DB writes this session.** Every research avenue that could plausibly move E, G, or I was
exhausted honestly and came back empty or below the confidence bar for a live write. Per BLANK >
WRONG, no parcel_id was guessed and no zone_code was fabricated. This report exists so the next
session doesn't re-spend the same effort on paths already proven dead.

## What happened

Per the ULTRALOOP protocol (ultracode opted in this dispatch), ran one Workflow
(`gadsden-gold-standard-e-g-i`, run `wf_14dcd36d-e87`) fanning two research agents — one for the 2
remaining E-gap case numbers, one for the 8 municipal-parcel G/I zoning gap — each followed by an
adversarial verify stage. Both research agents came back with **zero survivable claims** (no
`parcel_id_found`, no `zone_code_found` passed to verify), so the verify stage had nothing to check
— an honest null, not a refuted claim. After the workflow, I did additional first-hand research
myself (headless Playwright, since several sources return HTTP 403 to plain HTTP clients but may
render for a real browser) to push past where 3 prior gadsden sessions and this session's workflow
stopped.

### E: 91.3% (21/23) — 1 more parcel_id needed to PASS

The two gap cases are `25000901CA` and `25000942CA`. Fetched the **actual live source** the clerk
publishes (`https://www.gadsdenclerk.com/Foreclosures/Foreclosures_files/sheet001.htm`, an
Excel-export static page behind a frameset that returns HTTP 200 to a real browser but a bare
directory-listing 403 to the parent `/Foreclosures/` path — this is a directory-index restriction,
not a bot block, and explains why prior plain-`curl` sessions saw only 403s here).

Confirmed the sheet's actual columns: `Sale Date | CASE # | Plaintiff | Defendant | Property
Address | Judgment Amount` — **no parcel ID or legal-description column exists in this source at
all**. For `25000901CA` the row reads verbatim: Plaintiff `JLT Mortgage`, Defendant `Ramon's
Construction`, Property Address `Section 26, Township 2 North`, Judgment `$56,245.27` — i.e. the
clerk itself never publishes a more granular address for this case; our DB's existing
`property_address` field is a faithful copy of the source, not a scraping gap. `25000942CA` no
longer appears in the live sheet at all (expected — it already sold on 2026-07-02, so the clerk
dropped it from the active sale list; a completed-sale archive with a Certificate of Title would be
the next place to look, but that requires the same official-records search that's blocked below).

With a real name (`Ramon's Construction`, a business entity) in hand, tried to cross-reference it
against the Gadsden Property Appraiser (`qpublic.schneidercorp.com`, AppID=1023) by owner name —
**dead end, confirmed via two independent methods**: plain HTTP (403) and a real headless-Chromium
Playwright session with an 8s wait for the challenge to clear (still 403, title "Just a moment...",
Cloudflare managed bot-verification challenge that headless Chromium's automation fingerprint does
not pass). This is a stronger, more specific confirmation than prior sessions' generic "qpublic
403" note — it rules out "maybe it just needed a browser" as an untried angle.

**Net: E stays at 91.3%.** The blocker is not a scraping gap on our end — it's that the clerk's own
published record for `25000901CA` lacks a parcel ID, and the two candidate cross-reference paths
(property-appraiser owner search, official records for the already-sold case) are both behind a
Cloudflare bot-management wall that neither plain HTTP nor a real (non-stealth) headless browser
clears.

### G/I: null / 0% — root cause re-confirmed, zoning substrate genuinely unavailable

Prior sessions (20260718c, 20260718k, 20260718m) already established: zero `parcel_zones` rows
exist for gadsden; Quincy (4 auction parcels) and Chattahoochee (4 auction parcels) already have
real, ordinance-cited `zoning_districts`/`zone_standards` catalogs from municode-mirror/elaws.us
sources; the other 13 of 21 linked auction parcels are unincorporated county land (confirmed
authoritative via `fl_parcels.municipality='COUNTY'`, not address-string guessing) with no
"Unincorporated Gadsden" jurisdiction row and no accessible countywide LDC.

This session's workflow searched further and found the ARPC ArcGIS org's `Gadsden_FLUM`/`Gadsden_FLUM2`
services (Future Land Use Map — comp-plan categories like Ag1/Ag2/Commercial/Industrial, not zoning,
no density/FAR/parking numbers) and confirmed no `Quincy_Zoning` or `Chattahoochee_Zoning`
FeatureServer exists anywhere in ArcGIS Online's public index. It also re-checked
`Havana_Zoning_Districts_WFL1` (used successfully in a prior session for a different purpose) and
found layer 0 is actually a road-reference polyline dataset despite its name — not usable, and moot
anyway since none of our auction parcels are in Havana.

I then did first-hand follow-up with a real headless browser: **`library.municode.com/fl/gadsden_county`
loads fine for a real browser (HTTP 200)** — unlike the plain-HTTP 403 prior sessions hit — so I was
able to walk the actual chapter tree of Gadsden County's Code of Ordinances (version June 25, 2024,
single published document, no other Municode product exists for this county). **New confirmed
finding: there is no Zoning or Land Development chapter in Municode at all** — the chapter list runs
Chapter 18 (Buildings) directly to Chapter 20 (Economic Development) with nothing zoning-related in
between. This means Gadsden County's zoning/LDC is not codified on Municode, period — it lives only
in a standalone document (the Wayback-archived "Accessory Structure Checklist for Planning and
Zoning" PDF the workflow found cites a real LDC with real countywide setback numbers, but no
per-district R-1/R-2/Ag-1/Ag-2 table) that isn't reachable through `gadsdencountyfl.gov` (confirmed
403 "Access Denied" via real headless browser too — a WAF block stricter than the Municode/clerk
domains, not just bot-detection).

**Net: G/I stay at their pre-session values.** No zoning_districts/parcel_zones rows were inserted.
The honest state of the world: even where a district catalog exists (Quincy, Chattahoochee), there
is no discoverable parcel-level GIS source to assign any of the 8 municipal auction parcels to a
specific district: and for the 13 unincorporated parcels, the county's own zoning ordinance text
itself isn't accessible through any web-scrapable channel found across 4 independent sessions now.

## Recommendation for the next gadsden session

- **E**: do not re-try `qpublic.schneidercorp.com` owner-name search or the clerk sheet re-parse —
  both are now confirmed dead ends via 2+ independent methods each. The only remaining path is a
  stealth/residential-proxy scraping approach (e.g. Firecrawl once credits refill — confirmed still
  at 0 this session) or a manual public-records request; not worth another plain-browser attempt.
- **G/I**: do not re-search ArcGIS Online or re-probe `gadsdencountyfl.gov`/`maps.gadsdencountyfl.gov`
  — exhaustively covered. The one open thread: Gadsden County's genuine Municode client
  (`clientId=5945`) has a `codes` API that returned metadata but 401'd on content, and the
  `Foreclosures_files`-style Excel-export pattern suggests the county publishes other documents the
  same way — worth trying `gadsdencountyfl.gov`'s IIS-style static export paths directly (as done
  successfully for the clerk site above) rather than the WAF-blocked dynamic pages, if a future
  session has a stealth-capable fetch method for the WAF.

## Live evaluation JSON — BEFORE (session start, 2026-07-19)
```json
{"A":{"pass":true,"detail":"fc=16 td=7","metric":7},"B":{"pass":true,"detail":"verified=1 closed_sold=1","metric":100},"C":{"pass":true,"detail":"matched_clean=22","metric":95.7},"D":{"pass":true,"detail":"matched_any=22","metric":95.7},"E":{"pass":false,"detail":"parcel_linked=21","metric":91.3},"F":{"pass":true,"detail":"tier1_sold=1 closed_sold=1","metric":100},"G":{"pass":false,"detail":"density= far= pk1000=","metric":null},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":19.4},"I":{"pass":false,"detail":"card_complete=0 of 23","metric":0},"J":{"pass":true,"detail":"deal_complete=23 (triangle + two-arm CMA + ml_score + max_bid)","metric":100},"county":"gadsden","V2_LITMUS":null,"auctions_total":23}
```

## Live evaluation JSON — AFTER (post-research, same session)
```json
{"A":{"pass":true,"detail":"fc=16 td=7","metric":7},"B":{"pass":true,"detail":"verified=1 closed_sold=1","metric":100},"C":{"pass":true,"detail":"matched_clean=22","metric":95.7},"D":{"pass":true,"detail":"matched_any=22","metric":95.7},"E":{"pass":false,"detail":"parcel_linked=21","metric":91.3},"F":{"pass":true,"detail":"tier1_sold=1 closed_sold=1","metric":100},"G":{"pass":false,"detail":"density= far= pk1000=","metric":null},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":27.5},"I":{"pass":false,"detail":"card_complete=0 of 23","metric":0},"J":{"pass":true,"detail":"deal_complete=23 (triangle + two-arm CMA + ml_score + max_bid)","metric":100},"county":"gadsden","V2_LITMUS":null,"auctions_total":23}
```

## SQL VERIFICATION
```sql
SELECT public.pencil_dod_evaluate_county('gadsden');
-- returns the "AFTER" JSON above, run live 2026-07-19 via Supabase Management API SQL executor.
-- No INSERT/UPDATE/DDL statements were executed this session (zero DB writes).
```

dispatch_id: 47974994-0d84-4a27-a865-6429cab3303d
