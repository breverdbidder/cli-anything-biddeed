# CLAUDE.md — Site Manager / Rehab Monitor

> Harness: `cli-anything-biddeed/sitemanager/`
> Origin: Forked from NextAutomation Site Manager v1.0
> Owner: Ariel Shapira — ZoneWise.AI + BidDeed.AI

## What This Is

**THE ZONEWISE.AI POST-ACQUISITION WORKFLOW.** After BidDeed.AI wins at auction, Site Manager tracks the rehab — photo documentation, contractor accountability, phase completion, schedule health, safety compliance, quality checks — all with Mapbox pins on the ZoneWise.AI property map.

NOT for commercial construction. This is for $25K-$250K residential rehab projects in Brevard County.

## Pipeline

```
PROJECT → PHOTOS → SCHEDULE → SAFETY → QUALITY → DAILY → REPORT
```

| Stage | Status | What It Does |
|-------|--------|-------------|
| PROJECT | ✅ Working | Create/load project from BCPAO parcel data |
| PHOTOS | ⚠️ Basic | Register photos (needs Claude Vision for auto-analysis) |
| SCHEDULE | ✅ Working | Phase completion tracking, health score 0-100 |
| SAFETY | ✅ Working | 10 Brevard-specific code checks (auto-flags by year built) |
| QUALITY | ✅ Working | Issue tracking per phase |
| DAILY | ✅ Working | Keyword extraction from contractor notes |
| REPORT | ✅ Working | Composite score + Mapbox GeoJSON pin |

## 16 Rehab Phases (Matches Forecaster Templates)

demo → structural → roof → windows_doors → plumbing → electrical → hvac → insulation → drywall → interior_paint → flooring → kitchen → bathrooms → fixtures_appliances → landscaping_exterior → final_clean

## 10 Brevard Safety Auto-Checks

| Check | Auto-Flags When | Severity |
|-------|-----------------|----------|
| Polybutylene plumbing | Year < 1995 | CRITICAL |
| Chinese drywall | 2004-2009 | CRITICAL |
| Federal Pacific panel | Year < 1985 | CRITICAL |
| Asbestos | Year < 1980 | HIGH |
| Termite damage | Always (30% of Brevard rehabs) | HIGH |
| Hurricane straps | All roof work | HIGH |
| Stucco intrusion | Block construction | MEDIUM |
| Wind mitigation | After roof work | MEDIUM |
| Flood zone compliance | AE/VE zones | HIGH |
| Open permits | Always | HIGH |

## Supabase Table: `rehab_site_reports`

```sql
CREATE TABLE IF NOT EXISTS rehab_site_reports (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT UNIQUE NOT NULL,
  parcel_id TEXT,
  address TEXT,
  site_health_score INT,
  schedule_health INT,
  safety_score INT,
  quality_score INT,
  status TEXT DEFAULT 'ACTIVE',
  overall_pct INT DEFAULT 0,
  action_count INT DEFAULT 0,
  budget NUMERIC,
  template TEXT,
  gc_name TEXT,
  projected_completion DATE,
  geojson_feature JSONB,
  report_json JSONB,
  reported_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rsr_parcel ON rehab_site_reports(parcel_id);
CREATE INDEX IF NOT EXISTS idx_rsr_status ON rehab_site_reports(status);
CREATE INDEX IF NOT EXISTS idx_rsr_health ON rehab_site_reports(site_health_score);
```

### `rehab_site_photos`
```sql
CREATE TABLE IF NOT EXISTS rehab_site_photos (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT REFERENCES rehab_site_reports(project_id),
  phase TEXT,
  filename TEXT,
  storage_url TEXT,
  notes TEXT,
  analysis_json JSONB,
  uploaded_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Session Priorities

### P0 — Supabase + Persistence
1. Create `rehab_site_reports` + `rehab_site_photos` tables
2. Wire --save flag on create and report commands
3. Wire photo upload to Supabase storage (or just metadata to table)

### P1 — Contractor Workflow
4. Add `update-phase` command that loads project from Supabase, updates, re-saves
5. Add `add-issue` command for quality issue logging
6. Telegram alerts when site_health_score drops below 60

### P2 — Vision Integration
7. Claude Vision API for photo auto-analysis (phase detection, progress %, quality)
8. Before/after photo comparison for progress verification
9. Annotated photo generation with issue markers

### P3 — ZoneWise.AI Integration
10. Dashboard endpoint: all active projects ranked by health score
11. Mapbox layer: active rehab pins on county map (green/yellow/red by health)
12. DOCX weekly report generation per project
13. Integration with Forecaster: actual spend vs budget with schedule overlay

## CLI Quick Reference

```bash
# Create project
python3 -m sitemanager.agent create --parcel "25-37-22-00-00123.0-0000.00" --budget 85000 --gc "ABC Contractors" --json --save

# Update phase
python3 -m sitemanager.agent update --parcel "25-37-22-00-00123.0-0000.00" --phase roof --pct 75 --notes "Shingles done, ridge vent tomorrow"

# Register photo
python3 -m sitemanager.agent photo --parcel "25-37-22-00-00123.0-0000.00" --file kitchen_demo.jpg --phase kitchen

# Generate report
python3 -m sitemanager.agent report --parcel "25-37-22-00-00123.0-0000.00" --json --save

# Portfolio dashboard
python3 -m sitemanager.agent dashboard --json

# Status
python3 -m sitemanager.agent status
```
