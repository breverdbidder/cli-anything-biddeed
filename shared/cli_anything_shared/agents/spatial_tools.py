"""Spatial Conquest agent tools — registered with shared ToolRegistry."""

from dataclasses import dataclass
from typing import Optional

from cli_anything_shared.tool_registry import PermissionMode, ToolSpec
from cli_anything_shared.agent_base import AgentBase


@dataclass
class DiscoverEndpointInput:
    county: str

@dataclass
class ProbeFieldsInput:
    endpoint_url: str

@dataclass
class DiscoverZonesInput:
    endpoint_url: str
    zone_field: str = "ZONING"

@dataclass
class ListCountiesInput:
    pass

@dataclass
class ValidatePointInput:
    lat: float
    lng: float


def _handle_discover_endpoint(inp: DiscoverEndpointInput) -> dict:
    from cli_anything.spatial.core.discovery import get_endpoint
    result = get_endpoint(inp.county)
    return result if result else {"error": f"No endpoint found for {inp.county}"}

def _handle_probe_fields(inp: ProbeFieldsInput) -> dict:
    from cli_anything.spatial.core.discovery import probe_fields
    return probe_fields(inp.endpoint_url)

def _handle_discover_zones(inp: DiscoverZonesInput) -> dict:
    from cli_anything.spatial.core.discovery import discover_zones
    return discover_zones(inp.endpoint_url, inp.zone_field)

def _handle_list_counties(inp: ListCountiesInput) -> dict:
    from cli_anything.spatial.core.discovery import list_known_counties, list_pending
    return {"known": list_known_counties(), "pending": list_pending()}

def _handle_validate_point(inp: ValidatePointInput) -> dict:
    from cli_anything.spatial.core.discovery import validate_point_in_florida
    return {"in_florida": validate_point_in_florida(inp.lat, inp.lng), "lat": inp.lat, "lng": inp.lng}


SPATIAL_TOOLS = [
    ToolSpec(
        name="spatial_discover_endpoint",
        description="Find GIS endpoint URL for a county's zoning layer",
        handler=_handle_discover_endpoint,
        input_type=DiscoverEndpointInput,
        permission=PermissionMode.READ_ONLY,
        schema={"type": "object", "properties": {"county": {"type": "string"}}, "required": ["county"]},
        source="spatial",
    ),
    ToolSpec(
        name="spatial_probe_fields",
        description="Probe available fields on a GIS endpoint",
        handler=_handle_probe_fields,
        input_type=ProbeFieldsInput,
        permission=PermissionMode.READ_ONLY,
        schema={"type": "object", "properties": {"endpoint_url": {"type": "string"}}, "required": ["endpoint_url"]},
        source="spatial",
    ),
    ToolSpec(
        name="spatial_discover_zones",
        description="Discover all zoning codes from a GIS endpoint",
        handler=_handle_discover_zones,
        input_type=DiscoverZonesInput,
        permission=PermissionMode.READ_ONLY,
        schema={
            "type": "object",
            "properties": {
                "endpoint_url": {"type": "string"},
                "zone_field": {"type": "string", "default": "ZONING"},
            },
            "required": ["endpoint_url"],
        },
        source="spatial",
    ),
    ToolSpec(
        name="spatial_list_counties",
        description="List known counties and pending conquest targets",
        handler=_handle_list_counties,
        input_type=ListCountiesInput,
        permission=PermissionMode.READ_ONLY,
        schema={"type": "object", "properties": {}},
        source="spatial",
    ),
    ToolSpec(
        name="spatial_validate_point",
        description="Check if a lat/lng coordinate is within Florida",
        handler=_handle_validate_point,
        input_type=ValidatePointInput,
        permission=PermissionMode.READ_ONLY,
        schema={
            "type": "object",
            "properties": {"lat": {"type": "number"}, "lng": {"type": "number"}},
            "required": ["lat", "lng"],
        },
        source="spatial",
    ),
]


class SpatialAgent(AgentBase):
    AGENT_NAME = "spatial"

    def _register_tools(self):
        self.registry.register_many(SPATIAL_TOOLS)
