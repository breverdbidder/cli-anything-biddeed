# evolution/store.py
# Inspired by openJiuwen-ai/jiuwenclaw (Apache 2.0)
# AUTOLOOP V2 — Dual Persistence: Supabase + Local Sidecar
# Issue: breverdbidder/cli-anything-biddeed#67

"""
EvolutionStore — persists evolution signals and entries.

BEATS JiuwenClaw:
  - DUAL persistence: Supabase (SSOT) + local sidecar evolutions.json (cache)
  - format_evolution_report() for Telegram digests (they don't have)
  - solidify() patches SKILL.md and updates eval_score_after (they don't track score)
  - _inject_section() regex ported from JiuwenClaw with our SKILL.md structure
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .schema import EntryAction, EvolutionEntry, EvolutionFile, EvolutionSignal


class EvolutionStore:
    """
    Handles persistence for evolution signals and entries.

    Usage:
        store = EvolutionStore(skill_name="zonewise-scraper", supabase_url=..., supabase_key=...)
        store.save_signal(signal)
        store.save_entry(entry)
        store.solidify(".claude/skills/zonewise-scraper/SKILL.md")
    """

    SIDECAR_FILENAME = "evolutions.json"

    def __init__(
        self,
        skill_name: str,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        skill_dir: Optional[str] = None,
    ):
        self.skill_name = skill_name
        self._supabase_url = supabase_url or os.getenv("SUPABASE_URL", "")
        self._supabase_key = supabase_key or os.getenv("SUPABASE_KEY", "")
        self._skill_dir = skill_dir or self._resolve_skill_dir(skill_name)
        self._sidecar_path = Path(self._skill_dir) / self.SIDECAR_FILENAME

    # ── Signals ───────────────────────────────────────────────────────────────

    def save_signal(self, signal: EvolutionSignal) -> Optional[str]:
        """Persist signal to Supabase. Returns signal ID or None on failure."""
        if not self._supabase_url or not self._supabase_key:
            return None
        try:
            import httpx
            resp = httpx.post(
                f"{self._supabase_url}/rest/v1/skill_evolution_signals",
                headers=self._headers(prefer="return=representation"),
                json=signal.to_dict(),
                timeout=10.0,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                if data and isinstance(data, list):
                    signal.id = data[0].get("id")
                    return signal.id
        except Exception:
            pass
        return None

    def get_existing_fingerprints(self) -> set[str]:
        """Load fingerprints of already-processed signals to avoid duplicates."""
        if not self._supabase_url or not self._supabase_key:
            return self._load_sidecar_fingerprints()
        try:
            import httpx
            resp = httpx.get(
                f"{self._supabase_url}/rest/v1/skill_evolution_signals",
                headers=self._headers(),
                params={
                    "select": "fingerprint",
                    "skill_name": f"eq.{self.skill_name}",
                    "limit": "1000",
                },
                timeout=10.0,
            )
            if resp.status_code == 200:
                return {r["fingerprint"] for r in resp.json()}
        except Exception:
            pass
        return self._load_sidecar_fingerprints()

    def mark_signal_processed(self, signal_id: str) -> bool:
        if not self._supabase_url or not self._supabase_key or not signal_id:
            return False
        try:
            import httpx
            resp = httpx.patch(
                f"{self._supabase_url}/rest/v1/skill_evolution_signals",
                headers=self._headers(),
                params={"id": f"eq.{signal_id}"},
                json={"processed": True},
                timeout=10.0,
            )
            return resp.status_code in (200, 204)
        except Exception:
            return False

    # ── Entries ───────────────────────────────────────────────────────────────

    def save_entry(self, entry: EvolutionEntry) -> Optional[str]:
        """Persist entry to Supabase and update local sidecar."""
        entry_id = self._save_entry_supabase(entry)
        self._update_sidecar(entry, status="pending")
        return entry_id

    def update_entry_score(
        self, entry_id: str, eval_score_after: float, applied: bool = True
    ) -> bool:
        """Update eval_score_after once re-eval completes."""
        if not self._supabase_url or not self._supabase_key or not entry_id:
            return False
        try:
            import httpx
            resp = httpx.patch(
                f"{self._supabase_url}/rest/v1/skill_evolution_entries",
                headers=self._headers(),
                params={"id": f"eq.{entry_id}"},
                json={"eval_score_after": eval_score_after, "applied": applied},
                timeout=10.0,
            )
            return resp.status_code in (200, 204)
        except Exception:
            return False

    def get_pending_entries(self) -> list[dict]:
        """Get unapplied entries for this skill."""
        if self._supabase_url and self._supabase_key:
            try:
                import httpx
                resp = httpx.get(
                    f"{self._supabase_url}/rest/v1/skill_evolution_entries",
                    headers=self._headers(),
                    params={
                        "skill_name": f"eq.{self.skill_name}",
                        "applied": "eq.false",
                        "select": "*",
                        "limit": "50",
                    },
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
        # Fallback to sidecar
        evo_file = self._load_sidecar()
        return [e.to_dict() for e in evo_file.pending]

    # ── Solidify: pending → SKILL.md ──────────────────────────────────────────

    def solidify(
        self,
        skill_md_path: str,
        eval_score_after: Optional[float] = None,
        dry_run: bool = False,
    ) -> int:
        """
        Inject all pending entries into SKILL.md sections.
        Returns number of entries applied.
        Ports JiuwenClaw's solidify() with our SKILL.md structure.
        """
        pending = self.get_pending_entries()
        if not pending:
            return 0

        if not os.path.exists(skill_md_path):
            return 0

        with open(skill_md_path) as f:
            content = f.read()

        applied_count = 0
        for raw_entry in pending:
            section = raw_entry.get("section", "Instructions")
            patch_text = raw_entry.get("content", "").strip()
            action = raw_entry.get("action", "add")

            if not patch_text or action == "skip":
                continue

            new_content = self._inject_section(content, section, patch_text)
            if new_content != content:
                content = new_content
                applied_count += 1

        if applied_count > 0 and not dry_run:
            with open(skill_md_path, "w") as f:
                f.write(content)
            # Update sidecar: pending → applied
            self._move_pending_to_applied()
            # Update Supabase score if provided
            if eval_score_after is not None:
                self._bulk_update_applied_scores(eval_score_after)

        return applied_count

    # ── Report ────────────────────────────────────────────────────────────────

    def format_evolution_report(
        self,
        signals: list[EvolutionSignal],
        entries: list[EvolutionEntry],
        eval_score_before: Optional[float] = None,
        eval_score_after: Optional[float] = None,
    ) -> str:
        """
        Format a Telegram-friendly evolution summary.
        NEW: JiuwenClaw has no notification system.
        """
        lines = [
            f"🧬 AUTOLOOP V2 Evolution Report",
            f"Skill: {self.skill_name}",
            f"Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            "",
        ]

        # Score delta
        if eval_score_before is not None and eval_score_after is not None:
            delta = eval_score_after - eval_score_before
            direction = "📈" if delta >= 0 else "📉"
            lines.append(f"{direction} Score: {eval_score_before:.1%} → {eval_score_after:.1%} ({delta:+.1%})")
        elif eval_score_before is not None:
            lines.append(f"📊 Baseline: {eval_score_before:.1%}")

        # Signal summary
        from collections import Counter
        sig_counts = Counter(
            (s.signal_type.value if hasattr(s.signal_type, "value") else s.signal_type)
            for s in signals
        )
        if sig_counts:
            lines.append(f"\n🔍 Signals ({len(signals)} total):")
            for sig_type, count in sig_counts.items():
                lines.append(f"  • {sig_type}: {count}")

        # Entry summary
        if entries:
            lines.append(f"\n✏️ Patches generated ({len(entries)}):")
            for e in entries:
                lines.append(f"  • [{e.section}] {e.content[:80]}...")
                if e.llm_model_used:
                    lines.append(f"    via {e.llm_model_used} (cost: ${e.token_cost:.5f})")

        total_cost = sum(e.token_cost or 0 for e in entries)
        if total_cost > 0:
            lines.append(f"\n💰 Total LLM cost: ${total_cost:.5f}")

        return "\n".join(lines)

    # ── Sidecar ───────────────────────────────────────────────────────────────

    def _update_sidecar(self, entry: EvolutionEntry, status: str = "pending"):
        evo_file = self._load_sidecar()
        if status == "pending":
            evo_file.pending.append(entry)
        elif status == "applied":
            evo_file.applied.append(entry)
        elif status == "skipped":
            evo_file.skipped.append(entry)
        evo_file.last_updated = datetime.utcnow().isoformat()
        self._save_sidecar(evo_file)

    def _load_sidecar(self) -> EvolutionFile:
        if self._sidecar_path.exists():
            try:
                data = json.loads(self._sidecar_path.read_text())
                evo = EvolutionFile(skill_name=self.skill_name)
                evo.last_updated = data.get("last_updated")
                for raw in data.get("pending", []):
                    evo.pending.append(self._raw_to_entry(raw))
                for raw in data.get("applied", []):
                    evo.applied.append(self._raw_to_entry(raw))
                for raw in data.get("skipped", []):
                    evo.skipped.append(self._raw_to_entry(raw))
                return evo
            except Exception:
                pass
        return EvolutionFile(skill_name=self.skill_name)

    def _save_sidecar(self, evo_file: EvolutionFile):
        try:
            Path(self._skill_dir).mkdir(parents=True, exist_ok=True)
            self._sidecar_path.write_text(json.dumps(evo_file.to_dict(), indent=2))
        except Exception:
            pass

    def _load_sidecar_fingerprints(self) -> set[str]:
        evo_file = self._load_sidecar()
        fps = set()
        for entries in [evo_file.pending, evo_file.applied, evo_file.skipped]:
            for e in entries:
                if e.id:
                    fps.add(e.id)
        return fps

    def _move_pending_to_applied(self):
        evo_file = self._load_sidecar()
        evo_file.applied.extend(evo_file.pending)
        evo_file.pending = []
        evo_file.last_updated = datetime.utcnow().isoformat()
        self._save_sidecar(evo_file)

    # ── Section Injection (ported from JiuwenClaw) ────────────────────────────

    def _inject_section(self, content: str, section: str, patch_text: str) -> str:
        """
        Find ## {section} header in SKILL.md and append patch_text.
        Ports JiuwenClaw's _inject_section() regex approach.
        """
        header_pattern = re.compile(
            rf'^(##\s+{re.escape(section)}\s*\n)(.*?)(?=^##\s|\Z)',
            re.MULTILINE | re.DOTALL,
        )
        match = header_pattern.search(content)
        if match:
            # Append after existing section content
            header = match.group(1)
            existing_body = match.group(2)
            separator = "\n" if not existing_body.endswith("\n") else ""
            new_body = existing_body + separator + patch_text + "\n"
            return content[:match.start()] + header + new_body + content[match.end():]
        else:
            # Section doesn't exist — append at end
            return content.rstrip() + f"\n\n## {section}\n{patch_text}\n"

    # ── Supabase Helpers ──────────────────────────────────────────────────────

    def _save_entry_supabase(self, entry: EvolutionEntry) -> Optional[str]:
        if not self._supabase_url or not self._supabase_key:
            return None
        try:
            import httpx
            resp = httpx.post(
                f"{self._supabase_url}/rest/v1/skill_evolution_entries",
                headers=self._headers(prefer="return=representation"),
                json=entry.to_dict(),
                timeout=10.0,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                if data and isinstance(data, list):
                    entry.id = data[0].get("id")
                    return entry.id
        except Exception:
            pass
        return None

    def _bulk_update_applied_scores(self, eval_score_after: float):
        if not self._supabase_url or not self._supabase_key:
            return
        try:
            import httpx
            httpx.patch(
                f"{self._supabase_url}/rest/v1/skill_evolution_entries",
                headers=self._headers(),
                params={
                    "skill_name": f"eq.{self.skill_name}",
                    "applied": "eq.false",
                },
                json={"eval_score_after": eval_score_after, "applied": True},
                timeout=10.0,
            )
        except Exception:
            pass

    def _headers(self, prefer: Optional[str] = None) -> dict:
        h = {
            "apikey": self._supabase_key,
            "Authorization": f"Bearer {self._supabase_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            h["Prefer"] = prefer
        return h

    @staticmethod
    def _resolve_skill_dir(skill_name: str) -> str:
        candidates = [
            f".claude/skills/{skill_name}",
            f"skills/{skill_name}",
            f"{skill_name}",
        ]
        for c in candidates:
            if os.path.isdir(c):
                return c
        return f".claude/skills/{skill_name}"

    @staticmethod
    def _raw_to_entry(raw: dict) -> EvolutionEntry:
        return EvolutionEntry(
            skill_name=raw.get("skill_name", "unknown"),
            target=raw.get("target", ""),
            section=raw.get("section", "Instructions"),
            content=raw.get("content", ""),
            action=EntryAction(raw.get("action", "add")),
            id=raw.get("id"),
            applied=raw.get("applied", False),
            eval_score_before=raw.get("eval_score_before"),
            eval_score_after=raw.get("eval_score_after"),
            llm_model_used=raw.get("llm_model_used"),
            token_cost=raw.get("token_cost"),
            created_at=raw.get("created_at"),
        )

    # ── Format helpers (ported from JiuwenClaw) ───────────────────────────────

    @staticmethod
    def format_desc_experience_text(entry: EvolutionEntry) -> str:
        return f"[{entry.section}] {entry.content[:100]}"

    @staticmethod
    def format_body_experience_text(entry: EvolutionEntry) -> str:
        return (
            f"Section: {entry.section}\n"
            f"Action: {entry.action.value if isinstance(entry.action, EntryAction) else entry.action}\n"
            f"Content:\n{entry.content}"
        )
