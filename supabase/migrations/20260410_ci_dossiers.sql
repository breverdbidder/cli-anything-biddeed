-- CI Dossier Infrastructure — SUMMIT #424
-- 8 tables + indexes for competitive intelligence dossier system

-- 1. ci_dossiers (primary)
create table ci_dossiers (
  id uuid primary key default gen_random_uuid(),
  competitor_slug text unique not null,
  display_name text not null,
  domain text not null,
  category text,
  threat_level text check (threat_level in ('low','medium','high','critical')),
  threat_rationale text,
  moat_type text[],
  moat_description text,
  moat_strength smallint check (moat_strength between 1 and 10),
  moat_replicable_in text,
  hero_copy text,
  hero_evidence_path text,
  pricing_tiers jsonb,
  patent_claim_impacts jsonb,
  prior_art_risk_flag boolean default false,
  prior_art_notes text,
  pre_recon_assumption text,
  pre_recon_corrections text,
  dossier_status text default 'pending',
  recon_started_at timestamptz,
  recon_completed_at timestamptz,
  total_urls_discovered integer,
  total_urls_scraped integer,
  total_interact_sessions integer,
  firecrawl_credits_used integer,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- 2. ci_dossier_sitemaps
create table ci_dossier_sitemaps (
  id uuid primary key default gen_random_uuid(),
  competitor_slug text references ci_dossiers(competitor_slug),
  total_urls_discovered integer not null,
  urls_from_xml_sitemap integer default 0,
  urls_from_robots_txt integer default 0,
  urls_from_firecrawl_map integer default 0,
  urls_from_firecrawl_crawl integer default 0,
  hidden_pages_count integer default 0,
  disallowed_pages_count integer default 0,
  classification_breakdown jsonb,
  sitemap_tree_mermaid_path text,
  sitemap_graph_svg_path text,
  sitemap_table_csv_path text,
  sitemap_coverage_report_md_path text,
  robots_txt_content text,
  xml_sitemap_urls text[],
  discovered_at timestamptz default now(),
  completed_at timestamptz
);

-- 3. ci_dossier_urls
create table ci_dossier_urls (
  id uuid primary key default gen_random_uuid(),
  competitor_slug text references ci_dossiers(competitor_slug),
  url text not null,
  url_type text,
  http_status integer,
  markdown_content text,
  structured_extract jsonb,
  screenshot_desktop_path text,
  screenshot_mobile_path text,
  screenshot_desktop_captured_at timestamptz,
  screenshot_mobile_captured_at timestamptz,
  screenshot_capture_tool text,
  viewport_desktop text default '1920x1080',
  viewport_mobile text default '375x812',
  pdf_path text,
  scrape_method text,
  source_origins text[],
  lastmod_from_sitemap timestamptz,
  priority_from_sitemap numeric(2,1),
  depth_from_homepage integer,
  internal_inbound_links integer,
  is_hidden boolean default false,
  is_disallowed boolean default false,
  recon_priority text check (recon_priority in ('high','medium','low')),
  scraped_at timestamptz default now()
);

-- 4. ci_dossier_features
create table ci_dossier_features (
  id uuid primary key default gen_random_uuid(),
  competitor_slug text references ci_dossiers(competitor_slug),
  feature_name text not null,
  feature_description text,
  feature_category text,
  our_equivalent text,
  our_patent_claim integer[],
  winner text check (winner in ('them','us','tie')),
  evidence_url text,
  evidence_path text,
  created_at timestamptz default now()
);

-- 5. ci_dossier_feature_screenshots
create table ci_dossier_feature_screenshots (
  id uuid primary key default gen_random_uuid(),
  competitor_slug text references ci_dossiers(competitor_slug),
  feature_id uuid references ci_dossier_features(id),
  step_number integer not null,
  step_description text,
  screenshot_desktop_path text not null,
  screenshot_mobile_path text,
  captured_via text,
  captured_at timestamptz default now()
);

-- 6. ci_dossier_interrogations
create table ci_dossier_interrogations (
  id uuid primary key default gen_random_uuid(),
  competitor_slug text references ci_dossiers(competitor_slug),
  question text not null,
  response text,
  screenshot_path text,
  asked_at timestamptz default now()
);

-- 7. ci_dossier_api_endpoints
create table ci_dossier_api_endpoints (
  id uuid primary key default gen_random_uuid(),
  competitor_slug text references ci_dossiers(competitor_slug),
  endpoint_url text not null,
  method text,
  path_pattern text,
  discovery_source text not null,
  discovery_evidence_path text,
  is_documented boolean default false,
  is_authenticated boolean,
  auth_type text,
  inferred_purpose text,
  request_params jsonb,
  response_schema jsonb,
  sample_request text,
  sample_response text,
  reveals_feature text,
  patent_claim_impact jsonb,
  prior_art_risk boolean default false,
  is_hidden_endpoint boolean default false,
  is_internal_admin boolean default false,
  leaks_sensitive_data boolean default false,
  discovered_at timestamptz default now()
);

-- 8. ci_dossier_eg14_runs
create table ci_dossier_eg14_runs (
  id uuid primary key default gen_random_uuid(),
  competitor_slug text references ci_dossiers(competitor_slug),
  run_number integer not null,
  points_passed smallint,
  points_failed jsonb,
  verdict text check (verdict in ('pass','fail','timeout','running')),
  started_at timestamptz default now(),
  completed_at timestamptz,
  notified_telegram boolean default false
);

-- Indexes
create index idx_ci_dossiers_slug on ci_dossiers(competitor_slug);
create index idx_ci_dossiers_threat on ci_dossiers(threat_level);
create index idx_ci_dossier_urls_slug on ci_dossier_urls(competitor_slug);
create index idx_ci_dossier_urls_type on ci_dossier_urls(url_type);
create index idx_ci_dossier_features_slug on ci_dossier_features(competitor_slug);
create index idx_ci_dossier_api_endpoints_slug on ci_dossier_api_endpoints(competitor_slug);
create index idx_ci_dossier_api_endpoints_hidden on ci_dossier_api_endpoints(is_hidden_endpoint) where is_hidden_endpoint = true;

-- Storage bucket: ci-evidence
-- Note: Bucket creation handled via Supabase Dashboard/API, not SQL migration.
-- Structure: ci-evidence/{competitor_slug}/{sitemap,screenshots,features,samples,api_discovery,interrogations}/
