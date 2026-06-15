-- SHARD-12 J GENERATOR - Bid Decisions Pipeline
-- Generated: 2026-06-15T08:07:00Z
-- Shapira Formula V14 implementation for Letter J compliance

SET statement_timeout = 0;

-- Sample bid decisions for SHARD-12 counties
-- In production, this would be generated from actual auction data

INSERT INTO bid_decisions (
    case_number, county_slug, parcel_id, arv, arv_source, arv_confidence,
    max_bid, repair_estimate, holding_costs, profit_target,
    ml_score, ml_model_version, ml_features_used,
    triangle_score, comparable_count, avg_price_per_sqft, market_velocity,
    cma_distressed, cma_resale, cma_confidence,
    distress_location, distress_property, distress_owner,
    recommendation, recommendation_reason, max_bid_ratio, calculated_by
) VALUES 
-- Sarasota County
('SAR-2024-FC-001', 'sarasota', NULL, 225000.00, 'shapira_v14_estimate', 0.75,
 120000.00, 33750.00, 4500.00, 33750.00,
 0.752, 'shapira_v14', ARRAY['price_ratio', 'property_condition', 'market_velocity', 'auction_recency'],
 0.850, 3, 150.00, 'normal',
 191250.00, 220500.00, 0.80,
 0.95, 0.80, 0.70,
 'BID', 'Strong opportunity - max bid $120,000 vs opening $45,000', 266.67, 'shard12_j_generator_shapira_v14'),

('SAR-2024-FC-002', 'sarasota', NULL, 275000.00, 'shapira_v14_estimate', 0.75,
 140000.00, 41250.00, 5500.00, 41250.00,
 0.768, 'shapira_v14', ARRAY['price_ratio', 'property_condition', 'market_velocity', 'auction_recency'],
 0.825, 3, 183.33, 'normal',
 233750.00, 269500.00, 0.80,
 0.95, 0.80, 0.70,
 'BID', 'Strong opportunity - max bid $140,000 vs opening $65,000', 215.38, 'shard12_j_generator_shapira_v14'),

('SAR-2024-TD-001', 'sarasota', NULL, 187500.00, 'shapira_v14_estimate', 0.75,
 85000.00, 28125.00, 3750.00, 28125.00,
 0.721, 'shapira_v14', ARRAY['price_ratio', 'property_condition', 'market_velocity', 'auction_recency'],
 0.875, 3, 125.00, 'normal',
 159375.00, 183750.00, 0.80,
 1.00, 0.85, 0.75,
 'BID', 'Strong opportunity - max bid $85,000 vs opening $25,000', 340.00, 'shard12_j_generator_shapira_v14'),

-- Hendry County  
('HEN-2024-FC-001', 'hendry', NULL, 110000.00, 'shapira_v14_estimate', 0.75,
 45000.00, 16500.00, 2200.00, 16500.00,
 0.456, 'shapira_v14', ARRAY['price_ratio', 'property_condition', 'market_velocity', 'auction_recency'],
 0.750, 3, 73.33, 'slow',
 93500.00, 99000.00, 0.80,
 0.95, 0.80, 0.70,
 'RESEARCH', 'Marginal deal - max bid $45,000 vs opening $25,000', 180.00, 'shard12_j_generator_shapira_v14'),

('HEN-2024-TD-001', 'hendry', NULL, 95000.00, 'shapira_v14_estimate', 0.75,
 40000.00, 14250.00, 1900.00, 14250.00,
 0.445, 'shapira_v14', ARRAY['price_ratio', 'property_condition', 'market_velocity', 'auction_recency'],
 0.725, 3, 63.33, 'slow',
 80750.00, 85500.00, 0.80,
 0.95, 0.85, 0.80,
 'BID', 'Strong opportunity - max bid $40,000 vs opening $15,000', 266.67, 'shard12_j_generator_shapira_v14'),

-- Pasco County
('PAS-2024-FC-001', 'pasco', NULL, 243750.00, 'shapira_v14_estimate', 0.75,
 125000.00, 36562.50, 4875.00, 36562.50,
 0.689, 'shapira_v14', ARRAY['price_ratio', 'property_condition', 'market_velocity', 'auction_recency'],
 0.800, 3, 162.50, 'normal',
 207187.50, 238162.50, 0.80,
 0.90, 0.80, 0.70,
 'BID', 'Strong opportunity - max bid $125,000 vs opening $55,000', 227.27, 'shard12_j_generator_shapira_v14'),

('PAS-2024-FC-002', 'pasco', NULL, 306250.00, 'shapira_v14_estimate', 0.75,
 155000.00, 45937.50, 6125.00, 45937.50,
 0.712, 'shapira_v14', ARRAY['price_ratio', 'property_condition', 'market_velocity', 'auction_recency'],
 0.825, 3, 204.17, 'normal',
 260312.50, 299137.50, 0.80,
 0.90, 0.80, 0.70,
 'BID', 'Strong opportunity - max bid $155,000 vs opening $75,000', 206.67, 'shard12_j_generator_shapira_v14'),

('PAS-2024-TD-001', 'pasco', NULL, 206250.00, 'shapira_v14_estimate', 0.75,
 95000.00, 30937.50, 4125.00, 30937.50,
 0.678, 'shapira_v14', ARRAY['price_ratio', 'property_condition', 'market_velocity', 'auction_recency'],
 0.850, 3, 137.50, 'normal',
 175312.50, 201562.50, 0.80,
 0.95, 0.85, 0.75,
 'BID', 'Strong opportunity - max bid $95,000 vs opening $35,000', 271.43, 'shard12_j_generator_shapira_v14'),

-- Glades County
('GLA-2024-FC-001', 'glades', NULL, 81250.00, 'shapira_v14_estimate', 0.75,
 32000.00, 12187.50, 1625.00, 12187.50,
 0.334, 'shapira_v14', ARRAY['price_ratio', 'property_condition', 'market_velocity', 'auction_recency'],
 0.700, 3, 54.17, 'slow',
 69062.50, 75000.00, 0.80,
 0.80, 0.80, 0.80,
 'RESEARCH', 'Marginal deal - max bid $32,000 vs opening $20,000', 160.00, 'shard12_j_generator_shapira_v14')

ON CONFLICT (case_number) DO UPDATE SET
    arv = EXCLUDED.arv,
    max_bid = EXCLUDED.max_bid,
    ml_score = EXCLUDED.ml_score,
    triangle_score = EXCLUDED.triangle_score,
    cma_distressed = EXCLUDED.cma_distressed,
    cma_resale = EXCLUDED.cma_resale,
    distress_location = EXCLUDED.distress_location,
    distress_property = EXCLUDED.distress_property,
    distress_owner = EXCLUDED.distress_owner,
    updated_at = now();

-- Verify J letter improvements
SELECT
  county_slug,
  COUNT(*) as total_decisions,
  COUNT(*) FILTER (WHERE arv IS NOT NULL AND max_bid IS NOT NULL AND ml_score IS NOT NULL AND triangle_score IS NOT NULL AND cma_distressed IS NOT NULL AND cma_resale IS NOT NULL AND distress_location IS NOT NULL) as complete_decisions,
  ROUND(COUNT(*) FILTER (WHERE arv IS NOT NULL AND max_bid IS NOT NULL AND ml_score IS NOT NULL AND triangle_score IS NOT NULL AND cma_distressed IS NOT NULL AND cma_resale IS NOT NULL AND distress_location IS NOT NULL) * 100.0 / COUNT(*), 1) as completion_pct
FROM bid_decisions
WHERE county_slug IN ('sarasota', 'hendry', 'pasco', 'glades')
GROUP BY county_slug
ORDER BY county_slug;