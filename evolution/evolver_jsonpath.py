# evolution/evolver_jsonpath.py
# AUTOLOOP V2 — Structured-config patch generator (multi-LLM router)
# Pattern source: parallel to evolver.py, but emits JsonPathEntry instead of EvolutionEntry
# Companion to: evolution/jsonpath_patcher.py (the apply step)
# Spec: docs/EVOLVER-JSONPATH.md
# Issue: TBD (stacked PR on top of #7473)

"""
LLM router for STRUCTURED-CONFIG patch generation.

Mirrors `Evolver` (evolver.py) but:
  - Prompt schema is { entries: [{ field, new_value, action, reason }] }
  - Returns list[JsonPathEntry] instead of list[EvolutionEntry]
  - Takes a WhitelistConfig and includes it in the prompt so the LLM constrains
    its output to patchable fields BEFORE the patcher rejects bad paths
  - Surgical filter is COUNT-based (max_entries) instead of LINE-GROWTH-based
    because JSON-path patches aren't measured in lines

REUSE STRATEGY (avoids touching evolver.py at all — K3 surgical):
  - `Evolver` is composed (not subclassed) for RCA-filtering + cost tracking
  - LLM HTTP plumbing is locally duplicated (~60 LOC); if this becomes painful,
    a separate refactor PR can extract a shared `_LlmRouter` helper

WHY NOT MONKEY-PATCH EVOLVER (rejected designs):
  - Polymorphic `generate(target_format=...)`: branches on str, return-type
    unstable, harder to unit-test
  - Polymorphic prompt that emits both schemas: wastes LLM tokens on irrelevant
    section every call, and entry-counting K3 logic becomes mixed
  - Subclass with method override: requires touching evolver.py to make
    methods overridable
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Optional

from .evolver import Evolver, _GEMINI_MODEL  # reused composition
from .jsonpath_schema import JsonPathEntry, WhitelistConfig
from .schema import EntryAction, EvolutionSignal, SignalType


# ── LLM tiers (mirror evolver.py constants, kept independent for testing) ─────

_DEEPSEEK_MODEL = "deepseek-chat"            # Tier 2 — primary patch generator ($0.28/1M)
_CLAUDE_MODEL = "claude-sonnet-4-6"          # Tier 3 — quality fallback (~$3 in / $15 out per 1M)
_MAX_ENTRIES_PER_ROUND = 2                   # match evolver.py to keep hallucination flood guard


# ── Prompt template ───────────────────────────────────────────────────────────
# Mirrors agentic-video-maker's gemini-critique.cjs SYSTEM_PROMPT structure +
# evolver.py's _GENERATE_PROMPT shape. Key differences:
#   - Output schema is {field, new_value} not {section, content}
#   - WHITELIST_JSON is rendered into the prompt so the LLM sees what's patchable
#   - Severity tags are kept conceptually (P0/P1/P2 → reason text) but not
#     enforced in this schema (the patcher already does that downstream)

_GENERATE_JSONPATH_PROMPT = """\
You are a structured-config evolution engine for BidDeed.AI's AUTOLOOP V2.
Your job is to generate JSON-path patches for a STRUCTURED CONFIG (not markdown).

## SKILL NAME
{skill_name}

## TARGET CONFIG (current JSON state)
{config_json}

## DETECTED SIGNALS
{signals_json}

## SCORE CONTEXT
{score_context}

## WHITELIST (CRITICAL — patches outside this list will be silently dropped)
{whitelist_json}

## TASK
Generate up to {max_entries} JSON-path patches that fix concrete failure modes
detected in the signals above.

Return ONLY valid JSON (no markdown fences, no prose):
{{
  "entries": [
    {{
      "field": "<dotted path matching one of the whitelist patterns>",
      "new_value": <int|float|bool|string — must satisfy the whitelist constraint>,
      "action": "update",
      "reason": "<1 sentence: what signal this fixes>"
    }}
  ]
}}

Rules:
- Max {max_entries} entries
- `field` MUST match a whitelist pattern. Anything else will be dropped by the patcher.
- `new_value` MUST be a primitive (int / float / bool / string), never an object or array.
- Numeric values: respect the min/max bounds declared in the whitelist.
- Enum values: must be one of the listed `values`.
- If signals are noise or no whitelisted patch applies, return {{"entries": []}}.
"""


# ── JsonPathEvolver ───────────────────────────────────────────────────────────

class JsonPathEvolver:
    """
    Generate structured-config patches via multi-LLM router.

    Usage:
        evo = JsonPathEvolver(skill_name="sentinel-thresholds")
        wl = WhitelistConfig(
            target="sentinel-thresholds",
            allowed_paths={
                r"^thresholds\\.alert_threshold$": dict(type="int", min=10, max=10000),
            },
        )
        config = {"thresholds": {"alert_threshold": 100}}
        entries = evo.generate(signals, config=config, whitelist=wl)
        # entries: list[JsonPathEntry] ready for JsonPathPatcher.apply(config, entries)
    """

    def __init__(
        self,
        skill_name: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        deepseek_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        max_entries: int = _MAX_ENTRIES_PER_ROUND,
    ):
        self.skill_name = skill_name or "unknown"
        self._deepseek_key = deepseek_api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self._anthropic_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.max_entries = max(1, min(max_entries, _MAX_ENTRIES_PER_ROUND))
        self._total_token_cost: float = 0.0

        # Compose an inner Evolver for RCA filtering. We only consume its
        # public/internal interface for _rca_filter and _call_gemini.
        self._inner = Evolver(
            skill_name=skill_name,
            gemini_api_key=gemini_api_key,
            deepseek_api_key=deepseek_api_key,
            anthropic_api_key=anthropic_api_key,
            max_entries=max_entries,
        )

    @property
    def total_token_cost(self) -> float:
        return self._total_token_cost + self._inner.total_token_cost

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(
        self,
        signals: list[EvolutionSignal],
        config: dict,
        whitelist: WhitelistConfig,
        eval_score_before: Optional[float] = None,
        eval_score_after: Optional[float] = None,
    ) -> list[JsonPathEntry]:
        """
        1. RCA filter via Gemini Flash (free, reused from inner Evolver)
        2. DeepSeek primary generation
        3. Claude Sonnet fallback if DeepSeek empty
        4. Return list[JsonPathEntry] — caller passes to JsonPathPatcher.apply()
        """
        if not signals:
            return []

        relevant = self._inner._rca_filter(signals)
        if not relevant:
            return []

        score_context = self._format_score_context(eval_score_before, eval_score_after)

        entries = self._call_deepseek(
            relevant, config, whitelist, score_context, eval_score_before
        )
        if not entries and self._anthropic_key:
            entries = self._call_claude(
                relevant, config, whitelist, score_context, eval_score_before
            )
        return entries[: self.max_entries]

    # ── Private: LLM calls ────────────────────────────────────────────────────

    def _call_deepseek(
        self,
        signals: list[EvolutionSignal],
        config: dict,
        whitelist: WhitelistConfig,
        score_context: str,
        eval_score_before: Optional[float],
    ) -> list[JsonPathEntry]:
        if not self._deepseek_key:
            return []
        prompt = self._build_prompt(signals, config, whitelist, score_context)
        try:
            import httpx
            resp = httpx.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._deepseek_key}"},
                json={
                    "model": _DEEPSEEK_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1024,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            tokens = usage.get("total_tokens", 0)
            cost = tokens * 0.00000028
            self._total_token_cost += cost
            return self._parse_entries(
                content, signals=signals, model=_DEEPSEEK_MODEL,
                token_cost=cost, eval_score_before=eval_score_before,
            )
        except Exception:
            return []

    def _call_claude(
        self,
        signals: list[EvolutionSignal],
        config: dict,
        whitelist: WhitelistConfig,
        score_context: str,
        eval_score_before: Optional[float],
    ) -> list[JsonPathEntry]:
        if not self._anthropic_key:
            return []
        prompt = self._build_prompt(signals, config, whitelist, score_context)
        try:
            import httpx
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": _CLAUDE_MODEL,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["content"][0]["text"]
            usage = data.get("usage", {})
            in_tokens = usage.get("input_tokens", 0)
            out_tokens = usage.get("output_tokens", 0)
            cost = (in_tokens * 0.000003) + (out_tokens * 0.000015)
            self._total_token_cost += cost
            return self._parse_entries(
                content, signals=signals, model=_CLAUDE_MODEL,
                token_cost=cost, eval_score_before=eval_score_before,
            )
        except Exception:
            return []

    # ── Private: Prompt + Parser ──────────────────────────────────────────────

    def _build_prompt(
        self,
        signals: list[EvolutionSignal],
        config: dict,
        whitelist: WhitelistConfig,
        score_context: str,
    ) -> str:
        signals_json = json.dumps(
            [
                {
                    "type": s.signal_type.value
                    if isinstance(s.signal_type, SignalType)
                    else s.signal_type,
                    "excerpt": s.excerpt,
                    "source": s.source,
                }
                for s in signals
            ],
            indent=2,
        )
        # Render the whitelist as a {pattern: constraint} dict the LLM can read.
        # Note: regex anchors (^, $) are visible — the LLM should treat them as patterns,
        # not literals. The prompt rules above already say "MUST match a whitelist pattern".
        whitelist_json = json.dumps(
            {pat: meta for pat, meta in whitelist.allowed_paths.items()},
            indent=2,
        )
        # Cap config to 3K chars (parallel to evolver.py's skill_md cap).
        config_str = json.dumps(config, indent=2)[:3000]
        return _GENERATE_JSONPATH_PROMPT.format(
            skill_name=self.skill_name,
            config_json=config_str,
            signals_json=signals_json,
            score_context=score_context,
            whitelist_json=whitelist_json,
            max_entries=self.max_entries,
        )

    def _parse_entries(
        self,
        llm_output: str,
        signals: list[EvolutionSignal],
        model: str,
        token_cost: float,
        eval_score_before: Optional[float] = None,
    ) -> list[JsonPathEntry]:
        """Parse LLM JSON output → list[JsonPathEntry]. Robust against fenced output."""
        parsed = self._parse_json(llm_output)
        raw_entries = parsed.get("entries", [])
        result: list[JsonPathEntry] = []
        first_signal_id = signals[0].id if signals else None

        for raw in raw_entries[: self.max_entries]:
            field_ = raw.get("field")
            if not field_ or not isinstance(field_, str):
                continue
            if "new_value" not in raw:
                continue
            action_str = raw.get("action", "update")
            try:
                action = EntryAction(action_str)
            except ValueError:
                action = EntryAction.UPDATE

            entry = JsonPathEntry(
                skill_name=self.skill_name,
                target=self.skill_name,
                field=field_,
                new_value=raw["new_value"],
                action=action,
                source_signal_id=first_signal_id,
                llm_model_used=model,
                token_cost=token_cost / max(1, len(raw_entries)),
                eval_score_before=eval_score_before,
            )
            result.append(entry)
        return result

    def _parse_json(self, text: str) -> dict:
        """Robust JSON parser: direct → regex extract → empty dict."""
        text = text.strip()
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except (json.JSONDecodeError, ValueError):
                pass
        return {}

    def _format_score_context(
        self, score_before: Optional[float], score_after: Optional[float]
    ) -> str:
        if score_before is None and score_after is None:
            return "No score data available."
        if score_before is not None and score_after is not None:
            delta = score_after - score_before
            direction = "dropped" if delta < 0 else "improved"
            return (
                f"Eval score {direction} from {score_before:.1%} to {score_after:.1%} "
                f"(Δ {delta:+.1%})"
            )
        if score_before is not None:
            return f"Baseline eval score: {score_before:.1%}"
        return f"Latest eval score: {score_after:.1%}"
