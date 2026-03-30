# evolution/schema.py
# Inspired by openJiuwen-ai/jiuwenclaw (Apache 2.0)
# AUTOLOOP V2 — Data Models with Supabase integration
# Issue: breverdbidder/cli-anything-biddeed#67

"""
Data models for the AUTOLOOP V2 evolution engine.

BEATS JiuwenClaw:
  - Supabase-native tables (vs their flat JSON)
  - eval_score_before/after tracking
  - sentinel_alert + score_regression signal types (they only have 2)
  - llm_model_used + token_cost per entry
  - VALID_SECTIONS includes EdgeCases (they only have 3)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ── Signal Types ──────────────────────────────────────────────────────────────

class SignalType(str, Enum):
    EXECUTION_FAILURE = "execution_failure"
    USER_CORRECTION = "user_correction"
    SCORE_REGRESSION = "score_regression"     # NEW: not in JiuwenClaw
    SENTINEL_ALERT = "sentinel_alert"          # NEW: not in JiuwenClaw


# ── Entry Actions ─────────────────────────────────────────────────────────────

class EntryAction(str, Enum):
    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"
    SKIP = "skip"


# ── Valid SKILL.md Sections ───────────────────────────────────────────────────
# BEATS JiuwenClaw: adds EdgeCases (they only have Instructions, Examples, Troubleshooting)

VALID_SECTIONS = [
    "Instructions",
    "Examples",
    "Troubleshooting",
    "EdgeCases",       # NEW vs JiuwenClaw
]


# ── Data Models ───────────────────────────────────────────────────────────────

@dataclass
class EvolutionSignal:
    """
    A detected signal that may warrant a SKILL.md evolution.

    Maps to Supabase table: skill_evolution_signals
    """
    signal_type: SignalType
    skill_name: str
    excerpt: str
    tool_name: Optional[str] = None
    source: str = "session_log"          # session_log | eval_runner | sentinel | manual
    fingerprint: Optional[str] = None
    created_at: Optional[str] = None
    processed: bool = False
    id: Optional[str] = None

    def __post_init__(self):
        if self.fingerprint is None:
            raw = f"{self.signal_type}:{self.excerpt[:100]}"
            self.fingerprint = hashlib.sha256(raw.encode()).hexdigest()[:16]
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        return {
            "signal_type": self.signal_type.value if isinstance(self.signal_type, SignalType) else self.signal_type,
            "skill_name": self.skill_name,
            "excerpt": self.excerpt,
            "tool_name": self.tool_name,
            "source": self.source,
            "fingerprint": self.fingerprint,
            "created_at": self.created_at,
            "processed": self.processed,
        }


@dataclass
class EvolutionEntry:
    """
    A proposed evolution patch for a SKILL.md section.

    Maps to Supabase table: skill_evolution_entries

    BEATS JiuwenClaw: adds eval_score_before, eval_score_after, llm_model_used, token_cost
    """
    skill_name: str
    target: str                              # e.g. "zonewise-scraper"
    section: str                             # must be in VALID_SECTIONS
    content: str                             # the patch text
    action: EntryAction = EntryAction.ADD
    source_signal_id: Optional[str] = None
    skip_reason: Optional[str] = None
    merge_target: Optional[str] = None       # path to SKILL.md
    applied: bool = False
    eval_score_before: Optional[float] = None   # NEW vs JiuwenClaw
    eval_score_after: Optional[float] = None    # NEW vs JiuwenClaw
    llm_model_used: Optional[str] = None        # NEW vs JiuwenClaw
    token_cost: Optional[float] = None          # NEW vs JiuwenClaw
    created_at: Optional[str] = None
    id: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()
        if self.section not in VALID_SECTIONS:
            # Default to Instructions rather than raising
            self.section = "Instructions"

    def to_dict(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "source_signal_id": self.source_signal_id,
            "target": self.target,
            "section": self.section,
            "content": self.content,
            "action": self.action.value if isinstance(self.action, EntryAction) else self.action,
            "skip_reason": self.skip_reason,
            "merge_target": self.merge_target,
            "applied": self.applied,
            "eval_score_before": self.eval_score_before,
            "eval_score_after": self.eval_score_after,
            "llm_model_used": self.llm_model_used,
            "token_cost": self.token_cost,
            "created_at": self.created_at,
        }


@dataclass
class EvolutionFile:
    """
    Local sidecar representation of all evolutions for a skill.
    Stored as <skill_dir>/evolutions.json for offline/CC compatibility.
    Supabase is SSOT; this is cache.
    """
    skill_name: str
    pending: list[EvolutionEntry] = field(default_factory=list)
    applied: list[EvolutionEntry] = field(default_factory=list)
    skipped: list[EvolutionEntry] = field(default_factory=list)
    last_updated: Optional[str] = None

    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "last_updated": self.last_updated,
            "pending": [e.to_dict() for e in self.pending],
            "applied": [e.to_dict() for e in self.applied],
            "skipped": [e.to_dict() for e in self.skipped],
        }


# ── Supabase DDL (also in migrations/20260330_skill_evolution.sql) ────────────

SQL_SKILL_EVOLUTION_SIGNALS = """
CREATE TABLE IF NOT EXISTS skill_evolution_signals (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    signal_type     TEXT NOT NULL CHECK (signal_type IN ('execution_failure','user_correction','score_regression','sentinel_alert')),
    skill_name      TEXT NOT NULL,
    excerpt         TEXT NOT NULL,
    tool_name       TEXT,
    source          TEXT NOT NULL DEFAULT 'session_log',
    fingerprint     TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    processed       BOOLEAN DEFAULT FALSE,
    UNIQUE(fingerprint)
);
"""

SQL_SKILL_EVOLUTION_ENTRIES = """
CREATE TABLE IF NOT EXISTS skill_evolution_entries (
    id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    skill_name          TEXT NOT NULL,
    source_signal_id    UUID REFERENCES skill_evolution_signals(id),
    target              TEXT NOT NULL,
    section             TEXT NOT NULL CHECK (section IN ('Instructions','Examples','Troubleshooting','EdgeCases')),
    content             TEXT NOT NULL,
    action              TEXT NOT NULL DEFAULT 'add' CHECK (action IN ('add','update','delete','skip')),
    skip_reason         TEXT,
    merge_target        TEXT,
    applied             BOOLEAN DEFAULT FALSE,
    eval_score_before   FLOAT,
    eval_score_after    FLOAT,
    llm_model_used      TEXT,
    token_cost          FLOAT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
"""
