# Gold Standard Shard-5 — sumter / liberty / alachua — dispatch `39359e83-a5a2-4726-ab76-72513ae8bab9`

Session: autonomous 6h-budget daily run, loop run 13909, 2026-08-24. ULTRALOOP mode: fan-out fix agents per county + independent adversarial verifiers (Workflow `wf_57f180c5-785`, 12 subagents, 264 tool calls). Audit rows: `gold_standard_ultraloop_audit` ids 17666-17674.

## Result summary (live, re-verified after session close)

| County | Before | After | Letters touched |
|---|---|---|---|
| sumter | 9/10 | 9/10 (unchanged) | C — genuine structural ceiling, documented |
| liberty | 7/10 | 7/10 (unchanged) | A/B/F — genuine structural ceiling, documented |
| alachua | 5/10 | 5/10 (unchanged pass-count, real progress on I) | I: 81.2%→91.8% (still FAIL, <95%). C/D/E/J confirmed structural ceiling this session. |

No county flipped a letter from FAIL to PASS this session. This is an honest result, not a failed session — every claim below carries live before/after evidence and survived (or was correctly caught by) independent adversarial re-verification. Full commit for alachua's real fix: `eef72a55`.

## Sumter — letter C (structural ceiling, no write)

matched_clean=22/24 (91.7%, need ≥95%). The 2 gap rows are `case_number='104'` (parcel C27-268, Tax Deed #5066, cert 104/2020) and `case_number='1400'` (parcel N33-021, Tax Deed #5064, cert 1400/2023), both `auction_status='CANCELLED'` / `parity_status='CLERK_SSOT_CANCELLED'`, both originally noticed for a **2026-09-10** sale — still in the future as of this session (2026-08-24).

Researched live: sumterclerk.com public tax-deed notices (confirmed both cases' TD#/certificate#/parcel/assessed-owner details), sumtertaxcollector.com, Sumter Sun Times legal notices, and the clerk's "Lands Available for Taxes" page (states no properties currently listed — neither parcel present, which is expected pre-sale, not evidence of the cancellation). `public.tax_deed_outcomes` has zero rows for county=sumter matching either case_number or parcel_id (re-verified live both pre- and post-research).

Per criterion C's own independent-source rule and the gadsden precedent (`supabase/migrations/20260823_architect_triage_19393_gadsden_C_parity_gate_unblock.sql` — the only legitimate template for reclassifying a `CLERK_SSOT_CANCELLED` row, and only when genuine independent outcome evidence already exists), no write was made. **This is a genuine structural ceiling, not a bug**: it cannot legitimately close until real independent confirmation exists, which is only possible at/after the 2026-09-10 sale date — the notices found are pre-sale scheduling notices, not outcome records. Next session targeting sumter C: re-check `tax_deed_outcomes` and sumterclerk.com's post-sale results after 2026-09-10.

Adversarial verify: **survived=true** (live re-query confirmed 91.7% unchanged, confirmed zero rows in tax_deed_outcomes, confirmed the structural-ceiling conclusion is accurate).

## Liberty — letters A/B/F (structural ceiling, no write)

Only 1 auction row exists (`case_number='24-CA-22'`, foreclosure, `auction_date='2026-07-21'` — over a month in the past — `auction_status` still shows `'upcoming'`, stale). C/D/E/G/H/I/J already PASS on this single row and were **not** touched or regressed.

- **A** (dual-product, fc=1 td=0): `https://libertyclerk.com/courts/tax-deeds/` returns HTTP 200 with literal "There are no properties on the list of tax deeds at this time." No RealAuction/RealTaxDeed/ArcGIS platform link found anywhere on the page; WebSearch found no third-party listings either. Plausible real ceiling for an ~8K-population county (F.S. 197 tax deed sales only occur when a certificate goes unredeemed). **Note for future sessions**: `scripts/shard7_liberty_fixes.py` (2026-06-19) previously guessed at `liberty.realforeclose.com`/`liberty.realtaxdeed.com` and a `public.counties` config table that does not exist, and fabricated placeholder data (assessed_value=$50000, synthetic bid_decisions) when it found 0 real auctions — that script's approach is banned ghost-success behavior and should not be revived or trusted as a source of truth.
- **B/F**: `https://libertyclerk.com/courts/foreclosure-sales/` returns HTTP 200, case 24-CA-22 no longer listed as upcoming (implying it resolved), but the clerk provides no outcome archive or case-detail page. The only case-lookup system, Civitek OCRS (`civitekflorida.com/ocrs/county/39/`), is a stateful JSF/PrimeFaces form not drivable via curl/WebFetch (guessed sub-paths 404). WebSearch found no independent record of the actual disposition (one floridapublicnotices.com hit was a same-plaintiff but unrelated Broward County case). No sold_amount/outcome was fabricated.

Adversarial verify: **survived=true on all 3** (live re-queries confirmed A/B/F numbers are byte-identical to session-start baseline — no regression, no unverified improvement claimed). Next session targeting liberty B/F: try to reach Civitek OCRS with a stateful browser tool (Playwright/firecrawl-browser) instead of raw curl, since the JSF form is the only remaining lead for case 24-CA-22's real outcome.

## Alachua — letters C/D/E/I/J (real fix on I, structural ceiling on C/D/E/J)

Full detail in `supabase/migrations/20260824_gold_standard_alachua_cdeij_dispatch39359e83.sql` and `scripts/alachua-I_fix4_gold_standard_c39359e83.py` (already committed/pushed as `eef72a55`).

- **I fixed for real**: 9 rows that already had parcel_id/address but were missing `zoning_code` (3 also missing `assessed_value`) were backfilled via the Alachua County Property Appraiser ArcGIS `Parcels35_view` FeatureServer (same layer proven in `alachua-I_fix.py`/`_fix2.py`/`_fix3.py`). card_complete moved **69/85 (81.2%) → 78/85 (91.8%)** — real, adversarially-verified writes (refuter independently re-queried the live ArcGIS endpoint and confirmed every written value matches). Still 3 rows short of the 95% pass threshold.
- **C/D/E/J confirmed structural ceiling this session**: the remaining 7 rows (all `data_source='calendar_sweep_mca_v3'`, `auction_status='upcoming'`, future auction dates 2026-09-17/2026-10-06) have no discoverable parcel_id/address at any accessible source — verified live via the proven `scripts/shard2_run2450_ajax_realforeclose_harvest.py` AJAX harvester across all 5 relevant auction dates: RealForeclose's own listing shows literal "Property Appraiser"/"MULTIPLE PARCEL" placeholder text with an empty qPublic `KeyValue=` param and empty clerk `docid=`, meaning Alachua County's own auction platform has not linked a parcel to these cases yet. `qpublic.schneidercorp.com` direct query returns HTTP 403 (WAF). `public.refresh_parity_tier1_outcomes('alachua')` was re-run live and correctly no-op'd (only matches real sale outcomes; upcoming auctions don't have one yet).
- **J did not cascade**: checked `bid_decisions` live for all 9 zoning-fixed parcels — only 1 had a pre-existing row; the protected valuations/bid_decisions re-armer (cron 109/111/115, not modified) had not picked up the other 8 within the session window.

Adversarial verify: **C/D/E/I survived=true**. **J survived=false** — the refuter's live metric check confirmed J's 90.6%-unchanged claim exactly, but rejected the claim's supporting narrative after querying the wrong tables (`zoning_assignments`/`sample_properties` instead of `parcel_zones`/`zoning_districts`, and a case-sensitive `county=eq.Alachua` filter that doesn't match the stored lowercase `alachua`). The I-letter refuter, querying the correct tables, independently confirmed the same 9 `parcel_zones` writes are real and dated today. Logged both ledger rows honestly (`gold_standard_ultraloop_audit` ids 17673 true / 17674 false) rather than overriding the automated vote — the practical outcome is unaffected either way since J remains FAIL (90.6% < 95%) before and after.

Next session targeting alachua: re-check `bid_decisions` for the 9 zoning-fixed parcels (cron cascade may have landed by then) before building anything new for J; re-check the 7 no-parcel rows against RealForeclose closer to their auction dates in case the county links a parcel before sale.

## Close-out

`gold_standard_campaign` row for `dispatch_id=39359e83-a5a2-4726-ab76-72513ae8bab9` updated with `criteria_passed` reflecting live per-letter state, `exit_reason='timeout'`, `session_end_at=now()`. No `gold_standard_loop()`/`gold_standard_certify()` invocation this session per PARALLEL-FLEET RULES (other shards concurrently active, verified via git log showing 8 other shard commits landed on main during this session's runtime).
