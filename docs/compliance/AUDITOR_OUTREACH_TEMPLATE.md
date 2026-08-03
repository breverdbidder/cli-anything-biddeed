# Auditor Outreach Email Template

This is a draft email for Ariel to review, personalize, and send — not an
auto-sent artifact. It intentionally does not claim any certification is
complete, and it discloses the one open scan gap up front rather than let an
auditor discover it mid-engagement.

---

```
Subject: SOC 2 Type I + ISO 27001 — Reduced-Scope Engagement, Pre-Built PBC Package Ready

Hi [Name],

I am the solo founder of BidDeed.AI (biddeed.ai), a Florida-based AI platform
providing foreclosure and tax deed auction intelligence for FL real estate
investors. We operate under Everest Capital USA, Satellite Beach FL.

I am seeking a fixed-fee engagement for SOC 2 Type I attestation and/or ISO
27001 certification. I have pre-built a complete PBC (Prepared By Client)
package to reduce your team's setup time:

Policies: 9 written security policies (information security, access control,
change management, vendor management, vulnerability management, business
continuity, acceptable use, privacy, security awareness)

Risk Register: 23 risks formally assessed with likelihood/impact scoring,
mapped controls, and residual-risk status — including 5 items I've marked
"treatment planned" rather than closed, so you're not discovering open items
cold.

Internal Mock Audit: A self-assessment against SOC 2 CC criteria and ISO
27001 Annex A domains, run against live system queries rather than
assumptions — result was 27 of 34 control tests passing, with the gaps
documented rather than smoothed over.

Security Questionnaires: Completed CAIQ v4.1 (207 controls) and AI-CAIQ v1.1
(CSA AI security framework).

Evidence Pack: Full PBC index with vendor SOC 2 certifications (Supabase,
Vercel, Cloudflare, Stripe, GitHub), live system evidence, and external scan
reports (Mozilla HTTP Observatory, SSL Labs).

One gap I want to flag before you scope this: I have not yet run an external
DAST scan (OWASP ZAP or equivalent) against production. That's a deliberate
sequencing choice — I wanted a human decision point before pointing an
active scanner at live customer-facing infrastructure — but it means your
engagement should account for either running that scan yourselves or waiting
on me to complete it first. I'd rather you hear that from me now than find
it in week one.

Technology stack: Vercel + Supabase + Cloudflare + GitHub — all SOC 2 Type II
certified per their own published trust pages. Zero employees — no insider
threat surface, though also no segregation-of-duties control, which I know
you'll want to discuss.

I'd like your team to: review the pre-built documentation, test a sample of
controls against live system evidence in a walkthrough session, and advise
on what (if anything) needs to close before you can issue the SOC 2 Type I
attestation report or ISO 27001 certificate.

Given the disclosed gaps above, I'm estimating this at 3-4 auditor days
rather than a full 8-12 day unprepared-organization engagement — happy to be
corrected once you've seen the package.

Please quote a fixed fee for this scope. I'm also open to a combined SOC 2
Type I + ISO 27001 engagement if that reduces total cost.

Available for a 30-minute scoping call at your convenience.

Ariel Shapira
Founder, BidDeed.AI / Everest Capital USA
Satellite Beach, FL
ariel@biddeed.ai | biddeed.ai
```

---

**Note on the patent reference:** the original planning brief for this
package suggested including "Provisional Patent: [14-claim patent number]"
in the signature block. That placeholder is intentionally omitted above —
insert the actual application number yourself before sending; do not send
with a bracketed placeholder.
