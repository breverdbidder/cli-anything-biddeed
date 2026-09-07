#!/usr/bin/env python3
"""Palette gate for src/worker.js (the biddeed.ai Cloudflare Worker).

Why this exists
---------------
biddeed-web has scripts/palette-gate.mjs and runs it on every PR *and* again
inside the production deploy, so an off-canon colour cannot reach the Next.js
surfaces. The Worker had no equivalent: on 2026-09-06 the whole file was
converted to a retired palette and deployed with nothing failing, which left
biddeed.ai two-toned -- blue on /, /radar, /support (gated repo) and
cream/terracotta on /blog, /county/*, /deal/*, /reels (ungated repo). The
asymmetry between the two repos WAS the bug. This closes it.

What it checks
--------------
Every colour literal in src/worker.js -- #RRGGBB, #RGB, rgb(), rgba(), and the
Tailwind `rgb(R G B / <alpha>)` form -- must be one of the canon values below.
Alpha is free: rgba() of a canon colour at any opacity passes.

The canon is Ariel's palette (settled 2026-09-07: enterprise blue #005EB8); the same 15
values are in biddeed-web's lib/design-tokens.ts and scripts/palette-gate.mjs.
Changing the palette means changing BOTH repos' lists in the same reviewed
change -- never one of them alone, which is how the two-toned site happened.

Usage:  python3 scripts/ui-audit/palette_gate_worker.py [path-to-worker.js]
Exit 0 = clean, exit 1 = findings (prints file:line and the literal).
"""
import re
import sys

CANON_LIGHT = ["#ffffff", "#e6f0fa", "#1a1a1a", "#0a2540", "#d7e3f1", "#005eb8", "#004a92"]
CANON_DARK = ["#0b1119", "#111b27", "#1b2737", "#ededed", "#9eb2c7", "#24344c", "#1a90ff", "#4da6ff"]
CANON = set(CANON_LIGHT) | set(CANON_DARK)
CANON_RGB = set()
for _h in CANON:
    CANON_RGB.add((int(_h[1:3], 16), int(_h[3:5], 16), int(_h[5:7], 16)))

HEX6 = re.compile(r"#[0-9a-fA-F]{6}\b")
HEX3 = re.compile(r"#[0-9a-fA-F]{3}\b")
RGBFN = re.compile(r"rgba?\(([^)]*)\)")
NUM = re.compile(r"-?\d+(?:\.\d+)?")


def expand3(h):
    return "#" + "".join(c * 2 for c in h[1:])


def rgb_triple(args):
    """First three numbers of an rgb()/rgba() argument list, or None."""
    head = args.split("/")[0]
    nums = NUM.findall(head)
    if len(nums) < 3:
        return None
    try:
        return tuple(int(round(float(n))) for n in nums[:3])
    except ValueError:
        return None


def main(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()

    findings = []
    for i, line in enumerate(lines, 1):
        for m in HEX6.finditer(line):
            if m.group(0).lower() not in CANON:
                findings.append((i, m.group(0)))
        for m in HEX3.finditer(line):
            if expand3(m.group(0).lower()) not in CANON:
                findings.append((i, m.group(0)))
        for m in RGBFN.finditer(line):
            triple = rgb_triple(m.group(1))
            if triple is not None and triple not in CANON_RGB:
                findings.append((i, m.group(0)))

    if not findings:
        print("palette-gate(worker): clean -- every colour literal in %s is canon." % path)
        return 0

    counts = {}
    for _, lit in findings:
        counts[lit.lower()] = counts.get(lit.lower(), 0) + 1

    print("palette-gate(worker): %d off-canon colour literal(s) in %s" % (len(findings), path), file=sys.stderr)
    print("", file=sys.stderr)
    print("By value (most frequent first):", file=sys.stderr)
    for lit, n in sorted(counts.items(), key=lambda kv: -kv[1])[:40]:
        print("  %-40s x%d" % (lit, n), file=sys.stderr)
    print("", file=sys.stderr)
    print("First 25 locations:", file=sys.stderr)
    for ln, lit in findings[:25]:
        print("  %s:%d  %s" % (path, ln, lit), file=sys.stderr)
    print("", file=sys.stderr)
    print("Canon light: %s" % " ".join(CANON_LIGHT), file=sys.stderr)
    print("Canon dark:  %s" % " ".join(CANON_DARK), file=sys.stderr)
    print("", file=sys.stderr)
    print("A different palette needs Ariel's explicit decision, and then this list", file=sys.stderr)
    print("and biddeed-web's scripts/palette-gate.mjs change in the SAME change.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "src/worker.js"))
