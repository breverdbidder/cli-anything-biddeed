-- Chat Ground Truth + Reconciliation Tables
-- Created: 2026-03-29
-- Issue: #37 — Forensic validation of Q1 chat backfill data
-- Blocks: chat backfill verification pipeline

CREATE TABLE IF NOT EXISTS chat_ground_truth (
    session_id TEXT PRIMARY KEY,
    chat_date DATE NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    title TEXT,
    summary_chars INT DEFAULT 0,
    summary_words INT DEFAULT 0,
    scanned_at TIMESTAMPTZ DEFAULT now(),
    scan_source TEXT DEFAULT 'recent_chats'
);

CREATE TABLE IF NOT EXISTS chat_reconciliation (
    id SERIAL PRIMARY KEY,
    run_at TIMESTAMPTZ DEFAULT now(),
    month TEXT NOT NULL,
    total_ground_truth INT DEFAULT 0,
    total_in_db INT DEFAULT 0,
    verified INT DEFAULT 0,
    missing INT DEFAULT 0,
    orphan INT DEFAULT 0,
    mismatch INT DEFAULT 0,
    trust_score NUMERIC(5,2) DEFAULT 0,
    missing_ids TEXT[],
    orphan_ids TEXT[]
);

CREATE INDEX IF NOT EXISTS idx_chat_ground_truth_date ON chat_ground_truth(chat_date);
CREATE INDEX IF NOT EXISTS idx_chat_reconciliation_month ON chat_reconciliation(month);
CREATE INDEX IF NOT EXISTS idx_chat_reconciliation_run_at ON chat_reconciliation(run_at);
