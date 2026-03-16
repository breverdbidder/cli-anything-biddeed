#!/usr/bin/env python3
"""
YouTube Transcript AI Squad v1.0
cli-anything-youtube | BidDeed.AI

5-Agent Pipeline (Firecrawl-First):
  Agent 1: FETCH      — Firecrawl native YouTube transcript extraction (PAID, existing)
  Agent 2: CLEAN      — Merge segments, fix timestamps, paragraph flow ($0, pure compute)
  Agent 3+4: AI       — CLIProxyAPI → Gemini Flash summarize + insight ($0, FREE tier)
  Agent 5: REPORT     — Markdown + JSON + Supabase storage ($0, existing)

COST: $0 incremental (all existing paid/free services)
HUMAN-IN-THE-LOOP: None (all creds in GitHub Secrets)
"""

import json
import os
import re
import sys
import time
import urllib.request
import ssl
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
CLIPROXY_BASE_URL = os.environ.get("CLIPROXY_BASE_URL", "http://127.0.0.1:8317")
CLIPROXY_API_KEY = os.environ.get("CLIPROXY_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# SSL context for cloud environments
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def extract_video_id(url_or_id: str) -> str:
    """Extract video ID from URL or return as-is."""
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$',
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    raise ValueError(f"Cannot extract video ID from: {url_or_id}")


def format_timestamp(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"


def api_request(url: str, data: dict = None, headers: dict = None, method: str = "POST") -> dict:
    """Generic API request helper."""
    body = json.dumps(data).encode() if data else None
    hdrs = headers or {}
    if data:
        hdrs.setdefault("Content-Type", "application/json")
    
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        resp = urllib.request.urlopen(req, context=SSL_CTX, timeout=120)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        return {"error": f"HTTP {e.code}: {error_body[:500]}"}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
# AGENT 1: FETCH (Supadata → Firecrawl → youtube-transcript-api)
# ═══════════════════════════════════════════════════════════════

SUPADATA_API_KEY = os.environ.get("SUPADATA_API_KEY", "")


def agent_fetch_supadata(video_id: str) -> dict:
    """Primary: Fetch transcript via Supadata API (FREE, 100 req/mo)."""
    print(f"📡 AGENT 1: Supadata fetch for {video_id}...")
    
    if not SUPADATA_API_KEY:
        return {"status": "failed", "error": "SUPADATA_API_KEY not set"}
    
    result = api_request(
        f"https://api.supadata.ai/v1/transcript?url=https://youtu.be/{video_id}&text=true",
        headers={"x-api-key": SUPADATA_API_KEY},
        method="GET",
        data=None
    )
    
    if "error" in result:
        print(f"   ⚠️ Supadata error: {str(result['error'])[:200]}")
        return {"status": "failed", "error": result["error"]}
    
    content = result.get("content", "")
    lang = result.get("lang", "en")
    
    if not content or len(content) < 100:
        return {"status": "failed", "error": f"Insufficient content ({len(content)} chars)"}
    
    print(f"   ✅ Got transcript: {len(content):,} chars, {len(content.split()):,} words, lang={lang}")
    return {
        "status": "success",
        "video_id": video_id,
        "title": f"YouTube Video {video_id}",
        "raw_markdown": content,
        "char_count": len(content),
        "source": "supadata"
    }

def _firecrawl_scrape(url: str, formats=None, timeout=60000) -> dict:
    """Common Firecrawl scrape call."""
    return api_request(
        "https://api.firecrawl.dev/v2/scrape",
        data={"url": url, "formats": formats or ["markdown"], "timeout": timeout},
        headers={
            "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
            "Content-Type": "application/json"
        }
    )


def agent_fetch_firecrawl(video_id: str) -> dict:
    """Fetch transcript via Firecrawl scraping transcript aggregator sites.
    
    Strategy: Scrape free transcript sites that render YouTube captions as plain text.
    Firecrawl handles anti-bot; aggregator handles YouTube caption API.
    """
    print(f"🔥 AGENT 1: Firecrawl fetch for {video_id}...")
    
    if not FIRECRAWL_API_KEY:
        return {"status": "failed", "error": "FIRECRAWL_API_KEY not set"}
    
    # ── Strategy 1: Scrape youtubetranscript.com (renders full transcript) ──
    aggregator_urls = [
        f"https://youtubetranscript.com/?v={video_id}",
        f"https://tactiq.io/tools/youtube-transcript?videoId={video_id}",
    ]
    
    for agg_url in aggregator_urls:
        print(f"   Trying: {agg_url[:60]}...")
        result = _firecrawl_scrape(agg_url)
        
        if "error" not in result and result.get("success") and result.get("data"):
            md = result["data"].get("markdown", "")
            # Transcript sites produce text-heavy output — look for substantial content
            # Filter out short page-chrome results
            if md and len(md) > 500:
                # Extract title from YouTube metadata if available
                title = result["data"].get("metadata", {}).get("title", f"YouTube Video {video_id}")
                print(f"   ✅ Aggregator extracted {len(md):,} chars | {title[:50]}")
                return {
                    "status": "success",
                    "video_id": video_id,
                    "title": title,
                    "raw_markdown": md,
                    "char_count": len(md),
                    "source": f"firecrawl-aggregator"
                }
            else:
                print(f"   ⚠️ Too short ({len(md)} chars), trying next...")
    
    # ── Strategy 2: Scrape YouTube page with JSON extract for transcript ──
    print(f"   Trying: YouTube page with AI extract...")
    yt_url = f"https://www.youtube.com/watch?v={video_id}"
    result = api_request(
        "https://api.firecrawl.dev/v2/scrape",
        data={
            "url": yt_url,
            "formats": [
                "markdown",
                {"type": "json", "prompt": "Extract the complete video transcript/captions text, the video title, and the video description. Return all spoken words from the captions."}
            ],
            "timeout": 90000
        },
        headers={
            "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
            "Content-Type": "application/json"
        }
    )
    
    if "error" not in result and result.get("success") and result.get("data"):
        data = result["data"]
        # Check JSON extract first (AI-extracted transcript)
        json_data = data.get("json", {})
        transcript_text = ""
        if isinstance(json_data, dict):
            # Look for transcript-like fields
            for key in ["transcript", "captions", "text", "spoken_words", "content"]:
                if key in json_data and json_data[key]:
                    val = json_data[key]
                    if isinstance(val, list):
                        transcript_text = " ".join(str(v) for v in val)
                    else:
                        transcript_text = str(val)
                    if len(transcript_text) > 200:
                        break
        
        if transcript_text and len(transcript_text) > 200:
            title = json_data.get("title", data.get("metadata", {}).get("title", f"YouTube Video {video_id}"))
            print(f"   ✅ AI extract got {len(transcript_text):,} chars transcript")
            return {
                "status": "success",
                "video_id": video_id,
                "title": title,
                "raw_markdown": transcript_text,
                "char_count": len(transcript_text),
                "source": "firecrawl-ai-extract"
            }
        
        # Fall through to markdown with description/chapters
        md = data.get("markdown", "")
        if md and len(md) > 500:
            title = data.get("metadata", {}).get("title", f"YouTube Video {video_id}")
            print(f"   ✅ YouTube page markdown {len(md):,} chars (page content, not transcript)")
            return {
                "status": "success",
                "video_id": video_id,
                "title": title,
                "raw_markdown": md,
                "char_count": len(md),
                "source": "firecrawl-youtube-page"
            }
    
    return {"status": "failed", "error": "All Firecrawl strategies exhausted"}


def agent_fetch_transcript_api(video_id: str) -> dict:
    """Fallback: youtube-transcript-api (works from non-cloud IPs)."""
    print(f"📡 AGENT 1 FALLBACK: youtube-transcript-api for {video_id}...")
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        ytt = YouTubeTranscriptApi()
        transcript = ytt.fetch(video_id)
        
        segments = []
        for entry in transcript:
            segments.append({
                "start": float(entry.start),
                "duration": float(entry.duration),
                "text": entry.text.strip()
            })
        
        # Convert to markdown-like format
        md_lines = []
        for seg in segments:
            ts = format_timestamp(seg["start"])
            md_lines.append(f"[{ts}] {seg['text']}")
        
        md = "\n".join(md_lines)
        print(f"   ✅ Fetched {len(segments)} segments via transcript API")
        return {
            "status": "success",
            "video_id": video_id,
            "title": f"YouTube Video {video_id}",
            "raw_markdown": md,
            "char_count": len(md),
            "source": "youtube-transcript-api",
            "segments": segments
        }
    except Exception as e:
        print(f"   ❌ Fallback failed: {e}")
        return {"status": "failed", "error": str(e)}


def agent_fetch(video_id: str) -> dict:
    """Agent 1: Supadata first (FREE API), then youtube-transcript-api, then Firecrawl."""
    result = agent_fetch_supadata(video_id)
    if result["status"] == "success":
        return result
    
    print("   🔄 Supadata failed, trying youtube-transcript-api...")
    result = agent_fetch_transcript_api(video_id)
    if result["status"] == "success":
        return result
    
    print("   🔄 Transcript API failed, trying Firecrawl...")
    return agent_fetch_firecrawl(video_id)


# ═══════════════════════════════════════════════════════════════
# AGENT 2: CLEAN & CHUNK
# ═══════════════════════════════════════════════════════════════

def agent_clean(fetch_result: dict) -> dict:
    """Agent 2: Clean transcript into readable paragraphs."""
    print("📝 AGENT 2: Cleaning transcript...")
    
    raw = fetch_result.get("raw_markdown", "")
    if not raw:
        return {"status": "failed", "error": "No raw content"}
    
    # Remove common YouTube page artifacts
    # Strip navigation, ads, recommended videos noise
    lines = raw.split("\n")
    clean_lines = []
    skip_patterns = [
        r'^\s*$', r'^#{1,3}\s*(Subscribe|Like|Share|Comment)',
        r'^\[.*\]\(https?://.*\)$',  # bare links
        r'^!\[', r'^\*\*\d+[KMB]?\s*(views|subscribers)',
    ]
    
    for line in lines:
        skip = False
        for pat in skip_patterns:
            if re.match(pat, line, re.IGNORECASE):
                skip = True
                break
        if not skip:
            clean_lines.append(line)
    
    cleaned = "\n".join(clean_lines).strip()
    
    # Extract timestamped segments if present
    ts_pattern = r'\[(\d+:\d+(?::\d+)?)\]\s*(.*?)(?=\n\[|\Z)'
    ts_matches = re.findall(ts_pattern, cleaned, re.DOTALL)
    
    if ts_matches and len(ts_matches) > 3:
        chunks = []
        for ts, text in ts_matches:
            text = re.sub(r'\s+', ' ', text).strip()
            if text:
                chunks.append({"timestamp": ts, "text": text})
        
        full_text = "\n\n".join([f"[{c['timestamp']}] {c['text']}" for c in chunks])
    else:
        # No timestamps — chunk by paragraphs
        paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip() and len(p.strip()) > 20]
        chunks = [{"timestamp": f"p{i+1}", "text": p} for i, p in enumerate(paragraphs)]
        full_text = cleaned
    
    word_count = len(full_text.split())
    print(f"   ✅ {len(chunks)} chunks, {word_count:,} words")
    return {
        "status": "success",
        "chunks": chunks,
        "full_text": full_text,
        "word_count": word_count
    }


# ═══════════════════════════════════════════════════════════════
# AGENTS 3+4: AI SUMMARIZE + INSIGHT (Gemini Flash via CLIProxy)
# ═══════════════════════════════════════════════════════════════

ANALYSIS_PROMPT = """You are analyzing a YouTube video transcript for a real estate technology company (BidDeed.AI) that builds AI-powered foreclosure auction tools.

VIDEO TITLE: {title}
VIDEO ID: {video_id}

TRANSCRIPT:
{transcript}

---

Respond ONLY with valid JSON (no markdown fences, no preamble). Structure:

{{
  "tldr": "2-3 sentence summary of the entire video",
  "chapters": [
    {{"timestamp": "0:00", "title": "Chapter title", "summary": "1-2 sentence summary"}}
  ],
  "key_points": ["point 1", "point 2", "...up to 8 points"],
  "tools_mentioned": ["tool1", "tool2"],
  "tags": ["tag1", "tag2"],
  "biddeed_relevance": {{
    "score": 0-10,
    "reasons": ["reason1", "reason2"]
  }},
  "actionable_takeaways": [
    {{
      "action": "What to do",
      "effort": "LOW|MEDIUM|HIGH",
      "impact": "LOW|MEDIUM|HIGH",
      "details": "Implementation details specific to BidDeed.AI/foreclosure tech"
    }}
  ]
}}"""


def agent_ai_analyze(fetch_result: dict, clean_result: dict) -> dict:
    """Agents 3+4: Summarize + Insight via Gemini Flash (CLIProxyAPI)."""
    print("🧠 AGENTS 3+4: AI analysis via Gemini Flash...")
    
    title = fetch_result.get("title", "Unknown")
    video_id = fetch_result.get("video_id", "unknown")
    transcript = clean_result.get("full_text", "")
    
    # Truncate to ~100K chars for safety (Gemini handles 1M but be practical)
    if len(transcript) > 100000:
        transcript = transcript[:100000] + "\n\n[TRANSCRIPT TRUNCATED]"
    
    prompt = ANALYSIS_PROMPT.format(
        title=title, video_id=video_id, transcript=transcript
    )
    
    # Try CLIProxyAPI → Gemini Flash first
    gemini_result = _call_gemini_via_cliproxy(prompt)
    if gemini_result.get("status") == "success":
        return gemini_result
    
    # Direct Gemini API fallback
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        print("   🔄 CLIProxy failed, trying direct Gemini...")
        return _call_gemini_direct(prompt, gemini_key)
    
    # If all AI fails, return heuristic analysis
    print("   ⚠️ AI unavailable, using heuristic analysis")
    return _heuristic_analysis(clean_result, title, video_id)


def _call_gemini_via_cliproxy(prompt: str) -> dict:
    """Call Gemini Flash via CLIProxyAPI gateway."""
    if not CLIPROXY_BASE_URL or not CLIPROXY_API_KEY:
        return {"status": "failed", "error": "CLIProxy not configured"}
    
    result = api_request(
        f"{CLIPROXY_BASE_URL}/v1/chat/completions",
        data={
            "model": "gemini-2.5-flash",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.3
        },
        headers={
            "Authorization": f"Bearer {CLIPROXY_API_KEY}",
            "Content-Type": "application/json"
        }
    )
    
    if "error" in result:
        return {"status": "failed", "error": result["error"]}
    
    try:
        content = result["choices"][0]["message"]["content"]
        # Clean JSON fences if present
        content = re.sub(r'^```(?:json)?\s*', '', content.strip())
        content = re.sub(r'\s*```$', '', content.strip())
        analysis = json.loads(content)
        print(f"   ✅ Gemini Flash analysis: {len(analysis.get('key_points', []))} key points, "
              f"relevance {analysis.get('biddeed_relevance', {}).get('score', '?')}/10")
        return {"status": "success", "analysis": analysis, "source": "gemini-flash-cliproxy"}
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        return {"status": "failed", "error": f"Parse error: {e}"}


def _call_gemini_direct(prompt: str, api_key: str) -> dict:
    """Direct Gemini API call as fallback."""
    result = api_request(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
        data={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 4096}
        }
    )
    
    if "error" in result:
        print(f"   ⚠️ Gemini direct error: {str(result['error'])[:200]}")
        return {"status": "failed", "error": result["error"]}
    
    try:
        candidates = result.get("candidates", [])
        if not candidates:
            print(f"   ⚠️ No candidates in Gemini response. Keys: {list(result.keys())}")
            return {"status": "failed", "error": f"No candidates. Response keys: {list(result.keys())}"}
        
        content = candidates[0]["content"]["parts"][0]["text"]
        content = re.sub(r'^```(?:json)?\s*', '', content.strip())
        content = re.sub(r'\s*```$', '', content.strip())
        analysis = json.loads(content)
        print(f"   ✅ Gemini Flash (direct): {len(analysis.get('key_points', []))} key points, "
              f"relevance {analysis.get('biddeed_relevance', {}).get('score', '?')}/10")
        return {"status": "success", "analysis": analysis, "source": "gemini-flash-direct"}
    except json.JSONDecodeError as e:
        # Log what we got
        raw = content[:300] if 'content' in dir() else "no content"
        print(f"   ⚠️ JSON parse failed: {e}. Raw: {raw}")
        return {"status": "failed", "error": f"JSON parse: {e}"}
    except Exception as e:
        print(f"   ⚠️ Gemini parse error: {e}")
        return {"status": "failed", "error": f"Direct Gemini parse error: {e}"}


def _heuristic_analysis(clean_result: dict, title: str, video_id: str) -> dict:
    """Fallback heuristic analysis when AI is unavailable."""
    text = clean_result.get("full_text", "").lower()
    
    tags = [t for t in [
        'obsidian', 'claude code', 'second brain', 'productivity',
        'ai', 'automation', 'markdown', 'vault', 'pipeline',
        'slash commands', 'canvas', 'file processing', 'cli'
    ] if t in text]
    
    return {
        "status": "success",
        "analysis": {
            "tldr": f"Video about {', '.join(tags[:3]) or 'various topics'}. Full AI analysis unavailable.",
            "chapters": [],
            "key_points": [],
            "tools_mentioned": tags[:5],
            "tags": tags,
            "biddeed_relevance": {"score": 0, "reasons": ["AI analysis unavailable"]},
            "actionable_takeaways": []
        },
        "source": "heuristic"
    }


# ═══════════════════════════════════════════════════════════════
# AGENT 5: REPORT + STORE
# ═══════════════════════════════════════════════════════════════

def agent_report(video_id: str, fetch_result: dict, clean_result: dict, ai_result: dict) -> dict:
    """Agent 5: Generate markdown report + JSON metadata + Supabase store."""
    print("📊 AGENT 5: Generating report...")
    
    now = datetime.now(timezone.utc).isoformat()
    title = fetch_result.get("title", "Unknown")
    analysis = ai_result.get("analysis", {})
    word_count = clean_result.get("word_count", 0)
    
    # ── Markdown Report ──
    md = [
        f"# 🎬 YouTube Transcript Analysis",
        f"",
        f"**Video:** [{title}](https://youtu.be/{video_id})",
        f"**Words:** {word_count:,} | **Generated:** {now}",
        f"**Tags:** {', '.join(f'`{t}`' for t in analysis.get('tags', []))}",
        f"**Source:** {fetch_result.get('source', 'unknown')} → {ai_result.get('source', 'unknown')}",
        f"",
        f"## 📋 TL;DR",
        f"",
        f"{analysis.get('tldr', 'N/A')}",
        f"",
    ]
    
    # Relevance
    rel = analysis.get("biddeed_relevance", {})
    md.append(f"## 🎯 BidDeed.AI Relevance: {rel.get('score', 0)}/10")
    md.append("")
    for r in rel.get("reasons", []):
        md.append(f"- {r}")
    md.append("")
    
    # Chapters
    chapters = analysis.get("chapters", [])
    if chapters:
        md.append("## 📖 Chapters")
        md.append("")
        for i, ch in enumerate(chapters, 1):
            md.append(f"### {i}. [{ch.get('timestamp', '?')}] {ch.get('title', 'Section')}")
            md.append(f"{ch.get('summary', '')}")
            md.append("")
    
    # Key Points
    points = analysis.get("key_points", [])
    if points:
        md.append("## 🔑 Key Points")
        md.append("")
        for i, p in enumerate(points, 1):
            md.append(f"{i}. {p}")
        md.append("")
    
    # Takeaways
    takeaways = analysis.get("actionable_takeaways", [])
    if takeaways:
        md.append("## 💡 Actionable Takeaways")
        md.append("")
        md.append("| # | Action | Effort | Impact |")
        md.append("|---|--------|--------|--------|")
        for i, t in enumerate(takeaways, 1):
            md.append(f"| {i} | {t.get('action', '')} | {t.get('effort', '')} | {t.get('impact', '')} |")
        md.append("")
        for t in takeaways:
            md.append(f"**{t.get('action', '')}**")
            md.append(f"_{t.get('details', '')}_")
            md.append("")
    
    # Full Transcript
    md.append("## 📝 Full Transcript")
    md.append("")
    md.append(clean_result.get("full_text", "N/A"))
    
    report_md = "\n".join(md)
    
    # ── JSON Metadata ──
    metadata = {
        "video_id": video_id,
        "video_url": f"https://youtu.be/{video_id}",
        "title": title,
        "generated_at": now,
        "pipeline": "cli-anything-youtube-v1.0",
        "fetch_source": fetch_result.get("source", "unknown"),
        "ai_source": ai_result.get("source", "unknown"),
        "stats": {
            "word_count": word_count,
            "chunk_count": len(clean_result.get("chunks", [])),
            "char_count": fetch_result.get("char_count", 0)
        },
        "analysis": analysis
    }
    
    # ── Supabase Store ──
    if SUPABASE_URL and SUPABASE_SERVICE_KEY:
        _store_supabase(metadata)
    
    print(f"   ✅ Report: {len(report_md):,} chars markdown + JSON")
    return {"status": "success", "markdown": report_md, "metadata": metadata}


def _store_supabase(metadata: dict):
    """Store transcript analysis in Supabase."""
    try:
        result = api_request(
            f"{SUPABASE_URL}/rest/v1/youtube_transcripts",
            data={
                "video_id": metadata["video_id"],
                "title": metadata.get("title", ""),
                "video_url": metadata["video_url"],
                "analysis": json.dumps(metadata.get("analysis", {})),
                "word_count": metadata["stats"]["word_count"],
                "relevance_score": metadata.get("analysis", {}).get("biddeed_relevance", {}).get("score", 0),
                "pipeline_version": metadata["pipeline"],
                "created_at": metadata["generated_at"]
            },
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
        )
        if "error" not in result:
            print(f"   ✅ Stored in Supabase youtube_transcripts")
        else:
            print(f"   ⚠️ Supabase store skipped: {str(result.get('error', ''))[:100]}")
    except Exception as e:
        print(f"   ⚠️ Supabase store failed: {e}")


# ═══════════════════════════════════════════════════════════════
# PIPELINE ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════

def run_pipeline(url_or_id: str) -> dict:
    """Run the full 5-agent pipeline."""
    print("=" * 70)
    print("🎬 YOUTUBE TRANSCRIPT AI SQUAD v1.0")
    print("   cli-anything-youtube | BidDeed.AI")
    print("   Firecrawl → Clean → Gemini Flash → Report → Supabase")
    print("=" * 70)
    
    start = time.time()
    video_id = extract_video_id(url_or_id)
    print(f"\n🎯 Target: https://youtu.be/{video_id}\n")
    
    # Agent 1: Fetch
    fetch = agent_fetch(video_id)
    if fetch["status"] != "success":
        return {"status": "failed", "stage": "fetch", "error": fetch.get("error")}
    
    # Agent 2: Clean
    clean = agent_clean(fetch)
    if clean["status"] != "success":
        return {"status": "failed", "stage": "clean", "error": clean.get("error")}
    
    # Agents 3+4: AI Analysis
    ai = agent_ai_analyze(fetch, clean)
    
    # Agent 5: Report
    report = agent_report(video_id, fetch, clean, ai)
    
    elapsed = time.time() - start
    
    print(f"\n{'=' * 70}")
    print(f"✅ PIPELINE COMPLETE in {elapsed:.1f}s")
    print(f"   Source: {fetch.get('source')} → {ai.get('source', 'N/A')}")
    print(f"   Words: {clean.get('word_count', 0):,} | Cost: $0.00")
    print(f"{'=' * 70}")
    
    return {
        "status": "success",
        "elapsed_sec": round(elapsed, 1),
        "video_id": video_id,
        "report": report
    }


# ═══════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python yt_transcript_squad.py <youtube_url_or_id>")
        print("Example: python yt_transcript_squad.py 2kbINqpluM0")
        sys.exit(1)
    
    result = run_pipeline(sys.argv[1])
    
    if result["status"] == "success":
        report = result["report"]
        
        # Write outputs
        out_dir = os.environ.get("OUTPUT_DIR", ".")
        os.makedirs(out_dir, exist_ok=True)
        
        vid = result["video_id"]
        md_path = os.path.join(out_dir, f"transcript_{vid}.md")
        json_path = os.path.join(out_dir, f"transcript_{vid}.json")
        
        with open(md_path, "w") as f:
            f.write(report["markdown"])
        with open(json_path, "w") as f:
            json.dump(report["metadata"], f, indent=2)
        
        print(f"\n📁 Output: {md_path}")
        print(f"📁 Output: {json_path}")
    else:
        print(f"\n❌ FAILED at stage: {result.get('stage', 'unknown')}")
        print(f"   Error: {result.get('error', 'unknown')}")
        sys.exit(1)
