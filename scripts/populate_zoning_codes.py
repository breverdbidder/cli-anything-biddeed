import requests, json, sys, time

SB_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SB_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vY2VycWpua3NtaGNqenhyZXdvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NDUzMjUyNiwiZXhwIjoyMDgwMTA4NTI2fQ.fL255mO0V8-rrU0Il3L41cIdQXUau-HRQXiamTqp9nE"
H = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json", "Prefer": "return=minimal"}

def fetch_all(table, select="*", filters="", limit=5000):
    """Fetch all records with pagination"""
    all_data = []
    offset = 0
    while True:
        url = f"{SB_URL}/rest/v1/{table}?select={select}&limit={limit}&offset={offset}"
        if filters:
            url += f"&{filters}"
        r = requests.get(url, headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
        data = r.json()
        if not data:
            break
        all_data.extend(data)
        if len(data) < limit:
            break
        offset += limit
    return all_data

# Step 1: Get all jurisdictions (id -> name, county)
print("Loading jurisdictions...")
jurisdictions = {j['id']: j for j in fetch_all("jurisdictions", "id,name,county")}
print(f"  {len(jurisdictions)} jurisdictions")

# Step 2: Get all zoning districts
print("Loading zoning districts...")
districts = fetch_all("zoning_districts", "id,jurisdiction_id,code,name,category,description,ordinance_section")
print(f"  {len(districts)} districts")

# Step 3: Get dimensional standards (indexed by zoning_district_id)
print("Loading dimensional standards...")
dims = fetch_all("dimensional_standards", "*")
dims_by_district = {}
for d in dims:
    dims_by_district[d['zoning_district_id']] = d
print(f"  {len(dims)} dimensional standards")

# Step 4: Get permitted uses (grouped by zoning_district_id)
print("Loading permitted uses...")
uses = fetch_all("permitted_uses", "zoning_district_id,use_type,use_description,is_single_family,is_multi_family,is_commercial,is_industrial,is_mixed_use")
uses_by_district = {}
for u in uses:
    did = u['zoning_district_id']
    if did not in uses_by_district:
        uses_by_district[did] = []
    uses_by_district[did].append(u)
print(f"  {len(uses)} permitted uses")

# Step 5: Normalize categories
def normalize_category(cat):
    if not cat:
        return "OTHER"
    cat_lower = cat.lower().strip()
    if 'resid' in cat_lower:
        return "RESIDENTIAL"
    elif 'commer' in cat_lower:
        return "COMMERCIAL"
    elif 'industr' in cat_lower:
        return "INDUSTRIAL"
    elif 'agric' in cat_lower:
        return "AGRICULTURAL"
    elif 'mixed' in cat_lower:
        return "MIXED_USE"
    elif 'conserv' in cat_lower:
        return "CONSERVATION"
    elif 'instit' in cat_lower:
        return "INSTITUTIONAL"
    elif 'planned' in cat_lower or 'pud' in cat_lower:
        return "PUD"
    elif 'overlay' in cat_lower:
        return "OVERLAY"
    elif 'special' in cat_lower:
        return "SPECIAL"
    else:
        return "OTHER"

# Step 6: Build zoning_codes rows
print("\nBuilding zoning_codes master...")
rows = []
seen = set()

for d in districts:
    jid = d.get('jurisdiction_id')
    j = jurisdictions.get(jid, {})
    county = (j.get('county') or 'unknown').lower()
    jurisdiction = (j.get('name') or 'unknown').lower()
    code = d.get('code', '')
    
    if not code:
        continue
    
    key = (county, jurisdiction, code)
    if key in seen:
        continue
    seen.add(key)
    
    # Get dimensional standards
    dim = dims_by_district.get(d['id'], {})
    
    # Get permitted uses as JSON
    district_uses = uses_by_district.get(d['id'], [])
    permitted_json = {}
    for u in district_uses:
        desc = u.get('use_description', '')
        if desc:
            permitted_json[desc] = u.get('use_type', 'permitted')
    
    # Build setbacks JSON
    setbacks = None
    if dim:
        setbacks = {}
        if dim.get('setback_front_ft'):
            setbacks['front'] = dim['setback_front_ft']
        if dim.get('setback_side_ft'):
            setbacks['side'] = dim['setback_side_ft']
        if dim.get('setback_rear_ft'):
            setbacks['rear'] = dim['setback_rear_ft']
        if not setbacks:
            setbacks = None
    
    row = {
        "county": county,
        "jurisdiction": jurisdiction,
        "zoning_code": code,
        "zoning_desc": d.get('name') or d.get('description') or code,
        "category": normalize_category(d.get('category')),
        "permitted_uses": json.dumps(permitted_json) if permitted_json else None,
        "max_height_ft": int(dim['max_height_ft']) if dim.get('max_height_ft') else None,
        "max_density": None,
        "min_lot_size": f"{int(dim['min_lot_size_sf'])} sqft" if dim.get('min_lot_size_sf') else None,
        "setbacks": json.dumps(setbacks) if setbacks else None,
        "municode_url": None
    }
    rows.append(row)

print(f"  {len(rows)} unique zoning codes to insert")

# Step 7: Insert in batches
batch_size = 200
total = 0
errors = 0

for i in range(0, len(rows), batch_size):
    batch = rows[i:i+batch_size]
    resp = requests.post(
        f"{SB_URL}/rest/v1/zoning_codes",
        headers={**H, "Prefer": "return=minimal,resolution=merge-duplicates"},
        json=batch
    )
    if resp.status_code in (200, 201):
        total += len(batch)
        sys.stdout.write(f"\r  Inserted: {total}/{len(rows)}")
        sys.stdout.flush()
    else:
        errors += 1
        if errors <= 3:
            print(f"\n  ⚠️ Batch {i}: {resp.status_code} {resp.text[:150]}")
    time.sleep(0.2)

print(f"\n\n✅ Zoning codes master populated: {total} codes across {len(set(r['county'] for r in rows))} counties")

# Stats
from collections import Counter
cats = Counter(r['category'] for r in rows)
counties = Counter(r['county'] for r in rows)
print(f"\nBy category:")
for c, n in cats.most_common():
    print(f"  {c:20} {n:5}")
print(f"\nBy county (top 15):")
for c, n in counties.most_common(15):
    print(f"  {c:25} {n:5}")
