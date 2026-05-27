# BidDeed.AI · Internal Architecture v1.0

> **AUDIT TRAIL — read this before citing model metrics:** The Shapira V4 stacked ensemble described in this doc is the **patented architecture**, not the production implementation. As of 2026-05-27 the V4 stacked ensemble is NOT trained — no weights deployed, no AUC measured. Daily production scoring is V1 (rule-based heuristic, `scripts/shapira_score.py`). Owner vertex of the Triangle is live (8 SQL signals); property + financial vertices are planned. Canonical ground truth: `ci_v65_event_log.id = 13be7baa-c50c-4fd1-8223-091788cb9bda`. Real V14 XGBoost AUC will land via SUMMIT-B (`summit_chat_dispatch.id = 2572cb98-5c24-4606-800d-0b106e83de7f`). Do NOT cite 82.6% / 0.8832 AUC anywhere — those numbers cannot be traced to any training run in code.


**Status:** Internal-only dogfooding. No customer-facing endpoints yet.
**Last updated:** 2026-05-14
**Owner:** Ariel Shapira

This document describes how data, code, and deployments are organized in the BidDeed.AI Supabase project (`mocerqjnksmhcjzxrewo`) and how the various pieces fit together. It's the source of truth for "where does X live."

---

## TL;DR

- **Code** (HTML, CSS, JS) lives in `biddeed.app_files`. Versioned.
- **Data exports** (CSV, JSON) live in `biddeed.data_exports`. Cataloged.
- **Distress signals** are defined in `triangle.signal_catalog`. The Shapira Triangle V4.0 has 3 vertices (owner = live, property + financial = planned).
- **County pipelines** are tracked in `pipeline.counties`. Brevard is live; 66 others are planned.
- **Feature flags** live in `config.feature_flags`. Toggle UI features without redeploys.
- **Every deploy** is logged in `biddeed.deploy_log`. **Every mutation** is logged in `biddeed.audit_log`.

---

## Schemas

### `biddeed` — App code & deploy state

| Table | Purpose |
|---|---|
| `app_files` | HTML/JS/CSS files. Each row = one deployable file. Path is repo-relative (e.g. `docs/brevard.html`). |
| `app_file_versions` | Auto-snapshot of every previous version. Enables rollback. Trigger-managed. |
| `data_exports` | CSV/JSON exports for downstream consumption. Generated from views, uploaded to Storage. |
| `deploy_log` | Every push to GitHub, Vercel deploy, Storage upload. Single audit trail. |
| `audit_log` | High-signal mutations: schema changes, signal-catalog edits, dedup runs. |

**Helper function:** `biddeed.log_deploy(kind, asset_id, path, destination, ...)` standardizes deploy recording.

**Convenience views:**
- `biddeed.v_latest_deploys` — most recent deploy per asset
- `biddeed.v_system_overview` — single-query system health snapshot

### `triangle` — Shapira Triangle V4.0 distress system

The patented distress identification model. Three vertices.

| Vertex | Status | Weight | Signals | Max Score |
|---|---|---|---|---|
| `OWNER` | **Live** | 0.40 | 6 | 130 |
| `PROPERTY` | Planned | 0.30 | 0 | 100 |
| `FINANCIAL` | Planned | 0.30 | 0 | 100 |

**Owner vertex signals (live today):**

| Code | Label | Weight | Description |
|---|---|---|---|
| `OUT_OF_STATE` | 🌐 Out-of-state | 25 | Owner mailing state ≠ FL |
| `ABSENTEE` | 👻 Absentee | 20 | Mailing zip ≠ situs zip |
| `ESTATE_TRUST` | ⚰️ Estate/Trust | 30 | Estate, trust, heirs, deceased keywords |
| `ENTITY` | 🏢 Entity | 15 | LLC, Inc, Corp, holding company |
| `LENDER_REO` | 🏦 Lender REO | 10 | Bank, mortgage, Fannie, Freddie |
| `MULTI_PARCEL` | 🔁 Multi-parcel | 20 | Owner has 2+ parcels same auction date |

**Composite score formula** (when all 3 vertices live):
`composite_score = (owner_score × 0.40) + (property_score × 0.30) + (financial_score × 0.30)`

**Helper view:** `triangle.v_signals_active_today` — per-signal firing rates today.

### `pipeline` — Data ingestion tracking

| Table | Purpose |
|---|---|
| `counties` | 67 FL counties. Today: Brevard live, 66 planned. Tracks platform, URL, health. |
| `source_systems` | External data sources (BCPAO, brevardclerk, RealAuction, PropertyOnion, FL DOR). |
| `scrape_runs` | Every scrape attempt = one row. Use for freshness audits and alerting. |

**Helper view:** `pipeline.v_county_freshness` — at-a-glance pipeline health.

### `config` — Feature flags

| Table | Purpose |
|---|---|
| `feature_flags` | Toggle UI / pipeline features without redeploys. Read by frontend on each page load. |

**Active flags today:**
- `triangle.owner_vertex` ✅
- `ui.diamonds_persona` ✅
- `ui.owner_picker` ✅
- `ui.ai_chat_builder` ✅
- `pipeline.brevard_taxdeed` ✅
- `triangle.property_vertex` ⏳ (planned)
- `triangle.financial_vertex` ⏳ (planned)
- `pipeline.brevardclerk_ground_truth` ⏳ (TODO — Action Plan #3)

---

## Data Flow

```
┌──────────────────────────────────────────────────────────┐
│                  SUPABASE (single source of truth)        │
│                                                            │
│  Raw data:                                                 │
│    public.multi_county_auctions  (193K+ FL foreclosures)  │
│    public.po_listings            (62K+ PO listings)       │
│    public.zw_parcels             (342K Brevard parcels)   │
│    public.fl_parcels             (10.5M FL statewide)     │
│                                                            │
│  Today's snapshot (deduped 129 rows):                     │
│    public.brevard_taxdeed_today_snapshot                  │
│                                                            │
│  Export view (computes Triangle owner-vertex signals):    │
│    public.v_brevard_taxdeed_today_export                  │
│                                                            │
│  Materialized as CSV:                                      │
│    biddeed.data_exports (id=2, filename=brevard_...csv)   │
│                                                            │
│  App code:                                                 │
│    biddeed.app_files (id=N, path=docs/brevard.html)       │
└─────────────────┬──────────────────────────────────────────┘
                  │
                  │ extensions.http() PUT
                  │ base64(content) → GitHub Contents API
                  ↓
┌──────────────────────────────────────────────────────────┐
│  GITHUB · breverdbidder/cli-anything-biddeed              │
│    docs/brevard.html       ← HTML decoded from base64     │
│    docs/parity-2026-05-14.html                            │
│    docs/ARCHITECTURE.md    ← this document                 │
│    .github/workflows/                                      │
│      deploy-to-vercel.yml        ← triggered after push   │
│      export-csv-to-storage.yml   ← uploads CSVs           │
└─────────────────┬──────────────────────────────────────────┘
                  │
                  │ GHA: vercel deploy --prod
                  ↓
┌──────────────────────────────────────────────────────────┐
│  VERCEL · biddeed-tax-deed-demo                            │
│  Serves docs/brevard.html as text/html worldwide          │
│  HTML calls fetch() → CSV at Supabase Storage URL         │
└─────────────────┬──────────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────────────────────────┐
│  SUPABASE STORAGE · exports bucket (public, no-cache)     │
│    /exports/brevard_taxdeed_2026-05-14.csv               │
└──────────────────────────────────────────────────────────┘
```

---

## Common Queries

### Add a new app file
```sql
INSERT INTO biddeed.app_files (path, content, content_type, description)
VALUES ('docs/new-page.html', '<!doctype html>...', 'text/html', 'New thing');
```
Trigger auto-versions on update. Push to GitHub via existing pg_net pattern.

### Update an app file (auto-versioned)
```sql
UPDATE biddeed.app_files
SET content = '<!doctype html>... v2'
WHERE path = 'docs/brevard.html';
-- Previous version snapshotted to app_file_versions automatically
```

### Roll back to a previous version
```sql
UPDATE biddeed.app_files a
SET content = v.content
FROM biddeed.app_file_versions v
WHERE a.id = v.file_id AND v.version = <target_version>
  AND a.path = 'docs/brevard.html';
```

### Disable a Triangle signal (no redeploy)
```sql
UPDATE triangle.signal_catalog SET enabled = FALSE WHERE code = 'LENDER_REO';
-- Re-run snapshot rebuild to take effect on next export
```

### Add a new county pipeline (planning stage)
```sql
INSERT INTO pipeline.counties (county_slug, county_name, fips_code, pipeline_status, notes)
VALUES ('orange', 'Orange County', '12095', 'planned', 'Next after Brevard validates');
```

### See what changed today
```sql
SELECT event_at, actor, action, entity_table, details
FROM biddeed.audit_log
WHERE event_at > NOW() - INTERVAL '1 day'
ORDER BY event_at DESC;
```

### System health snapshot
```sql
SELECT * FROM biddeed.v_system_overview;
```

---

## What's still hacky (known debt)

1. **GHA workflow `export-csv-to-storage.yml` still reads from `public._csv_exports`**, not the new `biddeed.data_exports`. The old table is marked DEPRECATED but kept alive for backward compat. Migrate the workflow in a future task.
2. **No Edge Functions yet** — frontend reads CSV directly from Storage. Fine for internal use; add an API layer before opening to external users.
3. **No `buyboxes` table** — custom personas still live in browser localStorage. Move server-side when you want multi-device sync.
4. **No auth** — single-user system. Add Supabase Auth before any external user touches this.
5. **Triangle owner vertex only** — property + financial vertices are placeholder rows in `triangle.vertices` with status='planned'.
6. **Brevard only** — `pipeline.counties` has 1 row. The architecture supports 67; only 1 is live.

---

## Migration history

- **2026-05-14 v1.0** · Schemas created (`biddeed`, `triangle`, `pipeline`, `config`). HTML files migrated from `_csv_exports` to `biddeed.app_files`. CSV files migrated to `biddeed.data_exports`. Owner-vertex signals formalized in `triangle.signal_catalog`. Brevard county registered in `pipeline.counties`.

---

## Glossary

- **Shapira Triangle V4.0** · Patented architecture (14 claims filed under Ariel Shapira individual) for three-vertex distress identification: owner + property + financial. **Production status as of 2026-05-27:** owner vertex active with 8 SQL signals (6 enabled, 2 ready-but-disabled — PRIOR_REDEMPTION, PRIOR_SURPLUS); property + financial vertices planned. The patent-claimed XGBoost+LightGBM+CatBoost→RF meta-learner stacked ensemble (Claim 8) is NOT yet trained — measured AUC will be published only after SUMMIT-B (V14 training on 204K labeled rows in `multi_county_auctions`) completes and writes metadata to `shapira_formula_params`. Daily production scoring is V1 rule-based (`scripts/shapira_score.py`, cron 7 AM EST weekdays). Corpus at audit time: 356,384 auctions / 46 counties + 10.5M FL parcels. See `ci_v65_event_log` entry `13be7baa-c50c-4fd1-8223-091788cb9bda` for the canonical Diamonds/Triangle/V4 ground truth audit.
- **Owner vertex** · 6 distress signals computed from owner_name, mailing address, and parcel counts. Score 0-130. Live today.
- **Diamonds** · Properties with unknown/missing street addresses. Proxy bidders skip them. Surfaced as a UI persona.
- **EG18** · Internal governance: 14-point gate + K1-K4 discipline. Every meaningful change passes EG18.
- **MCA** · `multi_county_auctions` — primary auction-data table.
- **BCPAO** · Brevard County Property Appraiser. Parcel data source.
- **PO** · PropertyOnion. Competitor + data source we ingest from.

