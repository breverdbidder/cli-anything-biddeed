# Gold Standard shard-12: jefferson — 3rd firing addendum

dispatch_id: 0f9adc6e-3318-4b04-b0bd-119b07405d40 (same dispatch, re-fired)
mode: ULTRALOOP native (ultracode opt-in — Workflow fan-out: 3 blind finders, 0 refuters dispatched
since 0 finders claimed a viable source)

## Result: still unchanged at 8/10 (A,C,D,E,G,H,I,J PASS; B,F FAIL). No new lever found. BLANK > WRONG.

### Live state at start of this firing (`pencil_dod_evaluate_county('jefferson')`, via REST RPC —
psql direct connection failed on `SUPABASE_DB_PASSWORD` auth in this session's sandbox; REST API with
`SUPABASE_SERVICE_ROLE_KEY` worked and is the verified path used throughout)
```json
{"A":{"pass":true,"metric":1,"detail":"fc=1 td=2"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100.0,"detail":"matched_clean=3"},
 "D":{"pass":true,"metric":100.0,"detail":"matched_any=3"},
 "E":{"pass":true,"metric":100.0,"detail":"parcel_linked=3"},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000="},
 "H":{"pass":true,"metric":13.8,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":true,"metric":100.0,"detail":"card_complete=3 of 3"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=3 (triangle + two-arm CMA + ml_score + max_bid)"},
 "county":"jefferson","auctions_total":3}
```
Identical to both prior firings — the underlying blocker (case `25-CA-164`, defendant Thompson,
judgment $86,285.09, sale 2026-06-25, `sold_amount IS NULL`) has not resolved on its own.

### What this firing did differently
Before fanning out, re-tested the WebFetch-vs-Playwright asymmetry flagged in the hillsborough/calhoun
4th-firing report as a lead worth testing on jefferson specifically (not yet attempted here before this
firing): WebFetch reaches both `civitekflorida.com/ocrs/county/33/` and
`myfloridacounty.com/orisearch/33` cleanly, with no visible Turnstile challenge in the rendered HTML —
confirming the same vendor-stack behavior seen on Calhoun's county 07. But this does **not** unblock
anything: WebFetch is read-only and cannot execute the JS-driven form POST the search requires; a
GET-param submission attempt (`?partyName=Thompson&docType=CERT+TITLE`) just re-rendered the blank
form. This confirms the block is a genuine form-automation gap, not a network/IP block — consistent
with, not contradicting, the two prior firings' Playwright-based finding that actual submission is
Turnstile-gated.

With that confirmed as still a dead end (not a new lever, just re-verified), a 3-way finder fan-out
ran fresh angles not in either prior firing's list:

1. **jud2.flcourts.org / 2nd Judicial Circuit official site** — `jud2.flcourts.org` does not exist
   (DNS `ENOTFOUND`); the real domain is `2ndcircuit.leoncountyfl.gov`, which has no case-search tool
   of any kind and only links back to `jeffersonclerk.com`/Civitek (both already exhausted).
2. **myflcourtaccess.com** (statewide FL Courts E-Filing Portal) — registered-user document filing
   only, zero public case-search capability.
3. **floridacourtaccess.org/jefferson-county** — live (HTTP 200) but a static directory page with no
   functional search; routes back to the same exhausted infrastructure.
4. **floridapublicnotices.com** — a genuine live, searchable statewide legal-notice database (working
   permalinks, county/newspaper/date filters confirmed), but no exposed case-number/party-name search
   parameter; site-restricted WebSearch for "Jefferson"+"Thompson"/"25-CA-164" returned zero hits.
5. **ECB Publishing / Monticello News** (Jefferson's actual legal-notice publisher, confirmed — the
   Big Bend region's other notice vendor, `omg-legals.media.clients.ellingtoncms.com`, carries no
   Jefferson County pattern) — archive is PDF-only and unparseable via WebFetch; zero case-specific
   hits regardless.
6. **Trellis.law** — 403 Cloudflare-blocked, same pattern as `qpublic.schneidercorp.com`.
7. **CourtListener/RECAP** — indexes federal dockets only; structurally out of scope for FL state
   trial courts.
8. **UniCourt** — HTTP 405 on direct fetch; FL 2nd Circuit coverage not confirmed to include Jefferson
   specifically (scoped to Leon County Courthouse in its own materials).
9. **foreclosureauctiondata.com** — genuinely new find, has a case-search UI covering Jefferson County
   FL, but query endpoints returned HTTP 400 / are JS-gated. Excluded on principle regardless of
   access: by its own description it's a commercial DOR/parcel-data aggregator, the same
   non-independent tier as PropertyOnion — would not count as an independent source even if unblocked.
10. **publicnoticeads.com** — empty/unreachable via WebFetch.

**Structural finding (new this firing):** under FL Statute 45.031, the pre-sale "Notice of Sale"
(newspaper-published) and post-sale "Certificate of Sale" (court-filed, carries the winning bid) are
legally distinct documents. No Florida newspaper practice of publishing post-sale "high bidder" results
was found (unlike sheriff-sale states). This means the entire newspaper/notice-aggregator channel —
items 4, 5, 9 above and the newspaper angle generally — is **structurally incapable** of ever carrying
a sold amount, independent of any search-interface limitation. This narrows future firings: don't
re-spend budget on notice-aggregator angles for B/F on any FL foreclosure county.

0 of 3 finders claimed a viable independent source, so 0 adversarial refuters were dispatched (nothing
to refute). No sold_amount was fabricated.

### Verification protocol followed
- `pencil_dod_evaluate_county('jefferson')` re-run live via Supabase REST RPC before and after this
  firing's work — identical both times, pasted above. (psql direct connection failed on password auth
  in this sandbox; documented as an operational finding below, not worked around by any DB-write
  shortcut — REST API with the service-role key is a sanctioned equivalent path per CLAUDE.md.)
- 2 new rows written to `gold_standard_ultraloop_audit` (ids **8218**, **8219**;
  `dispatch_id=0f9adc6e-3318-4b04-b0bd-119b07405d40`, `letter=B`/`F`, `survived=false`,
  `ultraloop_mode=native`), carrying the full 11-source evidence list, the structural
  FL-45.031-newspaper finding, and confirmation no fabrication occurred — so this third exhaustion
  pass is on record and won't be silently re-attempted without genuinely new evidence.
- `gold_standard_loop()`/`gold_standard_certify()` not run — jefferson is not close to 10/10 (2 FAIL
  letters, same root cause), and per PARALLEL-FLEET RULES this session did not confirm other shards are
  idle, so per-county evaluation only.

### Operational finding: psql direct connection failing in-session
`PGPASSWORD="$SUPABASE_DB_PASSWORD" psql "postgresql://postgres.mocerqjnksmhcjzxrewo@aws-0-us-west-2.pooler.supabase.com:5432/postgres"`
returned `FATAL: password authentication failed for user "postgres"` twice, from two different pooler
IPs, on the first diagnostic call this firing. The REST API path (`$SUPABASE_URL/rest/v1/rpc/...` with
`$SUPABASE_SERVICE_ROLE_KEY`) worked immediately and was used for both the read (evaluate_county) and
the write (ultraloop_audit insert) in this firing. **VERIFIED**: REST path works, confirmed by the
200/201 responses pasted above. **UNKNOWN**: whether `SUPABASE_DB_PASSWORD` is stale in this GHA
runner's env vs. the live DB, or a transient pooler auth issue — worth a fleet-wide check if other
shards report the same psql failure, since several existing playbooks (E parcel linkage, G zoning
backfill) assume psql works.

### Escalation status: unchanged from the original session report and 2nd-firing addendum
Same two options, still outside this session's authority: a paid court/official-records API (not
covered by the existing ARM-2 pre-authorization, scoped to retail-comps for criterion J), or a
one-time manual CAPTCHA solve to seed this single fact (jefferson is low-volume — 3 total auctions —
so per-case manual seeding may be more practical than building unattended infrastructure that cannot
be wired to a cron per the WIRING MANDATE).

### Honesty Protocol tags
- WebFetch reaches both Civitek OCRS and myfloridacounty ORI forms without a visible Turnstile
  challenge, but cannot submit them (read-only, no JS execution): **VERIFIED** (live WebFetch calls
  this firing, outputs summarized above).
- 10 additional avenues checked and refuted this firing, 0/10 viable, so 0 adversarial refuters
  dispatched: **VERIFIED** (live re-fetches by finder agents, evidence in `gold_standard_ultraloop_audit`
  ids 8218/8219).
- FL Statute 45.031 pre-sale/post-sale document distinction structurally rules out the entire
  newspaper/notice-aggregator channel: **INFERRED** (statutory reasoning + absence of any counter-example
  found in this firing's searches, not a legal-counsel-confirmed reading).
- No sold_amount/winning-bidder recoverable from any of the 10 new sources or the WebFetch retest:
  **VERIFIED**.
- Paid-API or manual-solve remain the only real unblock levers: **INFERRED** (unchanged from prior
  firings — no new information this firing changes that assessment).
