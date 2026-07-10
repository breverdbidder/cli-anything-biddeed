#!/usr/bin/env python3
"""
server.py — Dify Custom Tool HTTP Server: zonewise-agent
Issue: breverdbidder/cli-anything-biddeed#108

FastAPI service exposing parcel_lookup, zoning_lookup, address_normalize
as HTTP API endpoints that Dify registers as custom tools.

Runs on Hetzner 87.99.129.125:8319
Dify registers via tools/zonewise-agent/dify_tool.yaml (OpenAPI 3.0)

Usage:
    uvicorn server:app --host 0.0.0.0 --port 8319
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="zonewise-agent",
    description=(
        "Dify Custom Tool — ZoneWise zoning lookup agent. "
        "Provides parcel_lookup, zoning_lookup, and address_normalize tools "
        "for the Dify zoning agent on ZoneWise.AI."
    ),
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


def _supa_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


# ── Request / Response Models ─────────────────────────────────────────────────

class ParcelLookupRequest(BaseModel):
    address: str
    county: str = "brevard"
    limit: int = 5


class ParcelResult(BaseModel):
    parcel_id: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    zone_code: Optional[str] = None
    zone_source: Optional[str] = None
    county: Optional[str] = None
    owner: Optional[str] = None
    dor_use_code: Optional[str] = None
    market_value: Optional[int] = None


class ParcelLookupResponse(BaseModel):
    query: str
    county: str
    results: list[ParcelResult]
    count: int
    queried_at: str


class ZoningLookupRequest(BaseModel):
    zone_code: Optional[str] = None
    parcel_id: Optional[str] = None
    county: str = "brevard"


class ZoneStandard(BaseModel):
    standard_type: Optional[str] = None
    value: Optional[str] = None
    unit: Optional[str] = None


class ZoningLookupResponse(BaseModel):
    zone_code: str
    zone_name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    standards: list[ZoneStandard]
    permitted_uses: list[str]
    county: str
    queried_at: str


class AddressNormalizeRequest(BaseModel):
    address: str
    state: str = "FL"


class AddressNormalizeResponse(BaseModel):
    original: str
    normalized: str
    city: Optional[str] = None
    state: str
    zip_code: Optional[str] = None
    street: Optional[str] = None
    encoded: str


# ── Address Normalization Logic ───────────────────────────────────────────────

_SUFFIX_MAP = {
    r"\bSt\.?\b": "Street",
    r"\bAve\.?\b": "Avenue",
    r"\bBlvd\.?\b": "Boulevard",
    r"\bDr\.?\b": "Drive",
    r"\bRd\.?\b": "Road",
    r"\bCt\.?\b": "Court",
    r"\bLn\.?\b": "Lane",
    r"\bPl\.?\b": "Place",
    r"\bCir\.?\b": "Circle",
    r"\bTer\.?\b": "Terrace",
    r"\bTerr\.?\b": "Terrace",
    r"\bHwy\.?\b": "Highway",
    r"\bPkwy\.?\b": "Parkway",
    r"\bFwy\.?\b": "Freeway",
    r"\bExpy\.?\b": "Expressway",
}

# Multi-word cities must be checked before single-word to avoid partial matches
_FLORIDA_CITIES = [
    "Satellite Beach", "Cocoa Beach", "Melbourne Beach", "Indian Harbour Beach",
    "Indian River Shores", "Cape Canaveral", "West Melbourne", "Palm Bay",
    "Merritt Island", "Port St. John", "Port St John", "Port Canaveral",
    "Rockledge", "Melbourne", "Titusville", "Cocoa", "Viera", "Suntree",
    "Indialantic", "Malabar", "Grant", "Micco", "Sebastian", "Fellsmere",
]


def _normalize_address(raw: str, state: str = "FL") -> AddressNormalizeResponse:
    addr = raw.strip()

    # Expand street type abbreviations (word-boundary, case-insensitive)
    for pattern, replacement in _SUFFIX_MAP.items():
        addr = re.sub(pattern, replacement, addr, flags=re.IGNORECASE)

    # Extract zip code
    zip_match = re.search(r"\b(\d{5})(?:-\d{4})?\b", addr)
    zip_code = zip_match.group(1) if zip_match else None

    # Detect state
    state_match = re.search(r"\b(FL|Florida)\b", addr, re.IGNORECASE)
    found_state = "FL" if state_match else state

    # Extract city — check known FL cities (multi-word first, longest first)
    city = None
    for candidate in _FLORIDA_CITIES:
        if re.search(re.escape(candidate), addr, re.IGNORECASE):
            city = candidate
            break

    # Street is everything before the first comma
    parts = addr.split(",")
    street_raw = parts[0].strip() if parts else addr
    # Title-case each word in the street portion
    street = " ".join(w.capitalize() for w in street_raw.split())

    # Build normalized address
    normalized_parts = [street]
    if city:
        normalized_parts.append(city)
    normalized_parts.append(found_state)
    if zip_code:
        normalized_parts.append(zip_code)
    normalized = ", ".join(normalized_parts)

    return AddressNormalizeResponse(
        original=raw,
        normalized=normalized,
        city=city,
        state=found_state,
        zip_code=zip_code,
        street=street,
        encoded=quote(normalized, safe=""),
    )


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "zonewise-agent",
        "port": 8319,
        "tools": ["parcel_lookup", "zoning_lookup", "address_normalize"],
    }


# ── parcel_lookup ─────────────────────────────────────────────────────────────

@app.post("/parcel_lookup", response_model=ParcelLookupResponse)
async def parcel_lookup(req: ParcelLookupRequest):
    """
    Look up parcel details from Supabase using a street address.

    Queries sample_properties with address_full ilike match and joins
    zoning_assignments for zone_code. Returns up to `limit` matching parcels.
    """
    if not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="SUPABASE_KEY not configured")

    # Normalize address to get clean street portion for DB matching
    norm = _normalize_address(req.address)
    search_term = norm.street.replace("'", "''")  # escape single quotes

    rows: list[dict] = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/sample_properties",
            headers=_supa_headers(),
            params={
                "select": "parcel_id,address_full,city,state,zip_code,owner_name,dor_use_code,just_value,county",
                "address_full": f"ilike.*{search_term}*",
                "limit": str(req.limit),
            },
        )
        if resp.status_code in (200, 206):
            rows = resp.json() or []

        # Fallback: search without county filter if no results
        if not rows:
            resp2 = await client.get(
                f"{SUPABASE_URL}/rest/v1/sample_properties",
                headers=_supa_headers(),
                params={
                    "select": "parcel_id,address_full,city,state,zip_code,owner_name,dor_use_code,just_value",
                    "address_full": f"ilike.*{search_term}*",
                    "limit": str(req.limit),
                },
            )
            if resp2.status_code in (200, 206):
                rows = resp2.json() or []

    if not isinstance(rows, list):
        rows = []

    # Enrich with zoning_assignments
    parcel_ids = [r.get("parcel_id") for r in rows if r.get("parcel_id")]
    zone_map: dict[str, dict] = {}

    if parcel_ids:
        id_csv = ",".join(parcel_ids[:10])
        async with httpx.AsyncClient(timeout=10.0) as client:
            za_resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/zoning_assignments",
                headers=_supa_headers(),
                params={
                    "select": "parcel_id,zone_code,zone_source",
                    "parcel_id": f"in.({id_csv})",
                },
            )
            if za_resp.status_code in (200, 206):
                for za in (za_resp.json() or []):
                    zone_map[za.get("parcel_id", "")] = za

    results = []
    for row in rows:
        pid = row.get("parcel_id")
        za = zone_map.get(pid or "", {})
        results.append(ParcelResult(
            parcel_id=pid,
            address=row.get("address_full"),
            city=row.get("city"),
            state=row.get("state"),
            zip_code=row.get("zip_code"),
            zone_code=za.get("zone_code"),
            zone_source=za.get("zone_source"),
            county=row.get("county", req.county),
            owner=row.get("owner_name"),
            dor_use_code=row.get("dor_use_code"),
            market_value=row.get("just_value"),
        ))

    return ParcelLookupResponse(
        query=req.address,
        county=req.county,
        results=results,
        count=len(results),
        queried_at=datetime.now(timezone.utc).isoformat(),
    )


# ── zoning_lookup ─────────────────────────────────────────────────────────────

@app.post("/zoning_lookup", response_model=ZoningLookupResponse)
async def zoning_lookup(req: ZoningLookupRequest):
    """
    Retrieve zoning regulations by zone_code or parcel_id.

    Queries zoning_districts for district info + zone_standards for setbacks,
    height, density. Also queries permitted_uses for allowed land uses.
    """
    if not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="SUPABASE_KEY not configured")

    zone_code = req.zone_code

    # If parcel_id provided, resolve zone_code first
    if not zone_code and req.parcel_id:
        async with httpx.AsyncClient(timeout=10.0) as client:
            za_resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/zoning_assignments",
                headers=_supa_headers(),
                params={
                    "select": "zone_code",
                    "parcel_id": f"eq.{req.parcel_id}",
                    "limit": "1",
                },
            )
            if za_resp.status_code in (200, 206):
                rows = za_resp.json() or []
                if rows:
                    zone_code = rows[0].get("zone_code")

    if not zone_code:
        raise HTTPException(
            status_code=404,
            detail="zone_code not found — provide zone_code or a valid parcel_id",
        )

    # Query zoning_districts
    district: dict = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        dist_resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/zoning_districts",
            headers=_supa_headers(),
            params={
                "select": "code,name,category,description,jurisdiction_id",
                "code": f"eq.{zone_code}",
                "limit": "1",
            },
        )
        if dist_resp.status_code in (200, 206):
            rows = dist_resp.json() or []
            if rows:
                district = rows[0]

    # Query zone_standards
    standards: list[ZoneStandard] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        std_resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/zone_standards",
            headers=_supa_headers(),
            params={
                "select": "standard_type,value,unit",
                "zone_code": f"eq.{zone_code}",
            },
        )
        if std_resp.status_code in (200, 206):
            for s in (std_resp.json() or []):
                standards.append(ZoneStandard(
                    standard_type=s.get("standard_type"),
                    value=str(s.get("value", "")),
                    unit=s.get("unit"),
                ))

    # Query permitted_uses
    uses: list[str] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        use_resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/permitted_uses",
            headers=_supa_headers(),
            params={
                "select": "use_description,permit_type",
                "zone_code": f"eq.{zone_code}",
                "limit": "20",
            },
        )
        if use_resp.status_code in (200, 206):
            for u in (use_resp.json() or []):
                desc = u.get("use_description", "")
                ptype = u.get("permit_type", "")
                if desc:
                    uses.append(f"{desc} ({ptype})" if ptype else desc)

    return ZoningLookupResponse(
        zone_code=zone_code,
        zone_name=district.get("name"),
        category=district.get("category"),
        description=district.get("description"),
        standards=standards,
        permitted_uses=uses,
        county=req.county,
        queried_at=datetime.now(timezone.utc).isoformat(),
    )


# ── address_normalize ─────────────────────────────────────────────────────────

@app.post("/address_normalize", response_model=AddressNormalizeResponse)
async def address_normalize_endpoint(req: AddressNormalizeRequest):
    """
    Normalize a raw address string for database matching.

    Expands street type abbreviations (St→Street, Ave→Avenue, Blvd→Boulevard),
    handles two-word FL cities (Satellite Beach, Cocoa Beach), extracts zip.
    Returns normalized form and URL-encoded version for API calls.
    """
    return _normalize_address(req.address, req.state)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8319"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
