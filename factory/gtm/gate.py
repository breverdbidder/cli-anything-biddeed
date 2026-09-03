#!/usr/bin/env python3
"""CMO FACTORY (issue #19777) -- compliance gate.

Runs the 6 compliance checks named in docs/gtm/MISSION.md over a given set
of artifact files (marketing copy, JSON, HTML -- anything text-based a GTM
lane produces), plus optional live page/render checks.

Markers (stdout, one per line, only on PASS of that specific thing):
    GTM_COMPLIANCE_PASSED   -- all 6 compliance checks passed
    GTM_PAGE_200            -- only emitted if --check-url was passed and it returned 200
    GTM_RENDER_OK           -- only emitted if --check-render-file was passed and it parsed non-empty

Absence of a marker for something you asked this script to check = FAIL.
Absence of a marker for something you did NOT ask it to check is simply
not applicable -- this script never fabricates a marker for a check it did
not run. merge.py and doctor.py must not assume a marker exists unless the
corresponding --check-* flag was passed.

Exit code: 0 if every check that WAS run passed, 1 otherwise.
"""
import argparse
import json
import os
import re
import sys
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MISSION_MD = os.path.join(REPO_ROOT, "docs", "gtm", "MISSION.md")

VENDOR_NAMES = [
    "Tracerfy", "Bright Data", "Apify", "OpenRouter", "ElevenLabs",
    "skip-trace", "skip trace", "summitleads",
]
HOMEOWNER_CONTACT_PATTERNS = [
    r"\bmailer\b", r"\btext (the|a) (homeowner|seller)\b",
    r"\bcall the (homeowner|seller)\b", r"\bforeclosure.?relief\b",
    r"\bsave your home\b", r"\bmortgage.?relief\b",
]
PERSON_NAME_FIELD_KEYS = {"buyer_name", "owner_name", "bidder_name", "winner_name", "defendant_name"}
PERSON_NAME_PROSE_RE = re.compile(
    r"\b(won by|owned by|bidder was|purchased by)\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b"
)
INSURANCE_RE = re.compile(r"\binsurance\b", re.IGNORECASE)
PROTECTION_PARTNERS_RE = re.compile(r"Protection Partners", re.IGNORECASE)
CERTIFIED_COUNT_RE = re.compile(r"(\d+)\s*(?:certified|gold[- ]standard)\s*counties", re.IGNORECASE)


def read_artifact_text(paths):
    chunks = []
    for p in paths:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            chunks.append(f.read())
    return "\n".join(chunks)


def check_banned_terms(text):
    hits = [name for name in VENDOR_NAMES if name.lower() in text.lower()]
    return (len(hits) == 0, {"hits": hits})


def check_vendor_name_detector(text):
    # Same source list as banned_terms -- kept as a distinct named check per
    # docs/gtm/MISSION.md's compliance-checks table (#4 in the NEVER-list
    # maps to both banned_terms's phrasing check and this structural check).
    hits = [name for name in VENDOR_NAMES if name.lower() in text.lower()]
    return (len(hits) == 0, {"hits": hits})


def check_person_name_detector(text):
    prose_hits = PERSON_NAME_PROSE_RE.findall(text)
    json_hits = []
    try:
        data = json.loads(text)
        found = _find_keys(data, PERSON_NAME_FIELD_KEYS)
        json_hits.extend(found)
    except (json.JSONDecodeError, ValueError):
        pass
    ok = not prose_hits and not json_hits
    return (ok, {"prose_hits": prose_hits, "json_key_hits": json_hits})


def _find_keys(obj, keys, path=""):
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            if k in keys and v:
                found.append(p)
            found.extend(_find_keys(v, keys, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found.extend(_find_keys(v, keys, f"{path}[{i}]"))
    return found


def check_homeowner_contact_scan(text):
    hits = [pat for pat in HOMEOWNER_CONTACT_PATTERNS if re.search(pat, text, re.IGNORECASE)]
    return (len(hits) == 0, {"pattern_hits": hits})


def check_certified_county_count_match(text, supabase_url=None, supabase_key=None):
    matches = CERTIFIED_COUNT_RE.findall(text)
    if not matches:
        # Nothing to check -- no county-count claim in this artifact set.
        return (True, {"claims_found": [], "note": "no certified-county count literal present"})
    supabase_url = supabase_url or os.environ.get("SUPABASE_URL")
    supabase_key = supabase_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        return (False, {"claims_found": matches, "error": "SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set -- cannot re-query v_certified_counties live, failing closed"})
    req = urllib.request.Request(
        f"{supabase_url}/rest/v1/v_certified_counties?select=county_slug&consecutive_gold=gte.1",
        headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Prefer": "count=exact",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_range = resp.headers.get("Content-Range", "")
            live_count = int(content_range.split("/")[-1]) if "/" in content_range else None
    except Exception as e:  # noqa: BLE001 -- report as a failed check, not a crash
        return (False, {"claims_found": matches, "error": f"live query failed: {e}"})
    claimed_counts = {int(m) for m in matches}
    ok = live_count is not None and claimed_counts == {live_count}
    return (ok, {"claims_found": matches, "live_count": live_count})


def check_insurance_exclusivity_scan(text):
    bad_spans = []
    for m in INSURANCE_RE.finditer(text):
        window = text[max(0, m.start() - 200): m.end() + 200]
        if not PROTECTION_PARTNERS_RE.search(window):
            bad_spans.append(text[max(0, m.start() - 30): m.end() + 30])
    return (len(bad_spans) == 0, {"unscoped_mentions": bad_spans})


CHECKS = [
    ("banned_terms", check_banned_terms),
    ("person_name_detector", check_person_name_detector),
    ("vendor_name_detector", check_vendor_name_detector),
    ("homeowner_contact_scan", check_homeowner_contact_scan),
    ("certified_county_count_match", check_certified_county_count_match),
    ("insurance_exclusivity_scan", check_insurance_exclusivity_scan),
]


def run_compliance_checks(text):
    results = {}
    all_ok = True
    for name, fn in CHECKS:
        ok, detail = fn(text)
        results[name] = {"passed": ok, "detail": detail}
        all_ok = all_ok and ok
    return all_ok, results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--paths", nargs="*", default=[], help="artifact files to run the 6 compliance checks over")
    ap.add_argument("--check-url", default=None, help="optional URL to GET and require 200 for GTM_PAGE_200")
    ap.add_argument("--check-render-file", default=None, help="optional path to a rendered artifact; non-empty required for GTM_RENDER_OK")
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON result summary to stderr")
    args = ap.parse_args()

    overall_ok = True
    summary = {}

    if args.paths:
        text = read_artifact_text(args.paths)
        compliance_ok, results = run_compliance_checks(text)
        summary["compliance"] = results
        if compliance_ok:
            print("GTM_COMPLIANCE_PASSED")
        else:
            overall_ok = False
            failed = [k for k, v in results.items() if not v["passed"]]
            print(f"COMPLIANCE FAIL: {', '.join(failed)}", file=sys.stderr)
    else:
        print("no --paths given -- compliance checks not run, GTM_COMPLIANCE_PASSED withheld", file=sys.stderr)
        overall_ok = False

    if args.check_url:
        try:
            with urllib.request.urlopen(args.check_url, timeout=15) as resp:
                status = resp.status
        except Exception as e:  # noqa: BLE001
            status = None
            summary["page_check_error"] = str(e)
        summary["page_status"] = status
        if status == 200:
            print("GTM_PAGE_200")
        else:
            overall_ok = False
            print(f"PAGE CHECK FAIL: status={status}", file=sys.stderr)

    if args.check_render_file:
        try:
            with open(args.check_render_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            render_ok = len(content.strip()) > 0
        except OSError as e:
            render_ok = False
            summary["render_check_error"] = str(e)
        if render_ok:
            print("GTM_RENDER_OK")
        else:
            overall_ok = False
            print("RENDER CHECK FAIL: empty or unreadable", file=sys.stderr)

    if args.json:
        print(json.dumps(summary, indent=2), file=sys.stderr)

    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()
