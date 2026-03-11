# CLI-Anything BidDeed

**Fork of [HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything)** — adapted for BidDeed.AI's foreclosure auction and zoning intelligence stack.

> CLI-Anything: Making ALL Software Agent-Native.
> This fork extends the methodology to API/DB backend targets.

---

## What This Fork Adds

CLI-Anything was built for GUI desktop apps (Blender, GIMP, LibreOffice). This fork applies the same proven 7-phase pipeline to **cloud APIs, web scrapers, and database-backed agents** — proving the methodology is universal.

### CLIs in This Fork

| CLI | Domain | Backend | Status |
|-----|--------|---------|--------|
| `cli-anything-zonewise` | Zoning data scraper | Firecrawl + Gemini + Claude + Supabase | 🔨 Planned |
| `cli-anything-auction` | Foreclosure analysis | RealForeclose + BCPAO + AcclaimWeb + Supabase | 🔨 Planned |
| `cli-anything-swimintel` | Swim meet intelligence | PDF + pdfplumber + Node.js docx + Supabase | ✅ Agent #139 (19 tests) |
| `cli-anything-btr` | Build-to-Rent + Distressed Assets | MAI Valuation + OpenMud + LangGraph + Supabase | ✅ Squad EVEREST-BTR (23 tests, 10 agents) |

### Stack Extensions (BIDDEED_OVERLAY.md)

| Extension | Description |
|-----------|-------------|
| Supabase State Layer | Hybrid persistence: JSON stdout for piping + Supabase for durability |
| GitHub Actions | Nightly/on-demand agent scheduling via cron workflows |
| Cost Tracking | Token budget enforcement per CLI invocation |
| Audit Logging | Every agent decision logged to Supabase |
| LangGraph Bridge | Multi-agent orchestration with checkpoint/resume |

---

## Quick Start

```bash
# Install shared utilities
cd shared && pip install -e .

# Install ZoneWise CLI
cd zonewise/agent-harness && pip install -e .
cli-anything-zonewise --help

# Install Auction CLI
cd auction/agent-harness && pip install -e .
cli-anything-auction --help

# Install SwimIntel CLI (Agent #139)
cd swimintel/agent-harness && pip install -e .
cli-anything-swimintel --help

# Install BTR Squad (EVEREST-BTR — 10 agents)
cd btr/agent-harness && pip install -e .
cli-anything-btr --help
```

## Agent Piping

```bash
# Chain agents via JSON stdout
cli-anything-zonewise --json parcel lookup --address "123 Ocean Ave" \
  | cli-anything-auction --json analyze --stdin

# Persist results to Supabase
cli-anything-auction --json analyze batch --date 2026-03-15 --persist

# SwimIntel full pipeline — PDF in, DOCX report out
cli-anything-swimintel pipeline --pdf psychsheet.pdf --swimmer "Last, First" -o report.docx

# BTR Squad — full analysis pipeline
cli-anything-btr --json analyze "123 Ocean Ave" --type sfr --scenario full

# BTR MAI Valuation — 3-approach method
cli-anything-btr --json mai "456 Beach St" --type multifamily \
  --noi 120000 --cap-rate 0.065 --comp-value 1800000 --cost-value 1650000

# BTR Rehab — distressed asset max bid calc
cli-anything-btr --json rehab "789 Foreclosure Dr" --type sfr \
  --arv 300000 --repairs 50000

# Chain BTR with ZoneWise for HBU analysis
cli-anything-zonewise --json parcel lookup --parcel "12-34-56" \
  | cli-anything-btr --json hbu --zoning "RM-6"
```

## Architecture

- **HARNESS.md** — Upstream SOP (untouched)
- **BIDDEED_OVERLAY.md** — Stack-specific extensions
- **docs/plans/** — Design spec + implementation plan
- **shared/** — Shared utilities (Supabase, cost, audit)
- **zonewise/** — ZoneWise Scraper CLI
- **auction/** — Auction Analyzer CLI
- **swimintel/** — SwimIntel Competitive Intelligence CLI (Agent #139)
- **btr/** — EVEREST-BTR Squad: Build-to-Rent + Distressed Assets (10 agents, 23 tests)

## Upstream

This fork keeps the `cli_anything.*` namespace and follows HARNESS.md patterns to enable eventual contribution back to [HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything).

---

## License

MIT License — same as upstream.
