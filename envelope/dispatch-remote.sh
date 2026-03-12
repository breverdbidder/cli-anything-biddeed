#!/usr/bin/env bash
# ============================================================================
# REMOTE CONTROL DISPATCH — Fire from claude.ai or mobile
# ============================================================================
# Usage: In Claude Code, run: /rc  (or: claude remote-control)
# Then paste the prompt below into claude.ai or mobile app
# ============================================================================

cat << 'PROMPT'
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PASTE THIS INTO CLAUDE.AI REMOTE CONTROL OR MOBILE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Summit: Deploy Envelope Squad.

1. cd ~/repos/cli-anything-biddeed && git pull
2. Read envelope/CLAUDE.md and envelope/TODO.md
3. Execute TODO.md phases 1-3:
   - Run Supabase migration (001_envelope_cache.sql)
   - Test all 7 agents individually on palm_bay
   - Run full pipeline: ./cli_anything.envelope.sh palm_bay
4. Mark completed tasks [x] in TODO.md, push after each phase
5. Report results when done

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROMPT
