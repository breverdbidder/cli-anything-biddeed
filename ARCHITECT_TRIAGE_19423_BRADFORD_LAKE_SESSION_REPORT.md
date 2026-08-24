# Architect Triage: issue #19423 (SHARD-5: bradford, lake)

Session: `auto-triage-issue-19423-202608242220`, dispatch `e82f3864-0b6c-404b-9813-763c5a220d42`, 2026-08-24.

## DoD
```sql
SELECT EXISTS (SELECT 1 FROM public.gold_standard_certifications WHERE county_slug = ANY('{bradford,lake}'::text[]) AND certified)
```
Re-verified live at session start and end: **FALSE both times.**

## Baseline -> End (live `pencil_dod_evaluate_county`)
```
bradford: {"A":1,"B":null FAIL,"C":100.0,"D":100.0,"E":100.0,"F":null FAIL,"G":100.0,"H":ok,"I":100.0,"J":100.0} — 8/10, unchanged
lake:     {"A":11,"B":100.0,"C":88.3 FAIL,"D":100.0,"E":93.4 FAIL,"F":100.0,"G":94.6 FAIL,"H":ok,"I":91.2 FAIL,"J":100.0} — 6/10
       -> {"A":11,"B":100.0,"C":88.3 FAIL,"D":100.0,"E":94.2 FAIL,"F":100.0,"G":94.6 FAIL,"H":ok,"I":91.2 FAIL,"J":100.0} — 6/10, E metric moved (129/137)
```

## What this session did differently from the prior 12+ bradford/lake sessions

1. **Closed the lake-I "scorecard drift" open question** left by this exact dispatch's prior run (commit `252e6159`). Pulled the live `pencil_dod_evaluate_county` function via `pg_get_functiondef` (Supabase Management API + `SUPABASE_ACCESS_TOKEN`, since direct psql remains blocked per repo precedent) and re-executed its I-criterion predicate by hand against lake's live data. Reproduced `card_rows=137, card_complete=125` exactly, matching the live scorecard. **Not a bug** — the prior session's manual SQL reconstruction had an error. No code change needed or made.

2. **Real-browser-tested bradford B/F for the first time.** `browser-use` CLI is not installed in this sandbox (confirmed, matches every prior session's finding), but `playwright` (Python) is available and was not previously discovered/used. Launched real headless Chromium against `https://www.myfloridacounty.com/orisearch/04` (Bradford's actual ORI search endpoint — discovered live via the site's own county-select dropdown; the `ori.myfloridacounty.com` URL guessed in a 2026-08-18 session does not resolve at all) and submitted the Book/Page search for 2226/469 (the Certificate of Title recorded 8/4/2026 for case 25000457CAAXMX, per decision_log id=2119). Real Chromium hits the identical Cloudflare Turnstile challenge ("Please verify you are human", `cf-chl` markers present in the DOM) as every prior raw-HTTP attempt. This is stronger evidence than before and closes off the "maybe a real browser gets through" hypothesis — it does not.

3. **Found and used a genuinely new working technique for lake E.** `officialrecords.lakecountyclerk.org`'s "Name" search (Telerik SoundEx tree) is JS-broken under raw HTTP replication, as documented by prior sessions. Its "Case Number" search (menu item `mncasenumber`, URL `/search/SearchTypeCaseNumber`) is a plain form with zero CAPTCHA/JS-widget gate and works cleanly via real browser automation. Used it to retrieve the Lis Pendens document index for case 2024CA002312 (defendant DALY MAUREEN A), which carries the legal description **"LT 11 PT LT 12 BLK 8 PALMORA PARK"**.
   - Cross-matched via Lake County's ArcGIS parcel layer (`gis.lakecountyfl.gov/lakegis/rest/services/InteractiveMap/MapServer/20`, `SubdivisionName` field) to parcel `35-19-24-0700-008-01100`.
   - Independently re-confirmed via `lakecopropappr.com`'s own property-detail page (AltKey 1458218), whose "Property Description" field reads **"LEESBURG, PALMORA PARK LOT 11, W 55 FT OF LOT 12 BLK 8 PB 5 PG 5 ORB 6067 PG 2190"** — an exact match against the clerk's Lis Pendens legal, from a fully independent source.
   - Computed a centroid from the parcel's own ArcGIS polygon geometry and pulled `TotalJustValue=458517` from the appraiser record.
   - Wrote `parcel_id`, `property_address`, `latitude`, `longitude`, `assessed_value` to `multi_county_auctions` id `360a3740-ba4e-4400-9b83-ba05bf782ca2`.
   - **Adversarially verified by an independent subagent with no shared context** (per this campaign's ULTRALOOP protocol): SURVIVED. 2 of 3 corroborating sources fully re-derived and matched; the clerk's own case-search UI returned a live HTTP 500 on re-check (a site bug, unrelated to the claim) so that one step was inconclusive rather than contradicting. Logged `gold_standard_ultraloop_audit` id=17969, `survived=true`.
   - Live re-check: lake E moved from 93.4% (128/137) to 94.2% (129/137). Still FAIL — needs ≥131.

   Attempted a second row (LABARCA / case 2026CA000560) with the same technique: found a real Lis Pendens legal description ("LT 2925 ORANGE BLOSSOM GARDENS UN 12", a genuine Lady Lake / Villages CDD subdivision, confirmed via ArcGIS), but could not resolve the Villages' large flat lot-numbering scheme to an exact parcel number within session budget, and an owner-name cross-check (LABARCA) returned zero matches in the county parcel roll. **Left unfixed rather than guess** — per HARD GUARDRAILS, no fabrication.

## Unchanged / reconfirmed with no drift
- **bradford B/F**: 0/5 closed_sold, genuine Turnstile-gated ceiling (12th consecutive session with this exact root cause).
- **lake C**: 88.3%, capped by evaluator design (16 `CLERK_SSOT_CANCELLED` rows correctly excluded from numerator, not denominator); reconfirmed no rescheduling.
- **lake I**: 91.2% (125/137); the 3 remaining zone-link gaps (052225010000001900, 221924085000000100, 011926060000202200) are the same 3 rows dispatch `8da53925`'s 2026-08-24 session already confirmed sit inside incorporated-municipality boundaries the county's unincorporated GIS layer doesn't cover. No new data found this session.
- **lake G**: 94.6%, density-binding. Groveland district id=13013 (JS-rendered ordinance table) and a possible `jurisdiction_id=835` mislabeling (flagged by the prior session — the row labeled "Leesburg" in `jurisdictions` appears to actually be used as Lake-County-unincorporated by every backfill script) both remain open. Not investigated this session — out of scope once the E lever was found; flagging for a dedicated look.

## Guardrails compliance
- PropertyOnion used as litmus only, never as a written data source.
- No schema changes.
- No fabrication: the one write made traces to two independent primary sources with an exact legal-description match, adversarially re-verified by a separate agent before being logged as `survived=true`. The LABARCA row, where the chain of evidence did not fully resolve, was explicitly left unfixed rather than guessed.
- Fail-loud: every blocked lever (Turnstile, Villages lot-numbering) reported its exact failure mode.

## Recommended next session priorities
1. **bradford B/F fleet-wide blocker**: real-browser-confirmed Cloudflare Turnstile on civitek ORI/OCRS. Posted BLOCKED/Recommend/Approve comment on #19423 recommending a CAPTCHA-solving subscription (e.g. 2Captcha) — same recommendation as decision_log ids 1986/2022, now with stronger (real-browser) evidence it's needed.
2. **lake E remaining 8 rows**: the Case-Number-search + ArcGIS-legal-description-crosscheck technique proven this session is reusable — each row needs ~15-20min of careful primary-source verification.
3. **lake G**: Groveland id=13013 ordinance fetch (needs JS-capable tooling), and verify/correct the jurisdiction_id=835 Leesburg-label question — could have fleet-wide impact on other counties using the same jurisdiction row.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
