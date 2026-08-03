# Privacy and Data Protection Policy

**Effective:** August 3, 2026 · **Owner:** Ariel Shapira
AI-generated PBC draft — for CPA/ISO auditor review, not a finished attestation.
This is not legal advice.

## 1. Data Collected

Email address, Stripe customer ID, and API usage logs (the hashed key only,
never the raw key) — per `mcp_api_keys` and `lead_profiles`.

## 2. Data Not Collected

BidDeed.AI does not capture or store a customer's property-targeting
strategy, bid amounts, or investment decisions as identifiable personal data.
Tool-call inputs/outputs pass through the MCP server but the platform does
not build a customer profile from investment behavior.

## 3. Legal Basis

Contract performance (providing the API/tool access the customer paid for)
and legitimate interest (fraud and abuse prevention via anomaly detection).

## 4. Florida FIPA (FS 501.171)

If a breach affects more than 500 Florida residents, BidDeed.AI notifies the
Florida Department of Legal Affairs and affected individuals within 30 days
of determining the breach occurred — the statutory outer bound. The
Incident Response Plan sets an internal 72-hour customer-notification target,
which is faster than, and not in conflict with, this statutory ceiling.

## 5. CCPA

California residents may request deletion of their personal data by emailing
privacy@biddeed.ai. Requests are processed within 30 days, per
`docs/legal/DATA_RETENTION_POLICY.md`.

## 6. Data Retention

Full detail: `docs/legal/DATA_RETENTION_POLICY.md`. Notable disclosed gap
carried from that document: an automated purge job for usage-metering tables
(`taxi_meter_streams`/`taxi_meter_tools`) has not been independently
confirmed to exist — the policy states this openly rather than claiming a
90-day auto-purge that hasn't been verified.

## 7. No Sale, No Advertising

BidDeed.AI does not sell customer data to third parties and runs no
advertising business built on customer data.

## 8. Enterprise DPA

A Data Processing Agreement is available on request for enterprise
customers. No DPA template has been drafted as of 2026-08-03 — this is
disclosed as available-on-request-and-not-yet-templated, not as a
ready-to-sign document.
