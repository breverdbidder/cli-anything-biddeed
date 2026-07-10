#!/usr/bin/env python3
"""
analyze.py — Viral analytics collection + winner extraction + feedback loop.
Port of GVB /viral:analyze command for BidDeed.AI Supabase stack.

Usage:
  python3 analyze.py --manual --all
  python3 analyze.py --manual --youtube
  python3 analyze.py --deep-analysis
"""

import argparse
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request

# Allow running from any directory
sys.path.insert(0, os.path.dirname(__file__))

from supabase_client import (
    get_brain,
    get_analytics,
    save_analytics,
    save_brain,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def days_since(dt_str: str) -> int:
    try:
        dt = datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        delta = datetime.datetime.now(datetime.timezone.utc) - dt
        return max(0, delta.days)
    except Exception:
        return 0


def analytics_id(date_str: str, seq: int) -> str:
    return f"analytics_{date_str}_{seq:03d}"


def today_str() -> str:
    return datetime.date.today().strftime("%Y%m%d")


def parse_iso8601_duration(duration: str) -> int:
    """Parse PT11M8S → 668 seconds."""
    import re
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not m:
        return 0
    h, mn, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mn * 60 + s


def safe_int(val, default=0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def engagement_rate(views: int, likes: int, comments: int) -> float:
    if views <= 0:
        return 0.0
    return round((likes + comments) / views * 100, 2)


def median(values: list) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return float(s[n // 2])
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


# ── YouTube Data API ──────────────────────────────────────────────────────────

def yt_api_call(endpoint: str, params: dict, api_key: str) -> dict:
    params["key"] = api_key
    qs = urllib.parse.urlencode(params)
    url = f"https://www.googleapis.com/youtube/v3/{endpoint}?{qs}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}


def fetch_youtube_channel(yt_key: str, channel_id: str = None, handle: str = None) -> dict | None:
    """Return {channel_id, uploads_playlist_id, title} or None."""
    if channel_id:
        data = yt_api_call("channels", {"part": "id,contentDetails,snippet", "id": channel_id}, yt_key)
    elif handle:
        data = yt_api_call("channels", {"part": "id,contentDetails,snippet", "forHandle": handle}, yt_key)
    else:
        return None

    items = data.get("items", [])
    if not items:
        return None

    ch = items[0]
    return {
        "channel_id": ch["id"],
        "title": ch["snippet"]["title"],
        "uploads_playlist": ch["contentDetails"]["relatedPlaylists"]["uploads"],
    }


def fetch_uploads(playlist_id: str, yt_key: str, max_results: int = 50) -> list[str]:
    """Return list of video IDs from uploads playlist."""
    items = []
    page_token = None
    while len(items) < max_results:
        params = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": min(50, max_results - len(items)),
        }
        if page_token:
            params["pageToken"] = page_token
        data = yt_api_call("playlistItems", params, yt_key)
        if "error" in data:
            break
        for item in data.get("items", []):
            vid_id = item["snippet"]["resourceId"].get("videoId")
            if vid_id:
                items.append(vid_id)
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return items


def fetch_video_stats(video_ids: list[str], yt_key: str) -> list[dict]:
    """Batch fetch statistics + contentDetails for up to 50 video IDs."""
    results = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        data = yt_api_call(
            "videos",
            {"part": "statistics,contentDetails,snippet", "id": ",".join(batch)},
            yt_key,
        )
        for item in data.get("items", []):
            stats = item.get("statistics", {})
            cd = item.get("contentDetails", {})
            sn = item.get("snippet", {})
            duration_s = parse_iso8601_duration(cd.get("duration", "PT0S"))
            views = safe_int(stats.get("viewCount", 0))
            likes = safe_int(stats.get("likeCount", 0))
            comments = safe_int(stats.get("commentCount", 0))
            fmt = "youtube_shorts" if duration_s < 60 else "youtube_longform"
            results.append({
                "video_id": item["id"],
                "title": sn.get("title", ""),
                "published_at": sn.get("publishedAt", ""),
                "duration_seconds": duration_s,
                "format": fmt,
                "views": views,
                "likes": likes,
                "comments": comments,
                "source_url": f"https://www.youtube.com/watch?v={item['id']}",
                "engagement_rate": engagement_rate(views, likes, comments),
                "subscribers_gained": None,
                "thumbnail_url": sn.get("thumbnails", {}).get("high", {}).get("url"),
            })
    return results


def composite_score(video: dict) -> float:
    """Score for ranking top 10."""
    fmt = video.get("format", "youtube_longform")
    views = video.get("views", 0)
    subs = video.get("subscribers_gained") or 0
    eng = video.get("engagement_rate", 0)

    if fmt == "youtube_longform":
        if video.get("subscribers_gained") is None:
            # redistribute subs weight
            return views * 0.583 + eng * 1000 * 0.417
        return views * 0.35 + subs * 500 * 0.40 + eng * 1000 * 0.25
    else:
        return views * 0.55 + eng * 1000 * 0.45


# ── Winner extraction ─────────────────────────────────────────────────────────

WINNER_THRESHOLDS = {
    "youtube_longform": [
        ("ctr", 1.5),
        ("avg_view_percentage", 1.3),
        ("engagement_rate", 2.0),
    ],
    "youtube_shorts": [
        ("views", 2.0),
        ("completion_rate", 1.3),
    ],
    "instagram_reels": [
        ("views", 2.0),
        ("completion_rate", 1.3),
    ],
}


def extract_winners(new_entries: list[dict], all_entries: list[dict]) -> list[dict]:
    """Mark winners in new_entries based on platform medians from all_entries."""
    # Build per-platform medians
    platform_data: dict[str, dict[str, list]] = {}
    for e in all_entries:
        plat = e.get("platform", "")
        if plat not in platform_data:
            platform_data[plat] = {}
        m = e.get("metrics", {})
        for key in ["ctr", "avg_view_percentage", "engagement_rate", "views", "completion_rate"]:
            val = m.get(key)
            if val is not None:
                platform_data.setdefault(plat, {}).setdefault(key, []).append(float(val))

    results = []
    for entry in new_entries:
        plat = entry.get("platform", "")
        thresholds = WINNER_THRESHOLDS.get(plat, [])
        pd = platform_data.get(plat, {})

        # Need at least 2 historical entries for baseline
        total_plat = sum(1 for e in all_entries if e.get("platform") == plat)
        if total_plat < 2:
            results.append(entry)
            continue

        m = entry.get("metrics", {})
        is_winner = False
        winner_reason = None

        for metric, multiplier in thresholds:
            vals = pd.get(metric, [])
            if not vals:
                continue
            plat_median = median(vals)
            entry_val = m.get(metric)
            if entry_val is None:
                continue
            entry_val = float(entry_val)
            threshold_val = plat_median * multiplier
            if entry_val >= threshold_val and plat_median > 0:
                is_winner = True
                ratio = round(entry_val / plat_median, 1)
                winner_reason = (
                    f"{metric} {entry_val:.1f} exceeds platform median "
                    f"{plat_median:.1f} by {ratio}x"
                )
                break

        if is_winner:
            entry["is_winner"] = True
            entry["winner_reason"] = winner_reason
        results.append(entry)

    return results


# ── Phase H: Feedback loop ─────────────────────────────────────────────────────

def run_feedback_loop(brain: dict, all_entries: list[dict], new_entries: list[dict]) -> dict:
    """Update brain learning_weights and hook_preferences based on analytics."""
    total = len(all_entries)
    if total < 5:
        print(f"\n🧠 Feedback loop needs more data ({total}/5 entries). Brain unchanged.")
        return brain

    # A. hook_preferences — adjust based on win rate per pattern
    hook_prefs = brain.get("hook_preferences", {
        "contradiction": 0, "specificity": 0, "timeframe_tension": 0,
        "pov_as_advice": 0, "vulnerable_confession": 0, "pattern_interrupt": 0,
    })

    for pattern in hook_prefs:
        matching = [e for e in all_entries if e.get("hook_pattern_used") == pattern]
        if len(matching) < 2:
            continue
        winners = [e for e in matching if e.get("is_winner")]
        win_rate = len(winners) / len(matching) if matching else 0
        current = float(hook_prefs.get(pattern, 0))
        if win_rate >= 0.5:
            hook_prefs[pattern] = min(5.0, current + 0.5)
        elif win_rate == 0 and len(matching) >= 3:
            hook_prefs[pattern] = max(-2.0, current - 0.2)

    brain["hook_preferences"] = hook_prefs

    # B. learning_weights — boost icp_relevance if winning pillars
    weights = brain.get("learning_weights", {
        "icp_relevance": 1.0, "timeliness": 1.0,
        "content_gap": 1.0, "proof_potential": 1.0,
    })
    pillars_seen: dict[str, list] = {}
    for e in all_entries:
        pillar = e.get("content_pillar")
        if not pillar:
            continue
        pillars_seen.setdefault(pillar, []).append(e)

    for pillar, entries in pillars_seen.items():
        if len(entries) < 2:
            continue
        win_rate = sum(1 for e in entries if e.get("is_winner")) / len(entries)
        if win_rate >= 0.5:
            weights["icp_relevance"] = min(2.0, float(weights.get("icp_relevance", 1.0)) + 0.1)

    brain["learning_weights"] = weights

    # C. performance_patterns
    perf = brain.get("performance_patterns", {})
    perf["total_content_analyzed"] = total

    ctrs = [float(e["metrics"]["ctr"]) for e in all_entries if e.get("metrics", {}).get("ctr") is not None]
    if ctrs:
        perf["avg_ctr"] = round(sum(ctrs) / len(ctrs), 1)

    ret30s = [float(e["metrics"]["retention_30s"]) for e in all_entries if e.get("metrics", {}).get("retention_30s") is not None]
    if ret30s:
        perf["avg_retention_30s"] = round(sum(ret30s) / len(ret30s), 1)

    brain["performance_patterns"] = perf

    # D. evolution log
    meta = brain.get("metadata", {})
    log = meta.get("evolution_log", [])
    log.append({
        "timestamp": now_iso(),
        "reason": "Auto-update via analyze.py feedback loop",
        "changes": [
            f"hook_preferences updated for {len(hook_prefs)} patterns",
            f"performance_patterns: {total} total analyzed",
            f"avg_ctr: {perf.get('avg_ctr', 'n/a')}",
        ],
    })
    meta["evolution_log"] = log[-50:]  # keep last 50
    meta["updated_at"] = now_iso()
    brain["metadata"] = meta

    return brain


# ── Display helpers ───────────────────────────────────────────────────────────

def print_top10(videos: list[dict]) -> None:
    print("\n════════════════════════════════════════")
    print("📊 YOUR TOP 10 PERFORMING CONTENT")
    print("════════════════════════════════════════")
    print(f" {'#':<3} {'Platform':<20} {'Title':<45} {'Views':<10} {'Eng%':<8} {'Subs+'}")
    print("─" * 100)
    for i, v in enumerate(videos[:10], 1):
        plat = v.get("format", v.get("platform", "unknown"))
        title = v.get("title", v.get("caption", ""))[:44]
        views = v.get("views", 0)
        eng = v.get("engagement_rate", 0)
        subs = v.get("subscribers_gained")
        subs_str = f"+{subs}" if subs is not None else "—"
        url = v.get("source_url", "")
        print(f" {i:<3} {plat:<20} {title:<45} {views:<10} {eng:<8.2f} {subs_str}")
        print(f"     {'':20} {url}")
    print("════════════════════════════════════════")


def print_winner_summary(new_entries: list[dict]) -> None:
    winners = [e for e in new_entries if e.get("is_winner")]
    losers = [e for e in new_entries if not e.get("is_winner")]
    print("\n════════════════════════════════════════")
    print("WINNER EXTRACTION")
    print("════════════════════════════════════════")
    if winners:
        print(f"Winners: {len(winners)} of {len(new_entries)}\n")
        for w in winners:
            print(f"🏆 {w.get('title', w.get('content_id', ''))} — {w.get('platform', '')}")
            print(f"   {w.get('winner_reason', '')}")
    else:
        print("No winners this batch. Content is tracking near baseline.")
    if losers:
        titles = [e.get("title", e.get("content_id", "")) for e in losers]
        print(f"\nDid not qualify: {', '.join(titles)}")
    print("════════════════════════════════════════")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Viral content analytics pipeline")
    parser.add_argument("--manual", action="store_true", help="Non-interactive cron mode")
    parser.add_argument("--all", action="store_true", dest="all_platforms", help="All platforms")
    parser.add_argument("--youtube", action="store_true")
    parser.add_argument("--instagram", action="store_true")
    parser.add_argument("--deep-analysis", action="store_true")
    args = parser.parse_args()

    print("════════════════════════════════════════")
    print("/viral:analyze — Performance Analytics")
    print(f"Mode: {'manual' if args.manual else 'interactive'} | Platforms: {'all' if args.all_platforms else 'selected'}")
    print(f"Timestamp: {now_iso()}")
    print("════════════════════════════════════════")

    # ── Phase A: Load brain ───────────────────────────────────────────────────
    brain = get_brain()
    if not brain:
        print("\n⚠ No agent brain found. Run /viral:onboard first to configure.")
        print("  Continuing with defaults — no YouTube channel configured.")
        brain = {}

    platforms_cfg = brain.get("platforms", {})
    api_keys = platforms_cfg.get("api_keys_configured", [])

    yt_key = os.environ.get("YOUTUBE_DATA_API_KEY") or os.environ.get("YOUTUBE_API_KEY", "")
    channel_id = os.environ.get("YOUTUBE_CHANNEL_ID", "")
    handle = (brain.get("identity", {}).get("youtube_handle") or
               platforms_cfg.get("handles", {}).get("youtube", ""))

    youtube_available = bool(yt_key)
    instagram_available = bool(os.environ.get("INSTAGRAM_ACCESS_TOKEN", ""))

    print(f"\nYouTube API: {'✓' if youtube_available else '✗ (YOUTUBE_DATA_API_KEY not set)'}")
    print(f"Instagram:   {'✓' if instagram_available else '✗ (no token)'}")

    # ── Phase B: Collect data ─────────────────────────────────────────────────
    all_videos: list[dict] = []

    if youtube_available and (args.all_platforms or args.youtube):
        print("\n🔄 Scanning YouTube channel...")
        ch = fetch_youtube_channel(yt_key, channel_id=channel_id or None, handle=handle or None)
        if not ch:
            print("   ✗ Could not resolve YouTube channel. Set YOUTUBE_CHANNEL_ID env var.")
        else:
            print(f"   Channel: {ch['title']}")
            video_ids = fetch_uploads(ch["uploads_playlist"], yt_key, max_results=50)
            print(f"   Found {len(video_ids)} videos — fetching stats...")
            videos = fetch_video_stats(video_ids, yt_key)
            longform = [v for v in videos if v["format"] == "youtube_longform"]
            shorts = [v for v in videos if v["format"] == "youtube_shorts"]
            print(f"   ✓ YouTube: {len(videos)} videos ({len(longform)} longform, {len(shorts)} shorts)")
            all_videos.extend(videos)
    else:
        if not youtube_available:
            print("\n⏩ YouTube skipped — no API key.")
        elif not (args.all_platforms or args.youtube):
            print("\n⏩ YouTube skipped — not in scope.")

    if instagram_available and (args.all_platforms or args.instagram):
        print("\n🔄 Scanning Instagram...")
        # Instagram Graph API mode
        ig_token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
        ig_url = f"https://graph.instagram.com/me/media?fields=id,caption,media_type,media_url,timestamp,like_count,comments_count,video_views&access_token={ig_token}"
        try:
            with urllib.request.urlopen(ig_url, timeout=15) as r:
                ig_data = json.loads(r.read().decode())
            reels = [
                {
                    "video_id": item["id"],
                    "title": (item.get("caption", "")[:80] or f"Reel {item['id']}"),
                    "caption": item.get("caption", ""),
                    "published_at": item.get("timestamp", ""),
                    "format": "instagram_reels",
                    "views": safe_int(item.get("video_views", 0)),
                    "likes": safe_int(item.get("like_count", 0)),
                    "comments": safe_int(item.get("comments_count", 0)),
                    "source_url": f"https://www.instagram.com/p/{item['id']}/",
                    "engagement_rate": engagement_rate(
                        safe_int(item.get("video_views", 0)),
                        safe_int(item.get("like_count", 0)),
                        safe_int(item.get("comments_count", 0)),
                    ),
                    "subscribers_gained": None,
                }
                for item in ig_data.get("data", [])
                if item.get("media_type") in ("VIDEO", "REEL")
            ]
            print(f"   ✓ Instagram: {len(reels)} Reels loaded")
            all_videos.extend(reels)
        except Exception as e:
            print(f"   ⚠ Instagram scan skipped — {e}")
    elif not (args.all_platforms or args.instagram):
        pass  # silently skip
    else:
        print("\n⏩ Instagram skipped — no access token.")

    # ── Phase B.3-4: Score & rank top 10 ────────────────────────────────────
    if not all_videos:
        print("\n════════════════════════════════════════")
        print("ANALYZE COMPLETE — No content collected")
        print("════════════════════════════════════════")
        print("\nNo YouTube or Instagram data available.")
        print("Configure APIs to enable automatic collection:")
        print("  YOUTUBE_DATA_API_KEY — YouTube Data API v3")
        print("  YOUTUBE_CHANNEL_ID   — Your channel ID")
        print("  INSTAGRAM_ACCESS_TOKEN — Instagram Graph API")

        # Still check existing analytics for winner extraction
        all_analytics = get_analytics()
        print(f"\nExisting analytics rows: {len(all_analytics)}")
        if len(all_analytics) >= 5:
            print("✅ Feedback loop ready — existing data available for brain update.")
        else:
            print(f"📊 {len(all_analytics)}/5 entries. Feedback loop activates after 5+.")
        return

    # Sort by composite score
    all_videos.sort(key=composite_score, reverse=True)
    print_top10(all_videos)

    # ── Phase E-F: Build + save analytics entries ─────────────────────────────
    existing_analytics = get_analytics()
    seq_start = len(existing_analytics)
    date_prefix = today_str()

    new_entries = []
    for i, v in enumerate(all_videos[:10]):
        entry_id = analytics_id(date_prefix, seq_start + i + 1)
        published_at = v.get("published_at", "")
        entry = {
            "id": entry_id,
            "content_id": v.get("video_id", f"adhoc_{date_prefix}_{i:03d}"),
            "platform": v.get("format", "youtube_longform"),
            "published_at": published_at or None,
            "analyzed_at": now_iso(),
            "days_since_publish": days_since(published_at) if published_at else 0,
            "metrics": {
                "views": v.get("views"),
                "likes": v.get("likes"),
                "comments": v.get("comments"),
                "engagement_rate": v.get("engagement_rate"),
                "subscribers_gained": v.get("subscribers_gained"),
            },
            "is_winner": False,
            "winner_reason": None,
            "collection_method": "youtube_data_api" if "youtube" in v.get("format", "") else "instagram_graph_api",
            "source_url": v.get("source_url"),
            "title": v.get("title", ""),
            "notes": "",
        }
        # Remove None metric values
        entry["metrics"] = {k: val for k, val in entry["metrics"].items() if val is not None}
        new_entries.append(entry)

    print(f"\n💾 Saving {len(new_entries)} analytics entries...")
    saved = 0
    for entry in new_entries:
        result = save_analytics(entry)
        if "error" not in result:
            saved += 1
    print(f"   ✓ {saved}/{len(new_entries)} saved to viral_analytics")

    # ── Phase G: Winner extraction ────────────────────────────────────────────
    all_analytics = get_analytics()
    total_entries = len(all_analytics)
    print(f"\n📊 Total analytics entries (all time): {total_entries}")

    if total_entries < 5:
        print(f"⏩ Winner extraction needs {5 - total_entries} more entries (need 5).")
    else:
        print("🏆 Running winner extraction...")
        new_entries = extract_winners(new_entries, all_analytics)
        print_winner_summary(new_entries)

        # Persist winner status
        for entry in new_entries:
            if entry.get("is_winner"):
                save_analytics(entry)

    # ── Phase H: Feedback loop ────────────────────────────────────────────────
    if total_entries >= 5:
        print("\n🧠 Running feedback loop...")
        updated_brain = run_feedback_loop(brain, all_analytics, new_entries)
        result = save_brain(updated_brain)
        if "error" not in (result if isinstance(result, dict) else {}):
            print("   ✓ Brain updated in Supabase")
        else:
            print(f"   ⚠ Brain save failed: {result}")

    print("\n════════════════════════════════════════")
    print("WEEKLY ANALYSIS COMPLETE")
    print(f"  Videos analyzed: {len(new_entries)}")
    print(f"  Winners found:   {sum(1 for e in new_entries if e.get('is_winner'))}")
    print(f"  Total DB entries: {total_entries}")
    print(f"  Timestamp: {now_iso()}")
    print("════════════════════════════════════════")
    print("\nNext: Run update_brain.py for full brain evolution.")


if __name__ == "__main__":
    main()
