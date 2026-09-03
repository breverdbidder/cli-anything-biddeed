#!/usr/bin/env bash
# CMO FACTORY (issue #19777) -- negative test (b) from the issue body:
# "merge.py with a verdict file lacking gates_green refuses."
set -euo pipefail
REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
cd "$REPO_ROOT"

FAIL=0
VDIR="factory/gtm/fixtures/verdicts"

echo "--- gates_green=false (issue 99999) must REFUSE ---"
if python3 factory/gtm/merge.py --issue 99999 --verdicts-dir "$VDIR" --dry-run; then
  echo "FAIL: merge.py decided MERGE despite gates_green=false"
  FAIL=1
else
  echo "PASS: merge.py refused (gates_green=false)"
fi

echo "--- control: verdict==PASS, gates_green==true (issue 99998) must decide MERGE ---"
if python3 factory/gtm/merge.py --issue 99998 --verdicts-dir "$VDIR" --dry-run; then
  echo "PASS (control): merge.py decided MERGE on a fully-green verdict"
else
  echo "FAIL (control): merge.py refused a fully-green verdict -- logic or fixture is broken"
  FAIL=1
fi

echo "--- missing verdict file (issue 88888) must REFUSE ---"
if python3 factory/gtm/merge.py --issue 88888 --verdicts-dir "$VDIR" --dry-run; then
  echo "FAIL: merge.py decided MERGE with no verdict file present"
  FAIL=1
else
  echo "PASS: merge.py refused (no verdict file)"
fi

if [ "$FAIL" -eq 0 ]; then
  echo "NEGATIVE TEST (b) RESULT: PASS"
  exit 0
else
  echo "NEGATIVE TEST (b) RESULT: FAIL"
  exit 1
fi
