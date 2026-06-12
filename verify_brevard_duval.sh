#!/bin/bash
# BREVARD & DUVAL BASELINE VERIFICATION
# Quick shell script to verify current state using curl

set -e

# Supabase configuration from environment
SUPABASE_URL="${SUPABASE_URL:-https://mocerqjnksmhcjzxrewo.supabase.co}"

echo "🔍 BREVARD & DUVAL GOLD STANDARD BASELINE VERIFICATION"
echo "Timestamp: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""

# Check if we have the required API key
if [ -z "$SUPABASE_KEY" ] && [ -z "$SUPABASE_SERVICE_KEY" ]; then
    echo "❌ No SUPABASE_KEY or SUPABASE_SERVICE_KEY found in environment"
    exit 1
fi

# Use whichever key is available
API_KEY="${SUPABASE_KEY:-$SUPABASE_SERVICE_KEY}"

echo "✅ API key available"
echo "Using Supabase URL: $SUPABASE_URL"
echo ""

# Function to make authenticated requests
function sb_request() {
    local endpoint="$1"
    local data="$2"
    
    if [ -n "$data" ]; then
        # POST request
        curl -s -X POST \
            -H "apikey: $API_KEY" \
            -H "Authorization: Bearer $API_KEY" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$SUPABASE_URL/rest/v1/$endpoint"
    else
        # GET request
        curl -s \
            -H "apikey: $API_KEY" \
            -H "Authorization: Bearer $API_KEY" \
            "$SUPABASE_URL/rest/v1/$endpoint"
    fi
}

echo "📡 Testing database connection..."
# Test basic connectivity
conn_test=$(sb_request "fl_counties?select=count&limit=1" | jq -r 'length // "error"' 2>/dev/null || echo "error")

if [ "$conn_test" = "error" ]; then
    echo "❌ Database connection failed"
    exit 1
fi

echo "✅ Database connection successful"
echo ""

# Try to evaluate counties using the RPC function
echo "📊 COUNTY EVALUATIONS"
echo ""

for county in brevard duval; do
    echo "--- Evaluating $county ---"
    
    # Try the pencil_dod_evaluate_county function
    eval_result=$(sb_request "rpc/pencil_dod_evaluate_county" '{"county_slug_arg":"'"$county"'"}' 2>/dev/null || echo "[]")
    
    # Parse the result
    if [ "$eval_result" = "[]" ] || [ -z "$eval_result" ]; then
        echo "⚠️ $county: RPC evaluation failed or returned empty"
        
        # Try basic metrics queries as fallback
        echo "   Attempting basic metrics..."
        
        # Get auction count
        auction_count=$(sb_request "multi_county_auctions?county=eq.$county&select=count" | jq 'length // 0' 2>/dev/null || echo "0")
        echo "   Total auctions: $auction_count"
        
    else
        echo "✅ $county: RPC evaluation successful"
        
        # Parse letter grades if possible
        pass_count=$(echo "$eval_result" | jq '[.[] | select(.pass == true)] | length' 2>/dev/null || echo "unknown")
        total_letters=$(echo "$eval_result" | jq 'length' 2>/dev/null || echo "unknown")
        
        echo "   Pass count: $pass_count/$total_letters"
        
        # Show letter details
        for letter in A B C D E F G H I J; do
            letter_lower=$(echo "$letter" | tr '[:upper:]' '[:lower:]')
            letter_data=$(echo "$eval_result" | jq -r '.[] | select(.letter == "'$letter_lower'") | "\(.pass // false)|\(.metric // "N/A")"' 2>/dev/null)
            
            if [ -n "$letter_data" ] && [ "$letter_data" != "" ]; then
                pass_status=$(echo "$letter_data" | cut -d'|' -f1)
                metric=$(echo "$letter_data" | cut -d'|' -f2)
                
                if [ "$pass_status" = "true" ]; then
                    status="✅ PASS"
                else
                    status="❌ FAIL"
                fi
                
                echo "   Letter $letter: $status ($metric)"
            fi
        done
    fi
    echo ""
done

echo "="*60
echo "BASELINE VERIFICATION COMPLETE"
echo "Timestamp: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""
echo "Next steps:"
echo "1. Analyze failing criteria for each county"
echo "2. Implement targeted fixes per priority (B+F for Brevard, C+D for Duval)"
echo "3. Execute pipeline improvements"
echo "="*60