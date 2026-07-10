CREATE TABLE IF NOT EXISTS ims_permits (
    id SERIAL PRIMARY KEY,
    record_number TEXT UNIQUE NOT NULL,
    permit_type TEXT,
    permit_subtype TEXT,
    milestone TEXT,
    address TEXT,
    city TEXT DEFAULT 'Palm Bay',
    county TEXT DEFAULT 'Brevard',
    applicant TEXT,
    description TEXT,
    scraped_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ims_address ON ims_permits(address);
CREATE INDEX IF NOT EXISTS idx_ims_type ON ims_permits(permit_type);
CREATE INDEX IF NOT EXISTS idx_ims_milestone ON ims_permits(milestone);
