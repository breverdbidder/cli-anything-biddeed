#!/usr/bin/env python3
"""Guards that auto-editor (WyattBlue/auto-editor, Unlicense) never enters the
bolt32 pipeline (issue #19787). Bolt32 is beat-locked to a hard 32.0s
timeline (beat_map/loop_frame_ms, DoD asserted by assert_bolt32_duration) --
auto-editor's silence/dead-air auto-trim would shift beat boundaries and
break the loop mechanic (assemble_video_bolt32's hook/end frame reuse).
docs/gtm/VIDEO_STACK.md #2 ADOPTS auto-editor for the long-form YouTube lane
ONLY (a separate pipeline in breverdbidder/everest-cinematic, not this repo).

This is a static source-grep gate, not a license gate (bolt32_license_gate.py
already covers license class) -- auto-editor is legitimately ADOPTED, the
violation this checks for is LANE, not license.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BOLT32_FILES = [
    "scripts/biddeed_reels_lib.py",
    "scripts/biddeed_reels_pipeline_bolt32.py",
    "scripts/bolt32_captions_whisperx.py",
    "scripts/bolt32_tts_fallback.py",
    "scripts/bolt32_qa_critique.py",
    "scripts/bolt32_recaption.py",
]
AUTOEDITOR_RE = re.compile(r"\bauto[-_]editor\b|\bimport\s+auto_editor\b", re.I)


class Bolt32AutoEditorLaneError(Exception):
    pass


def check(repo_root: str = ".") -> list[str]:
    hits = []
    for rel in BOLT32_FILES:
        path = Path(repo_root) / rel
        if not path.exists():
            continue
        text = path.read_text(errors="ignore")
        if AUTOEDITOR_RE.search(text):
            hits.append(rel)
    return hits


def _selftest() -> int:
    hits = check(".")
    if hits:
        print(f"::error::auto-editor referenced in bolt32-lane files: {hits} -- bolt32 is beat-locked, "
              f"auto-editor is long-form-lane-only per docs/gtm/VIDEO_STACK.md")
        return 1
    print(f"test_no_autoeditor_in_bolt32_lane: PASS (checked {len(BOLT32_FILES)} files)")

    # Negative-test the detector itself: it must actually catch a hit.
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(f"{d}/scripts")
        with open(f"{d}/scripts/biddeed_reels_lib.py", "w") as f:
            f.write("import auto_editor\n")
        hits = check(d)
        assert hits == ["scripts/biddeed_reels_lib.py"], hits
    print("test_detector_catches_synthetic_autoeditor_import: PASS")

    print("SELFTEST PASS")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())
