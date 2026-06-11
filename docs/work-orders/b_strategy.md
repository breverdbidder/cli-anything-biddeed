# Brevard Criterion-B — Corrected Strategy (supersedes wo_brevard_b.md)
*Authored 2026-06-11 after live source-probing + corpus provenance audit. This replaces the "scrape clerk calendar → BECA" model, which is dead.*

## TL;DR
B reads **0.0% and that is the honesty filter working correctly**, not a scraper gap. **99.9% of Brevard closed-sold rows (6,709 of 6,713) carry a sold amount sourced from PropertyOnion** — a competitor we are canonically forbidden to count. B is a **data-provenance problem wearing a scraper costume**. Reaching 95% requires solving THREE blockers, two of which only Ariel can unblock.

## The provenance audit (live, 2026-06-11)
Denominator `closed_sold = 6,713` (4,088 tax-deed + 2,625 foreclosure). Sold-amount provenance:

| Lane | data_source | closed-sold | countable for B? |
|---|---|---|---|
| Foreclosure | propertyonion | 2,621 | NO — competitor |
| Foreclosure | null (PO- keyed) | 4 | NO |
| Foreclosure | brevard_clerk(_scraper) | 0 sold | YES source, but zero outcomes captured |
| Tax-deed | propertyonion | 4,088 | NO — competitor |
| Tax-deed | realforeclose / realtaxdeed / rf_auth_scraper_v1 | 0 sold | YES source, but zero outcomes captured |

The independent scrapers exist (~830 rows) but **none has captured a realized sold amount**. Every price we have is PropertyOnion's.

## The three blockers (precise)

### Blocker 1 — Re-keying (PO-ids → real keys). Claude-solvable.
- Foreclosure: 8,613 rows keyed `PO-#######`; real clerk keys are `05-YYYY-CA-######-XXCA-BC`. Different keyspace. Must match PO row → real case by **parcel_id / address**, not case_number.
- Tax-deed: 4,054 rows keyed `PO-#######`; real RealTaxDeed keys are bare numerics (e.g. `250823`, `241159`). Different keyspace. Match by **parcel_id**.
- Deliverable: a crosswalk table `brevard_case_rekey(po_id, real_case_number, real_keyspace, match_method, match_confidence)` before any outcome lookup is meaningful.

### Blocker 2 — Legitimate source access (host WAF). Needs an access decision.
- Realized **foreclosure** outcomes = **Certificate of Title / Certificate of Sale**, a recorded document in **ACCLAIM Official Records** (`vaclmweb1.brevardclerk.us/AcclaimWeb`), searchable by case_number + document type, **free, no login**. This — not BECA — is the canonical home of the sold amount + grantee.
- Realized **tax-deed** outcomes = `brevard.realforeclose.com` (RealTaxDeed) closed-sale results.
- PROBLEM: both gated hosts (Acclaim `199.241.8.28`, BECA `199.241.8.45`) return **blanket HTTP 503 to datacenter/CI egress regardless of UA/headers/endpoint**; `www` + `vweb2` are open. TLS completes; the 503 is an edge/WAF policy on those subdomains.
- OPTIONS (Ariel decision): (a) residential-IP / stealth-browser path for Acclaim+RealTaxDeed; (b) Clerk **bulk-records / subscription** channel (Acclaim subscription + BECA registered-user agreement found in Part A); (c) public-records request for a one-time historical outcome export to seed the corpus. (a) is fastest-recurring; (b)/(c) are most defensible.

### Blocker 3 — RealAuction credentials (tax-deed lane). Ariel-only.
- The 4,088-row tax-deed half (larger share of B) needs a registered `brevard.realforeclose.com` login + the `FNC=UPDATE` diff endpoint; anonymous caps ~20. Supply via GH secret. Without it, tax-deed B cannot complete.

## Sequenced plan (do in order)
1. **Re-key (Claude, no blockers):** build `brevard_case_rekey` crosswalk by parcel_id/address for both lanes. This is pure in-DB work and unblocks everything downstream.
2. **Ariel unblocks access:** choose Blocker-2 option + supply Blocker-3 RealAuction creds.
3. **Outcome pull (session, once 1+2 done):** Acclaim Certificate-of-Title for foreclosure; authed RealTaxDeed for tax-deed. Write to `foreclosure_outcomes` / `tax_deed_outcomes` with independent `data_source`, keyed by real case_number, matched via crosswalk.
4. **Verify:** `pct_b ≥ 95` per lane; re-check `v_pencil_brevard_dod`.

## What must NEVER happen
- Do NOT count any PropertyOnion sold amount toward B (HARD FAIL).
- Do NOT write a row without a real recorded result. Missing = unwritten, never guessed.
- Do NOT fight the WAF from datacenter IPs at 576/day — that is the claude-code-direct.yml failure pattern. Solve access first, then pull.

## Honest status
B is not a week-one scrape. It is a provenance rebuild: re-key off PropertyOnion, reach the legitimate clerk sources we are currently IP-blocked from, and pull real outcomes. The corpus was bootstrapped on PropertyOnion for fast coverage — a reasonable start — but the gold standard's verified-source bar means that bootstrap has to be replaced with primary-source outcomes. That replacement IS criterion B.
