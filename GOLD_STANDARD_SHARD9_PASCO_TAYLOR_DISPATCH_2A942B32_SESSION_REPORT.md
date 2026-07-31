# Gold Standard shard-9: pasco + taylor (dispatch 2a942b32, 2026-07-31)

## Entry state (live, before this session)
```
pasco:  A PASS B PASS C PASS D PASS E PASS F PASS G PASS H PASS I FAIL(94.4, 269/285) J PASS  -- 9/10
taylor: A PASS B FAIL(null) C PASS D PASS E PASS F FAIL(null) G PASS H PASS I FAIL(88.9,8/9) J PASS -- 7/10
```

## Method
ULTRALOOP native workflow (`gold-standard-shard9-pasco-taylor-2a942b32`, run `wf_cf7827f6-3ed`, 10 agents,
5 research groups each independently adversarially refuted) fanned out over pasco's 16 card-completeness
gaps and taylor's B/F/I gaps. All web research was read-only; every write below is from a claim that
survived its own dedicated refuter agent (a second agent, blind to nothing but re-deriving independently).

## Pasco I: 269/285 (94.4%, FAIL) -> 271/285 (95.1%, PASS)
Corrected the wrong assumed data source first: `pcpao.org` (suggested in the dispatch brief) is Pinellas
County's PAO, not Pasco's. Real source: `mapping.pascopa.com/arcgis/rest/services/Parcels/MapServer/3`
(Pasco Property Appraiser GIS) and `.../Land_Use/MapServer/1` (Pasco BOCC zoning GIS).

**11 of 16 rows fixed with real, adversarially-verified data:**
- `f08c65ea` (case 51-2025-CC-004020): real parcel_id, address, lat/lng, assessed_value all VERIFIED via ArcGIS.
- `5ec38313`: parcel_id + assessed_value VERIFIED; refuter caught the original finding had borrowed a
  *sibling unit's* centroid instead of querying unit 302's own geometry -- corrected to the real value.
- `c2b08da3`: refuter caught the proposed parcel_id had its section/range digit groups **transposed**
  (`21-24-33-...` vs the ordinance-consistent `33-24-21-...`) -- wrote the corrected value, not the
  original "VERIFIED" claim.
- 6 freshly-scraped rows (`b635d53f`, `8ff4280b`, `f2b10982`, `d2675c0c`, `db300655`, `ba076e9d`): lat/lng
  + assessed_value backfilled from ArcGIS. Refuter caught 3 of these had the *Just/Market Value*
  mislabeled as Assessed Value (homestead-capped parcels) -- wrote the correct county Assessed Value to
  `assessed_value` and the Just Value to `market_value` as two separate, correctly-labeled fields.
- 2 rows (`ae0a7b8b`, `d034b065`): real per-parcel zone codes from Pasco's actual BOCC zoning GIS --
  **MPUD** and **R1** respectively -- neither of which is "R-2", proving the prior hardcoded R-2 default
  (`scripts/shard9_run651_pasco_zoning.py`, all 269 pre-existing pasco parcel_zones rows) is wrong for at
  least these 2 parcels. Also corrected duplicate/stale placeholder lat/lng that both rows had shared.

**5 rows left genuinely UNKNOWN, not fabricated** (structural tooling gaps, not lack of effort):
`84ab0a10` and `ffd8f042` -- the DB's stored addresses proved **not to exist** (exhaustively verified
against Pasco's own parcel layer: Tahitian Gardens Cir skips house numbers 4370-4372 entirely; no
"Beach Blvd" exists anywhere in the county). `ee7405d1`, `c7f13c39`, and the garbage row `c1b3fd78`
(parcel_id="IPLTMULE", judgment $17.76M -- 2.6x the next-highest in the county) are fully blocked:
`pasco.realforeclose.com` 403s all non-browser fetches, Firecrawl API returned 402 (out of credits), and
Pasco Clerk's CiviTek OCRS requires an interactive click-through with no case-number URL API. Recommend a
follow-up session with Firecrawl credits restored or browser-use available.

## Taylor I: 8/9 (88.9%, FAIL) -> 9/9 (100%, PASS)
Last failing row: case `23-597 CA`, parcel `05026-000`. Real address ("101 Buffalo Drive, Perry, FL
32348") and value ($83,750 market value; assessed_value correctly left NULL -- source ambiguous on
JV/AV/TV) sourced from `taylorclerk.com`'s Summary Final Judgment PDF and `floridaparcels.com`'s Taylor
mirror, cross-checked against the DOR County Number Map (CO_NO=72). Lat/lng is an address-level Nominatim
geocode (Taylor has no parcel-centroid layer in the FL GIO statewide cadastral service -- confirmed
empty for CO_NO=72). Zone: **RSF/MH-2** ("Residential (Mixed) Single Family/Mobile Home"), determined via
a real point-in-polygon read of the NCFRPC City of Perry Official Zoning Atlas (PEZN14.pdf) at 300 DPI --
the refuter specifically checked this was NOT just a copy of the RSF-2 code already assigned to 2 other
Perry parcels, and confirmed it's a geometrically distinct district one block away.

## Taylor B/F: still FAIL -- genuinely blocked, not attempted-and-failed
5 of taylor's 9 auctions have auction dates already past (07-16 through 07-30) but sit at
`auction_status='upcoming'`, `sold_amount=NULL` -- consistent with outcome-discovery never having run for
this 9-auction county before. 3 of the 5 cases were confirmed real and independently fetched via direct
clerk PDF (`pdftotext`, not WebFetch's summarizer, which choked on the binary and wrongly reported the
docs unreadable). But **zero post-sale outcome documents exist for any of the 5** through any read-only
channel reachable this session: `taylor.realtdm.com` and the clerk's results flow are JS-SPA/form-gated,
Firecrawl returned 402 (insufficient credits), and no browser-use binary was installed in this sandbox.
No bid amount was fabricated. Recommend a follow-up session with Firecrawl credits topped up or
browser-use restored before concluding "no sale occurred" on any of these 5 -- absence of evidence here
is a tooling gap, not proof of no sale.

**Follow-up same session, sharper diagnosis (Playwright + real Chromium, bypassing the Firecrawl-credit
limit entirely):** confirmed `taylor.realtdm.com` itself is NOT Cloudflare/bot-blocked -- it returns a
real HTTP 200 and a working case-search form (`filterCaseNumber`, `filterParcelNumber`, `filterPartyName`,
case-status dropdown with 19 real status values). But it returns **"NO CASES FOUND" for every filter
tried**, including a single-letter wildcard party-name search ("a") and all 8 sold/completed status
codes combined with no other filter -- i.e. the public case index for this Taylor instance appears to be
**entirely unpopulated**, not just missing these 5 specific cases (the page header also displays
"TEST / Test Clerk of the Courts" branding, consistent with an unpopulated or staging instance). Separately,
`taylorclerk.com/departments/foreclosure-sales/` (fetched live) confirms only 2 cases remain in "Active
Foreclosure Sales" (25-014 CA and 23-597 CA, both still scheduled) -- the 3 target foreclosure cases
(25-218, 25-196, 25-217) have dropped off that list, consistent with them having been processed, but the
clerk's own linked "Local Official Record Search" (`pubrecords.taylorclerk.com`) is genuinely
Cloudflare bot-challenge-gated (HTTP 403, "Performing security verification"), not merely
rate-limited/credential-limited. Bottom line unchanged (B/F remain FAIL, no fabrication), but the actual
blocker for a future session is now precisely identified: either get the realtdm.com case index actually
populated/re-pointed to the live instance, or get legitimate access through Cloudflare on
pubrecords.taylorclerk.com -- not simply "buy more Firecrawl credits."

## Self-caught regression (P0, fixed same session)
The I-fix migration (`20260731d`) added 3 new `parcel_zones` rows (MPUD, R1 for pasco; RSF/MH-2 for
taylor) with no matching `zoning_districts` row. `v_zoning_gold_standard_kpi_v3`'s
`COALESCE(applicability, true)` default then treated all 3 as far/pk1000-**applicable**-but-missing,
dropping **pasco G from 100/100/100 to density=99.2/far=50.0/pk1000=50.0** and **taylor G from
100/null/null to density=88.9/far=0.0/pk1000=0.0** -- caught immediately on the post-write verification
query, before moving on. Fixed same session (`20260731e`) with real ordinance-sourced classifications, not
a workaround: Pasco LDC Ch.500 Sec.514.5.A.2 gives R1 a real 2.2 du/ac max density; Sec.522.2.A.1.a
confirms MPUD genuinely has no blanket density table value (set per-project via FLU classification x
acreage) so it's correctly marked not density/far/parking-regulated rather than given a fabricated number;
City of Perry LDR Sec.4.6.9 gives RSF/MH-2 a real 1.0 FAR cap (no du/acre table value exists for it
either, correctly marked density-NA). G verified restored to 100/100/100 (pasco) and 100/100/vacuous-null
(taylor, actually improved -- far went from vacuous-null to a genuine 100% real-data pass) before this
report was written.

## Verification protocol
```
SELECT public.pencil_dod_evaluate_county('pasco');
-- pasco: 10/10 PASS (I flipped 94.4->95.1, everything else unchanged, G regression fixed same session)
SELECT public.pencil_dod_evaluate_county('taylor');
-- taylor: 8/10 (I flipped 88.9->100.0; B/F remain FAIL, genuinely tooling-blocked, not fabricated)
```
6 rows written to `gold_standard_ultraloop_audit` (dispatch_id `2a942b32-564d-4097-bc6a-5ac44d6e2be2`,
ids 11655-11660: pasco I/G, taylor I/G/B/F, all `survived=true`).

Per PARALLEL-FLEET RULES: `git fetch` before this commit showed 3 fresh commits from other shards
(`74ccf8d9`, `ffd4cd6c`, `bb580aa5`) landed on `main` during this session's window, confirming concurrent
activity -- `gold_standard_loop()`/`gold_standard_certify()` were **not** run; only the per-county
evaluator was used for verification, per protocol.

## Next-session priorities
1. Pasco rows `84ab0a10`/`ffd8f042` (wrong DB address, needs Clerk case-file legal description) and
   `ee7405d1`/`c7f13c39`/`c1b3fd78` (fully blocked) -- all need Firecrawl credits restored or a
   browser-use-capable session to clear `pasco.realforeclose.com`'s 403 and CiviTek OCRS's click-through gate.
2. Taylor B/F -- confirmed via a real Playwright/Chromium session (bypassing Firecrawl entirely) that
   `taylor.realtdm.com`'s public case search is reachable but returns zero results for any filter
   (looks unpopulated, "TEST" branding), and `pubrecords.taylorclerk.com`'s official record search is
   genuinely Cloudflare bot-gated (403). This is the last blocker keeping taylor off 10/10 -- needs
   either the realtdm.com instance actually populated/re-pointed, or legitimate Cloudflare access on
   pubrecords.taylorclerk.com, not just more Firecrawl credits.
3. Not touched this session (out of scope, flagged only): pasco's remaining 269 legacy parcel_zones rows
   still carry the hardcoded R-2 default from `scripts/shard9_run651_pasco_zoning.py` -- this session's
   research proved that default wrong for 2 sampled parcels (real codes were MPUD and R1, neither R-2).
   A full re-scrape of all 269 against Pasco's real BOCC zoning GIS (not the R-2 blanket default) is
   warranted for G-accuracy but is a larger, separate effort from this session's I-scoped mandate.

## 2nd firing (2026-07-31, same dispatch 2a942b32 re-fired) — honest no-op, zero drift

Live state confirmed via `pencil_dod_evaluate_county` before touching anything: `pasco` still exactly
10/10 (I=95.1 PASS, all letters PASS, `card_complete=271 of 285`). `taylor` still exactly 8/10 (B=FAIL
null, F=FAIL null, everything else including I=100 PASS). Both match this report's original close-out
byte-for-byte — no drift since the first firing.

Firecrawl credit check: `remaining_credits=-3` of 1000 (still exhausted, unchanged blocker).

ULTRALOOP recheck (workflow `wf_244ec65d-327`, 4 finder agents + 4 adversarial verifiers, one per
documented blocker) re-attempted all 4 open items from "Next-session priorities" with a fresh plain
fetch/search pass (no Cloudflare-bypass, no CAPTCHA-solving, no bot-evasion attempted, per guardrails):

- **`pubrecords.taylorclerk.com`**: still a genuine Cloudflare challenge (`Just a moment...`,
  `challenges.cloudflare.com` in CSP), reproduced live with a real browser UA. Verdict: **NO_CHANGE**.
- **`taylor.realtdm.com`**: the earlier-reported 403 was a plain User-Agent sniff (curl/WebFetch UA
  rejected), not Cloudflare or a real bot-wall — with a standard browser UA it returns 200. But the page
  behind it is a **login-gated splash page** for the same "TEST / Test Clerk" branded instance, no public
  case-search surface without credentials. Net effect unchanged: the 3 target case numbers (25-218 CA,
  25-196 CA, 25-217 CA) remain unobtainable. Verdict: **NEW_FINDING (diagnostic only) — no DB write**.
  Useful for a future session with browser-use/credentials: the actual barrier is an auth gate, not a
  network block.
- **`pasco.realforeclose.com`**: same UA-sniff pattern as above (403 without UA, 200 with a real browser
  UA — standard RealAuction terms-of-use splash page). Getting past it into the real AJAX case-search
  still requires a browser session/click-through that curl/WebFetch cannot perform. The 3 blocked pasco
  case IDs (`ee7405d1`, `c7f13c39`, `c1b3fd78`) remain unresolved. Verdict: **NO_CHANGE** (a prior
  finder's phrasing overstated this as "domain-level inaccessible" — corrected here: it's reachable, just
  gated behind an interactive flow no current tool can drive).
- **Pasco addresses (`84ab0a10`, `ffd8f042`)**: re-queried Pasco Property Appraiser's own Streets +
  Parcels ArcGIS layers live. Found and corrected a **query-formatting bug** in the original session's
  method — "Beach Blvd" doesn't match because the appraiser's data spells it out as "Beach Boulevard";
  the street genuinely exists (7 centerline segments, 31+ improved parcels in Hudson). But **6824 Beach
  Blvd specifically still has no row** in the appraiser's improved-parcel index (third-party listings
  confirm it's real but vacant/unbuilt land, consistent with no PHYS_STREET record). Tahitian Gardens Cir
  4370-4372 **still genuinely absent** from a fresh, non-paginated appraiser query, even though
  third-party rental listings market "4371 Tahitian Gardens Cir" as a real address (likely a
  differently-filed appraiser ParcelID for that building, not resolved). Per HONESTY PROTOCOL, writing an
  address into the gold-standard row without a matching authoritative parcel_id/geometry would be an
  ungrounded write, worse than leaving it UNKNOWN. Verdict: **NO_CHANGE** — both rows correctly remain
  UNKNOWN, sharper diagnosis only.

**No database writes this firing.** No `gold_standard_ultraloop_audit` rows added — all 4 findings
reconfirm blockers already logged `survived=true` in the first firing (ids 11655-11660, same day, well
within the 7-day certification freshness window), so no new audit row was needed for certification
purposes. Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were not run
(confirmed active concurrent shard activity: `1bc57557` shard-12 jefferson landed on `main` during this
session's window).

**Carried-forward next-session priorities (unchanged, now with sharper mechanism):**
1. Pasco's 5 blocked I rows and Taylor's B/F still need either Firecrawl credits restored or a
   browser-use/credentialed session — now known specifically: pasco.realforeclose.com and
   taylor.realtdm.com both need a real browser session to get past an interactive splash/login gate (not
   a network block); pubrecords.taylorclerk.com needs legitimate Cloudflare clearance.
2. The 2 pasco address rows need a Pasco Clerk case-file legal description (case
   `51-2025-CA-002914-CAAX-WS` for 4371 Tahitian Gardens Cir, case `51-2025-CA-000763-CAAX-WS` for 6824
   Beach Blvd) or the specific appraiser ParcelID underlying each third-party-marketed address, since
   PHYS_STREET text-matching against the appraiser's tax roll does not resolve them.

---
dispatch_id: 2a942b32-564d-4097-bc6a-5ac44d6e2be2
chat_session: architect-20260731T080000
