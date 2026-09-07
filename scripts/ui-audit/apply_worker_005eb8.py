#!/usr/bin/env python3
"""Convert src/worker.js to the #005EB8 canon, recovering navy vs ink exactly.

Ariel settled the palette on 2026-09-07: background/card #ffffff, tint #E6F0FA,
ink #1a1a1a, navy #0A2540, border #D7E3F1, brand #005EB8, hover #004A92.

Why this is not a plain search/replace
-------------------------------------
On 2026-09-06 the Worker was converted to the cream/terracotta palette, and that
conversion was LOSSY: ink #222222 (x122) and navy #002A54 (x172) both collapsed
into #1F1B16 (x294). Mapping cream forward by value would paint every navy
heading ink-black. So this script aligns the ordered sequence of colour literals
in the working file against the last pre-cream revision (REF_SHA below) with
difflib, and maps each literal from what it USED to be. 1,122 of 1,154 literals
align; the 32 that do not are content added after the conversion and are mapped
by value from the cream palette instead.

Run: python3 scripts/ui-audit/apply_worker_005eb8.py src/worker.js
Idempotent: a file already on the canon is left untouched (it exits 0 and says so).
"""
import difflib
import re
import subprocess
import sys
import urllib.request

REF_SHA = "d34cf95caf23772d1c3ba6996f340c3e2759c9cf"  # last revision before the cream conversion

LIT = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|rgba?\([^)]*\)")
NUM = re.compile(r"-?\d+(?:\.\d+)?")

HEX_FROM_BLUE = {
    "#ffffff": "#ffffff", "#fff": "#fff",
    "#0073cf": "#005EB8", "#002a54": "#0A2540", "#222222": "#1a1a1a",
    "#cccccc": "#D7E3F1", "#005daa": "#004A92", "#e8f4fc": "#E6F0FA",
}
HEX_FROM_CREAM = {
    "#fbfaf7": "#ffffff", "#f5f0e8": "#ffffff", "#fff": "#fff",
    "#f8d4c5": "#E6F0FA", "#1f1b16": "#1a1a1a", "#ddd5c9": "#D7E3F1",
    "#8f4028": "#005EB8", "#c15f3c": "#005EB8",
    "#7a3424": "#004A92", "#a94d30": "#004A92",
}
RGB_FROM_BLUE = {
    (0, 115, 207): (0, 94, 184), (0, 93, 170): (0, 74, 146), (0, 42, 84): (10, 37, 64),
    (34, 34, 34): (26, 26, 26), (204, 204, 204): (215, 227, 241),
    (232, 244, 252): (230, 240, 250), (255, 255, 255): (255, 255, 255),
    (0, 0, 0): (10, 37, 64),
}
RGB_FROM_CREAM = {
    (143, 64, 40): (0, 94, 184), (193, 95, 60): (0, 94, 184),
    (122, 52, 36): (0, 74, 146), (169, 77, 48): (0, 74, 146),
    (31, 27, 22): (26, 26, 26), (221, 213, 201): (215, 227, 241),
    (248, 212, 197): (230, 240, 250), (251, 250, 247): (255, 255, 255),
    (245, 240, 232): (255, 255, 255), (255, 255, 255): (255, 255, 255),
    (0, 0, 0): (10, 37, 64),
}
CANON = {
    "#ffffff", "#e6f0fa", "#1a1a1a", "#0a2540", "#d7e3f1", "#005eb8", "#004a92",
    "#0b1119", "#111b27", "#1b2737", "#ededed", "#9eb2c7", "#24344c", "#1a90ff", "#4da6ff",
}
CANON_RGB = {(int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)) for h in CANON}


def triple(lit):
    nums = NUM.findall(lit.split("/")[0])
    if len(nums) < 3:
        return None
    return tuple(int(round(float(n))) for n in nums[:3])


def retint(lit, new):
    """Rewrite only the first three numbers of an rgb()/rgba() literal."""
    result, pos, k = [], 0, 0
    for m in NUM.finditer(lit):
        if k >= 3:
            break
        result.append(lit[pos:m.start()])
        result.append(str(new[k]))
        pos = m.end()
        k += 1
    result.append(lit[pos:])
    return "".join(result)


def convert(lit, hexmap, rgbmap):
    low = lit.lower()
    if low.startswith("#"):
        return hexmap.get(low, lit)
    tr = triple(lit)
    if tr is None or tr not in rgbmap:
        return lit
    return retint(lit, rgbmap[tr])


def audit(text):
    bad = []
    for m in LIT.finditer(text):
        lit = m.group(0).lower()
        if lit.startswith("#"):
            h = lit if len(lit) == 7 else "#" + "".join(c * 2 for c in lit[1:])
            if h not in CANON:
                bad.append(m.group(0))
        else:
            tr = triple(lit)
            if tr is not None and tr not in CANON_RGB:
                bad.append(m.group(0))
    return bad


def read_reference():
    """The pre-cream revision of src/worker.js.

    actions/checkout is shallow by default, so `git show <sha>:...` usually
    fails in CI; the raw URL is tried first and git is the offline fallback.
    """
    url = ("https://raw.githubusercontent.com/breverdbidder/cli-anything-biddeed/%s/src/worker.js"
           % REF_SHA)
    try:
        with urllib.request.urlopen(url, timeout=60) as fh:
            return fh.read().decode("utf-8")
    except Exception as exc:
        print("apply_worker_005eb8: raw fetch failed (%s), falling back to git" % exc)
        return subprocess.run(["git", "show", "%s:src/worker.js" % REF_SHA],
                              capture_output=True, text=True, check=True).stdout


def main(path):
    cur = open(path, encoding="utf-8").read()
    if not audit(cur):
        print("apply_worker_005eb8: already on the canon palette, nothing to do.")
        return 0

    ref = read_reference()

    cm = list(LIT.finditer(cur))
    rm = list(LIT.finditer(ref))
    cs = [m.group(0).lower() for m in cm]
    rs = [m.group(0).lower() for m in rm]

    aligned = {}
    sm = difflib.SequenceMatcher(a=rs, b=cs, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal" or (tag == "replace" and (i2 - i1) == (j2 - j1)):
            for k in range(j2 - j1):
                aligned[j1 + k] = rm[i1 + k].group(0)

    out, pos, from_ref, from_cream = [], 0, 0, 0
    for idx, m in enumerate(cm):
        out.append(cur[pos:m.start()])
        if idx in aligned:
            new = convert(aligned[idx], HEX_FROM_BLUE, RGB_FROM_BLUE)
            from_ref += 1
        else:
            new = convert(m.group(0), HEX_FROM_CREAM, RGB_FROM_CREAM)
            from_cream += 1
        out.append(new)
        pos = m.end()
    out.append(cur[pos:])
    new_text = "".join(out)

    bad = audit(new_text)
    if bad:
        print("apply_worker_005eb8: REFUSING to write, %d off-canon literal(s) remain: %s"
              % (len(bad), sorted(set(bad))[:20]), file=sys.stderr)
        return 1

    open(path, "w", encoding="utf-8").write(new_text)
    print("apply_worker_005eb8: wrote %s" % path)
    print("  literals mapped from the pre-cream revision: %d" % from_ref)
    print("  literals mapped by value (added after the conversion): %d" % from_cream)
    print("  off-canon literals remaining: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "src/worker.js"))
