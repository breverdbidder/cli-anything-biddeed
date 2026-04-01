"""Agent Base — shared foundation wiring ToolRegistry + SessionCompactor + Observability.

Every cli-anything agent inherits from this to get:
- Typed tool dispatch with permission gating
- Structured session compaction
- Structured logging, metrics, timing, alerting
- Uniform tool definition generation for LLM
- Session token tracking

SUMMIT #147 + #148 + Observability upgrade.
"""

import json
from datetime import datetime, timezone
from typing import Optional

from .tool_registry import PermissionMode, ToolRegistry, ToolResult, ToolSpec
from .session_compactor import CompactionConfig, CompactionResult, compact_session, estimate_session_tokens
from .observability import AgentMetrics, ToolTimer, get_logger, send_alert

_DENIAL_ALERT_THRESHOLD = 3
_ERROR_RATE_ALERT_THRESHOLD = 50.0
_MAX_INPUT_CHARS = 50_000


class AgentBase:
    """Base class for all CLI-Anything agents.

    Subclasses register their tools in _register_tools() and get
    automatic permission gating, token tracking, compaction, and observability.
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
        self.metrics = AgentMetrics(agent_name=self.AGENT_NAME)
        self.logger = get_logger(self.AGENT_NAME)
        self._register_tools()
        self.logger.info(f"initialized with {len(self.registry.names())} tools at {permission.name}")

    def _register_tools(self) -> None:
        """Override in subclass to register agent-specific tools."""
        pass

    def execute_tool(self, name: str, input_json: dict) -> ToolResult:
        """Execute a tool with full observability: timing, logging, metrics, alerting."""
        input_size = len(json.dumps(input_json, default=str))
        if input_size > _MAX_INPUT_CHARS:
            self.logger.warning(f"large input for '{name}': {input_size} chars")

        with ToolTimer() as timer:
            result = self.registry.execute(name, input_json)

        if result.ok:
            self.logger.info(f"tool '{name}' OK in {timer.elapsed_ms:.0f}ms")
            self.metrics.record_call(name, timer.elapsed_ms, success=True)
        elif "permission denied" in (result.error or ""):
            self.logger.warning(f"DENIED: {result.error}")
            self.metrics.record_denial(name)
            self._check_denial_alert(name)
        else:
            self.logger.error(f"tool '{name}' FAILED in {timer.elapsed_ms:.0f}ms: {result.error}")
            self.metrics.record_call(name, timer.elapsed_ms, success=False, error=result.error)
            self._check_error_rate_alert(name)

        self.messages.append({"role": "assistant", "content": [{"type": "tool_use", "id": f"tu_{len(self.messages):04d}", "name": name, "input": input_json}]})
        self.messages.append({"role": "tool", "content": [{"type": "tool_result", "tool_use_id": f"tu_{len(self.messages)-1:04d}", "tool_name": name, "content": result.to_json()}]})
        return result

    def add_user_message(self, content: str) -> None:
        """Track a user message for compaction."""
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """Track an assistant message for compaction."""
        self.messages.append({"role": "assistant", "content": content})

    def compact(self) -> CompactionResult:
        """Run compaction on current message history with metrics tracking."""
        result = compact_session(self.messages, self.compaction_config)
        if result.compacted:
            self.messages = result.compacted_messages
            self.metrics.record_compaction(result.estimated_tokens_before, result.estimated_tokens_after)
            self.logger.info(f"compacted: {result.removed_count} msgs removed, {result.estimated_tokens_before}->{result.estimated_tokens_after} tokens")
        return result

    def tool_definitions(self) -> list[dict]:
        """Get LLM-compatible tool definitions for this agent."""
        return self.registry.tool_definitions()

    def available_tools(self) -> list[dict]:
        """Get tool definitions filtered to current permission level."""
        return self.registry.available_tools()

    def status(self) -> dict:
        """Agent status summary with metrics."""
        tokens = estimate_session_tokens(self.messages)
        return {
            "agent": self.AGENT_NAME,
            "permission": self.registry.permission_level.name,
            "tools_registered": len(self.registry.names()),
            "tools_available": len(self.available_tools()),
            "messages": len(self.messages),
            "estimated_tokens": tokens,
            "needs_compaction": len(self.messages) > self.compaction_config.preserve_recent_messages and tokens >= self.compaction_config.max_estimated_tokens,
            "uptime_seconds": round((datetime.now(timezone.utc) - self.started_at).total_seconds(), 1),
            "metrics": self.metrics.summary(),
        }

    def _check_denial_alert(self, tool_name: str) -> None:
        """Alert if denial count exceeds threshold."""
        total = sum(self.metrics.permission_denials.values())
        if total >= _DENIAL_ALERT_THRESHOLD:
            send_alert(f"agent={self.AGENT_NAME} denials={total} latest={tool_name}", level="denied")

    def _check_error_rate_alert(self, tool_name: str) -> None:
        """Alert if error rate exceeds threshold."""
        calls = self.metrics.tool_calls.get(tool_name, 0)
        errors = self.metrics.tool_errors.get(tool_name, 0)
        if calls >= 3 and (errors / calls * 100) >= _ERROR_RATE_ALERT_THRESHOLD:
            send_alert(f"agent={self.AGENT_NAME} tool={tool_name} errors={errors}/{calls}", level="error")
