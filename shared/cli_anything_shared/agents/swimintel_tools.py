"""SwimIntel agent tools — registered with shared ToolRegistry."""

from dataclasses import dataclass
from typing import Optional

from cli_anything_shared.tool_registry import PermissionMode, ToolSpec
from cli_anything_shared.agent_base import AgentBase


@dataclass
class AnalyzeSwimmerInput:
    swimmer_name: str
    age_group: str = "15-16"

@dataclass
class ClassifyZoningInput:
    zone_code: str
    zone_name: str = ""

@dataclass
class ParseTimeInput:
    time_str: str


def _handle_analyze_swimmer(inp: AnalyzeSwimmerInput) -> dict:
    return {"status": "requires parsed psych sheet data", "swimmer": inp.swimmer_name, "age_group": inp.age_group}

def _handle_parse_time(inp: ParseTimeInput) -> dict:
    from cli_anything.swimintel.core.parser import parse_time_to_seconds
    seconds = parse_time_to_seconds(inp.time_str)
    return {"time_str": inp.time_str, "seconds": seconds}


SWIMINTEL_TOOLS = [
    ToolSpec(
        name="swimintel_analyze",
        description="Analyze a swimmer's times against cuts and competitors",
        handler=_handle_analyze_swimmer,
        input_type=AnalyzeSwimmerInput,
        permission=PermissionMode.READ_ONLY,
        schema={
            "type": "object",
            "properties": {
                "swimmer_name": {"type": "string"},
                "age_group": {"type": "string", "default": "15-16"},
            },
            "required": ["swimmer_name"],
        },
        source="swimintel",
    ),
    ToolSpec(
        name="swimintel_parse_time",
        description="Parse a swim time string (e.g. '48.48') to seconds",
        handler=_handle_parse_time,
        input_type=ParseTimeInput,
        permission=PermissionMode.READ_ONLY,
        schema={
            "type": "object",
            "properties": {"time_str": {"type": "string"}},
            "required": ["time_str"],
        },
        source="swimintel",
    ),
]


class SwimIntelAgent(AgentBase):
    AGENT_NAME = "swimintel"

    def _register_tools(self):
        self.registry.register_many(SWIMINTEL_TOOLS)
