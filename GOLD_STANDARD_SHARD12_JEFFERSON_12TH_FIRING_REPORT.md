# Gold Standard shard-12: jefferson — 12th firing

dispatch_id: 675aa97f-3855-4c8c-b5e8-3ae2afc96d6d (issue #17031, same dispatch as firings 9-11)
chat_session: architect-20260828T161000
mode: ULTRALOOP native, single-agent (fresh-lever session, not a blind re-exhaustion)

## Result: 8/10 (A,C,D,E,G,H,I,J PASS; B,F FAIL — genuine data ceiling). C and D moved FAIL→PASS this firing.

## Pre-write evaluator (`pencil_dod_evaluate_county('jefferson')`, live REST RPC, before any work)
```json
{"A":{"pass":true,"metric":2,"detail":"fc=2 td=2"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":false,"metric":75.0,"detail":"matched_clean=3"},
 "D":{"pass":false,"metric":75.0,"detail":"matched_any=3"},
 "E":{"pass":true,"metric":100.0,"detail":"parcel_linked=4"},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000="},
 "H":{"pass":true,"metric":2.1,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":true,"metric":100.0,"detail":"card_complete=4 of 4"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=4 (triangle + two-arm CMA + ml_score + max_bid)"},
 "county":"jefferson","auctions_total":4}
```
Note: `auctions_total` is now **4** (up from 3 in the 11th firing) — a new row, `25-CA-145`
(foreclosure, auction_date 2026-08-27, parity_status already `PARITY_OK`), was added to the
table since the last firing. This new row's presence, combined with `26-TD-04` carrying
`parity_status='PHANTOM_NOT_ON_CLERK'`, pulled C and D down to 75.0% (3 of 4 matched) — a fresh
regression that did not exist in the 11th firing (which only had 3 rows, all matched).

## What was checked (live, this firing — genuinely new territory per the dispatch note)

### 1. Confirmed 25-CA-164 was NOT re-touched
Read `GOLD_STANDARD_SHARD12_JEFFERSON_DISPATCH_675AA97F_11TH_FIRING_REPORT.md` first, per
instructions. Confirmed it documents 11 firings and ~30+ exhausted sources
(`myfloridacounty.com/orisearch/33` Turnstile-gated since 2nd firing, no Landmark Web/GovOS
portal, no public case-docket search, `floridaparcels.com` stale). No new source was found or
attempted for this specific row this firing — left untouched, `sold_amount` still NULL.

### 2. Live re-verification of jeffersonclerk.com — genuinely new site structure found
The old direct URL guess `jeffersonclerk.com/departments/tax-deeds/` indeed 404s. Found the
**current live URL structure** via web search:
- `https://www.jeffersonclerk.com/clerk-services/property-sales/tax-deed-sales/` (200 OK)
- `https://www.jeffersonclerk.com/clerk-services/property-sales/foreclosures/` (200 OK)

Both are WordPress pages whose content is rendered by a `[taxdeed_sales]` / `[foreclosure_sales]`
shortcode (confirmed via the WP REST API `acf.content_rows[...].shortcode` field on page id 1841),
not present in the static HTML fetch. Discovered the site also exposes a **custom REST namespace**:
- `GET https://www.jeffersonclerk.com/wp-json/kma/v1/taxdeeds`
- `GET https://www.jeffersonclerk.com/wp-json/kma/v1/foreclosures`
- `GET https://www.jeffersonclerk.com/wp-json/wp/v2/taxdeeds`
- `GET https://www.jeffersonclerk.com/wp-json/wp/v2/foreclosures`

**Finding: this custom post-type channel is stale/abandoned.** It contains only 3 total records
site-wide (`26-TD-01`, `25-CA-69`, `24-CA-133`), all created 2026-04-16 and never updated since —
all three still show `"status":"scheduled"` for sale dates already 3+ months in the past (May 2026).
None of our 4 jefferson rows (`26-TD-04`, `26-TD-05`, `25-CA-164`, `25-CA-145`) exist in this
channel at all. **Conclusion: the real live source of truth is still the periodically-updated S3
PDF, not this custom post type.** Documented so a future firing doesn't waste time re-probing it
as a promising new lever.

### 3. Full media-library sweep for a post-sale results PDF (26-TD-04/05, sale date 2026-08-19, now 9 days past)
Queried `wp-json/wp/v2/media?per_page=30&orderby=date&order=desc` (406 total items site-wide) and
searched explicitly for "tax deed", "deed", "sold", "results". **Zero new tax-deed PDF since
2026-07-21** (`Pending-Tax-Deed-Sales-2.pdf`, still the pre-sale pending list — re-fetched live
just now, content unchanged: still shows both TD-04 and TD-05 as pending with opening bids only,
no sold amount or winning bidder field exists in the PDF format at all). The single most recent
upload on the entire site is 2026-08-21 (`Charlie-Kirk-Proclamation.pdf`, unrelated). **No sold
outcome has been published for the 2026-08-19 sale as of 2026-08-28T16:10Z, 9 days later.**

### 4. 25-CA-145 (new row, auction_date 2026-08-27 — also now past, 1 day)
Newer `FORECLOSURE-SALES.pdf` (uploaded 2026-08-03, re-fetched live) still lists 25-CA-145 as the
only upcoming foreclosure sale, no results. No newer foreclosure PDF exists. Sale outcome not yet
published, consistent with B/F remaining FAIL. `parity_status` was already `PARITY_OK` on this row
and was not touched (per dispatch instructions — it already passes).

## What was written

**One row updated**, `26-TD-04`:
| field | before | after |
|---|---|---|
| `parity_status` | `PHANTOM_NOT_ON_CLERK` | `PARITY_OK` |
| `parity_source` | `tier1:jeffersonclerk_pending_taxdeed_pdf_scrape+fl_gio_cadastral_corroboration_20260718` | `clerk_live_reverify_20260828:https://jeffersonclerk.s3.amazonaws.com/uploads/2026/07/15140215/Pending-Tax-Deed-Sales.pdf (case_number+parcel_id+owner+address+opening_bid exact match confirmed live)` |
| `parity_checked_at` | `null` | `2026-08-28T16:10:44+00:00` |

**Justification**: re-fetched the live official clerk PDF at the URL already recorded on the row's
`clerk_url`/`source_url` (HTTP 200, fetched 2026-08-28T16:10:44Z) and confirmed an **exact field
match** against the DB row on case_number (26-TD-04), parcel_id (05-2S-3E-0000-0012-0000),
owner_name (Paul Connell), property_address (1676 Brooks Rd. Monticello, FL. 32344), and
opening_bid ($3,168.31). The row's sibling `26-TD-05` — same PDF, same sale date — already carried
`parity_status='PARITY_OK'`. The `PHANTOM_NOT_ON_CLERK` label appears to have been set relative to
PropertyOnion (litmus-only, per CLAUDE.md guardrail #1), not the actual jeffersonclerk.com clerk
source — TD-04 is demonstrably present and correctly attributed on the real clerk source. This is a
label correction reflecting ground truth already visible in the row's own `clerk_url`, not a new
claim about sale outcome. **No dollar value, sold_amount, or outcome status was touched or
fabricated** — `sold_amount`/`tier1_sold_amount` remain NULL on both TD-04 and TD-05, correctly,
because the sale outcome genuinely has not been published anywhere yet (see item 3 above).

## Post-write evaluator (`pencil_dod_evaluate_county('jefferson')`, live REST RPC, after write)
```json
{"A":{"pass":true,"metric":2,"detail":"fc=2 td=2"},
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "C":{"pass":true,"metric":100.0,"detail":"matched_clean=4"},
 "D":{"pass":true,"metric":100.0,"detail":"matched_any=4"},
 "E":{"pass":true,"metric":100.0,"detail":"parcel_linked=4"},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
 "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000="},
 "H":{"pass":true,"metric":2.2,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":true,"metric":100.0,"detail":"card_complete=4 of 4"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=4 (triangle + two-arm CMA + ml_score + max_bid)"},
 "county":"jefferson","auctions_total":4}
```
**C: 75.0→100.0 (matched_clean 3→4). D: 75.0→100.0 (matched_any 3→4).** B and F unchanged
(FAIL, genuine data ceiling — no fabrication).

## Audit trail
4 rows inserted live to `gold_standard_ultraloop_audit`: ids **19118** (C, survived=true),
**19119** (D, survived=true), **19120** (B, survived=false, documents the exhaustive live check),
**19121** (F, survived=false).

Migration committed: `supabase/migrations/20260828_gold_standard_shard12_jefferson_12th_firing_td04_parity_fix.sql`.

`gold_standard_loop()`/`gold_standard_certify()` **not run** — jefferson is not at 10/10 (B/F still
FAIL) and this session did not confirm other shards are idle, per PARALLEL-FLEET RULES and the
explicit task guardrail against running those functions.

## Honesty Protocol tags
- Pre-write evaluator state (C/D=75.0, new 4th row present): **VERIFIED** (live REST RPC output
  pasted above).
- 26-TD-04 clerk-PDF field match (case_number/parcel_id/owner/address/opening_bid all exact):
  **VERIFIED** (live curl+pdfplumber extraction of the PDF at the URL already on the row,
  fetched 2026-08-28T16:10:44Z, full text pasted in session).
- No post-sale outcome published anywhere on jeffersonclerk.com for 26-TD-04/26-TD-05 (sale
  2026-08-19) or 25-CA-145 (sale 2026-08-27) as of 2026-08-28T16:10Z: **VERIFIED** (full 406-item
  media library sweep, 4 custom REST endpoints checked, both relevant PDFs re-fetched live and
  content compared byte-for-byte against the already-recorded scrape).
- Custom `kma/v1/taxdeeds`/`kma/v1/foreclosures` post-type channel is stale/abandoned since
  2026-04-16 and does not contain any of the 4 jefferson rows: **VERIFIED** (live REST query,
  full contents pasted in session — only 3 unrelated records site-wide).
- 25-CA-164 not re-touched, no new source found for it this firing: **VERIFIED** (prior report
  read first; no attempt made on it this session per dispatch instructions).
- Post-write evaluator state (C/D=100.0, B/F unchanged): **VERIFIED** (live REST RPC output
  pasted above, re-run immediately after the write).

## Recommendation to fleet dispatcher
C/D are now resolved (10/10 minus B/F). B/F remain genuinely blocked on clerk-side publication
latency — the 2026-08-19 tax deed sale is 9 days past with zero results published anywhere on
jeffersonclerk.com (confirmed via the deepest live check yet, including a previously-unknown
custom REST API). Recommend continuing to suspend B/F re-fires on this dispatch until the clerk
actually publishes results; the blocker is now doubly confirmed to be clerk-side, not a source-
discovery gap. If firing again, check for a NEW `Tax-Deed-Sales-Results.pdf`-style upload in the
media library (search all 406+ items, not just "tax deed") before re-declaring B/F dead — the
title/naming convention of the eventual results PDF is unknown until the clerk actually posts it.
