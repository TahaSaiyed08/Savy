// Demo-only product photography, keyed by keyword. The Figma mock supplied a handful of sample photos
// (not scraped from real flyers — see mock_data.py); reused here so deal cards don't render blank. Items
// with no match fall back to a plain monogram tile in DealCard rather than a fabricated photo.
const MILK_BY_STORE: Record<string, string> = {
  "No Frills": "/products/milk-nofrills.jpg",
  "Save-On-Foods": "/products/milk-saveonfoods.jpg",
  Safeway: "/products/milk-safeway.jpg",
};

const BY_KEYWORD: { test: RegExp; src: string }[] = [
  { test: /olive oil/i, src: "/products/olive-oil-bottle.jpg" },
  { test: /chicken/i, src: "/products/chicken-thighs.jpg" },
  { test: /egg/i, src: "/products/eggs.jpg" },
  { test: /milk/i, src: "/products/milk-nofrills.jpg" },
];

export function productImage(label: string): string | null {
  return BY_KEYWORD.find((m) => m.test.test(label))?.src ?? null;
}

/** Store-aware lookup for the deal carousel, where the same item shows a different store's packaging. */
export function productImageFor(label: string, store: string): string | null {
  if (/milk/i.test(label) && MILK_BY_STORE[store]) return MILK_BY_STORE[store];
  return productImage(label);
}
