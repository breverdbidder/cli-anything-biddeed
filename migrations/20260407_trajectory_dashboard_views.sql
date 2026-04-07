-- Dashboard views for prediction accuracy over time
-- Issue: https://github.com/breverdbidder/cli-anything-biddeed/issues/119
-- Success Criterion: "Dashboard view: prediction accuracy over time by zip/auction_type"

-- View 1: Prediction accuracy by zip code
CREATE OR REPLACE VIEW trajectory_accuracy_by_zip AS
SELECT
  zip_code,
  auction_type,
  COUNT(*) AS total_predictions,
  COUNT(*) FILTER (WHERE actual_sold IS NOT NULL) AS outcomes_recorded,
  COUNT(*) FILTER (WHERE reward_score IS NOT NULL) AS scored,
  ROUND(AVG(reward_score) FILTER (WHERE reward_score IS NOT NULL), 4) AS avg_reward,
  ROUND(AVG(CASE WHEN recommendation = 'BID' AND actual_buyer_type = 'third_party' THEN 1.0
             WHEN recommendation = 'SKIP' AND actual_buyer_type != 'third_party' THEN 1.0
             ELSE 0.0 END) FILTER (WHERE actual_sold IS NOT NULL), 4) AS recommendation_accuracy,
  COUNT(*) FILTER (WHERE recommendation = 'BID') AS total_bids,
  COUNT(*) FILTER (WHERE recommendation = 'SKIP') AS total_skips,
  COUNT(*) FILTER (WHERE recommendation = 'REVIEW') AS total_reviews,
  ROUND(AVG(prediction_delta) FILTER (WHERE prediction_delta IS NOT NULL), 2) AS avg_price_delta,
  MIN(auction_date) AS earliest_auction,
  MAX(auction_date) AS latest_auction
FROM prediction_trajectories
GROUP BY zip_code, auction_type
ORDER BY outcomes_recorded DESC, zip_code;

-- View 2: Prediction accuracy over time (monthly)
CREATE OR REPLACE VIEW trajectory_accuracy_monthly AS
SELECT
  DATE_TRUNC('month', auction_date)::date AS month,
  auction_type,
  county,
  COUNT(*) AS total_predictions,
  COUNT(*) FILTER (WHERE actual_sold IS NOT NULL) AS outcomes_recorded,
  ROUND(AVG(reward_score) FILTER (WHERE reward_score IS NOT NULL), 4) AS avg_reward,
  ROUND(AVG(CASE WHEN recommendation = 'BID' AND actual_buyer_type = 'third_party' THEN 1.0
             WHEN recommendation = 'SKIP' AND actual_buyer_type != 'third_party' THEN 1.0
             ELSE 0.0 END) FILTER (WHERE actual_sold IS NOT NULL), 4) AS recommendation_accuracy,
  COUNT(*) FILTER (WHERE recommendation = 'BID' AND actual_buyer_type = 'third_party' AND actual_sale_price <= max_bid_calculated) AS would_have_won,
  ROUND(SUM(CASE WHEN recommendation = 'SKIP' AND actual_buyer_type = 'third_party' AND actual_sale_price < max_bid_calculated
            THEN arv_estimate - actual_sale_price - repair_estimate - 10000 ELSE 0 END) FILTER (WHERE actual_sold IS NOT NULL), 2) AS missed_profit_estimate,
  model_version,
  formula_version
FROM prediction_trajectories
GROUP BY month, auction_type, county, model_version, formula_version
ORDER BY month DESC;

-- View 3: Overall engine health summary
CREATE OR REPLACE VIEW trajectory_engine_health AS
SELECT
  COUNT(*) AS total_trajectories,
  COUNT(*) FILTER (WHERE actual_sold IS NOT NULL) AS with_outcomes,
  COUNT(*) FILTER (WHERE reward_score IS NOT NULL) AS with_rewards,
  COUNT(*) FILTER (WHERE actual_sold IS NULL AND auction_date < CURRENT_DATE) AS pending_outcomes,
  ROUND(AVG(reward_score) FILTER (WHERE reward_score IS NOT NULL), 4) AS overall_avg_reward,
  ROUND(AVG(CASE WHEN recommendation = 'BID' AND actual_buyer_type = 'third_party' THEN 1.0
             WHEN recommendation = 'SKIP' AND actual_buyer_type != 'third_party' THEN 1.0
             ELSE 0.0 END) FILTER (WHERE actual_sold IS NOT NULL), 4) AS overall_recommendation_accuracy,
  COUNT(DISTINCT zip_code) AS zip_codes_covered,
  COUNT(DISTINCT county) AS counties_covered,
  MAX(created_at) AS last_prediction_at,
  MAX(outcome_recorded_at) AS last_outcome_at
FROM prediction_trajectories;
