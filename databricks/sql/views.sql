-- Run AFTER the pipeline's first successful update (needs flyer_items).
USE realdeal.core;

-- Gold: best match per (user item, store) in that store's current flyer, with savings vs the median across stores.
-- "Current" is per store (its latest week_start): chains start their flyers on different days, so a global
-- max(week_start) would hide every store whose flyer started earlier.
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
FROM (
  -- One row per (user item, flyer item) even if duplicates were ever stored, so they can't skew the median.
  SELECT user_item_id, flyer_item_id, max(match_score) AS match_score FROM user_item_matches GROUP BY ALL
) m
JOIN user_items u USING (user_item_id)
JOIN (SELECT * FROM flyer_items QUALIFY week_start = max(week_start) OVER (PARTITION BY store)) f
  ON f.item_id = m.flyer_item_id
QUALIFY row_number() OVER (PARTITION BY m.user_item_id, f.store ORDER BY m.match_score DESC) = 1;
