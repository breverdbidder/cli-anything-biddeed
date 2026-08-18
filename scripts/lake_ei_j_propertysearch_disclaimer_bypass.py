#!/usr/bin/env python3
"""Lake E/I/J session (2026-08-18): owner-name -> parcel_id lookup via the
lakecopropappr.com HTML search form (property-search.aspx), bypassing its
disclaimer-page redirect gate.

WHY THIS ROUTE (distinct from scripts/shard14_lake_e_ownername_match.py,
which queries PropertyAppraiser/FieldMap/MapServer/0 directly): that ArcGIS
FieldMap layer either doesn't expose OwnerName for these 12 case rows or was
exhausted in a prior session -- 12 lake auctions still had parcel_id IS NULL
at session start. This script instead drives the public-facing HTML search
UI at lakecopropappr.com/property-search.aspx, which requires POSTing the
disclaimer form (property-disclaimer.aspx) first to receive a valid session
cookie. Once past the disclaimer, the search form is a plain ASP.NET
postback (owner-name / street / subdivision fields -> gvParcels GridView).

DISCLAIMER BYPASS MECHANICS (not a CAPTCHA, just a session-cookie gate):
  1. GET property-search.aspx -> 302 redirect to property-disclaimer.aspx
     (ASP.NET_SessionId cookie set on this first response).
  2. GET property-disclaimer.aspx?to=... -> extract __VIEWSTATE,
     __VIEWSTATEGENERATOR, __EVENTVALIDATION hidden fields.
  3. POST those fields + ctl00$cphMain$imgBtnSubmit.x/y (the "I Agree"
     image button) back to the same disclaimer URL, using the SAME cookie
     jar. Response redirects internally (200) to property-search.aspx with
     the disclaimer flag now cleared for this session.
  4. From then on, GET property-search.aspx returns the real search form
     (not the disclaimer) as long as the cookie jar persists.

SEARCH MECHANICS: POST to property-search.aspx with
  ctl00$cphMain$txtOwnerName = "<LASTNAME> <firstname-fragment-or-blank>"
  ctl00$cphMain$rblRealTangible = "Real"
  ctl00$cphMain$btnSearch = "Search"
  (+ fresh __VIEWSTATE/__VIEWSTATEGENERATOR/__EVENTVALIDATION pulled from
  the GET immediately prior -- the ASP.NET form is stateful per-request)
Results parse out of the gvParcels GridView: AltKey, Owner, Address, STRAP
(parcel number, dash-separated e.g. 24-24-26-0011-000-18200). Also supports
txtStreet+txtCity for address search and txtSubdivision for subdivision
search when owner-name search returns zero/ambiguous hits.

MATCHING RULE (conservative, BLANK > WRONG): only write when the search
returns a single row whose Owner field contains the case's defendant
surname AND (for multi-word defendants) a first-name/given-name token, OR
an unambiguous single exact-surname hit after last-name-only search. Skipped
if zero hits, or if multiple same-surname owners exist and no first-name
token disambiguates (see ZAYAS/CARTWRIGHT/DALY/LABARCA in the receipt below
-- correctly left NULL).

PARCEL_ID FORMAT: convert the dash-separated STRAP to the county's existing
18-digit no-dash format already used in multi_county_auctions.parcel_id for
lake (e.g. "24-24-26-0011-000-18200" -> "242426001100018200") to match the
convention of pre-existing linked rows.

GEO (lat/lng): property-details.aspx does not expose parcel geometry, but
the STRAP maps 1:1 to an AltKey which is exactly the LocalGov/
ParcelPublicAccess/MapServer/7 (OwnerParcel_1K) layer's OWNPARCELID field on
gis.lakecountyfl.gov/lakegis/rest/services -- queried by AltKey, not STRAP.
Centroid is a simple vertex-average of the returned polygon ring (adequate
for card-completeness geo, not survey-grade).

VALUES: property-details.aspx?AltKey=<n> has an "Estimated Taxes" table
whose first two $ columns per row are Market Value then Assessed Value
(same figure repeated per taxing authority row -- take the first row).

ZONING CAVEAT (does not close I on its own): letter I additionally requires
the parcel to already exist in v_zoning_gold_standard_card (parcel_zones ->
zoning_districts) with a non-null zone_code. Newly parcel-linked rows are
NOT automatically zone-linked. Of the 6 rows this script successfully
linked, 4 sit in unincorporated Lake County (no zoning MapServer layer found
anywhere in gis.lakecountyfl.gov/lakegis/rest/services -- LocalGov/
CityZoning only covers 11 incorporated municipalities, not unincorporated
county), and the other 2 (Eustis, Leesburg) are in cities that ALSO have no
layer in LocalGov/CityZoning. Populating real zone_code/standards for these
6 parcels is letter-G-scope ordinance research, out of scope here.

RESULTS THIS SESSION (2026-08-18, lake E/I/J push):
  Linked (parcel_id + address + city + zip + market/assessed value +
  lat/lng, all written via PostgREST PATCH):
    2024CA002034 -> altkey 3929464, owner "ZEBALLOS SORIANO XAVIER S & IVONNE
        M RODRIGUEZ LAMILLA" (case defendant "IVONNE MERCEDES RODRIGUEZ
        LAMILLA, ET AL"), 17571 SAW PALMETTO AVE, CLERMONT FL 34714,
        STRAP 24-24-26-0011-000-18200
    2025CA002147 -> altkey 3744608, owner "BUCHANAN THOMAS E" (case
        defendant "THOMAS E. BUCHANAN, ET AL"), 35103 MARSHALL RD, EUSTIS FL
        32736, STRAP 05-19-27-0004-000-00700
    2025CA002565 -> altkey 1636132, owner "FRANCILLON EDWIN H" (case
        defendant "EDWIN HYPPPOLITE FRANCILLON, ET AL"), 2106 HOLLYWOOD AVE,
        EUSTIS FL 32726, STRAP 01-19-26-0600-002-02200
    2026CA000434 -> altkey 3794578, owner "OLIO MARY F" (case defendant
        "MARY FRANCES OLIO ET AL"), 1220 TUSKEGEE ST, LEESBURG FL 34748,
        STRAP 22-19-24-0850-000-00100
    2025CA001816 -> altkey 3839650, owner "MC CORD MARK & KRYSTAL" (case
        defendant "MARK MCCORD ET AL"), 7536 PARK HILL AVE, LEESBURG FL
        34748, STRAP 29-19-25-1600-000-01000
    2024CA001936 -> altkey 3739957, owner "HAUSCHILDT STEPHANIE & CASEY"
        (case defendant "STEPHANIE HAUSCHILDT, ET AL" -- this case had no
        owner_name/plaintiff/clerk_url in our DB at all; recovered fresh
        from the LIVE clerk calendar default.aspx + sale_details.aspx?id=
        20597, which resolved plaintiff="WOODRIDGE MASTER ASSOCIATION INC"),
        1126 WOODSONG WAY, CLERMONT FL 34714, STRAP 26-24-26-2400-000-02800

  Genuinely blocked (real effort, no match -- left NULL):
    2023CA000367 (PRIDE FUNDING LLC) -- searched "PRIDE FUNDING" and "PRIDE"
        last-name-only: zero appraiser records for the LLC itself (expected;
        an LLC lienholder/plaintiff-side entity is not necessarily the
        record titleholder at the appraiser)
    2024CA002312 (MAUREEN A DALY ET AL, cancelled auction, lower priority)
        -- "DALY" surname search returns 25 results, alphabetically sorted;
        no "DALY MAUREEN"/"MAUREEN A DALY" entry exists in that list
    2025CA001590 (recovered fresh from clerk calendar: plaintiff="JPMORGAN
        CHASE BANK", defendant="JULIE A. JEFFERSON, ET AL", id=20596) --
        "JEFFERSON JULIE"/"JEFFERSON JULIE A" zero hits; "JEFFERSON J"
        returns only JOHANN and JUDY, neither a plausible match
    2025CA001729 (TIFFANY MONIQUE CARTWRIGHT ET AL) -- 13 CARTWRIGHT
        records, none first-named Tiffany/Monique
    2025CC010839 (VALERIE LEON ZAYAS, ET AL) -- 25 ZAYAS records (surname
        search page-1-capped), none matching "VALERIE"/"LEON"; subdivision
        search on "ARDMORE" (the HOA plaintiff's name, Ardmore Reserve HOA)
        returned 25 rows but ~16 were owner-redacted "Not public record per
        F.S. 119.071" (LE/first-responder exemption) and the visible names
        didn't include Zayas -- inconclusive, not a confirmed non-match, but
        not usable as a positive match either
    2026CA000560 (MARYLINDA LABARCA ET AL) -- zero hits for
        "LABARCA"/"LABARCA MARYLINDA"/"MARY LINDA LABARCA" (surname does not
        exist in the appraiser owner index at all)

Usage: python3 scripts/lake_ei_j_propertysearch_disclaimer_bypass.py <OWNER SEARCH STRING>
  (interactive/manual lookup tool -- prints JSON of matched rows; does not
  write to the DB itself. DB writes for this session were done via direct
  PostgREST PATCH calls, documented in the session's commit/PR history.)
"""
import http.cookiejar
import json
import re
import sys
import urllib.parse
import urllib.request

BASE = "https://www.lakecopropappr.com"
COOKIE_FILE = "/tmp/lake_lca_cookies.txt"


def _opener():
    cj = http.cookiejar.MozillaCookieJar(COOKIE_FILE)
    try:
        cj.load(ignore_discard=True, ignore_expires=True)
    except FileNotFoundError:
        pass
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)), cj


def agree_disclaimer():
    opener, cj = _opener()
    req0 = urllib.request.Request(f"{BASE}/property-search.aspx", headers={"User-Agent": "Mozilla/5.0"})
    resp0 = opener.open(req0, timeout=20)
    if "property-disclaimer" in resp0.geturl():
        html = resp0.read().decode("utf-8", errors="replace")
        vs = re.search(r'id="__VIEWSTATE" value="([^"]*)"', html).group(1)
        vsg = re.search(r'id="__VIEWSTATEGENERATOR" value="([^"]*)"', html).group(1)
        ev = re.search(r'id="__EVENTVALIDATION" value="([^"]*)"', html).group(1)
        data = urllib.parse.urlencode(
            {
                "__VIEWSTATE": vs,
                "__VIEWSTATEGENERATOR": vsg,
                "__EVENTVALIDATION": ev,
                "ctl00$cphMain$imgBtnSubmit.x": "50",
                "ctl00$cphMain$imgBtnSubmit.y": "15",
            }
        ).encode()
        req = urllib.request.Request(
            resp0.geturl(),
            data=data,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mozilla/5.0"},
        )
        opener.open(req, timeout=20)
    cj.save(COOKIE_FILE, ignore_discard=True, ignore_expires=True)


def search_owner(owner_name):
    opener, cj = _opener()
    req0 = urllib.request.Request(f"{BASE}/property-search.aspx", headers={"User-Agent": "Mozilla/5.0"})
    resp0 = opener.open(req0, timeout=20)
    html = resp0.read().decode("utf-8", errors="replace")
    if "property-disclaimer" in resp0.geturl():
        return None
    vs = re.search(r'id="__VIEWSTATE" value="([^"]*)"', html).group(1)
    vsg = re.search(r'id="__VIEWSTATEGENERATOR" value="([^"]*)"', html).group(1)
    ev = re.search(r'id="__EVENTVALIDATION" value="([^"]*)"', html).group(1)
    fields = [
        ("__EVENTTARGET", ""),
        ("__EVENTARGUMENT", ""),
        ("__LASTFOCUS", ""),
        ("__VIEWSTATE", vs),
        ("__VIEWSTATEGENERATOR", vsg),
        ("__VIEWSTATEENCRYPTED", ""),
        ("__EVENTVALIDATION", ev),
        ("ctl00$cphMain$txtOwnerName", owner_name),
        ("ctl00$cphMain$txtStreet", ""),
        ("ctl00$cphMain$txtCity", ""),
        ("ctl00$cphMain$txtSubdivision", ""),
        ("ctl00$cphMain$txtSubdivisionNum", ""),
        ("ctl00$cphMain$txtBlock", ""),
        ("ctl00$cphMain$txtLot", ""),
        ("ctl00$cphMain$txtAltKey", ""),
        ("ctl00$cphMain$txtPropertyName", ""),
        ("ctl00$cphMain$txtBook", ""),
        ("ctl00$cphMain$txtPage", ""),
        ("ctl00$cphMain$txtTownship", ""),
        ("ctl00$cphMain$txtRange", ""),
        ("ctl00$cphMain$txtSection", ""),
        ("ctl00$cphMain$rblRealTangible", "Real"),
        ("ctl00$cphMain$btnSearch", "Search"),
    ]
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        f"{BASE}/property-search.aspx",
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0",
            "Referer": f"{BASE}/property-search.aspx",
        },
    )
    resp = opener.open(req, timeout=20)
    body = resp.read().decode("utf-8", errors="replace")
    cj.save(COOKIE_FILE, ignore_discard=True, ignore_expires=True)
    return body


def parse_results(html):
    rows = []
    pattern = (
        r'href="property-details\.aspx\?AltKey=(\d+)">view</a>\s*</td><td>\s*([^\n<]+)\s*\n'
        r'\s*<div class="property"[^>]*>([^\n<]*)\s*\n\s*</td><td>\s*\n\s*([^\n<]+?)\s*\n\s*</td>'
    )
    for m in re.finditer(pattern, html):
        altkey, owner, addr, strap = m.groups()
        rows.append(
            {
                "altkey": altkey.strip(),
                "owner": owner.strip(),
                "address": addr.strip(),
                "strap": strap.strip(),
                "parcel_id": strap.strip().replace("-", ""),
            }
        )
    return rows


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: lake_ei_j_propertysearch_disclaimer_bypass.py '<OWNER SEARCH STRING>'", file=sys.stderr)
        sys.exit(1)
    owner = sys.argv[1]
    agree_disclaimer()
    body = search_owner(owner)
    if body is None:
        print(json.dumps({"error": "disclaimer not accepted"}))
        sys.exit(1)
    if "no results found" in body:
        print(json.dumps({"results": [], "no_results": True}))
    else:
        print(json.dumps({"results": parse_results(body)}, indent=2))
