"""Agent Base — shared foundation wiring ToolRegistry + SessionCompactor.

Every cli-anything agent inherits from this to get:
- Typed tool dispatch with permission gating
- Structured session compaction
- Uniform tool definition generation for LLM
- Session token tracking

SUMMIT #147 + #148 integration layer.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .tool_registry import PermissionMode, ToolRegistry, ToolResult, ToolSpec
from .session_compactor import CompactionConfig, CompactionResult, compact_session


class AgentBase:
    """Base class for all CLI-Anything agents.

    Subclasses register their tools in `_register_tools()` and get
    automatic permission gating, token tracking, and compaction.
    """

    AGENT_NAME: str = "base"

    def __init__(
        self,
        permission: PermissionMode = PermissionMode.READ_ONLY,
        compaction_config: Optional[CompactionConfig] = None,
    ):
        self.registry = ToolRegistry(permission_level=permission)
        self.compaction_config = compaction_config or CompactionConfig()
        self.messages: list[dict] = []
        self.started_at = datetime.now(timezone.utc)
        self._register_tools()

    def _register_tools(self) -> None:
        """Override in subclass to register agent-specific tools."""
        pass

    def execute_tool(self, name: str, input_json: dict) -> ToolResult:
        """Execute a tool and track the call in message history."""
        result = self.registry.execute(name, input_json)

        # Track tool call in messages for compaction
        self.messages.append({
            "role": "assistant",
            "content": [{
                "type": "tool_use",
                "id": f"tu_{len(self.messages):04d}",
                "name": name,
                "input": input_json,
            }],
        })
        self.messages.append({
            "role": "tool",
            "content": [{
                "type": "tool_result",
                "tool_use_id": f"tu_{len(self.messages) - 1:04d}",
                "tool_name": name,
                "content": result.to_json(),
            }],
        })

        return result

    def add_user_message(self, content: str) -> None:
        """Track a user message for compaction."""
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """Track an assistant message for compaction."""
        self.messages.append({"role": "assistant", "content": content})

    def compact(self) -> CompactionResult:
        """Run compaction on current message history."""
        result = compact_session(self.messages, self.compaction_config)
        if result.compacted:
            self.messages = result.compacted_messages
        return result

    def tool_definitions(self) -> list[dict]:
        """Get LLM-compatible tool definitions for this agent."""
        return self.registry.tool_definitions()

    def available_tools(self) -> list[dict]:
        """Get tool definitions filtered to current permission level."""
        return self.registry.available_tools()

    def status(self) -> dict:
        """Agent status summary."""
        from .session_compactor import estimate_session_tokens
        return {
            "agent": self.AGENT_NAME,
            "permission": self.registry.permission_level.name,
            "tools_registered": len(self.registry.names()),
            "tools_available": len(self.available_tools()),
            "messages": len(self.messages),
            "estimated_tokens": estimate_session_tokens(self.messages),
            "needs_compaction": len(self.messages) > self.compaction_config.preserve_recent_messages
                and estimate_session_tokens(self.messages) >= self.compaction_config.max_estimated_tokens,
            "uptime_seconds": (datetime.now(timezone.utc) - self.started_at).total_seconds(),
        }
