#!/usr/bin/env python3
"""Install a new Gemini API key into /opt/cliproxy-gateway/config.yaml.
Reads plaintext key from /root/.tmp_newkey (written by SSH stdin pipe).
Never echoes the key value.
"""
import os, re, sys

CFG = "/opt/cliproxy-gateway/config.yaml"
KEY_FILE = "/root/.tmp_newkey"

with open(KEY_FILE) as f:
    newkey = f.read().strip()

if len(newkey) < 30 or not newkey.startswith("AIza"):
    print(f"ERROR: invalid key format (len={len(newkey)})", file=sys.stderr)
    sys.exit(1)

with open(CFG) as f:
    c = f.read()

new = re.sub(
    r"(gemini-api-key:\s*\n\s*-\s*api-key:\s*)\S+",
    lambda m: m.group(1) + newkey,
    c,
    count=1,
)

if new == c:
    print("ERROR: regex did not match — config structure changed?", file=sys.stderr)
    sys.exit(2)

with open(CFG, "w") as f:
    f.write(new)

# Only report length info, NEVER the value
print(f"config patched: key len={len(newkey)} first4={newkey[:4]}")
