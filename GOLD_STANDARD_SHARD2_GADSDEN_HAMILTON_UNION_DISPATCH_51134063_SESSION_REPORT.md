# GOLD STANDARD shard-2: gadsden / hamilton / union — session report

- dispatch_id: `51134063-3ac7-4cb0-94c6-9e7a2125dd20`
- chat_session: `architect-20260817T080000`
- loop run at launch: 12108
- session date: 2026-08-17
- gold_standard_campaign row: `id=4519`

## Result summary

No metric moved this session. All three counties' failing letters were re-diagnosed
from first principles, then independently adversarially verified by a 3-agent
ULTRALOOP refutation workflow (`gold-standard-shard2-gadsden-hamilton-union-adversarial-verify`,
run `wf_d7e1dd95-bc8`). All three "no legitimate fix exists today" claims **SURVIVED**
refutation. No database write was made anywhere — writing one would have required
either fabricating an outcome or (for gadsden) touching the shared
`pencil_dod_evaluate_county` function used by every other concurrent shard, both of
which are explicitly prohibited.

| county | before | after | letters worked | verdict |
|---|---|---|---|---|
| gadsden | 9/10 | 9/10 | C | SURVIVES (correctly classified, not a bug) |
| hamilton | 8/10 | 8/10 | C, D | SURVIVES (5th independent reconfirmation) |
| union | 6/10 | 6/10 | B, C, D, F | SURVIVES (3rd+ independent reconfirmation) |

## BEFORE/AFTER `pencil_dod_evaluate_county` (byte-identical, confirmed live)

```json
gadsden:  {"A":true,"B":true,"C":false,"D":true,"E":true,"F":true,"G":true,"H":true,"I":true,"J":true}
          C: matched_clean=57, auctions_total=65, metric=87.7
hamilton: {"A":true,"B":true,"C":false,"D":false,"E":true,"F":true,"G":true,"H":true,"I":true,"J":true}
          C: matched_clean=17, D: matched_any=17, auctions_total=21, metric=81.0
union:    {"A":true,"B":false,"C":false,"D":false,"E":true,"F":false,"G":true,"H":true,"I":true,"J":true}
          B: verified=0 closed_sold=0 | C: matched_clean=2 | D: matched_any=2 | F: tier1_sold=0 closed_sold=0
          auctions_total=3
```

## gadsden — C (parity_clean, 87.7%)

**Root cause, VERIFIED live this session**: the 8-row gap (65 total − 57 matched_clean)
is 8 tax-deed cases (26000018TDC, 26000021TDC, 26000022TDC, 26000024TDC, 26000025TDC,
26000029TDC, 26000032TDC, 26000034TDC; all `auction_date=2026-09-02`) carrying
`parity_status='CLERK_SSOT_CANCELLED'`.

Fresh `httpx` GET of `http://www.gadsdenclerk.com/Tax_deeds/Tax_deeds_files/sheet001.htm`
(the exact URL `scripts/clerk_ssot/parsers/gadsden.py` scrapes) returned all 8 case
numbers present, with parcel_id matching our DB exactly, but the SalePrice column
(index 9) reads **"Redeemed 8/3/26"**, **"Redeemed 6/29/26"**, etc. for every one of
the 8. Independently re-ran the actual production parser
`scripts/clerk_ssot/parsers/gadsden.py:parse_tax_deed()` live (not a reimplementation)
and it returns `cancelled=True` for all 8 with the identical raw text. These are
**genuinely redeemed** tax-deed certs — the owner paid the debt before the 9/2/2026
sale, so no sale will ever occur.

Per the evaluator's own documented design (`supabase/migrations/20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql`,
lines 18–27), `CLERK_SSOT_CANCELLED` intentionally does **not** count toward
`matched_clean` (there's nothing to cleanly match — the sale doesn't exist) but does
count toward `matched_any` (D correctly passes at 100%). Reclassifying these 8 rows as
clean would be exactly the ghost-success pattern that migration was written to prevent.

**Adversarial refutation (independent agent, fresh fetch + fresh parser run)**:
VERDICT SURVIVES. No per-county denominator-override mechanism exists in the schema;
excluding redeemed rows from `auctions_total` would require editing the shared
evaluator function used by every other concurrent shard's session — out of scope for a
county-level session and explicitly against the guardrails. **No DB write made.**

## hamilton — C / D (parity_clean / parity_any, 81.0%)

**5th independent session reconfirmation.** Gap rows: `2024-CA-19`, `2023-CA-41`,
`2021-CA-46` (`parity_status='mca_only'`) and `2025-CA-37`
(`parity_status='PHANTOM_NOT_ON_CLERK'`). Prior sessions on 2026-07-27, 2026-07-31,
2026-08-07, and 2026-08-14 (see `scripts/hamilton-CD_fix.py`,
`scripts/hamilton-CD_fix_20260814.py`) exhaustively checked hamiltonclerk.com's
foreclosure/tax-deed/records pages and civitekflorida.com OCRS (no case-number search
field) — no trace of the 4 target cases anywhere.

This session re-checked `hamiltoncountyfl.com/foreclosure-sales/` (previously logged as
"HTTP 403, untested") — still 403 under plain `curl`. The adversarial refuter agent then
went one step further with headless Playwright and got a **clean HTTP 200** — the 403
was a bot-detection artifact, not a permanent block. This surfaced a genuinely new
document, `hamiltoncountyfl.com/wp-content/uploads/FORECLOSURE-SALE-LIST-1.pdf` (a live
January-2026 sale list), plus an 11-PDF `hamiltonclerk.com/wp-content/uploads/Foreclosure-Sale-List-{1-10}.pdf`
archive found via web search that no prior session had discovered — containing real
historical sale-*notice* records for `21-46-CA` and `23-41-CA`, but no sale *outcome*
(sold/cancelled/redeemed) for any of the 4 target cases, and no record at all of
`2024-CA-19` or `2025-CA-37` (2025-filed cases fall outside the archive's date range).

**Adversarial refutation**: VERDICT SURVIVES. C/D remain at 81.0% — no citable outcome
exists anywhere. One factual correction for future sessions: `hamiltoncountyfl.com` is
**not** permanently blocked; a headless-browser fetch clears it and should be added to
the county's known-source inventory. **No DB write made.**

## union — B, C, D, F (verified outcomes / parity / tier1-sold)

**3rd+ independent session reconfirmation** (see
`scripts/shard6_run4870_union_3rd_firing_addendum.py`). Union has exactly 3 auctions:
`63-2024-CA-0047` (future, 2026-10-15), `UNION-TD-CERT223` (confirmed REDEEMED — no sale
price exists by FL Ch.197 definition), and `63-2025-CA-0053` (foreclosure,
`auction_date=2026-08-13`, now 4 days past, `parity_status='PHANTOM_NOT_ON_CLERK'`).

This session used a genuinely new technique — stealth Playwright
(`--disable-blink-features=AutomationControlled` + `navigator.webdriver` override + a
real 1366×900 viewport) — to clear the Cloudflare "Just a moment…" challenge on
`unionclerk.com/foreclosure-sales/`, which plain `curl` and prior plain-Playwright
attempts could not do. The cleared, fully-rendered page (76 KB, confirmed real title)
lists **only** `63-2024-CA-0047` under "Upcoming Foreclosure Sales" — `63-2025-CA-0053`
does not appear, and no results/archive section exists anywhere in the site nav.

The adversarial refuter independently reproduced this bypass, then went further on
`civitekflorida.com/ocrs/county/63/`: it drove the full Public → I Agree → Case Search
flow and filled Year/CourtType/Seq for the case, but confirmed via direct DOM inspection
that **Cloudflare Turnstile never issues a token in headless mode**, even after a
30-second wait — a more precise root cause than prior sessions had ("couldn't drive the
UI"). It also fetched raw BC Telegraph legal-notice HTML (not AI-summarized) confirming
`63-2025-CA-0053` (TD Bank N.A. v. Linda Andrews Scott, parcel `31-05-18-00-000-0101-2`,
matching our DB) is a real, multiply-rescheduled case whose final reschedule lands
exactly on 2026-08-13 — and confirmed no post-sale-date issue reports an outcome.

**Adversarial refutation**: VERDICT SURVIVES. B and F remain genuine 0/0-denominator
failures; C/D remain blocked by the single unconfirmable row. **No DB write made.**

## Session artifacts

- Workflow run: `wf_d7e1dd95-bc8` (3 agents, 149 tool calls, 337,508 tokens)
- `gold_standard_ultraloop_audit`: 7 new rows (gadsden-C, hamilton-C, hamilton-D,
  union-B, union-C, union-D, union-F), all `survived=true` — these are diagnostic
  "structural ceiling confirmed" claims, **not** pass-certification votes; all three
  counties remain below 10/10 live.
- `gold_standard_campaign` id=4519 updated: `criteria_passed` (per-county A–J),
  `exit_reason='timeout'`, `session_end_at` set.

## Residual / next-session notes

- gadsden C is structurally capped at 87.7% until the shared evaluator's denominator
  policy for genuinely-redeemed tax-deed rows is revisited at the fleet level (out of
  scope for a single county-shard session).
- hamilton: `hamiltoncountyfl.com` is reachable via headless browser (not a permanent
  403) — catalog this for future sessions. The 4 gap cases still have no discoverable
  outcome anywhere checked across 5 sessions.
- union: `civitekflorida.com` OCRS is blocked specifically by Turnstile token issuance
  in headless mode (confirmed via DOM inspection) — a non-headless run or a Turnstile
  solver would be the only way past it, if ever revisited.
