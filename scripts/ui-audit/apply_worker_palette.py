#!/usr/bin/env python3
"""Map every remaining off-palette colour literal in src/worker.js onto Ariel's
2026-09-04 seven-colour palette (white #ffffff, tint #E8F4FC, ink #222222,
navy #002A54, border #CCCCCC, brand #0073CF, hover #005DAA). Exact-rule
rewrites first (where a value swap alone would break contrast), then generic
value substitutions, then a hard assertion that nothing off-palette is left."""
import re, sys, pathlib
from collections import Counter

SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "src/worker.js"); s = SRC.read_text()
orig = s
if "#F26A36" not in s and "--soft-terracotta:#EFE2D6" not in s:
    print("already applied - nothing to do"); sys.exit(0)

def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, f"expected {count} of {old[:70]!r}, found {n}"
    s = s.replace(old, new)

# ---- exact-rule rewrites -------------------------------------------------
rep('background:#DC2626;color:#fff;font-weight:800', 'background:#002A54;color:#ffffff;font-weight:800')
rep('--navy:#1E3A5F;', '--navy:#002A54;', 2)
rep('.bd-shell-cta{background:#F26A36!important;', '.bd-shell-cta{background:#0073CF!important;')

# the share/scorecard page was a dark page carrying navy text (unreadable)
rep("body{background:#0a0f1a;color:#002A54;", "body{background:#ffffff;color:#222222;")
rep(".hero{background:linear-gradient(135deg,#0a0f1a 0%,#0f1829 60%,#0a0f1a 100%);border-bottom:1px solid rgba(251,146,60,.15);",
    ".hero{background:#E8F4FC;border-bottom:1px solid #CCCCCC;")
rep(".badge{display:inline-block;background:rgba(251,146,60,.12);border:1px solid rgba(251,146,60,.35);color:#0073CF;",
    ".badge{display:inline-block;background:#ffffff;border:1px solid #0073CF;color:#0073CF;")
rep("background:linear-gradient(135deg,#fff 40%,#0073CF);-webkit-background-clip:text",
    "background:linear-gradient(135deg,#002A54 40%,#0073CF);-webkit-background-clip:text")
rep(".scorecard{background:#0f1829;border:1px solid rgba(251,146,60,.3);", ".scorecard{background:#ffffff;border:1px solid #CCCCCC;")
rep(".sc-header{background:linear-gradient(90deg,rgba(251,146,60,.15),rgba(251,146,60,.05));padding:20px 28px;border-bottom:1px solid rgba(251,146,60,.2);",
    ".sc-header{background:#E8F4FC;padding:20px 28px;border-bottom:1px solid #CCCCCC;")
rep(".sc-header .badge-num{background:#0073CF;color:#000;", ".sc-header .badge-num{background:#0073CF;color:#ffffff;")
rep(".property-bar{background:rgba(255,255,255,.03);border-bottom:1px solid rgba(255,255,255,.06);",
    ".property-bar{background:#E8F4FC;border-bottom:1px solid #CCCCCC;")
rep(".sc-row{display:flex;align-items:flex-start;gap:16px;padding:16px 0;border-bottom:1px solid rgba(255,255,255,.05)}",
    ".sc-row{display:flex;align-items:flex-start;gap:16px;padding:16px 0;border-bottom:1px solid #CCCCCC}")
rep(".equity-bar{background:rgba(52,211,153,.08);border:1px solid rgba(52,211,153,.25);", ".equity-bar{background:#E8F4FC;border:1px solid #0073CF;")
rep(".cta-section h2{font-size:28px;font-weight:800;margin-bottom:12px;color:#fff}", ".cta-section h2{font-size:28px;font-weight:800;margin-bottom:12px;color:#002A54}")
rep(".cta-btn{display:inline-block;background:linear-gradient(135deg,#0073CF,#0073CF);color:#000;", ".cta-btn{display:inline-block;background:#0073CF;color:#ffffff;")
rep("box-shadow:0 8px 32px rgba(251,146,60,.4)", "box-shadow:0 8px 32px rgba(0,115,207,.35)")
# brand blue on the tint is 4.31:1 (fails G-CONTRAST); text on tint uses the hover blue (5.97:1)
rep(".sc-title{font-weight:700;font-size:16px;color:#0073CF}", ".sc-title{font-weight:700;font-size:16px;color:#005DAA}")
rep(".price-cta.ghost:hover{border-color:var(--orange);color:#fff}", ".price-cta.ghost:hover{border-color:var(--orange);color:var(--orange)}")
# /buy-report section numbers: brand on the .s5-overview tint measured 4.18:1 live (2026-09-06 18:40 UTC)
rep(".s5-grid b{color:#0073CF;", ".s5-grid b{color:#005DAA;")

rep("html[data-theme=light] .disclaimer{color:#8f8479}", "html[data-theme=light] .disclaimer{color:#002A54}")
rep(".bbl.user{background:#1e3a5f;color:var(--text);border:1px solid #2d5a8e}", ".bbl.user{background:#E8F4FC;color:var(--text);border:1px solid #CCCCCC}")
rep("border-color:#8f4028;color:#ffffff}", "border-color:#005DAA;color:#ffffff}")
rep(".pc-badge.td{background:rgba(20,184,166,.12);color:#2dd4bf;border:1px solid rgba(20,184,166,.3)}",
    ".pc-badge.td{background:#E8F4FC;color:#002A54;border:1px solid #CCCCCC}")
rep("border:1px solid rgba(148,163,184,.3)}", "border:1px solid #CCCCCC}")
rep("border-color:#B5A9A0}", "border-color:#CCCCCC}")
rep("--terracotta-hover:#BC5B3F;", "--terracotta-hover:#005DAA;")
rep("--soft-terracotta:#EFE2D6;", "--soft-terracotta:#E8F4FC;")

# grade badges (county pages): five palette steps, every one >= 4.5:1
rep(".grade-A { background:linear-gradient(135deg,#0073CF,#059669); color:#fff; }", ".grade-A { background:#0073CF; color:#ffffff; }")
rep(".grade-B { background:linear-gradient(135deg,#0073CF,#16a34a); color:#fff; }", ".grade-B { background:#005DAA; color:#ffffff; }")
rep(".grade-C { background:linear-gradient(135deg,#005DAA,#ca8a04); color:#1f2937; }", ".grade-C { background:#002A54; color:#ffffff; }")
rep(".grade-D { background:linear-gradient(135deg,#0073CF,#ea580c); color:#fff; }", ".grade-D { background:#E8F4FC; color:#002A54; }")
rep("linear-gradient(135deg,#38bdf8,#0073CF)", "linear-gradient(135deg,#005DAA,#0073CF)", 2)

# glass overlays
rep(".glass { background:rgba(230,240,250,0.55);", ".glass { background:rgba(232,244,252,.55);")
rep(".glass-diamond { background:linear-gradient(135deg,rgba(56,189,248,0.12),rgba(168,85,247,0.12)); backdrop-filter:blur(10px); border:1px solid rgba(168,85,247,0.35); }",
    ".glass-diamond { background:rgba(0,115,207,.10); backdrop-filter:blur(10px); border:1px solid rgba(0,115,207,.35); }")
rep(".glass-sold { background:rgba(59,130,246,0.06); backdrop-filter:blur(10px); border:1px solid rgba(59,130,246,0.25); }",
    ".glass-sold { background:rgba(0,93,170,.06); backdrop-filter:blur(10px); border:1px solid rgba(0,93,170,.25); }")
rep(".glass-canceled { background:rgba(100,116,139,0.06); backdrop-filter:blur(10px); border:1px solid rgba(100,116,139,0.25); opacity:0.7; }",
    ".glass-canceled { background:rgba(204,204,204,.25); backdrop-filter:blur(10px); border:1px solid rgba(204,204,204,.6); opacity:0.7; }")

# signal + status chips: solid palette steps instead of pastel-on-tint (~1.5:1)
rep(".sig-out { background:rgba(0,42,84,.18); color:#fca5a5; border:1px solid rgba(0,42,84,.3); }", ".sig-out { background:#002A54; color:#ffffff; border:1px solid #002A54; }")
rep(".sig-est { background:rgba(168,85,247,.20); color:#d8b4fe; border:1px solid rgba(168,85,247,.35); }", ".sig-est { background:#0073CF; color:#ffffff; border:1px solid #0073CF; }")
rep(".sig-ent { background:rgba(59,130,246,.18); color:#93c5fd; border:1px solid rgba(59,130,246,.3); }", ".sig-ent { background:#005DAA; color:#ffffff; border:1px solid #005DAA; }")
rep(".sig-len { background:rgba(20,184,166,.18); color:#5eead4; border:1px solid rgba(20,184,166,.3); }", ".sig-len { background:#E8F4FC; color:#002A54; border:1px solid #0073CF; }")
rep(".sig-mul { background:rgba(244,114,182,.18); color:#f9a8d4; border:1px solid rgba(244,114,182,.3); }", ".sig-mul { background:#ffffff; color:#002A54; border:1px solid #002A54; }")
rep(".status-LISTED { background:rgba(16,185,129,0.18); color:#6ee7b7; border:1px solid rgba(16,185,129,0.35); }", ".status-LISTED { background:#0073CF; color:#ffffff; border:1px solid #0073CF; }")
rep(".status-SOLD { background:rgba(59,130,246,0.18); color:#93c5fd; border:1px solid rgba(59,130,246,0.35); }", ".status-SOLD { background:#002A54; color:#ffffff; border:1px solid #002A54; }")
rep(".status-CANCELED { background:rgba(100,116,139,0.20); color:#222222; border:1px solid rgba(100,116,139,0.35); }", ".status-CANCELED { background:#E8F4FC; color:#222222; border:1px solid #CCCCCC; }")
rep(".status-REDEEMED { background:rgba(168,85,247,0.20); color:#d8b4fe; border:1px solid rgba(168,85,247,0.35); }", ".status-REDEEMED { background:#005DAA; color:#ffffff; border:1px solid #005DAA; }")
rep(".cert-review { background:rgba(100,116,139,0.20); color:#222222; border:1px solid rgba(100,116,139,0.35); }", ".cert-review { background:#E8F4FC; color:#222222; border:1px solid #CCCCCC; }")
rep(".skeleton { background:linear-gradient(90deg,#E8F4FC 0%,#f4eadf 50%,#E8F4FC 100%); }", ".skeleton { background:linear-gradient(90deg,#E8F4FC 0%,#ffffff 50%,#E8F4FC 100%); }")
# the 💎 / 🔺 chips keep white text on a brand→hover gradient; the ink override
# on .text-white would put #222222 on #0073CF (3.1:1), so drop it from that list
rep(".text-white, .text-slate-200, .text-slate-300, .text-slate-400, .text-slate-500, .text-slate-600 { color:var(--ink) !important; }",
    ".text-slate-200, .text-slate-300, .text-slate-400, .text-slate-500, .text-slate-600 { color:var(--ink) !important; }")

# county landing (line ~9449): nav/disclaimer/chat-close were still dark navy at .7-.92 alpha
rep("--navy-band:#0E2136;", "--navy-band:#002A54;")
rep("--divider:rgba(148,163,184,0.12);", "--divider:rgba(204,204,204,.6);")
rep("nav{position:sticky;top:0;z-index:100;background:rgba(11,25,41,0.92);", "nav{position:sticky;top:0;z-index:100;background:rgba(255,255,255,.94);")
rep(".disclaimer-bar{background:rgba(11,25,41,0.7);", ".disclaimer-bar{background:#E8F4FC;")
rep("background:rgba(11,25,41,.85);border:1px solid var(--charcoal)", "background:rgba(255,255,255,.92);border:1px solid #CCCCCC")
rep("--orange-hover:#a94f31;--slate:#5f564e;", "--orange-hover:#005DAA;--slate:#002A54;")
rep("--red:#a13b32;", "--red:#002A54;")
rep("--divider:rgba(31,27,22,.14);", "--divider:rgba(204,204,204,.8);")

# ---- generic value substitutions (remaining rgba(...) families) -----------
GEN = {
    # comma rgba triples -> palette triples (alpha preserved)
    r'rgba\(230,240,250,': 'rgba(232,244,252,',
    r'rgba\(59,130,246,': 'rgba(0,115,207,',
    r'rgba\(16,185,129,': 'rgba(0,115,207,',
    r'rgba\(168,85,247,': 'rgba(0,42,84,',
    r'rgba\(251,146,60,': 'rgba(0,115,207,',
    r'rgba\(100,116,139,': 'rgba(204,204,204,',
    r'rgba\(31,27,22,': 'rgba(0,42,84,',
    r'rgba\(51,65,85,': 'rgba(204,204,204,',
    r'rgba\(52,211,153,': 'rgba(0,115,207,',
    r'rgba\(20,184,166,': 'rgba(0,42,84,',
    r'rgba\(11,25,41,': 'rgba(0,42,84,',
    r'rgba\(14,165,233,': 'rgba(0,115,207,',
    r'rgba\(20,83,45,': 'rgba(0,93,170,',
    r'rgba\(130,63,41,': 'rgba(0,115,207,',
    r'rgba\(248,113,113,': 'rgba(0,42,84,',
    r'rgba\(148,163,184,': 'rgba(204,204,204,',
    r'rgba\(244,114,182,': 'rgba(0,42,84,',
    r'rgba\(11,18,32,': 'rgba(255,255,255,',
    r'rgba\(245,158,11,': 'rgba(0,115,207,',
    r'rgba\(56,189,248,': 'rgba(0,93,170,',
    r'rgba\(29,78,216,': 'rgba(0,93,170,',
    r'rgba\(4,120,87,': 'rgba(0,93,170,',
    r'rgba\(23,37,84,': 'rgba(232,244,252,',
    r'rgba\(2,44,34,': 'rgba(232,244,252,',
    r'rgba\(0,0,0,\.(\d)': r'rgba(0,42,84,.\1',        # bg-black/NN modal scrims -> navy scrim
    r'rgba\(0,0,0,0\.(\d)': r'rgba(0,42,84,.\1',
}
for pat, new in GEN.items():
    s = re.sub(pat, new, s)

# compiled Tailwind (county pages): rule-specific first, then value swaps
s = s.replace('.text-slate-900{--tw-text-opacity:1;color:rgb(15 23 42/', '.text-slate-900{--tw-text-opacity:1;color:rgb(34 34 34/')
s = s.replace('.hover\\\\:text-white:hover{--tw-text-opacity:1;color:rgb(255 255 255/', '.hover\\\\:text-white:hover{--tw-text-opacity:1;color:rgb(0 42 84/')
TW = {
    '15 23 42': '255 255 255',   # slate-900/950 backgrounds
    '30 41 59': '232 244 252',   # slate-800
    '51 65 85': '204 204 204',   # slate-700
    '71 85 105': '204 204 204',  # slate-600
    '100 116 139': '0 42 84',    # slate-500 text
    '148 163 184': '0 42 84',    # slate-400 text
    '203 213 225': '34 34 34',   # slate-300 text
    '226 232 240': '34 34 34',   # slate-200 text
    '245 158 11': '0 115 207',   # amber-500
    '251 191 36': '0 93 170',    # amber-400
    '252 211 77': '0 93 170',    # amber-300
    '147 197 253': '0 115 207',  # blue-300
    '96 165 250': '0 115 207',   # blue-400
    '125 211 252': '0 115 207',  # sky-300
    '52 211 153': '0 93 170',    # emerald-400
    '249 168 212': '0 42 84',    # pink-300
    '192 132 252': '0 42 84',    # purple-400
    '252 165 165': '0 42 84',    # red-300
    '248 113 113': '0 42 84',    # red-400
}
for a, b in TW.items():
    s = re.sub(r'rgb\(' + a.replace(' ', r' ') + r'/', 'rgb(' + b + '/', s)

HEX = {
    '#4ade80': '#005DAA', '#9ca3af': '#002A54', '#e5e7eb': '#CCCCCC', '#0ea5e9': '#0073CF',
    '#fde68a': '#E8F4FC', '#3b82f6': '#0073CF', '#ec4899': '#002A54', '#1f2937': '#222222',
    '#fee2e2': '#E8F4FC', '#fca5a5': '#002A54', '#7f1d1d': '#002A54', '#f4eadf': '#ffffff',
    '#efe2d6': '#E8F4FC', '#b5a9a0': '#CCCCCC', '#5f564e': '#002A54', '#8f8479': '#002A54',
    '#dc2626': '#002A54', '#16a34a': '#005DAA', '#059669': '#005DAA', '#ca8a04': '#005DAA',
    '#ea580c': '#0073CF', '#bc5b3f': '#005DAA', '#a94f31': '#005DAA', '#a13b32': '#002A54',
    '#8f4028': '#005DAA', '#6ee7b7': '#005DAA', '#5eead4': '#002A54', '#2dd4bf': '#002A54',
    '#2d5a8e': '#CCCCCC', '#0e2136': '#002A54', '#1e3a5f': '#002A54', '#0a0f1a': '#ffffff',
    '#0f1829': '#E8F4FC', '#d8b4fe': '#002A54', '#93c5fd': '#0073CF', '#38bdf8': '#005DAA',
    '#f9a8d4': '#002A54', '#f26a36': '#0073CF',
}
for a, b in HEX.items():
    s = re.sub(re.escape(a), b, s, flags=re.I)

rep("body{background:#fff;color:#000;padding:0}", "body{background:#ffffff;color:#222222;padding:0}")
rep(".reel-player-wrap{position:relative;aspect-ratio:9/16;background:#000}", ".reel-player-wrap{position:relative;aspect-ratio:9/16;background:#002A54}")

# ---- verification ----------------------------------------------------------
PAL = {'#ffffff', '#e8f4fc', '#222222', '#002a54', '#cccccc', '#0073cf', '#005daa', '#fff', '#000'}
hexes = Counter(h.lower() for h in re.findall(r'#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b(?![0-9a-fA-F])', s))
bad_hex = {h: n for h, n in hexes.items() if h not in PAL}
PAL_RGB = {'255,255,255', '232,244,252', '34,34,34', '0,42,84', '204,204,204', '0,115,207', '0,93,170'}
rg = Counter(','.join(t) for t in re.findall(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', s))
bad_rgb = {k: n for k, n in rg.items() if k not in PAL_RGB and k != '0,0,0'}
rg2 = Counter(t.replace(' ', ',') for t in re.findall(r'rgb\((\d+ \d+ \d+)/', s))
bad_rgb2 = {k: n for k, n in rg2.items() if k not in PAL_RGB}
print('off-palette hex left:', bad_hex)
print('off-palette rgba left:', bad_rgb)
print('off-palette tailwind rgb left:', bad_rgb2)
print('#000 (3-digit) occurrences left:', hexes.get('#000', 0), ' rgba(0,0,0) left:', rg.get('0,0,0', 0))
assert not bad_hex and not bad_rgb and not bad_rgb2 and hexes.get('#000', 0) == 0, 'off-palette literals remain'
SRC.write_text(s)
print('bytes', len(orig), '->', len(s))
