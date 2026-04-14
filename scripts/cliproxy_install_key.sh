#!/bin/bash
# Read /root/.tmp_plain.txt and inject into /opt/cliproxy-gateway/config.yaml
set -e
export CFG=/opt/cliproxy-gateway/config.yaml
cp "$CFG" "${CFG}.bak.predify.$(date +%s)"
KEY=$(cat /root/.tmp_plain.txt)
export DIFY_KEY="$KEY"
python3 -c 'import re,os; c=open(os.environ["CFG"]).read(); k=os.environ["DIFY_KEY"]; new=re.sub(r"(gemini-api-key:\s*\n\s*-\s*api-key:\s*)\S+", r"\g<1>"+k, c, count=1); open(os.environ["CFG"],"w").write(new); print("patched")' 
unset KEY DIFY_KEY
grep -A1 '^gemini-api-key:' "$CFG" | head -3 | sed -E 's/(api-key:\s*).*/\1<redacted>/'
