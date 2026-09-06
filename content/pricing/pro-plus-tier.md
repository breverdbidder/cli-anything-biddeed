# Pricing page — Pro Plus tier block

For issue #20011 (GTM-CMO). Feeds the `/subscribe` pricing surface (`src/worker.js`
`SUBSCRIBE_HTML`) and any pricing-card component `#20010` builds. Prices are
tokens, never literals — resolve at render time from the live checkout/tier
config (`packages/biddeed-mcp/src/constants.js` `TIER_RANK`, the
`stripe_products` table via `biddeed-checkout`), per CONTENT_SOP hard rule 2
and the brief's "live price token" instruction. Seat count is a plan
attribute, not a live metric, so it ships as a literal.

## Tier label
Pro Plus

## One-line promise (Ariel voice — no buzzwords, no exclamation marks)
The bid gets you the property. Pro Plus runs everything after it — one project, start to exit.

## Price block
- Monthly: `{{pricing.pro_plus.monthly}}`/mo
- Annual: `{{pricing.pro_plus.annual}}`/yr
- Seats: 3 seats included
- Everything in Investor and Pro, plus the Rehab-to-Exit suite below

## What it includes — Rehab-to-Exit suite (feature grid, 6 items)
Mirrors the `s5-overview`/`s5-grid` pattern already used on `/buy-report`
(`BUY_REPORT_HTML` in `src/worker.js`) — short label, one-line description.

1. **Budget & scopes of work** — set the number and the scope before the first receipt.
2. **Schedule** — the timeline that keeps trades and draws in sync.
3. **Ledger** — receipts and budget-vs-actual in one place, not a spreadsheet.
4. **Lender draws** — draw requests tied to the same budget, not re-typed for the bank.
5. **Funding pack** — built straight from the SIGNAL$ Property Report you bid from.
6. **Exit pack** — the sale or lease package when the project is done.

## CTA
Primary: `Start Pro Plus — {{pricing.pro_plus.monthly}}/mo`
Links to `/subscribe?tier=proplus`.
