"""Shared utilities for BidDeed CLI-Anything tools."""
__version__ = "1.1.0"

from .tool_registry import PermissionMode, ToolRegistry, ToolResult, ToolSpec
from .session_compactor import CompactionConfig, CompactionResult, compact_session
from .agent_base import AgentBase
