# EVEREST AI-GOVERNANCE REGISTRY
Authoritative source for ai-governance-legal:use-case-triage. The Risk-Classification subagent reads THIS. Binds to ssot_registry_components (governance_tier='gate') + ci_v65_risk_register. Read by ci_governance_triage.py.

RED LINES (deterministic — auto NOT_APPROVED, no LLM discretion):
- RL1 auth_bypass: No login/paywall/access-control circumvention of ANY third party. on_hit BLOCKED/restricted.
- RL2 security_probing: No OWASP/auth-weakness/vuln testing against any competitor PRODUCTION env. BLOCKED.
- RL3 moat_contamination: Competitor-derived data NEVER written to moats (zw_parcels, fl_parcels, BCPAO bridge, SSOTs). BLOCKED.
- RL4 litmus_only: PropertyOnion AND FloridaBidder = parity litmus ONLY. Never enrichment/resolution source. BLOCKED.
- RL5 gated_endpoint_replay: Endpoints requiring auth are never replayed; gated pages enumerated, never fetched. BLOCKED.

USE-CASE REGISTRY (LLM triage classifies against these):
- CI001 public_competitor_recon: crawl PUBLIC competitor surface -> APPROVED / AUTO_CLEAR. Ordinary business, no litigation nexus.
- CI002 pii_capture_at_scale: scrape captures PII at scale -> CONDITIONAL / ESCALATED, handoff privacy-legal (run privacy-legal:use-case-triage, PIA, minimize).
- CI003 gated_competitor_access: access authenticated/paywalled competitor data -> NOT_APPROVED / BLOCKED (RL1+RL5).
- CI004 vendor_data_tool: paid vendor (Bright Data/BuiltWith/SimilarWeb/Firecrawl) in pipeline -> CONDITIONAL / ESCALATED, handoff commercial-legal (commercial-legal:review + ai-governance-legal:vendor-ai-review, ToS, spend<=cap).
- CI005 parity_litmus: field-level parity vs CANONICAL SOURCE -> APPROVED / AUTO_CLEAR. Source adjudicates, zero competitor rows into moats.
- CI006 oss_dependency: adopt forked skill/scraper/library (Apache-2.0) -> CONDITIONAL / ESCALATED, handoff ip-legal (ip-legal:oss-review, preserve license, no patent assertion over forked methodology).

CLASSIFICATION -> ci_v65_risk_register MAPPING:
- APPROVED -> AUTO_CLEAR, severity 2, likelihood 1 (GREEN)
- CONDITIONAL -> ESCALATED, severity 3, likelihood 2 (YELLOW, run handoff skill)
- NOT_APPROVED -> BLOCKED, severity 4, likelihood 3 (ORANGE, stop run)
Counsel escalation only if handoff skill output is itself unresolved (narrow exception).