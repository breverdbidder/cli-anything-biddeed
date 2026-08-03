# SafeBase Trust Portal — Setup Guide (Ariel, manual, ~30 min)

**Status as of this document's creation (2026-08-03): NOT YET DONE.** No
SafeBase account exists for BidDeed.AI. Claude Code cannot create it — the
signup flow requires a browser session and human identity verification.
Everything in this document is instructions for Ariel to execute manually.
Nothing here has been executed automatically.

## Why SafeBase (not Conveyor/Hypercomply)

Per `CLAUDE.md`'s NEVER-purchase-paid-questionnaire-tool non-goal for this
task: SafeBase offers a free tier trust portal (hosted document
distribution with gated/request-access control). This document only covers
that free tier — do not upgrade to a paid plan without a separate,
explicit decision.

## Step-by-step

1. Go to `safebase.io` → **Sign up free**.
   - Use `security@biddeed.ai` (not a personal address) as the account
     email — this keeps the account owned by the company identity, not
     Ariel's personal inbox, matching every other vendor account pattern
     documented in `VENDOR_SUB_PROCESSOR_LIST.md`.
2. Company profile:
   - Name: `BidDeed.AI / Everest Capital USA`
   - Website: `https://biddeed.ai`
   - Industry: Real estate technology / PropTech, AI-native SaaS
3. Upload documents (all committed to `docs/security/` and `docs/legal/`
   as of this session — verify each exists before uploading, `git log
   --oneline -- docs/security docs/legal` should show today's commit):

   | Upload as | Source file |
   |---|---|
   | "Security Overview" | `docs/security/SECURITY_EVIDENCE_PACK.md` |
   | "CAIQ Self-Assessment" | `docs/security/CAIQ-v4.1-BidDeed-Completed.md` |
   | "AI Security Assessment" | `docs/security/AI-CAIQ-v1.1-BidDeed-Completed.md` |
   | "Sub-Processor List" | `docs/security/VENDOR_SUB_PROCESSOR_LIST.md` |
   | "Data Retention Policy" | link to `https://biddeed.ai/data-retention` (live page, don't re-upload as a static file — it can drift from the source of truth) |
   | "External Scan Results" | `docs/security/EXTERNAL_SCAN_SUMMARY.md` |

   **Do not upload a "Penetration Test Report."** No OWASP ZAP or other DAST
   scan has been run against production as of this session — see the
   corrections sections in the CAIQ/AI-CAIQ documents. Uploading a
   nonexistent report, or a placeholder titled as if one exists, would be a
   false claim on a document enterprise buyers rely on directly. Add that
   upload only after a real scan has actually been run and a report exists.

4. Trust center URL: request `trust.biddeed.ai` as the custom domain in
   SafeBase's settings. SafeBase will generate a CNAME target after this
   step — **that target does not exist until you complete this step**, so
   the Cloudflare DNS record in the next section cannot be created until
   you have it in hand.
5. Access setting: **"Request access"** (visitor requests, Ariel approves)
   — gated but frictionless, matches the brief's intent and avoids fully
   open public distribution of a document that includes named security
   gaps (network-restriction status, unrotated-secret counts, etc.) that
   are appropriate for a vetted enterprise counterparty but not for
   anonymous public indexing.
6. Once the portal is live, come back to this repo and:
   - Update `src/worker.js`'s `SECURITY_HTML` enterprise-trust-portal
     section (added this session, currently marked "coming soon") to link
     directly to `https://trust.biddeed.ai`.
   - Update `BIDDEED_SSOT.md`'s trust portal reference with the live URL
     and the date it went live.

## Cloudflare DNS (do this AFTER step 4 above, not before)

Once SafeBase shows you its CNAME target value:

```
Type: CNAME
Name: trust
Target: [SafeBase-provided CNAME — only appears after step 4]
Proxy: DNS only (grey cloud)
```

**Why "DNS only" (grey cloud) and not proxied (orange cloud):** SafeBase
needs to terminate TLS and serve its own content directly for this
hostname; routing it through Cloudflare's proxy first can break SafeBase's
own certificate provisioning for the custom domain. If SafeBase's own docs
say otherwise at setup time, follow SafeBase's current instructions over
this note — their platform may have changed since this guide was written.

This DNS step requires Cloudflare dashboard access and was not executed by
Claude Code in this session — both because the CNAME target doesn't exist
yet (blocked on step 4, which requires a browser) and because DNS changes
to production-serving domains are exactly the kind of hard-to-reverse,
externally-visible change that should go through explicit confirmation,
not an automated documentation session.

## After it's live: add to /security page

This session already added a "coming soon"-style Enterprise Trust Portal
section to the public `/security` page (see `src/worker.js`). Once
`trust.biddeed.ai` actually resolves and the portal is populated, edit that
section to turn the placeholder text into a live link — do not flip that
link live before the portal itself is live, or the public site will 404
for enterprise prospects, which is worse than not having the section at
all.

## Verification checklist (run these, don't assume)

- [ ] `dig trust.biddeed.ai CNAME` resolves to SafeBase's target
- [ ] `curl -I https://trust.biddeed.ai` returns `200` (not `404`/`522`)
- [ ] Requesting access as a test (non-Ariel) email actually reaches
      Ariel's approval queue
- [ ] Every uploaded document opens and matches the current committed
      version in `docs/security/`/`docs/legal/` (not a stale upload)

*This is not legal advice.*
