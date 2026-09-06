#!/usr/bin/env python3
"""Map canonical Worker presentation tokens to the WinnerDataAI house brand.

This intentionally changes presentation literals only. It does not change route
ownership, data adapters, auth, payment, or API contracts.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

path = Path(sys.argv[1] if len(sys.argv) > 1 else "src/worker.js")
source = path.read_text()
original = source

# Legacy blue canon -> WinnerDataAI light-mode canon.
hex_map = {
    "#ffffff": "#FBFAF7",  # bright cream surface / light text
    "#fff": "#FBFAF7",
    "#e8f4fc": "#F8D4C5",  # soft terracotta tint
    "#222222": "#1F1B16",  # black-brown ink
    "#002a54": "#1F1B16",  # legacy navy -> ink
    "#cccccc": "#DDD5C9",  # warm border
    "#0073cf": "#C15F3C",  # terracotta action
    "#005daa": "#A94D30",  # terracotta hover
    "#000": "#1F1B16",
}
for old, new in hex_map.items():
    source = re.sub(re.escape(old) + r"(?![0-9a-fA-F])", new, source, flags=re.IGNORECASE)

# Equivalent CSS rgb()/rgba() spellings, including Tailwind's space syntax.
rgb_map = {
    "255,255,255": "251,250,247",
    "232,244,252": "248,212,197",
    "34,34,34": "31,27,22",
    "0,42,84": "31,27,22",
    "204,204,204": "221,213,201",
    "0,115,207": "193,95,60",
    "0,93,170": "169,77,48",
}
for old, new in rgb_map.items():
    source = source.replace(old, new)
    source = source.replace(old.replace(",", " "), new.replace(",", " "))

if source == original:
    print("house-brand worker: already applied")
    raise SystemExit(0)

path.write_text(source)
print(f"house-brand worker: updated {path}")
