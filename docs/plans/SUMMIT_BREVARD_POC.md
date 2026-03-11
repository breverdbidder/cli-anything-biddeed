# 🏔️ SUMMIT MISSION: CONQUER BREVARD COUNTY — ZONEWISE POC

## MISSION ORDER FROM CHIEF OF STAFF

```
╔══════════════════════════════════════════════════════════════╗
║  OPERATION: CONQUER THE LAND                                ║
║  OBJECTIVE: 85%+ zoning coverage for 133,350 Brevard parcels║
║  BENCHMARK: Match Malabar POC on ALL dimensions             ║
║  COST: $0 (public GIS + Firecrawl within plan)              ║
║  REPORT: Telegram at each phase completion                  ║
╚══════════════════════════════════════════════════════════════╝
```

---

## STEP 0: LOAD YOUR SQUAD (MANDATORY — DO THIS FIRST)

You are NOT working alone. You have 9 AI agents assigned to this mission.
Before writing ANY code, you MUST read each agent's full definition and
internalize their domain expertise, rules, and protocols.

```bash
# Clone agent definitions
git clone https://github.com/breverdbidder/agency-agents.git ~/agency-agents

# READ EACH ASSIGNED AGENT — absorb their expertise
echo "=== LOADING SQUAD ==="

echo "--- CAPTAIN: Pipeline Orchestrator ---"
cat ~/agency-agents/customized/biddeed-pipeline-orchestrator.md

echo "--- OPERATOR: Data Pipeline ETL ---"
cat ~/agency-agents/customized/biddeed-data-pipeline-agent.md

echo "--- SPECIALIST: Supabase Architect ---"
cat ~/agency-agents/customized/biddeed-supabase-architect.md

echo "--- SPECIALIST: Analytics ---"
cat ~/agency-agents/customized/biddeed-analytics-agent.md

echo "--- SPECIALIST: Security Auditor ---"
cat ~/agency-agents/customized/biddeed-security-auditor.md
```

After reading ALL 5 agents, confirm:
- Pipeline Orchestrator: what are the 5 pipeline phases it coordinates?
- Data Pipeline: what are the anti-detection rules (delays, UA rotation, robots.txt)?
- Supabase Architect: what are the upsert patterns and schema rules?
- Analytics: how does it validate coverage % and data quality?
- Security Auditor: what rate limits must be enforced?

DO NOT PROCEED until you have read all 5 agent definitions.

---

## STEP 1: CLONE REPOS + LOAD MALABAR BENCHMARK

```bash
# Clone all required repos
git clone https://github.com/breverdbidder/zonewise.git ~/zonewise
git clone https://github.com/breverdbidder/zonewise-scraper-v4.git ~/zonewise-scraper-v4
git clone https://github.com/breverdbidder/cli-anything-biddeed.git ~/cli-anything-biddeed

# Install CLI tools
cd ~/cli-anything-biddeed
pip install -e shared/
pip install -e zonewise/agent-harness/

# Verify CLI works
cli-anything-zonewise --json county list | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Counties: {d[\"count\"]}')"
```

### Understand the Malabar Benchmark

Malabar POC achieved 100% coverage on 1,430 parcels with:
- zone_code assigned to every parcel
- 13 zoning districts fully defined (RS-10, RR-65, RS-15, RS-21, RM-6, etc.)
- Dimensional standards per district (min_lot_size, max_height, setbacks)
- Permitted + conditional uses per district
- Demographics via Census API (median income, poverty rate, home values)
- Walk Score, School Score, Crime Score
- BCPAO property photos (masterPhotoUrl)

Check existing Malabar data in zonewise repo:
```bash
find ~/zonewise -name "*.json" -path "*malabar*" -o -name "*.json" -path "*data*" | head -20
cat ~/zonewise/data/malabar_zoning_districts.json 2>/dev/null || echo "Search for Malabar schema"
```

Also check Supabase for current state:
```bash
# Count parcels with zone_code assigned
curl -s "${SUPABASE_URL}/rest/v1/sample_properties?zone_code=not.is.null&select=count" \
  -H "apikey: ${SUPABASE_KEY}" -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Prefer: count=exact"

# Count total Brevard parcels
curl -s "${SUPABASE_URL}/rest/v1/sample_properties?county=eq.brevard&select=count" \
  -H "apikey: ${SUPABASE_KEY}" -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Prefer: count=exact"
```

---

## STEP 2: RECON — GIS ENUMERATION (Pipeline Orchestrator Phase 1)

Apply the **Pipeline Orchestrator** agent's Phase 1 protocol: parallel discovery.
Apply the **Security Auditor** agent's rate limiting: 2-5 second delays.

### 2a: Enumerate Unincorporated Brevard Zoning Districts

```bash
# BCPAO GIS MapServer — query all distinct zoning codes
# Filter by jurisdiction = Unincorporated
curl -s "https://gis.brevardfl.gov/gissrv/rest/services/Planning_Development/Zoning_WKID2881/MapServer/0/query?where=JUR%3D'UNINCORPORATED'&outFields=ZONING&returnDistinctValues=true&f=json"
```

Parse the response. Expect ~54 zoning districts for Unincorporated Brevard.
Store the list as JSON.

### 2b: Enumerate Titusville Zoning Districts

```bash
curl -s "https://gis.brevardfl.gov/gissrv/rest/services/Planning_Development/Zoning_WKID2881/MapServer/0/query?where=JUR%3D'TITUSVILLE'&outFields=ZONING&returnDistinctValues=true&f=json"
```

### 2c: Enumerate Cocoa Zoning Districts

```bash
curl -s "https://gis.brevardfl.gov/gissrv/rest/services/Planning_Development/Zoning_WKID2881/MapServer/0/query?where=JUR%3D'COCOA'&outFields=ZONING&returnDistinctValues=true&f=json"
```

### 2d: Report Recon via Telegram

```bash
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d chat_id="${TELEGRAM_CHAT_ID}" \
  -d text="🏔️ SUMMIT RECON COMPLETE
  
Unincorporated: X districts found
Titusville: X districts found  
Cocoa: X districts found
Total: X districts across 3 jurisdictions

Proceeding to Phase 2: Ordinance Scraping"
```

---

## STEP 3: SCRAPE ORDINANCES (Data Pipeline Agent Protocol)

Apply the **Data Pipeline** agent's Medallion architecture:
- Bronze: raw HTML/markdown from Municode
- Silver: structured JSON per district
- Gold: enriched with dimensional standards

Apply the **Security Auditor** agent's anti-detection:
- 2-5 second delays between requests
- User-Agent rotation (10+ realistic browsers)
- Respect robots.txt
- Max 1 concurrent request per domain

### 3a: Scrape Brevard County LDC from Municode

Use Firecrawl (Tier 1) to scrape:
```python
import httpx
import time
import os

FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY")

# Brevard County Land Development Code on Municode
# This covers ALL Unincorporated Brevard zoning
base_url = "https://library.municode.com/fl/brevard_county/codes/code_of_ordinances"

resp = httpx.post(
    "https://api.firecrawl.dev/v0/scrape",
    headers={"Authorization": f"Bearer {FIRECRAWL_KEY}"},
    json={"url": f"{base_url}?nodeId=PTIICOOR_CH62ZO"},
    timeout=60.0
)
# Parse the zoning chapter
```

### 3b: Extract Dimensional Standards Per District

For each zoning district found in RECON, extract:
- min_lot_size_sqft
- max_height_ft
- setbacks: front, rear, side (in feet)
- max_lot_coverage_pct
- FAR (floor area ratio)

Use Gemini Flash (FREE) for structured parsing if Firecrawl markdown needs interpretation.

### 3c: Extract Permitted + Conditional Uses

For each district:
- permitted_uses: list of allowed uses
- conditional_uses: list of uses requiring special approval
- prohibited_uses: explicitly banned uses

### 3d: Store in Supabase

Apply **Supabase Architect** agent protocol:
- Create `zoning_districts` table if not exists
- Schema: jurisdiction, zone_code, zone_name, category, min_lot_size, max_height, setbacks (jsonb), permitted_uses (jsonb), conditional_uses (jsonb), source_url
- Upsert on (jurisdiction, zone_code)

```bash
curl -s -X POST "${SUPABASE_URL}/rest/v1/rpc/execute_sql" \
  -H "apikey: ${SUPABASE_KEY}" -H "Authorization: Bearer ${SUPABASE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"query": "CREATE TABLE IF NOT EXISTS zoning_districts (...)"}'
```

### 3e: Telegram Phase 2 Report

---

## STEP 4: SPATIAL JOIN — ASSIGN ZONE CODES (Core Conquest)

This is the main conquest. For each of the 133,350 parcels, query the GIS
MapServer to get their zone_code and assign it.

Apply **Data Pipeline** agent's batch processing protocol.
Apply **Security Auditor** agent's rate limiting strictly.

### 4a: Query Strategy

The GIS MapServer supports spatial queries. Two approaches:

**Approach A — Parcel-by-parcel (slow but accurate):**
For each parcel with known lat/lon, query the zoning layer at that point.
Rate: ~1 query per 3 seconds = 1,200/hour = ~111 hours for 133K parcels.
TOO SLOW.

**Approach B — Bulk export by zone (fast):**
For each zoning district, query all parcels within that zone polygon.
Rate: ~54 queries for Unincorporated = done in minutes.
THIS IS THE WAY.

```python
import httpx
import time

GIS_BASE = "https://gis.brevardfl.gov/gissrv/rest/services/Planning_Development/Zoning_WKID2881/MapServer/0"

# Get all parcels for a specific zone in a specific jurisdiction
def get_parcels_for_zone(jurisdiction, zone_code, offset=0, batch=1000):
    """Query GIS for all parcel IDs in a zone. Paginate with resultOffset."""
    where = f"JUR='{jurisdiction}' AND ZONING='{zone_code}'"
    params = {
        "where": where,
        "outFields": "PARCELID,ZONING,JUR",
        "returnGeometry": "false",
        "resultOffset": offset,
        "resultRecordCount": batch,
        "f": "json"
    }
    resp = httpx.get(f"{GIS_BASE}/query", params=params, timeout=30)
    return resp.json()

# Iterate all zones for Unincorporated Brevard
for zone in unincorporated_zones:
    offset = 0
    while True:
        data = get_parcels_for_zone("UNINCORPORATED", zone, offset)
        features = data.get("features", [])
        if not features:
            break
        
        # Batch of parcel_ids with their zone_code
        parcels = [{"parcel_id": f["attributes"]["PARCELID"], "zone_code": zone} for f in features]
        
        # Upsert to Supabase
        upsert_to_supabase(parcels)
        
        offset += len(features)
        time.sleep(2)  # Security Auditor: rate limit
```

### 4b: Repeat for Titusville and Cocoa

Same approach, different JUR filter.

### 4c: Telegram Phase 3 Report

Report: X parcels zoned out of 133,350 target. X% coverage.

---

## STEP 5: PROPERTY PHOTOS — BCPAO masterPhotoUrl

For every parcel, fetch the property photo URL from BCPAO API.

```python
import httpx
import time

def get_bcpao_photo(parcel_account):
    """Fetch masterPhotoUrl from BCPAO API."""
    # Clean parcel ID: remove dashes, asterisks
    account = parcel_account.replace("-", "").replace("*", "").replace(" ", "")
    
    resp = httpx.get(
        f"https://www.bcpao.us/api/v1/search?account={account}",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15
    )
    if resp.status_code == 200:
        data = resp.json()
        if isinstance(data, list) and data:
            return data[0].get("masterPhotoUrl")
        elif isinstance(data, dict):
            return data.get("masterPhotoUrl")
    return None

# Batch process — Security Auditor: 2-5 second delays
for parcel in parcels_needing_photos:
    photo_url = get_bcpao_photo(parcel["parcel_id"])
    if photo_url:
        update_supabase(parcel["id"], {"photo_url": photo_url})
    time.sleep(3)  # Rate limit
```

IMPORTANT: This is the slowest phase. At 3 seconds per parcel, 133K parcels = ~111 hours.
Strategy: Prioritize improved properties (more likely to have photos).
Query BCPAO for property type first, skip vacant land photo lookups.

Alternative batch approach if BCPAO has bulk endpoints — check first:
```bash
curl -s "https://www.bcpao.us/api/v1/search?address=&zip=32780&limit=100" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))"
```

### Telegram Phase 4 Report

---

## STEP 6: DEMOGRAPHICS + SCORES (Enrichment)

Apply **Analytics** agent protocol for validation.

### 6a: Census API Demographics

For each new census tract covered by the Tier 1 parcels:
```python
# Census ACS 5-Year API (free, key in CENSUS_API_KEY or use without for lower limits)
VARIABLES = "B19013_001E,B25077_001E,B17001_002E,B01001_001E"
# median_household_income, median_home_value, poverty_count, total_population

import httpx
resp = httpx.get(
    f"https://api.census.gov/data/2023/acs/acs5?get={VARIABLES}&for=tract:*&in=state:12+county:009"
)
# state 12 = Florida, county 009 = Brevard
```

### 6b: Walk / School / Crime Scores

Apply same methodology as Malabar POC:
- Walk Score: rural Brevard = low (car-dependent), use centroid + WalkScore API or estimate
- School Score: Florida DOE school grades, map to nearest schools
- Crime Score: Brevard County crime rate vs Florida average

### Telegram Phase 5 Report

---

## STEP 7: VALIDATE + FINAL REPORT (Analytics Agent Protocol)

Apply **Analytics** agent's validation checklist:

```python
# Coverage validation
total_target = 133350
zoned_count = query_supabase_count("zone_code is not null AND jurisdiction in ('UNINCORPORATED','TITUSVILLE','COCOA')")
coverage_pct = zoned_count / total_target * 100

# Quality checks
null_rate_zone = query_null_rate("zone_code")
null_rate_photo = query_null_rate("photo_url") 
districts_with_dims = query_count("zoning_districts where min_lot_size is not null")
total_districts = query_count("zoning_districts")

# Compare to Malabar benchmark
malabar_coverage = 100.0  # Our benchmark
```

### Final Telegram Report:

```
🏔️ SUMMIT COMPLETE: BREVARD COUNTY CONQUERED

📊 COVERAGE:
  Unincorporated: X/75,350 (X%)
  Titusville: X/28,118 (X%)  
  Cocoa: X/29,882 (X%)
  TOTAL: X/133,350 (X%)

📋 ZONING DISTRICTS:
  Unincorporated: X districts
  Titusville: X districts
  Cocoa: X districts
  With dimensional standards: X/X

📸 PHOTOS:
  Fetched: X photo URLs
  Properties with photos: X%

📈 vs MALABAR BENCHMARK:
  Malabar: 1,430 parcels, 100% coverage, 13 districts
  Tier 1: X parcels, X% coverage, X districts

✅ SAFEGUARD: X% (target: 85%+)
```

---

## CREDENTIALS

```bash
export SUPABASE_URL="https://mocerqjnksmhcjzxrewo.supabase.co"
# SUPABASE_KEY from env or ~/SUPABASE_CREDENTIALS.md (service role, ends ...Tqp9nE)
# FIRECRAWL_API_KEY from env (starts fc-)
# TELEGRAM_BOT_TOKEN from env
# TELEGRAM_CHAT_ID from env
# GIS endpoints are PUBLIC — no auth needed
# BCPAO API is PUBLIC — no auth needed
# Census API works without key (lower rate limit) or use CENSUS_API_KEY if available
```

## CONSTRAINTS

- Security Auditor rules: 2-5s delays between same-domain requests
- No aggressive scraping — max 1 concurrent request per domain
- Use Approach B (bulk zone export) NOT Approach A (parcel-by-parcel)
- Checkpoint progress to Supabase after each phase
- If any phase fails, report to Telegram and continue with next phase
- Total session budget: $0 API cost (GIS=free, Census=free, BCPAO=free, Firecrawl=within plan)
