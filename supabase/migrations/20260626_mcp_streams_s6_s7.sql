-- Migration: MCP revenue streams S6 (Market Data) + S7 (Property Intel)
-- Created: 2026-06-26 | Additive, idempotent, safe to re-run
-- Fixes taxi_meter_tools stream_id mismatches to align with constants.js TOOL_STREAM

-- Add S6 and S7 to taxi_meter_streams
INSERT INTO taxi_meter_streams (stream_id, name, unit_price_usd, gate_tier, billing_type, stripe_metered)
VALUES
  ('s6', 'Market Data',    0.0500, 'free',     'per_call', FALSE),
  ('s7', 'Property Intel', 0.2500, 'investor', 'per_call', FALSE)
ON CONFLICT (stream_id) DO UPDATE
  SET name           = EXCLUDED.name,
      unit_price_usd = EXCLUDED.unit_price_usd,
      gate_tier      = EXCLUDED.gate_tier;

-- Fix tool → stream mismatches (align DB config with constants.js TOOL_STREAM)
-- get_interest_rate and get_market_data are free market data (S6, not S1/S3)
UPDATE taxi_meter_tools SET stream_id = 's6' WHERE tool_name IN ('get_interest_rate', 'get_market_data');
-- search_properties and get_property_detail are property intel (S7, not S1/S2)
UPDATE taxi_meter_tools SET stream_id = 's7' WHERE tool_name IN ('search_properties', 'get_property_detail');

-- Add skip_trace if missing (S3 Fusion — $5/call, pro tier)
INSERT INTO taxi_meter_tools (tool_name, stream_id, gate_cert, product)
VALUES ('skip_trace', 's3', FALSE, 'biddeed')
ON CONFLICT (tool_name) DO NOTHING;
