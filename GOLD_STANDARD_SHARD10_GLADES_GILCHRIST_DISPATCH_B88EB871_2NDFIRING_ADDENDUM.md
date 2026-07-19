# GOLD STANDARD shard-10 — glades, gilchrist — dispatch b88eb871 — 2nd-firing addendum

session: architect-20260718T160000 (re-fired 2026-07-19, same dispatch_id and chat_session as the
2026-07-18T21:27:58Z session in commit `41a05653`)

## Duplicate-dispatch finding

This session's issue (#12766) and dispatch_id (`b88eb871-d591-4bee-ba54-cd8975d486b5`) are
**identical** to the session that already shipped `41a05653` yesterday. Live DB state on
entry matched that commit's claimed after-state exactly:

- **gilchrist: genuine 10/10** (A–J all PASS) — unchanged since the prior session's fix.
- **glades: 8/10**, C/D still `matched_clean=0` / `matched_any=0` — unchanged, structurally
  blocked.

The diagnostic research agent additionally confirmed via GitHub issue activity that **this is
GOLD STANDARD SHARD-10's 3rd automated guard-redispatch attempt** (issue #12766, re-fired
`2026-07-19T00:20:02Z`), and that at least 7 other shard sessions were simultaneously open/
active in the same window. Per PARALLEL-FLEET RULES, `gold_standard_loop()`/
`gold_standard_certify()` were **not** run this session — evidence was affirmatively
conclusive that other shards were mid-flight, not merely inconclusive.

Given the substantive fix already shipped and adversarially verified yesterday, this session
did not repeat that work. Instead it: (1) re-verified the prior fix held with zero
regression, (2) closed the two residual items the prior session's report flagged for
"whichever shard picks these counties up again", and (3) made one more good-faith attempt at
a fresh angle for glades C/D per the standing "do not idle" directive, using a Workflow
fan-out (4 research → 2 apply → 2 adversarial-verify agents, all findings independently
re-confirmed) rather than repeating the 6 already-exhausted investigations.

## Residual item 1 (prior report item 2): glades parity_scope NULL row — FIXED

One glades row (`case_number=222025CA000139CAAXMX`, the county's single foreclosure case,
`data_source=municode_munidocs:GLADES-FC-V1`) had `parity_scope=NULL` while the other 69
tax-deed rows carry `parity_scope='archive_no_source_truth'`. Verified live (gladesclerk.com
foreclosure FAQ: in-person courthouse lobby sales, Room 102 registration, 11:00 AM; the site's
own "view online" link points to the same Municode document-library platform already recorded
as this row's source) that the identical structural blocker applies to this foreclosure case,
not just the tax deeds. Patched `parity_scope='archive_no_source_truth'` — **documentation-only,
does not touch `parity_status`/matched_clean/matched_any, does not move C or D**. Adversarially
verified (`survived=true`): write confirmed via independent re-query, pass/fail-relevant
columns confirmed untouched, underlying evidence independently spot-checked.

```sql
-- SQL VERIFICATION (2026-07-19T00:2xZ UTC, live REST query)
SELECT case_number, county, auction_type, parity_scope, parity_status
FROM multi_county_auctions
WHERE case_number = '222025CA000139CAAXMX' AND county = 'glades';
-- => parity_scope: "archive_no_source_truth" (was NULL), parity_status: null (unchanged)
-- Sanity check: SELECT count(*) glades rows WHERE parity_scope IS NULL -> 0 (was 1)
```

## Residual item 2 (prior report item 3): gilchrist gap-parcel geocode — UPGRADED

Prior session flagged the gap parcel's lat/long (`161015-00000048-0010`, tax deed
26-0006-TD) as INFERRED (OSM/Nominatim geocode) because Gilchrist's own GIS returned 403 at
the time. This session found and queried Gilchrist County Property Appraiser's live
production ArcGIS backend directly:
`https://gis1.hcpao.org/arcgiscv/rest/services/Gilchrist/GilchristCounty_Basemap/MapServer/0/query`
(reached via `gilchrist-search.gsacorp.io` → `map-config-gis.js`'s declared `ParcelQueryUrl`),
confirmed by exact STRAP match (`151016000000480010`) and owner-name/address match
(HOLDER RAYMOND & LESSIE, 316 NE FIFTH ST). Computed an area-weighted (shoelace) centroid
from the returned 6-vertex parcel polygon and patched:

- latitude: `29.6155849` → `29.6152419`
- longitude: `-82.8130037` → `-82.8128655`
  (~40m shift — a genuine parcel-level precision upgrade over the geocoder inference)

Adversarially verified (`survived=true`): DB write independently re-confirmed, source
endpoint independently re-queried (bogus-STRAP control returned zero features, ruling out a
spurious default match), centroid math independently recomputed in Python and matched to
~4×10⁻⁸ degrees. `E` was already PASS (98.6%→ now still 98.6% for glades context aside;
gilchrist E stays 100%) — this is a confidence/precision upgrade, not a pass/fail change.
One caveat carried forward: `gis1.hcpao.org`'s TLS cert didn't chain-verify in this sandbox
(local CA-bundle gap, reproduced independently by the verifier — not a data-integrity issue).

```sql
-- SQL VERIFICATION (2026-07-19T00:2xZ UTC, live REST query)
SELECT county, parcel_id, latitude, longitude
FROM multi_county_auctions
WHERE county = 'gilchrist' AND parcel_id = '161015-00000048-0010';
-- => latitude: 29.6152419, longitude: -82.8128655 (was 29.6155849 / -82.8130037)
```

## Glades C/D — one more fresh-angle attempt, clean negative (7th session)

Investigated 4 genuinely new angles (not the 6 already-exhausted ones: FL Courts e-filing
portal, 2026 digitization-initiative search, Hendry/Highlands interlocal sharing, GovPilot/
CivicPlus/Tyler vendor portals). All four returned clean negatives. One new fact surfaced and
is recorded here so an 8th session doesn't re-check it: Glades County **Tax Collector**
(distinct from the Clerk, who runs the actual sales) uses VisualGov at
`taxcertsale.com/GladesTaxSale/` for its delinquent tax-certificate auction — a different,
upstream sale type from tax deed foreclosure, and login-gated for any substantive data
regardless. No row-level, case-number-matchable source exists for Glades tax deed/foreclosure
sales. No write made. No change to the standing recommendation: **this is a canon-exception
decision for Ariel, not a further investigation** — 7 independent sessions have now reached
the identical structural conclusion (RealAuction dead subdomain, no PropertyOnion coverage,
kofile name-indexed/paywalled, floridabidder no coverage, myglades generic, gladesclerk
confirms in-person-only, myfloridacounty/civitek/bid4assets/Wayback-CDX/FL-courts-efiling/
digitization-news/interlocal-sharing/GovPilot-CivicPlus-Tyler all negative, VisualGov wrong
sale type).

## Verification protocol compliance

- `pencil_dod_evaluate_county` re-run for both counties before touching anything, and again
  after the two applied fixes — pasted above (this document) and matches the assigned
  shard-brief's stated entry state exactly for both counties.
- Zero regression: no letter's pass/fail flipped for either county from either fix.
- `gold_standard_loop()`/`gold_standard_certify()` intentionally **not** run — confirmed
  multiple other shard sessions (including this same shard) were mid-flight via GitHub issue
  activity in the 10-70 minutes preceding this session.
- 2 database writes made, both applied via a dedicated Apply-phase agent and independently
  re-verified by a separate adversarial Verify-phase agent (`survived=true` both) — Workflow
  tool fan-out per the ULTRALOOP protocol (research → apply → verify, 8 agents total).

## Next-session priorities (unchanged from prior report, reconfirmed)

1. **Glades C/D**: genuinely structurally blocked, 7 independent sessions now. Escalate to
   Ariel for a canon-exception decision (analogous to, but broader than, the Brevard
   foreclosure carve-out) rather than an 8th identical investigation.
2. **Gilchrist**: fully 10/10, no further action needed unless a regression is detected by a
   future session.
