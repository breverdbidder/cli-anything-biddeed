#!/bin/bash
# One-shot: apply bay C/D/I/J migration (run6253) to live Supabase
# dispatch_id: 0c4df455-e5d2-4d65-9237-0d35132b0e53
# Usage: bash scripts/apply_bay_cdij_now.sh
set -euo pipefail

REF="mocerqjnksmhcjzxrewo"
TOKEN="${SUPABASE_ACCESS_TOKEN:-}"

if [ -z "$TOKEN" ]; then
  echo "ERROR: SUPABASE_ACCESS_TOKEN not set"
  exit 1
fi

MIGRATION="$(dirname "$0")/../supabase/migrations/20260724_gold_standard_shard9_bay_cdij_run6253.sql"

if [ ! -f "$MIGRATION" ]; then
  echo "ERROR: Migration file not found: $MIGRATION"
  exit 1
fi

echo "=== BEFORE STATE ==="
SQL_BEFORE='SELECT public.pencil_dod_evaluate_county('"'"'bay'"'"');'
python3 -c "import json; print(json.dumps({'query': '$SQL_BEFORE'}))" > /tmp/before.json
curl -sS -o /tmp/before_resp.json -w "HTTP %{http_code}\n" \
  -X POST "https://api.supabase.com/v1/projects/${REF}/database/query" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d @/tmp/before.json
cat /tmp/before_resp.json
echo

echo "=== APPLYING MIGRATION ==="
python3 -c "import json; sql=open('$MIGRATION').read(); print(json.dumps({'query': sql}))" > /tmp/payload.json
HTTP=$(curl -sS -o /tmp/resp.json -w "%{http_code}" \
  -X POST "https://api.supabase.com/v1/projects/${REF}/database/query" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d @/tmp/payload.json)
echo "HTTP: $HTTP"
cat /tmp/resp.json
echo

if [[ "$HTTP" == "200" || "$HTTP" == "201" ]]; then
  echo "Migration applied successfully!"
else
  echo "ERROR: Migration failed HTTP $HTTP"
  exit 1
fi

echo "=== AFTER STATE ==="
python3 -c "import json; print(json.dumps({'query': '$SQL_BEFORE'}))" > /tmp/after.json
curl -sS -o /tmp/after_resp.json -w "HTTP %{http_code}\n" \
  -X POST "https://api.supabase.com/v1/projects/${REF}/database/query" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d @/tmp/after.json
cat /tmp/after_resp.json
