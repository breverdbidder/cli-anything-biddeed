# Gold Standard Shard-6: hillsborough / flagler / bay — dispatch 1f302343

Session: architect-20260719T160000, loop run 5153. Ultracode/ULTRALOOP protocol: 8 fan-out
diagnostic agents (one per failing county+letter) → adversarial refuter per finding → surviving
fixes applied live → live re-verify.

## Environment note (VERIFIED)

Direct psql against the pooler hosts fails password auth in this sandbox (confirmed:
`SUPABASE_DB_PASSWORD` is stale, matching the note already in `migrations/run_migration.js`).
Live DB writes in this session went through the Supabase Management API
(`node migrations/run_migration.js <file>`, authed with `SUPABASE_ACCESS_TOKEN`), which is the
canonical, already-established path in this repo. `exec`/`exec_sql` PostgREST RPCs referenced by
some older scripts (`apply_migration.py`, `shard28_*.py`) do not currently exist in the schema
cache — that path is dead; the Management API is the live one.

## BEFORE (live, confirmed at session start)

```json
hillsborough: A✓ B✓ C✓ D✓ E✓ F✓ G✓ H✓ I✗(68.0%, 623/916) J✓        -- 9/10
flagler:      A✓ B✗(null) C✓ D✓ E✓ F✗(null) G✓ H✓ I✗(93.6%,131/140) J✓  -- 7/10
bay:          A✓ B✗(null) C✗(92.9%) D✗(92.9%) E✓ F✗(null) G✗(27.3%) H✓ I✗(93.7%,119/127) J✓  -- 4/10
```

## AFTER (live, re-verified post-fix)

```json
hillsborough: A✓ B✓ C✓ D✓ E✓ F✓ G✓ H✓ I✗(68.0%, 623/916) J✓        -- 9/10 (unchanged)
flagler:      A✓ B✗(null) C✓ D✓ E✓ F✗(null) G✓ H✓ I✓(97.9%,137/140) J✓  -- 8/10 (+1)
bay:          A✓ B✗(null) C✓(100.0%) D✓(100.0%) E✓ F✗(null) G✓(96.5%) H✓ I✗(93.7%,119/127) J✓  -- 7/10 (+3)
```

Exact `pencil_dod_evaluate_county` output pasted, before/after, in the tool-call log of this
session (RPC calls at session start and again after each migration applied).

## SHIPPED (3 migrations, applied live via Management API, committed to main)

1. **`20260719j_gtm22j_shard6_flagler_i_palmcoast_zoning_backfill.sql`** — flagler I 93.6%→97.9%
   (131→137/140). 6 `parcel_zones` rows inserted (real zone codes SFR-2/SFR-3, jurisdiction_id=966
   Palm Coast) via live point-in-polygon queries against
   `gis.palmcoast.gov/.../Op_ULDCZoning/MapServer/3`, plus a NULL-guarded lat/lon backfill for 5
   rows from `gis.palmcoast.gov/.../FlaglerCountyParcels/MapServer/1`. 3 of the original 9 gap rows
   remain unfixed and are logged as residual (see below) — no fabricated value was written for
   them.

2. **`20260719k_gtm22j_shard6_bay_cd_foreclosure_ajax_promote.sql`** — bay C/D 92.9%→100.0%
   (118→127/127 both). 9 rows had NULL `parity_status`/`parity_source` — all on the foreclosure
   track for 4 auction dates the last AJAX harvest pass hadn't reached yet (harvest-lag, not a
   matching-key bug, not a PropertyOnion-exclusion artifact — zero propertyonion rows in bay).
   Two independent agents each re-ran the live `bay.realforeclose.com` AJAX harvest (one in-process
   import of the existing `scripts/shard2_run2450_ajax_realforeclose_harvest.py`, the other a
   from-scratch reimplementation) and got byte-identical case numbers before promoting
   `parity_status='matched_clean'`.

3. **`20260719l_gtm22j_shard6_bay_g_pk1000_real_ordinance_backfill.sql`** — bay G 27.3%→96.5%
   (LEAST(density=96.5, far=100.0, pk1000=100.0), pk1000 was the sole binding constraint, now
   11/11). 4 `zone_standards` rows (Panama City MU-1, Bay Co. unincorporated C-1/C-3A, Panama City
   Beach CH) backfilled with real `parking_per_1000sf` values extracted via pdfplumber from the
   jurisdictions' own current ordinance PDFs (Panama City ULDC Ch.108 Table 108-1; Bay County LDR
   Ch.25 Table 25.1; PCB LDC Table 4.05.02.A) — verified independently by two agents, both
   downloaded and extracted the PDFs themselves rather than trusting a citation. **Disclosed
   judgment call**: none of the three tables publish a rate broken out by exact zone code; each
   value is mapped from the closest matching general-commercial/retail use category. Panama City
   MU-1 in particular could plausibly use the table's 3.33 "retail" rate instead of the 4.0
   "office" rate applied here — flagged in the migration's `ordinance_section` text for future
   review, not hidden.

## NOT SHIPPED — structurally blocked, no fabrication path exists (BLANK > WRONG)

- **flagler B/F, bay B/F** (closed_sold=0 in all four cases): zero `multi_county_auctions` rows
  have `sold_amount` populated for flagler or bay, and both `tax_deed_outcomes`/
  `foreclosure_outcomes` have zero rows for either county. Root cause is genuinely a missing
  independent-source scraper, not a backfill gap:
  - **flagler**: the two clerk-adjacent sources reachable from this sandbox
    (`flagler.realtdm.com` case detail, `flagler.realtaxdeed.com` live-bidding AJAX) do not expose
    a winning-bid field for tax deed cases (confirmed by reading the actual response payloads).
    The two sources that plausibly would (`qpublic.schneidercorp.com` sales history,
    `records.flaglerclerk.gov` Landmark Web official records) are blocked by a WAF (403) and a live
    reCAPTCHA v3 challenge respectively. Firecrawl (which is specifically built to get past this
    class of WAF) returned HTTP 402 "Insufficient credits" — **this is a billing/account decision,
    not a per-session spend, so per CLAUDE.md `spend_over_10: STOP and confirm` it is flagged to
    Ariel rather than resolved unilaterally.** This exact ceiling has now been independently
    rediscovered across 9+ prior sessions (shard1/4/5/6/7/9/10/13, including one explicit
    fabrication-and-revert, `508ed2dc`) — it is convergent, not under-investigated.
  - **bay**: `bay.realforeclose.com`'s AJAX endpoint only carries sold-to/winning-bid data during
    the live auction session window, not retroactively. The only remaining lead for the 20 already-
    concluded historical cases is OCR'ing scanned (no text layer) recorded Certificate of
    Title/Sale PDFs at `records2.baycoclerk.com` — low-confidence (COTs don't reliably state sale
    price) and out of scope for a diagnostic pass. A durable fix requires a day-of-auction scraper
    architecture change, not a backfill.
  - Neither county's PropertyOnion `po_sold_amount` field was used as a substitute — the evaluator
    itself excludes `data_source='propertyonion'` rows unless `tier1_authoritative=true`, and for
    3 of bay's 20 concluded rows PropertyOnion's own `auction_status` disagrees with ours, which
    would have injected wrong values.

- **hillsborough I** (68.0%, 623/916, unchanged): the first-pass diagnostic proposed a
  point-in-polygon spatial fix keyed on each auction row's own lat/lon, and found 204 of the 293
  gap rows share a placeholder Tampa-downtown centroid coordinate, concluding those 204 were
  blocked behind an upstream geocoding fix (capping any same-session fix at ~75%, still a fail).
  **The adversarial refuter found this reasoning was wrong**: the I-metric's zone join key is
  `parcel_id`, not lat/lon (confirmed by re-reading the evaluator SQL directly) — 511 of the 740
  rows sharing that same placeholder coordinate are *already* `card_complete=true` in production,
  proving the bad coordinate does not block a match when `parcel_id` already resolves. The real
  fix is a `parcel_id`/folio-keyed zoning lookup (not a point-coordinate query) for the 268
  has-parcel_id gap rows, which was never attempted or verified live this session. **No fix was
  applied** — applying the original point-coordinate-keyed scraper spec as proposed would have
  been correct for only ~64 of 293 rows and silently wrong (or a no-op) for the rest.
  Confirmed-real building blocks for a future session: Hillsborough County's own unincorporated
  zoning layer (`maps.hillsboroughcounty.org/.../DSD_Viewer_Zoning_Regulatory/MapServer/0`) and
  City of Tampa's own zoning layer (`arcgis.tampagov.net/.../OpenData/Planning/MapServer/28`) are
  both live and return real zones — Plant City has no live zoning-layer source found.

- **bay I** (93.7%, 119/127, unchanged): 8-row gap splits into 2 timeshare-foreclosure rows (no
  real property parcel exists for these by definition), 2 rows with UI-label garbage in
  `parcel_id` (`'Property Appraiser'`, `'MULTIPLE PARCELS'` — needs a real browser to read the
  correct DOM field, `bay.realforeclose.com` returns 403 to curl/WebFetch), 1 calendar-sweep
  placeholder for a genuinely-future sale, 1 row where the underlying sale already closed per the
  clerk PDF but the row is stuck at `auction_status='upcoming'` (a safe unstick-only SQL fix was
  drafted but does not move the metric by itself — it only re-arms the existing detail-scraper,
  and even a full best-case fix caps at ~121/125, still under the 95% bar), and 2 Lynn Haven
  parcels the county's own GIS explicitly refuses to classify (`ZONING='See FLU'`, defers to a
  city Future Land Use map with no parcel-level digital API). Not shippable this session under
  BLANK > WRONG.

## VERIFICATION PROTOCOL

Per-county `pencil_dod_evaluate_county` before/after pasted above (live RPC, re-run after each
migration). Did not run `gold_standard_loop()`/`gold_standard_certify()` — other shards may be
mid-flight per PARALLEL-FLEET RULES; per-county evaluation is the correct verification surface for
this session.

## NEXT-SESSION PRIORITIES

1. **hillsborough I**: build a `parcel_id`/folio-keyed (not coordinate-keyed) zoning lookup against
   the confirmed-live Hillsborough County + City of Tampa layers for the 268 has-parcel_id gap
   rows. Ceiling unknown until the parcel-id-keyed query is actually run — do not assume the
   coordinate-based ceiling estimate from this session's refuted finding.
2. **flagler/bay B+F**: flag Firecrawl credit top-up decision to Ariel (billing, not a per-session
   spend). If unblocked, retry `qpublic.schneidercorp.com` scrape for flagler. For bay, evaluate
   whether a day-of-auction live scraper is worth building vs. OCR'ing scanned Certificates of
   Title.
3. **bay I**: needs browser automation (Playwright/firecrawl-browser) to read `bay.realforeclose.com`
   detail-page DOM correctly for the 2 UI-label-polluted rows, plus a decision from Ariel on
   whether timeshare-foreclosure rows should be excluded from the I-metric's `card_rows`
   denominator (a definitional change to the evaluator, not a data fix — flagged, not applied).

---
dispatch_id: 1f302343-9361-451a-8baa-7c22dd8844d8
chat_session: architect-20260719T160000
