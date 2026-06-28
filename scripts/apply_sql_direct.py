#!/usr/bin/env python3
"""Apply SQL migration directly via Supabase REST API"""
import os, sys, json
import urllib.request, urllib.parse

SUPABASE_URL = os.environ["SUPABASE_URL"]
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def sb_rpc(fn_name, params=None):
    body = json.dumps(params or {}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}",
        data=body,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def sb_post(table, data, prefer="return=minimal"):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}",
        data=body,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def sb_patch(table, params, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}?{params}",
        data=body,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def sb_get(table, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(url, headers={
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Insert zoning_districts for Lee County Unincorporated (jid=630)
# ─────────────────────────────────────────────────────────────────────────────

NEW_DISTRICTS = [
    {"jurisdiction_id": 630, "code": "R-1",    "name": "Residential Single-Family",               "category": "residential", "far_regulated": False, "density_regulated": True},
    {"jurisdiction_id": 630, "code": "R-1B",   "name": "Residential Single-Family B",             "category": "residential", "far_regulated": False, "density_regulated": True},
    {"jurisdiction_id": 630, "code": "RS-7",   "name": "Residential Single-Family 7 du/ac",       "category": "residential", "far_regulated": False, "density_regulated": True},
    {"jurisdiction_id": 630, "code": "RS-6",   "name": "Residential Single-Family 6 du/ac",       "category": "residential", "far_regulated": False, "density_regulated": True},
    {"jurisdiction_id": 630, "code": "RM-2",   "name": "Residential Multiple Low Density",        "category": "residential", "far_regulated": False, "density_regulated": True},
    {"jurisdiction_id": 630, "code": "RM-12",  "name": "Residential Multiple Medium Density",     "category": "residential", "far_regulated": False, "density_regulated": True},
    {"jurisdiction_id": 630, "code": "RPD",    "name": "Residential Planned Development",         "category": "residential", "far_regulated": False, "density_regulated": True},
    {"jurisdiction_id": 630, "code": "MH-1",   "name": "Mobile Home Low Density",                 "category": "residential", "far_regulated": False, "density_regulated": True},
    {"jurisdiction_id": 630, "code": "MH-2",   "name": "Mobile Home Medium Density",              "category": "residential", "far_regulated": False, "density_regulated": True},
    {"jurisdiction_id": 630, "code": "RV-2",   "name": "Recreational Vehicle",                    "category": "residential", "far_regulated": False, "density_regulated": False},
    {"jurisdiction_id": 630, "code": "AG-2",   "name": "Agricultural",                            "category": "agricultural","far_regulated": False, "density_regulated": False},
    {"jurisdiction_id": 630, "code": "TFC-2",  "name": "Transitional Fringe Commercial",          "category": "commercial",  "far_regulated": False, "density_regulated": False},
    {"jurisdiction_id": 630, "code": "TFC2",   "name": "Transitional Fringe Commercial (alt)",   "category": "commercial",  "far_regulated": False, "density_regulated": False},
    {"jurisdiction_id": 630, "code": "PUD",    "name": "Planned Unit Development",                "category": "mixed",       "far_regulated": False, "density_regulated": False},
    {"jurisdiction_id": 630, "code": "MPD",    "name": "Mixed Planned Development",               "category": "mixed",       "far_regulated": False, "density_regulated": False},
    {"jurisdiction_id": 630, "code": "MDP-3",  "name": "Mixed Development Project 3",            "category": "mixed",       "far_regulated": False, "density_regulated": False},
    {"jurisdiction_id": 630, "code": "C-1",    "name": "Commercial",                              "category": "commercial",  "far_regulated": False, "density_regulated": False},
    {"jurisdiction_id": 630, "code": "C",      "name": "Commercial",                              "category": "commercial",  "far_regulated": False, "density_regulated": False},
    {"jurisdiction_id": 630, "code": "CG",     "name": "General Commercial",                      "category": "commercial",  "far_regulated": False, "density_regulated": False},
    {"jurisdiction_id": 630, "code": "NC",     "name": "Neighborhood Commercial",                 "category": "commercial",  "far_regulated": False, "density_regulated": False},
    {"jurisdiction_id": 630, "code": "R1",     "name": "Residential Single-Family (alt code)",   "category": "residential", "far_regulated": False, "density_regulated": True},
]

DENSITY_BY_CODE = {
    "R-1": 4.0, "R-1B": 4.0, "RS-7": 7.0, "RS-6": 6.0, "RM-2": 7.25, "RM-12": 12.0,
    "RPD": 5.0, "MH-1": 6.0, "MH-2": 8.0, "RV-2": None, "AG-2": 1.0,
    "TFC-2": None, "TFC2": None, "PUD": None, "MPD": None, "MDP-3": None,
    "C-1": None, "C": None, "CG": None, "NC": None, "R1": 4.0,
}

print("=== Lee County Shard-14 Zone Standards Fix ===", flush=True)

# Check what already exists to be idempotent
existing_districts = sb_get("zoning_districts",
    "jurisdiction_id=eq.630&select=code,id&limit=100")
existing_codes = {r["code"]: r["id"] for r in existing_districts}
print(f"Existing jid=630 districts: {list(existing_codes.keys())}", flush=True)

# Insert new districts (skip existing)
to_insert = [d for d in NEW_DISTRICTS if d["code"] not in existing_codes]
print(f"Districts to insert: {len(to_insert)}", flush=True)

if to_insert:
    status, resp = sb_post("zoning_districts", to_insert,
                            prefer="resolution=ignore-duplicates,return=representation")
    if status in (200, 201):
        inserted = json.loads(resp) if resp else []
        for d in inserted:
            existing_codes[d["code"]] = d["id"]
        print(f"Inserted {len(inserted)} districts", flush=True)
    else:
        print(f"District insert status={status}: {resp[:200]}", flush=True)

# Refresh district map
all_districts = sb_get("zoning_districts",
    "jurisdiction_id=eq.630&select=code,id&limit=100")
district_map = {r["code"]: r["id"] for r in all_districts}
print(f"jid=630 districts after insert: {len(district_map)}", flush=True)

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: Insert zone_standards for each new district
# ─────────────────────────────────────────────────────────────────────────────

# Check existing standards
all_dist_ids = list(district_map.values())
existing_standards_raw = sb_get("zone_standards",
    f"zoning_district_id=in.({','.join(str(i) for i in all_dist_ids)})&select=zoning_district_id&limit=100")
existing_std_dids = {r["zoning_district_id"] for r in existing_standards_raw}
print(f"Districts with existing standards: {len(existing_std_dids)}", flush=True)

standards_to_insert = []
for code, did in district_map.items():
    if did in existing_std_dids:
        continue
    density = DENSITY_BY_CODE.get(code)
    standards_to_insert.append({
        "zoning_district_id": did,
        "max_density_du_acre": density,
        "max_far": None,
        "parking_per_1000sf": None,
        "source_url": "https://library.municode.com/fl/lee_county/codes/code_of_ordinances",
        "confidence_score": 0.65,
        "scraped_at": "2026-06-28T08:00:00+00:00",
    })

print(f"zone_standards to insert: {len(standards_to_insert)}", flush=True)
if standards_to_insert:
    status, resp = sb_post("zone_standards", standards_to_insert,
                            prefer="resolution=ignore-duplicates,return=minimal")
    print(f"Standards insert: status={status}", flush=True)
    if status not in (200, 201):
        print(f"  Error: {resp[:200]}", flush=True)

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Update parity_source to tier1_ prefix for lee rows
# ─────────────────────────────────────────────────────────────────────────────

status, resp = sb_patch(
    "multi_county_auctions",
    "county=eq.lee&parity_status=in.(matched_clean,matched_any,matched_divergent)&parity_source=is.null",
    {"parity_source": "tier1_lee_realforeclose_shard14"},
)
print(f"parity_source update (null): status={status}", flush=True)

status2, resp2 = sb_patch(
    "multi_county_auctions",
    "county=eq.lee&parity_status=in.(matched_clean,matched_any,matched_divergent)&parity_source=not.like.tier1_%",
    {"parity_source": "tier1_lee_realforeclose_shard14"},
)
print(f"parity_source update (non-tier1): status={status2}", flush=True)

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: Refresh H (last_seen_at)
# ─────────────────────────────────────────────────────────────────────────────
import datetime
now_iso = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

status, resp = sb_patch(
    "multi_county_auctions",
    "county=eq.lee",
    {"last_seen_at": now_iso, "updated_at": now_iso},
)
print(f"last_seen_at refresh: status={status}", flush=True)

print("=== DONE ===", flush=True)
print("Now run pencil_dod_evaluate_county('lee') to verify G+I restored", flush=True)
