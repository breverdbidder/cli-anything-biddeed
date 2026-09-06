#!/bin/bash
# One-time (per new company/environment) Odoo database init: creates the Postgres DB via
# odoo-bin's own -i (install) bootstrap, which is the standard non-interactive way to stand
# up a fresh Odoo DB when list_db=False hides the web /web/database/manager wizard.
# Run from infra/odoo/ on the box, after `docker compose up -d odoo-db`.
set -euo pipefail

: "${ODOO_DB_NAME:?ODOO_DB_NAME not set}"

echo "$(date -u +%FT%TZ) initializing Odoo database '${ODOO_DB_NAME}' (project, account, purchase, documents, analytic, deed_budget)"
docker compose run --rm odoo \
  odoo -d "$ODOO_DB_NAME" \
  -i project,account,purchase,documents,analytic,deed_budget \
  --without-demo=all \
  --stop-after-init

echo "$(date -u +%FT%TZ) init complete — restart the odoo service to pick up the new DB: docker compose restart odoo"
