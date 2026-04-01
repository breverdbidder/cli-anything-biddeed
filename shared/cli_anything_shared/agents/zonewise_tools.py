"""ZoneWise agent tools — registered with shared ToolRegistry.

Wraps existing core functions (scraper, parser, export) as typed tools
with permission gating and LLM-compatible schemas.
"""

from dataclasses import dataclass
from typing import Optional

from cli_anything_shared.tool_registry import PermissionMode, ToolSpec
from cli_anything_shared.agent_base import AgentBase


# --- Typed input structs ---

@dataclass
class CountyListInput:
    state: str = "FL"

@dataclass
class CountyScrapeInput:
    county: str
    tier: int = 1

@dataclass
class ScrapeStatusInput:
    county: str

@dataclass
class ClassifyZoningInput:
    zone_code: str
    zone_name: str = ""

@dataclass
class ExportJsonInput:
    output_path: str

@dataclass
class ExportSupabaseInput:
    table: str = "zoning_records"
    county: Optional[str] = None


# --- Handlers (delegate to core) ---

def _handle_county_list(inp: CountyListInput) -> dict:
    from cli_anything.zonewise.core.scraper import get_county_list
    return {"counties": get_county_list(inp.state)}

def _handle_county_scrape(inp: CountyScrapeInput) -> dict:
    from cli_anything.zonewise.core.scraper import scrape_county
    return scrape_county(inp.county, tier=inp.tier)

def _handle_scrape_status(inp: ScrapeStatusInput) -> dict:
    from cli_anything.zonewise.core.scraper import get_scrape_status
    return get_scrape_status(inp.county)

def _handle_classify_zoning(inp: ClassifyZoningInput) -> dict:
    from cli_anything.zonewise.core.parser import classify_zoning
    return {"classification": classify_zoning(inp.zone_code, inp.zone_name)}


# --- Tool specs ---

ZONEWISE_TOOLS = [
    ToolSpec(
        name="zonewise_county_list",
        description="List all available counties for zoning data",
        handler=_handle_county_list,
        input_type=CountyListInput,
        permission=PermissionMode.READ_ONLY,
        schema={
            "type": "object",
            "properties": {"state": {"type": "string", "default": "FL"}},
        },
        source="zonewise",
    ),
    ToolSpec(
        name="zonewise_county_scrape",
        description="Scrape zoning data for a county using tiered Firecrawl strategy",
        handler=_handle_county_scrape,
        input_type=CountyScrapeInput,
        permission=PermissionMode.WORKSPACE_WRITE,
        schema={
            "type": "object",
            "properties": {
                "county": {"type": "string"},
                "tier": {"type": "integer", "default": 1, "minimum": 1, "maximum": 3},
            },
            "required": ["county"],
        },
        source="zonewise",
    ),
    ToolSpec(
        name="zonewise_scrape_status",
        description="Check scrape status and coverage for a county",
        handler=_handle_scrape_status,
        input_type=ScrapeStatusInput,
        permission=PermissionMode.READ_ONLY,
        schema={
            "type": "object",
            "properties": {"county": {"type": "string"}},
            "required": ["county"],
        },
        source="zonewise",
    ),
    ToolSpec(
        name="zonewise_classify_zoning",
        description="Classify a zoning code into category (residential, commercial, etc.)",
        handler=_handle_classify_zoning,
        input_type=ClassifyZoningInput,
        permission=PermissionMode.READ_ONLY,
        schema={
            "type": "object",
            "properties": {
                "zone_code": {"type": "string"},
                "zone_name": {"type": "string", "default": ""},
            },
            "required": ["zone_code"],
        },
        source="zonewise",
    ),
]


class ZoneWiseAgent(AgentBase):
    AGENT_NAME = "zonewise"

    def _register_tools(self):
        self.registry.register_many(ZONEWISE_TOOLS)
