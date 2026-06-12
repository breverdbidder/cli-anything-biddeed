-- Migration: SHARD-7 Gold Standard Setup
-- Date: 2026-06-12
-- Purpose: Ensure all necessary tables and functions exist for SHARD-7 county improvements

-- Create extension if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Ensure fl_counties table has SHARD-7 counties
INSERT INTO public.fl_counties (co_no, name, slug, state, total_parcels, created_at, updated_at)
VALUES 
    (29, 'Hillsborough', 'hillsborough', 'FL', 0, now(), now()),
    (61, 'St. Lucie', 'st_lucie', 'FL', 0, now(), now()),
    (35, 'Hernando', 'hernando', 'FL', 0, now(), now()),
    (18, 'Columbia', 'columbia', 'FL', 0, now(), now()),
    (41, 'Madison', 'madison', 'FL', 0, now(), now())
ON CONFLICT (co_no) DO UPDATE SET
    updated_at = now();

-- Ensure county_conquest_status table exists with SHARD-7 entries
CREATE TABLE IF NOT EXISTS public.county_conquest_status (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    co_no integer REFERENCES public.fl_counties(co_no),
    county text,
    parcels_ingested integer DEFAULT 0,
    parcels_with_zone integer DEFAULT 0,
    parcels_from_usecode integer DEFAULT 0,
    coverage_pct numeric(5,2) DEFAULT 0.0,
    status text DEFAULT 'pending',
    jurisdictions_total integer DEFAULT 0,
    jurisdictions_done integer DEFAULT 0,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    UNIQUE(co_no)
);

-- Initialize conquest status for SHARD-7 counties
INSERT INTO public.county_conquest_status (co_no, county, status, notes, created_at, updated_at)
VALUES 
    (29, 'hillsborough', 'in_progress', 'SHARD-7 target county', now(), now()),
    (61, 'st_lucie', 'in_progress', 'SHARD-7 target county', now(), now()),
    (35, 'hernando', 'in_progress', 'SHARD-7 target county', now(), now()),
    (18, 'columbia', 'pending', 'SHARD-7 foundational county', now(), now()),
    (41, 'madison', 'pending', 'SHARD-7 foundational county', now(), now())
ON CONFLICT (co_no) DO UPDATE SET
    updated_at = now(),
    notes = COALESCE(county_conquest_status.notes, EXCLUDED.notes);

-- Ensure verified outcomes tables exist
CREATE TABLE IF NOT EXISTS public.tax_deed_outcomes (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    case_number text NOT NULL,
    county_slug text NOT NULL,
    outcome_type text,
    winning_bid numeric(12,2),
    sale_date date,
    data_source text NOT NULL,
    verified_at timestamp with time zone DEFAULT now(),
    verification_status text DEFAULT 'pending',
    raw_data jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    UNIQUE(case_number, data_source)
);

CREATE TABLE IF NOT EXISTS public.foreclosure_outcomes (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    case_number text NOT NULL,
    county_slug text NOT NULL,
    outcome_type text,
    winning_bid numeric(12,2),
    sale_date date,
    data_source text NOT NULL,
    verified_at timestamp with time zone DEFAULT now(),
    verification_status text DEFAULT 'pending',
    raw_data jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    UNIQUE(case_number, data_source)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_county ON public.tax_deed_outcomes(county_slug);
CREATE INDEX IF NOT EXISTS idx_tax_deed_outcomes_case ON public.tax_deed_outcomes(case_number);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_county ON public.foreclosure_outcomes(county_slug);
CREATE INDEX IF NOT EXISTS idx_foreclosure_outcomes_case ON public.foreclosure_outcomes(case_number);

-- Ensure bid_decisions table exists for Letter J improvements
CREATE TABLE IF NOT EXISTS public.bid_decisions (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    case_number text NOT NULL,
    county text NOT NULL,
    parcel_id text,
    arv_estimate numeric(12,2),
    max_bid numeric(12,2),
    ml_score numeric(5,4),
    triangle_factors jsonb,
    two_arm_cma jsonb,
    deal_complete boolean DEFAULT false,
    pipeline_status text DEFAULT 'initialized',
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    UNIQUE(case_number)
);

CREATE INDEX IF NOT EXISTS idx_bid_decisions_county ON public.bid_decisions(county);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_parcel ON public.bid_decisions(parcel_id);

-- Ensure gold_standard_county_status table exists
CREATE TABLE IF NOT EXISTS public.gold_standard_county_status (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    county text NOT NULL,
    letter_a_pass boolean DEFAULT false,
    letter_b_pass boolean DEFAULT false,
    letter_c_pass boolean DEFAULT false,
    letter_d_pass boolean DEFAULT false,
    letter_e_pass boolean DEFAULT false,
    letter_f_pass boolean DEFAULT false,
    letter_g_pass boolean DEFAULT false,
    letter_h_pass boolean DEFAULT false,
    letter_i_pass boolean DEFAULT false,
    letter_j_pass boolean DEFAULT false,
    total_passes integer DEFAULT 0,
    last_evaluated timestamp with time zone DEFAULT now(),
    evaluation_data jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    UNIQUE(county)
);

-- Initialize gold standard status for SHARD-7 counties
INSERT INTO public.gold_standard_county_status (county, created_at, updated_at)
VALUES 
    ('hillsborough', now(), now()),
    ('st_lucie', now(), now()),
    ('hernando', now(), now()),
    ('columbia', now(), now()),
    ('madison', now(), now())
ON CONFLICT (county) DO UPDATE SET updated_at = now();

-- Create function to promote tier1 sold amounts (Letter F improvement)
CREATE OR REPLACE FUNCTION public.promote_tier1_from_outcomes()
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    promoted_count integer := 0;
BEGIN
    -- Update multi_county_auctions with winning_bid from verified outcomes
    UPDATE public.multi_county_auctions mca
    SET 
        winning_bid = COALESCE(tdo.winning_bid, fo.winning_bid),
        tier1_verified = true,
        updated_at = now()
    FROM (
        SELECT case_number, winning_bid
        FROM public.tax_deed_outcomes
        WHERE winning_bid IS NOT NULL
        UNION ALL
        SELECT case_number, winning_bid  
        FROM public.foreclosure_outcomes
        WHERE winning_bid IS NOT NULL
    ) outcomes(case_number, winning_bid)
    LEFT JOIN public.tax_deed_outcomes tdo ON outcomes.case_number = tdo.case_number
    LEFT JOIN public.foreclosure_outcomes fo ON outcomes.case_number = fo.case_number
    WHERE mca.case_number = outcomes.case_number
      AND mca.winning_bid IS NULL
      AND outcomes.winning_bid IS NOT NULL;
      
    GET DIAGNOSTICS promoted_count = ROW_COUNT;
    
    RETURN promoted_count;
END;
$$;

-- Comment the migration
COMMENT ON TABLE public.county_conquest_status IS 'SHARD-7 Gold Standard migration: County ingestion and conquest tracking';
COMMENT ON TABLE public.tax_deed_outcomes IS 'SHARD-7 Gold Standard migration: Independent tax deed outcome verification';
COMMENT ON TABLE public.foreclosure_outcomes IS 'SHARD-7 Gold Standard migration: Independent foreclosure outcome verification';
COMMENT ON TABLE public.bid_decisions IS 'SHARD-7 Gold Standard migration: Shapira Formula deal thesis pipeline';
COMMENT ON TABLE public.gold_standard_county_status IS 'SHARD-7 Gold Standard migration: Letter A-J evaluation tracking';
COMMENT ON FUNCTION public.promote_tier1_from_outcomes() IS 'SHARD-7 Gold Standard migration: Letter F tier1 sold amount promotion';

-- Log migration completion
INSERT INTO public.migration_log (migration_name, applied_at, notes)
VALUES ('20260612_shard7_gold_standard_setup', now(), 'SHARD-7 counties initialized for autonomous gold standard improvements')
ON CONFLICT DO NOTHING;