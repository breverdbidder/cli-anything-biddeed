#!/usr/bin/env python3
"""bolt32 post-render QA critique pass (issue #19787).

Ports the self-correcting critique-loop DESIGN from
breverdbidder/agentic-video-maker's scripts/gemini-critique.cjs (score ->
gate -> plan_patch feedback) but implements it as a deterministic,
artifact-based scorer rather than an LLM-vision call: this issue doesn't
authorize new Gemini API spend, and every dimension below is independently
computable from data this pipeline already has (real ffprobe durations,
real caption groups, real title validation, real extracted frames) --
cheaper, zero-latency, and reproducible. #19782 (CMO FACTORY CP3c) owns a
future Director/QA agent role; if that lands with an LLM-vision critique
pass, this module's job is to be extended/replaced, not duplicated
(coordinate there, per the issue's own instruction) -- as of this session
#19782 is OPEN with no committed code (verified via `git log --all | grep
19782` returning nothing), so this module is the first real implementation.

4 dimensions, matching docs/gtm/VIDEO_STACK.md #3's original description:
  hook_clarity        -- does title_chosen pass validate_bolt32_title()?
  caption_readability -- do the whisperX/faster-whisper caption groups all
                         satisfy the 3-5 word window (assert_valid_groups)?
  beat_timing_drift   -- |actual rendered duration - 32.0s| in ms
  loop_seam_continuity -- pixel-diff between the first frame and the last
                         frame (both SHOULD be the same 'aerial_wide' still
                         per assemble_video_bolt32's loop mechanic)

Negative test (d) (docs/gtm/VIDEO_STACK.md #3): a score reported without an
`observed` evidence field is rejected -- validate_score() enforces this.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from biddeed_reels_lib import validate_bolt32_title  # noqa: E402
from bolt32_captions_whisperx import assert_valid_groups, Bolt32CaptionError, MIN_GROUP_WORDS, MAX_GROUP_WORDS  # noqa: E402

QA_PASS_THRESHOLD = 7.0  # out of 10, per-dimension minimum to count as qa_pass


class Bolt32QAEvidenceError(Exception):
    pass


def validate_score(dim: dict) -> None:
    """Negative test (d): every dimension must carry a non-null `observed`
    field alongside its numeric score."""
    if dim.get("observed") in (None, ""):
        raise Bolt32QAEvidenceError(
            f"dimension {dim.get('dimension')!r} reports score={dim.get('score')} "
            f"with no `observed` evidence -- rejected"
        )


def score_hook_clarity(title_chosen: str, banned_names: list[str] | None = None) -> dict:
    ok, reasons = validate_bolt32_title(title_chosen, banned_names)
    return {
        "dimension": "hook_clarity",
        "score": 10.0 if ok else 3.0,
        "observed": {"title": title_chosen, "validation_passed": ok, "reasons": reasons},
    }


def score_caption_readability(caption_groups: list[dict]) -> dict:
    try:
        assert_valid_groups(caption_groups)
        passed = True
        reason = None
    except Bolt32CaptionError as e:
        passed = False
        reason = str(e)
    if caption_groups:
        avg_words = sum(g["words"] for g in caption_groups) / len(caption_groups)
        closeness = 1 - abs(avg_words - 4) / 4  # 4 = midpoint of 3-5
    else:
        avg_words, closeness = 0, 0
    score = (10.0 if passed else 2.0) * max(closeness, 0.3 if passed else 0.2)
    return {
        "dimension": "caption_readability",
        "score": round(min(score, 10.0), 2),
        "observed": {
            "n_groups": len(caption_groups), "avg_words_per_group": round(avg_words, 2),
            "window": [MIN_GROUP_WORDS, MAX_GROUP_WORDS], "all_groups_valid": passed, "reason": reason,
        },
    }


def score_beat_timing_drift(actual_duration_sec: float, target_sec: float = 32.0) -> dict:
    drift_ms = abs(actual_duration_sec - target_sec) * 1000
    # 0ms drift -> 10.0, 100ms -> 7.0, 300ms+ -> 0.0 (linear)
    score = max(0.0, 10.0 - (drift_ms / 100.0) * 3.0)
    return {
        "dimension": "beat_timing_drift",
        "score": round(min(score, 10.0), 2),
        "observed": {"actual_sec": actual_duration_sec, "target_sec": target_sec, "drift_ms": round(drift_ms, 1)},
    }


def score_loop_seam_continuity(video_path: str) -> dict:
    """Extracts the first frame and the last frame, computes normalized
    pixel-difference (mean absolute error, 0-255 scale). assemble_video_bolt32
    deliberately reuses the SAME still ('aerial_wide') for both the hook
    segment and the 1s 'end' segment so the loop is visually seamless --
    this check verifies that actually happened in the rendered output,
    not just in the intended design."""
    import numpy as np
    from PIL import Image

    with tempfile.TemporaryDirectory() as d:
        first_path = f"{d}/first.png"
        last_path = f"{d}/last.png"
        subprocess.run(["ffmpeg", "-y", "-i", video_path, "-frames:v", "1", "-update", "1", first_path],
                       capture_output=True, check=True)
        dur = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        last_ts = max(float(dur) - 0.1, 0)
        subprocess.run(["ffmpeg", "-y", "-ss", str(last_ts), "-i", video_path, "-frames:v", "1",
                         "-update", "1", last_path], capture_output=True, check=True)

        img1 = np.asarray(Image.open(first_path).convert("RGB").resize((320, 569)), dtype=np.float32)
        img2 = np.asarray(Image.open(last_path).convert("RGB").resize((320, 569)), dtype=np.float32)
        mae = float(np.abs(img1 - img2).mean())

    # mae near 0 (identical still, different text overlay is expected/OK at
    # this resolution) -> high score; large mae (different scene entirely) -> low.
    score = max(0.0, 10.0 - (mae / 255.0) * 10.0 * 2.5)
    return {
        "dimension": "loop_seam_continuity",
        "score": round(min(score, 10.0), 2),
        "observed": {"mean_abs_pixel_diff_0_255": round(mae, 2), "first_frame": "first.png", "last_frame": "last.png"},
    }


def run_qa(video_path: str, title_chosen: str, caption_groups: list[dict],
           actual_duration_sec: float, banned_names: list[str] | None = None) -> dict:
    dims = [
        score_hook_clarity(title_chosen, banned_names),
        score_caption_readability(caption_groups),
        score_beat_timing_drift(actual_duration_sec),
        score_loop_seam_continuity(video_path),
    ]
    for d in dims:
        validate_score(d)
    overall = round(sum(d["score"] for d in dims) / len(dims), 2)
    qa_pass = all(d["score"] >= QA_PASS_THRESHOLD for d in dims)
    return {"overall_score": overall, "qa_pass": qa_pass, "dimensions": dims}


def _selftest() -> int:
    # Negative test (d): a score dict without `observed` must be rejected.
    try:
        validate_score({"dimension": "x", "score": 9.0})
        print("test_score_without_observed_rejected: FAIL (no exception raised)")
        return 1
    except Bolt32QAEvidenceError as e:
        print(f"test_score_without_observed_rejected: PASS ({e})")

    # hook_clarity: valid title scores high, invalid scores low.
    d = score_hook_clarity("This Broward Home Just Sold For $50,000...😳🏆")
    assert d["score"] == 10.0, d
    d = score_hook_clarity("No stakes here")
    assert d["score"] == 3.0, d
    print("test_hook_clarity_scoring: PASS")

    # caption_readability: an 8-word group must score low / raise internally handled.
    bad_groups = [{"text": "a b c d e f g h", "start": 0.0, "end": 2.0, "words": 8}]
    d = score_caption_readability(bad_groups)
    assert d["observed"]["all_groups_valid"] is False and d["score"] < 5, d
    good_groups = [{"text": "This home just sold", "start": 0.0, "end": 1.0, "words": 4}]
    d = score_caption_readability(good_groups)
    assert d["observed"]["all_groups_valid"] is True and d["score"] >= 7, d
    print("test_caption_readability_scoring: PASS")

    # beat_timing_drift: exact 32.0s -> perfect score; 34.0s -> heavily penalized.
    d = score_beat_timing_drift(32.0)
    assert d["score"] == 10.0, d
    d = score_beat_timing_drift(34.0)
    assert d["score"] == 0.0, d
    print("test_beat_timing_drift_scoring: PASS")

    print("SELFTEST PASS")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())
