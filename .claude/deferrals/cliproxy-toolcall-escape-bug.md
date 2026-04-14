---
priority: P1
status: deferred
owner: claude-architect
blocker: cliproxy-Anthropic-to-Gemini-Write-tool-escape
dependency: none
minutes: 45
tags: [summit, cliproxy, tool-use, gemini]
created: 2026-04-14
---

# Cliproxy tool-call newline escape bug

## Root cause
When Claude Code sends a Write tool_call with multi-line content, the cliproxy Anthropic→Gemini translation layer double-escapes newline characters. File content arrives at the Write tool with literal backslash-n sequences instead of newlines, producing TypeScript that will not parse.

## Evidence
- SUMMIT #90 (zonewise-web PR #87): Gemini 2.5 Flash broken file, closed
- SUMMIT #91 (zonewise-web PR #88): Gemini 2.5 Pro IDENTICAL broken file, closed
- Delta variable: model tier (flash vs pro) — no effect
- Constant: cliproxy translation layer
- Conclusion: bug is in cliproxy, not the model

## Working path (proven by SUMMIT #89 canary)
Bash tool calls DO work correctly through cliproxy. SUMMIT #89 (issue #475) successfully ran uname, git clone, head, and multi-command bash pipelines, producing correct verbatim output.

## Two fix paths

### Path 1: Bash-heredoc workaround (~20 min)
Prompt template that forbids Write/Edit tools, forces cat heredoc patterns for file writes. Bypasses the escape issue because bash strings do not route through the same tool_call translation.

### Path 2: Cliproxy source patch (~60 min)
Clone cliproxy repo, locate Anthropic→Gemini request translator, add explicit unescape step for tool_call.input fields, rebuild docker image.

## Next session spec
- Title: SUMMIT bash-heredoc code-edit workaround
- Budget: 30 min
- Success: mergeable PR on zonewise-web with proper multi-line TS code
- Target: re-attempt the Mapbox check on /api/health/route.ts
- Strategy: explicit bash-only prompt, forbid Write/Edit tools

## Session context
Session 2026-04-14. Sprint around SUMMIT cliproxy recovery. 5 PRs merged, 2 SUMMITs succeeded (canary #89 + #91), 2 SUMMITs produced broken code (#90 + #91 code quality), 1 key rotation blocked.
