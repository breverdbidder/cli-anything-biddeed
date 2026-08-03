# AI-CAIQ — BidDeed.AI AI Security Self-Assessment

**Prepared by:** Ariel Shapira, Founder, BidDeed.AI / Everest Capital USA
**Date:** August 3, 2026
**Scope:** MCP tool server (`mcp.biddeed.ai`, 25 tools), chatbot (`biddeed.ai`),
`shapira_models` XGBoost auction-outcome classifier
**This is not legal advice, and this is not a certified audit.**

## Version note (read before distributing)

**INFERRED, not confirmed this session:** "AI-CAIQ v1.1" is the version name
requested by the internal brief. No live check was performed against
CSA/any standards body to confirm an official "AI-CAIQ v1.1" specification
exists with a fixed control-ID list. This document is organized around the
five domains the brief itself named — AI Governance, AI Security, AI
Privacy, AI Operational Resilience, AI Transparency — and answers their
substance. Treat the domain answers below as BidDeed's own structured
AI-security self-assessment, not a verbatim reproduction of a numbered
external spec.

## Trade secret boundary (read before distributing)

`TRADE-SECRET-POLICY.md` (this repo) designates the following as protected
trade secrets, not to be disclosed in investor decks, marketing materials,
or public documents without Ariel Shapira's written approval: **Shapira
Formula parameters, XGBoost model weights, reward function constants, the
historical training dataset itself, CMA adjustment coefficients,
jurisdiction opportunity-scoring thresholds, and behavioral matching model
weights.** This document describes AI *governance and security posture*
only — it does not disclose any of the above. Where a question would
require disclosing a trade secret to answer fully (e.g., "describe your
training data in detail"), this document answers at the governance level
and states that the underlying detail is confidential IP, available under
NDA only.

---

## Corrections from the originating brief

Several AI-security claims assumed by the internal brief do not match live
evidence gathered this session. Corrected here rather than repeated:

| Brief assumed | Live evidence | This document answers |
|---|---|---|
| Prompt injection protection via LlamaFirewall (Meta) + LLM Guard (Protect AI), 35 scanners, on 36 MCP tools | No Python runtime in the MCP server's deploy path (Node ESM). Actual control: native JS pattern-based prompt-injection/secret-leak scanning in `guardrails.js` at the single `handleToolCall` chokepoint. 25 tools, not 36. | AI Security section describes the real guardrails.js control. |
| Adversarial testing via Garak LLM vulnerability scanner, monthly | No reference to Garak found anywhere in this repository or its docs. | Answered NO — no LLM red-team/adversarial scan has been run yet. |
| Model documentation: "training corpus 171,860 samples documented, AUC 0.783, accuracy 0.722" | The AUC figure is corroborated across multiple independent internal session reports referencing `shapira_models` v14.0 (values observed: 0.7834, 0.78) — treated as CONFIRMED. The 171,860-sample count and 0.722 accuracy figure were **not found anywhere in this repository** during this session's search — not claimed here as verified. | AI Governance section cites only the AUC figure, with its actual sourced value, and marks sample count/accuracy as unverified rather than repeating unconfirmed numbers. |
| Bias monitoring via `parity_status`/`parity_checked_at` on `multi_county_auctions` | These fields track **data-source reconciliation** — whether BidDeed's scraped auction record matches the official county source — not model fairness or demographic bias. Conflating a data-quality field with AI bias monitoring would misrepresent the control. | AI Transparency section answers bias monitoring as NOT YET IMPLEMENTED, and separately credits the real (but distinct) data-parity control under AI Governance/data quality. |
| Explainability: "SHAP values planned in V4.0 ensemble; current v14.0 provides feature importance" | No reference to SHAP, a "V4.0 ensemble," or a documented feature-importance report was found in this session's search of the repository. | Answered as ROADMAP / NOT YET IMPLEMENTED, not as a current capability. |

---

## AI Governance

| Question | Answer | Evidence |
|---|---|---|
| Is there an inventory of AI/ML models in production? | YES | `shapira_models` table (Supabase) tracks model versions; the production auction-outcome classifier is version `v14.0`, stored in the `shapira-models` storage bucket. Corroborated independently across multiple internal session reports (not a single unverified claim). |
| Is model performance documented? | PARTIAL | The model's AUC (~0.78, observed as 0.7834 and 0.78 across independent sessions on different dates — consistent, treated as CONFIRMED) is documented and cross-referenced repeatedly. A formal, single model card with training corpus size, accuracy, precision/recall, and evaluation methodology was **not found** in this repository as of this session — recommend creating one rather than continuing to cite the AUC figure without its supporting documentation. |
| Is there an AI risk management process? | YES | `CERT_REQUIRED` gating exists on higher-risk MCP tool tiers (e.g., S3/S5); attempts to bypass the cert gate are logged as P2-severity `security_events`, per the Incident Response Plan. |
| Is a known model-quality issue tracked and disclosed? | YES (disclosed, not hidden) | An internal audit (`GOLD_STANDARD_SHARD1_...C40BB245...` session report) found `ml_score` returning a constant, zero-variance value for at least two counties (pinellas, citrus) — a real, undisclosed scorer-degeneracy bug at the time it was found, flagged for follow-up investigation. Referencing this here rather than omitting it is consistent with this document's own honesty standard: an AI-CAIQ that only lists working controls is not credible. |
| Is training data governance documented? | PARTIAL | Training data is Florida public court/property records for the auction-outcome model — disclosed at that level. The dataset's exact composition, size, and labeling methodology are trade secret (`TRADE-SECRET-POLICY.md` item 4) and are not disclosed beyond that in this document; available under NDA. |
| Is there human accountability for AI-driven output? | YES | Ariel Shapira is the sole model owner and sole approver of any change to production scoring logic — no autonomous retraining/redeploy pipeline operates without his review (see AI Operational Resilience). |

## AI Security

| Question | Answer | Evidence |
|---|---|---|
| Is there prompt injection protection? | YES | Native pattern-based scanning (`packages/biddeed-mcp/src/security/guardrails.js`) runs at the single canonical `handleToolCall` chokepoint on all 25 MCP tools — scans both caller arguments and tool results before caching for idempotent replay. 60/60 guardrail tests passing as of commit `31a71992`. This is a **documented deviation** from an earlier spec that called for Python-based LlamaFirewall/LLM Guard; the MCP server has no Python runtime in its deploy path, so native JS scanning was built instead. |
| Is untrusted external data labeled as such to the model? | YES | Every MCP tool response carries an explicit notice that scraped county court documents and case data are untrusted external data, never instructions — addresses OWASP LLM Top 10 (prompt injection via retrieved content). |
| Has adversarial/red-team testing been performed against the LLM surface? | **NO** | No LLM red-team or adversarial-prompt scanning tool (Garak or otherwise) has been run against production. Stated plainly; this is an open item, not a claimed control. |
| Is model artifact integrity protected? | PARTIAL | The production model is stored in a dedicated Supabase storage bucket (`shapira-models`) rather than embedded in application code or committed to a public path. Cryptographic hash-verification of the artifact at load time was **not confirmed** this session — do not treat "hash-verified" as an established control until directly checked. |
| Is API/tool access to AI capabilities rate-limited and billing-gated? | YES | All 25 MCP tools are billing-gated and idempotency-keyed; a retried or replayed call cannot double-charge or double-execute a model inference. |
| Are secrets used by AI infrastructure (API keys, model storage credentials) protected the same as other secrets? | YES | Same vault/gated-accessor pattern as all other secrets in the platform — no separate, weaker path for AI-specific credentials was found. |

## AI Privacy

| Question | Answer | Evidence |
|---|---|---|
| Is training data free of customer PII? | YES | The auction-outcome model trains on Florida public court/property records — sourced from government filings, not from BidDeed customer accounts or their individual usage behavior. |
| Is customer chat content used to train or fine-tune any model? | NO | Chat content is sent to Anthropic for inference only, per the vendor list; BidDeed does not separately fine-tune a model on customer chat transcripts. |
| Is data minimization applied to AI-adjacent logging? | PARTIAL | `taxi_meter_streams`/`taxi_meter_tools` log tool name, timing, and billing metadata per call. Whether the raw API key or only a hashed form is stored in every one of these logging paths was **not independently re-verified** this session — the platform's stated design intent is hash-only, but this document does not claim that as freshly confirmed. |
| Is there a documented data subject deletion path? | YES | `docs/legal/DATA_RETENTION_POLICY.md` — deletion requests via `privacy@biddeed.ai`, processed within 30 days. Public-record auction/property data is explicitly excluded (not BidDeed's to delete — sourced from county government systems). |
| Is there user-facing transparency about AI involvement in output? | YES | Investor-facing reports include an explicit disclaimer that output is decision-support, not an appraisal, and not legal/investment advice — consistent with the "not legal advice" framing used across every document in `docs/security/` and `docs/legal/`. |

## AI Operational Resilience

| Question | Answer | Evidence |
|---|---|---|
| Is there a fallback when the AI/scoring pipeline fails or is uncertain? | YES | If a certification gate fails or a tool cannot complete cert-required verification, the platform returns a REVIEW-class output rather than a BID-class recommendation — the system is designed to degrade to "ask a human" rather than fail open into an autonomous action. |
| Is model output monitored post-deployment for drift or degradation? | PARTIAL | The `ml_score` zero-variance finding above (pinellas/citrus) demonstrates that degeneracy detection currently happens through ad hoc county-level audits, not a standing automated drift-monitoring job. This is a real, disclosed gap — automated post-deployment score-distribution monitoring does not appear to exist yet as a scheduled control. |
| Is there an incident response path specific to AI failures (e.g., successful prompt injection, bad model output causing customer harm)? | YES | Playbook P0-B in `INCIDENT_RESPONSE_PLAN.md` covers "Prompt Injection Success (guardrails bypassed)" specifically — pull logs, identify the bypassing input, add a regression pattern + test, redeploy, review the same API key's recent call history for further exploitation. |
| Is there a fully autonomous AI action path with no human checkpoint (e.g., autonomous bid execution)? | NO | No autonomous bid-execution path exists. All Shapira Formula/model output is decision-support for a human bidder; there is no automated system that places a bid on a customer's behalf. |

## AI Transparency

| Question | Answer | Evidence |
|---|---|---|
| Is model explainability (e.g., feature importance, SHAP) provided to users? | **NO — roadmap item, not current capability** | No SHAP integration or per-prediction feature-importance report was found in this repository. Corrected from the originating brief, which described this as in-progress/planned; this document does not claim even "planned/candidate status" work exists without evidence, only that it is not currently implemented. |
| Is there human oversight of AI-driven recommendations before customer-facing use? | YES | Ariel Shapira reviews and attributes the Shapira Formula methodology directly; reports are explicitly attributed to a named, accountable human process, not presented as an unowned black-box output. |
| Is AI model bias/fairness monitored (e.g., across geography, property type, demographic proxy)? | **NO** | Corrected from the originating brief. `parity_status`/`parity_checked_at` on `multi_county_auctions` track whether BidDeed's scraped auction record matches the official county data source (a data-quality/reconciliation control) — they are not a model-fairness or demographic-bias monitoring mechanism, and no separate bias-monitoring process was found. Given the model scores Florida foreclosure/tax-deed opportunities rather than individuals, geographic/property-type skew (e.g., which counties get the most reliable scores) is the more relevant fairness question for this product and is not currently tracked as such. |
| Are limitations of the AI system disclosed to users? | YES | Reports carry an explicit "decision-support, not an appraisal" disclaimer; the public `/security` page discloses, rather than omits, that DAST/LLM red-team testing has not yet been performed. |

---

## Summary for procurement/investor reviewers

BidDeed.AI's AI-specific security posture rests on one real, load-bearing
control — native prompt-injection/secret-leak scanning at a single
canonical MCP chokepoint — plus a working, if manually-audited, production
XGBoost classifier with a corroborated ~0.78 AUC. Its genuine, disclosed AI
gaps are: no LLM red-team/adversarial testing performed, no automated
post-deployment model-drift monitoring, no explainability (SHAP or
equivalent) surfaced to users, and no true bias/fairness monitoring
(the existing `parity_status` field solves a different, data-reconciliation
problem and should not be conflated with fairness monitoring). Underlying
model weights, training dataset composition, and Shapira Formula parameters
are protected trade secrets and are described here only at the governance
level, per `TRADE-SECRET-POLICY.md`.

*Questions not answered here: security@biddeed.ai.*
