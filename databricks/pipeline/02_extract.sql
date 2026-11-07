-- Silver (raw): one ai_query call per flyer page image. This is the SQL to show judges (demo step 6).
-- The prompt below must equal shared/prompts/flyer_page.v1.md; databricks/test_prompt_sync.py enforces it.
-- ${realdeal.model} comes from the pipeline configuration in databricks.yml.
CREATE OR REFRESH STREAMING TABLE flyer_extractions
COMMENT 'ai_query output per flyer page'
AS SELECT
  page_id, store, week_start, page_no, image_path,
  ai_query(
    '${realdeal.model}',
    'You are reading one page of a weekly grocery flyer from a Vancouver, Canada supermarket.
Extract every advertised product with a price. Skip banners, recipes, coupons without a product, and loyalty point offers.
When a price is "2 for $5", record price as 2.50. When a price is per lb or per kg, set size_qty to 1 and size_unit to "lb" or "kg".
Also include for each item:
- raw_text: the product text as printed, at most 120 characters
- bbox: [x0, y0, x1, y1] of the product tile as fractions of page width and height
Return ONLY a JSON object of the form {"items": [ ... ]} where each item has:
- brand: string or null (e.g. "PC", "Kirkland"; null for produce and generic items)
- item: string, the product noun in plain English, singular (e.g. "chicken thigh", "milk")
- variant: string or null (e.g. "boneless skinless", "2%", "extra virgin")
- size_qty: number or null, exactly as printed for ONE purchasable unit, multiplied out for multipacks (2 x 1.89 L -> 3.78)
- size_unit: one of "g", "kg", "ml", "l", "lb", "ea", or null
- price: number or null, the price for one purchasable unit in CAD, no currency symbol
- confidence: number from 0 to 1, your confidence that every field above is correct
Do not invent items, sizes or prices that are not visible. Use null instead of guessing.',
    files => content,
    -- The top-level field must be a STRUCT (ai_query rejects ARRAY there); the response JSON is {"items": [...]}.
    responseFormat => 'STRUCT<result: STRUCT<items: ARRAY<STRUCT<brand: STRING, item: STRING, variant: STRING, size_qty: DOUBLE, size_unit: STRING, price: DOUBLE, confidence: DOUBLE, raw_text: STRING, bbox: ARRAY<DOUBLE>>>>>'
  ) AS response
FROM STREAM(flyer_pages);
