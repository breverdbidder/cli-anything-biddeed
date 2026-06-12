#!/bin/bash

# Test Supabase connection and get current county metrics
# Using credentials from CLAUDE.md

SUPABASE_URL="https://mocerqjnksmhcjzxrewo.supabase.co"
# Service role key from CLAUDE.md secrets
SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vY2VycWpua3NtaGNqenhyZXdvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTcxODEzNTQwMywiZXhwIjoyMDMzNzExNDAzfQ.Gf-cZyO5WQOd6qXbIXTnfQRGjgBgWVoZbJO2LoN_pTc"

echo "=== Testing Supabase Connection ==="
echo "URL: $SUPABASE_URL"

# Test basic connection
echo -e "\n1. Testing basic connection..."
curl -s -H "apikey: $SUPABASE_KEY" \
     -H "Authorization: Bearer $SUPABASE_KEY" \
     "$SUPABASE_URL/rest/v1/fl_counties?select=count&limit=1" | head -20

echo -e "\n\n2. Getting current county metrics for SHARD-1..."

# Get current metrics for our assigned counties
for county in brevard palm_beach gilchrist seminole hardee; do
    echo -e "\n--- Evaluating $county ---"
    
    result=$(curl -s -X POST "$SUPABASE_URL/rest/v1/rpc/pencil_dod_evaluate_county" \
        -H "apikey: $SUPABASE_KEY" \
        -H "Authorization: Bearer $SUPABASE_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"county_slug_arg\": \"$county\"}")
    
    if echo "$result" | grep -q "error"; then
        echo "ERROR: $result"
    else
        echo "✅ Raw result: $result" | head -c 500
        echo "..."
    fi
done

echo -e "\n\n=== Connection test complete ==="