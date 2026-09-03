#!/usr/bin/env python3
"""whisperX word-timestamp -> Bolt caption-group formatter (issue #19781, wired
into the live pipeline in #19787).

Bolt's cadence is centered, high-contrast captions in 3-5 word groups, one
visual change every 2-4s. whisperX (docs/gtm/VIDEO_STACK.md, ADOPTED) gives
word-level timestamps; this module turns that word stream into caption
groups a bolt32 render step can burn in via ffmpeg drawtext
(biddeed_reels_lib.py::burn_word_captions_bolt32).

transcribe_words_faster_whisper() is the real production entry point
(faster-whisper, the ADOPTED CPU backend, docs/gtm/VIDEO_STACK.md). It is a
thin wrapper -- import is lazy so unit-testing group_words()/
assert_valid_groups() never requires the (heavy) faster-whisper install.
"""
from __future__ import annotations

MIN_GROUP_WORDS = 3
MAX_GROUP_WORDS = 5


class Bolt32CaptionError(Exception):
    pass


def group_words(words: list[dict], min_words: int = MIN_GROUP_WORDS,
                 max_words: int = MAX_GROUP_WORDS) -> list[dict]:
    """Groups whisperX word-timestamp dicts into 3-5 word caption groups.

    Input: [{"word": "The", "start": 0.0, "end": 0.2}, ...]
    Output: [{"text": "The Bank Wanted", "start": 0.0, "end": 0.9, "words": 3}, ...]

    Greedy pack to max_words, but never leaves a trailing group smaller than
    min_words unless it's the very last group in the stream (a sentence can
    legitimately end on 1-2 words).
    """
    groups = []
    i = 0
    n = len(words)
    while i < n:
        remaining = n - i
        if remaining <= max_words:
            take = remaining
        elif remaining < max_words + min_words:
            take = remaining // 2 if remaining // 2 >= min_words else remaining
        else:
            take = max_words
        chunk = words[i:i + take]
        groups.append({
            "text": " ".join(w["word"].strip() for w in chunk),
            "start": chunk[0]["start"],
            "end": chunk[-1]["end"],
            "words": len(chunk),
        })
        i += take
    return groups


def assert_valid_groups(groups: list[dict], min_words: int = MIN_GROUP_WORDS,
                         max_words: int = MAX_GROUP_WORDS) -> None:
    """Negative test (c): a caption group of 8 words fails this assertion."""
    for idx, g in enumerate(groups):
        wc = g["words"]
        is_last = idx == len(groups) - 1
        if wc > max_words:
            raise Bolt32CaptionError(
                f"group {idx} has {wc} words (max {max_words}): {g['text']!r}"
            )
        if wc < min_words and not is_last:
            raise Bolt32CaptionError(
                f"group {idx} has {wc} words (min {min_words}, not last group): {g['text']!r}"
            )


class Bolt32TranscriptionUnavailableError(Exception):
    """Raised when the ADOPTED faster-whisper backend cannot produce a
    transcript (e.g. its Hugging Face Hub model weights are unreachable).
    Callers decide whether to retry, skip, or use a documented session-local
    substitute -- this module never silently swaps backends itself."""


def transcribe_words_faster_whisper(audio_path: str, model_size: str = "small",
                                     device: str = "cpu", compute_type: str = "int8") -> list[dict]:
    """Real production entry point. faster-whisper (MIT, SYSTRAN/faster-whisper)
    is the ADOPTED CPU backend for whisperX-shaped word timestamps
    (docs/gtm/VIDEO_STACK.md #2). Returns [{"word","start","end"}, ...] in
    the same shape group_words() expects.

    Raises Bolt32TranscriptionUnavailableError if the model weights can't be
    fetched (e.g. Hugging Face Hub rate-limiting) -- this is a real,
    observable failure mode (confirmed live 2026-09-03: HF Hub CloudFront
    429 on both the metadata API and the CDN resolve endpoint from this
    session's network egress), not something to paper over.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise Bolt32TranscriptionUnavailableError(f"faster-whisper not installed: {e}") from e

    try:
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        segments, _info = model.transcribe(audio_path, word_timestamps=True)
        words = []
        for seg in segments:
            for w in seg.words:
                words.append({"word": w.word.strip(), "start": round(w.start, 2), "end": round(w.end, 2)})
        return words
    except Exception as e:
        raise Bolt32TranscriptionUnavailableError(f"faster-whisper transcription failed: {e}") from e


def _synthetic_words(sentence: str, start: float = 0.0, per_word_sec: float = 0.3) -> list[dict]:
    out = []
    t = start
    for w in sentence.split():
        out.append({"word": w, "start": round(t, 2), "end": round(t + per_word_sec, 2)})
        t += per_word_sec
    return out


def _selftest() -> int:
    # Normal case: valid grouping.
    words = _synthetic_words("The Bank Wanted One Hundred Sixty Four Thousand Dollars For This House")
    groups = group_words(words)
    assert_valid_groups(groups)
    print(f"test_normal_grouping_valid: PASS ({len(groups)} groups)")
    for g in groups:
        print(f"    {g['words']}w [{g['start']:.1f}-{g['end']:.1f}] {g['text']!r}")

    # Negative test (c): an 8-word group must be rejected.
    bad_groups = [{"text": "a b c d e f g h", "start": 0.0, "end": 2.0, "words": 8}]
    try:
        assert_valid_groups(bad_groups)
        print("test_eight_word_group_rejected: FAIL (no exception raised)")
        return 1
    except Bolt32CaptionError as e:
        print(f"test_eight_word_group_rejected: PASS ({e})")

    print("SELFTEST PASS")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
