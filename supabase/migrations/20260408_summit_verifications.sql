-- SUMMIT 277: Spec Fulfillment Verifier — delivery gate enforcement
-- Tracks verification results for SUMMIT issues

CREATE TABLE IF NOT EXISTS summit_verifications (
  id BIGSERIAL PRIMARY KEY,
  issue_number INT NOT NULL,
  repo TEXT NOT NULL DEFAULT 'cli-anything-biddeed',
  verified_at TIMESTAMPTZ DEFAULT NOW(),
  overall_verdict TEXT CHECK (overall_verdict IN ('DELIVERED','PARTIAL','FAILED')),
  checklist_total INT,
  checklist_passed INT,
  checklist_failed INT,
  failed_items JSONB,
  cc_report_url TEXT,
  evidence JSONB
);

CREATE INDEX IF NOT EXISTS idx_summit_verif_issue ON summit_verifications(issue_number);
CREATE INDEX IF NOT EXISTS idx_summit_verif_verdict ON summit_verifications(overall_verdict);
