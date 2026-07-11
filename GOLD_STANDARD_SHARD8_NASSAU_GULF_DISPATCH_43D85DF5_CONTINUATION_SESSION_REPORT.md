# GOLD STANDARD shard-8 (nassau, gulf) — dispatch `43d85df5-ca99-4b37-8fa0-b36bfc1c401e`, continuation session

chat_session: `architect-20260711T160000` · 2026-07-11 · mode: ULTRALOOP native (Workflow tool, 6 agents: 3 diagnose + 3 adversarial verify)

## Starting state (live query, before this session's work)

This dispatch was already fired once earlier today; commit `529c7bed` (migration
`20260711u_gold_standard_shard8_run3786_nassau_gulf.sql`) shipped the real gains
available at that time. This continuation re-verified the live scoreboard fresh at
session start — no assumptions carried forward from the brief's stale snapshot:

```
nassau 8/10: A✓ B✗(null) C✓ D✓ E✓(100.0) F✗(null) G✓ H✓ I✓(97.1) J✓
gulf   4/10: A✓ B✗(null) C✗(78.6) D✗(78.6) E✗(78.6) F✗(null) G✓ H✓ I✗(64.3) J✓
```

## What this session did

Ran a full ULTRALOOP fan-out via the Workflow tool against the two open leads flagged in
the prior migration's "NEXT STEP" note:

1. **gulf I** — chase real street addresses for the 2 remaining fixable-looking
   card_complete gaps (parcels `03426604R`, `00469000R`).
2. **nassau B/F** — one genuinely fresh attempt at an independent verified-outcomes
   source (not a repeat of the 6 previously-exhausted avenues).
3. **gulf B/F** — same, plus direct case-detail attempts on the 3 specifically blocked
   foreclosure cases.

Each diagnose agent's report was then handed to an independent adversarial verify agent
whose only job was to re-fetch every cited source itself and try to refute the claim.

## Findings (all independently reproduced — see verify pass below)

### gulf I: confirmed NOT fixable — no fabrication
Gulf County's own authoritative parcel GIS (`arcgis5.roktech.net/.../GoMaps4/MapServer`,
reached via `gulfcounty-fl.gov`) confirms both parcels are **vacant, unaddressed land**
(`USEDESC=VACANT`, `HOUSE_NO`/`STREET`/`LOC` all null). The address-looking fields
returned by generic search are the **owner's out-of-county mailing address**, not a
situs address. Writing that as `property_address` would have been a fabrication.
Independently cross-checked: parcel polygon centroids match our stored lat/lon to ~10m
(same physical parcel), and both are already correctly zoned (`zone_code='RES'`,
jurisdiction 1010). **No write made.** gulf I stays at 64.3% (9/14) — genuinely capped by
these 2 rows + the 3 parcel-less blocked foreclosure rows.

New reusable lead for future Gulf County sessions: `arcgis5.roktech.net` is a real,
live, unauthenticated ArcGIS REST endpoint for Gulf's parcel/address data — not
previously known to this repo. `gulfpa.com`/Beacon/qPublic are hard Cloudflare-blocked;
`gulfcountypropertyappraiser.org` is a fake third-party WordPress mockup — don't retry
either.

### nassau B: new source found, applied, result is honestly inconclusive — no fabrication
`search.ncpafl.com` (Nassau County Property Appraiser sales-history search) is a real,
live, non-JS-gated, non-PropertyOnion source exposing deed/CT (Certificate of Title)
records with grantor/grantee/price/date — the first non-dead avenue found for nassau
B/F across two sessions. Nassau has exactly one `auction_status='completed'` row (case
`452025CA000382CAAXYX`, 724 N 14TH ST). Searched it: the most recent recorded instrument
on that parcel is a **Warranty Deed** ($440,000, private grantor→grantee), not a **CT**
from the Clerk of Court, and no CT has been recorded in the 2+ months since the auction
date. This most plausibly means the case was resolved by a private sale/payoff before
the courthouse auction — a real, legitimate outcome, but **not** a foreclosure-auction
sale. Writing that $440,000 into `sold_amount` would have misattributed a private resale
as an independent foreclosure outcome (a canon violation). **No write made.** nassau
B/F remain FAIL, honest and unchanged.

`search.ncpafl.com` is a genuine, reusable lead for a future session: it has no
case_number field (keyed by STRAP + OR book/page), so scaling it requires a
STRAP↔case_number matching pipeline — concrete and buildable, not yet built. Most
useful once more nassau auctions age into `completed`/past-due status (currently 1 of 34).

### gulf B/F: re-confirmed dead, fresh evidence (not a stale repeat)
`gulf.realforeclose.com` AID pages: flat HTTP 403 (AWS ELB), re-confirmed independently
today. `civitekflorida.com/ocrs/county/23/`: JS-search-gated, plus a newly-discovered
mail-in registration-agreement requirement. `myflcourtaccess.com`: e-filing only, no
case search (confirmed live). `myfloridacounty.com/orisearch/23`: real and live but
name-search-only — unusable, none of the 3 target cases have an owner_name on file.
Gulf Tax Collector surplus process: structurally inapplicable (tax-deed only, these are
foreclosure cases). Firecrawl: fleet-wide credit-exhausted, confirmed live via direct
API call today (`"Insufficient credits to perform this request"`). One avenue
(floridapublicnotices.com/Column-powered legal notices) is blocked-by-tooling (needs a
real rendering browser, not curl/WebFetch) rather than blocked-by-source — a legitimate
next-session action item.

## Adversarial verification (3 independent refuter agents)

- **gulf I claim**: 8/8 factual sub-claims SURVIVED independent re-query (exact field
  match on ArcGIS response, WAF-403 reproduction, WordPress-mockup reproduction,
  centroid geo cross-check). One minor flag (verifier checked the wrong table,
  `zoning_assignments` instead of `parcel_zones`) — resolved directly against the live
  DB: `parcel_zones` and `v_zoning_gold_standard_card` both confirm zone_code='RES' for
  both parcels, so the original claim stands as stated.
- **nassau B claim**: 5/5 sub-claims SURVIVED with exact byte-for-byte reproduction
  (identical CT example row, identical form-field enumeration), 2 trivial cosmetic
  corrections (`/parcel/` not `/parcels/`, 72 vs 67 result count on a slightly different
  date range) that don't affect the substance.
- **gulf B/F claim**: 8 of 9 sub-claims SURVIVED; 1 narrow mechanism-level REFUTED (the
  realforeclose.com block reproduced as a flat 403 rather than the "login splash page"
  the original agent described — the practical conclusion, no data obtainable, is
  unaffected either way).

All 4 substantive findings logged to `public.gold_standard_ultraloop_audit`
(`dispatch_id='43d85df5-ca99-4b37-8fa0-b36bfc1c401e'`, `ultraloop_mode='native'`,
`survived=true`), on top of the 8 rows from the dispatch's first firing.

## Closing scoreboard (live, re-verified after this session — zero regression)

```
nassau 8/10: A✓ B✗(null: verified=0 closed_sold=0) C✓(100.0) D✓(100.0) E✓(100.0)
             F✗(null: tier1_sold=0 closed_sold=0) G✓(100.0) H✓(1.9h) I✓(97.1) J✓(100.0)
gulf   4/10: A✓(fc=5 td=9) B✗(null) C✗(78.6: matched_clean=11) D✗(78.6) E✗(78.6)
             F✗(null) G✓(100.0) H✓(23.0h) I✗(64.3: card_complete=9 of 14) J✓(100.0)
```

Unchanged from session start — this was a genuine-diagnosis session, not a
metric-moving one. No fabricated data was written; no ghost-success risk introduced.

## Next-session priorities (concrete, in order)

1. **nassau B/F**: build the `search.ncpafl.com` STRAP↔case_number matching pipeline.
   Revisit once more of nassau's 25 upcoming auctions age into `completed` status —
   right now there's only 1 candidate row and it turned out inconclusive.
2. **gulf B/F**: try `floridapublicnotices.com` / `portstjoestar.column.us` with real
   browser automation (Playwright/browser-use skill) instead of curl/WebFetch — the one
   avenue that's blocked-by-tooling, not blocked-by-source.
3. **gulf C/D/E/I ceiling**: structurally tied to the same 3 blocked foreclosure cases
   as gulf B/F (232024CA000072CAAXMX, 232019CA000060CAAXMX, 232024CC000157CCAXMX) — a
   fix there flips 4 letters at once, not just B/F.
4. Both counties' remaining gaps are genuinely blocked by external tooling/access, not by
   unexplored research surface — further sessions should prioritize the browser-
   automation prerequisite (item 2) over re-running curl/WebFetch-only investigation.

---
dispatch_id: 43d85df5-ca99-4b37-8fa0-b36bfc1c401e (continuation firing)
