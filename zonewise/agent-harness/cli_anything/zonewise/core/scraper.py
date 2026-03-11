"""County scraping pipeline for ZoneWise CLI.

Tiered approach: Firecrawl → Gemini → Claude → Manual flag.
"""

import json
from datetime import datetime, timezone
from typing import Optional

# Florida counties (46 active in multi_county_auctions)
FL_COUNTIES = [
    "alachua", "baker", "bay", "brevard", "broward", "charlotte", "citrus",
    "clay", "collier", "columbia", "duval", "escambia", "flagler", "hernando",
    "hillsborough", "indian_river", "lake", "lee", "leon", "manatee",
    "marion", "martin", "miami_dade", "monroe", "nassau", "okaloosa",
    "okeechobee", "orange", "osceola", "palm_beach", "pasco", "pinellas",
    "polk", "putnam", "santa_rosa", "sarasota", "seminole", "st_johns",
    "st_lucie", "sumter", "suwannee", "taylor", "volusia", "wakulla",
    "walton", "washington",
]


def get_county_list(state: str = "FL") -> list[dict]:
    """Return available counties."""
    if state.upper() != "FL":
        return []
    return [{"county": c, "state": "FL"} for c in FL_COUNTIES]


def scrape_county(county: str, tier: int = 1, firecrawl_key: Optional[str] = None) -> dict:
    """Scrape zoning data for a county using the tiered pipeline.

    Tier 1: Firecrawl (requires API key)
    Tier 2: Gemini Flash (free, structured parsing)
    Tier 3: Claude Sonnet (complex zoning interpretation)
    Tier 4: Manual flag (returns stub for human review)
    """
    county = county.lower().replace("-", "_").replace(" ", "_")
    if county not in FL_COUNTIES:
        raise ValueError(f"Unknown county: {county}. Use 'county list' to see available counties.")

    result = {
        "county": county,
        "state": "FL",
        "tier_used": tier,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "records": [],
    }

    if tier == 1:
        result = _scrape_tier1(county, firecrawl_key, result)
    elif tier == 2:
        result = _scrape_tier2(county, result)
    elif tier == 3:
        result = _scrape_tier3(county, result)
    else:
        result["status"] = "manual_flag"
        result["message"] = f"County {county} flagged for manual review"

    return result


def _scrape_tier1(county: str, api_key: Optional[str], result: dict) -> dict:
    """Tier 1: Firecrawl scraping to markdown."""
    if not api_key:
        try:
            from cli_anything_shared.config import get_config
            api_key = get_config("zonewise", "firecrawl_api_key", env_var="FIRECRAWL_API_KEY")
        except ImportError:
            pass

    if not api_key:
        result["status"] = "error"
        result["message"] = "Firecrawl API key not set. Use: export FIRECRAWL_API_KEY=fc-xxx"
        return result

    try:
        import httpx
        # Firecrawl scrape endpoint
        resp = httpx.post(
            "https://api.firecrawl.dev/v0/scrape",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"url": f"https://www.municode.com/library/{county}-county-fl/codes/code_of_ordinances"},
            timeout=60.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            result["status"] = "scraped"
            result["raw_markdown"] = data.get("data", {}).get("markdown", "")[:1000]  # Truncate for output
            result["message"] = f"Tier 1 scrape complete for {county}"
        else:
            result["status"] = "error"
            result["message"] = f"Firecrawl returned {resp.status_code}"
    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)

    return result


def _scrape_tier2(county: str, result: dict) -> dict:
    """Tier 2: Gemini Flash parsing (stub — requires LLM integration)."""
    result["status"] = "stub"
    result["message"] = f"Tier 2 (Gemini Flash) parsing for {county} — requires LLM integration"
    return result


def _scrape_tier3(county: str, result: dict) -> dict:
    """Tier 3: Claude Sonnet interpretation (stub — requires LLM integration)."""
    result["status"] = "stub"
    result["message"] = f"Tier 3 (Claude Sonnet) interpretation for {county} — requires LLM integration"
    return result


def get_scrape_status(county: str) -> dict:
    """Get last scrape status for a county from Supabase or local cache."""
    county = county.lower().replace("-", "_").replace(" ", "_")
    try:
        from cli_anything_shared.supabase import query_table
        rows = query_table("county_scrapes", {"county": county}, limit=1, cli_name="zonewise")
        if rows:
            return rows[0]
    except Exception:
        pass
    return {"county": county, "status": "unknown", "message": "No scrape history found"}
