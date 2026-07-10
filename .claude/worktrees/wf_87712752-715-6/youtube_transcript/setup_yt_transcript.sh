#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# YouTube Transcript Squad — One-Time Hetzner Setup
# Run: ssh root@87.99.129.125 < setup_yt_transcript.sh
# ═══════════════════════════════════════════════════════════════

set -e

echo "🎬 Setting up YouTube Transcript Squad on Hetzner..."

# 1. Create working directory
mkdir -p /opt/yt-transcript/output
echo "   ✅ Created /opt/yt-transcript/"

# 2. Install youtube-transcript-api
pip3 install youtube-transcript-api --break-system-packages -q 2>/dev/null || \
pip install youtube-transcript-api --break-system-packages -q 2>/dev/null || \
pip3 install youtube-transcript-api -q
echo "   ✅ Installed youtube-transcript-api"

# 3. Test transcript fetch (THIS is the critical test)
echo "   🧪 Testing transcript fetch from Hetzner IP..."
python3 -c "
from youtube_transcript_api import YouTubeTranscriptApi
ytt = YouTubeTranscriptApi()
t = ytt.fetch('2kbINqpluM0')
segs = list(t)
print(f'   ✅ TEST PASSED: {len(segs)} segments fetched')
print(f'   First segment: {segs[0].text[:80]}...')
" 2>&1

if [ $? -ne 0 ]; then
    echo "   ❌ TEST FAILED: Hetzner IP may also be blocked"
    echo "   Fallback: Will use Firecrawl aggregator scraping"
    exit 1
fi

# 4. Verify CLIProxyAPI is reachable
echo "   🧪 Testing CLIProxyAPI (Gemini Flash)..."
HEALTH=$(curl -s --max-time 5 http://127.0.0.1:8317/health 2>/dev/null || echo "unreachable")
if echo "$HEALTH" | grep -qi "ok\|healthy\|alive"; then
    echo "   ✅ CLIProxyAPI is live"
else
    echo "   ⚠️ CLIProxyAPI not responding (Gemini analysis will use direct API)"
fi

echo ""
echo "══════════════════════════════════════════════════════════"
echo "✅ SETUP COMPLETE"
echo ""
echo "To test manually:"
echo "  cd /opt/yt-transcript"
echo "  python3 yt_transcript_squad.py 'https://youtu.be/2kbINqpluM0'"
echo ""
echo "To trigger via GitHub Actions:"
echo "  Go to: github.com/breverdbidder/cli-anything-biddeed/actions"
echo "  Run: 'YouTube Transcript Squad' workflow"
echo "  Paste any YouTube URL"
echo "══════════════════════════════════════════════════════════"
