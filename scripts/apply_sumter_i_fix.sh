#!/bin/bash
# Apply sumter I reverse-geocode fix migration
# Run from repo root: bash scripts/apply_sumter_i_fix.sh
# Requires: SUPABASE_ACCESS_TOKEN and SUPABASE_URL env vars
set -euo pipefail

REF="mocerqjnksmhcjzxrewo"
MIGRATION="supabase/migrations/20260725_sumter_i_d29a024_reverse_geocode_address.sql"

if [ -z "${SUPABASE_ACCESS_TOKEN:-}" ]; then
  echo "ERROR: SUPABASE_ACCESS_TOKEN not set"
  exit 1
fi

echo "=== Applying: $MIGRATION ==="
python3 -c "import json; print(json.dumps({'query': open('${MIGRATION}').read()}))" > /tmp/sumter_payload.json
HTTP=$(curl -sS -o /tmp/sumter_resp.json -w "%{http_code}" \
  -X POST "https://api.supabase.com/v1/projects/${REF}/database/query" \
  -H "Authorization: Bearer ${SUPABASE_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  --data-binary @/tmp/sumter_payload.json)
echo "HTTP: $HTTP"
cat /tmp/sumter_resp.json
echo
if [[ "$HTTP" != "200" && "$HTTP" != "201" ]]; then
  echo "ERROR: Migration failed with HTTP $HTTP"
  exit 1
fi
echo "Migration applied OK"

echo ""
echo "=== Verifying D29A024 row ==="
python3 -c "import json; print(json.dumps({'query': \"SELECT id, case_number, parcel_id, property_address, round(latitude::numeric,6) AS lat, assessed_value FROM multi_county_auctions WHERE county='sumter' AND case_number='2025-CA-000255'\"}))" > /tmp/sumter_verify.json
curl -sS -X POST "https://api.supabase.com/v1/projects/${REF}/database/query" \
  -H "Authorization: Bearer ${SUPABASE_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  --data-binary @/tmp/sumter_verify.json
echo

echo ""
echo "=== pencil_dod_evaluate_county('sumter') ==="
python3 -c "import json; print(json.dumps({'query': \"SELECT public.pencil_dod_evaluate_county('sumter')\"}))" > /tmp/sumter_eval.json
curl -sS -X POST "https://api.supabase.com/v1/projects/${REF}/database/query" \
  -H "Authorization: Bearer ${SUPABASE_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  --data-binary @/tmp/sumter_eval.json
echo
