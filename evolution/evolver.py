# evolution/evolver.py
# Inspired by openJiuwen-ai/jiuwenclaw (Apache 2.0)
# AUTOLOOP V2 — Multi-LLM Skill Patcher via Smart Router
# Issue: breverdbidder/cli-anything-biddeed#67

"""
Evolver — generates SKILL.md patches using a multi-LLM Smart Router.

BEATS JiuwenClaw:
  - Multi-LLM: Gemini Flash (RCA) → DeepSeek V3.2 (patch) → Claude Sonnet (quality fallback)
  - Score regression context in prompt (they don't have)
  - Sentinel alert context in prompt (they don't have)
  - Our SKILL.md structure vs their format
  - token_cost tracking per entry
  - English-only prompts (stripped their Chinese)
  - Max 2 entries per round (same cap, different reason)
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Optional

from .schema import EntryAction, EvolutionEntry, EvolutionSignal, SignalType, VALID_SECTIONS

# ── Smart Router Config ───────────────────────────────────────────────────────
# Tier 1: Gemini Flash FREE — initial RCA classification
# Tier 2: DeepSeek V3.2 $0.28/1M — patch generation
# Tier 3: Claude Sonnet — quality fallback when DeepSeek patch fails eval

_GEMINI_MODEL = "gemini-2.0-flash"
_DEEPSEEK_MODEL = "deepseek-chat"
_CLAUDE_MODEL = "claude-sonnet-4-6"

_MAX_ENTRIES_PER_ROUND = 2   # Prevents hallucination flood (port from JiuwenClaw)
_MAX_LINE_GROWTH_PCT = 20  # K3 surgical-changes: reject diffs exceeding this % of baseline

# ── Prompt Template ───────────────────────────────────────────────────────────

_GENERATE_PROMPT = """\
You are a skill evolution engine for BidDeed.AI's AUTOLOOP V2.
Your job is to generate a patch for a SKILL.md file based on detected signals.

## SKILL NAME
{skill_name}

## CURRENT SKILL.md CONTENT
{skill_md_content}

## DETECTED SIGNALS
{signals_json}

## SCORE CONTEXT
{score_context}

## SENTINEL CONTEXT
{sentinel_context}

## TASK
Generate up to {max_entries} improvement entries for this SKILL.md.
Each entry should fix a concrete failure mode detected in the signals above.

Return ONLY valid JSON (no markdown, no explanation):
{{
  "entries": [
    {{
      "section": "<one of: Instructions, Examples, Troubleshooting, EdgeCases>",
      "action": "<add|update>",
      "content": "<the patch text to inject into that section>",
      "reason": "<1 sentence why this fixes the signal>"
    }}
  ]
}}

Rules:
- Max {max_entries} entries
- section MUST be one of: Instructions, Examples, Troubleshooting, EdgeCases
- content must be concrete and actionable, not generic advice
- Do NOT rewrite the entire SKILL.md — target the specific failure
- If signals are noise, return {{"entries": []}}
"""

_RCA_PROMPT = """\
You are a root cause analyzer for AI skill failures.
Given this failure signal, identify the root cause in one sentence.

Signal type: {signal_type}
Excerpt: {excerpt}

Return JSON: {{"root_cause": "...", "confidence": 0.0-1.0, "is_skill_related": true/false}}
"""


class Evolver:
    """
    Generates SKILL.md patches from evolution signals using a multi-LLM Smart Router.

    Usage:
        evolver = Evolver(skill_name="zonewise-scraper")
        entries = evolver.generate(signals, skill_md_path=".claude/skills/zonewise-scraper/SKILL.md")
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
        self._gemini_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self._deepseek_key = deepseek_api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self._anthropic_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.max_entries = max(1, min(max_entries, _MAX_ENTRIES_PER_ROUND))
        self._total_token_cost: float = 0.0

    @property
    def total_token_cost(self) -> float:
        return self._total_token_cost

    def generate(
        self,
        signals: list[EvolutionSignal],
        skill_md_path: Optional[str] = None,
        eval_score_before: Optional[float] = None,
        eval_score_after: Optional[float] = None,
    ) -> list[EvolutionEntry]:
        """
        Generate SKILL.md patch entries from detected signals.

        1. RCA via Gemini Flash (FREE) — filter non-skill-related signals
        2. Patch generation via DeepSeek V3.2 ($0.28/1M)
        3. Fallback to Claude Sonnet if DeepSeek fails
        """
        if not signals:
            return []

        skill_md_content = self._read_skill_md(skill_md_path)
        score_context = self._format_score_context(eval_score_before, eval_score_after)
        sentinel_context = self._format_sentinel_context(signals)

        # Step 1: RCA filter via Gemini Flash
        relevant_signals = self._rca_filter(signals)
        if not relevant_signals:
            return []

        # Step 2: Patch generation via DeepSeek V3.2
        entries = self._generate_with_deepseek(
            relevant_signals, skill_md_content, score_context, sentinel_context,
            eval_score_before=eval_score_before,
        )

        # Step 3: Claude Sonnet fallback if DeepSeek returned nothing useful
        if not entries and self._anthropic_key:
            entries = self._generate_with_claude(
                relevant_signals, skill_md_content, score_context, sentinel_context,
                eval_score_before=eval_score_before,
            )


        # K3 Surgical-changes guardrail (Karpathy discipline, adopted 2026-04-12)
        entries = self._surgical_filter(entries, skill_md_content)
        return entries[:self.max_entries]

    # ── Private: RCA Filter ───────────────────────────────────────────────────

    def _rca_filter(self, signals: list[EvolutionSignal]) -> list[EvolutionSignal]:
        """Use Gemini Flash to filter out non-skill-related signals."""
        if not self._gemini_key:
            return signals  # Skip filter if no key

        relevant = []
        for signal in signals:
            try:
                result = self._call_gemini(
                    _RCA_PROMPT.format(
                        signal_type=signal.signal_type.value
                        if isinstance(signal.signal_type, SignalType) else signal.signal_type,
                        excerpt=signal.excerpt[:300],
                    )
                )
                parsed = self._parse_json(result)
                if parsed.get("is_skill_related", True):
                    relevant.append(signal)
            except Exception:
                relevant.append(signal)  # Include on error (conservative)

        return relevant

    # ── Private: DeepSeek Patch Generation ───────────────────────────────────

    def _generate_with_deepseek(
        self,
        signals: list[EvolutionSignal],
        skill_md_content: str,
        score_context: str,
        sentinel_context: str,
        eval_score_before: Optional[float] = None,
    ) -> list[EvolutionEntry]:
        if not self._deepseek_key:
            return []

        prompt = self._build_prompt(
            signals, skill_md_content, score_context, sentinel_context
        )
        try:
            import httpx
            t0 = time.time()
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
            # DeepSeek V3.2 pricing: $0.28/1M tokens
            tokens = usage.get("total_tokens", 0)
            cost = tokens * 0.00000028
            self._total_token_cost += cost

            return self._parse_entries(
                content,
                signals=signals,
                model=_DEEPSEEK_MODEL,
                token_cost=cost,
                eval_score_before=eval_score_before,
            )
        except Exception:
            return []

    # ── Private: Claude Sonnet Fallback ──────────────────────────────────────

    def _generate_with_claude(
        self,
        signals: list[EvolutionSignal],
        skill_md_content: str,
        score_context: str,
        sentinel_context: str,
        eval_score_before: Optional[float] = None,
    ) -> list[EvolutionEntry]:
        if not self._anthropic_key:
            return []

        prompt = self._build_prompt(
            signals, skill_md_content, score_context, sentinel_context
        )
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
            # Sonnet pricing: ~$3/1M input, $15/1M output
            in_tokens = usage.get("input_tokens", 0)
            out_tokens = usage.get("output_tokens", 0)
            cost = (in_tokens * 0.000003) + (out_tokens * 0.000015)
            self._total_token_cost += cost

            return self._parse_entries(
                content,
                signals=signals,
                model=_CLAUDE_MODEL,
                token_cost=cost,
                eval_score_before=eval_score_before,
            )
        except Exception:
            return []

    # ── Private: Gemini Flash Call ────────────────────────────────────────────

    def _call_gemini(self, prompt: str) -> str:
        try:
            import httpx
            resp = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{_GEMINI_MODEL}:generateContent",
                params={"key": self._gemini_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 256},
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return "{}"

    # ── Private: Helpers ──────────────────────────────────────────────────────

    def _build_prompt(
        self,
        signals: list[EvolutionSignal],
        skill_md_content: str,
        score_context: str,
        sentinel_context: str,
    ) -> str:
        signals_json = json.dumps(
            [
                {
                    "type": s.signal_type.value if isinstance(s.signal_type, SignalType) else s.signal_type,
                    "excerpt": s.excerpt,
                    "source": s.source,
                }
                for s in signals
            ],
            indent=2,
        )
        return _GENERATE_PROMPT.format(
            skill_name=self.skill_name,
            skill_md_content=skill_md_content[:3000],  # Cap to ~3K chars
            signals_json=signals_json,
            score_context=score_context,
            sentinel_context=sentinel_context,
            max_entries=self.max_entries,
        )

    def _surgical_filter(
        self,
        entries: list[EvolutionEntry],
        baseline_content: str,
    ) -> list[EvolutionEntry]:
        """
        K3 surgical-changes guardrail — reject patch entries whose combined
        content would grow the baseline SKILL.md by more than
        _MAX_LINE_GROWTH_PCT. Adopted from forrestchang/andrej-karpathy-skills
        (MIT, 2026-04-12). Closes AUTOLOOP V2 bloat failure mode flagged
        independently by Dylan Cleppe and Karpathy.
        """
        if not entries:
            return entries
        baseline_lines = max(1, len(baseline_content.splitlines()))
        max_added = max(1, (baseline_lines * _MAX_LINE_GROWTH_PCT) // 100)

        kept: list[EvolutionEntry] = []
        running_added = 0
        for entry in entries:
            entry_lines = len(entry.content.splitlines()) or 1
            if running_added + entry_lines > max_added:
                continue  # over budget, skip but keep evaluating
            running_added += entry_lines
            kept.append(entry)
        return kept

    def _parse_entries(
        self,
        llm_output: str,
        signals: list[EvolutionSignal],
        model: str,
        token_cost: float,
        eval_score_before: Optional[float] = None,
    ) -> list[EvolutionEntry]:
        """Parse LLM JSON response with robust regex fallback (ported from JiuwenClaw)."""
        parsed = self._parse_json(llm_output)
        raw_entries = parsed.get("entries", [])

        result = []
        first_signal_id = signals[0].id if signals else None

        for raw in raw_entries[:self.max_entries]:
            section = raw.get("section", "Instructions")
            if section not in VALID_SECTIONS:
                section = "Instructions"
            action_str = raw.get("action", "add")
            try:
                action = EntryAction(action_str)
            except ValueError:
                action = EntryAction.ADD

            content = str(raw.get("content", "")).strip()
            if not content:
                continue

            entry = EvolutionEntry(
                skill_name=self.skill_name,
                target=self.skill_name,
                section=section,
                content=content,
                action=action,
                source_signal_id=first_signal_id,
                llm_model_used=model,
                token_cost=token_cost / max(1, len(raw_entries)),
                eval_score_before=eval_score_before,
            )
            result.append(entry)

        return result

    def _parse_json(self, text: str) -> dict:
        """Robust JSON parser: tries direct parse, then regex extraction."""
        text = text.strip()
        # Try direct parse
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass
        # Regex: find first {...} block
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except (json.JSONDecodeError, ValueError):
                pass
        return {}

    def _read_skill_md(self, skill_md_path: Optional[str]) -> str:
        if not skill_md_path:
            # Try standard paths
            for candidate in [
                f".claude/skills/{self.skill_name}/SKILL.md",
                f"{self.skill_name}/SKILL.md",
            ]:
                if os.path.exists(candidate):
                    skill_md_path = candidate
                    break
        if skill_md_path and os.path.exists(skill_md_path):
            try:
                return open(skill_md_path).read()
            except OSError:
                pass
        return "(SKILL.md not found)"

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

    def _format_sentinel_context(self, signals: list[EvolutionSignal]) -> str:
        sentinel_signals = [
            s for s in signals
            if (s.signal_type == SignalType.SENTINEL_ALERT
                or s.signal_type == "sentinel_alert")
        ]
        if not sentinel_signals:
            return "No Sentinel alerts."
        return "Sentinel alerts detected:\n" + "\n".join(
            f"  - {s.excerpt}" for s in sentinel_signals
        )
