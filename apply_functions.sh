#!/bin/bash

# Apply the tier1 promotion and queue functions via curl POST to database

SUPABASE_URL="https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vY2VycWpua3NtaGNqenhyZXdvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTcxODEzNTQwMywiZXhwIjoyMDMzNzExNDAzfQ.Gf-cZyO5WQOd6qXbIXTnfQRGjgBgWVoZbJO2LoN_pTc"

echo "=== Applying Gold Standard Functions ==="

# Test connection first
echo "Testing connection..."
curl -s -H "apikey: $SUPABASE_KEY" \
     -H "Authorization: Bearer $SUPABASE_KEY" \
     "$SUPABASE_URL/rest/v1/fl_counties?select=count&limit=1" | head -20

echo -e "\n\n=== Running tier1 promotion function ==="

# Try to run the promotion function
result=$(curl -s -X POST "$SUPABASE_URL/rest/v1/rpc/promote_tier1_from_outcomes" \
    -H "apikey: $SUPABASE_KEY" \
    -H "Authorization: Bearer $SUPABASE_KEY" \
    -H "Content-Type: application/json" \
    -d '{}')

echo "Promotion result: $result"

echo -e "\n\n=== Running Brevard queue feeder ==="

# Try to run the queue feeder
queue_result=$(curl -s -X POST "$SUPABASE_URL/rest/v1/rpc/feed_acclaim_queue_brevard" \
    -H "apikey: $SUPABASE_KEY" \
    -H "Authorization: Bearer $SUPABASE_KEY" \
    -H "Content-Type: application/json" \
    -d '{}')

echo "Queue feeder result: $queue_result"

echo -e "\n\n=== Functions application complete ==="