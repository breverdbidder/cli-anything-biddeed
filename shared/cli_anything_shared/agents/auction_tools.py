"""Auction agent tools — registered with shared ToolRegistry."""

from dataclasses import dataclass
from typing import Optional

from cli_anything_shared.tool_registry import PermissionMode, ToolSpec
from cli_anything_shared.agent_base import AgentBase


@dataclass
class UpcomingAuctionsInput:
    date: Optional[str] = None
    county: str = "brevard"

@dataclass
class CaseDetailsInput:
    case_number: str

@dataclass
class AnalyzeCaseInput:
    case_number: str
    arv: Optional[float] = None
    repairs: Optional[float] = None

@dataclass
class MaxBidInput:
    arv: float
    repairs: float


def _handle_upcoming(inp: UpcomingAuctionsInput) -> dict:
    from cli_anything.auction.core.discovery import get_upcoming_auctions
    return get_upcoming_auctions(date=inp.date, county=inp.county)

def _handle_case_details(inp: CaseDetailsInput) -> dict:
    from cli_anything.auction.core.discovery import get_case_details
    result = get_case_details(inp.case_number)
    return result if result else {"error": f"Case {inp.case_number} not found"}

def _handle_analyze(inp: AnalyzeCaseInput) -> dict:
    from cli_anything.auction.core.discovery import get_case_details
    from cli_anything.auction.core.analysis import analyze_case
    case_data = get_case_details(inp.case_number)
    if not case_data:
        return {"error": f"Case {inp.case_number} not found"}
    return analyze_case(case_data, arv=inp.arv, repairs=inp.repairs)

def _handle_max_bid(inp: MaxBidInput) -> dict:
    from cli_anything.auction.core.analysis import calculate_max_bid
    return calculate_max_bid(inp.arv, inp.repairs)


AUCTION_TOOLS = [
    ToolSpec(
        name="auction_upcoming",
        description="Discover upcoming foreclosure auctions by date and county",
        handler=_handle_upcoming,
        input_type=UpcomingAuctionsInput,
        permission=PermissionMode.READ_ONLY,
        schema={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD or 'next'"},
                "county": {"type": "string", "default": "brevard"},
            },
        },
        source="auction",
    ),
    ToolSpec(
        name="auction_case_details",
        description="Get detailed information for a specific foreclosure case",
        handler=_handle_case_details,
        input_type=CaseDetailsInput,
        permission=PermissionMode.READ_ONLY,
        schema={
            "type": "object",
            "properties": {"case_number": {"type": "string"}},
            "required": ["case_number"],
        },
        source="auction",
    ),
    ToolSpec(
        name="auction_analyze",
        description="Run full BidDeed analysis on a foreclosure case (ARV, repairs, max bid, recommendation)",
        handler=_handle_analyze,
        input_type=AnalyzeCaseInput,
        permission=PermissionMode.READ_ONLY,
        schema={
            "type": "object",
            "properties": {
                "case_number": {"type": "string"},
                "arv": {"type": "number", "description": "After-repair value override"},
                "repairs": {"type": "number", "description": "Repair cost override"},
            },
            "required": ["case_number"],
        },
        source="auction",
    ),
    ToolSpec(
        name="auction_max_bid",
        description="Calculate max bid using Everest formula: (ARV*70%)-Repairs-$10K-MIN($25K,15%*ARV)",
        handler=_handle_max_bid,
        input_type=MaxBidInput,
        permission=PermissionMode.READ_ONLY,
        schema={
            "type": "object",
            "properties": {
                "arv": {"type": "number"},
                "repairs": {"type": "number"},
            },
            "required": ["arv", "repairs"],
        },
        source="auction",
    ),
]


class AuctionAgent(AgentBase):
    AGENT_NAME = "auction"

    def _register_tools(self):
        self.registry.register_many(AUCTION_TOOLS)
