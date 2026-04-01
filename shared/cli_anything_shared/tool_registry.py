"""Tool Execution Registry for CLI-Anything BidDeed agents.

Typed dispatch with permission gating, uniform error handling,
and JSON schema generation for LLM tool definitions.

Pattern source: breverdbidder/claw-code rust/crates/tools/src/lib.rs
SUMMIT: #147
"""

import json
import traceback
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Optional, Type


class PermissionMode(IntEnum):
    """Permission levels, ordered by access scope.

    IntEnum so comparisons work: READ_ONLY < WORKSPACE_WRITE < DANGER_FULL.
    """
    READ_ONLY = 1
    WORKSPACE_WRITE = 2
    DANGER_FULL = 3


@dataclass(frozen=True)
class ToolSpec:
    """Specification for a single tool in the registry.

    Attributes:
        name: Tool identifier (must be unique in registry).
        description: Human-readable description for LLM tool definitions.
        handler: Callable that receives typed input and returns a dict result.
        input_type: Dataclass or class used to validate/deserialize input.
        permission: Minimum permission level required to execute.
        schema: JSON Schema dict describing the input for LLM tool use.
        source: Which agent or module provides this tool (e.g. 'zonewise', 'auction').
    """
    name: str
    description: str
    handler: Callable
    input_type: Type
    permission: PermissionMode
    schema: dict
    source: str = "shared"


@dataclass
class ToolResult:
    """Uniform result from tool execution.

    Either result is set (success) or error is set (failure). Never both.
    """
    result: Optional[Any] = None
    error: Optional[str] = None
    tool_name: str = ""

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_json(self) -> str:
        if self.ok:
            return json.dumps(self.result, indent=2, default=str)
        return json.dumps({"error": self.error}, indent=2)


class ToolRegistry:
    """Central registry for all agent tools.

    Design decisions (from claw-code Pattern #4):
    1. Typed input structs — validation at deserialization, not runtime.
    2. Permission gating in spec, not execution — checked BEFORE handler call.
    3. Uniform error type — all tools return ToolResult.
    4. Registry generates LLM tool_definitions automatically.
    """

    def __init__(self, permission_level: PermissionMode = PermissionMode.READ_ONLY):
        self._tools: dict[str, ToolSpec] = {}
        self._permission_level = permission_level

    @property
    def permission_level(self) -> PermissionMode:
        return self._permission_level

    def set_permission(self, level: PermissionMode) -> None:
        """Change the current permission level for all subsequent executions."""
        self._permission_level = level

    def register(self, spec: ToolSpec) -> None:
        """Register a tool. Raises ValueError if name already registered."""
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def register_many(self, specs: list[ToolSpec]) -> None:
        """Register multiple tools at once."""
        for spec in specs:
            self.register(spec)

    def unregister(self, name: str) -> bool:
        """Remove a tool from the registry. Returns True if it existed."""
        return self._tools.pop(name, None) is not None

    def get(self, name: str) -> Optional[ToolSpec]:
        """Get a tool spec by name, or None."""
        return self._tools.get(name)

    def names(self) -> list[str]:
        """List all registered tool names, sorted."""
        return sorted(self._tools.keys())

    def execute(self, name: str, input_json: dict) -> ToolResult:
        """Execute a tool by name with JSON input.

        Flow:
        1. Lookup tool in registry
        2. Check permission level
        3. Deserialize input to typed struct
        4. Call handler
        5. Return ToolResult
        """
        spec = self._tools.get(name)
        if not spec:
            return ToolResult(error=f"unsupported tool: {name}", tool_name=name)

        # Permission gating BEFORE execution
        if spec.permission > self._permission_level:
            return ToolResult(
                error=f"permission denied: '{name}' requires {spec.permission.name}, "
                      f"current level is {self._permission_level.name}",
                tool_name=name,
            )

        # Typed deserialization
        try:
            typed_input = spec.input_type(**input_json)
        except (TypeError, ValueError) as e:
            return ToolResult(
                error=f"invalid input for '{name}': {e}",
                tool_name=name,
            )

        # Execute handler
        try:
            result = spec.handler(typed_input)
            return ToolResult(result=result, tool_name=name)
        except Exception as e:
            return ToolResult(
                error=f"tool '{name}' failed: {e}",
                tool_name=name,
            )

    def tool_definitions(self) -> list[dict]:
        """Generate LLM-compatible tool definitions for all registered tools.

        Returns list suitable for Anthropic API tools parameter.
        """
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "input_schema": spec.schema,
            }
            for spec in self._tools.values()
        ]

    def available_tools(self) -> list[dict]:
        """Like tool_definitions but filtered to current permission level."""
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "input_schema": spec.schema,
            }
            for spec in self._tools.values()
            if spec.permission <= self._permission_level
        ]

    def summary(self) -> str:
        """Human-readable summary of registry state."""
        lines = [f"ToolRegistry: {len(self._tools)} tools, permission={self._permission_level.name}"]
        for spec in self._tools.values():
            marker = "✅" if spec.permission <= self._permission_level else "🔒"
            lines.append(f"  {marker} {spec.name} [{spec.permission.name}] ({spec.source})")
        return "\n".join(lines)
