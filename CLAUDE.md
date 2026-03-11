# CLAUDE.md — CLI-Anything BidDeed Fork

## Identity
This is a fork of [HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything) adapted for BidDeed.AI's foreclosure auction and zoning intelligence stack.

## Architecture
- **HARNESS.md**: Upstream SOP for building CLI harnesses. Read it before every session.
- **BIDDEED_OVERLAY.md**: Our stack-specific extensions (Supabase, cost tracking, audit logging, GitHub Actions).
- **cli-anything-plugin/**: Upstream plugin (do not modify).
- **shared/cli_anything_shared/**: Shared utilities (supabase, cost, audit, config).
- **zonewise/agent-harness/**: ZoneWise Scraper CLI (`cli-anything-zonewise`).
- **auction/agent-harness/**: Auction Analyzer CLI (`cli-anything-auction`).

## Rules
1. Read HARNESS.md + BIDDEED_OVERLAY.md before coding anything.
2. PEP 420: `cli_anything/` directory has NO `__init__.py`. Sub-packages DO.
3. Every Click command supports `--json` output.
4. Bare command (no subcommand) enters REPL via ReplSkin.
5. All subprocess tests use `_resolve_cli()` pattern.
6. Copy `repl_skin.py` from `cli-anything-plugin/` into each CLI's `utils/`.
7. `--persist` flag = write to Supabase. Without it = pure JSON stdout.
8. `@audit_logged` decorator on all Click commands.
9. All backends follow `find_<service>()` → RuntimeError with setup instructions pattern.
10. pytest must pass before any git push.

## Stack
- Python 3.10+, Click 8+, prompt-toolkit 3+
- Supabase (mocerqjnksmhcjzxrewo.supabase.co)
- GitHub Actions for scheduling
- Backends: Firecrawl, Gemini Flash, BCPAO, AcclaimWeb, RealForeclose

## Cost Discipline
$10/session max. No retry loops. No verbose dumps. One attempt per approach.

## Git
PAT: See SECURITY.md (never commit tokens to repo)
Commit after each completed phase. Descriptive messages.

## Plan Reference
See `docs/plans/CLI-Anything-BidDeed-Plan.md` for session-by-session implementation plan.
