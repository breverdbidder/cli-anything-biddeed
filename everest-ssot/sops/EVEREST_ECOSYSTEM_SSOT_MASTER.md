# EVEREST ECOSYSTEM MASTER SSOT & SOP
Canonical operating reference. Role of Claude = AI Architect (designs+decides+ships+reports; asks only for 4 gated items: >$10 spend, destructive schema ALTER/DROP, security/auth, methodology pivot). Everything else EXECUTE_AND_REPORT.

THE SPINE: ssot_registry_projects + ssot_registry_components tie projects -> agents/subagents/skills/workflows/repos. v_ssot_master = every component x project x tier. v_ssot_legal_master = all legal sources unified (150 skills + legal repos). Spine POINTS INTO existing catalogs (external_skill_catalog, external_agent_catalog, anthropic_managed_agents, gha_workflow_catalog, repo_evaluations, ci_v65_*), does NOT duplicate them.

PROJECTS (6, veils separated): everest_capital_usa (parent), everest_capital_development (RE dev), everest_capital_of_brevard_llc (litigant, ci NONE), biddeed_ai (ci PRIMARY), zonewise_ai (ci PRIMARY), everest_shared (cross-cutting legal/infra/SOPs).

GOVERNANCE TIERS: catalogued / reference / gate / active / counsel / restricted. The 7 legal gate skills: ai-governance-legal:use-case-triage, ai-governance-legal:vendor-ai-review, ai-governance-legal:reg-gap-analysis, ip-legal:oss-review, ip-legal:fto-triage, commercial-legal:review, privacy-legal:use-case-triage.

STANDING SOP for any new component: (1) register row in ssot_registry_components; (2) detail body lives in its catalog; (3) assign governance_tier honestly; (4) honesty_marker on row; (5) if touches competitors/vendors/PII route through matching gate skill before active.

QUERY ENTRY POINTS: whole ecosystem = select * from v_ssot_master; one project = where project_key=...; all legal = select * from v_ssot_legal_master; active gates = where governance_tier='gate'. Gated (your word): consolidating/retiring 4 legacy project tables (ecu_projects/pm_projects/project_tracker_projects/rehab_projects).