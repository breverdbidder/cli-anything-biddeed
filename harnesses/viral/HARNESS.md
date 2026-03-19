# Viral Content Pipeline Harness

## Origin
Forked from [GoViralBitch (GVB) v0.1.0](https://github.com/charlesdove977/goviralbitch) by Charles Dove.
Adapted for BidDeed.AI stack: Supabase + GHA + Supadata + DeepSeek.

## Pipeline
```
DISCOVER ──> ANGLE ──> SCRIPT ──> POST ──> ANALYZE
    ^                                           |
    └─── feedback loop (brain evolves) ─────────┘
```

## Architecture (BidDeed.AI Adaptation)

| GVB Original | BidDeed.AI Harness | Why |
|---|---|---|
| JSONL files | Supabase (9 `viral_*` tables) | Persistence, RLS, API access |
| Claude Code slash commands | cli-anything harness phases | Standardized execution |
| OpenAI Whisper | Supadata API (`sd_3c7a57546da7893f9ae3056a664d5dc9`) | FREE 100/mo, already integrated |
| macOS launchd cron | GHA scheduled workflows | Server-side, no local deps |
| YouTube Data API | YouTube Data API (same) | No change needed |
| instaloader | instaloader (same) | No change needed |
| Flask web UI | BidDeed.AI dashboard (future) | CF Pages |

## Supabase Tables (9)
- `viral_agent_brain` - Evolving system memory
- `viral_topics` - Discovered content ideas
- `viral_angles` - Contrast Formula angles
- `viral_hooks` - HookGenie generated hooks
- `viral_scripts` - Generated content scripts
- `viral_analytics` - Performance data
- `viral_swipe_hooks` - Competitor hook inspiration
- `viral_insights` - Aggregated pattern library
- `viral_competitor_reels` - Scraped competitor content

## Key Concepts

### Contrast Formula
Every angle flips an expectation: **Common Belief (A)** → **Surprising Truth (B)**.
Strength rated: mild / moderate / strong / extreme.

### HookGenie (6 Patterns)
1. **Contradiction** — "Everyone says {A}, but {B}"
2. **Specificity** — "I {specific_result} in {specific_timeframe}"
3. **Timeframe Tension** — "In {short_time}, I {impressive_result}"
4. **POV as Advice** — "Stop {common_practice}. {better_alternative}."
5. **Vulnerable Confession** — "I was wrong about {A}. {what_changed}."
6. **Pattern Interrupt** — Unexpected opening that breaks scroll behavior

### Brain Evolution
- `learning_weights`: 4 scoring axes adjusted by win rate
- `hook_preferences`: 6 pattern scores boosted by performance
- `visual_patterns`: Aggregated visual hook intelligence
- `performance_patterns`: Running averages (CTR, retention, topics, formats)

### Scoring Engine
ICP keyword matching with stem extraction, 4-axis weighted scoring.
Pure Python, zero dependencies. Reused directly from GVB.

## Commands (mapped from GVB slash commands)

| Phase | GVB Command | Harness Entry |
|---|---|---|
| Setup | /viral:setup | `src/setup.py` |
| Onboard | /viral:onboard | `src/onboard.py` |
| Discover | /viral:discover | `src/discover.py` (uses Supadata) |
| Angle | /viral:angle | `src/angle.py` |
| Script | /viral:script | `src/script.py` |
| Analyze | /viral:analyze | `src/analyze.py` |
| Learn | /viral:update-brain | `src/update_brain.py` |

## Eval
`eval/eval.json` — 25 binary assertions covering:
- Brain CRUD operations
- Topic scoring accuracy
- Hook pattern generation
- Analytics winner extraction
- Feedback loop weight updates
