#!/usr/bin/env python3
"""SHARD-6, county=alachua, letter E (parcel linkage) -- Playwright JS-rendered
investigation of the 12 rows in multi_county_auctions with parcel_id IS NULL.

Prior sessions (scripts/shard14_run121fa7c3_alachua_e_i_diagnosis.py,
scripts/shard10_run3645_alachua_e_parcel_backfill.py,
scripts/shard10_run_alachua_docid_harvest.py) established via raw HTTP/AJAX:
  - alachua.realforeclose.com's own AJAX calendar 'Parcel ID' field for these
    12 cases decodes to a placeholder or is genuinely absent.
  - isol.alachuaclerk.org docid links embedded in the AJAX Case# column are
    EMPTY (docid=&ms=0) for 11 of the 12 (the 12th, 003287, has docid=3683369
    but was previously confirmed "MULTIPLE PARCEL" -- unusable without
    fabricating which lot).
  - qpublic.schneidercorp.com returns HTTP 403 (Cloudflare) on raw HTTP.
  - isol.alachuaclerk.org direct docid links 301-redirect to a JS-required
    BrowserTest.aspx page on raw HTTP.

THIS SCRIPT tries the one thing not yet tried: a real headless browser
(Playwright/Chromium, same pattern as .github/scripts/scrape_realauction_county.py)
against:
  (a) the RealForeclose per-case DETAILS page for each AID (JS-rendered DOM,
      not just the AJAX calendar snippet) --
      https://alachua.realforeclose.com/index.cfm?zaction=auction&zmethod=details&AID=<aid>
  (b) isol.alachuaclerk.org SearchDetail.aspx?docid=3683369 for case 003287
      (the only case with a non-empty docid) via a JS-capable browser, in case
      the BrowserTest.aspx JS-redirect that blocked raw HTTP resolves cleanly
      in a real browser session.
  (c) qpublic.schneidercorp.com direct case/owner search via a real browser
      session, in case Cloudflare's bot-check passes for a genuine browser.

Read-only reconnaissance. Prints one JSON object per case with whatever real
text was found in the rendered DOM. NO DB WRITES from this script.
"""
import json
import re
import sys

from playwright.sync_api import sync_playwright

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')

# AIDs harvested live this session via scripts/shard10_run_alachua_docid_harvest.py
# against alachua.realforeclose.com's AJAX calendar for each case's own
# auction_date (see migration 20260725_gold_standard_shard6_alachua_e_parcel_linkage.sql
# for the full evidence chain / findings from running this script).
CASES = {
    "01 2025 CA 003287": {"aid": "1497418", "auction_date": "2026-05-04", "docid": "3683369"},
    "01 2025 CA 001928": {"aid": "1491316", "auction_date": "2026-05-14", "docid": None},
    "01 2025 CA 002643": {"aid": "1503874", "auction_date": "2026-07-23", "docid": None},
    "01 2025 CA 001634": {"aid": "1506211", "auction_date": "2026-08-11", "docid": None},
    "01 2025 CA 003629": {"aid": "1509513", "auction_date": "2026-08-18", "docid": None},
    "01 2025 CC 001552": {"aid": "1509516", "auction_date": "2026-08-18", "docid": None},
    "01 2025 CA 003919": {"aid": "1509514", "auction_date": "2026-08-18", "docid": None},
    "01 2023 CA 004261": {"aid": "1510233", "auction_date": "2026-08-18", "docid": None},
    "01 2025 CC 001127": {"aid": "1509515", "auction_date": "2026-08-27", "docid": None},
    "01 2025 CC 007164": {"aid": "1509517", "auction_date": "2026-08-27", "docid": None},
    "01 2026 CA 000211": {"aid": "1509889", "auction_date": "2026-08-27", "docid": None},
    "01 2024 CC 005935": {"aid": "1512594", "auction_date": "2026-09-01", "docid": None},
}

DETAILS_URL_TMPL = 'https://alachua.realforeclose.com/index.cfm?zaction=auction&zmethod=details&AID={aid}'


def strip_ws(t):
    return re.sub(r'\s+', ' ', t or '').strip()


def investigate_details_page(browser, case_number, aid):
    url = DETAILS_URL_TMPL.format(aid=aid)
    page = browser.new_page(user_agent=UA)
    out = {'case_number': case_number, 'aid': aid, 'url': url}
    try:
        resp = page.goto(url, timeout=45000)
        out['http_status'] = resp.status if resp else None
        page.wait_for_timeout(4000)
        body_text = strip_ws(page.inner_text('body'))
        out['body_text_len'] = len(body_text)
        # Look for parcel id / legal description / owner / defendant patterns.
        for label in ['Parcel ID', 'Parcel Number', 'Legal Description',
                      'Defendant', 'Property Address', 'Assessed Value',
                      'Final Judgment Amount']:
            m = re.search(re.escape(label) + r'\s*:?\s*([^\n]{0,120})', body_text, re.IGNORECASE)
            out[label.lower().replace(' ', '_')] = strip_ws(m.group(1)) if m else None
        # Grab any qpublic / appraiser link the rendered DOM adds.
        links = page.eval_on_selector_all('a[href]', 'els => els.map(e => e.href)')
        qpublic_links = [l for l in links if 'qpublic' in l.lower() or 'acpafl' in l.lower()]
        out['qpublic_links'] = qpublic_links
        # Save a body snippet for manual audit.
        out['body_snippet'] = body_text[:1500]
    except Exception as e:
        out['error'] = f'{type(e).__name__}: {e}'
    finally:
        page.close()
    return out


def investigate_clerk_docid(browser, docid):
    url = f'http://isol.alachuaclerk.org/RealEstate/SearchDetail.aspx?docid={docid}&ms=0'
    page = browser.new_page(user_agent=UA)
    out = {'docid': docid, 'url': url}
    try:
        resp = page.goto(url, timeout=45000)
        out['http_status'] = resp.status if resp else None
        page.wait_for_timeout(5000)
        out['final_url'] = page.url
        body_text = strip_ws(page.inner_text('body'))
        out['body_text_len'] = len(body_text)
        out['body_snippet'] = body_text[:2000]
    except Exception as e:
        out['error'] = f'{type(e).__name__}: {e}'
    finally:
        page.close()
    return out


def investigate_qpublic(browser, case_number):
    # Alachua County Property Appraiser via Schneider Corp qpublic search UI.
    url = 'https://qpublic.schneidercorp.com/Application.aspx?AppID=1081&LayerID=26490&PageTypeID=2&PageID=10770'
    page = browser.new_page(user_agent=UA)
    out = {'case_number': case_number, 'url': url}
    try:
        resp = page.goto(url, timeout=45000)
        out['http_status'] = resp.status if resp else None
        page.wait_for_timeout(4000)
        out['final_url'] = page.url
        title = page.title()
        out['title'] = title
        body_text = strip_ws(page.inner_text('body'))
        out['body_text_len'] = len(body_text)
        out['body_snippet'] = body_text[:800]
        out['cloudflare_blocked'] = 'attention required' in body_text.lower() or 'cloudflare' in body_text.lower() or (resp and resp.status == 403)
    except Exception as e:
        out['error'] = f'{type(e).__name__}: {e}'
    finally:
        page.close()
    return out


def main():
    results = {'details_pages': [], 'clerk_docid': None, 'qpublic': None}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox'])
        try:
            for case_number, meta in CASES.items():
                r = investigate_details_page(browser, case_number, meta['aid'])
                results['details_pages'].append(r)
                print(f"=== {case_number} (AID {meta['aid']}) ===", file=sys.stderr)
                print(json.dumps(r, indent=2)[:2000], file=sys.stderr)

            # Test qpublic reachability via real browser once.
            results['qpublic'] = investigate_qpublic(browser, 'PROBE')
            print("=== QPUBLIC PROBE ===", file=sys.stderr)
            print(json.dumps(results['qpublic'], indent=2), file=sys.stderr)

            # Test the one non-empty docid (003287) via real browser.
            results['clerk_docid'] = investigate_clerk_docid(browser, '3683369')
            print("=== CLERK DOCID 3683369 (case 01 2025 CA 003287) ===", file=sys.stderr)
            print(json.dumps(results['clerk_docid'], indent=2), file=sys.stderr)
        finally:
            browser.close()

    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
