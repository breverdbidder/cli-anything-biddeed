from pathlib import Path

path = Path(__file__).resolve().parents[2] / 'src' / 'worker.js'
s = path.read_text()
replacements = {
    '#ffffff': '#FBFAF7',
    '#FFFFFF': '#FBFAF7',
    '#222222': '#1F1B16',
    '#222': '#1F1B16',
    '#0073CF': '#8F4028',
    '#0073cf': '#8F4028',
    '#005DAA': '#7A3424',
    '#005daa': '#7A3424',
    '#E8F4FC': '#F8D4C5',
    '#e8f4fc': '#F8D4C5',
    '#002A54': '#1F1B16',
    '#002a54': '#1F1B16',
    '#CCCCCC': '#DDD5C9',
    '#cccccc': '#DDD5C9',
    'rgba(0,115,207,': 'rgba(143,64,40,',
    'rgba(0,42,84,': 'rgba(31,27,22,',
    'rgba(232,244,252,': 'rgba(248,212,197,',
    'rgba(255,255,255,': 'rgba(251,250,247,',
    'rgba(255, 255, 255,': 'rgba(251,250,247,',
}
counts = {}
for old, new in replacements.items():
    n = s.count(old)
    if n:
        s = s.replace(old, new)
        counts[old] = n
old = '.bd-shell-drawer{position:fixed;display:flex;flex-direction:column;'
new = '.bd-shell-drawer{position:fixed;display:none;flex-direction:column;'
if old in s:
    s = s.replace(old, new, 1)
    s = s.replace('.bd-shell-drawer[data-open=true]{transform:translateX(0)}', '.bd-shell-drawer[data-open=true]{display:flex;transform:translateX(0)}', 1)
    counts['closed_drawer'] = 1
path.write_text(s)
print({'file': str(path), 'replacements': counts})
