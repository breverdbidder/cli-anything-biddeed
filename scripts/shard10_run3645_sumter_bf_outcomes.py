#!/usr/bin/env python3
"""
shard10_run3645_sumter_bf_outcomes.py

Sumter county B/F (verified independent sale outcomes) backfill.

Live sources fetched (real HTTP, no fabrication):
  1. https://www.sumterclerk.com/2026/3/tax-deed-sale
     - Raw HTML confirms TD-5028 (G03A014, ROBINSON KENNETH C, $13,515.69)
       and TD-5031 (D20G135, ROBINSON RONALD W, $16,506.04) and TD-5036
       (J34A003, PERKINS DIXIE ADAMS ETAL, $4,559.56) show a dollar opening
       bid figure (NOT "REDEEMED"), meaning they proceeded to auction.
       TD-5027 (D34E010, CURRY DAVID W & WILMA A) IS marked REDEEMED --
       this is a DIFFERENT parcel than TD-5028 (prior task context had
       mismatched this).
  2. https://docs.google.com/spreadsheets/d/1uW4muYX69nJvSNPqLt93jf0IYcNWxzpA3HEjUxIZoz4/export?format=csv
     ("Tax Deed Sales Surplus" -- linked from https://www.sumterclerk.com/surplus-funds-list)
     - Confirms surplus funds held by the Clerk for TD-5028 ($186,371.18
       surplus), TD-5031 ($190,366.66 surplus), TD-5036 ($45,365.00 surplus),
       all dated sale 3/26/2026. Surplus ONLY exists when a tax deed sale
       actually occurs and the winning bid exceeds the statutory minimum --
       this is independent, clerk-published proof these 3 parcels SOLD.
     - NOTE: "surplus" per Fla. Stat. 197.582 is winning_bid minus statutory
       disbursements (opening bid + fees + interest), NOT simply
       winning_bid - opening_bid. The exact winning bid dollar figure is
       NOT published anywhere we could find (no per-case "certificate of
       sale" / results page exists on sumterclerk.com; official records
       index search (myfloridacounty.com/orisearch/60) and the county OCRS
       civil case search (civitekflorida.com/ocrs/county/60) were both
       attempted live and could not be completed -- OCRS requires a
       Cloudflare Turnstile-gated PrimeFaces form that could not be
       reliably automated in this session).
     - Therefore: we record outcome=SOLD with winning_bid = opening_bid
       (the last CONFIRMED real dollar figure tied to the case) is NOT
       done -- that would misrepresent an unverified number as a sale
       price. Instead we do NOT set sold_amount/tier1_sold_amount for
       these three (would require fabricating the actual winning bid),
       but we DO insert a tax_deed_outcomes row documenting outcome=SOLD
       with winning_bid=NULL and a note in data_source, since B/F's
       "verified_outcomes" defder needs sold_amount IS NOT NULL on the
       multi_county_auctions row to count anyway -- so this is honest
       housekeeping, not a metric-mover, and avoids ever writing a
       fabricated dollar amount as VERIFIED.
  3. https://www.sumterclerk.com/2026/7/tax-deed-sales
     - Raw HTML for the July 9 2026 sale confirms:
         TD-5054 (G05R062, JUDD KAREN L)              REDEEMED
         TD-5056 (G07F008, KLEYN PATRICIA I)          $1,467.39 (NOT redeemed)
         TD-5057 (G06F064, MORROW SCOTT JR ESTATE OF) REDEEMED
         TD-5058 (J16C019, JACKSON MARTIN)            REDEEMED
       This matches (and confirms) the prior session's
       shard1_run3534_sumter_td_case_backfill.py claim exactly.
  4. Foreclosure sale PDF for 2026-07-02 (fetched via Playwright-rendered
     event page https://www.sumterclerk.com/events?ID=DB281A5D-9574-4E4C-9AD4-C6D65507C821
     -> https://www.sumterclerk.com/?a=Files.Serve&File_id=1ECCECFB-B437-408E-AEDE-A65428B402A3
     "MFS-2026-7-02.pdf"):
       2024-CA-000364  CARRINGTON MORTGAGE SERVICES LLC vs PATAWARAN, MARLON
                       Final Judgment $270,019.20 -- 4266 CR 691, Webster FL
       2024-CA-000367  U S Bank Trust National Association vs The Village CDD #3
                       Final Judgment $309,422.24 -- 3288 Shelby St, The Villages FL
       2025-CA-000255  TL Gulf Coast Holdings LLC vs Wildwood Phase One LLC
                       SALE CANCELLED (matches our DB auction_status='cancelled')
     This PDF is a PRE-sale listing (judgment amount, not sale result).
     No post-sale results page, certificate of title list, or foreclosure-
     surplus-by-case record for 07/02/2026 could be found on
     sumterclerk.com. The Registry/Foreclosure Sales Surplus ledger
     (https://www.sumterclerk.com/index.cfm?a=Files.Serve&File_id=A18CDE74-E88E-4589-AD30-B81888DC2B26,
     titled "REGISTRY - MAY 2026") only covers disbursements through
     5/29/2026 and does not reach the 07/02/2026 sale date.
     Sumter County OCRS (civitekflorida.com/ocrs/county/60) case search was
     attempted live via Playwright but is gated by a Cloudflare Turnstile
     token embedded in a PrimeFaces form whose dynamic component IDs could
     not be driven reliably -- search never returned results.
     CONCLUSION: 2024-CA-000364 and 2024-CA-000367 final sale outcome
     (sold vs no-sale, and winning bid) is UNVERIFIED. No write made for
     either row. auction_status='closed' in our DB is left as-is since we
     cannot disprove it and the sale did happen at the scheduled date/time
     per the calendar event; only the winning bid / SOLD determination is
     unverified.

WRITES PERFORMED (see main()):
  - tax_deed_outcomes: 3 new rows (TD-5028, TD-5031, TD-5036) with
    outcome='SOLD', winning_bid=NULL (unverified), data_source=
    'sumterclerk_official:surplus_funds_list_proves_sale' (no 'promote'
    substring), source_url = the surplus funds CSV export URL.
    NOTE: multi_county_auctions.sold_amount is intentionally NOT set for
    these because we do not have a verified dollar figure for the actual
    winning bid -- only proof that a sale occurred. This means B/F metrics
    will NOT move from this run (by design -- avoids fabricating a number).
  - No writes for TD-5054/5057/5058 (REDEEMED, correctly excluded).
  - No writes for TD-5056 (sale occurred, no verified outcome/amount found).
  - No writes for 2024-CA-000364 / 2024-CA-000367 (no verified outcome found).
  - No sold_amount/tier1_sold_amount PATCHed on multi_county_auctions at all
    in this run, since every dollar figure we could find was either a
    pre-sale opening bid or an unverifiable derived surplus figure, and the
    hard guardrail forbids writing a value we cannot trace to a real,
    directly-confirmed sale price.
"""
import os
import sys
import json
import urllib.request
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

SURPLUS_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1uW4muYX69nJvSNPqLt93jf0IYcNWxzpA3HEjUxIZoz4/export?format=csv"
)
MARCH_SALE_URL = "https://www.sumterclerk.com/2026/3/tax-deed-sale"

# Rows confirmed SOLD (proceeded to auction, surplus generated -> clerk-verified
# proof of sale) but with NO verified winning-bid dollar figure available from
# any public source we could reach this session.
CONFIRMED_SOLD_NO_VERIFIED_AMOUNT = [
    {
        "case_number": "TD-5028",
        "parcel_id": "G03A014",
        "auction_date": "2026-03-26",
        "surplus_evidence": 186371.18,
    },
    {
        "case_number": "TD-5031",
        "parcel_id": "D20G135",
        "auction_date": "2026-03-26",
        "surplus_evidence": 190366.66,
    },
    {
        "case_number": "TD-5036",
        "parcel_id": "J34A003",
        "auction_date": "2026-03-26",
        "surplus_evidence": 45365.00,
    },
]


def http(method, path, body=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read().decode() or "null")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {e.read().decode()}")


def main():
    written = []

    # Insert tax_deed_outcomes rows documenting the confirmed sale (via
    # surplus-fund proof), explicitly leaving winning_bid NULL since we
    # cannot verify the exact dollar figure. This is honest housekeeping,
    # NOT a B/F metric mover (B/F additionally require sold_amount on the
    # multi_county_auctions row, which we do not set here).
    for row in CONFIRMED_SOLD_NO_VERIFIED_AMOUNT:
        payload = {
            "case_number": row["case_number"],
            "county": "sumter",
            "auction_date": row["auction_date"],
            "parcel_id": row["parcel_id"],
            "outcome": "SOLD",
            "winning_bid": None,
            "data_source": "sumterclerk_official:surplus_funds_list_proves_sale",
            "source_url": SURPLUS_CSV_URL,
        }
        status, resp = http("POST", "tax_deed_outcomes", payload)
        print(f"INSERT tax_deed_outcomes {row['case_number']}: HTTP {status}")
        print(json.dumps(resp, indent=2))
        if status not in (200, 201):
            raise RuntimeError(f"FAILED to insert outcome row for {row['case_number']}: {resp}")
        written.append((row["case_number"], row["parcel_id"]))

    if not written:
        raise RuntimeError(
            "FAIL-LOUD: parsed >0 real confirmed-sold records but wrote 0 rows. "
            "This should never happen silently."
        )

    print("\n=== SUMMARY ===")
    print(f"tax_deed_outcomes rows written: {len(written)}")
    for cn, pid in written:
        print(f"  {cn} / {pid}")
    print(
        "\nNo sold_amount / tier1_sold_amount PATCHed on multi_county_auctions "
        "in this run -- no verified winning-bid dollar figure was found for "
        "ANY of the 9 candidate rows examined. B/F metrics are NOT expected "
        "to change from this run."
    )


if __name__ == "__main__":
    main()
