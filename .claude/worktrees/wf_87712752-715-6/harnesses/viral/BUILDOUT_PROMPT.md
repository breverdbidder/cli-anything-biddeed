# Viral Harness Buildout — Claude Code Session

## Context
- You're in: breverdbidder/cli-anything-biddeed (harnesses/viral/)
- GVB source: /home/claude/goviralbitch/ (reference implementation)
- Supabase: mocerqjnksmhcjzxrewo.supabase.co (9 viral_* tables live)
- Supadata: sd_3c7a57546da7893f9ae3056a664d5dc9

## Read First
- harnesses/viral/HARNESS.md (our adaptation spec)
- harnesses/viral/src/supadata_transcript.py (Whisper replacement)
- harnesses/viral/src/supabase_client.py (JSONL replacement)
- harnesses/viral/src/scoring_engine.py (ICP scoring, already ported)

## Task 1: Wire src/discover.py
Port /home/claude/goviralbitch/.claude/commands/viral-discover.md

Core adaptations:
- Transcription: call supadata_transcript.get_transcript(url) instead of Whisper/yt-dlp audio
- Persistence: call supabase_client.save_topic(topic_dict) instead of JSONL append
- Scoring: call scoring_engine.score_topic(title, desc, views, timeliness, is_competitor)
- YouTube API: keep curl-based calls (same YouTube Data API v3)
- Instagram: keep instaloader scraping (same)
- Modes: --competitors, --keywords, --all
- Phases: competitor scrape → keyword search → trend discovery → score → save

Key functions:
- discover_competitors(brain, mode) → scrape YouTube + Instagram
- discover_keywords(brain, queries) → YouTube/Reddit/GitHub search
- transcribe_video(url) → supadata_transcript.get_transcript(url)
- score_and_save(topics, brain) → scoring_engine + supabase_client

## Task 2: Port 6 remaining commands
Create in harnesses/viral/src/:

### onboard.py
Port from viral-onboard.md. 9 sections (identity, ICP, pillars, platforms, competitors, cadence, monetization, audience_blockers, content_jobs). Saves to viral_agent_brain via supabase_client.save_brain().

### angle.py
Port from viral-angle.md. Contrast Formula engine. 15 angles per topic (5 longform + 5 shortform + 5 linkedin). Saves to viral_angles. Reads brain for ICP/pillars/monetization context.

### script.py
Port from viral-script.md. HookGenie 6-pattern engine with composite scoring + brain weight boost. 10 hooks (5 brain + 5 swipe). Longform scripts with filming cards, shortform HEIL beats. Saves to viral_hooks + viral_scripts.

### analyze.py
Port from viral-analyze.md. YouTube Analytics API + instaloader auto-fetch. Top 10 ranking. Winner extraction with median-based thresholds. Deep analysis with transcript + visual hooks. Saves to viral_analytics. Uses supadata for transcription.

### update_brain.py
Port from viral-update-brain.md. Evolves learning_weights, hook_preferences, visual_patterns, performance_patterns. Reads viral_analytics for winner data. Writes back to viral_agent_brain. Evolution log append.

### setup.py
Port from viral-setup.md. Dependency check (Python, yt-dlp, instaloader). API key config (.env). Connection verification. YouTube Analytics OAuth setup. Simplified for server deployment.

## Task 3: Run eval assertions
Write harnesses/viral/eval/eval_runner.py:
- Read eval.json (25 assertions)
- Test Supabase table schemas exist with correct columns
- Test scoring_engine functions with known inputs
- Test supadata_transcript with a public video
- Test supabase_client CRUD operations
- Output: pass/fail per assertion, X/25 summary

## Task 4: Already done (viral-weekly-analyze.yml deployed)

## Rules
- $10 budget — batch operations, ONE attempt per approach
- Pure Python stdlib + urllib (no pip installs)
- All persistence via supabase_client.py (never JSONL)
- All transcription via supadata_transcript.py (never Whisper)
- Commit and push after each task completes
- Update HARNESS.md if architecture changes during build
