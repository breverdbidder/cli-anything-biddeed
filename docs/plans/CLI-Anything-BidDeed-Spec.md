# CLI-Anything Fork: BidDeed.AI Agent-Native Stack
## Design Specification v1.0 — March 11, 2026

**Status:** BRAINSTORM → **DESIGN** ✅ → SPEC (this doc) → PLAN → HANDOFF

---

## 1. STRATEGIC RATIONALE

### The Problem We're Solving
Every time we spin up a new agent (like today's insurance business plan — 5 agents running, needed a 6th on the fly), we reinvent:
- How agents accept input (ad-hoc prompts vs structured commands)
- How agents produce output (unstructured text vs parseable JSON)
- How agents hand off to each other (copy-paste vs pipeline)
- How agents get tested (manual spot checks vs automated suites)

### The CLI-Anything Solution Applied to Our Stack
CLI-Anything's 7-phase pipeline becomes our **agent factory**. Instead of GUI→CLI (their use case), we do **Agent Logic→CLI** (our use case). The `anygen` harness in the repo already proves this pattern works for cloud/API backends — it wraps a REST API into a structured CLI with JSON output, session management, and REPL. Our agents ARE the backends.

### What We Keep from Upstream
| Component | Keep? | Why |
|-----------|-------|-----|
| HARNESS.md 7-phase pipeline | ✅ | Proven methodology for building production CLIs |
| PEP 420 namespace packages | ✅ | `cli_anything.zonewise`, `cli_anything.auction` coexist |
| Click framework + `--json` | ✅ | Agent-native I/O, LLM-friendly |
| ReplSkin REPL interface | ✅ | Interactive debugging + demos |
| `_resolve_cli()` test pattern | ✅ | Subprocess testing exactly like production |
| Session/undo/redo | ✅ | State management between commands |
| setup.py + PATH install | ✅ | `which cli-anything-zonewise` works everywhere |

### What We Add (BIDDEED_OVERLAY.md)
| Component | Description |
|-----------|-------------|
| Supabase state layer | Hybrid persistence: JSON stdout for piping + Supabase for durability |
| GitHub Actions scheduling | Nightly/on-demand agent runs via cron workflows |
| LangGraph orchestration | Multi-agent pipelines with checkpoint/resume |
| Cost tracking | Token budget enforcement per CLI invocation |
| Audit logging | Every agent decision logged to Supabase `audit_log` |

---

## 2. ARCHITECTURE

### 2.1 Namespace & Package Structure

```
cli-anything-biddeed/                    # Fork repo
├── HARNESS.md                           # Upstream (untouched)
├── BIDDEED_OVERLAY.md                   # Our stack-specific additions
├── cli-anything-plugin/                 # Upstream plugin (untouched)
│   ├── commands/
│   ├── repl_skin.py
│   └── HARNESS.md → ../HARNESS.md
│
├── zonewise/                            # CLI #1: ZoneWise Scraper
│   └── agent-harness/
│       ├── ZONEWISE.md                  # Software-specific SOP
│       ├── setup.py
│       └── cli_anything/               # NO __init__.py (namespace)
│           └── zonewise/               # HAS __init__.py
│               ├── zonewise_cli.py     # Click entry: cli-anything-zonewise
│               ├── core/
│               │   ├── scraper.py      # County scraping logic
│               │   ├── parser.py       # Zoning code parsing
│               │   ├── export.py       # JSON/CSV/Supabase output
│               │   └── session.py      # State management
│               ├── utils/
│               │   ├── supabase_backend.py   # Supabase read/write
│               │   ├── firecrawl_backend.py  # Tier1 scraping
│               │   ├── repl_skin.py          # Copy from plugin
│               │   └── cost_tracker.py       # Token budget
│               └── tests/
│                   ├── TEST.md
│                   ├── test_core.py
│                   └── test_full_e2e.py
│
├── auction/                             # CLI #2: Auction Analyzer
│   └── agent-harness/
│       ├── AUCTION.md
│       ├── setup.py
│       └── cli_anything/
│           └── auction/
│               ├── auction_cli.py      # Click entry: cli-anything-auction
│               ├── core/
│               │   ├── discovery.py    # RealForeclose scraping
│               │   ├── title_search.py # AcclaimWeb lien search
│               │   ├── analysis.py     # Bid/Skip/Review logic
│               │   ├── report.py       # DOCX/PDF generation
│               │   ├── export.py       # Multi-format output
│               │   └── session.py
│               ├── utils/
│               │   ├── supabase_backend.py
│               │   ├── bcpao_backend.py    # Property appraiser
│               │   ├── acclaimweb_backend.py
│               │   ├── repl_skin.py
│               │   └── cost_tracker.py
│               └── tests/
│
└── shared/                              # Shared utilities
    └── cli_anything_shared/
        ├── supabase.py                  # Connection + common queries
        ├── cost.py                      # Token budget enforcement
        ├── audit.py                     # Audit logging
        └── langraph.py                  # LangGraph state bridge
```

### 2.2 Agent Communication: Hybrid Model

**Principle:** JSON stdout for composability, Supabase for durability.

#### Layer 1: Unix Pipe (Immediate, Local)
```bash
# Chain agents via JSON stdout — works locally, no infrastructure needed
cli-anything-zonewise --json scrape --county brevard \
  | cli-anything-auction --json analyze --stdin

# Single agent, structured output
cli-anything-auction --json analyze --case 2024-CA-001234
{
  "case_number": "2024-CA-001234",
  "recommendation": "BID",
  "bid_ratio": 0.82,
  "max_bid": 142000,
  "arv": 285000,
  "repairs": 35000,
  "liens": [{"type": "mortgage", "amount": 198000, "position": 1}]
}
```

#### Layer 2: Supabase State (Persistent, Cross-Session)
```bash
# Write results to Supabase for durability + other agents to consume
cli-anything-auction analyze --case 2024-CA-001234 --persist
# Writes to auction_analysis table, returns row ID

# Another agent reads from Supabase
cli-anything-auction report --from-db --case 2024-CA-001234 --format docx
# Reads analysis from Supabase, generates report
```

#### Layer 3: LangGraph Orchestration (Multi-Agent Workflows)
```bash
# GitHub Actions workflow calls agents in sequence
# Each step: CLI call → JSON stdout → next step's stdin + Supabase checkpoint
# LangGraph manages state graph, retries, circuit breakers
```

### 2.3 Command Design

#### cli-anything-zonewise

```
cli-anything-zonewise
├── county
│   ├── scrape     --county <name> [--tier 1|2|3]     # Scrape zoning data
│   ├── list       [--state FL]                        # List available counties
│   └── status     --county <name>                     # Last scrape status
├── parcel
│   ├── lookup     --address <addr> | --parcel <id>    # Single parcel zoning
│   ├── batch      --input <file.csv>                  # Batch lookup
│   └── report     --parcel <id> --format json|csv     # Zoning report
├── export
│   ├── supabase   --county <name> [--table <name>]    # Push to Supabase
│   ├── csv        --county <name> -o <file>           # Export CSV
│   └── json       --county <name> -o <file>           # Export JSON
├── session
│   ├── status                                         # Current state
│   ├── history                                        # Command history
│   └── undo                                           # Undo last operation
├── config
│   ├── set        <key> <value>                       # Set config
│   └── get        [key]                               # Get config
└── (no subcommand)                                    # Enter REPL
```

#### cli-anything-auction

```
cli-anything-auction
├── discover
│   ├── upcoming   [--date <YYYY-MM-DD>]               # Upcoming auctions
│   ├── scrape     --date <YYYY-MM-DD>                 # Scrape auction list
│   └── status                                         # Discovery status
├── analyze
│   ├── case       --case <number>                     # Full case analysis
│   ├── batch      --date <YYYY-MM-DD>                 # Analyze all cases
│   ├── liens      --case <number>                     # Lien priority only
│   └── arv        --case <number>                     # ARV estimate only
├── recommend
│   ├── bid        --date <YYYY-MM-DD> [--min-ratio 0.75]  # BID recommendations
│   ├── review     --date <YYYY-MM-DD>                 # REVIEW cases
│   └── summary    --date <YYYY-MM-DD>                 # Full summary
├── report
│   ├── generate   --case <number> --format docx|pdf   # Single case report
│   ├── batch      --date <YYYY-MM-DD> -o <dir>       # All reports
│   └── dashboard  --date <YYYY-MM-DD> --format html   # Summary dashboard
├── export
│   ├── supabase   --date <YYYY-MM-DD>                 # Push to DB
│   └── csv        --date <YYYY-MM-DD> -o <file>       # Export
├── session
│   ├── status
│   ├── history
│   └── undo
└── (no subcommand)                                    # Enter REPL
```

### 2.4 Backend Architecture

Following HARNESS.md's core principle: **"build the data → call the real software → verify the output"**

For us, "real software" = external data sources + Supabase + LLM inference:

| CLI | Backend (Real Software) | Intermediate Format | Final Output |
|-----|------------------------|--------------------|--------------| 
| zonewise | Firecrawl → Gemini Flash → Claude Sonnet | Raw HTML → Markdown → JSON | Supabase rows + CSV |
| auction | RealForeclose + BCPAO + AcclaimWeb | Scraped HTML → Structured JSON | DOCX reports + Supabase |

Each backend gets its own `utils/<service>_backend.py` with:
- Service discovery (`find_<service>()` pattern)
- Error handling with clear setup instructions
- Health check commands

```python
# utils/firecrawl_backend.py — follows HARNESS.md pattern
import os

def find_firecrawl():
    """Verify Firecrawl API access."""
    key = os.environ.get("FIRECRAWL_API_KEY")
    if key:
        return key
    raise RuntimeError(
        "Firecrawl API key not found. Set it with:\n"
        "  export FIRECRAWL_API_KEY=fc-xxx\n"
        "  # or: cli-anything-zonewise config set firecrawl_api_key fc-xxx"
    )
```

---

## 3. BIDDEED_OVERLAY.md — Stack-Specific Extensions

These are additions to HARNESS.md, not replacements:

### 3.1 Supabase State Layer
Every CLI gets optional `--persist` flag:
- Without `--persist`: pure JSON stdout (stateless, pipeable)
- With `--persist`: writes results to Supabase + returns row ID
- `--from-db` flag: reads input from Supabase instead of stdin/args

### 3.2 Cost Tracking
Built into every CLI via `shared/cost.py`:
```python
# Automatic — wraps every LLM call
with cost_tracker(budget=1.00, session_id="auction-2024-03-11"):
    result = llm.invoke(prompt)
# Logs: model, tokens_in, tokens_out, cost_usd, timestamp → Supabase daily_quota_usage
```

### 3.3 GitHub Actions Integration
Each CLI ships with a `.github/workflows/` template:
```yaml
# zonewise-nightly.yml
name: ZoneWise Nightly Scrape
on:
  schedule:
    - cron: '0 4 * * *'  # 11 PM EST
jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - run: pip install cli-anything-zonewise
      - run: cli-anything-zonewise --json county scrape --county brevard --persist
```

### 3.4 Audit Logging
Every command invocation logged to Supabase `audit_log`:
```json
{
  "cli": "cli-anything-auction",
  "command": "analyze case --case 2024-CA-001234",
  "timestamp": "2026-03-11T14:30:00Z",
  "duration_ms": 4200,
  "cost_usd": 0.03,
  "result": "BID",
  "user": "github-actions"
}
```

---

## 4. IMPLEMENTATION PLAN

### Phase 0: Fork & Setup (Day 1)
- Fork HKUDS/CLI-Anything → breverdbidder/cli-anything-biddeed
- Create BIDDEED_OVERLAY.md
- Create shared/ utilities (supabase, cost, audit)
- Verify upstream plugin still works

### Phase 1-7: ZoneWise CLI (Days 2-4)
Follow HARNESS.md phases exactly:
1. Analyze zonewise-scraper-v4 codebase
2. Design CLI architecture (command tree above)
3. Implement core modules + backends
4. Plan tests in TEST.md
5. Write unit + E2E tests
6. Document results
7. Publish: `pip install -e . && which cli-anything-zonewise`

### Phase 1-7: Auction CLI (Days 5-8)
Same 7-phase pipeline for auction analyzer.

### Integration Phase (Days 9-10)
- LangGraph orchestration workflow connecting both CLIs
- GitHub Actions workflows for nightly runs
- End-to-end pipeline test: scrape → analyze → report → persist

---

## 5. CONCRETE EXAMPLES: WHAT DAILY USAGE LOOKS LIKE

### Example 1: Morning Auction Analysis
```bash
# Discover upcoming auctions
$ cli-anything-auction --json discover upcoming
{"date": "2026-03-15", "count": 23, "venue": "Titusville", "type": "in-person"}

# Analyze all cases, persist to Supabase
$ cli-anything-auction --json analyze batch --date 2026-03-15 --persist
{"analyzed": 23, "bid": 4, "review": 3, "skip": 16, "db_batch_id": "batch_abc123"}

# Generate reports for BID recommendations only
$ cli-anything-auction report batch --date 2026-03-15 --filter bid -o ./reports/
✓ Generated 4 reports in ./reports/
```

### Example 2: ZoneWise Nightly Pipeline (GitHub Actions)
```bash
# Runs at 11 PM EST via cron
$ cli-anything-zonewise --json county scrape --county brevard --persist
{"county": "brevard", "parcels_scraped": 1247, "new": 34, "updated": 89, "db_sync": true}
```

### Example 3: Ad-Hoc Agent (What You Needed Today)
```bash
# Interactive REPL for insurance business plan
$ cli-anything-auction
╭──────────────────────────────────────────╮
│    cli-anything-auction v1.0.0           │
│    Foreclosure Auction Intelligence      │
╰──────────────────────────────────────────╯

auction> analyze case --case 2024-CA-005678
✓ Case 2024-CA-005678: REVIEW (ratio: 0.68)
  ARV: $310,000 | Repairs: $45,000 | Max Bid: $152,000
  Judgment: $223,000 | Bid/Judgment: 68%

auction[2024-CA-005678]*> report generate --format docx
✓ Report: auction_2024-CA-005678.docx (2.1 MB)

auction> exit
Goodbye! 👋
```

### Example 4: Piped Multi-Agent Workflow
```bash
# ZoneWise feeds Auction Analyzer
$ cli-anything-zonewise --json parcel lookup --address "123 Ocean Ave, Satellite Beach" \
  | cli-anything-auction --json analyze --stdin --enrich-zoning
{
  "address": "123 Ocean Ave, Satellite Beach, FL 32937",
  "zoning": "RS-1 (Single Family Residential)",
  "case": "2024-CA-003456",
  "recommendation": "BID",
  "zoning_risk": "LOW",
  "notes": "Conforming use, no zoning variances needed"
}
```

---

## 6. UPSTREAM CONTRIBUTION PATH

By keeping `cli_anything.*` namespace and HARNESS.md untouched:

**Short-term:** Our `BIDDEED_OVERLAY.md` patterns (Supabase backends, API-only targets, cost tracking) can be proposed as official overlay templates.

**Medium-term:** `cli-anything-zonewise` and `cli-anything-auction` demonstrate non-GUI use cases that expand the project's scope beyond creative software.

**Long-term:** If CLI-Anything grows a marketplace, our CLIs could be listed as real-estate/fintech vertical tools.

---

## 7. SUCCESS CRITERIA

- [ ] Fork created at breverdbidder/cli-anything-biddeed
- [ ] BIDDEED_OVERLAY.md written and reviewed
- [ ] `cli-anything-zonewise` passes all tests, installed to PATH
- [ ] `cli-anything-auction` passes all tests, installed to PATH
- [ ] Piped workflow works: zonewise → auction → report
- [ ] GitHub Actions nightly workflow running
- [ ] Supabase persistence working for both CLIs
- [ ] Cost tracking logging to daily_quota_usage
- [ ] REPL mode works for both CLIs
