#!/usr/bin/env python3
"""SHARD-14, dispatch 121fa7c3-6131-474f-b6c8-928efe26d2f5, county=alachua.

Diagnosis-only script (no fabricated writes). Investigates the 7 rows in
multi_county_auctions (county=alachua) missing parcel_id, which blocks both
E (parcel_linked, 40/47=85.1%, need >=45/47=95%) and part of I (card_complete,
33/47=70.2%, need >=45/47=95%).

FINDINGS (all VERIFIED live this session):

1. All 7 missing-parcel_id case numbers were re-harvested live via the proven
   AJAX RealForeclose pattern (scripts/shard2_run2450_ajax_realforeclose_harvest.py)
   against alachua.realforeclose.com for their exact auction dates. In every
   case the site's own "Parcel ID" anchor decodes to the literal placeholder
   text "Property Appraiser" (or "MULTIPLE PARCEL" for 01 2025 CA 003287) --
   RealForeclose itself does not carry a real parcel number for these specific
   listings. This is not a parser bug (is_real_parcel_id() correctly rejects
   the placeholder); the source data is genuinely absent.

2. The qpublic.schneidercorp.com link embedded in the same anchor (AppID=1081,
   LayerID=26490, PageTypeID=4, PageID=10770, Q=320373606, KeyValue=) is
   IDENTICAL/boilerplate across all 7 cases (same Q= value every time) -- it
   is a static template link, not a per-parcel key. It does not encode a real
   parcel ID we can extract.

3. qpublic.schneidercorp.com (Alachua County Property Appraiser's actual
   parcel search) returns HTTP 403 from Cloudflare's bot-protection layer on
   every request pattern tried (direct docid link, owner-search link) --
   confirmed live, not a guess.

4. The Clerk's official records portal (isol.alachuaclerk.org) redirects
   (301) any direct docid link to a JS-required BrowserTest.aspx localization
   page -- confirmed live -- so no case-file property address is extractable
   without a JS-capable browser, which is out of scope/budget this session.

5. Discovered (and wrote to fl_counties, a metadata-only field with no scoring
   impact) Alachua County Property Appraiser's public ArcGIS FeatureServer:
   https://services.arcgis.com/cNo3jpluyt69V8Ek/arcgis/rest/services/PublicParcel/FeatureServer/0
   Fields: OBJECTID, Name, Prop_ID, FULLADDR, Owner_Mail_*, geometry. This
   layer supports address/owner lookup IF we had a real address or owner name
   for the 7 target cases -- we do not (their property_address is either NULL
   or the literal placeholder "ALACHUA COUNTY FL" with county-centroid lat/lon
   29.6516/-82.3248, written by an earlier unrelated fallback pass, confirmed
   NOT a real street address).

CONCLUSION: no evidence-backed parcel_id, address, or geo value can be
written for these 7 rows this session without fabrication, which is
explicitly forbidden by the repo's guardrails (rule #5: never fabricate a
parcel_id/address/geo/case match). Reported as residual gap.

I SECONDARY FINDING (independent of the above): of the 40 alachua rows that
DO have parcel_id, all 40 already have property_address + lat/lon +
assessed_value filled (from prior shard runs) -- so E/I's address/geo/value
sub-checks are not the blocker for those 40. The remaining I shortfall
(33/40 card_complete among parcel-linked rows) is caused by 7 of those 40
parcel_ids having NO row in parcel_zones / v_zoning_gold_standard_card for
alachua (only 38 alachua parcels total have zoning loaded, confirmed via
direct REST query). This is a zoning-coverage gap (G-adjacent), not writable
via PostgREST without fabricating zoning district/standards data for those
specific parcels -- also out of scope and forbidden without a real source.

No multi_county_auctions rows were written by this script. The only write
made this session was fl_counties.appraiser_url / gis_endpoint (previously
NULL, now populated with the two real URLs discovered above) -- metadata
only, does not affect any pencil_dod_evaluate_county letter.
"""
print(__doc__)
