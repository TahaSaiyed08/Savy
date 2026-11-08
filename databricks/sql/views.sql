-- Run AFTER the pipeline's first successful update (needs flyer_items).
USE realdeal.core;

-- Gold: best match per (user item, store) in that store's current flyer, with savings vs the median across stores.
-- "Current" is per store (its latest week_start): chains start their flyers on different days, so a global
-- max(week_start) would hide every store whose flyer started earlier.
-- The median is taken over the one-row-per-store result, so a store with several matches counts once.
CREATE OR REPLACE VIEW my_deals AS
WITH best AS (
  SELECT
    u.user_id,
    m.user_item_id,
    m.flyer_item_id,
    f.store,
    f.price,
    f.unit_price,
    m.match_score
  FROM (
    -- One row per (user item, flyer item) even if duplicates were ever stored.
    SELECT user_item_id, flyer_item_id, max(match_score) AS match_score FROM user_item_matches GROUP BY ALL
  ) m
  JOIN user_items u USING (user_item_id)
  JOIN (SELECT * FROM flyer_items QUALIFY week_start = max(week_start) OVER (PARTITION BY store)) f
    ON f.item_id = m.flyer_item_id
  -- Ties (e.g. every LIKE-fallback match scores 0.75) go to the cheapest unit price, then a stable id.
  QUALIFY row_number() OVER (
    PARTITION BY m.user_item_id, f.store ORDER BY m.match_score DESC, f.unit_price ASC NULLS LAST, f.item_id
  ) = 1
)
SELECT best.*, median(unit_price) OVER (PARTITION BY user_item_id) - unit_price AS savings_vs_median
FROM best;
