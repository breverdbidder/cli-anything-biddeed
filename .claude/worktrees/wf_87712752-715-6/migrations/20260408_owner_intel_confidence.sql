-- ============================================================
-- ADD confidence_score TO auction_owner_intel
-- Migration: 20260408_owner_intel_confidence.sql
-- Issue: https://github.com/breverdbidder/cli-anything-biddeed/issues/391
-- Fixes #387 classifier: adds confidence_score for INVESTOR gating
-- ============================================================

ALTER TABLE auction_owner_intel
    ADD COLUMN IF NOT EXISTS confidence_score NUMERIC(4,3);

CREATE INDEX IF NOT EXISTS idx_aoi_confidence ON auction_owner_intel(confidence_score);

COMMENT ON COLUMN auction_owner_intel.confidence_score IS
    'Confidence score 0.0-1.0 for classification. '
    'Computed from: name length, first-name match strength, page-cap hit, owner_state agreement. '
    'INVESTOR requires >= 3 parcels AND confidence >= 0.7 (issue #391).';
