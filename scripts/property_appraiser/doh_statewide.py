#!/usr/bin/env python3
"""FL DOH statewide parcels layer -- SSOT client for property-appraiser
cross-verification, replacing per-county WAF-blocked scraping as the primary
path (see issue for the Aug 26 2026 P0: adopt statewide DOR layer).

https://gis.floridahealth.gov/server/rest/services/EHWATER/Parcels/MapServer
(redirects to maps.floridahealth.gov -- called directly here to skip the
redirect hop) is a single ArcGIS MapServer with one Feature Layer per FL
county, standard FL DOR NAL field names, no auth, no WAF, plain GET/JSON.

LAYER_MAP below was built by fetching '?f=json' on the MapServer root and
reading every layer's id + name (verified live 2026-08-26, all 67 layers
present). Do not hand-edit without re-verifying against a live '?f=json'
call -- these ids are NOT the same as either public.fl_counties.co_no (the
real FL DOR county code, e.g. Wakulla=75) or .co_no_old_alphabetical (a
different historical alphabetical scheme) -- confirmed live these three
numbering schemes diverge from each other after the first few counties, so
county identity here is matched by name, not by arithmetic on another
scheme's id. The source service's own layer names carry two upstream
typos ("Hernado County", "Pineallas County") which are corrected in the
slugs below (hernando, pinellas) since every other consumer in this repo
spells them correctly.

Parcel ID format is not uniform across counties -- confirmed live against
real leads: Wakulla and Flagler both store the same dashed format our
leads use ('00-00-034-009-08162-000'), Alachua stores its own PARCEL_ID
with spaces instead of dashes ('12631 000 000'). CANDIDATE_TRANSFORMS
tries the stored value as-is, then dash<->space swaps, then fully
stripped, and returns the first format that resolves to exactly one
feature -- rather than assuming one canonical format works everywhere.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://maps.floridahealth.gov/server/rest/services/EHWATER/Parcels/MapServer"

FIELDS = "PARCEL_ID,OWN_NAME,PHY_ADDR1,JV,AV_SD,TV_SD,LND_VAL,DOR_UC,NO_BULDNG"

RETRIES = 3
BACKOFF_SECONDS = 2

# Verified live 2026-08-26 via GET {BASE_URL}?f=json -- 67 layers, ids 0-66.
LAYER_MAP = {
    "alachua": 0, "baker": 1, "bay": 2, "bradford": 3, "brevard": 4,
    "broward": 5, "calhoun": 6, "charlotte": 7, "citrus": 8, "clay": 9,
    "collier": 10, "columbia": 11, "desoto": 12, "dixie": 13, "duval": 14,
    "escambia": 15, "flagler": 16, "franklin": 17, "gadsden": 18,
    "gilchrist": 19, "glades": 20, "gulf": 21, "hamilton": 22, "hardee": 23,
    "hendry": 24, "hernando": 25, "highlands": 26, "hillsborough": 27,
    "holmes": 28, "indian_river": 29, "jackson": 30, "jefferson": 31,
    "lafayette": 32, "lake": 33, "lee": 34, "leon": 35, "levy": 36,
    "liberty": 37, "madison": 38, "manatee": 39, "marion": 40, "martin": 41,
    "miami_dade": 42, "monroe": 43, "nassau": 44, "okaloosa": 45,
    "okeechobee": 46, "orange": 47, "osceola": 48, "palm_beach": 49,
    "pasco": 50, "pinellas": 51, "polk": 52, "putnam": 53, "st_johns": 54,
    "st_lucie": 55, "santa_rosa": 56, "sarasota": 57, "seminole": 58,
    "sumter": 59, "suwannee": 60, "taylor": 61, "union": 62, "volusia": 63,
    "wakulla": 64, "walton": 65, "washington": 66,
}


def candidate_formats(parcel_id: str) -> list[str]:
    seen = []
    for cand in (parcel_id, parcel_id.replace("-", " "), parcel_id.replace("-", ""), parcel_id.replace(" ", "")):
        if cand not in seen:
            seen.append(cand)
    return seen


def _query(layer_id: int, where: str) -> dict:
    q = (f"{BASE_URL}/{layer_id}/query?where={urllib.parse.quote(where)}"
         f"&outFields={FIELDS}&returnGeometry=false&f=json")
    req = urllib.request.Request(q, headers={"User-Agent": "biddeed-doh-statewide/1.0"})
    last_err = None
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last_err = e
            if attempt < RETRIES:
                time.sleep(BACKOFF_SECONDS * attempt)
    raise last_err


def query_parcel(county: str, parcel_id: str) -> dict | None:
    """Returns {**NAL fields, 'matched_format', 'layer_id'} for the first
    parcel-id format that resolves to exactly one feature, or None if this
    county has no layer on the statewide service or no format matched."""
    slug = (county or "").strip().lower().replace(" ", "_").replace("-", "_")
    layer_id = LAYER_MAP.get(slug)
    if layer_id is None or not parcel_id:
        return None

    for fmt in candidate_formats(parcel_id):
        escaped = fmt.replace("'", "''")
        result = _query(layer_id, f"PARCEL_ID='{escaped}'")
        if result.get("error"):
            raise RuntimeError(f"DOH statewide query error for {county}/{fmt}: {result['error']}")
        features = result.get("features", [])
        if len(features) == 1:
            attrs = dict(features[0]["attributes"])
            attrs["matched_format"] = fmt
            attrs["layer_id"] = layer_id
            return attrs
    return None
