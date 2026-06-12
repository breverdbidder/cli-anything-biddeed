# ULTRALOOP — SSOT: Gold Standard Certification Audits via Dynamic Workflows
**Status:** ACTIVE (ratified Ariel 2026-06-12) | **Owner:** Claude AI Architect | **Runtime copy:** `gold_standard_brief_template` id=1 (§ ULTRALOOP PROTOCOL)
**Scope:** every gold-standard fleet session (08:00Z / 16:00Z / 00:00Z + autopilot launches, cron 161) and every `gold_standard_certify` claim.

## Why
Single-context 6h sessions exhibit agentic laziness, self-preferential bias, and goal drift. Certification on self-graded numbers produced the Brevard B=135.8% anomaly passing as gold. ULTRALOOP moves audit orchestration out of the main context window: isolated subagents measure, independent refuters attack, claims certify only on survival.

## Protocol (canonical — brief template mirrors this)
1. **INIT** — `/effort ultracode` (Claude Code >= 2.1.154, xhigh-capable model). Menu lacks ultracode → fall back to manual Task-subagent fan-out, same patterns, no blocking. Record mode (see Storage).
2. **AUDIT = fan-out-and-synthesize** — one workflow; one isolated subagent per failing letter per county; goal: measure letter vs `pencil_dod_criteria` from live tables only. Honesty markers mandatory; no VERIFIED without an executed query.
3. **VERIFY = adversarial survival vote** — every "letter moved/passed" claim gets an independent refuter whose only goal is to break it (denominator mismatch, double-count, ghost-success, stale source). Survives → ships. Refuted → false positive: logged, not counted, never certified. Anomalous ratios (metric > 100%) auto-fail.
4. **FIX = loop-until-done** — iterate against live `gold_standard_county_status`; fixer ≠ verifier, always.
5. **SAVE** — persist working workflows under `.claude/workflows/` in-repo; deterministic + resumable; next session re-runs, never re-derives.
6. **TOKEN GUARDRAILS** — ultracode for AUDIT/VERIFY/bug-hunt phases only; `/effort high` for routine chores; max ONE deep workflow per letter per session; Max-plan OAuth only — metered API keys BANNED for workflow runs.
7. **CERTIFY GATE** — no refuter evidence = no certification, regardless of scoreboard numbers.

## Storage (structured — replaces free-text self_audit notes)
Table `public.gold_standard_ultraloop_audit` — one row per claim per session:
- `dispatch_id` → summit_chat_dispatch.id of the session
- `ultraloop_mode` — `native` | `fallback`
- `county_slug`, `letter` (A–J), `claim`
- `refuter_evidence` (jsonb: what was attacked, queries run, result)
- `survived` (bool) — false rows are the false-positive ledger
- `created_at`
`gold_standard_certify` MUST find, for each letter it certifies, >= 1 row with `survived = true` for that county+letter newer than the letter's last metric change. Zero rows = gate fails closed.

## Failure semantics
- Refuted claim → row with `survived=false`; session continues to next target; NEVER retries the same claim without new evidence.
- Anomaly class (B>100% style) → auto `survived=false` + Telegram via telegram-notify.yml.
- BLANK > WRONG: a letter with no audit row is UNKNOWN, not passing.

## Cross-refs (SSOT discipline)
- `docs/EVEREST-GATE.md` (EG14+K1-K4) — ULTRALOOP supplements, never replaces, prod gates.
- `docs/plans/CI-DOSSIER-CHECKPOINT-PROTOCOL-v1-2.md` — ghost-success ban inherited verbatim.
- `gold_standard_brief_template` id=1 — runtime mirror; this file wins on conflict.
- Honesty Protocol V3 — markers mandatory in all subagent outputs.
