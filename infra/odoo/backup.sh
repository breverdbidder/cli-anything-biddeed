#!/bin/bash
# Nightly pg_dump of the Odoo database, uploaded to Cloudflare R2 (S3-compatible),
# 30-day retention. Runs inside the odoo-backup service (see docker-compose.yml),
# invoked by cron at 03:00 box-local time.
set -euo pipefail

: "${ODOO_DB_NAME:?ODOO_DB_NAME not set}"
: "${R2_BUCKET:?R2_BUCKET not set}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

if [ -z "${R2_ACCOUNT_ID:-}" ] || [ -z "${R2_ACCESS_KEY_ID:-}" ] || [ -z "${R2_SECRET_ACCESS_KEY:-}" ]; then
  echo "$(date -u +%FT%TZ) R2 credentials not configured (R2_ACCOUNT_ID/R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY) — skipping backup, dump stays local only" >&2
  exit 0
fi

STAMP="$(date -u +%Y%m%d_%H%M%S)"
DUMP_FILE="/backup/odoo_${ODOO_DB_NAME}_${STAMP}.dump"
ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

export AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION="auto"

echo "$(date -u +%FT%TZ) dumping ${ODOO_DB_NAME} -> ${DUMP_FILE}"
pg_dump -Fc -d "$ODOO_DB_NAME" -f "$DUMP_FILE"

echo "$(date -u +%FT%TZ) uploading to r2://${R2_BUCKET}/odoo-backups/$(basename "$DUMP_FILE")"
aws --endpoint-url "$ENDPOINT" s3 cp "$DUMP_FILE" "s3://${R2_BUCKET}/odoo-backups/$(basename "$DUMP_FILE")"
rm -f "$DUMP_FILE"

echo "$(date -u +%FT%TZ) pruning objects older than ${RETENTION_DAYS}d"
CUTOFF_EPOCH=$(( $(date -u +%s) - RETENTION_DAYS * 86400 ))
aws --endpoint-url "$ENDPOINT" s3api list-objects-v2 --bucket "$R2_BUCKET" --prefix "odoo-backups/" \
  --query 'Contents[].[Key,LastModified]' --output text 2>/dev/null | while read -r KEY MODIFIED; do
  [ -z "${KEY:-}" ] && continue
  MODIFIED_EPOCH=$(date -u -d "$MODIFIED" +%s 2>/dev/null || echo 0)
  if [ "$MODIFIED_EPOCH" -lt "$CUTOFF_EPOCH" ] && [ "$MODIFIED_EPOCH" -gt 0 ]; then
    echo "$(date -u +%FT%TZ) deleting expired backup: $KEY"
    aws --endpoint-url "$ENDPOINT" s3 rm "s3://${R2_BUCKET}/${KEY}"
  fi
done

echo "$(date -u +%FT%TZ) backup complete"
