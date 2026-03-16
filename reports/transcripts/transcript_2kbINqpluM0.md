# 🎬 YouTube Transcript Analysis

**Video:** [Claude Code + Obsidian = Your Dream Second Brain](https://youtu.be/2kbINqpluM0)
**Creator:** Mark Kashef (Early AI Dopters, 68.4K subscribers)
**Duration:** ~14 min | **Generated:** 2026-03-15
**Tags:** `obsidian`, `claude code`, `second brain`, `productivity`, `ai`, `vault`, `slash commands`, `cli`, `markdown`, `file processing`, `json canvas`
**Source:** PDF guide + video chapter extraction | Pipeline: cli-anything-youtube v1.0

---

## 📋 TL;DR

Mark Kashef demonstrates how to combine Obsidian (free, local-first markdown note-taking) with Claude Code to build a functional "second brain" — specifically designed for people who have struggled with consistency in productivity tools. The system uses Obsidian's CLI to let Claude Code read, write, and organize notes directly. Four pre-built slash commands (`/vault-setup`, `/daily`, `/tldr`, `/file-intel`) automate common workflows, while Kepano's official Obsidian Skills teach Claude to natively navigate vaults. A file processing pipeline converts messy PDFs/DOCX into clean markdown, and JSON Canvas provides visual idea mapping. Setup takes under 10 minutes on macOS or Windows.

---

## 🎯 BidDeed.AI Relevance: 8/10

- **CLI-based tooling** directly mirrors our cli-anything harness architecture
- **Slash commands pattern** applicable to BidDeed.AI agent dispatching (`/auction`, `/report`, `/scrape`)
- **File processing pipeline** (PDF/DOCX → markdown) directly applicable to foreclosure document ingestion
- **CLAUDE.md context injection** pattern already used in our repos — validates our approach
- **Automated daily briefing** (`/daily`) maps to automated auction summary generation
- **Local-first markdown** aligns with our GitHub-based documentation strategy
- **Vault-as-project pattern** applicable to per-auction or per-county research folders
- **Zero-cost tooling** (Obsidian free, Claude Code on Max plan) aligns with cost discipline

---

## 📖 Chapters

### 1. [0:00] Why I Kept Quitting Obsidian
The creator explains the common struggle with productivity tools — inconsistency. Previous attempts with note-taking apps failed because they required too much manual organization. The breakthrough was using AI as the bridge between capturing ideas and actually maintaining the system.

### 2. [1:12] What Obsidian Actually Is
Obsidian is a free note-taking app where all notes are plain `.md` files stored locally. Unlike Notion or Apple Notes, there's no cloud lock-in, no subscription, no proprietary format. This matters because Claude Code can read those same files directly — no API, no plugin, no sync required. Two apps working on the same folder simultaneously.

### 3. [2:30] The Bridge: Obsidian CLI + Claude Code
The key integration: Obsidian's command-line interface lets Claude Code interact with the vault programmatically. Enable it in Settings → General → CLI → toggle ON. Claude Code installs via `curl -fsSL https://claude.ai/install.sh | sh` (macOS) or `winget install Anthropic.ClaudeCode` (Windows). Once both are running, Claude has direct file-system access to all notes.

### 4. [4:15] Vault Setup — One Command
A dedicated `/vault-setup` command automates creating a personalized vault structure. Run it and Claude interviews you about your role, goals, and workflow — then generates a custom `CLAUDE.md` (context file) and folder structure. The setup repo is at github.com/earlyaidopters/second-brain with one-command install scripts for both macOS and Windows.

### 5. [6:40] Slash Commands: /daily, /standup, /tldr
Four pre-installed slash commands:
- **`/vault-setup`** — Interviews you, builds CLAUDE.md and folder structure (run first)
- **`/daily`** — Starts your day: reads today's note, surfaces priorities, asks what you're working on
- **`/tldr`** — End-of-session: saves structured summary to the right folder automatically
- **`/file-intel`** — Points at any folder, Gemini reads every file, generates Obsidian-ready summaries into inbox

### 6. [8:20] File Processing Pipeline
A method to turn messy files (PDFs, DOCX) into clean, synthesized markdown notes using an AI pipeline. The `/file-intel` command reads entire folders and produces structured summaries. This is the "file processing pipeline" — raw documents go in, organized knowledge comes out.

### 7. [10:05] Kepano's Official Obsidian Skills
Steph Ango (Kepano), CEO of Obsidian, created official skills for Claude Code:
- **obsidian-cli** — Read, create, search, manage notes via CLI
- **obsidian-markdown** — Obsidian-flavored markdown (wikilinks, callouts, embeds)
- **obsidian-bases** — Database-style views of notes
- **json-canvas** — Create and edit visual Canvas files

Repo: github.com/kepano/obsidian-skills

### 8. [11:30] JSON Canvas Demo
Visual organization using JSON Canvas to map out ideas. Canvas files let you spatially arrange notes, images, and connections on an infinite board — useful for brainstorming and project planning.

### 9. [12:45] Context Injection Tip
Wire your vault to any Claude Code project by adding one line to your project's CLAUDE.md:
> `At the start of every session, read "/path/to/your-vault/CLAUDE.md" for full context about who I am.`

Make it global by adding the same line to `~/.claude/CLAUDE.md` — Claude Code loads this automatically in every session.

### 10. [13:30] Free Starter Kit + Community
Resources provided: Setup repo (github.com/earlyaidopters/second-brain), Obsidian Skills (github.com/kepano/obsidian-skills), free Google API key (aistudio.google.com/apikey), and community at skool.com/earlyaidopters/about (800+ members).

---

## 🔑 Key Points

1. Obsidian stores notes as local `.md` files — Claude Code reads them natively with zero configuration
2. The `/vault-setup` slash command interviews you and auto-generates a personalized folder structure + CLAUDE.md
3. Four pre-built commands (`/vault-setup`, `/daily`, `/tldr`, `/file-intel`) handle the most common second-brain workflows
4. `/file-intel` creates an AI file processing pipeline: point it at a folder of PDFs/DOCX → get organized markdown summaries
5. Kepano (Obsidian CEO) published official Claude Code skills for native vault navigation
6. Context injection via CLAUDE.md lets any Claude Code project access your entire vault context
7. Global context: add vault path to `~/.claude/CLAUDE.md` for automatic loading in every session
8. The entire stack is free: Obsidian ($0) + Claude Code (Max plan) + Gemini API (free tier for /file-intel)

---

## 🛠️ Tools & Technologies

- **Obsidian** — Free, local-first markdown note-taking app
- **Claude Code** — Anthropic's CLI agent for file manipulation and code generation
- **Obsidian CLI** — Command-line interface for programmatic vault access
- **Slash Commands** — Custom Claude Code commands (`.claude/commands/` directory)
- **Gemini API** — Used by `/file-intel` for file processing (free tier)
- **JSON Canvas** — Visual spatial mapping format native to Obsidian
- **CLAUDE.md** — Context injection file read at session start
- **GitHub** — Setup repo hosting (earlyaidopters/second-brain)

---

## 💡 Actionable Takeaways for BidDeed.AI

| # | Action | Effort | Impact |
|---|--------|--------|--------|
| 1 | Create `/auction-brief` slash command for daily auction summaries | LOW | HIGH |
| 2 | Build `/file-intel` equivalent for foreclosure document ingestion | MEDIUM | HIGH |
| 3 | Implement CLAUDE.md context injection across all BidDeed repos | LOW | HIGH |
| 4 | Create `/transcript` slash command that triggers our YouTube Squad | LOW | MEDIUM |
| 5 | Apply vault-setup pattern for new county onboarding | LOW | MEDIUM |
| 6 | Use JSON Canvas for visual 12-stage pipeline documentation | LOW | LOW |

**1. Create `/auction-brief` slash command for daily auction summaries**
_Direct adaptation of the `/daily` command pattern. Instead of reading today's note and surfacing priorities, it queries Supabase for upcoming auctions, pulls latest metrics, and generates a morning briefing. Drops into `reports/daily/` automatically. The slash command pattern is already how Claude Code works — just create `.claude/commands/auction-brief.md` with the prompt._

**2. Build `/file-intel` equivalent for foreclosure document ingestion**
_The file processing pipeline (PDF/DOCX → clean markdown) is directly applicable to processing foreclosure filings, HOA lien documents, and court records. Point it at a folder of downloaded court PDFs and get structured markdown with key data extracted (judgment amounts, property addresses, plaintiff names, lien positions). Uses Gemini Flash via CLIProxyAPI for $0._

**3. Implement CLAUDE.md context injection across all BidDeed repos**
_We already use CLAUDE.md in most repos. The video validates adding a global `~/.claude/CLAUDE.md` that points to our master context. This means any Claude Code session anywhere automatically knows about BidDeed.AI, our stack, our conventions. One-time setup, permanent benefit._

**4. Create `/transcript` slash command that triggers our YouTube Squad**
_Meta-application: use the slash command pattern to trigger the transcript pipeline we just built. Claude Code command that takes a YouTube URL, SSHs to Hetzner, runs the squad, and saves the result into the current vault/project. Research → notes pipeline in one command._

**5. Apply vault-setup pattern for new county onboarding**
_When expanding beyond Brevard County, create a `/county-setup` command that interviews about the new county (auction format, GIS endpoints, clerk website, zoning codes) and auto-generates the folder structure, scraper configs, and data source mappings. Same interview → scaffold pattern._

**6. Use JSON Canvas for visual 12-stage pipeline documentation**
_Low effort, nice-to-have: create a Canvas file that visually maps the BidDeed.AI 12-stage pipeline (Discovery → Scraping → Title → Lien → Tax → Demographics → ML → Max Bid → Decision → Report → Disposition → Archive). Good for onboarding documentation and investor presentations._

---

## 📎 Source Material

- **Video:** https://youtu.be/2kbINqpluM0
- **Setup Repo:** https://github.com/earlyaidopters/second-brain
- **Obsidian Skills:** https://github.com/kepano/obsidian-skills
- **Creator:** Mark Kashef — skool.com/earlyaidopters/about
- **PDF Guide:** obsidian-setup-guide (7 pages)
- **SKILL.md:** vault-setup skill file (full source, 169 lines)

---

## 🔬 Deep Dive: vault-setup SKILL.md Pattern Analysis

Mark's `vault-setup` SKILL.md is a masterclass in agent skill design. Here's what makes it exceptional and how we should steal every pattern:

### Architecture: 5-Step Interview → Scaffold → Wire

```
STEP 1: One free-text question (gather ALL context at once)
STEP 2: Infer role/scope/pain points — DON'T ask more questions
STEP 3: Build folders + CLAUDE.md + skill files + memory.md
STEP 4: Context injection (global vs manual vs vault-only)
STEP 5: Final output with next-action instructions
```

### Pattern 1: "One Question, Zero Clarification"
The skill asks ONE open-ended question then INFERS everything else. No back-and-forth. This is anti-chatbot design — it trusts the LLM to figure out role, pain points, and scope from free text. Critical for zero-HITL.

**BidDeed adaptation:** Our `/county-setup` should ask one question: "Tell me about this county — what you know about the auction format, GIS system, and any contacts." Then infer everything.

### Pattern 2: Role-Based Folder Templates
Instead of one-size-fits-all, the skill maps roles to folder sets:
- Business Owner → `people/ operations/ decisions/`
- Developer → `research/ clients/`
- Creator → `content/ research/ clients/`

**BidDeed adaptation:** Map auction types to pipeline configs:
- Foreclosure → `filings/ liens/ bids/ reports/`
- Tax Deed → `certificates/ surplus/ parcels/`
- Municipal → `zoning/ permits/ contacts/`

### Pattern 3: CLAUDE.md as Living Context
The generated CLAUDE.md isn't static documentation — it's ACTIVE context with routing rules:

```markdown
## Context Rules
When I mention a decision → check decisions/ first
When I mention a person → look in people/
When I ask you to write → read daily/ to match my voice
When something lands in inbox/ → ask if I want it sorted
```

**BidDeed adaptation:** Our repo CLAUDE.md should have:
```markdown
## Context Rules  
When I mention an auction → query Supabase multi_county_auctions first
When I mention a property → check BCPAO + AcclaimWeb
When analyzing a deal → apply max bid formula automatically
When new data lands → validate against existing records before insert
```

### Pattern 4: memory.md as Persistent Learning
Separate from CLAUDE.md, a `memory.md` file tracks session-by-session learnings and preferences. The `/tldr` command updates this automatically after every session.

**BidDeed adaptation:** We already have Supabase `insights` table — but a per-repo `memory.md` that Claude Code updates after each session would capture architectural decisions, failed approaches, and learned patterns locally.

### Pattern 5: Skill File Minimalism
Each skill file is 1-2 sentences. Not a novel. Not a prompt template. Just the intent:

> "Summarize this conversation: decisions, things to remember, next actions. Save to the most relevant folder. Update memory.md."

Claude Code fills in the rest from context. Less is more.

### Pattern 6: Context Injection Architecture
Three tiers of context loading:
1. **Global** (`~/.claude/CLAUDE.md`) — loads in EVERY session, everywhere
2. **Project** (repo-level `CLAUDE.md`) — loads in that project only
3. **Vault** — auto-loads when running from inside the folder

This is a composable context system. Global sets identity, project sets domain, vault sets workspace.

**BidDeed adaptation:** We should implement all three tiers:
- Global: BidDeed.AI identity, stack overview, cost discipline rules
- Per-repo: Repo-specific conventions (e.g., zonewise-scraper-v4 has its own patterns)
- Per-session: Dynamic context from Supabase queries

### Summary: What to Steal

| Pattern | Mark's Implementation | BidDeed.AI Adaptation |
|---------|----------------------|----------------------|
| One-question interview | Free text → infer role | Free text → infer county/auction type |
| Role-based scaffolding | 5 role templates | Auction-type templates |
| Active context rules | "When X → do Y" in CLAUDE.md | "When auction → query Supabase" |
| memory.md | Session log + preferences | Per-repo architectural memory |
| Minimal skill files | 1-2 sentence intents | Same — trust Claude to fill in |
| 3-tier context injection | Global/Project/Vault | Global/Repo/Session |
