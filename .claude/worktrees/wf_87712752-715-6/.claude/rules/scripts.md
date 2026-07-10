---
pattern: "scripts/**"
---
# Scripts Rules

- setup-claude-hygiene.sh is canonical for session setup across all repos
- sentinel.sh + sentinel-patrol.sh: NEVER modify without testing locally first
- All scripts: set -euo pipefail at top. No silent failures
- Telegram notifications: use bot API, never log tokens in output
- Weekly health check: Sundays 9AM EST. Staleness alert if >7d no commits
- Token/secret handling: never echo secrets. Use env vars or /tmp/ files only
- Exit codes: 0=success, 1=failure, 2=partial (some items failed)
