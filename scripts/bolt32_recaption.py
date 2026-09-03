#!/usr/bin/env python3
"""Re-caption an already-rendered bolt32 reel with real whisperX/faster-whisper
word-level captions (issue #19787), replacing the hand-timed beat title-card
captions. Downloads the existing video_bolt32_url, extracts audio, transcribes,
groups into 3-5 word captions, burns them in as a second overlay layer, and
uploads the result to video_bolt32_captions_url.

Usage:
  python3 scripts/bolt32_recaption.py --id <row-uuid>
  python3 scripts/bolt32_recaption.py --id <row-uuid> --allow-session-substitute
      # only if faster-whisper's HF Hub model download is unreachable
      # (confirmed live 2026-09-03: CloudFront 429 on both the metadata API
      # and the CDN resolve endpoint from this session's network egress) --
      # falls back to openai-whisper, LOCAL-ONLY, never added to
      # requirements-bolt32.txt, and always logged as
      # captions_source='openai_whisper_session_substitute' so nobody
      # mistakes it for the ADOPTED faster-whisper path.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from biddeed_reels_lib import storage_upload, burn_word_captions_bolt32  # noqa: E402
from bolt32_captions_whisperx import (  # noqa: E402
    group_words, assert_valid_groups, transcribe_words_faster_whisper,
    Bolt32TranscriptionUnavailableError,
)
import mgmt_sql  # noqa: E402 -- same Management-API SQL path every other bolt32/reels script uses


def _sql_str(s: str) -> str:
    return s.replace("'", "''")


def _fetch_row(row_id: str) -> dict:
    r = mgmt_sql.run(
        f"select id, county, case_number, video_bolt32_url from winnerdata.biddeed_reels "
        f"where id = '{_sql_str(row_id)}'"
    )
    rows = r.json()
    if not rows:
        raise ValueError(f"no row {row_id}")
    return rows[0]


def _update_row(row_id: str, captions_url: str, source: str, groups: list[dict], model_size: str) -> None:
    groups_json = _sql_str(json.dumps(groups))
    q = f"""
        update winnerdata.biddeed_reels set
            video_bolt32_captions_url = '{_sql_str(captions_url)}',
            captions_source = '{_sql_str(source)}',
            captions_groups = '{groups_json}'::jsonb,
            captions_model = '{_sql_str(model_size)}',
            captions_generated_at = '{datetime.now(timezone.utc).isoformat()}'
        where id = '{_sql_str(row_id)}';
    """
    r = mgmt_sql.run(q)
    if r.status_code >= 300:
        raise RuntimeError(f"DB update failed ({r.status_code}): {r.text[:500]}")


def _transcribe_session_substitute(audio_path: str) -> tuple[list[dict], str]:
    import whisper  # openai-whisper -- session-local only, see module docstring
    model = whisper.load_model("base")
    result = model.transcribe(audio_path, word_timestamps=True)
    words = []
    for seg in result["segments"]:
        for w in seg.get("words", []):
            words.append({"word": w["word"].strip(), "start": round(w["start"], 2), "end": round(w["end"], 2)})
    return words, "base"


def recaption(row_id: str, allow_session_substitute: bool = False) -> dict:
    row = _fetch_row(row_id)
    if not row.get("video_bolt32_url"):
        raise ValueError(f"row {row_id} has no video_bolt32_url yet (bolt32 not rendered)")

    with tempfile.TemporaryDirectory() as d:
        video_path = os.path.join(d, "in.mp4")
        subprocess.run(["curl", "-sL", "-o", video_path, row["video_bolt32_url"]], check=True)
        audio_path = os.path.join(d, "audio.wav")
        subprocess.run(["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
                         "-ar", "16000", "-ac", "1", audio_path],
                        capture_output=True, check=True)

        source = "faster_whisper"
        model_size = "small"
        try:
            words = transcribe_words_faster_whisper(audio_path, model_size=model_size)
        except Bolt32TranscriptionUnavailableError as e:
            if not allow_session_substitute:
                raise
            print(f"::warning::faster-whisper unavailable ({e}); using openai-whisper session substitute")
            words, model_size = _transcribe_session_substitute(audio_path)
            source = "openai_whisper_session_substitute"

        groups = group_words(words)
        assert_valid_groups(groups)

        out_path = os.path.join(d, "out.mp4")
        duration = burn_word_captions_bolt32(video_path, groups, out_path)

        key = row["video_bolt32_url"].split("/public/biddeed-reels/", 1)[1].replace(
            "reel_bolt32.mp4", "reel_bolt32_captions.mp4")
        captions_url = storage_upload(out_path, key, "video/mp4")

    _update_row(row_id, captions_url, source, groups, model_size)

    return {
        "id": row_id, "captions_url": captions_url, "duration": duration,
        "n_groups": len(groups), "source": source, "model": model_size,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--allow-session-substitute", action="store_true")
    args = ap.parse_args()
    print(json.dumps(recaption(args.id, args.allow_session_substitute), indent=2))
