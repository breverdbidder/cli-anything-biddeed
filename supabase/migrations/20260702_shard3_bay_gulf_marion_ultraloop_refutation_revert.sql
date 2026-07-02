-- SHARD-3 (2nd pass): revert ULTRALOOP-refuted false positives from the
-- bay/gulf/marion/seminole/lee C/D parity migration
-- (20260702_shard3_bay_gulf_marion_seminole_lee_cd_parity.sql).
-- dispatch_id: 5bd50375-d8f8-4a8e-ae84-e791b393360f
-- Session: architect-20260702T160000
--
-- Per the ULTRALOOP protocol, every claim of a moved letter got an independent
-- adversarial refuter (Workflow tool, 5 parallel agents, one per county). Results:
--   bay      SURVIVED=false  (2 of 9 stamped rows matched sentinel-valued
--                              parcel_id='Property Appraiser'/'MULTIPLE PARCELS'
--                              source rows via the case_number path)
--   gulf     SURVIVED=false  (all 3 stamped rows matched against
--                              realforeclose_aids rows with parcel_id='Property
--                              Appraiser' and NULL address -- no independent
--                              corroboration beyond case_number equality)
--   marion   SURVIVED=false  (2 sentinel-parcel_id rows + 1 pre-existing
--                              county-casing duplicate ('marion' vs 'Marion')
--                              double-stamped for the same real-world case
--                              422024CA002455CAAXMX, inflating the numerator)
--   seminole SURVIVED=true   (21 genuine matches, zero sentinel/duplicate/leakage)
--   lee      SURVIVED=true   (32 genuine matches; case_number-path matches were
--                              independently corroborated by matching
--                              judgment_amount + auction_date across both tables)
--
-- Per protocol: "Refuted = false positive: log it, do not count it." This
-- migration reverts exactly the refuted rows (parity_status/parity_source back
-- to NULL) -- it does NOT touch seminole or lee's genuine matches, and does not
-- delete any auction rows (the underlying listings are real; only the
-- unverified parity stamp is removed, same remediation pattern as the marion
-- SYN- fabrication cleanup earlier today).
--
-- gulf note: after this revert gulf's C/D matched_clean/matched_any both return
-- to their pre-migration values (0 genuine cross-source matches survive) --
-- gulf's tax-deed AND foreclosure lanes both need a real scrape run against
-- realforeclose_aids/realtaxdeed before C/D can move; the 4 of 5
-- realforeclose_aids rows for gulf are themselves sentinel/placeholder scrapes
-- (parcel_id='Property Appraiser', address=NULL), a source-data quality gap,
-- not a matching-logic gap.
--
-- marion note: case_number 422024CA002455CAAXMX is the SAME ambiguous
-- county-casing duplicate pair shard7 already flagged today as unresolved
-- (needs county clerk docket lookup, could be legitimate reschedule history --
-- see 20260702_shard7_marion_syn_fabrication_cleanup.sql). This migration keeps
-- the tier1_authoritative=true row (id a2aabfe2) as matched_clean and reverts
-- only the non-authoritative duplicate (id a8fddffb) so the case counts once,
-- not twice, toward C/D -- it does not attempt to resolve which row is the
-- "real" one.

-- bay: 2 sentinel-parcel_id false positives
UPDATE public.multi_county_auctions
SET parity_status = NULL, parity_source = NULL, updated_at = now()
WHERE lower(county) = 'bay'
  AND case_number IN ('23001239CA', '25000637CA')
  AND parity_source = 'tier1_realforeclose_bay';

-- gulf: all 3 stamped rows matched against sentinel-valued source data
UPDATE public.multi_county_auctions
SET parity_status = NULL, parity_source = NULL, updated_at = now()
WHERE lower(county) = 'gulf'
  AND case_number IN ('232024CA000072CAAXMX', '232019CA000060CAAXMX', '232024CC000157CCAXMX')
  AND parity_source = 'tier1_realforeclose_gulf';

-- marion: 2 sentinel-parcel_id false positives
UPDATE public.multi_county_auctions
SET parity_status = NULL, parity_source = NULL, updated_at = now()
WHERE id IN ('6c49c160-c539-4096-9671-ded57a8282a1', '4a0e831b-c702-4c00-8d85-d7db00ab12e7')
  AND parity_source = 'tier1_realforeclose_marion';

-- marion: revert the non-authoritative half of the county-casing duplicate
-- pair for case 422024CA002455CAAXMX (keep id a2aabfe2, tier1_authoritative=true)
UPDATE public.multi_county_auctions
SET parity_status = NULL, parity_source = NULL, updated_at = now()
WHERE id = 'a8fddffb-7ea7-4652-abe5-3f14b26267fc'
  AND parity_source = 'tier1_realforeclose_marion';

-- ── VERIFICATION QUERIES (run after migration) ─────────────────────────────────────
-- SELECT public.pencil_dod_evaluate_county('bay');
-- SELECT public.pencil_dod_evaluate_county('gulf');
-- SELECT public.pencil_dod_evaluate_county('marion');
