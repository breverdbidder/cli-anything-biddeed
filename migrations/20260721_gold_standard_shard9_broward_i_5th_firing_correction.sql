-- GOLD STANDARD shard-9 (dispatch 20a33672), 5th firing, broward Letter I lane.
-- CORRECTION to 20260721_gold_standard_shard9_broward_i_5th_firing.sql.
--
-- Post-apply re-verification against the live evaluator found the Bay Club Dr
-- fix (CACE-20-018707, parcel_id corrected to 494212AK1970 in the prior
-- migration) was STILL failing letter I -- the parcel_id/zone fix landed
-- correctly, but market_value (BCPA justValue $347,740, already fetched live
-- during discovery in this same session) was never written to the row. This
-- was an oversight in the prior migration, caught by re-running the exact
-- failing-row query after apply rather than trusting the predicted count.
-- Applying the missed value now.

UPDATE multi_county_auctions
SET market_value = 347740
WHERE county = 'broward' AND case_number = 'CACE-20-018707' AND parcel_id = '494212AK1970';
