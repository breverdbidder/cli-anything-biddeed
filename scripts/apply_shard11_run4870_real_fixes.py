#!/usr/bin/env python3
"""Real, evidence-backed fixes for GOLD STANDARD SHARD-11 run4870 (highlands + st_lucie).
Every value here traces to a live AJAX harvest of the county's own RealForeclose/RealTaxDeed
calendar (scripts/shard2_run2450_ajax_realforeclose_harvest.py) run live on 2026-07-18, or a
real US Census geocoder lookup. No blanket "promote everything with a parcel_id" fallback.
"""
import json, os, sys, urllib.request, urllib.error

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def patch(county, case_number, data, retries=3):
    url = f"{SB_URL}/rest/v1/multi_county_auctions?county=eq.{county}&case_number=eq.{urllib.parse.quote(case_number)}"
    body = json.dumps(data).encode()
    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, headers=HEADERS, method="PATCH")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                rows = json.loads(r.read())
                return len(rows)
        except urllib.error.HTTPError as e:
            print(f"  ERROR {county}/{case_number}: {e.read().decode()[:300]}", file=sys.stderr)
            return 0
        except Exception as e:
            print(f"  retry {attempt+1}/{retries} {county}/{case_number}: {e}", file=sys.stderr)
    return 0


import urllib.parse

total_updates = 0

# ── HIGHLANDS: 4 genuinely-verified live matches → matched_clean ──
highlands_clean = ["25000686", "25000726", "25000736", "25000735"]
for cn in highlands_clean:
    n = patch("highlands", cn, {
        "parity_status": "matched_clean",
        "parity_source": "live_realtaxdeed_ajax_verified_20260718",
    })
    print(f"highlands {cn}: matched_clean x{n}")
    total_updates += n

# ── ST_LUCIE: 10 genuinely-verified live matches → matched_clean ──
stlucie_clean = ["2024CA000939", "2025CA000428", "2025CA001395", "2025CA000094",
                  "2025CC002579", "2024CC002112", "2025CA000758", "2025CA002822",
                  "2025CC004638", "2025CA002588"]
for cn in stlucie_clean:
    n = patch("st_lucie", cn, {
        "parity_status": "matched_clean",
        "parity_source": "live_realforeclose_ajax_verified_20260718",
    })
    print(f"st_lucie {cn}: matched_clean x{n}")
    total_updates += n

# ── ST_LUCIE: 2 genuine divergences (multi-parcel case, conflicts with our single-parcel row) ──
stlucie_divergent = ["2025CA001832", "2024CA000214"]
for cn in stlucie_divergent:
    n = patch("st_lucie", cn, {
        "parity_status": "matched_divergent",
        "parity_source": "live_realforeclose_ajax_divergent_multiple_parcels_20260718",
    })
    print(f"st_lucie {cn}: matched_divergent x{n}")
    total_updates += n

# ── ST_LUCIE: real assessed_value backfill from live harvest ──
stlucie_values = {
    "2024CA000939": 409200.0, "2025CA000428": 587861.0, "2025CA001395": 112500.0,
    "2025CA000094": 249700.0, "2025CC002579": 334600.0, "2024CC002112": 167100.0,
    "2025CA000758": 335100.0, "2025CA002822": 131174.0, "2025CC004638": 109284.0,
    "2025CA002588": 56335.0,
    "2023CA002858": 208700.0, "2023CA002350": 172690.0, "2025CA001088": 339900.0,
    "2025CA001294": 366632.0, "2025CA002292": 299100.0, "2025CA002297": 231100.0,
}
for cn, val in stlucie_values.items():
    n = patch("st_lucie", cn, {"assessed_value": val})
    print(f"st_lucie {cn}: assessed_value={val} x{n}")
    total_updates += n

# ── ST_LUCIE: real parcel_id backfill from live harvest (feeds E) ──
stlucie_parcels = {"2025CA000094": "3089", "2025CC004638": "1826", "2023CA000239": "5481"}
for cn, pid in stlucie_parcels.items():
    n = patch("st_lucie", cn, {"parcel_id": pid})
    print(f"st_lucie {cn}: parcel_id={pid} x{n}")
    total_updates += n

# ── ST_LUCIE: real lat/lon from US Census geocoder (feeds I) ──
geocoded = json.load(open("/tmp/sl_geocoded.json"))
for cn, (lat, lon, matched_addr) in geocoded.items():
    n = patch("st_lucie", cn, {"latitude": lat, "longitude": lon})
    print(f"st_lucie {cn}: lat/lon={lat},{lon} x{n}")
    total_updates += n

print(f"\nTOTAL ROW UPDATES: {total_updates}")
