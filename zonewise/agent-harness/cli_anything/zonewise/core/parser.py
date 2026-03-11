"""Zoning code parser for ZoneWise CLI.

Parses raw HTML/markdown into structured zoning records.
"""

import re
from typing import Optional


# Zoning category classification
CATEGORY_PATTERNS = {
    "residential": re.compile(r"(^R[SMUEC]|^PUD|^MH|residential|single.?family|multi.?family)", re.IGNORECASE),
    "conservation": re.compile(r"(^CON|^OS|^P[RK]|conservation|open.?space|park)", re.IGNORECASE),
    "commercial": re.compile(r"(^C[GRN]|^B[UPCD]|commercial|retail|office)", re.IGNORECASE),
    "industrial": re.compile(r"(^[IM][LHGP]|industrial|manufactur|warehouse)", re.IGNORECASE),
    "agricultural": re.compile(r"(^A[GRUC]|agricultur|farming|rural)", re.IGNORECASE),
    "mixed_use": re.compile(r"(^MU|^MX|mixed.?use|planned.?unit)", re.IGNORECASE),
}


def classify_zoning(zone_code: str, zone_name: str = "") -> str:
    """Classify a zoning code into a category."""
    text = f"{zone_code} {zone_name}"
    for category, pattern in CATEGORY_PATTERNS.items():
        if pattern.search(text):
            return category
    return "other"


def parse_zoning_record(raw: dict) -> dict:
    """Parse a raw zoning entry into a structured record."""
    zone_code = raw.get("code", raw.get("zone_code", "")).strip().upper()
    zone_name = raw.get("name", raw.get("zone_name", "")).strip()

    record = {
        "zone_code": zone_code,
        "zone_name": zone_name,
        "category": classify_zoning(zone_code, zone_name),
        "min_lot_size_sqft": _parse_int(raw.get("min_lot_size")),
        "max_height_ft": _parse_int(raw.get("max_height")),
        "setbacks": _parse_setbacks(raw.get("setbacks", {})),
        "allowed_uses": raw.get("allowed_uses", []),
        "source_url": raw.get("source_url", ""),
    }
    return record


def parse_zoning_from_markdown(markdown: str, county: str) -> list[dict]:
    """Extract zoning records from markdown text (Tier 2 output).

    This is a pattern-matching parser. For complex zoning documents,
    Tier 3 (Claude Sonnet) is required.
    """
    records = []
    # Look for common zoning code patterns in markdown
    code_pattern = re.compile(
        r"(?:^|\n)\s*\*?\*?([A-Z]{1,3}[-\s]?\d{0,2}[A-Z]?)\*?\*?"
        r"\s*[-–:]\s*(.+?)(?:\n|$)",
        re.MULTILINE,
    )
    for match in code_pattern.finditer(markdown):
        code = match.group(1).strip()
        name = match.group(2).strip()
        if len(code) >= 2 and len(name) >= 3:
            records.append(parse_zoning_record({
                "code": code,
                "name": name,
                "county": county,
            }))
    return records


def _parse_int(value) -> Optional[int]:
    """Safely parse an integer from various input types."""
    if value is None:
        return None
    try:
        # Handle strings like "7,500 sqft" or "35 ft"
        cleaned = re.sub(r"[^\d.]", "", str(value))
        return int(float(cleaned)) if cleaned else None
    except (ValueError, TypeError):
        return None


def _parse_setbacks(raw: dict) -> dict:
    """Parse setback values into structured format."""
    return {
        "front": _parse_int(raw.get("front")),
        "rear": _parse_int(raw.get("rear")),
        "side": _parse_int(raw.get("side")),
    }
