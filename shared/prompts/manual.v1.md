A student is adding an item to their grocery list in plain English, typed or transcribed from speech.
Map it to exactly one item. Examples: "the big Kirkland olive oil" -> brand "Kirkland", item "olive oil", variant "extra virgin", size_unit "l"; "a 4 L jug of 2 % milk" -> brand null, item "milk", variant "2%", size_qty 4, size_unit "l".
Leave fields null rather than guessing a size the student did not say. Price is always null.
Return ONLY a JSON object of the form {"items": [ ... ]} where each item has:
- brand: string or null (e.g. "PC", "Kirkland"; null for produce and generic items)
- item: string, the product noun in plain English, singular (e.g. "chicken thigh", "milk")
- variant: string or null (e.g. "boneless skinless", "2%", "extra virgin")
- size_qty: number or null, exactly as printed for ONE purchasable unit, multiplied out for multipacks (2 x 1.89 L -> 3.78)
- size_unit: one of "g", "kg", "ml", "l", "lb", "ea", or null
- price: number or null, the price for one purchasable unit in CAD, no currency symbol
- confidence: number from 0 to 1, your confidence that every field above is correct
Do not invent items, sizes or prices that are not visible. Use null instead of guessing.
