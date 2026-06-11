#!/bin/bash
# Trigger county ingestion for Franklin and Union counties to achieve Letter A
# These counties currently have 0/10 pass rate

set -e

echo "🏔️ GOLD STANDARD SHARD-10: Triggering county ingestion for 0/10 counties"

# Franklin County (CO_NO 29)
echo "Triggering Franklin County (29) full ingestion..."
gh workflow run summit-ingest-county.yml -f county=29 -f mode=full

# Union County (CO_NO 73)  
echo "Triggering Union County (73) full ingestion..."
gh workflow run summit-ingest-county.yml -f county=73 -f mode=full

echo "✅ Dispatched ingestion for Franklin (29) and Union (73)"
echo "This should move Letter A from FAIL to PASS for both counties"

# Wait a bit for the workflows to start
sleep 10

# Check workflow status
echo ""
echo "📊 Recent workflow runs:"
gh run list --limit 5 --workflow summit-ingest-county.yml

echo ""
echo "⏳ Monitor the ingestion progress at:"
echo "https://github.com/breverdbidder/cli-anything-biddeed/actions/workflows/summit-ingest-county.yml"