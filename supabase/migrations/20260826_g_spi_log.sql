-- Migration: Growth-Sprint SPI (G-SPI) tracking
-- Issue: breverdbidder/cli-anything-biddeed#19480
-- Sprint 0: Sep 1–14 2026
-- NOTE: This is Growth-Sprint SPI (Earned Value / Planned Value) only.
--       NOT spi_daily / spi_gates / spi_task_registry. Do not conflate.

CREATE TABLE IF NOT EXISTS g_spi_log (
    id              BIGSERIAL PRIMARY KEY,
    sprint          TEXT NOT NULL DEFAULT 'sprint-0-2026-09',
    sprint_day      INT NOT NULL,
    work_date       DATE NOT NULL,
    task_ref        TEXT NOT NULL,
    planned_value   NUMERIC(5,2) NOT NULL DEFAULT 0,
    earned_value    NUMERIC(5,2) NOT NULL DEFAULT 0,
    spi             NUMERIC(5,3) GENERATED ALWAYS AS (
                        CASE WHEN planned_value = 0 THEN NULL
                             ELSE ROUND(earned_value / planned_value, 3)
                        END
                    ) STORED,
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','completed','blocked')),
    notes           TEXT,
    evidence_url    TEXT,
    logged_by       TEXT NOT NULL DEFAULT 'claude-code',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_g_spi_sprint    ON g_spi_log(sprint);
CREATE INDEX IF NOT EXISTS idx_g_spi_work_date ON g_spi_log(work_date);

-- Seed Sprint 0 planned tasks (PV = 1 per task-day)
INSERT INTO g_spi_log (sprint_day, work_date, task_ref, planned_value, earned_value, status, notes) VALUES
    (1,  '2026-09-01', 'day1-stripe-purchase-gate',        1, 0, 'pending', 'Close founder test purchase end-to-end (real card → stripe-webhook v9 → subscription_events → entitlement proof)'),
    (1,  '2026-09-01', 'day1-digest-audit',                1, 0, 'pending', 'Audit digest workflow run history + content-cron (#19372) dispatch status'),
    (1,  '2026-09-01', 'day1-gspi-standup',                1, 0, 'pending', 'G-SPI log table live (this migration)'),
    (2,  '2026-09-02', 'day2-run-daily-funnel-mcp',        1, 0, 'pending', 'run_daily_funnel MCP tool: thin orchestrator wrapping .cjs digest logic (dry_run param)'),
    (2,  '2026-09-02', 'day2-log-funnel-execution-table',  1, 0, 'pending', 'log_funnel_execution table live'),
    (3,  '2026-09-03', 'day3-get-top-auction-highlights',  1, 0, 'pending', 'get_top_auction_highlights MCP tool: reads county_twin_snapshot / daily_auction_outcomes'),
    (4,  '2026-09-04', 'day4-generate-funnel-content',     1, 0, 'pending', 'generate_funnel_content MCP tool: Claude primary via Smart Router, Grok second'),
    (7,  '2026-09-07', 'day7-homepage-top-auctions',       1, 0, 'pending', 'Homepage Today Top Auctions module in biddeed-web (Next.js/Vercel)'),
    (8,  '2026-09-08', 'day8-e2e-dry-run',                 1, 0, 'pending', 'End-to-end dry-run (data → content → email). First live send to internal/test list via Resend'),
    (9,  '2026-09-09', 'day9-send-path-reconcile',         1, 0, 'pending', 'Reconcile send_daily_digest with existing cron: exactly one send path'),
    (10, '2026-09-10', 'day10-live-send-2-3',              1, 0, 'pending', 'Live send #2-3. Backfill G-SPI stand-ups for Days 1-9 from actual commits'),
    (11, '2026-09-11', 'day11-live-send-4',                1, 0, 'pending', 'Live send #4. Buffer/bugfix day'),
    (14, '2026-09-14', 'day14-live-send-5-review',         1, 0, 'pending', 'Live send #5 (closes 5 consecutive days success criterion). Sprint 0 Review + Retro')
ON CONFLICT DO NOTHING;
