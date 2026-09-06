#!/usr/bin/env python3
"""Convert legacy blue Worker presentation literals to the house-brand palette.

This changes presentation literals only; routing, data, authentication, and API
contracts are untouched. Review the diff and run the Worker build/audit after use.
"""
from pathlib import Path
import re
import sys

source = Path(sys.argv[1] if len(sys.argv) > 1 else 'src/worker.js')
text = source.read_text()
original = text

hex_map = {
    '#FFFFFF': '#FBFAF7', '#ffffff': '#FBFAF7', '#FFF': '#FBFAF7', '#fff': '#FBFAF7',
    '#E8F4FC': '#F8D4C5', '#e8f4fc': '#F8D4C5',
    '#222222': '#1F1B16', '#222': '#1F1B16',
    '#002A54': '#1F1B16', '#002a54': '#1F1B16',
    '#CCCCCC': '#DDD5C9', '#cccccc': '#DDD5C9',
    '#0073CF': '#C15F3C', '#0073cf': '#C15F3C',
    '#005DAA': '#A94D30', '#005daa': '#A94D30',
}
rgb_map = {
    '255,255,255': '251,250,247', '232,244,252': '248,212,197',
    '34,34,34': '31,27,22', '0,42,84': '31,27,22',
    '204,204,204': '221,213,201', '0,115,207': '193,95,60',
    '0,93,170': '169,77,48',
}
for old, new in hex_map.items():
    text = re.sub(re.escape(old), new, text, flags=re.IGNORECASE)
for old, new in rgb_map.items():
    text = text.replace(old, new)

if text == original:
    print('no legacy palette literals found; nothing changed')
    raise SystemExit(0)
source.write_text(text)
remaining = []
for old in ['#ffffff', '#fff', '#e8f4fc', '#222222', '#002a54', '#cccccc', '#0073cf', '#005daa', '255,255,255', '232,244,252', '34,34,34', '0,42,84', '204,204,204', '0,115,207', '0,93,170']:
    if re.search(re.escape(old), text, flags=re.IGNORECASE):
        remaining.append(old)
if remaining:
    raise SystemExit(f'remaining legacy literals: {remaining}')
print(f'updated {source}; house-brand palette applied')
