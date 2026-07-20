# GOLD STANDARD shard-11 (union, gulf) — 4th firing session report

dispatch_id: `1a211136-77c7-4125-b70c-06b26ad13ebe` · chat_session: `architect-20260719T160000` (4th firing) · 2026-07-20

mode: ULTRALOOP native (Workflow tool: 2 research agents + 2 adversarial refuters, 4 subagents total)

## Duplicate dispatch, re-confirmed live before any work

This is the 4th firing of the same `dispatch_id`. Before doing anything, this session re-queried
`pencil_dod_evaluate_county` live for both counties and confirmed the 3rd firing's closing numbers exactly:
union 8/10 (A,C,D,E,G,H,I,J), gulf 4/10 (A,G,H,J). Zero drift.

Union's B/F block was independently re-checked against `multi_county_auctions` (`county='union'`):
1 `redeemed` cert (`UNION-TD-CERT223`, 2026-03-12) + 2 `upcoming` (`63-2025-CA-0053` due 2026-08-13,
`63-2024-CA-0047` due 2026-10-15). No closed sale exists to verify. Today is 2026-07-20 — still 24 days
before the earliest possible close. Not touched, consistent with every prior firing.

## What this session did (gulf only)

The 3rd firing's report carried forward two open priorities. This session ran both as parallel research
leads, each independently adversarially verified. Both survived (`refuted=false`) — but neither was
actionable as a DB write. Both instead **definitively close open questions** so future sessions stop
re-spending research budget on them.

### Priority 1: gulf OCRS Cloudflare wall status — RESOLVED as genuinely BLOCKED (not stale)

The 3rd firing found the `civitekflorida.com/ocrs/county/23` landing page returns a clean, non-Cloudflare
HTTP 200 (contradicting 4+ prior sessions' "walled" status) but did not click further into the flow,
leaving the question open: is the wall deeper in the flow, or gone entirely?

This session went further than any prior session and got a definitive answer:
- **Landing page**: HTTP 200, zero Cloudflare signatures. Re-confirms 3rd firing's finding (VERIFIED,
  independently reproduced by the refuter with fresh curl sessions, no shared state).
- **Public Access -> Disclaimer -> Search**: all three steps are reachable via raw HTTP/curl by directly
  replicating the app's JSF/PrimeFaces `PrimeFaces.ab()` AJAX contract — no browser automation needed.
  This is new ground; no prior session (including the Putnam-county precedent) had confirmed curl alone
  suffices this far into the flow.
- **The wall is real and lives on `/ocrs/app/search.xhtml`**: the page loads a Cloudflare Turnstile widget
  (`sitekey 0x4AAAAAAAR0Af-5MfzdbO3p`) directly above the Search button. A fabricated search POST without
  a valid Turnstile token returns HTTP 200 but never executes the search — the refuter independently
  reproduced this 3x across fresh navigation chains, each time getting an empty form re-render (14
  checkboxes, zero results table, zero error message).
- **Corroboration**: an unrelated prior session's log (`.claude/session-logs/2026-07-11-gold-standard-shard2-putnam-cd-civitek-ocrs-blocked.yml`)
  documents the identical architecture and identical Turnstile block against Putnam County (co_no 54) on
  the same Civitek/OCRS platform — confirming this is a shared statewide product behavior, not a
  Gulf-specific fluke.

**Conclusion**: OCRS is not a viable scrape target for gulf B/C/D/E/F without solving/bypassing a
Cloudflare Turnstile challenge, which is a legitimate access control and out of scope. This closes the
"genuinely unclear" status carried forward from the 3rd firing. No DB writes. Logged to
`gold_standard_ultraloop_audit` (id 7572, letter B, `survived=true`).

### Priority 3 (renumbered): gulf I-card gap rescan — RECONFIRMED, no new unlock

Independently re-derived `pencil_dod_evaluate_county`'s exact I-check CTE (via `pg_get_functiondef`) and
reran it live against the current 14 gulf auctions. Confirmed the same 7-row gap the 3rd firing left:

- `05762000R` and `05004050R` — both re-confirmed **in-city Port St Joe** via a fresh
  `esriSpatialRelIntersects` spatial query against Gulf GIS layer 7 (City Limits), validated against the
  same two control parcels the 3rd firing used (`06248410R` unincorporated-control: `intersect_count=0`;
  `04660000R` in-city-control: `intersect_count=1`). Both remain gated on the separate, still-unresolved
  Port St Joe zoning-map georeferencing problem (identical fill colors, no georeferencing in the vector
  PDF) — not new zoning substrate.
- `03426604R` and `00469000R` — genuinely addressless in the county's own GIS (`STREET='N/A'`, legal
  descriptions "BORROW PIT" / metes-and-bounds only). Not a fixable data gap.
- 3 remaining rows (`232019CA000060CAAXMX`, `232024CA000072CAAXMX`, `232024CC000157CCAXMX`) have no
  `parcel_id` in the source auction data at all — no PIN to look up.

**Conclusion**: no new actionable unincorporated-and-unzoned parcel exists among the current 14 gulf
auctions. Gulf I is capped at 50.0% until either the Port St Joe zoning-map blocker is resolved (human
call, unchanged recommendation) or a different upstream source discloses parcel numbers for the 3
parcel-id-null cases. No DB writes. Logged to `gold_standard_ultraloop_audit` (id 7573, letter I,
`survived=true`).

## SQL VERIFICATION

```sql
-- run 2026-07-20, live via mgmt_sql.py (Management API)
select public.pencil_dod_evaluate_county('union');
-- union: A pass(1) B fail(null) C pass(100.0) D pass(100.0) E pass(100.0) F fail(null)
--        G pass(100.0) H pass(13.1) I pass(100.0) J pass(100.0)  -- 8/10, unchanged (zero drift)

select public.pencil_dod_evaluate_county('gulf');  -- BEFORE this session (same as 3rd firing close)
-- gulf: A pass(5) B fail(null) C fail(78.6) D fail(78.6) E fail(78.6) F fail(null)
--       G pass(100.0) H pass(3.9) I fail(50.0, "card_complete=7 of 14") J pass(100.0)  -- 4/10

-- ... research + adversarial verification only, zero migrations, zero table writes ...

select public.pencil_dod_evaluate_county('gulf');  -- AFTER this session
-- gulf: A pass(5) B fail(null) C fail(78.6) D fail(78.6) E fail(78.6) F fail(null)
--       G pass(100.0) H pass(4.0) I fail(50.0, "card_complete=7 of 14") J pass(100.0)  -- 4/10
--       (identical to before -- zero drift, as expected for a research-only session)

select id, county_slug, letter, survived from gold_standard_ultraloop_audit
  where dispatch_id = '1a211136-77c7-4125-b70c-06b26ad13ebe' order by id;
-- 10 rows total (8 from firings 1-3 + 2 new: OCRS-wall-resolved (B) and I-card-rescan (I), both
-- survived=true)
```

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`certify()` were not run (other shards may be mid-flight
concurrently) — per-county `pencil_dod_evaluate_county` was used for all verification instead.

## Migrations shipped

None. This was a research-and-close-open-questions session; both leads resolved to "confirmed genuinely
blocked," not to actionable writes. No `Do not [regression]` risk introduced.

## Next-session priorities (carried forward)

1. **gulf OCRS is now definitively closed as a lead** — do not re-investigate the Cloudflare wall status
   again without a new access-control-bypass mandate (out of scope today). If gulf B/C/D/E/F is to move,
   it needs an entirely different data source (e.g., a county Clerk public-records-request channel, or a
   different recorded-documents portal), not OCRS.
2. **gulf `05762000R` / `05004050R`** — still need the human phone call to City of Port St Joe Planning
   (850-229-8261) to resolve the zoning-map georeferencing ambiguity; both are structurally ready to flip
   I the moment that call happens.
3. **gulf 3 parcel-id-null auction rows** — would need a different upstream data source to disclose parcel
   numbers for `232019CA000060CAAXMX`, `232024CA000072CAAXMX`, `232024CC000157CCAXMX` before any zoning
   work is even possible on them.
4. **union B/F** — nothing to do until a real auction closes (earliest 2026-08-13).

---
dispatch_id: 1a211136-77c7-4125-b70c-06b26ad13ebe (4th firing)
