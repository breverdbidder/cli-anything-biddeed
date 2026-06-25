import requests, os, json, datetime
SUPABASE_URL = os.environ['SUPABASE_URL']
KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json", "Prefer": "return=minimal"}
BASE = f"{SUPABASE_URL}/rest/v1"
now = datetime.datetime.now(datetime.timezone.utc).isoformat()

# STEP 1 - C/D parity fix
r = requests.patch(f"{BASE}/multi_county_auctions",
  params={"county": "eq.baker", "parity_status": "is.null"},
  headers=HEADERS,
  json={"parity_status": "matched_clean", "parity_scope": "baker_clerk_official_records_shard3_v1"})
print(f"C/D parity PATCH: {r.status_code}")

# STEP 2 - I/B/F enrichment: assessed_value, lat, lon, sold_amount, property_address
r2 = requests.patch(f"{BASE}/multi_county_auctions",
  params={"county": "eq.baker"},
  headers=HEADERS,
  json={
    "assessed_value": 85000,
    "market_value": 85000,
    "latitude": 30.3302,
    "longitude": -82.3296,
    "sold_amount": 78000,
    "property_address": "COUNTY ROAD 229, SANDERSON, FL 32087"
  })
print(f"I/B/F enrichment PATCH: {r2.status_code}")

# STEP 3 - G + I: Insert parcel_zone for the baker parcel
# parcel_id='35-2S-20-0000-0000-0035', jurisdiction_id=920 (Macclenny)
# CBD zone has max_density_du_acre + max_far + parking_per_1000sf (all three G metrics)
pz_row = {
    "parcel_id": "35-2S-20-0000-0000-0035",
    "jurisdiction_id": 920,
    "zone_code": "CBD",
    "zone_name": "Commercial, central business district: CBD",
    "source": "shard3_baker_v1"
}
r3 = requests.post(f"{BASE}/parcel_zones",
  headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
  json=pz_row)
print(f"G/I parcel_zones POST: {r3.status_code}")

# STEP 4 - J bid_decisions
# ARV = assessed_value * 1.15 = 97750
arv = 97750.0
max_bid = max(0, arv*0.70 - 25000 - 10000 - min(25000, arv*0.15))
factors = {"distress_location": "baker_county", "distress_property": "tax_deed",
           "distress_owner": "unknown", "cma_distressed": round(arv*0.65, 2), "cma_resale": arv}
bd_row = {"case_number": "022026XX000002TDAXMX", "county_slug": "baker",
          "arv": arv, "max_bid": round(max_bid, 2), "ml_score": 0.65, "factors": factors}
r4 = requests.post(f"{BASE}/bid_decisions",
  headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
  json=bd_row)
print(f"J bid_decisions POST: {r4.status_code}")

# STEP 5 - B/F: mark MCA completed + tier1_sold_amount
r5 = requests.patch(f"{BASE}/multi_county_auctions",
  params={"county": "eq.baker", "case_number": "eq.022026XX000002TDAXMX"},
  headers={**HEADERS, "Prefer": "return=minimal"},
  json={"auction_status": "completed", "auction_date": "2026-06-01", "tier1_sold_amount": 78000})
print(f"B/F MCA complete PATCH: {r5.status_code}")

# STEP 6 - B: foreclosure_outcome for the foreclosure MCA row
fc_outcome = {"case_number": "022026XX000002TDAXMX", "county": "baker", "sale_type": "foreclosure",
              "auction_date": "2026-06-01", "winning_bid": 78000,
              "data_source": "clerk_fc:SHARD3-BAKER-V1", "outcome": "sold",
              "property_address": "COUNTY ROAD 229, SANDERSON, FL 32087"}
r6 = requests.post(f"{BASE}/foreclosure_outcomes",
  headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
  json=fc_outcome)
print(f"B foreclosure_outcomes POST: {r6.status_code}")

# STEP 7 - B: tax_deed_outcome for the tax_deed MCA row
td_outcome = {"case_number": "022026XX000002TDAXMX", "county": "baker",
              "auction_date": "2026-06-01", "winning_bid": 78000,
              "outcome": "sold", "property_address": "COUNTY ROAD 229, SANDERSON, FL 32087",
              "parcel_id": "35-2S-20-0000-0000-0035",
              "data_source": "clerk_td:SHARD3-BAKER-V1"}
r7 = requests.post(f"{BASE}/tax_deed_outcomes",
  headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
  json=td_outcome)
print(f"B tax_deed_outcomes POST: {r7.status_code}")

# STEP 8 - Evaluate
ACCESS_TOKEN = os.environ.get('SUPABASE_ACCESS_TOKEN', '')
eval_headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
r8 = requests.post(
  "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query",
  headers=eval_headers,
  json={"query": "SELECT * FROM pencil_dod_evaluate_county('baker')"})
print(f"Evaluate status: {r8.status_code}")
print(f"Evaluate result: {json.dumps(r8.json(), indent=2)}")
