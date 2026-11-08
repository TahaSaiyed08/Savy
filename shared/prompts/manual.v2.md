A student is adding an item to their grocery list in plain English, typed or transcribed from speech.
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
- confidence: number from 0 to 1, your confidence that every field above is correct
