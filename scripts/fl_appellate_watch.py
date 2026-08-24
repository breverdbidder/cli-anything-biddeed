#!/usr/bin/env python3
"""
FL appellate docket watch + lien-priority citation audit.

Two independent passes, both BSD-2 only (juriscraper + eyecite -- see
pyproject.toml [project.optional-dependencies] "legal"). No CourtListener
API, no AGPL code, no Brevard circuit-court scraping (juriscraper does not
support circuit dockets -- that is a separate, unbuilt mission).

Pass 1 -- appellate watch:
  Polls the Florida Supreme Court + all six District Courts of Appeal via
  juriscraper site classes. Each court gets exactly ONE HTTP request per run
  (juriscraper's default Site.set_url() with no args already fetches a single
  page of the most recent opinions -- this script never invokes backscraping,
  which would issue multiple requests). Rows whose case name substring-matches
  --party are upserted into public.fl_appellate_watch.

Pass 2 -- citation audit:
  Runs eyecite over a text/markdown corpus (default: content matched by
  `git grep -l "lien priority" -- '*.md'`), classifies every citation-shaped
  span as resolved / unresolved / malformed, prints a JSON report, and
  upserts rows into public.fl_citation_audit.

Usage:
  python scripts/fl_appellate_watch.py --dry-run
  python scripts/fl_appellate_watch.py --party "Everest Capital" --since 2026-01-01
  python scripts/fl_appellate_watch.py --courts fla,fladistctapp_5 --dry-run
  python scripts/fl_appellate_watch.py --cite-file docs/plans/CLI-Anything-BidDeed-Plan.md
"""
from __future__ import annotations

import argparse
import asyncio
import glob
import importlib
import json
import os
import re
import sys
from datetime import datetime, timezone

import httpx

COURT_DELAY_SECONDS = 2  # pacing between per-court requests, courtesy only
CONNECT_RETRY_DELAY_SECONDS = 5  # single bounded retry on transient network error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_KEY", "")

ALL_COURTS = [
    "fla",             # Florida Supreme Court
    "fladistctapp_1",  # 1st DCA
    "fladistctapp_2",  # 2nd DCA
    "fladistctapp_3",  # 3rd DCA
    "fladistctapp_4",  # 4th DCA
    "fladistctapp_5",  # 5th DCA
    "fladistctapp_6",  # 6th DCA
]

client = httpx.Client(timeout=60)


def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }


def upsert(table, rows):
    if not rows:
        return
    r = client.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(), json=rows)
    r.raise_for_status()


# ---------------------------------------------------------------------------
# Pass 1: appellate watch
# ---------------------------------------------------------------------------

async def poll_court(court_module: str, party: str, since: str | None):
    """Fetch exactly one page of recent opinions for a single court and
    return the cases whose name matches `party` (case-insensitive substring).
    """
    mod = importlib.import_module(
        f"juriscraper.opinions.united_states.state.{court_module}"
    )
    site = mod.Site()
    if since:
        start = datetime.strptime(since, "%Y-%m-%d").date()
        site.set_url(start=start)

    try:
        await site.parse()  # single HTTP request
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
        # One bounded retry for transient network failures -- not a second
        # "real" request in the hammering sense, just resilience against a
        # single dropped connection.
        await asyncio.sleep(CONNECT_RETRY_DELAY_SECONDS)
        await site.parse()

    matches = []
    party_lower = party.lower()
    for case in site.cases:
        name = case.get("name", "") or ""
        if party_lower in name.lower():
            matches.append(case)
    return site, matches


def case_to_row(court_module: str, case: dict, party: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "court": court_module,
        "case_name": case.get("name", ""),
        "docket_number": case.get("docket", ""),
        "date_filed": case.get("date"),
        "url": case.get("url"),
        "party_match": party,
        "first_seen_at": now,
        "raw": case,
    }


async def run_appellate_watch(courts: list[str], party: str, since: str | None, dry_run: bool):
    all_matches = []
    for idx, court_module in enumerate(courts):
        if idx > 0:
            await asyncio.sleep(COURT_DELAY_SECONDS)
        try:
            site, matches = await poll_court(court_module, party, since)
        except Exception as exc:
            print(f"[{court_module}] ERROR fetching: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        print(f"[{court_module}] fetched {len(site.cases)} cases (1 request), "
              f"{len(matches)} match(es) for party={party!r}")
        rows = [case_to_row(court_module, c, party) for c in matches]
        all_matches.extend(rows)

    if dry_run:
        print(f"DRY RUN: would upsert {len(all_matches)} row(s) into fl_appellate_watch")
    elif all_matches:
        upsert("fl_appellate_watch", all_matches)
        print(f"Upserted {len(all_matches)} row(s) into fl_appellate_watch")
    else:
        print("No matches -- nothing to upsert")

    return all_matches


# ---------------------------------------------------------------------------
# Pass 2: citation audit
# ---------------------------------------------------------------------------

# Loose "looks like a case citation" shape: VOLUME REPORTER-ABBREV PAGE, e.g.
# "999 So. 2d 1" or "410 U.S. 113". Used only to catch citation-shaped text
# that eyecite's reporters-db tokenizer refuses to recognize (bad/garbled
# reporter abbreviation, fabricated series like "So. 99d") so those don't
# silently vanish -- they get classified "malformed" instead of being missed
# entirely, since eyecite's own get_citations() simply returns nothing for
# text it can't match to a real reporter edition.
CANDIDATE_CITE_RE = re.compile(
    r"\d{1,4}\s+[A-Z][A-Za-z.]{1,10}\.?\s*\d*[a-z]{0,2}\s+\d{1,5}"
)


def default_cite_targets() -> list[str]:
    import subprocess
    try:
        out = subprocess.run(
            ["git", "grep", "-li", "lien priority", "--", "*.md"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            capture_output=True, text=True, timeout=30,
        )
        files = [f for f in out.stdout.splitlines() if f.strip()]
        if files:
            return files
    except Exception:
        pass
    # Fallback per spec: run against docs/ if no lien-priority seed found.
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return sorted(glob.glob(os.path.join(repo_root, "docs", "**", "*.md"), recursive=True))


def audit_citations(text: str) -> dict:
    from eyecite import get_citations
    from eyecite.models import FullCitation

    cites = get_citations(text)

    resolved, unresolved = [], []
    matched_spans = set()
    for c in cites:
        matched_text = c.matched_text()
        matched_spans.add(matched_text)
        entry = {
            "cite_text": matched_text,
            "cite_type": type(c).__name__,
        }
        if isinstance(c, FullCitation):
            groups = getattr(c, "groups", {}) or {}
            entry.update({
                "reporter": groups.get("reporter"),
                "volume": groups.get("volume"),
                "page": groups.get("page"),
            })
            resolved.append(entry)
        else:
            # Short-form / Id. / Supra / reference citations -- eyecite found
            # them but they need antecedent resolution we don't attempt here.
            unresolved.append(entry)

    malformed = []
    for m in CANDIDATE_CITE_RE.finditer(text):
        span_text = m.group(0)
        if span_text in matched_spans:
            continue
        # Skip spans that are substrings of something eyecite already matched.
        if any(span_text in mt or mt in span_text for mt in matched_spans):
            continue
        malformed.append({"cite_text": span_text, "cite_type": "UNRECOGNIZED_REPORTER"})

    return {"resolved": resolved, "unresolved": unresolved, "malformed": malformed}


def audit_row(source_path: str, entry: dict, resolved: bool) -> dict:
    return {
        "source_path": source_path,
        "cite_text": entry["cite_text"],
        "cite_type": entry["cite_type"],
        "resolved": resolved,
        "reporter": entry.get("reporter"),
        "volume": entry.get("volume"),
        "page": entry.get("page"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def run_citation_audit(cite_file: str | None, dry_run: bool) -> dict:
    targets = [cite_file] if cite_file else default_cite_targets()
    combined = {"resolved": [], "unresolved": [], "malformed": []}
    rows = []

    for path in targets:
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except FileNotFoundError:
            print(f"ERROR: cite file not found: {path}", file=sys.stderr)
            continue

        report = audit_citations(text)
        for entry in report["resolved"]:
            rows.append(audit_row(path, entry, resolved=True))
        for entry in report["unresolved"]:
            rows.append(audit_row(path, entry, resolved=False))
        for entry in report["malformed"]:
            rows.append(audit_row(path, entry, resolved=False))

        for k in combined:
            combined[k].extend(report[k])

    if dry_run:
        print(f"DRY RUN: would upsert {len(rows)} row(s) into fl_citation_audit")
    elif rows:
        upsert("fl_citation_audit", rows)
        print(f"Upserted {len(rows)} row(s) into fl_citation_audit")
    else:
        print("No citations found -- nothing to upsert")

    return combined


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--courts", default="all",
                         help="Comma-separated court modules (e.g. fla,fladistctapp_5). Default: all seven.")
    parser.add_argument("--party", default="Everest Capital", help="Case-insensitive party-name substring to watch for.")
    parser.add_argument("--since", default=None, help="YYYY-MM-DD -- only fetch opinions on/after this date.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to Supabase.")
    parser.add_argument("--cite-file", default=None,
                         help="Path to a markdown/text file to run the eyecite citation audit against. "
                              "If omitted, targets files matched by `git grep -l \"lien priority\" -- '*.md'`.")
    args = parser.parse_args()

    if args.courts == "all":
        courts = ALL_COURTS
    else:
        courts = [c.strip() for c in args.courts.split(",") if c.strip()]
        unknown = set(courts) - set(ALL_COURTS)
        if unknown:
            print(f"ERROR: unknown court module(s): {sorted(unknown)}. Valid: {ALL_COURTS}", file=sys.stderr)
            sys.exit(1)

    if not args.dry_run and not SUPABASE_KEY:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set and --dry-run not passed", file=sys.stderr)
        sys.exit(1)

    asyncio.run(run_appellate_watch(courts, args.party, args.since, args.dry_run))

    # Pass 2 always runs -- --cite-file targets one file explicitly, otherwise
    # it falls back to `git grep -l "lien priority" -- '*.md'` discovery (or
    # docs/ if that finds nothing), per spec.
    cite_report = run_citation_audit(args.cite_file, args.dry_run)
    print(json.dumps(cite_report, indent=2))

    sys.exit(0)


if __name__ == "__main__":
    main()
