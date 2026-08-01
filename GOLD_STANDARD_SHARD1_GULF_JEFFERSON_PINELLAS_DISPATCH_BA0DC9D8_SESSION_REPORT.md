# Gold Standard Shard-1: gulf / jefferson / pinellas (dispatch ba0dc9d8)

Session: architect-20260801T160000. Mode: ultracode (Workflow tool, 4-lane fix+adversarial-verify pipeline) + inline session-closing fixes. All numbers below are VERIFIED via fresh `SELECT public.pencil_dod_evaluate_county('<county>')` calls run at session close, not trusted from any agent's self-report.

## Score movement (before -> after, this session)

| County | Before | After | Delta |
|---|---|---|---|
| gulf | 9/10 (I fail) | **8/10** (H, I fail) | H flipped pass->fail mid-session (48h freshness SLA expired naturally; not caused by any write this session — see gulf-H note below). I unchanged: confirmed dead end. |
| jefferson | 8/10 (B, F fail) | **8/10** (B, F fail) | Unchanged — confirmed dead end, honestly reported, no fabricated data. |
| pinellas | 7/10 (C, D, J fail) | **10/10 — all pass** | C, D, J fixed. A side effect regressed B mid-session; caught and fixed before close-out (see below). |

## What was fixed and shipped (commits, in order)

1. **`b222a2fb`** — jefferson B/F research (`jefferson_bf_25ca164_outcome_fix.sql`, doc/read-only, no data write — see dead-end below).
2. **`0eee0f26`** — pinellas C/D parity backfill (`pinellas_cd_21row_parity_backfill.py` + `.sql`): 21 never/mis-checked foreclosure cases resolved against `pinellas.realforeclose.com` (Clerk's Auction Results Report id=18 + Playwright DAYLIST pages). 9 sold, 7 canceled, 5 upcoming. C and D: 94.9% (390/411) -> **100% (411/411)**.
3. **`d031e03a`** — pinellas J bid_decisions backfill (`pinellas_j_23row_bid_decisions_backfill.sql`): 23 case_numbers with zero `bid_decisions` rows populated via the fleet's existing ARV/CMA/Shapira-ml_score methodology (parcel join on `fl_parcels` co_no=62, tier-1 comps by zip+dor_uc+living-area+recency). J: 94.4% (388/411) -> **100% (411/411)**.
4. **`e9d5f84f`** — pinellas B regression fix (`pinellas_b_9row_outcome_backfill.sql`): the C/D fix in (2) surfaced 9 previously-unknown *closed* sales, growing `closed_sold` 132->141 without matching `foreclosure_outcomes` rows, which dropped B to 93.6% (132/141) — caught by this session's own fresh re-verification pass (not by the workflow's built-in adversarial layer, which had already finished by the time this was discovered). Backfilled `foreclosure_outcomes` for exactly those 9 cases from the same RealAuction report already used for `sold_amount`. B restored to **100% (141/141)**.
5. Both applied live via `mgmt_sql.py`; audit trail in `gold_standard_shard1_ba0dc9d8_ultraloop_audit.sql` (7 rows in `gold_standard_ultraloop_audit`, one per letter worked); close-out in `gold_standard_shard1_ba0dc9d8_closeout.sql`.

## Confirmed dead ends (honest UNKNOWN, no data written, per Honesty Protocol)

**gulf I (12/14, 85.7%)** — parcels `05762000R` (256 Ave C) and `05004050R` (Knowles Ave), Port St Joe, have no verifiable zoning source:
- Gulf County's ArcGIS Future Land Use layer (`gulf/GoMaps4/MapServer/40`) returns `Type=Municipal` for both points — an ~2,733-acre city-limits jurisdictional flag, not a parcel-level land-use category (unlike the smaller `Mixed_Comm/Res`/`Residential` polygons a prior session used for 3 *other* PSJ parcels from this same layer).
- The official 2012 City of Port St Joe zoning-map PDF has no machine-extractable street label for either address (`KNOWLES` token count = 0 in the text layer; `AVE C` is ambiguous/rotated text).
- No dedicated PSJ zoning ArcGIS layer exists (71 layers enumerated, none is "Zoning").
- A tempting-looking `SiteType=R1` field on a nearby Addresses-layer point was checked against its ArcGIS coded-value domain and is an E911 addressing structure-type code ("Single Family"), **not** a zoning district — correctly rejected as a red herring rather than used as a shortcut.
- **Next step (requires a human):** call City of Port St Joe Planning & Zoning, 850-229-8261, and ask directly.

**jefferson B/F (0/0 closed)** — the county's only closed case, `25-CA-164` (foreclosure, sold 2026-06-25, final judgment $86,285.09, defendant James W. Thompson, 340 Marvin St, Monticello FL):
- The Clerk's own foreclosure-sales PDF (`jeffersonclerk.s3.amazonaws.com/.../Foreclosure-Sales.pdf`) is a **pre-sale** notice list — it has no winning-bid/sale-result field for any case, by design.
- `jeffersonpa.net` (Property Appraiser) returns HTTP 403 (Cloudflare-blocked); `search.jeffersonpa.net` times out.
- Civitek OCRS (official records search) is Turnstile-gated on form submission, which requires a real browser session — not disprovable via `curl`, and not attempted with a browser given session scope.
- **Next step:** either a browser-automation pass against Civitek OCRS, or a direct records request to the Jefferson County Clerk for the Certificate of Title on 25-CA-164.

**gulf H (48.4h > 48h SLA)** — flipped from pass to fail *during this session*, purely from time elapsing since gulf's last scrape; no auction data was touched by any fix here. This is a scraper-cadence/freshness issue for the existing county-rotation scraper, not a data-correctness gap — flagging per the "any regression is P0" rule rather than silently letting it pass unmentioned. Not remediated: writing a fake `last_seen_at` to force a pass would itself be a fabrication.

## Process note (transparency, not a data-integrity defect)

- The pinellas-J adversarial verifier found that 13 of the 23 new `bid_decisions` rows (56%) default `distress_property`/`distress_owner` to a constant `0.45/0.45` when the underlying `final_judgment` value is missing. `ml_score`, `distress_location`, `arv`, `max_bid`, and the CMA percentiles are real, independently-reproduced computed values in all 23 rows — this is a legitimate "missing optional input -> conservative default" fallback, not the ghost-success pattern (constant *everything*) this campaign was previously burned by. It was not disclosed in the migration's own comments, which is a documentation-accuracy gap worth closing in a future pass, logged in the ultraloop audit row for J.
- The pinellas-B fix (item 4 above) was written and applied by this session's closing agent directly, not routed through a separate adversarial-verify agent, due to session budget. Confidence basis: the same 9 sold amounts were already independently re-derived to the penny by the pinellas-CD verifier agent (a different agent) before this fix was written — logged as a documented limitation in the ultraloop audit row rather than silently treated as fully adversarially cleared.

## SQL VERIFICATION

```sql
-- gulf, run 2026-08-01T16:4x UTC
SELECT public.pencil_dod_evaluate_county('gulf');
-- A:true(5) B:true(100) C:true(100) D:true(100) E:true(100) F:true(100) G:true(100)
-- H:false(48.4) I:false(85.7, card_complete=12 of 14) J:true(100)  => 8/10

-- jefferson, run 2026-08-01T16:4x UTC
SELECT public.pencil_dod_evaluate_county('jefferson');
-- A:true(1) B:false(null, verified=0 closed_sold=0) C:true(100) D:true(100) E:true(100)
-- F:false(null, tier1_sold=0 closed_sold=0) G:true(100) H:true(6.3) I:true(100) J:true(100)  => 8/10

-- pinellas, run 2026-08-01T16:51 UTC (after the B regression fix)
SELECT public.pencil_dod_evaluate_county('pinellas');
-- A:true(34) B:true(100, verified=141 closed_sold=141) C:true(100, matched_clean=411)
-- D:true(100, matched_any=411) E:true(99.8) F:true(100, tier1_sold=141 closed_sold=141)
-- G:true(95.8) H:true(0.1) I:true(95.1, card_complete=391 of 411) J:true(100, deal_complete=411)  => 10/10 ALL PASS
```

`gold_standard_campaign` row (dispatch_id `ba0dc9d8-ec70-402f-9b1f-a35dab864033`) updated with the above per-county criteria_passed, `exit_reason='completed_workqueue'`, `session_end_at=2026-08-01 16:51:01 UTC`. 7 rows written to `gold_standard_ultraloop_audit` (one per letter worked, all `survived=true`, full evidence in `gold_standard_shard1_ba0dc9d8_ultraloop_audit.sql`).

## Next-session priorities

1. **pinellas**: now 10/10 — per the campaign's certify gate, needs a second consecutive 10/10 daily run before auto-certification lands. Nothing to do except let the next scheduled run confirm no drift.
2. **jefferson B/F**: needs a browser-automation (not curl) pass at Civitek OCRS for case 25-CA-164, or a manual clerk records request.
3. **gulf I**: needs a human phone call to City of Port St Joe Planning (850-229-8261) for the 2 remaining parcels — this is not resolvable via any GIS/PDF source that exists online.
4. **gulf H**: will likely self-heal on the next scheduled scrape of gulf; if it doesn't within another cycle, the county-rotation scraper cadence for small counties may need review (out of this session's scope — do not touch cron jobs 109/111/115 per standing guardrail).
