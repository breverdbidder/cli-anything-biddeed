# Homepage — Plans section revision

For issue #20011 (GTM-CMO). Targets the "Plans" section on `/`
(`breverdbidder/biddeed-web`, per CONTENT_SOP §5.6 S4 — Worker routes stay
in this repo, `/` lives in biddeed-web). This file is copy only; the actual
page edit is a separate engineering PR in biddeed-web, scoped by whoever
picks that up next. **The canon hero stack is not touched by this file —
do not carry hero copy over when this is implemented.**

Three cards, in this order: Investor, Pro, Pro Plus. Prices are tokens,
resolved live from the checkout/tier config — never literals, per
CONTENT_SOP hard rule 2.

## Card 1 — Investor
**Price:** `{{pricing.investor.monthly}}`/mo
**One-line:** Every FL county auction, one search, before you ever place a bid.

- Live auction calendar across every FL county we cover
- Owner intel, lien stack, and rent estimates before you underwrite
- Statewide property search
- Start a Project — files, notes, and project chat

CTA: `Start Investor` → `/subscribe?tier=investor`

## Card 2 — Pro
**Price:** `{{pricing.pro.monthly}}`/mo
**One-line:** Underwrite the deal, not just the calendar.

- Everything in Investor
- Zoning check, sales comps, and bid package for underwriting
- Auction watch alerts — sale date, postponement, cancellation
- Max Bid — the ceiling number for a certified county, calculated

CTA: `Start Pro` → `/subscribe?tier=pro`

## Card 3 — Pro Plus
**Price:** `{{pricing.pro_plus.monthly}}`/mo · 3 seats
**One-line:** The bid gets you the property. Pro Plus runs everything after it.

- Everything in Pro
- Run the project: budget, scopes of work, schedule
- Ledger with receipts, budget-vs-actual, and lender draws
- Funding pack and exit pack, built from your SIGNAL$ Property Report

CTA: `Start Pro Plus` → `/subscribe?tier=proplus`
