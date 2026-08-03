# BidDeed.AI Data Retention & Deletion Policy

**Last updated:** August 3, 2026
**Live at:** https://biddeed.ai/data-retention

This is not legal advice. BidDeed.AI is an information and analytics
platform, not a law firm or title company.

## What we retain, and for how long

| Data | Table(s) | Retention | Why |
|---|---|---|---|
| Customer account data (email, Stripe customer ID) | `lead_profiles`, `mcp_api_keys` | While account is active, then 7 years after closure | Florida business records practice |
| API/tool usage metering | `taxi_meter_streams`, `taxi_meter_tools` | Retained per active billing cycle; not subject to a fixed short-window auto-purge as of this review | Billing accuracy, abuse investigation (see Incident Response Plan) |
| Payment records | `stripe_checkout_sessions`, `stripe_webhook_events` | 7 years | IRS recordkeeping requirement |
| Security events | `security_events` | 1 year, then purged | Incident investigation window; avoids indefinite accumulation of access logs |
| Chat history | `claude_chat_history` | 30 days, then purged | Support/debugging window only — chat is not a system of record |
| Florida property/auction data | `multi_county_auctions`, `fl_parcels`, `zoning_assignments` | Indefinite | Sourced from public government records; contains no personal data about our customers |

**Correction note:** we could not independently confirm an automated 90-day
purge job for the usage-metering tables (`taxi_meter_streams` /
`taxi_meter_tools`) in this review — the originally planned claim of a
90-day auto-purge is **not yet verified** and is not stated as fact above.
If and when that purge job is implemented and confirmed, this table will be
updated.

## Right to deletion

You may request deletion of your personal data (email, payment-related
identifiers) by emailing **privacy@biddeed.ai**. We will process deletion
requests within 30 days.

**What we cannot delete:** Florida public-record data (property records,
auction/case data) is sourced from county government systems. We do not
control that data at its source and cannot delete it from our copy without
losing the ability to serve public-record lookups accurately — this data
was never personal to you in the first place; it is the county's own public
filing.

## Florida-specific notice

Under Florida's Information Protection Act (FS 501.171), if a breach affects
more than 500 Florida residents, we will notify the Florida Department of
Legal Affairs and affected individuals within 30 days of determining the
breach occurred, consistent with the Incident Response Plan.

## Contact

Questions about this policy: privacy@biddeed.ai
Security incidents: security@biddeed.ai

---

*This is not legal advice. Consult a licensed Florida attorney for guidance
specific to your situation.*
