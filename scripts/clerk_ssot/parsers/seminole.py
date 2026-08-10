"""Seminole clerk foreclosure + tax deed parser. UNCOVERABLE — no parser
functions in this module. This is a documented blocker, not an oversight.

Investigated live 2026-08-10 (parser_hint was "unknown" going in — nobody
had looked at this county before this session):

1. The two URLs given as the starting point,
   https://webapps.seminoleclerk.org/ForeclosureSales/ and
   https://webapps.seminoleclerk.org/TaxDeedSales/, are both on
   webapps.seminoleclerk.org (64.187.122.51). That host is entirely
   unreachable from this environment: TCP connect times out on BOTH port
   80 and port 443, confirmed independently via curl, python httpx, wget,
   and a raw `/dev/tcp` connect probe, across multiple retries. This is a
   network-level failure (nothing ever accepts the TCP handshake), not an
   application-layer block/WAF/captcha we could work around with better
   headers — there's no HTTP response to even inspect.

2. Crucially, reachability of that subdomain wouldn't have mattered anyway.
   The main clerk site (https://www.seminoleclerk.org — a different IP,
   64.187.122.56, which IS reachable) has its own "Foreclosures" and
   "Tax Deed Sales" landing pages. Both are WordPress marketing pages, and
   both point their actual "see current sales" call-to-action links at
   gated third-party RealAuction-family platforms, not at any Seminole-
   clerk-hosted calendar:
     - Foreclosures page -> "Click Here For Current Foreclosure Sales"
       -> https://seminole.realforeclose.com/index.cfm  (RealForeclose)
     - Tax Deed Sales page -> https://seminole.realtdm.com/public/cases/list
       (RealTDM)
   Both are explicitly off-limits per this pipeline's guardrails (gated
   RealAuction-family auction platforms requiring authentication/JS this
   pipeline is not allowed to touch).

Conclusion: even setting aside the webapps.seminoleclerk.org network
failure, Seminole's real public foreclosure and tax deed sale calendars
live exclusively on RealForeclose/RealTDM. There is no independent,
clerk-hosted, non-gated calendar for either sale type to parse. This
matches the same blocker pattern as counties whose only calendar is
RealAuction-hosted — a legitimate UNCOVERABLE outcome, not a parsing
failure.

No parse_foreclosure() or parse_tax_deed() is implemented here on purpose.
"""
