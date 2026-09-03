#!/usr/bin/env python3
"""License V2 gate for the bolt32 video-tooling stack (issue #19781).

Scans a requirements file for packages/lines matching HARD REJECT projects
(GPL/AGPL/SSPL/BUSL, or non-commercial-weights tools) per
docs/gtm/VIDEO_STACK.md, and exits non-zero if any are present.

Negative test (a) from the issue: a GPL-licensed dependency entering
requirements-bolt32.txt fails the run.
"""
import re
import sys

# Package name (as it would appear in a requirements.txt / import) -> reason.
# Sourced from docs/gtm/VIDEO_STACK.md HARD REJECT rows. Do not re-litigate
# without updating that doc.
BANNED_PACKAGES = {
    "pyvideotrans": "jianchang512/pyvideotrans is GPL-3.0 -- License V2 HARD REJECT",
    "tts": "coqui-ai/TTS (import name 'TTS') ships XTTS weights under CPML "
           "(non-commercial) and is unmaintained since 2024-08 -- HARD REJECT",
    "coqui-tts": "coqui-ai/TTS fork/rename -- XTTS weights CPML non-commercial -- HARD REJECT",
    "f5-tts": "SWivid/F5-TTS code is MIT but pretrained weights are CC-BY-NC "
              "(non-commercial) -- weights HARD REJECT",
}

BANNED_LICENSE_TOKENS = ("GPL", "AGPL", "SSPL", "BUSL")


class Bolt32LicenseError(Exception):
    pass


def _package_name(line: str) -> str | None:
    line = line.split("#", 1)[0].strip()
    if not line:
        return None
    m = re.match(r"^([A-Za-z0-9_.\-]+)", line)
    return m.group(1).lower() if m else None


def scan_requirements(path: str) -> list[str]:
    """Returns a list of violation strings; empty list = clean."""
    violations = []
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            pkg = _package_name(raw)
            if pkg is None:
                continue
            if pkg in BANNED_PACKAGES:
                violations.append(
                    f"{path}:{lineno}: '{pkg}' -- {BANNED_PACKAGES[pkg]}"
                )
            for tok in BANNED_LICENSE_TOKENS:
                if re.search(rf"\b{tok}\b", raw, re.IGNORECASE):
                    violations.append(
                        f"{path}:{lineno}: license token '{tok}' found in line: {raw.strip()}"
                    )
    return violations


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return _selftest()
    if len(argv) < 2:
        print("usage: bolt32_license_gate.py <requirements-file> [--selftest]", file=sys.stderr)
        return 2
    violations = scan_requirements(argv[1])
    if violations:
        print("HARD REJECT -- License V2 violation(s):", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print(f"OK -- {argv[1]} clean against License V2 gate")
    return 0


def _selftest() -> int:
    import tempfile
    import os

    clean = "whisperx>=3.1.1\nfaster-whisper>=1.0.0\nkokoro>=0.9.4\n"
    dirty = clean + "pyvideotrans==2.0\n"

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(clean)
        clean_path = f.name
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(dirty)
        dirty_path = f.name

    try:
        assert scan_requirements(clean_path) == [], "clean file must have zero violations"
        dirty_violations = scan_requirements(dirty_path)
        assert dirty_violations, "dirty file (pyvideotrans) must be flagged"
        print("SELFTEST PASS")
        print(f"  clean file: 0 violations")
        print(f"  dirty file (synthetic pyvideotrans line): {len(dirty_violations)} violation(s)")
        for v in dirty_violations:
            print(f"    - {v}")
        return 0
    finally:
        os.unlink(clean_path)
        os.unlink(dirty_path)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
