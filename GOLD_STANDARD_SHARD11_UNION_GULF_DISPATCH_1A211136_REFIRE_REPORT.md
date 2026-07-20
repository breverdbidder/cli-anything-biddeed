# GOLD STANDARD shard-11 (union, gulf) — RE-FIRE session report

dispatch_id: `1a211136-77c7-4125-b70c-06b26ad13ebe` · chat_session: `architect-20260719T160000` (2nd firing) · 2026-07-20
mode: ULTRALOOP native (Workflow tool, 2 research agents + 2 independent adversarial refuters, 4 total)

## This is a duplicate dispatch — flagged before any redundant work started

This exact `dispatch_id` already ran to completion ~40 minutes prior to this firing and shipped real
fixes to main (commit `7ffd8c88`, session report
`GOLD_STANDARD_SHARD11_UNION_GULF_DISPATCH_1A211136_SESSION_REPORT.md`). Before doing anything, this
session re-queried live `pencil_dod_evaluate_county` for both counties and confirmed **zero drift**
from that prior session's closing numbers (union 8/10 unchanged, gulf 4/10 unchanged, both exact
metric-for-metric matches). The dispatch brief's stated gulf figures (3/10, I=35.7%) are stale —
they reflect the state *before* the first firing, not current live state.

Given zero drift and a prior session that already exhausted every immediately-actionable lead (full
detail in the referenced report), this session's only legitimate value-add was checking whether any
**genuinely new** tool/capability existed that the prior session explicitly flagged as missing. It did:
the prior report states "no browser-rendering tool was available in this sandbox" for gulf I's two
open GIS leads. This session had WebSearch/WebFetch and ToolSearch-loadable Firecrawl tools available,
so it targeted exactly those two leads and nothing else. Union was not touched — its B/F block (all 3
auctions `upcoming`/`redeemed`, zero closed sales) was already independently reconfirmed live and is
unaffected by tooling; there is nothing for any tool to research there.

## What was researched this session

### Lead 1: gulf `05762000R` (256 Ave C, Port St Joe) — zoning ambiguity — still UNRESOLVED, correctly not written
The research agent queried Gulf County's own GIS backend directly (reverse-engineered the interactive
map at `maps2.roktech.net/GulfGoMaps4` to its underlying ArcGIS REST service,
`arcgis5.roktech.net/arcgis/rest/services/gulf/GoMaps4/MapServer`) and obtained more precise parcel
data than the prior session had (exact legal description, geometry, owner) — but confirmed **no layer
in that service carries a zoning-district attribute** (checked all 7 services in the `/gulf` folder;
only a broader Future-Land-Use layer exists, not zoning). qpublic.schneidercorp.com and gulfpa.com both
403'd (Cloudflare). The City of Port St Joe zoning map PDF remains the only zoning source and remains
genuinely ambiguous for this parcel (all residential sub-districts render in identical fill color; the
label-to-parcel binding cannot be resolved from the PDF alone). Confidence: NONE. Not written to
production. Recommended next step (human action, outside agent scope): call City of Port St Joe
Planning/Community Development, (850) 229-8261, and request a zoning verification letter for
Block 1004 Lot 20.

### Lead 2: gulf `06248-410R` (112 Shallow Reed Dr) — jurisdiction — RESOLVED, adversarially verified, written as audit evidence
The prior session found a jurisdiction claim for this parcel (outside Port St Joe city limits) but
**refuted** it (audit row 7445) because the cited real-estate listing didn't actually describe this
parcel. This session re-derived the same conclusion via a materially different and much stronger
evidence chain: a live `esriSpatialRelIntersects` query of the parcel's own polygon geometry against
Gulf County GIS's own "City Limits of Port St Joe" layer, which returned zero intersecting features.
Methodology was validated with a control query against a known in-city parcel (200 Reid Ave, PIN
04660-000R), which correctly returned a match. Two independent adversarial refuters each re-fetched the
same live ArcGIS services from scratch and reproduced every specific data point (parcel attributes,
geometry bounds, city-limits layer acreage, zero-intersection result, control-parcel match) —
`survived=true` from both.

**This does not flip letter I.** Knowing the parcel is unincorporated Gulf County only tells us *which*
zoning code should apply — and unincorporated Gulf County has no `jurisdiction`/`zoning_districts` row
in this system at all (only Port St. Joe id=952 and Wewahitchka id=1010 exist). A quick check for the
county's unincorporated zoning ordinance (Gulf County Code of Ordinances Ch. 30, Municode) 403'd again
this session — same blocker every prior session's SSOT has documented for Municode generally. Building
that substrate is a real Phase-4-scale ordinance-research task, not something to force in a duplicate
re-fire session, especially in a county with a documented 3+ session history of fabricated
zoning/outcomes data being caught and purged (2026-07-18 ghost-success purge). The corrected finding was
written as `gold_standard_ultraloop_audit` row 7535 (`survived=true`), explicitly superseding the
refuted row 7445, so a future ordinance-research session starts from "jurisdiction is known, zoning code
is not" instead of re-litigating the jurisdiction question.

## What was NOT attempted (and why)

- Gulf B/F/E's Cloudflare Turnstile wall on OCRS case search (`civitekflorida.com/ocrs/county/23`) —
  confirmed blocked across 4 sessions now, most recently again this session as a side-effect
  (qpublic's identical Cloudflare front-end 403'd for both leads above). Not re-attempted; CAPTCHA
  bypass is out of scope regardless of lead novelty.
- Union B/F — nothing changed; no tool can manufacture a closed sale. Earliest real auction close:
  63-2025-CA-0053, 2026-08-13.

## SQL VERIFICATION

```sql
-- run 2026-07-20T~16:5x UTC, live via pencil_dod_evaluate_county (Management API, mgmt_sql.py)
select public.pencil_dod_evaluate_county('union');
-- union: A pass(1) B fail(null) C pass(100.0) D pass(100.0) E pass(100.0) F fail(null)
--        G pass(100.0) H pass(12.3) I pass(100.0) J pass(100.0)  -- 8/10, unchanged from prior firing
select public.pencil_dod_evaluate_county('gulf');
-- gulf: A pass(5) B fail(null) C fail(78.6) D fail(78.6) E fail(78.6) F fail(null)
--       G pass(100.0) H pass(3.0) I fail(42.9, "card_complete=6 of 14") J pass(100.0)
--       -- 4/10 (A,G,H,J), unchanged from prior firing (7ffd8c88's closing state)
select id, county_slug, letter, survived from gold_standard_ultraloop_audit
  where dispatch_id = '1a211136-77c7-4125-b70c-06b26ad13ebe' order by id;
-- 6 rows total (5 from the first firing + 1 new: id 7535, gulf/I/survived=true)
```

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`certify()` were not run — two other-shard queries hit
transient `FATAL: database system is not accepting connections / Hot standby mode is disabled` errors
mid-session, consistent with concurrent shard load, and cleared on retry.

## Next-session priorities (carried forward + refined)

1. **gulf unincorporated zoning substrate** (new, more precise framing than the prior report's generic
   item 2): find an accessible source for Gulf County's unincorporated-area zoning/land-development code
   — Municode is 403'd; try a direct county-hosted PDF (per the Port St Joe LDR-PDF precedent) or a
   public-records request. Until this exists, `06248-410R` and any other unincorporated-Gulf parcel
   cannot pass I no matter how precisely their jurisdiction is known.
2. **gulf `05762000R`** — needs a human phone call to City of Port St Joe Planning (850-229-8261); no
   further automated GIS/document research path exists.
3. **gulf E/C/D** (3 null-parcel cases) and **gulf B/F** — still gated on the same Cloudflare Turnstile
   wall on Gulf OCRS, confirmed again this session. No CAPTCHA solver available; not re-attempted.
4. **union B/F** — nothing to do until a real auction closes (earliest 2026-08-13).

---
dispatch_id: 1a211136-77c7-4125-b70c-06b26ad13ebe (2nd firing)
