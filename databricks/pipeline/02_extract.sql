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
    -- JSON schema, not DDL: the DDL form makes every field optional and maverick silently drops price,
    -- confidence, raw_text and bbox. required + nullable types keep them (verified on page 1).
    responseFormat => '{"type":"json_schema","json_schema":{"name":"flyer_page","strict":true,"schema":{"type":"object","additionalProperties":false,"required":["items"],"properties":{"items":{"type":"array","items":{"type":"object","additionalProperties":false,"properties":{"brand":{"type":["string","null"]},"item":{"type":"string"},"variant":{"type":["string","null"]},"size_qty":{"type":["number","null"]},"size_unit":{"type":["string","null"]},"price":{"type":["number","null"]},"confidence":{"type":"number"},"raw_text":{"type":"string"},"bbox":{"type":["array","null"],"items":{"type":"number"}}},"required":["brand","item","variant","size_qty","size_unit","price","confidence","raw_text","bbox"]}}}}}}'
  ) AS response
FROM STREAM(flyer_pages);


-- Silver (raw): one text ai_query per Flipp item. Flipp already gives the price, tile and dates; this only splits
-- the printed text into brand / item / variant / size. It uses the app's typed-intake prompt (must equal
-- shared/prompts/manual.v2.md), so a flyer item and the user's own item end up in the same canonical words and
-- logic.same_item can compare them exactly.
CREATE OR REFRESH STREAMING TABLE flipp_extractions
COMMENT 'ai_query output per Flipp item'
AS SELECT
  *,
  ai_query(
    '${realdeal.model}',
    concat('A student is adding an item to their grocery list in plain English, typed or transcribed from speech.
Map it to exactly one item. Fill in only what the student said; leave everything else null.
Examples:
- "a 4 L jug of 2 % milk" -> brand null, item "milk", variant "2%", size_qty 4, size_unit "l"
- "the big Kirkland olive oil" -> brand "Kirkland", item "olive oil", variant null, size_qty null, size_unit null ("big" is not a size, and no variant was said)
- "two dozen eggs" -> brand null, item "eggs", variant null, size_qty 24, size_unit "ea"
Never add a variant (e.g. "extra virgin", "organic") or a size the student did not say. Set size_unit only when size_qty is known.
Lower confidence when the request is vague (e.g. "big", "the usual"). Price is always null.
Return ONLY a JSON object of the form {"items": [ ... ]} where each item has:
- brand: string or null (e.g. "PC", "Kirkland"; null for produce and generic items)
- item: string, the product noun in plain English, singular (e.g. "chicken thigh", "milk")
- variant: string or null (e.g. "boneless skinless", "2%", "extra virgin")
- size_qty: number or null, for ONE purchasable unit, multiplied out for multipacks (2 x 1.89 L -> 3.78)
- size_unit: one of "g", "kg", "ml", "l", "lb", "ea", or null
- price: always null
- confidence: number from 0 to 1, your confidence that every field above is correct', '\n\nText: ', raw_text),
    responseFormat => '{"type":"json_schema","json_schema":{"name":"flyer_text","strict":true,"schema":{"type":"object","additionalProperties":false,"required":["items"],"properties":{"items":{"type":"array","items":{"type":"object","additionalProperties":false,"properties":{"brand":{"type":["string","null"]},"item":{"type":"string"},"variant":{"type":["string","null"]},"size_qty":{"type":["number","null"]},"size_unit":{"type":["string","null"]},"price":{"type":["number","null"]},"confidence":{"type":"number"}},"required":["brand","item","variant","size_qty","size_unit","price","confidence"]}}}}}}'
  ) AS response
FROM STREAM(flipp_items);
