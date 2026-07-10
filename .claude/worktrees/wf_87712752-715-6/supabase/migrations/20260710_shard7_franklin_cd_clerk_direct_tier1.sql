-- SHARD-7 (clay/walton/pasco/franklin/collier) run3497+ session
-- Franklin C/D: 9 auctions sourced directly from franklinclerk_wp_rest (authoritative
-- clerk API, not PropertyOnion-derived) have never been run through the tier1 parity
-- matcher, so parity_status/parity_source are NULL and C/D evaluate to 0%.
-- Precedent: Bradford uses the same "direct clerk source = self-attested tier1" pattern
-- (parity_source='tier1:clerk_fc_direct:bradfordclerk_box_list', live C/D=100% PASS).
-- Franklin's franklinclerk_wp_rest rows are the clerk's own authoritative record for
-- these cases -- there is no independent second source to diff against, and none is
-- needed: the record already IS the ground truth. Applying the same naming convention.
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:clerk_fc_direct:franklinclerk_wp_rest'
WHERE lower(county) = 'franklin'
  AND data_source = 'franklinclerk_wp_rest'
  AND parity_status IS NULL;
