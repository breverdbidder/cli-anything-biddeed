#!/bin/bash

# Quick check of SHARD-1 county status using curl
SUPABASE_URL="https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vY2VycWpua3NtaGNqenhyZXdvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTcxODEzNTQwMywiZXhwIjoyMDMzNzExNDAzfQ.Gf-cZyO5WQOd6qXbIXTnfQRGjgBgWVoZbJO2LoN_pTc"

echo "=== SHARD-1 County Status Check ==="
echo "Counties: brevard, palm_beach, gilchrist, seminole, hardee"
echo ""

# Test basic connection
echo "Testing connection..."
curl -s -H "apikey: $SUPABASE_KEY" \
     -H "Authorization: Bearer $SUPABASE_KEY" \
     "$SUPABASE_URL/rest/v1/fl_counties?select=count&limit=1" | head -20

echo ""
echo ""

# Check current county evaluations
for county in brevard palm_beach gilchrist seminole hardee; do
    echo "=== $county ==="
    
    result=$(curl -s -X POST "$SUPABASE_URL/rest/v1/rpc/pencil_dod_evaluate_county" \
        -H "apikey: $SUPABASE_KEY" \
        -H "Authorization: Bearer $SUPABASE_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"county_name\": \"$county\"}")
    
    echo "Result: $result" | head -c 300
    echo ""
    echo ""
done