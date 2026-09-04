#!/usr/bin/env bash
# CMO FACTORY (issue #19777) -- negative test (a) from the issue body:
# "planting the string 'Tracerfy' in a fixture caption makes gate.py FAIL."
#
# SPR-01 (issue #19826) extends this with one negative case per new check
# added to factory/gtm/gate.py (CONTENT_SOP.md SS6 P2/P6/P7/P8/P9/P17/P18),
# plus a control fixture proving the founder allowlist (M7) still passes.
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

echo "--- control: founder-attributed caption (M7 allowlist) must PASS ---"
if python3 factory/gtm/gate.py --paths factory/gtm/fixtures/caption_with_founder_allowlisted.txt; then
  echo "PASS (control): founder-allowlisted caption passed gate.py"
else
  echo "FAIL (control): founder-allowlisted caption did not pass -- M7 carve-out is broken"
  FAIL=1
fi

echo "--- Tracerfy-planted caption must FAIL ---"
if python3 factory/gtm/gate.py --paths factory/gtm/fixtures/caption_with_tracerfy.txt; then
  echo "FAIL: caption_with_tracerfy.txt passed gate.py -- vendor-name detection is broken"
  FAIL=1
else
  echo "PASS: caption_with_tracerfy.txt correctly failed gate.py (banned_terms/vendor_name_detector)"
fi

echo "--- second-person-to-owner phrasing (P4 widening) must FAIL ---"
if python3 factory/gtm/gate.py --paths factory/gtm/fixtures/caption_with_homeowner_contact.txt; then
  echo "FAIL: caption_with_homeowner_contact.txt passed gate.py -- widened homeowner_contact_scan is broken"
  FAIL=1
else
  echo "PASS: caption_with_homeowner_contact.txt correctly failed gate.py (homeowner_contact_scan)"
fi

echo "--- competitor name (canon hard rule 1) must FAIL ---"
if python3 factory/gtm/gate.py --paths factory/gtm/fixtures/caption_with_competitor.txt; then
  echo "FAIL: caption_with_competitor.txt passed gate.py -- competitor_terms_scan is broken"
  FAIL=1
else
  echo "PASS: caption_with_competitor.txt correctly failed gate.py (competitor_terms_scan)"
fi

echo "--- retired tagline line must FAIL ---"
if python3 factory/gtm/gate.py --paths factory/gtm/fixtures/caption_with_retired_tagline.txt; then
  echo "FAIL: caption_with_retired_tagline.txt passed gate.py -- retired_lines_and_product_names_scan is broken"
  FAIL=1
else
  echo "PASS: caption_with_retired_tagline.txt correctly failed gate.py (retired_lines_and_product_names_scan)"
fi

echo "--- 'S5' as a public product name must FAIL ---"
if python3 factory/gtm/gate.py --paths factory/gtm/fixtures/caption_with_s5.txt; then
  echo "FAIL: caption_with_s5.txt passed gate.py -- retired_lines_and_product_names_scan (S5) is broken"
  FAIL=1
else
  echo "PASS: caption_with_s5.txt correctly failed gate.py (retired_lines_and_product_names_scan)"
fi

echo "--- '14 patents' phrasing must FAIL ---"
if python3 factory/gtm/gate.py --paths factory/gtm/fixtures/caption_with_patent.txt; then
  echo "FAIL: caption_with_patent.txt passed gate.py -- patent_phrasing_scan is broken"
  FAIL=1
else
  echo "PASS: caption_with_patent.txt correctly failed gate.py (patent_phrasing_scan)"
fi

echo "--- canon string with wrong case/punctuation must FAIL ---"
if python3 factory/gtm/gate.py --paths factory/gtm/fixtures/caption_with_canon_drift.txt; then
  echo "FAIL: caption_with_canon_drift.txt passed gate.py -- canon_strings_scan is broken"
  FAIL=1
else
  echo "PASS: caption_with_canon_drift.txt correctly failed gate.py (canon_strings_scan)"
fi

echo "--- multiple '!' / manufactured urgency must FAIL ---"
if python3 factory/gtm/gate.py --paths factory/gtm/fixtures/caption_with_urgency.txt; then
  echo "FAIL: caption_with_urgency.txt passed gate.py -- energy_rules_scan is broken"
  FAIL=1
else
  echo "PASS: caption_with_urgency.txt correctly failed gate.py (energy_rules_scan)"
fi

echo "--- 'all 50 states' positioning claim must FAIL ---"
if python3 factory/gtm/gate.py --paths factory/gtm/fixtures/caption_with_positioning.txt; then
  echo "FAIL: caption_with_positioning.txt passed gate.py -- positioning_scan is broken"
  FAIL=1
else
  echo "PASS: caption_with_positioning.txt correctly failed gate.py (positioning_scan)"
fi

echo "--- contempt-for-the-bidder line (P17/N4) must FAIL ---"
if python3 factory/gtm/gate.py --paths factory/gtm/fixtures/caption_with_contempt.txt; then
  echo "FAIL: caption_with_contempt.txt passed gate.py -- contempt_scan is broken"
  FAIL=1
else
  echo "PASS: caption_with_contempt.txt correctly failed gate.py (contempt_scan)"
fi

echo "--- buzzword line (P18/N5) must FAIL ---"
if python3 factory/gtm/gate.py --paths factory/gtm/fixtures/caption_with_buzzword.txt; then
  echo "FAIL: caption_with_buzzword.txt passed gate.py -- buzzword_scan is broken"
  FAIL=1
else
  echo "PASS: caption_with_buzzword.txt correctly failed gate.py (buzzword_scan)"
fi

echo "--- non-founder person name (widened person_name_detector) must FAIL ---"
if python3 factory/gtm/gate.py --paths factory/gtm/fixtures/caption_with_nonfounder_name.txt; then
  echo "FAIL: caption_with_nonfounder_name.txt passed gate.py -- widened person_name_detector is broken"
  FAIL=1
else
  echo "PASS: caption_with_nonfounder_name.txt correctly failed gate.py (person_name_detector)"
fi

if [ "$FAIL" -eq 0 ]; then
  echo "NEGATIVE TEST RESULT: PASS"
  exit 0
else
  echo "NEGATIVE TEST RESULT: FAIL"
  exit 1
fi
