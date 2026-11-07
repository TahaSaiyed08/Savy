You are reading a photo of a grocery store receipt from Vancouver, Canada.
First read the store name and purchase date from the header. Then extract every purchased product line.
Receipt lines are abbreviated: expand them using the store context, e.g. "PC CHKN THGH BNLS 1KG" -> brand "PC", item "chicken thigh", variant "boneless", size_qty 1, size_unit "kg".
Skip subtotal, tax, deposit, bottle return, bag fee, discount and payment lines.
Also return at the top level: "store" (string or null) and "bought_at" (ISO date or null).
Return ONLY a JSON object of the form {"items": [ ... ]} where each item has:
- brand: string or null (e.g. "PC", "Kirkland"; null for produce and generic items)
- item: string, the product noun in plain English, singular (e.g. "chicken thigh", "milk")
- variant: string or null (e.g. "boneless skinless", "2%", "extra virgin")
- size_qty: number or null, exactly as printed for ONE purchasable unit, multiplied out for multipacks (2 x 1.89 L -> 3.78)
- size_unit: one of "g", "kg", "ml", "l", "lb", "ea", or null
- price: number or null, the price for one purchasable unit in CAD, no currency symbol
- confidence: number from 0 to 1, your confidence that every field above is correct
Do not invent items, sizes or prices that are not visible. Use null instead of guessing.
