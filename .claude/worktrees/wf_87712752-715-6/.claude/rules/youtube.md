---
pattern: "youtube/**"
---
# YouTube Transcript Squad Rules

- "Transcript:" + URL = INSTANT execution. Never search/web_fetch/yt-dlp
- API: api.supadata.ai/v1/youtube/transcript + /video
- Key: sd_3c7a57546da7893f9ae3056a664d5dc9. $0.01/vid, 100 FREE/mo
- Output: AI insights → Supabase youtube_transcript table → display
- Transcript processing: summarize, extract insights, tag relevance to ecosystem
- Never store raw transcript in Supabase (token waste). Store summary + insights only
