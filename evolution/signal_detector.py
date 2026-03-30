# evolution/signal_detector.py
# Inspired by openJiuwen-ai/jiuwenclaw (Apache 2.0)
# AUTOLOOP V2 — Hybrid regex+LLM Signal Detection
# Issue: breverdbidder/cli-anything-biddeed#67

"""
SignalDetector — detects skill evolution signals from session logs and eval output.

BEATS JiuwenClaw:
  - Regex + LLM hybrid classification (they use regex-only)
  - score_regression signal type (new)
  - sentinel_alert signal type (new)
  - Supabase dedup by fingerprint (they do in-memory only)
  - Tracks active skill via SKILL.md file reads in tool calls
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Optional

from .schema import EvolutionSignal, SignalType

# ── Regex Patterns (ported + extended from JiuwenClaw) ───────────────────────

_EXECUTION_FAILURE_PATTERNS = [
    re.compile(r'\bTraceback\b.*\bError\b', re.DOTALL | re.IGNORECASE),
    re.compile(r'\b(Error|Exception|FAILED|failed|timeout|timed out)\b', re.IGNORECASE),
    re.compile(r'\bPermission denied\b', re.IGNORECASE),
    re.compile(r'\bNo such file or directory\b', re.IGNORECASE),
    re.compile(r'\bCommand not found\b', re.IGNORECASE),
    re.compile(r'\bAssertionError\b', re.IGNORECASE),
    re.compile(r'\bKeyError\b|\bValueError\b|\bTypeError\b|\bAttributeError\b', re.IGNORECASE),
    re.compile(r'\bExited with (code|status) [^0]\b', re.IGNORECASE),
    re.compile(r'\bstack trace\b', re.IGNORECASE),
]

_USER_CORRECTION_PATTERNS = [
    re.compile(r"that'?s wrong", re.IGNORECASE),
    re.compile(r'\bshould be\b', re.IGNORECASE),
    re.compile(r'\bactually[,\s]', re.IGNORECASE),
    re.compile(r'\bno[,\s]+wait\b', re.IGNORECASE),
    re.compile(r'\bincorrect\b', re.IGNORECASE),
    re.compile(r'\byou missed\b', re.IGNORECASE),
    re.compile(r'\bthat is not right\b', re.IGNORECASE),
    re.compile(r'\bwrong\b.*\bshould\b', re.IGNORECASE),
    re.compile(r'\bfix\b.*\bmistake\b', re.IGNORECASE),
    re.compile(r"\bdon['\u2019]t do that\b", re.IGNORECASE),
    re.compile(r'\bstop doing\b', re.IGNORECASE),
    re.compile(r'\byou need to\b', re.IGNORECASE),
]

_SENTINEL_ALERT_PATTERNS = [
    re.compile(r'\bsentinel\b.*\b(alert|fail|warn|error)\b', re.IGNORECASE),
    re.compile(r'\bhealth[_ ]check\b.*\bfailed\b', re.IGNORECASE),
    re.compile(r'\binfra(structure)?\b.*\b(down|fail|unreachable)\b', re.IGNORECASE),
    re.compile(r'\bskill[_ ]related\b.*\bfailure\b', re.IGNORECASE),
]

# Skills-related keywords to filter sentinel alerts
_SKILL_RELATED_KEYWORDS = [
    'skill', 'harness', 'eval', 'autoloop', 'prompt', 'SKILL.md', 'claude',
]


class SignalDetector:
    """
    Detects evolution signals from session logs and eval output.

    Usage:
        detector = SignalDetector(skill_name="zonewise-scraper")
        signals = detector.detect(session_log_text)
        score_signals = detector.detect_score_regression(score_before=0.72, score_after=0.64)
    """

    def __init__(
        self,
        skill_name: Optional[str] = None,
        use_llm: bool = True,
        llm_threshold: float = 0.5,
        deepseek_api_key: Optional[str] = None,
        existing_fingerprints: Optional[set] = None,
    ):
        self.skill_name = skill_name or "unknown"
        self.use_llm = use_llm
        self.llm_threshold = llm_threshold
        self._deepseek_api_key = deepseek_api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self._existing_fingerprints: set[str] = existing_fingerprints or set()

    # ── Public API ────────────────────────────────────────────────────────────

    def detect(self, text: str, source: str = "session_log") -> list[EvolutionSignal]:
        """
        Detect evolution signals in a text blob (session log, eval output, etc.).
        Returns deduplicated list of EvolutionSignal objects.
        """
        signals: list[EvolutionSignal] = []
        lines = text.splitlines()

        for i, line in enumerate(lines):
            context = "\n".join(lines[max(0, i - 2):i + 3])
            sig = self._classify_line(line, context, source)
            if sig and sig.fingerprint not in self._existing_fingerprints:
                signals.append(sig)
                self._existing_fingerprints.add(sig.fingerprint)

        # LLM fallback for ambiguous signals
        if self.use_llm and self._deepseek_api_key:
            signals = self._llm_reclassify_ambiguous(signals, text)

        return signals

    def detect_score_regression(
        self,
        score_before: float,
        score_after: float,
        skill_name: Optional[str] = None,
    ) -> Optional[EvolutionSignal]:
        """
        Detect a score_regression signal when eval score drops.
        Returns None if no regression (score_after >= score_before).
        """
        if score_after >= score_before:
            return None
        name = skill_name or self.skill_name
        drop = score_before - score_after
        excerpt = f"Score dropped from {score_before:.1%} to {score_after:.1%} (drop: {drop:.1%})"
        sig = EvolutionSignal(
            signal_type=SignalType.SCORE_REGRESSION,
            skill_name=name,
            excerpt=excerpt,
            source="eval_runner",
        )
        if sig.fingerprint in self._existing_fingerprints:
            return None
        self._existing_fingerprints.add(sig.fingerprint)
        return sig

    def detect_sentinel_alert(
        self,
        sentinel_log: str,
        skill_name: Optional[str] = None,
    ) -> list[EvolutionSignal]:
        """
        Detect sentinel_alert signals from Sentinel log output.
        Only returns signals that appear skill-related.
        """
        name = skill_name or self.skill_name
        signals = []
        for line in sentinel_log.splitlines():
            if not any(p.search(line) for p in _SENTINEL_ALERT_PATTERNS):
                continue
            # Filter: only include if skill-related keyword present in context
            if not any(kw.lower() in line.lower() for kw in _SKILL_RELATED_KEYWORDS):
                continue
            excerpt = line.strip()[:200]
            sig = EvolutionSignal(
                signal_type=SignalType.SENTINEL_ALERT,
                skill_name=name,
                excerpt=excerpt,
                source="sentinel",
            )
            if sig.fingerprint not in self._existing_fingerprints:
                signals.append(sig)
                self._existing_fingerprints.add(sig.fingerprint)
        return signals

    def detect_active_skill(self, tool_calls_text: str) -> Optional[str]:
        """
        Detect which skill is being modified by scanning tool call text
        for SKILL.md file reads. Ports JiuwenClaw's approach.
        """
        # Look for .claude/skills/<name>/SKILL.md or <name>/SKILL.md patterns
        patterns = [
            re.compile(r'\.claude/skills/([^/\s"\']+)/SKILL\.md'),
            re.compile(r'([^/\s"\']+)/SKILL\.md'),
        ]
        for pat in patterns:
            m = pat.search(tool_calls_text)
            if m:
                return m.group(1)
        return None

    def clear_conversation_signals(self):
        """Reset fingerprint dedup set at conversation boundaries."""
        self._existing_fingerprints.clear()

    # ── Private ───────────────────────────────────────────────────────────────

    def _classify_line(
        self, line: str, context: str, source: str
    ) -> Optional[EvolutionSignal]:
        """Classify a single line into a signal type using regex."""
        stripped = line.strip()
        if not stripped:
            return None

        excerpt = stripped[:200]

        if any(p.search(line) for p in _EXECUTION_FAILURE_PATTERNS):
            return EvolutionSignal(
                signal_type=SignalType.EXECUTION_FAILURE,
                skill_name=self.skill_name,
                excerpt=excerpt,
                source=source,
            )

        if any(p.search(line) for p in _USER_CORRECTION_PATTERNS):
            return EvolutionSignal(
                signal_type=SignalType.USER_CORRECTION,
                skill_name=self.skill_name,
                excerpt=excerpt,
                source=source,
            )

        return None

    def _llm_reclassify_ambiguous(
        self, signals: list[EvolutionSignal], full_text: str
    ) -> list[EvolutionSignal]:
        """
        Use DeepSeek V3.2 (ULTRA_CHEAP at $0.28/1M) to reclassify ambiguous signals.
        Only called when regex confidence is low (short excerpts, no clear pattern).
        """
        try:
            import httpx
        except ImportError:
            return signals

        ambiguous = [s for s in signals if len(s.excerpt) < 30]
        if not ambiguous:
            return signals

        prompt = (
            "You are a signal classifier for a skill evolution engine. "
            "Classify each excerpt as one of: execution_failure, user_correction, score_regression, sentinel_alert, or noise. "
            "Return JSON array: [{\"index\": 0, \"type\": \"...\", \"confidence\": 0.0}]\n\n"
            "Excerpts:\n"
            + "\n".join(f"{i}: {s.excerpt}" for i, s in enumerate(ambiguous))
        )

        try:
            resp = httpx.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._deepseek_api_key}"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 512,
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            # Robust JSON parse
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                classifications = json.loads(match.group())
                for item in classifications:
                    idx = item.get("index", -1)
                    confidence = item.get("confidence", 0.0)
                    sig_type = item.get("type", "noise")
                    if 0 <= idx < len(ambiguous) and confidence >= self.llm_threshold:
                        if sig_type == "noise":
                            # Remove low-confidence noise signals
                            signals = [s for s in signals if s is not ambiguous[idx]]
                        else:
                            try:
                                ambiguous[idx].signal_type = SignalType(sig_type)
                            except ValueError:
                                pass
        except Exception:
            pass  # LLM fallback failure is non-fatal

        return signals
