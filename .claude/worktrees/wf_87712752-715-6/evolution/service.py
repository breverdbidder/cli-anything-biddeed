# evolution/service.py
# Inspired by openJiuwen-ai/jiuwenclaw (Apache 2.0)
# AUTOLOOP V2 — Orchestrator: SUMMIT + Sentinel + Nexus Integration
# Issue: breverdbidder/cli-anything-biddeed#67

"""
EvolutionService — orchestrates the full skill evolution lifecycle.

BEATS JiuwenClaw:
  - SUMMIT dispatch on repeated failures (auto-create issue for human review)
  - Sentinel integration (wired into sentinel.yml failures)
  - Telegram notifications via Nexus
  - /evolve and /solidify command support
  - Batch hook wired into eval_runner.py
  - CC session post-processing hook
  - clear_processed_signals() at conversation boundaries
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from typing import Optional

from .evolver import Evolver
from .schema import EvolutionEntry, EvolutionSignal, SignalType
from .signal_detector import SignalDetector
from .store import EvolutionStore


class EvolutionService:
    """
    Orchestrates: detect → deduplicate → RCA → generate → approve → persist → notify.

    Usage:
        svc = EvolutionService(skill_name="zonewise-scraper")

        # After eval score drops:
        result = svc.on_eval_score_drop(score_before=0.72, score_after=0.64)

        # After session log available:
        result = svc.on_session_log(log_text)

        # Manual trigger:
        result = svc.evolve()

        # Solidify pending patches into SKILL.md:
        count = svc.solidify()
    """

    _MAX_ATTEMPTS_BEFORE_SUMMIT = 3   # After 3 failed attempts → open SUMMIT issue

    def __init__(
        self,
        skill_name: str,
        skill_md_path: Optional[str] = None,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        deepseek_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        github_token: Optional[str] = None,
        github_repo: Optional[str] = None,
        dry_run: bool = False,
    ):
        self.skill_name = skill_name
        self._skill_md_path = skill_md_path or self._resolve_skill_md(skill_name)
        self._dry_run = dry_run
        self._telegram_token = telegram_bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._telegram_chat_id = telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self._github_token = github_token or os.getenv("GH_TOKEN", "")
        self._github_repo = github_repo or os.getenv("GITHUB_REPO", "breverdbidder/cli-anything-biddeed")

        self._store = EvolutionStore(
            skill_name=skill_name,
            supabase_url=supabase_url,
            supabase_key=supabase_key,
        )
        existing_fps = self._store.get_existing_fingerprints()
        self._detector = SignalDetector(
            skill_name=skill_name,
            deepseek_api_key=deepseek_api_key,
            existing_fingerprints=existing_fps,
        )
        self._evolver = Evolver(
            skill_name=skill_name,
            gemini_api_key=gemini_api_key,
            deepseek_api_key=deepseek_api_key,
            anthropic_api_key=anthropic_api_key,
        )
        self._failed_attempt_count: int = 0

    # ── Public Hooks ──────────────────────────────────────────────────────────

    def on_eval_score_drop(
        self,
        score_before: float,
        score_after: float,
        session_log: Optional[str] = None,
    ) -> dict:
        """
        Called by eval_runner.py when score drops instead of blind revert.
        Returns dict with: signals, entries, applied, score_after.
        """
        signals = []

        # Score regression signal
        reg_signal = self._detector.detect_score_regression(score_before, score_after)
        if reg_signal:
            signals.append(reg_signal)
            self._store.save_signal(reg_signal)

        # Also scan session log if provided
        if session_log:
            log_signals = self._detector.detect(session_log, source="session_log")
            for s in log_signals:
                self._store.save_signal(s)
            signals.extend(log_signals)

        if not signals:
            return {"signals": 0, "entries": 0, "applied": 0}

        entries = self._evolver.generate(
            signals,
            skill_md_path=self._skill_md_path,
            eval_score_before=score_before,
            eval_score_after=score_after,
        )

        if not entries:
            self._failed_attempt_count += 1
            if self._failed_attempt_count >= self._MAX_ATTEMPTS_BEFORE_SUMMIT:
                self._dispatch_summit_issue(signals, score_before, score_after)
            return {"signals": len(signals), "entries": 0, "applied": 0}

        applied = 0
        for entry in entries:
            entry.eval_score_before = score_before
            self._store.save_entry(entry)

        # Solidify: inject into SKILL.md
        if not self._dry_run:
            applied = self._store.solidify(
                self._skill_md_path, dry_run=self._dry_run
            )

        report = self._store.format_evolution_report(
            signals, entries,
            eval_score_before=score_before,
        )
        self._send_telegram(report)

        return {
            "signals": len(signals),
            "entries": len(entries),
            "applied": applied,
            "report": report,
        }

    def on_session_log(self, log_text: str) -> dict:
        """
        Called after a CC session completes. Detects signals in session log.
        """
        signals = self._detector.detect(log_text, source="session_log")
        if not signals:
            return {"signals": 0, "entries": 0}

        for s in signals:
            self._store.save_signal(s)

        entries = self._evolver.generate(signals, skill_md_path=self._skill_md_path)
        for entry in entries:
            self._store.save_entry(entry)

        return {"signals": len(signals), "entries": len(entries)}

    def on_sentinel_alert(self, sentinel_log: str) -> dict:
        """
        Called when Sentinel detects infra failure. Checks if skill-related.
        """
        signals = self._detector.detect_sentinel_alert(sentinel_log, self.skill_name)
        if not signals:
            return {"signals": 0, "entries": 0}

        for s in signals:
            self._store.save_signal(s)

        entries = self._evolver.generate(signals, skill_md_path=self._skill_md_path)
        for entry in entries:
            self._store.save_entry(entry)

        return {"signals": len(signals), "entries": len(entries)}

    # ── Commands ──────────────────────────────────────────────────────────────

    def evolve(self, session_log: Optional[str] = None) -> dict:
        """/evolve command: manual trigger of the evolution pipeline."""
        if session_log:
            return self.on_session_log(session_log)
        # Read latest autoloop session log if available
        log_text = self._read_latest_session_log()
        if log_text:
            return self.on_session_log(log_text)
        return {"signals": 0, "entries": 0, "note": "No session log found"}

    def solidify(self, eval_score_after: Optional[float] = None) -> int:
        """/solidify command: merge pending entries into SKILL.md."""
        count = self._store.solidify(
            self._skill_md_path,
            eval_score_after=eval_score_after,
            dry_run=self._dry_run,
        )
        if count > 0 and not self._dry_run:
            self._git_commit_skill_md(count)
        return count

    def clear_processed_signals(self):
        """Reset dedup state at conversation boundaries."""
        self._detector.clear_conversation_signals()

    # ── SUMMIT Dispatch ───────────────────────────────────────────────────────

    def _dispatch_summit_issue(
        self,
        signals: list[EvolutionSignal],
        score_before: float,
        score_after: float,
    ):
        """
        Auto-create a SUMMIT issue when evolution fails 3+ times.
        NEW: JiuwenClaw has no auto-escalation.
        """
        if not self._github_token:
            return
        title = f"P1 SUMMIT: {self.skill_name} evolution failing ({self._failed_attempt_count}x)"
        sig_summary = "\n".join(f"- [{s.signal_type}] {s.excerpt[:80]}" for s in signals[:5])
        body = (
            f"## Auto-escalation from AUTOLOOP V2\n\n"
            f"Skill `{self.skill_name}` has failed to improve after "
            f"{self._failed_attempt_count} evolution attempts.\n\n"
            f"**Score:** {score_before:.1%} → {score_after:.1%}\n\n"
            f"**Signals detected:**\n{sig_summary}\n\n"
            f"**Next step:** Human review required. "
            f"Check `.claude/skills/{self.skill_name}/evolutions.json` for pending entries.\n\n"
            f"Auto-generated by AUTOLOOP V2 on {datetime.utcnow().isoformat()}"
        )
        try:
            import httpx
            httpx.post(
                f"https://api.github.com/repos/{self._github_repo}/issues",
                headers={
                    "Authorization": f"token {self._github_token}",
                    "Accept": "application/vnd.github+json",
                },
                json={"title": title, "body": body, "labels": ["p1", "summit", "autoloop-v2"]},
                timeout=15.0,
            )
        except Exception:
            pass

    # ── Telegram ──────────────────────────────────────────────────────────────

    def _send_telegram(self, message: str):
        """Send evolution report to Telegram via Nexus."""
        if not self._telegram_token or not self._telegram_chat_id:
            return
        try:
            import httpx
            httpx.post(
                f"https://api.telegram.org/bot{self._telegram_token}/sendMessage",
                data={
                    "chat_id": self._telegram_chat_id,
                    "text": message[:4096],
                    "parse_mode": "HTML",
                },
                timeout=10.0,
            )
        except Exception:
            pass

    # ── Git ───────────────────────────────────────────────────────────────────

    def _git_commit_skill_md(self, entry_count: int):
        """Commit solidified SKILL.md changes."""
        try:
            subprocess.run(
                ["git", "add", self._skill_md_path],
                capture_output=True, check=True
            )
            subprocess.run(
                [
                    "git", "commit", "-m",
                    f"evolution({self.skill_name}): solidify {entry_count} patches"
                ],
                capture_output=True, check=True
            )
            subprocess.run(
                ["git", "push", "origin", "main"],
                capture_output=True, check=True
            )
        except subprocess.CalledProcessError:
            pass

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _read_latest_session_log(self) -> Optional[str]:
        """Find and read the latest autoloop session log for this skill."""
        import glob
        patterns = [
            f".claude/skills/{self.skill_name}/eval_outputs/autoloop_session_*.log",
            f"{self.skill_name}/eval_outputs/autoloop_session_*.log",
            f"{self.skill_name}/eval/autoloop_session_*.log",
        ]
        for pattern in patterns:
            files = sorted(glob.glob(pattern), reverse=True)
            if files:
                try:
                    return open(files[0]).read()
                except OSError:
                    pass
        return None

    @staticmethod
    def _resolve_skill_md(skill_name: str) -> str:
        candidates = [
            f".claude/skills/{skill_name}/SKILL.md",
            f"skills/{skill_name}/SKILL.md",
            f"{skill_name}/SKILL.md",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return f".claude/skills/{skill_name}/SKILL.md"
