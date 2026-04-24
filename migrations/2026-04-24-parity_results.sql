-- Parity results table — one row per scraper run
CREATE TABLE IF NOT EXISTS parity_results (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_date                date NOT NULL,
    run_timestamp           timestamptz NOT NULL DEFAULT now(),
    total_counties          int,
    parsed_ok_counties      int,
    probe_only_counties     int,
    error_counties          int,
    total_source_cases      int,
    total_in_both           int,
    total_only_source       int,
    total_rows_inserted     int,
    per_county_results      jsonb,
    created_at              timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_parity_run_date ON parity_results(run_date DESC);
CREATE INDEX IF NOT EXISTS idx_parity_counties ON parity_results USING gin(per_county_results);

-- Convenience view: latest run per day with county breakdown
CREATE OR REPLACE VIEW parity_latest AS
SELECT 
    run_date,
    run_timestamp,
    parsed_ok_counties || '/' || total_counties AS parsed_ratio,
    total_source_cases,
    total_rows_inserted,
    total_only_source AS gaps_found,
    per_county_results
FROM parity_results
ORDER BY run_timestamp DESC
LIMIT 30;
