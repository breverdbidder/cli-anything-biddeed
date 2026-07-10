"""
Supadata transcript adapter — replaces OpenAI Whisper for video transcription.
FREE tier: 100 videos/month.
"""

import json
import urllib.request
import os

SUPADATA_API_KEY = os.environ.get("SUPADATA_API_KEY", "sd_3c7a57546da7893f9ae3056a664d5dc9")
BASE_URL = "https://api.supadata.ai/v1/youtube"


def get_transcript(video_url: str, text_only: bool = True) -> dict:
    """
    Fetch YouTube transcript via Supadata API.
    
    Args:
        video_url: YouTube URL (any format: watch, shorts, youtu.be)
        text_only: If True, returns plain text. If False, returns timestamped segments.
    
    Returns:
        dict with keys: content (str or list), lang (str), status (str)
    """
    url = f"{BASE_URL}/transcript?url={video_url}&text_only={'true' if text_only else 'false'}"
    req = urllib.request.Request(url, headers={"x-api-key": SUPADATA_API_KEY})
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        
        if text_only:
            # text_only=true returns content as list of segment objects
            segments = data.get("content", [])
            if isinstance(segments, list):
                full_text = " ".join(seg.get("text", "") for seg in segments)
            else:
                full_text = str(segments)
            
            return {
                "content": full_text,
                "lang": data.get("lang", "en"),
                "char_count": len(full_text),
                "word_count": len(full_text.split()),
                "status": "success",
                "source": "supadata"
            }
        else:
            return {
                "content": data.get("content", []),
                "lang": data.get("lang", "en"),
                "status": "success",
                "source": "supadata"
            }
    
    except urllib.error.HTTPError as e:
        return {"status": "failed", "error": f"HTTP {e.code}: {e.reason}", "source": "supadata"}
    except urllib.error.URLError as e:
        return {"status": "failed", "error": str(e.reason), "source": "supadata"}
    except Exception as e:
        return {"status": "failed", "error": str(e), "source": "supadata"}


def get_video_info(video_url: str) -> dict:
    """Fetch video metadata (title, channel, duration, etc.)."""
    url = f"{BASE_URL}/info?url={video_url}"
    req = urllib.request.Request(url, headers={"x-api-key": SUPADATA_API_KEY})
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python supadata_transcript.py <youtube_url>")
        sys.exit(1)
    
    result = get_transcript(sys.argv[1])
    if result["status"] == "success":
        print(f"Language: {result['lang']}")
        print(f"Words: {result['word_count']}")
        print(f"Chars: {result['char_count']}")
        print(f"\n{result['content'][:500]}...")
    else:
        print(f"Error: {result['error']}")
