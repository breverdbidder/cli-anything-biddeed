#!/usr/bin/env python3
"""Gold Standard, county=brevard, letter I (property card completeness).

Dispatch: issue #19806 (this session, 2026-09-03), consuming the diagnosis
from the immediately-prior diagnose-only session on the same snapshot
(auctions_total=7491, card_complete=6322 (84.4%), needs >=95%
(7117/7491) to PASS -- 795-row gap to threshold, 1169 total failing rows).

DIAGNOSIS RECAP (fresh-verified live at the top of THIS session before any
write, via direct curl against PostgREST -- not re-trusting the cached
diagnosis JSON):
  - 2 rows: assessed_value AND market_value both NULL, but parcel_id,
    property_address, latitude/longitude ALL already present. Re-confirmed
    live this session (curl multi_county_auctions?id=in.(...)) still NULL.
  - 159 rows: true "skeleton" rows -- only case_number/sale_type/county/
    auction_date populated, property_address/parcel_id/latitude/longitude/
    assessed_value/market_value ALL NULL, bcpao_enriched=false. This is a
    NEW population vs every prior brevard-I session (which only ever
    diagnosed the STREET_NAME=UNKNOWN / no-GIS-feature structural-ceiling
    bucket) -- these rows never had ANY enrichment attempted, because the
    standard scraper pipeline step hasn't reached them yet (pipeline lag,
    not a data ceiling).

METHOD (two independent, source-verified levers -- NEW for letter I, never
tried in a prior brevard-I session):

  Lever 1 -- VALUE_MISSING (2 rows): both rows' parcel_id/address/geo were
  already complete; only assessed_value/market_value were missing. Backfill
  assessed_value = LAND_VALUE + BLDG_VALUE read live from Brevard County's
  own GIS parcel layer (Base_Map/Parcel_New_WKID2881/MapServer/5), keyed by
  the row's existing parcel_id (TaxAcct). Prior brevard-I sessions only ever
  queried STREET_NAME on this same layer -- the LAND_VALUE/BLDG_VALUE fields
  were never pulled before for this letter.

  Lever 2 -- SKELETON (159 rows): two-step live lookup by case_number,
  branching on case-number format:
    (a) Tax-deed numeric case_number (e.g. "260256"): POST
        https://brevard.realtdm.com/public/cases/list filtered by
        filterCaseNumber -> parses "Parcel Number" (=Brevard TaxAcct) off
        the public case card. Public portal, no auth (same mechanism
        already proven and scheduled in scripts/realtdm_cases_sweep.py /
        .github/workflows/scrape-brevard-realtdm.yml, reused verbatim
        here as a synchronous per-case lookup instead of the async sweep).
    (b) Foreclosure/civil case_number (has dashes, e.g.
        "05-2025-CA-048681-XXCA-BC"): Brevard Clerk AcclaimWeb
        (vaclmweb1.brevardclerk.us) case-number search -> extract
        DocLegalDescription -> regex LT/BLK/PB/PG (BLK-first, no-BLK
        fallback) -> resolve PLAT_BOOK/PLAT_PAGE(/BLOCK)/LOT against the
        same Base_Map GIS layer. Identical mechanism to
        scripts/brevard_i_clerk_platform_legal_backfill_e91f7a52.py,
        reused verbatim, applied here to a population that script never
        touched (parcel_id-IS-NULL rows filtered there required
        data_source IS NULL; here the trigger is "skeleton row", a
        disjoint condition).
    Once a TaxAcct is resolved (either path), a SECOND query against
    Base_Map/Parcel_New_WKID2881/MapServer/5 by TaxAcct fetches
    PARCEL_ID/STREET_NUMBER/STREET_NAME/STREET_TYPE/CITY/ZIP_CODE/
    LAND_VALUE/BLDG_VALUE + polygon geometry (centroid computed from the
    ring). property_address is written ONLY if STREET_NAME is populated
    and not 'UNKNOWN'/blank and not 'CONFIDENTIAL' (fabrication guard,
    identical to every prior brevard-I script). assessed_value =
    LAND_VALUE+BLDG_VALUE (written only if the sum is > 0). parcel_id is
    written as the TaxAcct string (matches the format already live in
    multi_county_auctions.parcel_id for every other brevard row, confirmed
    this session via live sample query).

FABRICATION GUARD: every written field traces to a live upstream feature
attribute (RealTDM public case card, AcclaimWeb legal description, or
Brevard County's own GIS parcel layer). No inference, no fallback value, no
STREET_NAME=UNKNOWN/CONFIDENTIAL ever written as property_address. Rows
where the case-number lookup returns zero results, or the GIS TaxAcct
lookup returns anything other than exactly 1 feature, are left untouched
and reported as residual/blocked -- not force-fixed.

Zoning linkage (the 4th card_complete predicate, parcel_id/tax_account
present in v_zoning_gold_standard_card with zone_code NOT NULL) is NOT
separately written by this script -- Brevard's zoning coverage is already
broad (v_zoning_gold_standard_card), so a resolved TaxAcct is checked
read-only against that view for reporting purposes but no parcel_zones
INSERT is attempted here (out of scope for this lever; a resolved-but-
zone-unlinked row will still show up as a residual in the post-fix count
and is a separate, already-documented lever from
scripts/gold_standard_brevard_i_countyzoning_2row_20260826.py).

Usage:
  python3 scripts/gold_standard_brevard_i_shard19806_fix.py             # dry-run (default)
  python3 scripts/gold_standard_brevard_i_shard19806_fix.py --apply     # write resolved rows live

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
dispatch: issue #19806 (brevard-I gold-standard fix session, 2026-09-03)
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar
import datetime as dt

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
assert SB_URL and SB_KEY, "SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

BASE_PARCEL = ("https://gis.brevardfl.gov/gissrv/rest/services/"
               "Base_Map/Parcel_New_WKID2881/MapServer/5/query")
REALTDM_BASE = "https://brevard.realtdm.com"
ACCLAIM_BASE = "http://vaclmweb1.brevardclerk.us"

LEGAL_RE_BLK = re.compile(r"LT\s*(\S+)\s+BLK\s*(\S+)\s+PB\s*(\d+)\s+PG\s*(\d+)", re.IGNORECASE)
LEGAL_RE_NOBLK = re.compile(r"LT\s*(\S+)\s+PB\s*(\d+)\s+PG\s*(\d+)", re.IGNORECASE)

# ── Row lists (id, case_number), frozen from the live diagnosis re-verified
# at session start -- see docstring. ────────────────────────────────────────
SKELETON_ROWS = [
    ("00cb844d-5439-42f7-9f00-df9b592c0564", "05-2025-CA-048681-XXCA-BC"),
    ("040b0307-05d2-4f86-a7cc-c49f5870443e", "260256"),
    ("05520177-0494-4cf7-adf4-ed2b0eb07feb", "05-2025-CA-051473-XXCA-BC"),
    ("0692e30b-a860-45d1-8c5a-9a3dfcbe448e", "260120"),
    ("09685302-4bac-4607-93dd-90e929a712a4", "260089"),
    ("09e868e9-8c9c-4915-bb0d-4981ebeb402f", "05-2025-CA-062804-XXCA-BC"),
    ("0b9706a8-070c-48e1-bde2-c1b47251ecd9", "260310"),
    ("0c01d738-171d-4ab0-ad9f-81bd67606df9", "260085"),
    ("0c4d7c22-81b4-46aa-9c4f-6b1c3b46ffb8", "260092"),
    ("0e409252-0980-4a83-b179-a2bdea02b8b6", "05-2025-CA-049223-XXCA-BC"),
    ("0f68b6cb-9cf7-4199-bb28-b8eb8f7bfa35", "05-2026-CA-026832-XXCA-BC"),
    ("10a760ab-5067-4d5a-b9ee-b854a88b5f2c", "05-2025-CA-055712-XXCA-BC"),
    ("10aeee91-f199-4a54-9260-f7d8f7b05420", "260276"),
    ("1117e838-2109-45e0-8bb9-1daf20a095f4", "260087"),
    ("15529cc8-2320-4fd0-b2ae-29eea11fa19d", "260184"),
    ("168a34a0-3d7f-4598-a1aa-128617713d49", "05-2025-CA-037060-XXCA-BC"),
    ("17cc0f27-a1af-4113-838f-79efa4201267", "260250"),
    ("18a2f389-c37f-49f7-8aa5-2a0c026757de", "260049"),
    ("18bb7f28-0477-48c7-aba9-15c13be48920", "05-2025-CA-057921-XXCA-BC"),
    ("1ad00813-cdf2-450b-83b2-48eba7bab6aa", "260079"),
    ("1b8d1736-ae8e-45b8-a00f-a1edd6726ffc", "05-2026-CA-027714-XXCA-BC"),
    ("22e25fe9-a0a4-4ea7-9163-4e5645bd700c", "260056"),
    ("2711e51a-8e9a-496d-b436-447c14cae254", "260124"),
    ("289a5994-95c5-496f-bbbc-3489a8029cac", "260275"),
    ("290048f5-3a45-4faa-9f18-fe4a617053c7", "05-2025-CC-040905-XXCC-BC"),
    ("2b0338a2-098f-4fa3-beb2-35cb5d0431f4", "260065"),
    ("2b096a64-4235-48ac-a36c-bdcc2e93a800", "260284"),
    ("2b8dacd7-6b48-4f7d-a6b5-458e5d5afac7", "260130"),
    ("2e82afcd-9ec3-4e05-994e-2b66f9b8b5e0", "260227"),
    ("31154cd3-7889-4923-8800-66d7bdc7ed20", "260283"),
    ("3252d14b-b043-4eaa-8ced-c379870c8c58", "05-2025-CC-055721-XXCC-BC"),
    ("38d414b5-1e88-405c-aad8-1a847ef184cb", "260147"),
    ("3bb2042f-4fa5-4128-aff1-ae646e498425", "260181"),
    ("3c1e0dec-936e-4021-9a32-7f7d93ac90e8", "260294"),
    ("3d1f0f86-3b45-4d8f-afe2-d829ef1d6993", "260126"),
    ("411ac422-8efa-4050-96c4-ea3dd250218d", "260064"),
    ("41b41c42-cd3f-4805-9af1-08e448b807ae", "260163"),
    ("43c9be36-bffe-43a7-9966-7ca28af6c08e", "05-2025-CA-024895-XXCA-BC"),
    ("4494fc41-e268-4e0d-95e3-f46fec55e807", "260061"),
    ("44b8319b-2fe5-4696-9a80-4e1988bf8483", "260075"),
    ("457b86c1-1834-4596-8f08-6dc52eb471ef", "260059"),
    ("461bde0a-b547-4a33-83ea-542ed392523a", "05-2026-CA-021618-XXCA-BC"),
    ("46b4f3ff-7ac7-4620-973f-dada23b28904", "05-2025-CA-049531-XXCA-BC"),
    ("4948b90a-2bb4-4c2c-b5ea-d6608c1ac31f", "260051"),
    ("4a718b1e-030d-409c-9799-4e6306ef8c9b", "260050"),
    ("4aca3338-b323-4b1c-b046-047905d0d801", "260121"),
    ("509e0bf0-71cc-45b8-aba5-3a57e2bc33d2", "260243"),
    ("5301e001-3261-4d75-a69f-dcb642d13ff9", "260183"),
    ("5398d60d-6238-41e4-bd05-02fd57ac1901", "260088"),
    ("54ad4d12-6ede-44ad-a9e1-d067504f651e", "260226"),
    ("55f70206-c357-4dce-81fe-9bd437e220d8", "260148"),
    ("56f758e5-bbdb-4c55-9da7-1b48f43e8dbf", "05-2025-CA-055318-XXCA-BC"),
    ("58320753-97fd-4768-91c2-015fb9634af1", "260185"),
    ("592cfa82-e78e-4c50-a430-718da51b8cad", "05-2025-CA-057733-XXCA-BC"),
    ("5a1e70d1-3a98-478e-a235-870591ac7652", "05-2025-CA-049232-XXCA-BC"),
    ("5b3f3046-d89c-42db-9db9-aae8f61335a3", "05-2026-CA-011334-XXCA-BC"),
    ("5beeb487-ee66-43f6-8753-ccd42beb9504", "260219"),
    ("5e4c8b99-5c35-4d14-b007-09f7e55d58ec", "260264"),
    ("5fb6593e-be07-4c4d-a84b-9bbc10255f31", "260272"),
    ("5fbc2f34-8667-4f6b-b292-594ed5fec77d", "260081"),
    ("6286d958-1f7a-4327-a458-602162176c9e", "260070"),
    ("62bc1e75-1d61-4d94-9711-16b5347e9cf3", "260057"),
    ("635376a1-19b4-4bb1-bd2d-e933be050420", "260067"),
    ("64300ab3-5460-44ab-8ddd-cb06d3013e46", "260093"),
    ("653b525e-1bc4-4c91-8f3a-c2b0a5c16167", "260178"),
    ("669f7baa-f5b5-415d-8932-ec82117d5c89", "260246"),
    ("6a01a337-d6de-4f9f-9d73-c794af4b0635", "260123"),
    ("6b76ace0-d345-40cd-b0b3-d18c6d83555a", "260302"),
    ("6e926ec9-396d-4ece-8ba4-e2b99d379adb", "260053"),
    ("703c9b61-a937-4ea1-b8fb-242131ef44cd", "05-2025-CC-054298-XXCC-BC"),
    ("718332a9-4ebe-4f5f-ad08-022907428f58", "260282"),
    ("72ef5dde-36eb-4761-ae8a-80254d2826d9", "260220"),
    ("758f4714-aacb-4dc8-ba9a-4175d8543f0c", "260177"),
    ("7605352b-2bc7-4144-bec3-4b3db9fb87e8", "260195"),
    ("772db85e-bcbd-4f0c-a126-b6fa05cbb842", "260154"),
    ("797c5cfe-8470-4808-8231-068a4debf0bd", "260237"),
    ("7bb0ccaa-1482-4a0c-a70b-107372c8cab2", "05-2025-CA-030132-XXCA-BC"),
    ("7e03efb5-c85c-423b-a6ac-f2229e3d1d6f", "260265"),
    ("7fc84df4-548d-47b7-a553-2d0a5fbbf885", "260060"),
    ("7fe56d00-6e44-4bb0-89c0-a7da1df2fba0", "260231"),
    ("827d8bfe-cdc9-4903-a423-e905a11c3c40", "260058"),
    ("838a63a9-1bf9-4ae0-b478-39a4e17d508c", "260289"),
    ("86db5fa1-6ebd-4df6-9225-e5f4d8621134", "05-2026-CA-022911-XXCA-BC"),
    ("88d905dd-33a7-464a-9c7d-5e13888a9003", "260299"),
    ("8a910546-8f6e-428d-a3c6-90b2cdbe9756", "260162"),
    ("8bc705a0-c514-4d04-b4f5-ff90a6db257f", "260156"),
    ("8dce209c-71d0-4ee5-98f1-e43e5b2bdd58", "260055"),
    ("914e29e6-636f-4d66-bbfa-9b385c3dc6dd", "260077"),
    ("9246d0a5-dddd-4521-a655-39d6a6432b30", "05-2025-CA-022704-XXCA-BC"),
    ("92f0ec2d-30b4-4c1a-9f9f-a85e476cc3f9", "260171"),
    ("93541d4f-74ca-4542-940e-35fe678f3a89", "260054"),
    ("93b10c6d-c8f3-4b49-a8be-4d2251fc8edc", "260273"),
    ("94d3b7a9-c2bc-4197-9cb5-a57b5a53f158", "260292"),
    ("95136b43-aa38-4c64-aaac-ae506d1a566e", "260262"),
    ("958dbcf0-6ce4-4227-ab92-6762c8ab8b73", "05-2025-CA-037988-XXCA-BC"),
    ("9a386ab2-4341-4fae-9407-65422fdf6fd4", "260241"),
    ("9b217cb6-72e0-41be-b7c6-8c02acaec1b8", "260131"),
    ("9b2abc1f-9f0f-4c88-bd3f-18331ae39b9c", "260142"),
    ("9ca92338-794f-4fee-82cd-25bb7090ce9e", "05-2025-CA-017803-XXCA-BC"),
    ("9cc20cff-9f13-46af-8bc1-9c9f2b6bb585", "260138"),
    ("9cdd25c3-2009-42ff-8d3f-83f68144b467", "260044"),
    ("9edda294-5f50-4522-a58a-6cd1b85f9905", "260308"),
    ("9f5a6599-2766-4ef2-8aff-12a2b34a5f75", "260287"),
    ("9fb1acab-4403-4d8e-9a28-5a522a5ee3a0", "260167"),
    ("a12575c2-5451-4d22-afb7-dc6377a04cf2", "260267"),
    ("a2a33402-70a0-4eec-993c-870630dfa883", "260129"),
    ("a85691f0-8754-4809-ad81-968e02649d60", "260223"),
    ("aa2e4341-4eab-4833-b198-12e772ea34ae", "260134"),
    ("aae7dad5-3766-421d-aca4-0f49c88ccff0", "05-2025-CA-050924-XXCA-BC"),
    ("ac3e9e12-8602-4458-bd42-8aebe9e45e3c", "260137"),
    ("ac5bdb86-2b19-46b8-8121-89c1d6dfc546", "260143"),
    ("ae2e4e26-012b-4422-b989-c5dfab003e3d", "260270"),
    ("ae4d84fc-23a6-4030-bcc4-f0f09d86727d", "260078"),
    ("b1d16fd5-ec87-4d82-bfd3-66bdcecd7e49", "05-2025-CA-042645-XXCA-BC"),
    ("b1e1d03b-ac10-4dea-84e0-a2ac7fd92591", "260288"),
    ("b30c51fe-d411-4f40-8bd1-2372d808edfd", "260072"),
    ("b412bfb3-841c-41db-ad78-34790a93782a", "260307"),
    ("b6e76b26-b882-477a-8e0b-910192da3941", "260128"),
    ("b799a693-c415-4051-84a3-3abf93469861", "260253"),
    ("b852356b-9b25-4a8b-be2c-641b7f9625b0", "05-2026-CA-027717-XXCA-BC"),
    ("b8814895-3ab5-4d01-9ea7-3184d2d2c4f5", "260187"),
    ("ba102678-3d72-458d-a354-e713f707c413", "260259"),
    ("bd29b789-41d2-44d8-8f04-70f483ef01c4", "260268"),
    ("c04750d5-9db9-465a-983e-9f6e6e702818", "260170"),
    ("c1a7adac-c50e-4358-8c77-fb6156d61b00", "260296"),
    ("c1ef9f99-e587-4a9b-8cce-742ee7821d8b", "260222"),
    ("c40fbfd8-bab1-4b8e-9993-c3d026ebe1fa", "260122"),
    ("c51f72fd-bf43-4e5d-ba9d-393854e01f6a", "260298"),
    ("c6f70d23-de31-400b-8b17-3d9651eac479", "260046"),
    ("c86b37aa-7234-4e19-99f5-97dc3a603247", "260239"),
    ("cb0d3624-375a-44b1-8f96-0c73ddfddca0", "260076"),
    ("cd10140e-db99-4a58-bee5-3a73692e2344", "05-2023-CA-020534-XXXX-XX"),
    ("ce0a2776-5466-47af-a16f-5b7d99e66250", "260179"),
    ("cea5a70c-9803-4768-a3f8-634a1984ff5b", "05-2025-CA-052707-XXCA-BC"),
    ("cf137b08-d40e-40ea-9731-732ef4e5f198", "260048"),
    ("d079b05e-8b54-41b7-bd38-1de2f15584e9", "05-2025-CA-040781-XXCA-BC"),
    ("d4c47396-ab43-4417-9892-3bb8776a9f52", "260303"),
    ("d6ae3dc1-ff5b-48b8-beac-8e296358d897", "260091"),
    ("d854c594-c632-4898-9bd2-950a03550b0a", "260180"),
    ("d9d62af8-5812-4deb-8818-5aaf50152b05", "260127"),
    ("dd826f7c-d498-40ab-b924-30565979d8f1", "260074"),
    ("df39403e-ffca-4804-8191-5cbb03bb0989", "260286"),
    ("e02e2e3d-f3df-47cf-8546-9efa717493db", "260240"),
    ("e6569359-b771-4b50-8fed-fe62d9286be2", "260271"),
    ("e679d208-ee69-470b-b554-0cedcc2386f7", "260043"),
    ("e991dea0-b210-431f-bc56-b04e42aeaa76", "05-2025-CA-035554-XXCA-BC"),
    ("ea0fdc3c-e4ed-4ff2-9f2c-431124ea26cd", "260252"),
    ("ecaf1455-e50f-4faa-8cf9-5b4c46fdda21", "260151"),
    ("ee499085-6cb1-46e8-8515-f6f81d7b62c3", "260255"),
    ("ee821ed7-d6a0-4bff-ac77-84dd0e901443", "260280"),
    ("f6b97691-0b84-4b04-8ade-f0d488008479", "260260"),
    ("f6cd4fbc-c7b2-4882-a4c7-14e9aeb55090", "05-2025-CC-062516-XXCC-BC"),
    ("f799be7d-241e-43ce-92b5-9183c1dfb43c", "05-2025-CC-064638-XXCC-BC"),
    ("f8bc2006-bcb6-49e2-8ad6-e12e93ed4151", "260221"),
    ("fcccb7ea-04b3-4020-88f9-75e311b16392", "260155"),
    ("fe0854cb-0e2b-4fe5-9bee-0fd01c592432", "260291"),
    ("fee5e137-0c7c-40b3-a160-642e3fc2fc12", "05-2025-CA-027416-XXCA-BC"),
    ("ff0077a5-78c6-4fba-8909-442d4de32057", "05-2025-CA-043830-XXCA-BC"),
    ("fffea56a-b1ae-4120-9068-f832e9462695", "260082"),
]

VALUE_MISSING_ROWS = [
    ("26ffb46e-3a9e-4a0a-9aeb-f532880cbde8", "260209"),
    ("fbc227a6-c0ae-4d01-9084-ad4050212f52", "260212"),
]


def sb_headers():
    return {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}


def get(url, headers=None, retries=4):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:300]
            if e.code == 503 and "PGRST002" in body and attempt < retries - 1:
                time.sleep(4)
                continue
            raise
        except Exception:
            if attempt < retries - 1:
                time.sleep(3)
                continue
            raise


def sb_get(path, retries=4):
    return get(f"{SB_URL}/rest/v1/{path}", sb_headers(), retries=retries)


def sb_patch(row_id, fields):
    body = json.dumps(fields).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}", data=body, method="PATCH",
        headers={**sb_headers(), "Content-Type": "application/json", "Prefer": "return=minimal"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        print(f"  PATCH ERROR id={row_id}: {e.code} {e.read().decode()[:300]}", file=sys.stderr)
        return e.code


def base_parcel_lookup(tax_account):
    """Query Brevard GIS Base_Map by TaxAcct. Returns attrs+centroid or None
    if not exactly 1 feature."""
    params = {"where": f"TaxAcct={tax_account}",
              "outFields": "TaxAcct,PARCEL_ID,STREET_NUMBER,STREET_NAME,STREET_TYPE,CITY,ZIP_CODE,LAND_VALUE,BLDG_VALUE",
              "returnGeometry": "true", "outSR": "4326", "f": "json"}
    d = get(BASE_PARCEL + "?" + urllib.parse.urlencode(params))
    feats = d.get("features", [])
    if len(feats) != 1:
        return None
    f = feats[0]
    a = f["attributes"]
    ring = (f.get("geometry") or {}).get("rings", [[]])[0]
    lat = lon = None
    if ring:
        lon = sum(p[0] for p in ring) / len(ring)
        lat = sum(p[1] for p in ring) / len(ring)
    return a, lat, lon


def build_fields_from_gis(a, lat, lon):
    """Apply fabrication guard, return dict of writable fields (may omit
    property_address if UNKNOWN/CONFIDENTIAL/blank)."""
    street = " ".join(x for x in [a.get("STREET_NUMBER"), a.get("STREET_NAME"), a.get("STREET_TYPE")] if x).strip()
    city = (a.get("CITY") or "").strip()
    street_name = (a.get("STREET_NAME") or "").strip().upper()
    is_confidential = "CONFIDENTIAL" in street_name
    is_unknown = street_name in ("", "UNKNOWN") or not street

    fields = {}
    if street and city and not is_confidential and not is_unknown:
        zip_code = (a.get("ZIP_CODE") or "").strip()
        addr = f"{street}, {city}, FL {zip_code}".strip().rstrip(",")
        fields["property_address"] = addr
    if lat is not None and lon is not None:
        fields["latitude"] = lat
        fields["longitude"] = lon
    value = (a.get("LAND_VALUE") or 0) + (a.get("BLDG_VALUE") or 0)
    if value:
        fields["assessed_value"] = value
    parcel_id = a.get("TaxAcct")
    if parcel_id is not None:
        fields["parcel_id"] = str(parcel_id)
    return fields, is_confidential, is_unknown


# ── RealTDM (tax deed) lookup ────────────────────────────────────────────
_rtdm_cj = http.cookiejar.CookieJar()
_rtdm_op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_rtdm_cj))
_rtdm_session_init = False


def _rtdm_req(url, data=None, retries=3):
    global _rtdm_session_init
    if not _rtdm_session_init:
        _rtdm_op.open(urllib.request.Request(REALTDM_BASE + "/public/cases/list",
                                              headers={"User-Agent": UA}), timeout=30)
        _rtdm_session_init = True
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data.encode() if isinstance(data, str) else data)
            req.add_header("User-Agent", UA)
            if data:
                req.add_header("Content-Type", "application/x-www-form-urlencoded")
                req.add_header("Referer", REALTDM_BASE + "/public/cases/list")
            with _rtdm_op.open(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if attempt == retries - 1:
                print(f"  RealTDM request failed: {e}", file=sys.stderr)
                return None
            time.sleep(2 * (attempt + 1))


def realtdm_lookup_account(case_number):
    body = urllib.parse.urlencode({
        "filterPageNumber": 1, "filterFiltered": 1, "isPublic": 1,
        "sectionRouteCode": "", "filtercasestatus": "", "filterPartyName": "",
        "filterCaseNumber": case_number, "filterParcelNumber": "", "filterAppNumber": "",
        "filterCertNumber": "", "filterPropAddress": "",
        "filterSaleDateStart": "", "filterSaleDateStop": "",
        "filterBalanceType": "", "filterCasesPerPage": 100,
    })
    html = _rtdm_req(REALTDM_BASE + "/public/cases/list", data=body)
    if not html:
        return None
    for blk in re.split(r'class="content-box contain', html)[1:]:
        case = re.search(r"CASE #(\w+)", blk)
        if not case or case.group(1) != case_number:
            continue
        labels = dict(re.findall(
            r'data-label">([^<]+)</div>\s*<div class="data-value[^"]*">([^<]*)<', blk))
        acct = (labels.get("Parcel Number") or "").strip()
        return acct or None
    return None


# ── AcclaimWeb (foreclosure/civil) lookup ────────────────────────────────
_acclaim_cj = http.cookiejar.CookieJar()
_acclaim_op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_acclaim_cj))
_acclaim_session_init = False


def _acclaim_req(url, data=None, hdrs=None, retries=4):
    global _acclaim_session_init
    if not _acclaim_session_init:
        _acclaim_req_raw(ACCLAIM_BASE + "/AcclaimWeb/")
        _acclaim_req_raw(ACCLAIM_BASE + "/AcclaimWeb/search/Disclaimer", data="disclaimer=on",
                          hdrs={"Content-Type": "application/x-www-form-urlencoded",
                                "Referer": ACCLAIM_BASE + "/AcclaimWeb/"})
        _acclaim_session_init = True
    return _acclaim_req_raw(url, data, hdrs, retries)


def _acclaim_req_raw(url, data=None, hdrs=None, retries=4):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data.encode() if isinstance(data, str) else data)
            req.add_header("User-Agent", UA)
            for k, v in (hdrs or {}).items():
                req.add_header(k, v)
            with _acclaim_op.open(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if attempt == retries - 1:
                print(f"  AcclaimWeb request failed: {e}", file=sys.stderr)
                return None
            time.sleep(2.5 * (attempt + 1))


def acclaim_lookup_legal(case_number):
    today = dt.date.today()
    payload = urllib.parse.urlencode({
        "CaseNumber": case_number, "CaseNumberFilter": "0", "DocTypes": "all",
        "DocTypesDisplay-input": "All", "DocTypesDisplay": "", "DateRangeList": " ",
        "RecordDateFrom": "1/1/1981", "RecordDateTo": f"{today.month}/{today.day}/{today.year}",
    })
    h = {"Content-Type": "application/x-www-form-urlencoded", "X-Requested-With": "XMLHttpRequest",
         "Referer": ACCLAIM_BASE + "/AcclaimWeb/search/SearchTypeCaseNumber"}
    body = _acclaim_req(ACCLAIM_BASE + "/AcclaimWeb/search/SearchTypeCaseNumber?Length=6", data=payload, hdrs=h)
    if not body or "Error.htm" in body:
        return None
    gr = _acclaim_req(ACCLAIM_BASE + "/AcclaimWeb/search/GridResults", data="page=1&size=200", hdrs=h)
    if not gr:
        return None
    try:
        rows = json.loads(gr).get("data", [])
    except Exception:
        return None
    for r in rows:
        legal = r.get("DocLegalDescription") or ""
        m = LEGAL_RE_BLK.search(legal)
        if m:
            return ("blk", m.group(1), m.group(2), m.group(3).zfill(4), m.group(4).zfill(4))
    for r in rows:
        legal = r.get("DocLegalDescription") or ""
        m = LEGAL_RE_NOBLK.search(legal)
        if m:
            return ("noblk", m.group(1), None, m.group(2).zfill(4), m.group(3).zfill(4))
    return None


def gis_resolve_by_plat(lot, blk, pb, pg):
    if blk:
        where = f"PLAT_BOOK='{pb}' AND PLAT_PAGE='{pg}' AND BLOCK='{blk}' AND LOT='{lot}'"
    else:
        where = f"PLAT_BOOK='{pb}' AND PLAT_PAGE='{pg}' AND LOT='{lot}'"
    params = {"where": where,
              "outFields": "TaxAcct,PARCEL_ID,STREET_NUMBER,STREET_NAME,STREET_TYPE,CITY,ZIP_CODE,LAND_VALUE,BLDG_VALUE",
              "returnGeometry": "true", "outSR": "4326", "f": "json"}
    d = get(BASE_PARCEL + "?" + urllib.parse.urlencode(params))
    feats = d.get("features", [])
    if len(feats) != 1:
        return None
    f = feats[0]
    a = f["attributes"]
    ring = (f.get("geometry") or {}).get("rings", [[]])[0]
    lat = lon = None
    if ring:
        lon = sum(p[0] for p in ring) / len(ring)
        lat = sum(p[1] for p in ring) / len(ring)
    return a, lat, lon


def is_tax_deed_case(case_number):
    return case_number.isdigit()


def process_skeleton_row(row_id, case_number, verbose=True):
    """Returns (status, fields_dict_or_None, note)."""
    if is_tax_deed_case(case_number):
        acct = realtdm_lookup_account(case_number)
        if not acct:
            return "BLOCKED", None, "no RealTDM case match / no Parcel Number on card"
        result = base_parcel_lookup(acct)
        if result is None:
            return "BLOCKED", None, f"TaxAcct={acct} (RealTDM) -> 0 or >1 GIS features"
        a, lat, lon = result
        fields, is_conf, is_unk = build_fields_from_gis(a, lat, lon)
        if not fields.get("property_address"):
            reason = "CONFIDENTIAL" if is_conf else ("STREET_NAME=UNKNOWN/blank" if is_unk else "no address fields")
            return "BLOCKED", None, f"TaxAcct={acct} (RealTDM) -> address guard: {reason}"
        return "RESOLVED", fields, f"TaxAcct={acct} via RealTDM+GIS"
    else:
        legal = acclaim_lookup_legal(case_number)
        if not legal:
            return "BLOCKED", None, "no AcclaimWeb case match / no parseable legal description"
        _, lot, blk, pb, pg = legal
        result = gis_resolve_by_plat(lot, blk, pb, pg)
        if result is None:
            return "BLOCKED", None, f"legal LT{lot} BLK{blk} PB{pb} PG{pg} -> 0 or >1 GIS features"
        a, lat, lon = result
        fields, is_conf, is_unk = build_fields_from_gis(a, lat, lon)
        if not fields.get("property_address"):
            reason = "CONFIDENTIAL" if is_conf else ("STREET_NAME=UNKNOWN/blank" if is_unk else "no address fields")
            return "BLOCKED", None, f"TaxAcct={a.get('TaxAcct')} (AcclaimWeb) -> address guard: {reason}"
        return "RESOLVED", fields, f"TaxAcct={a.get('TaxAcct')} via AcclaimWeb+GIS"


def process_value_missing_row(row_id, case_number):
    row = sb_get(f"multi_county_auctions?select=parcel_id&id=eq.{row_id}")
    if not row or not row[0].get("parcel_id"):
        return "BLOCKED", None, "no parcel_id on row (unexpected)"
    tax_acct = row[0]["parcel_id"]
    result = base_parcel_lookup(tax_acct)
    if result is None:
        return "BLOCKED", None, f"TaxAcct={tax_acct} -> 0 or >1 GIS features"
    a, lat, lon = result
    value = (a.get("LAND_VALUE") or 0) + (a.get("BLDG_VALUE") or 0)
    if not value:
        return "BLOCKED", None, f"TaxAcct={tax_acct} -> GIS LAND_VALUE+BLDG_VALUE also 0/null"
    return "RESOLVED", {"assessed_value": value}, f"TaxAcct={tax_acct} LAND_VALUE={a.get('LAND_VALUE')} BLDG_VALUE={a.get('BLDG_VALUE')}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Write resolved rows live (default: dry-run)")
    ap.add_argument("--limit", type=int, default=None, help="Cap number of skeleton rows processed (testing)")
    args = ap.parse_args()

    resolved = []
    blocked = []

    print(f"=== Lever 1: VALUE_MISSING ({len(VALUE_MISSING_ROWS)} rows) ===")
    for row_id, case_number in VALUE_MISSING_ROWS:
        status, fields, note = process_value_missing_row(row_id, case_number)
        print(f"  {case_number} ({row_id[:8]}): {status} -- {note}")
        if status == "RESOLVED":
            resolved.append((row_id, case_number, fields, note))
        else:
            blocked.append((row_id, case_number, note))

    skeleton = SKELETON_ROWS[: args.limit] if args.limit else SKELETON_ROWS
    print(f"\n=== Lever 2: SKELETON ({len(skeleton)} rows) ===")
    for i, (row_id, case_number) in enumerate(skeleton, 1):
        status, fields, note = process_skeleton_row(row_id, case_number)
        print(f"  [{i}/{len(skeleton)}] {case_number} ({row_id[:8]}): {status} -- {note}")
        if status == "RESOLVED":
            resolved.append((row_id, case_number, fields, note))
        else:
            blocked.append((row_id, case_number, note))
        time.sleep(1.2)  # polite throttle against shared county production sites

    print(f"\n=== SUMMARY: resolved={len(resolved)} blocked={len(blocked)} total={len(VALUE_MISSING_ROWS) + len(skeleton)} ===")

    if args.apply:
        applied = 0
        for row_id, case_number, fields, note in resolved:
            status = sb_patch(row_id, fields)
            print(f"  APPLIED PATCH {case_number} ({row_id[:8]}) fields={list(fields.keys())} status={status}")
            if status in (200, 201, 204):
                applied += 1
            else:
                print(f"  *** WRITE FAILED for resolved row {row_id} -- status={status} ***", file=sys.stderr)
        print(f"\nTOTAL applied: {applied}/{len(resolved)}")
        if applied != len(resolved):
            print("*** FAIL-LOUD: some resolved rows did not write successfully -- see stderr above ***", file=sys.stderr)
    else:
        print("\nDRY-RUN: re-run with --apply to PATCH the resolved rows into multi_county_auctions.")

    print("\n=== BLOCKED (left untouched, residual/structural) ===")
    for row_id, case_number, note in blocked:
        print(f"  {case_number} ({row_id[:8]}): {note}")


if __name__ == "__main__":
    main()
