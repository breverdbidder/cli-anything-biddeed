-- GOLD STANDARD AUTOPILOT: Ultraloop Audit Table
-- Per brief: "Certification of a letter requires >=1 survived=true row for that county+letter newer than the letter's last metric change"

CREATE TABLE IF NOT EXISTS gold_standard_ultraloop_audit (
  id BIGSERIAL PRIMARY KEY,
  dispatch_id UUID NOT NULL,
  ultraloop_mode TEXT NOT NULL CHECK (ultraloop_mode IN ('native', 'fallback')),
  county_slug TEXT NOT NULL,
  letter CHAR(1) NOT NULL CHECK (letter IN ('A','B','C','D','E','F','G','H','I','J')),
  claim TEXT NOT NULL,
  refuter_evidence JSONB,
  survived BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  session_id TEXT
);

-- Indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_ultraloop_audit_county_letter ON gold_standard_ultraloop_audit(county_slug, letter);
CREATE INDEX IF NOT EXISTS idx_ultraloop_audit_survived ON gold_standard_ultraloop_audit(survived);
CREATE INDEX IF NOT EXISTS idx_ultraloop_audit_dispatch ON gold_standard_ultraloop_audit(dispatch_id);
CREATE INDEX IF NOT EXISTS idx_ultraloop_audit_created ON gold_standard_ultraloop_audit(created_at);

-- Function to check certification eligibility
CREATE OR REPLACE FUNCTION check_certification_eligibility(county TEXT, target_letter CHAR(1))
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
AS $$
  SELECT EXISTS (
    SELECT 1 FROM gold_standard_ultraloop_audit 
    WHERE county_slug = county 
      AND letter = target_letter 
      AND survived = true 
      AND created_at > NOW() - INTERVAL '7 days'
  );
$$;

COMMENT ON TABLE gold_standard_ultraloop_audit IS 'Tracks ultraloop verification survival votes for gold standard letter certification';
COMMENT ON COLUMN gold_standard_ultraloop_audit.dispatch_id IS 'GitHub Actions workflow dispatch ID';
COMMENT ON COLUMN gold_standard_ultraloop_audit.refuter_evidence IS 'Evidence from adversarial refuter subagent attempting to break the claim';
COMMENT ON COLUMN gold_standard_ultraloop_audit.survived IS 'Whether the claim survived adversarial refutation';
COMMENT ON FUNCTION check_certification_eligibility IS 'Checks if a county+letter has survived=true rows within 7 days for certification eligibility';