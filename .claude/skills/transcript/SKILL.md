---
name: transcript
description: Transcribe and analyze any YouTube video. Triggers the YouTube Transcript Squad pipeline on Hetzner via SSH or GitHub Actions. Returns structured analysis with BidDeed.AI relevance scoring.
---

# Transcript — YouTube Video Analysis

Takes a YouTube URL. Fetches transcript. Analyzes with AI. Returns structured report.

## Process

1. Extract video ID from URL
2. SSH to Hetzner (87.99.129.125) and run:
   ```
   cd /opt/yt-transcript && python3 yt_transcript_squad.py "[URL]"
   ```
3. SCP results back: `transcript_[id].md` and `transcript_[id].json`
4. Save report to `reports/transcripts/`
5. Surface the TL;DR, relevance score, and top takeaways

If SSH fails, trigger via GitHub Actions:
```
gh workflow run transcript.yml -f youtube_url="[URL]" --repo breverdbidder/cli-anything-biddeed
```

Output the TL;DR and actionable takeaways inline. Save full report to file.
