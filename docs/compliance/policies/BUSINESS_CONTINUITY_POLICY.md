# Business Continuity Policy

**Effective:** August 3, 2026 · **Owner:** Ariel Shapira
AI-generated PBC draft — for CPA/ISO auditor review, not a finished attestation.

## 1. Objectives

- **RTO (Recovery Time Objective):** 4 hours.
- **RPO (Recovery Point Objective):** 1 hour, via Supabase point-in-time
  recovery.

## 2. Single Points of Failure

BidDeed.AI owns no physical or self-managed infrastructure. The three
platform dependencies (Vercel, Supabase, Cloudflare) each publish a 99.9%
SLA. The one true single point of failure the company does own is the
founder himself — see Risk Register R013 (solo-founder incapacitation),
mitigated by fully autonomous pg_cron-driven operations that require no
human intervention for routine function (110 active scheduled jobs
confirmed live in `cron.job`, 2026-08-03).

## 3. Backup

- Supabase daily automated backups plus continuous point-in-time recovery.
- Application code and configuration: GitHub is the system of record; a full
  rebuild of any deploy target starts from a `git clone`.

## 4. Disaster Scenarios

| Scenario | Impact | Recovery |
|---|---|---|
| Vercel outage | MCP tool calls unavailable; customer data untouched (lives in Supabase) | Redeploy to an alternate host or wait out Vercel's own SLA-backed recovery; typically <15 min |
| Cloudflare Worker outage | `biddeed.ai` marketing/chat surface down | Redeploy via `deploy-worker.yml`; Cloudflare's own edge network provides redundancy |
| Supabase outage | Full platform down (data layer) | Wait on Supabase's 99.9% SLA; PITR available for point-in-time restore if data corruption (not just unavailability) is the cause |
| Founder unavailable (illness, travel) | No human dispatch for new SUMMIT work | Automated loops (gold-standard-autopilot, everest-dispatcher-v7, security-alert-sweep, etc.) continue unattended; no customer-facing feature depends on same-day human action |

## 5. DR Testing

Quarterly tabletop review by Ariel: walk through each disaster scenario above
against the current architecture and confirm the stated recovery path is
still accurate. No live failover drill has been run to date — this is
disclosed as a tabletop-only practice, not a tested cutover.
