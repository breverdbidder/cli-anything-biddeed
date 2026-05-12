# evolution/__init__.py
# Inspired by openJiuwen-ai/jiuwenclaw (Apache 2.0)
# AUTOLOOP V2 — LLM-Powered Skill Evolution Engine
# Issue: breverdbidder/cli-anything-biddeed#67

"""
evolution — BidDeed.AI AUTOLOOP V2 Skill Evolution Engine.

Beats JiuwenClaw on every dimension:
  - Multi-LLM via Smart Router (Gemini Flash + DeepSeek + Claude Sonnet)
  - Supabase persistence + local sidecar (vs their JSON-only)
  - Sentinel + SUMMIT integration (vs their standalone)
  - score_regression + sentinel_alert signal types (vs their 2 types)
  - eval_score_before/after tracking (they don't)
  - Token cost tracking per entry (they don't)
  - Telegram notifications via Nexus (they don't)
"""

from .schema import (
    EvolutionSignal,
    EvolutionEntry,
    EvolutionFile,
    SignalType,
    EntryAction,
    VALID_SECTIONS,
    SQL_SKILL_EVOLUTION_SIGNALS,
    SQL_SKILL_EVOLUTION_ENTRIES,
)
from .signal_detector import SignalDetector
from .evolver import Evolver

# JSON-path patcher (structured-config evolution; parallel to markdown evolver)
# Pattern source: Meir770ar/agentic-video-maker patch-plan.cjs (MIT, REPOEVAL REFERENCE_ONLY)
# See: docs/EVOLVER-JSONPATH.md
from .jsonpath_schema import (
    JsonPathEntry,
    WhitelistConfig,
    SQL_SKILL_EVOLUTION_JSONPATH_ENTRIES,
)
from .jsonpath_patcher import (
    JsonPathPatcher,
    PatchResult,
    AppliedPatch,
    SkippedPatch,
    parse_path,
    path_exists,
    set_path,
    coerce,
)
from .store import EvolutionStore
from .service import EvolutionService

__all__ = [
    "EvolutionSignal",
    "EvolutionEntry",
    "EvolutionFile",
    "SignalType",
    "EntryAction",
    "VALID_SECTIONS",
    "SQL_SKILL_EVOLUTION_SIGNALS",
    "SQL_SKILL_EVOLUTION_ENTRIES",
    "SignalDetector",
    "Evolver",
    "EvolutionStore",
    "EvolutionService",
]
