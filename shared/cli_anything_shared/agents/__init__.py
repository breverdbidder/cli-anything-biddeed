"""Agent tool registrations for all CLI-Anything agents."""

from .zonewise_tools import ZoneWiseAgent, ZONEWISE_TOOLS
from .auction_tools import AuctionAgent, AUCTION_TOOLS
from .spatial_tools import SpatialAgent, SPATIAL_TOOLS
from .swimintel_tools import SwimIntelAgent, SWIMINTEL_TOOLS

ALL_AGENTS = {
    "zonewise": ZoneWiseAgent,
    "auction": AuctionAgent,
    "spatial": SpatialAgent,
    "swimintel": SwimIntelAgent,
}

ALL_TOOLS = ZONEWISE_TOOLS + AUCTION_TOOLS + SPATIAL_TOOLS + SWIMINTEL_TOOLS
