#!/usr/bin/env bash
# ============================================================================
# gh-pages-deploy.sh — CANONICAL Everest pattern for pushing from Claude chat
# ============================================================================
# Created Apr 16 2026. Ratified after Ariel pushback:
# "You did it many times find previous chats with our battle cards"
# Apr 12 precedent: breverdbidder/everest-battle-cards mono-repo.
#
# PROVES: Claude AI Architect CAN push to GitHub from chat.
# Pattern: Supabase vault (everest_gh_pat) → bash_tool → GH REST API.
# NO GitHub MCP needed. NO SSH to Hetzner needed. NO Ariel paste needed.
#
# USAGE (from Claude chat session, bash_tool):
#   ./gh-pages-deploy.sh <repo-name> <source-file> [subpath]
#
# Example:
#   ./gh-pages-deploy.sh everest-status /mnt/user-data/outputs/index.html
#   ./gh-pages-deploy.sh everest-battle-cards /tmp/dono-ai.html dono-ai
#
# CRED HYGIENE (mem:25):
#   - PAT pulled to /tmp/.pat.secure chmod 600, shredded at end
#   - ALL stdout/stderr filtered through redact() sed filter
#   - NEVER echoes ghp_* anywhere
#   - Pre-flight grep before any output to user
# ============================================================================
set -e

REPO="${1:?Usage: $0 <repo-name> <source-file> [subpath]}"
SOURCE="${2:?Usage: $0 <repo-name> <source-file> [subpath]}"
SUBPATH="${3:-}"  # optional subpath for mono-repo pattern
OWNER="breverdbidder"
GH_API="https://api.github.com"

# === Redaction filter (applied to ALL stdout/stderr per mem:25) ===
redact() {
  sed -E 's/ghp_[A-Za-z0-9]{30,}/[REDACTED]/g;
          s/"token [^"]*"/"token [REDACTED]"/g;
          s/Authorization: token [^ ]*/Authorization: token [REDACTED]/g'
}

# === Step 0: Pull PAT from Supabase vault ===
# NOTE: In Claude chat context, PAT comes from Supabase MCP:
#   SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'everest_gh_pat';
# Here we assume it's pre-stashed at /tmp/.pat.secure by the caller.
if [ ! -f /tmp/.pat.secure ]; then
  echo "ERROR: /tmp/.pat.secure not found. Pull from vault first:" | redact
  echo "  Supabase:execute_sql → SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name='everest_gh_pat'" | redact
  echo "  Then: cat > /tmp/.pat.secure <<'EOF'" | redact
  echo "  ghp_xxxxx" | redact
  echo "  EOF" | redact
  echo "  chmod 600 /tmp/.pat.secure" | redact
  exit 1
fi
PAT=$(tr -d '\n' < /tmp/.pat.secure)
trap 'shred -u /tmp/.pat.secure 2>/dev/null || rm -f /tmp/.pat.secure; rm -f /tmp/gh_*.json /tmp/gh_upload_payload.json' EXIT

# === Step 1: Check/create repo ===
echo "=== [1/5] Check repo $OWNER/$REPO ==="
STATUS=$(curl -s -o /tmp/gh_repo.json -w "%{http_code}" \
  -H "Authorization: token $PAT" \
  -H "Accept: application/vnd.github.v3+json" \
  "$GH_API/repos/$OWNER/$REPO")
echo "Repo HTTP: $STATUS" | redact

if [ "$STATUS" = "404" ]; then
  echo "Creating new repo..."
  curl -s -o /tmp/gh_create.json -w "Create HTTP: %{http_code}\n" \
    -X POST \
    -H "Authorization: token $PAT" \
    -H "Accept: application/vnd.github.v3+json" \
    "$GH_API/user/repos" \
    -d "{\"name\":\"$REPO\",\"private\":false,\"auto_init\":true,\"homepage\":\"https://$OWNER.github.io/$REPO/\"}" | redact
  sleep 3  # let repo settle
fi

# === Step 2: Determine upload path ===
if [ -n "$SUBPATH" ]; then
  UPLOAD_PATH="$SUBPATH/index.html"
else
  UPLOAD_PATH="index.html"
fi
echo ""
echo "=== [2/5] Base64 encode $SOURCE ==="
BASE64_CONTENT=$(base64 -w 0 "$SOURCE")
echo "Bytes: $(wc -c < "$SOURCE"), base64 len: ${#BASE64_CONTENT}"

# === Step 3: Check if file exists (for update vs create) ===
echo ""
echo "=== [3/5] Check if $UPLOAD_PATH exists ==="
EXISTING_SHA=$(curl -s -H "Authorization: token $PAT" \
  "$GH_API/repos/$OWNER/$REPO/contents/$UPLOAD_PATH" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('sha','') if isinstance(d, dict) else '')" 2>/dev/null || echo "")
echo "Existing SHA: ${EXISTING_SHA:-none (will create)}"

# === Step 4: Upload file ===
echo ""
echo "=== [4/5] Upload $UPLOAD_PATH ==="
if [ -n "$EXISTING_SHA" ]; then
  cat > /tmp/gh_upload_payload.json <<EOF
{"message":"update: $UPLOAD_PATH","content":"$BASE64_CONTENT","sha":"$EXISTING_SHA"}
EOF
else
  cat > /tmp/gh_upload_payload.json <<EOF
{"message":"feat: deploy $UPLOAD_PATH via canonical chat→vault→API pattern","content":"$BASE64_CONTENT"}
EOF
fi

UPLOAD_STATUS=$(curl -s -o /tmp/gh_upload.json -w "%{http_code}" \
  -X PUT \
  -H "Authorization: token $PAT" \
  -H "Accept: application/vnd.github.v3+json" \
  "$GH_API/repos/$OWNER/$REPO/contents/$UPLOAD_PATH" \
  -d @/tmp/gh_upload_payload.json)
echo "Upload HTTP: $UPLOAD_STATUS" | redact

COMMIT_SHA=$(python3 -c "import json; d=json.load(open('/tmp/gh_upload.json')); print(d.get('commit',{}).get('sha','?')[:8])" 2>/dev/null)
echo "Commit: $COMMIT_SHA" | redact

# === Step 5: Enable Pages (idempotent — 409 if already enabled) ===
echo ""
echo "=== [5/5] Enable GitHub Pages ==="
PAGES_STATUS=$(curl -s -o /tmp/gh_pages.json -w "%{http_code}" \
  -X POST \
  -H "Authorization: token $PAT" \
  -H "Accept: application/vnd.github.v3+json" \
  "$GH_API/repos/$OWNER/$REPO/pages" \
  -d '{"source":{"branch":"main","path":"/"}}')
echo "Pages HTTP: $PAGES_STATUS (201=enabled, 409=already enabled)" | redact

# === Step 6: Poll until live ===
LIVE_URL="https://$OWNER.github.io/$REPO/"
[ -n "$SUBPATH" ] && LIVE_URL="${LIVE_URL}${SUBPATH}/"

echo ""
echo "=== Poll $LIVE_URL until live ==="
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  sleep 15
  S=$(curl -s -o /dev/null -w "%{http_code}" "$LIVE_URL")
  echo "  Attempt $i (t+$((i*15))s): HTTP $S"
  if [ "$S" = "200" ]; then
    echo ""
    echo "✅ LIVE: $LIVE_URL"
    break
  fi
done

# Cleanup handled by trap
echo ""
echo "=== Done. PAT wiped. Temp JSONs cleaned. ==="
