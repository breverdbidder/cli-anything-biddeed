#!/usr/bin/env python3
"""Second Worker pass, from the first post-sweep live audit (2026-09-06 19:05 UTC):
/buy-report "Included intelligence overlays" brand-on-tint 4.31:1; county-page
"Build with AI" button kept ink text on what is now a brand-blue gradient
(3.3:1). Exact-string rewrites; idempotent; asserts nothing regressed."""
import sys, pathlib
SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "src/worker.js"); s = SRC.read_text()
if ".s5-overlays strong{color:#0073CF}" not in s and "to-amber-400 text-slate-900" not in s:
    print("already applied - nothing to do"); sys.exit(0)
def rep(old, new, count=1):
    global s
    n = s.count(old); assert n == count, f"expected {count} of {old[:70]!r}, found {n}"
    s = s.replace(old, new)
rep(".s5-overlays strong{color:#0073CF}", ".s5-overlays strong{color:#005DAA}")
rep("from-amber-500 to-amber-400 text-slate-900 font-bold rounded-full shadow-2xl shadow-amber-500/40",
    "from-amber-500 to-amber-400 text-white font-bold rounded-full shadow-2xl shadow-amber-500/40")
SRC.write_text(s); print("applied", len(s))
