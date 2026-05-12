# evolution/jsonpath_schema.py
# AUTOLOOP V2 — Structured-config patch schema (parallel to markdown EvolutionEntry)
# Pattern source: Meir770ar/agentic-video-maker scripts/patch-plan.cjs (MIT, REPOEVAL REFERENCE_ONLY)
# Spec: docs/EVOLVER-JSONPATH.md
# Issue: TBD

"""
Schema for structured-config evolution patches.

While `EvolutionEntry` (schema.py) targets SKILL.md sections with markdown text
injection, `JsonPathEntry` targets arbitrary JSON/YAML config files with
dotted-path field mutations.

USE CASES (where SKILL.md text-injection is the wrong tool):
  - Per-county scraper config (ZoneWise: 67 counties × structured params)
  - Shapira Formula V4.0 ensemble weights (XGBoost/LightGBM/CatBoost coefficients)
  - Sentinel failure-pattern thresholds (11 patterns, tunable numerics)
  - LLM router T1/T2/T3 routing rules
  - Marketing OS Hub tenant config (8 tenants)

DESIGN PARALLEL TO EvolutionEntry:
  EvolutionEntry.section       → JsonPathEntry.field         (where to patch)
  EvolutionEntry.content       → JsonPathEntry.new_value     (what to set)
  EvolutionEntry.action        → JsonPathEntry.action        (add|update|delete|skip)
  EvolutionEntry.target        → JsonPathEntry.target        (config file path or table.row)
  VALID_SECTIONS whitelist     → WhitelistConfig.allowed_paths
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Pattern
import re


# ── Entry Action (re-import to avoid circular dep with schema.py) ─────────────

# Reuse EntryAction from schema.py to keep enum unified across both evolvers.
from .schema import EntryAction


# ── Whitelist Configuration ───────────────────────────────────────────────────
# Mirrors the AUTO_CREATE_ROOTS + path-existence-check pattern from patch-plan.cjs.

@dataclass
class WhitelistConfig:
    """
    Per-target whitelist of patchable fields with type expectations + default values.

    A target (e.g. "zonewise-county-config", "shapira-v4-weights", "sentinel-thresholds")
    registers a WhitelistConfig declaring which dotted paths can be patched. Paths NOT in
    the whitelist are skipped at apply time with reason="path not whitelisted".

    EXAMPLE:
        WhitelistConfig(
            target="sentinel-thresholds",
            allowed_paths={
                r"^thresholds\\.[a-z_]+$": dict(type="number", min=0, max=1000),
                r"^retry_max$":             dict(type="int", min=1, max=10),
            },
            auto_create_roots={"thresholds"},  # auto-materialize root if absent
        )

    The regex pattern is matched against the full dotted path. `auto_create_roots`
    is a set of top-level keys that may be created if absent (mirrors AUTO_CREATE_ROOTS
    behavior in patch-plan.cjs for text_style / audio_mix defaults).
    """
    target: str
    allowed_paths: dict[str, dict[str, Any]] = field(default_factory=dict)
    auto_create_roots: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        # Pre-compile regex patterns for hot-path matching.
        self._compiled: dict[Pattern[str], dict[str, Any]] = {
            re.compile(p): meta for p, meta in self.allowed_paths.items()
        }

    def match(self, dotted_path: str) -> Optional[dict[str, Any]]:
        """Return constraint metadata for the first matching pattern, or None."""
        for pat, meta in self._compiled.items():
            if pat.match(dotted_path):
                return meta
        return None

    def validate_value(self, dotted_path: str, value: Any) -> tuple[bool, str]:
        """
        Validate a value against the whitelist constraint for a given path.
        Returns (ok, reason_if_not_ok).
        """
        meta = self.match(dotted_path)
        if meta is None:
            return False, "path not whitelisted"

        expected_type = meta.get("type")
        if expected_type == "number" and not isinstance(value, (int, float)):
            return False, f"expected number, got {type(value).__name__}"
        if expected_type == "int" and not isinstance(value, int):
            return False, f"expected int, got {type(value).__name__}"
        if expected_type == "bool" and not isinstance(value, bool):
            return False, f"expected bool, got {type(value).__name__}"
        if expected_type == "string" and not isinstance(value, str):
            return False, f"expected string, got {type(value).__name__}"
        if expected_type == "enum":
            allowed = meta.get("values", [])
            if value not in allowed:
                return False, f"value {value!r} not in enum {allowed}"

        if isinstance(value, (int, float)):
            if "min" in meta and value < meta["min"]:
                return False, f"value {value} below min {meta['min']}"
            if "max" in meta and value > meta["max"]:
                return False, f"value {value} above max {meta['max']}"

        return True, ""


# ── JsonPathEntry Data Model ──────────────────────────────────────────────────

@dataclass
class JsonPathEntry:
    """
    A proposed structured-config patch.

    Maps to Supabase table: skill_evolution_jsonpath_entries (DDL below).

    PARALLEL TO EvolutionEntry but for JSON/YAML config files instead of SKILL.md prose.

    fingerprint is auto-generated from field + new_value if not provided, enabling
    idempotent INSERT ON CONFLICT DO NOTHING.
    """
    skill_name: str
    target: str                              # e.g. "sentinel-thresholds", "zonewise-county-config"
    field: str                               # e.g. "thresholds.alert_threshold", "counties[3].rate_limit"
    new_value: Any                           # int|float|bool|str — coerced from string at apply time
    action: EntryAction = EntryAction.UPDATE
    source_signal_id: Optional[str] = None
    skip_reason: Optional[str] = None
    merge_target: Optional[str] = None       # path to JSON config file
    applied: bool = False
    eval_score_before: Optional[float] = None
    eval_score_after: Optional[float] = None
    llm_model_used: Optional[str] = None
    token_cost: Optional[float] = None
    fingerprint: Optional[str] = None
    created_at: Optional[str] = None
    id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()
        if self.fingerprint is None:
            raw = f"{self.target}:{self.field}:{self.new_value!r}"
            self.fingerprint = hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "source_signal_id": self.source_signal_id,
            "target": self.target,
            "field": self.field,
            "new_value": self.new_value,
            "action": self.action.value if isinstance(self.action, EntryAction) else self.action,
            "skip_reason": self.skip_reason,
            "merge_target": self.merge_target,
            "applied": self.applied,
            "eval_score_before": self.eval_score_before,
            "eval_score_after": self.eval_score_after,
            "llm_model_used": self.llm_model_used,
            "token_cost": self.token_cost,
            "fingerprint": self.fingerprint,
            "created_at": self.created_at,
        }


# ── Supabase DDL (to be added to a future migration) ──────────────────────────

SQL_SKILL_EVOLUTION_JSONPATH_ENTRIES = """
CREATE TABLE IF NOT EXISTS skill_evolution_jsonpath_entries (
    id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    skill_name          TEXT NOT NULL,
    source_signal_id    UUID REFERENCES skill_evolution_signals(id),
    target              TEXT NOT NULL,
    field               TEXT NOT NULL,
    new_value           JSONB NOT NULL,                    -- preserves typed value
    action              TEXT NOT NULL DEFAULT 'update' CHECK (action IN ('add','update','delete','skip')),
    skip_reason         TEXT,
    merge_target        TEXT,
    applied             BOOLEAN DEFAULT FALSE,
    eval_score_before   FLOAT,
    eval_score_after    FLOAT,
    llm_model_used      TEXT,
    token_cost          FLOAT,
    fingerprint         TEXT NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_jsonpath_entries_skill  ON skill_evolution_jsonpath_entries(skill_name);
CREATE INDEX IF NOT EXISTS idx_jsonpath_entries_target ON skill_evolution_jsonpath_entries(target);
CREATE INDEX IF NOT EXISTS idx_jsonpath_entries_applied ON skill_evolution_jsonpath_entries(applied) WHERE applied = FALSE;
"""
