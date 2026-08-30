# ULTRALOOP — SSOT: Gold Standard Certification Audits via Dynamic Workflows
**Status:** ACTIVE (ratified Ariel 2026-06-12) | **Owner:** Claude AI Architect | **Runtime copy:** `gold_standard_brief_template` id=1 (§ ULTRALOOP PROTOCOL)
**Scope:** every gold-standard fleet session (08:00Z / 16:00Z / 00:00Z + autopilot launches, cron 161) and every `gold_standard_certify` claim.

## Why
Single-context 6h sessions exhibit agentic laziness, self-preferential bias, and goal drift. Certification on self-graded numbers produced the Brevard B=135.8% anomaly passing as gold. ULTRALOOP moves audit orchestration out of the main context window: isolated subagents measure, independent refuters attack, claims certify only on survival.

## Protocol (canonical — brief template mirrors this)
1. **INIT** — `/effort ultracode` (Claude Code >= 2.1.154, xhigh-capable model). Menu lacks ultracode → fall back to manual Task-subagent fan-out, same patterns, no blocking. Record mode (see Storage).
2. **AUDIT = fan-out-and-synthesize** — one workflow; one isolated subagent per failing letter per county; goal: measure letter vs `pencil_dod_criteria` from live tables only. Honesty markers mandatory; no VERIFIED without an executed query.
3. **VERIFY = adversarial survival vote** — every "letter moved/passed" claim gets an independent refuter whose only goal is to break it (denominator mismatch, double-count, ghost-success, stale source, cross-case duplicate-value clusters — see Failure semantics). Survives → ships. Refuted → false positive: logged, not counted, never certified. Anomalous ratios (metric > 100%) auto-fail.
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
- **DUPLICATE-CLUSTER CHECK (added 2026-08-30, architect triage on issue #19621, jackson J):** for any letter backed by a per-row generator (J's `bid_decisions` is the recurring offender), the refuter MUST group the claimed rows by their full value tuple (e.g. `arv,max_bid,ml_score,repairs` for J) and fail the claim if any tuple is shared across more than a handful of distinct `case_number`s. Point-checking one or two rows against a live source is not sufficient — a formula that is individually plausible per row (e.g. a floor/ceiling clamp, or a COALESCE default applied when real source data is missing) can still collapse dozens of unrelated properties onto byte-identical output. CONFIRMED live 2026-08-30: jackson J's 08-23 "rebuild" (audit id 17282, wrongly `survived=true`) left 124 of 145 jackson cases resting on only 3 shared constant-tuple clusters in `bid_decisions` (`scripts/shard6_j_generator.py`'s `arv = max(arv, arv_base*0.4)` floor collapses any case with a low `opening_bid` to the same county-wide constant); the identical anti-pattern recurred again the same day this was diagnosed (14 more jackson cases collapsed onto a new shared tuple at 2026-08-30T08:22Z, audit id 19666 — refuted for a different reason, evidence-quality, without ever noticing the duplicate-cluster signature). `arv_source`/similar provenance-label tombstoning does NOT fix this — `pencil_dod_evaluate_county`'s J check does not read that column, so relabeling ghost rows changes nothing about the metric.

## Cross-refs (SSOT discipline)
- `docs/EVEREST-GATE.md` (EG14+K1-K4) — ULTRALOOP supplements, never replaces, prod gates.
- `docs/plans/CI-DOSSIER-CHECKPOINT-PROTOCOL-v1-2.md` — ghost-success ban inherited verbatim.
- `gold_standard_brief_template` id=1 — runtime mirror; this file wins on conflict.
- Honesty Protocol V3 — markers mandatory in all subagent outputs.
