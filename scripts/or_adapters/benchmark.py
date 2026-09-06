#!/usr/bin/env python3
"""Benchmark adapter — issue #20050 Step 2 asked for "Benchmark adapter, same
contract as landmark.py, roll out to Benchmark counties." This session's
platform-discovery work (fingerprinting + a live check of
apps.stjohnsclerk.com/Benchmark/Home.aspx/Search, the one FL clerk site this
session found branded "Benchmark") found that finding to be a FALSE PREMISE:

Benchmark and Landmark are both Pioneer Technology Group / Catalis products,
but they are NOT the same kind of system:
  - Landmark Web = Official Records / recording search (deeds, mortgages,
    liens, judgments, lis pendens) — what scripts/or_adapters/landmark.py
    covers.
  - Benchmark = COURT CASE MANAGEMENT (docket search: Criminal Felony,
    Domestic Relations, Probate, Guardianship, Civil Traffic, etc. case
    types) — a different system entirely, serving court dockets, not
    recorded land instruments.

Live evidence (2026-09-06): apps.stjohnsclerk.com/Benchmark/Home.aspx/Search
returns a real search form (HTTP 200, no login/paywall/captcha) whose
case-type dropdown is exclusively court-docket categories (Criminal Felony,
Misdemeanor, Domestic Relations/Family, Probate, Guardianship, Small Claims,
Code Enforcement, ...) — no document-type/book-page/instrument-number/party-
name-on-a-recorded-instrument fields anywhere. St. Johns's own real Official
Records Search link (apps.stjohnsclerk.com/Landmark) is a SEPARATE app.

No Florida county was found this session running Benchmark for Official
Records / recorded-instrument search — because that product does not do
that job. Every other FL clerk site checked this session (see
docs/spec/20050.md and scripts/clerk_ssot/or_platform_map.json) runs
AcclaimWeb, Landmark Web, kofile, myfloridacounty.com, or a county-custom
system for Official Records.

This file exists because the issue asked for it. It intentionally does NOT
contain speculative scraping code against a product with no real target —
per K2 (no code for scenarios that can't happen) and the Honesty Protocol
(no convincing-looking but untestable code). If a genuine FL Benchmark-
branded OFFICIAL RECORDS (not court-docket) deployment is ever found, build
its adapter here following the exact contract in landmark.py (same
LandmarkSession-style Playwright driver, same classify_docs()/tier1_rows()
reuse, same COUNTY_* config dict shape).
"""
import sys

COUNTY_BENCHMARK = {}  # no FL county confirmed this session — see module docstring


def main():
    print(
        "BLOCKED: no genuine FL Official-Records Benchmark deployment was found this "
        "session (issue #20050) — every 'Benchmark'-branded FL clerk site checked turns "
        "out to be Pioneer/Catalis's COURT CASE docket-search product, not a land-records "
        "system. See this file's module docstring and docs/spec/20050.md for the evidence "
        "trail. 0 counties attempted — disclosed finding, not a silent skip."
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
