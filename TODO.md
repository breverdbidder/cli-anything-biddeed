# CLI-Anything BidDeed — TODO

## Session 1: Fork + Foundation + Shared Utilities
- [x] Create GitHub repo breverdbidder/cli-anything-biddeed
- [x] Create directory structure (PEP 420 namespace)
- [x] Copy upstream HARNESS.md
- [x] Create CLAUDE.md root directive
- [x] Create BIDDEED_OVERLAY.md
- [x] Create docs/plans/ with Spec + Plan
- [x] Create setup.py for all packages
- [x] Create __init__.py files (PEP 420 compliant)
- [x] Push initial commit
- [ ] Implement shared/cli_anything_shared/supabase.py
- [ ] Implement shared/cli_anything_shared/cost.py
- [ ] Implement shared/cli_anything_shared/audit.py
- [ ] Implement shared/cli_anything_shared/config.py
- [ ] Unit tests for shared utilities
- [ ] Verify `pip install -e shared/` works

## Session 2: ZoneWise CLI (7-Phase Pipeline)
- [ ] Phase 1: Analyze zonewise-scraper-v4 codebase → ZONEWISE.md
- [ ] Phase 2: CLI architecture design (command tree)
- [ ] Phase 3: Implement core modules (scraper, parser, export, session)
- [ ] Phase 3: Implement backends (firecrawl, supabase)
- [ ] Phase 3: Implement zonewise_cli.py with Click + REPL
- [ ] Phase 4: Write TEST.md test plan
- [ ] Phase 5: Implement test_core.py + test_full_e2e.py
- [ ] Phase 6: Run tests, document results in TEST.md
- [ ] Phase 7: setup.py + pip install + PATH verification

## Session 3: Auction CLI (7-Phase Pipeline)
- [ ] Phase 1: Analyze brevard-bidder-scraper codebase → AUCTION.md
- [ ] Phase 2: CLI architecture design (command tree)
- [ ] Phase 3: Implement core modules (discovery, title_search, analysis, report, export)
- [ ] Phase 3: Implement backends (bcpao, acclaimweb, realforeclose)
- [ ] Phase 3: Implement auction_cli.py with Click + REPL
- [ ] Phase 4: Write TEST.md test plan
- [ ] Phase 5: Implement test_core.py + test_full_e2e.py
- [ ] Phase 6: Run tests, document results in TEST.md
- [ ] Phase 7: setup.py + pip install + PATH verification

## Session 4: Integration + Deployment
- [ ] Piped workflow: zonewise → auction
- [ ] GitHub Actions workflows (zonewise nightly, auction morning)
- [ ] Supabase persistence verification
- [ ] Audit logging verification
- [ ] LangGraph scaffold (shared/cli_anything_shared/langgraph.py)
- [ ] End-to-end integration test
- [ ] Final README update
