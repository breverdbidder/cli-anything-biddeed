-- Property Appraiser Cross-Verification infra (multi-county)
-- Parallel to fl_court_systems / realauction_subdomains: one config row per
-- county property appraiser platform, driving a per-platform Playwright
-- scraper set (not per-county -- platforms repeat across counties).
--
-- Reuses public.parity_audit (existing BidDeed/PropertyOnion litmus table)
-- for verification results. That table's biddeed_value/competitor_value
-- columns are numeric-only, which fits the just_value/assessed_value delta
-- checks but not the parcel_id/address/owner_of_record text comparisons
-- this brief also requires -- so two nullable text columns are added
-- (additive, non-destructive, existing rows unaffected).

CREATE TABLE IF NOT EXISTS public.fl_property_appraiser_configs (
    county_slug text PRIMARY KEY,
    appraiser_url text NOT NULL,
    search_method text NOT NULL, -- parcel_id | strap | address | parcel_id_get
    platform text NOT NULL,      -- wordpress_spa | aspnet_webforms | aspnet_webmethods_hybrid | aspnet_mvc_direct_get | aspnet_devexpress | qpublic_schneider
    form_field_selectors jsonb,
    needs_cert_bypass boolean NOT NULL DEFAULT false,
    needs_js boolean NOT NULL DEFAULT true,
    blocked_by_waf boolean NOT NULL DEFAULT false,
    known_issues text,
    added_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.fl_property_appraiser_configs IS
    'Per-platform config for county property appraiser Playwright scrapers, driving Winner Data FF parcel cross-verification. Dispatch: Property Appraiser Cross-Verification (2026-08-24).';

ALTER TABLE public.parity_audit
    ADD COLUMN IF NOT EXISTS ff_value text,
    ADD COLUMN IF NOT EXISTS appraiser_value text,
    ADD COLUMN IF NOT EXISTS verdict_note text;

COMMENT ON COLUMN public.parity_audit.ff_value IS
    'Text-form value from our Winner Data fact-finder for non-numeric field comparisons (parcel_id/address/owner_of_record). Numeric just_value/assessed_value deltas still use biddeed_value/competitor_value.';
COMMENT ON COLUMN public.parity_audit.appraiser_value IS
    'Text-form value observed live on the county property appraiser site for the same field_name.';
COMMENT ON COLUMN public.parity_audit.verdict_note IS
    'Free-text explanation for verdict (e.g. why a mismatch is flagged non-blocking). verdict itself stays a short enum value per the check constraint.';

-- Existing check constraint only allowed the BidDeed/PropertyOnion competitor-
-- value vocabulary (parity/biddeed_superior/po_superior/biddeed_only/po_only).
-- Extend additively (existing rows/values unaffected) with the vocabulary this
-- brief's blocking/informational/flag classification needs.
ALTER TABLE public.parity_audit DROP CONSTRAINT IF EXISTS parity_audit_verdict_check;
ALTER TABLE public.parity_audit ADD CONSTRAINT parity_audit_verdict_check
    CHECK (verdict = ANY (ARRAY[
        'parity', 'biddeed_superior', 'po_superior', 'biddeed_only', 'po_only',
        'pass', 'fail', 'flag', 'informational', 'unverified'
    ]));
