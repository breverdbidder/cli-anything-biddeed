# 🎬 YouTube Transcript AI Squad

**cli-anything-youtube** | BidDeed.AI

Zero-cost, zero-HITL YouTube video transcript extraction, AI summarization, and insight generation.

## Architecture

```
YouTube URL → Firecrawl (PAID, existing) → Clean (Python, $0) → Gemini Flash ($0) → Supabase ($0)
```

### 5-Agent Pipeline

| Agent | Function | Service | Cost |
|-------|----------|---------|------|
| 1. FETCH | Extract transcript | Firecrawl (native YT support) | $0* |
| 2. CLEAN | Chunk, dedup, paragraph | Python (pure compute) | $0 |
| 3. SUMMARIZE | Chapters, key points, TL;DR | Gemini Flash via CLIProxyAPI | $0 |
| 4. INSIGHT | BidDeed relevance, takeaways | Gemini Flash via CLIProxyAPI | $0 |
| 5. REPORT | Markdown + JSON + Supabase | Python + Supabase | $0 |

*\*Firecrawl is already paid — no incremental cost*

### Fallback Chain
1. **Primary:** Firecrawl → YouTube transcript (handles anti-bot via their infra)
2. **Fallback:** youtube-transcript-api (works from non-cloud IPs like Hetzner)
3. **AI Fallback:** Direct Gemini API if CLIProxyAPI unavailable
4. **Last Resort:** Heuristic analysis (no AI needed)

## Usage

### GitHub Actions (Zero HITL)
1. Go to Actions → "YouTube Transcript Squad"
2. Click "Run workflow"
3. Paste YouTube URL
4. Report appears in `reports/transcripts/`

### CLI (on Hetzner or local)
```bash
export FIRECRAWL_API_KEY=fc-xxx
export GEMINI_API_KEY=AIza-xxx
export SUPABASE_URL=https://mocerqjnksmhcjzxrewo.supabase.co
export SUPABASE_SERVICE_KEY=eyJ...

python src/yt_transcript_squad.py "https://youtu.be/2kbINqpluM0"
```

### Telegram (future)
```
/transcript https://youtu.be/2kbINqpluM0
```

## Required Secrets (all existing in GitHub)
- `FIRECRAWL_API_KEY` — Firecrawl paid plan
- `GEMINI_API_KEY` — Google Gemini (FREE tier)
- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_SERVICE_KEY` — Supabase service role key

## Output

### Markdown Report
- TL;DR summary
- BidDeed.AI relevance score (0-10)
- Chapter breakdown with timestamps
- Key points (up to 8)
- Actionable takeaways with effort/impact scoring
- Full cleaned transcript

### JSON Metadata
- Video metadata
- Analysis results
- Pipeline stats

### Supabase Table
`youtube_transcripts` — stores all analyses for future querying.

## Setup

### 1. Run Supabase migration
```sql
-- Execute migrations/001_youtube_transcripts.sql in Supabase SQL editor
```

### 2. Push to GitHub
All secrets already configured in `breverdbidder/zonewise-scraper-v4`.
Copy secrets to new repo or use existing repo.

### 3. Trigger
GitHub Actions workflow_dispatch with any YouTube URL.
