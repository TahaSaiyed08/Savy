-- Run AFTER the pipeline's first successful update (needs flyer_items).
USE realdeal.core;

-- Gold: this week's best match per (user item, store), with savings vs the median across stores.
CREATE OR REPLACE VIEW my_deals AS
SELECT
  u.user_id,
  m.user_item_id,
  m.flyer_item_id,
  f.store,
  f.price,
  f.unit_price,
  m.match_score,
  median(f.unit_price) OVER (PARTITION BY m.user_item_id) - f.unit_price AS savings_vs_median
FROM user_item_matches m
JOIN user_items u USING (user_item_id)
JOIN flyer_items f ON f.item_id = m.flyer_item_id
WHERE f.week_start = (SELECT max(week_start) FROM flyer_items)
QUALIFY row_number() OVER (PARTITION BY m.user_item_id, f.store ORDER BY m.match_score DESC) = 1;
