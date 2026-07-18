# GOLD STANDARD shard-7 session report — leon / jefferson / alachua

dispatch_id: `7066f088-5bfc-42d7-8ac1-35a03ab50ecc`
chat_session: architect-20260718T160000
date: 2026-07-18

## Plan vs actual

| County | Planned | Actual | Deviation |
|---|---|---|---|
| leon | fix I (94.5%→95%+) | **10/10, certified-eligible** — I fixed to 96.4% via live parcel_id backfill | None — target hit with margin |
| jefferson | fix A/B/F | A durably fixed (real tax-deed data appeared mid-session); B/F remain correctly blocked (no realized sale yet); **I regressed 100%→33.3%** as a side effect of adding the 2 real rows, then C/D/E/J recovered same session | I not fully recovered — real zoning-jurisdiction verification needed, not guessed |
| alachua | fix C/D/E/I/J | No metric change — root cause fully diagnosed, one new real path found (isol.alachuaclerk.org grantee names → ArcGIS Owner_Mail_Name match), not executed this session | Deferred to next session — time budget |

## Environment notes (useful for future sessions)

- Direct Bash/httpx egress works for: `github.com`, `api.github.com`, `api.supabase.com`, `*.supabase.co`, `api.firecrawl.dev` (currently **HTTP 402 insufficient credits** — re-verify before relying on it), `services.arcgis.com` and other ArcGIS-Online-hosted FeatureServers, and RealAuction-family sites (`*.realforeclose.com`, `*.realtaxdeed.com`) **provided a real browser User-Agent header is sent** (bare httpx UA gets 403 from the WAF).
- County-specific custom domains (e.g. `tlcgis.leon.fl.us`, `qpublic.schneidercorp.com`) fail DNS resolution or return 403/bot-wall from Bash. `WebFetch`/`WebSearch` reach a wider set of domains (different infra) but return AI-summarized content, not raw JSON — good for discovery, unreliable for structured extraction.
- `myfloridacounty.com/orisearch/<co_no>` (statewide Official Records Index used by many small counties) is reachable but the search POST is gated by a Cloudflare Turnstile challenge — **not attempted to bypass**, correctly left as a dead end.
- **`fl_parcels.co_no` is NOT the FL DOR standard county number** — verified live: `co_no=37` actually contains Hernando County parcels (Spring Hill/Brooksville/Weeki Wachee), real Leon (Tallahassee) parcels live under `co_no=47`, and real Jefferson (Monticello) parcels live under `co_no=43`. This is a real, pre-existing data-quality bug in `fl_parcels` — flagged here, **not fixed** (out of scope, would be a large cross-cutting remap; correct co_no discovered empirically per-county by matching `phy_city`). Do not trust `fl_parcels.co_no` against FL DOR's standard numbering without re-verifying the real co_no first.
- `scripts/shard2_run2450_ajax_realforeclose_harvest.py` (`harvest_date(subdomain, county_slug, date_mmddyyyy, platform_domain)`) is a proven, unauthenticated, no-login RealAuction AJAX harvester that returns live `parcel_id`/`property_address`/`assessed_value` per case_number for a given auction date. Reused verbatim for both leon and alachua this session.

## leon — 9/10 → 10/10 (VERIFIED)

**Root cause:** 9 of 165 auctions failed `card_complete` (letter I). Diagnosed each individually:
- 3 rows had address/geo/assessed+market value already present and parity-matched, but `parcel_id` was NULL.
- 2 rows were bare calendar-sweep stubs with no data at all.
- 1 row had `parcel_id='MULTIPLE PARCELS'` (a placeholder, not a real ID).
- 1 row had a real `parcel_id` but that parcel is not in `parcel_zones` (no zone_code).
- 1 tax-deed row had a partial address only.
- 1 row (`2026 CA 000112`) resolved fully live but its parcel also has no zone_code.

**Fix applied:** Live-harvested `leon.realforeclose.com`'s AJAX preview for auction dates 07/20/2026 and 07/22/2026 (unauthenticated), matched by case_number, and recovered the real `parcel_id` for 3 of the 9 rows (`320835 A0440`, `320626 C0050`, `320835 A0510`). Cross-checked: harvested `assessed_value` for all 3 exactly matched the value already stored on each row (88862 / 196141 / 93853) — same real record, high confidence. All 3 confirmed present in `parcel_zones` with `zone_code='RP'` **before** the UPDATE was applied.

Migration: `migrations/20260718_gold_standard_shard7_leon_i_parcel_backfill.sql`

**Adversarial verification (independent Workflow agent, not the fixer):** PASS. Re-derived all 5 checks independently (DB row integrity, structural zone_code requirement via `v_zoning_gold_standard_card`, live re-fetch reproducing the identical parcel_id, live evaluator re-run, idempotency/scope check confirming the UPDATE only touched the 3 intended rows). `gold_standard_ultraloop_audit` id=6830, `survived=true`.

### Before/after (pencil_dod_evaluate_county('leon'))

```
BEFORE: A✓49 B✓100 C✓98.2 D✓98.2 E✓96.4 F✓100 G✓98.7 H✓ I✗94.5(156/165) J✓98.2  → 9/10
AFTER:  A✓49 B✓100 C✓98.2 D✓98.2 E✓98.2 F✓100 G✓98.7 H✓ I✓96.4(159/165) J✓98.2  → 10/10
```
E also ticked up (96.4%→98.2%) as a side effect of the same parcel_id backfill. **Leon is now 10/10 — certification lands automatically after a second consecutive 10/10 daily 07:30Z run**, per the campaign's certification gate.

## jefferson — 7/10 → 7/10 (different composition; A durably fixed with real data)

**Starting state:** A FAIL (fc=1, td=0), B FAIL (0 closed), F FAIL (0 closed); C/D/E/G/H/I/J passing (auctions_total=1).

A prior session (2026-07-05, logged in `pipeline.counties.notes`) had already exhaustively confirmed Jefferson had zero real tax-deed channel (RealAuction tenants unprovisioned/sandbox-only) and no independent sale-results source for the single foreclosure case. This session independently re-attempted a B/F path (Civitek OCRS, myfloridacounty ORI) and hit a Cloudflare Turnstile CAPTCHA on the ORI search — correctly stopped, not bypassed.

**New finding (this session, live):** `jeffersonclerk.com`'s tax-deed-sales page now links a PDF posted **2026-07-15** — `Pending-Tax-Deed-Sales.pdf` — listing 2 real, currently-scheduled tax deed sales (26-TD-04, 26-TD-05, both 8/19/2026). This did not exist at the prior session's 07-05 check. Fetched and parsed live, confirmed verbatim.

**Fix applied (3 migrations, in order):**
1. `20260718_gold_standard_shard7_jefferson_a_taxdeed_ingest.sql` — inserted the 2 real tax-deed rows. **A: FAIL(td=0) → PASS(td=2)**. Side effect (expected, not a bug): C/D/I/J dropped because the 2 new rows had zero enrichment beyond the clerk PDF's site address.
2. `20260718_gold_standard_shard7_jefferson_taxdeed_enrichment.sql` — backfilled real `assessed_value`/`market_value`/`latitude`/`longitude` for both new parcels from FL GIO cadastral (`fl_parcels`, real co_no=43 for Jefferson — see environment notes), cross-verified by exact parcel_id + exact street address match to the clerk PDF. Marked `parity_status='matched_clean'` using the same `fl_gio_cadastral_corroboration` methodology already established for jefferson's original row. **C/D/E: back to 100%.**
3. Reran `scripts/shard5_run3786_jefferson_j_generator.py` **unmodified** (reused verbatim, not rewritten) now that market_value exists for the new rows. **J: 33.3% → 100%.**

**Not resolved — I remains FAIL (33.3%, 1 of 3):** `parcel_zones` has exactly 1 zoned parcel for jefferson countywide (the original R-1A foreclosure parcel, jurisdiction=Monticello town). Whether the 2 new rural-acreage parcels (6.4ac / 7.63+2.63ac, "Brooks Rd"/"Cherry Tree Rd") fall under Monticello town or unincorporated Jefferson's A-1 Agricultural district (which already has real zone_standards) could not be verified live this session — `fl_parcels.municipality='MONTICELLO'` is a mailing-address field, not an incorporation boundary, and the FL Statewide Cadastral ArcGIS query for a definitive tax-authority code timed out. **Left unresolved rather than guessed** — do not assign `zone_code='A-1'` to these parcels without a real jurisdiction-boundary confirmation.

**B/F remain correctly FAIL:** both tax-deed sales are scheduled for 8/19/2026 (future) — no realized sold_amount exists yet. This is a genuine real-world timing gap, not fabricated.

Audit: `gold_standard_ultraloop_audit` rows for jefferson/A and jefferson/J, both `survived=true` (self-verified with live re-fetch + before/after evaluator diff, since this was investigated directly rather than delegated).

### Before/after (pencil_dod_evaluate_county('jefferson'))

```
BEFORE: A✗(fc=1,td=0) B✗(null) C✓100 D✓100 E✓100 F✗(null) G✓100 H✓ I✓100(1/1) J✓100  → 7/10
AFTER:  A✓(fc=1,td=2) B✗(null) C✓100 D✓100 E✓100 F✗(null) G✓100 H✓ I✗33.3(1/3) J✓100 → 7/10
```

## alachua — 5/10 → 5/10 (no metric change; root cause fully diagnosed, one real path found)

**Confirmed live:** all 10 gap rows (driving C/D/E/I/J failures — same 4-10 rows across all 5 letters) are cases whose `realforeclose.com` listing renders the "Parcel ID" table cell as an anchor with link text **"Property Appraiser"** (not an actual parcel number) linking to a `qpublic.schneidercorp.com` URL — while other cases on the *same* auction dates in the *same* county have real parcel data populated. Reproduced live for 8/10 target cases. The `qpublic.schneidercorp.com` `Q=` query parameter was checked against Alachua's ArcGIS `PublicParcel` FeatureServer (`Prop_ID` field) and does not resolve — it is not a valid parcel key, a dead end regardless of `qpublic.schneidercorp.com`'s own bot-wall (403, not pursued further).

**New path found (adversarial recheck agent), not yet executed:** `isol.alachuaclerk.org` — the Clerk's own Official Records index, linked directly from each RealForeclose case row — is publicly reachable with **no login and no CAPTCHA**, and returns real judgment documents including grantor/grantee names. Alachua's `PublicParcel` FeatureServer can be queried by **`Owner_Mail_Name`** (not `Prop_ID`) using the grantee name recovered from the judgment; this was spot-checked live for one name ("PAUL JEREMY") and returned a clean single match (parcel `02975-002-000`, address `10815 NW 199TH AVE`).

**Next session:** for each of the 8-10 placeholder cases, fetch the case's `isol.alachuaclerk.org` docid page → extract grantee name(s) → query `PublicParcel` FeatureServer with `Owner_Mail_Name LIKE '%<grantee>%'` → backfill `property_address`/`parcel_id` on the MCA row. This should cascade to resolve C/D/E, and I/J should follow per the dependency chain (I ⊆ E by construction; J's gap is the identical 4 rows as C/D).

### Before/after (pencil_dod_evaluate_county('alachua')) — unchanged

```
A✓3 B✓100 C✗92.2(47/51) D✗92.2(47/51) E✗80.4(41/51) F✓100 G✓97.8 H✓ I✗78.4(40/51) J✗92.2(47/51)  → 5/10 (no change)
```

## Verification evidence (live, this session)

```json
// leon — pencil_dod_evaluate_county('leon'), post-fix
{"A":{"pass":true,"metric":49},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":98.2},
 "D":{"pass":true,"metric":98.2},"E":{"pass":true,"metric":98.2},"F":{"pass":true,"metric":100.0},
 "G":{"pass":true,"metric":98.7},"H":{"pass":true},"I":{"pass":true,"metric":96.4,"detail":"card_complete=159 of 165"},
 "J":{"pass":true,"metric":98.2},"auctions_total":165}

// jefferson — pencil_dod_evaluate_county('jefferson'), post-fix
{"A":{"pass":true,"metric":1,"detail":"fc=1 td=2"},"B":{"pass":false,"metric":null},
 "C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},
 "F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0},"H":{"pass":true},
 "I":{"pass":false,"metric":33.3,"detail":"card_complete=1 of 3"},"J":{"pass":true,"metric":100.0},
 "auctions_total":3}

// alachua — pencil_dod_evaluate_county('alachua'), unchanged
{"A":{"pass":true,"metric":3},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":92.2},
 "D":{"pass":false,"metric":92.2},"E":{"pass":false,"metric":80.4},"F":{"pass":true,"metric":100.0},
 "G":{"pass":true,"metric":97.8},"H":{"pass":true},"I":{"pass":false,"metric":78.4},
 "J":{"pass":false,"metric":92.2},"auctions_total":51}
```

Per the PARALLEL-FLEET RULES, `public.gold_standard_loop()`/`gold_standard_certify()` were **not** run this session (cannot confirm no other shard is mid-flight) — per-county `pencil_dod_evaluate_county` was used for all verification, as instructed.

## Ultracode / ULTRALOOP audit trail

- `gold_standard_ultraloop_audit` rows: leon/I (id=6830, adversarially verified by an independent Workflow agent, `survived=true`), jefferson/A and jefferson/J (self-verified with live re-fetch + evaluator diff, `survived=true`).
- A second Workflow agent independently re-checked the jefferson/alachua "blocked" conclusions rather than accepting them at face value — this is what surfaced the new jefferson tax-deed PDF and the alachua `isol.alachuaclerk.org` path documented above.

## Next-session priority queue (pre-continuation)

1. **jefferson I**: resolve the Monticello-town-vs-unincorporated jurisdiction question for parcels `05-2S-3E-0000-0012-0000` and `01-1S-3E-0000-0021-0000` (real zoning-map/boundary check, not a guess) to restore I to 3/3.
2. **alachua C/D/E/I/J**: execute the `isol.alachuaclerk.org` grantee-name → `Owner_Mail_Name` FeatureServer path for the 8-10 placeholder cases.
3. **jefferson B/F**: will resolve automatically once 8/19/2026 passes and a real sale-results source appears (re-check `jeffersonclerk.com` and the OCRS/ORI paths periodically; do not attempt to bypass the Turnstile CAPTCHA).

---

## Continuation session (2026-07-18, same dispatch re-fired, run4870, ultracode)

This dispatch (`7066f088`) was re-fired later the same day. Live DB state matched the first firing's end-state exactly (leon 10/10, jefferson 7/10, alachua 5/10) confirming no drift/regression. Worked the exact next-session priority queue above, item by item, with `/effort ultracode` Workflow-based adversarial verification per ULTRALOOP PROTOCOL.

### Plan vs actual

| Item | Planned | Actual | Deviation |
|---|---|---|---|
| jefferson I | resolve jurisdiction, restore 3/3 | **Done — 33.3%→100.0% (3/3), PASS.** Jefferson now 8/10. | First-draft migration comment mis-cited `zoning_districts.id=3777`; an adversarial refuter caught it (it was actually `zone_standards.id`, real PK is `11069`) — corrected before shipping, re-verified clean. |
| alachua C/D/E/I/J | execute `isol.alachuaclerk.org` path for 8-10 rows | **1 of 10 rows resolved** (E: 80.4%→82.4%), not the full batch. | The `isol.alachuaclerk.org` path only works when RealForeclose's own AJAX payload carries a non-empty `docid=` cross-reference for that case. Re-harvested all 8 remaining rows live: every one has `docid=&ms=0` (empty) — the Clerk has not cross-referenced a recorded document to those cases. This is the same dead-end the prior firing already found for a different case subset; it is not fabricatable. The one row that *did* move was a previously-discovered-but-never-executed fix (`scripts/shard10_run3645_alachua_e_parcel_backfill.py`, case `01 2024 CA 001683`) found sitting unexecuted in the repo. |
| jefferson B/F | expect auto-resolve after 8/19/2026 | **No change (correctly still FAIL)** — sale date has not arrived; confirmed no independent verified-outcome source exists yet. | None — as planned. Also checked whether the *already-past* foreclosure sale (`25-CA-164`, `auction_status='sold'`, date 2026-06-25) had a recoverable `sold_amount`; `jeffersonclerk.com`'s foreclosures page is a generic WordPress listing page with no per-case sale-results data — dead end, not pursued further (Turnstile-gated ORI remains the only lead, correctly not bypassed). |

### jefferson — 7/10 → 8/10 (VERIFIED)

**Fix:** Both new tax-deed parcels' unincorporated status was verified live via two independent, real sources (not guessed): (1) US Census Bureau Geocoder `geographies/coordinates` (federal, `layers=Incorporated Places`) returned zero incorporated places for both exact coordinates; (2) Jefferson County Property Appraiser's own ArcGIS zoning layer `JC_CITY_ZONING_view` (the same layer that sourced the original parcel's R-1A zone in the prior shard5/run3786 fix) returned zero intersecting features for both points — i.e. genuinely outside Monticello's city zoning coverage. Both parcels were written to `parcel_zones` under `jurisdiction_id=1259` ("Jefferson County"), `zone_code='A-1'` (Agricultural) — the same pre-existing zoning district already documented in this DB as the county's inferred dominant unincorporated zone, with real (non-null) `max_far=0.10`/`max_density_du_acre=1.00` standards.

Migration: `migrations/20260718_gold_standard_shard7_jefferson_i_zoning_backfill.sql`

**Adversarial verification (2 rounds, independent Workflow/Agent, not the fixer):** Round 1 **REFUTED** (confidence 0.85) — caught a real citation bug: the migration comment's `SELECT zd.*, zs.*` (unaliased) produced a JSON object where the duplicate `id` key silently kept `zone_standards.id` (3777) instead of `zoning_districts.id`; the comment wrongly cited 3777 as the zoning_districts PK, and a direct lookup of `zoning_districts.id=3777` resolves to an unrelated Tavares/Lake-County municipal-code row. The refuter explicitly noted the underlying `parcel_zones` writes and both live geocoding/GIS checks held up regardless. Corrected the citation to the real PK (`zoning_districts.id=11069`, whose `zone_standards` row is id=3777) and re-ran verification. Round 2 **SURVIVED** (confidence 0.97) — all 6 checks (Census geocoder ×2, ArcGIS point-in-polygon ×2, DB id lookups, fresh `pencil_dod_evaluate_county`) independently reproduced exactly. `gold_standard_ultraloop_audit` row logged with both rounds' evidence in `refuter_evidence`, `survived=true`.

### alachua — 5/10 → 5/10 (E incrementally improved, no letter flipped)

**Fix:** Applied a deferred write that a prior session (`scripts/shard10_run3645_alachua_e_parcel_backfill.py`, run3645, 2026-07-10) had already fully evidenced but never executed: case `01 2024 CA 001683` → `parcel_id='02975-002-000'` (`PAUL JEREMY & VIRGINIA`, 10815 NW 199TH AVE, via `isol.alachuaclerk.org` docid=3696062 cross-referenced against Alachua's public ArcGIS `PublicParcel` FeatureServer, `Owner_Mail_Name LIKE '%PAUL%JEREMY%'`, unambiguous single match). Its sibling fix in the same old script (case `01 2025 CA 001356`) had already landed in a prior session; this row alone had been missed.

Migration: `migrations/20260718_gold_standard_shard7_alachua_e_parcel_backfill.sql`

**Adversarial verification:** **SURVIVED** (confidence 0.97) — independent Workflow agent re-ran the live ArcGIS query (reproduced the same 2-row result, same unique match), confirmed the DB write and no parcel_id collision, and reproduced the exact evaluator metric (42/51, 82.4%).

**Remaining 9 alachua gap rows — confirmed genuine dead end this session, not re-attempted without new evidence:** re-harvested the live RealForeclose AJAX payload for all 8 case numbers with `parity_status='matched_clean'` but no parcel_id — every one carries an empty `docid=&ms=0` cross-reference (the Clerk has not linked a recorded document to these cases yet). The 9th (`01 2025 CA 003287`) remains the confirmed `MULTIPLE PARCEL` case, correctly unresolvable to one parcel_id. The 4 rows with `parity_status IS NULL` (`01 2023 CA 004261`, `01 2025 CA 003629`, `01 2025 CA 003919`, `01 2025 CC 001552`) are all `data_source='calendar_sweep_mca_v3'` bare stubs for a future 2026-08-18 auction date — the source has not published case detail yet, same pattern as leon's bare calendar-sweep stubs in the first firing. No further real lead exists for alachua this session without fabrication.

### Verification evidence (live, this continuation session)

```json
// jefferson — pencil_dod_evaluate_county('jefferson'), post-fix
{"A":{"pass":true,"metric":1,"detail":"fc=1 td=2"},"B":{"pass":false,"metric":null},
 "C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},
 "F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0"},
 "H":{"pass":true},"I":{"pass":true,"metric":100.0,"detail":"card_complete=3 of 3"},
 "J":{"pass":true,"metric":100.0},"auctions_total":3}   // 8/10 (B, F fail — genuine, future sale date)

// alachua — pencil_dod_evaluate_county('alachua'), post-fix
{"A":{"pass":true,"metric":3},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":92.2},
 "D":{"pass":false,"metric":92.2},"E":{"pass":false,"metric":82.4,"detail":"parcel_linked=42"},
 "F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":97.8},"H":{"pass":true},
 "I":{"pass":false,"metric":78.4},"J":{"pass":false,"metric":92.2},"auctions_total":51}  // 5/10, unchanged letter composition

// leon — pencil_dod_evaluate_county('leon'), re-verified unchanged
{"A":{"pass":true},"B":{"pass":true},"C":{"pass":true},"D":{"pass":true},"E":{"pass":true},
 "F":{"pass":true},"G":{"pass":true},"H":{"pass":true},"I":{"pass":true,"metric":96.4},
 "J":{"pass":true},"auctions_total":165}  // 10/10, stable
```

### Ultracode / ULTRALOOP audit trail (this continuation)

- `gold_standard_ultraloop_audit`: jefferson/I (2 rounds — refuted then survived after citation correction) and alachua/E (survived first pass), both logged with full `refuter_evidence` jsonb, `survived=true`.
- Demonstrates the audit gate working as designed: the refuter caught a real self-inflicted SQL bug (unaliased duplicate-column JSON collision) in the fixer's own citation before it shipped, without touching the correctness of the underlying data write.

### Updated next-session priority queue

1. **alachua C/D/E/I/J**: no further real lead via RealForeclose/isol.alachuaclerk.org this session. Untried options for next session: (a) `qpublic.schneidercorp.com` remains 403/Cloudflare-blocked from Bash — worth a `WebFetch`-based retry (different infra path per the first firing's environment notes); (b) periodically re-harvest the 8 empty-docid cases — the Clerk's cross-reference could appear later as case documents get recorded; (c) the 4 future-auction (`2026-08-18`) bare stubs will self-resolve once the source publishes detail closer to the date, same as leon's pattern.
2. **jefferson B/F**: unchanged — will resolve once 8/19/2026 passes and a real sale-results source appears. `25-CA-164`'s already-passed 2026-06-25 sale still has no recoverable `sold_amount` (jeffersonclerk.com's foreclosures page is a generic listing page, no per-case results; Turnstile-gated ORI correctly not bypassed).
3. **leon**: stable at 10/10 — no action needed; certification lands automatically after a second consecutive 10/10 daily 07:30Z run per campaign rules.
