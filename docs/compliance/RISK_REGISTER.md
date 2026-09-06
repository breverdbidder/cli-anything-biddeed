# BidDeed.AI — Risk Register

**Effective:** August 3, 2026 · **Owner:** Ariel Shapira
AI-generated PBC draft — for CPA/ISO auditor review, not a finished attestation.

Scoring: Likelihood (1-5) × Impact (1-5) = Risk Score. Residual risk reflects
the score *after* the listed controls. Every risk below with a live-verifiable
control was checked against production during this review (2026-08-03); where
a claimed control could not be verified, that is stated explicitly rather than
assumed.

| Risk ID | Risk Description | Likelihood | Impact | Score | Controls in Place | Residual Risk | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| R001 | Unauthorized access to customer PII via Supabase breach or RLS gap | 2 | 5 | 10 | RLS enabled on 727/732 public tables (verified live, 2026-08-03); AES-256 at rest; no anon access on sensitive tables | LOW–MEDIUM | Ariel | ACCEPTED — 5 tables (`llm_router_logs`, `model_artifacts`, `auction_buyer_profiles`, `auction_buyer_sightings`, `spatial_ref_sys`) have RLS disabled; `spatial_ref_sys` is a PostGIS reference table (accepted exception), the other 4 need an explicit RLS decision — TREATMENT PLANNED |
| R002 | API key exfiltration enabling unauthorized MCP access | 2 | 4 | 8 | Keys hashed (SHA-256, verified 64-char hashes on sample rows); `is_active` kill switch; anomaly detection | LOW | Ariel | ACCEPTED |
| R003 | Prompt injection via scraped court documents or chat input | 3 | 4 | 12 | Pattern-based guardrail scanning at single `handleToolCall` chokepoint (`guardrails.js`), 60/60 tests passing as of commit `31a71992` | LOW–MEDIUM | Ariel | ACCEPTED — native JS scanning, not LlamaFirewall/LLM Guard as originally specified (Python runtime not in this deploy path); deviation is documented in `SECURITY_EVIDENCE_PACK.md` §5, not hidden |
| R004 | Data breach notification failure (FL FIPA violation) | 1 | 5 | 5 | IRP with 72h internal notification target; statutory 30-day outer bound (FS 501.171); `security-alert-sweep` cron (jobid 10937, `*/15 * * * *`, confirmed active) | LOW | Ariel | ACCEPTED |
| R005 | Vercel platform outage (MCP unavailable) | 2 | 3 | 6 | 99.9% SLA; instant rollback; `llm-health-5min` (jobid 10935, `*/5 * * * *`, confirmed active) | LOW | Ariel | ACCEPTED |
| R006 | Supabase platform breach (vendor-owned surface, zero-day) | 1 | 5 | 5 | RLS, AES-256, 90-day secret rotation *schedule* (see R008 for execution gap) | MEDIUM | Ariel | ACCEPTED — vendor-owned surface, outside BidDeed's direct control |
| R007 | Cloudflare WAF bypass / DDoS attack | 2 | 3 | 6 | Rate limiting (30/min chat, 60/min MCP), security headers deployed 2026-08-03 (Mozilla Observatory F→C+) | LOW | Ariel | ACCEPTED |
| R008 | Vault secret rotation registry tracks schedule but not execution | 3 | 4 | 12 | `secret_rotation_registry` tracks 37 secrets with defined intervals; weekly Telegram reminder (`secret-rotation-check`, jobid 10939, `0 9 * * 1`, confirmed active) | MEDIUM | Ariel | TREATMENT PLANNED — verified live 2026-08-03: 35 of 37 registered secrets have `last_rotated_at IS NULL`; the registry and reminder exist, but actual rotation has only executed twice since the table was created |
| R009 | XGBoost/scoring model producing inaccurate auction predictions (financial harm) | 3 | 4 | 12 | SIGNAL$ Max Bid ceiling, UPL disclaimer on every report | MEDIUM | Ariel | ACCEPTED — disclosed via disclaimer, not a solved-model claim |
| R010 | Competitor/attacker reverse-engineering the Shapira Formula via API responses | 2 | 5 | 10 | S5 `cert_required` gate, tier gating, `mcp-anomaly-detect-30min` (jobid 10973, confirmed active) | LOW | Ariel | ACCEPTED |
| R011 | Bulk county sweep / data exfiltration via a valid API key | 2 | 4 | 8 | Anomaly detection cron (jobid 10973), key suspension playbook (P1-A) | LOW | Ariel | ACCEPTED |
| R012 | LLM hallucination in a customer-facing report causing investor financial loss | 3 | 4 | 12 | UPL disclaimer, "decision-support not an appraisal" language | MEDIUM | Ariel | ACCEPTED — disclosed, not solved |
| R013 | Solo-founder incapacitation (illness, unavailability) | 2 | 5 | 10 | 110 active pg_cron jobs (confirmed live) run the platform without human intervention for routine operation | MEDIUM | Ariel | ACCEPTED — accepted structural risk of a solo-founder company |
| R014 | Social engineering / phishing attack on the founder | 3 | 5 | 15 | SIM lock, canonical-URL bookmarking, dedicated security email | MEDIUM–HIGH | Ariel | TREATMENT PLANNED — YubiKey hardware key not yet purchased as of 2026-08-03; highest-scoring risk in this register precisely because the strongest planned control isn't deployed yet |
| R015 | GitHub repository compromise | 1 | 5 | 5 | Private repo, CC runner uses Max OAuth (not a long-lived PAT), MFA on GitHub | LOW | Ariel | ACCEPTED |
| R016 | Stripe webhook failure (revenue not activated after payment) | 2 | 4 | 8 | Idempotency on `processed=true`, 500 returned to force Stripe retry, `agent_ops_log` monitoring | LOW | Ariel | ACCEPTED |
| R017 | County data contamination (e.g. mislabeled sale_type/co_no cross-county rows) | 2 | 3 | 6 | Per-county gold-standard verification loops (`gold-standard-autopilot`, jobid 161, confirmed active); co_no resolution thresholds documented in ZoneWise pipeline | LOW | Ariel | ACCEPTED |
| R018 | Unverified/stale data served to customers before parity checks complete | 3 | 3 | 9 | `parity_status` documented as a known gap; gold-standard calendar-parity cron (jobid 204, `*/5 * * * *`, confirmed active) | MEDIUM | Ariel | TREATMENT PLANNED — known open item, not newly discovered |
| R019 | UPL (Unauthorized Practice of Law) claim against investment-intelligence reports | 2 | 5 | 10 | Explicit disclaimers on every customer-facing report and on `/disclaimer` | LOW | Ariel | ACCEPTED — mitigated by disclosure, not by legal review of every report |
| R020 | CCPA/Florida privacy rights request not fulfilled within 30 days | 1 | 3 | 3 | `privacy@biddeed.ai` monitored by Ariel; 30-day SLA stated in `DATA_RETENTION_POLICY.md` | LOW | Ariel | ACCEPTED |
| R021 | Overly broad `get_vault_secret_mcp()` grant enables unrestricted vault reads | 2 | 5 | 10 | No internal gate; `EXECUTE` granted to `PUBLIC`/`anon`/`authenticated`/`service_role`/`postgres` — carried-over open finding from GTM-22D (2026-07-19) | MEDIUM–HIGH | Ariel | TREATMENT PLANNED — top follow-up flagged in the GTM-22D closing report; not yet remediated as of this review |
| R022 | CI security-gate workflow exists but is not confirmed to be logging results | 2 | 2 | 4 | `.github/workflows/security-scan.yml` present and wired into PR gating (Semgrep, Gitleaks, npm/pip audit) | LOW | Ariel | TREATMENT PLANNED — `security_scan_results` table holds 0 rows as of 2026-08-03; the gate may be functioning at the PR-check level without persisting to this table, or may not yet have had a qualifying run — not yet distinguished |
| R023 | No external DAST/penetration test has been run against production | 2 | 4 | 8 | Mozilla HTTP Observatory + SSL Labs run 2026-08-03 (header/TLS hygiene only, not a penetration test) | MEDIUM | Ariel | TREATMENT PLANNED — OWASP ZAP, Garak, and Nikto scans are policy-defined (`VULNERABILITY_MANAGEMENT_POLICY.md`) but have not yet been executed against production; requires an explicit go-ahead before pointing a DAST scanner at live customer-facing infrastructure |

## Notes on scoring methodology

Score = Likelihood × Impact, both 1 (rare/negligible) to 5 (frequent/severe).
"Residual Risk" is a qualitative post-control judgment, not a re-multiplied
number — ISO 27001 auditors expect to see the reasoning, not just an
arithmetic residual score.

## Highest-priority open items (TREATMENT PLANNED, ranked by score)

1. **R014** (score 15) — YubiKey purchase, founder social-engineering surface.
2. **R008 / R009 / R012** (score 12 each) — secret-rotation execution gap;
   model/report accuracy risk (both accepted-with-disclosure, not solved).
3. **R018** (score 9) — parity_status gating gap, already tracked pre-existing.
4. **R021 / R010 / R001 / R019** (score 10) — the vault-grant open finding
   (R021) is the single highest-severity *unremediated* item in this register
   in terms of blast radius, since it affects secret confidentiality
   platform-wide, not one customer's data.

This register does not claim any of the above are closed. Where a control is
"planned" rather than "in place," this document says so.
