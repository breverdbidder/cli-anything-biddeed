#!/usr/bin/env bash
# CMO FACTORY (issue #19777) -- negative test (a) from the issue body:
# "planting the string 'Tracerfy' in a fixture caption makes gate.py FAIL."
set -euo pipefail
REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
cd "$REPO_ROOT"

FAIL=0

echo "--- control: clean caption must PASS ---"
if python3 factory/gtm/gate.py --paths factory/gtm/fixtures/caption_clean.txt; then
  echo "PASS (control): clean caption passed gate.py"
else
  echo "FAIL (control): clean caption did not pass -- test fixture or gate.py logic is broken"
  FAIL=1
fi

echo "--- Tracerfy-planted caption must FAIL ---"
if python3 factory/gtm/gate.py --paths factory/gtm/fixtures/caption_with_tracerfy.txt; then
  echo "FAIL: caption_with_tracerfy.txt passed gate.py -- vendor-name detection is broken"
  FAIL=1
else
  echo "PASS: caption_with_tracerfy.txt correctly failed gate.py (banned_terms/vendor_name_detector)"
fi

if [ "$FAIL" -eq 0 ]; then
  echo "NEGATIVE TEST (a) RESULT: PASS"
  exit 0
else
  echo "NEGATIVE TEST (a) RESULT: FAIL"
  exit 1
fi
