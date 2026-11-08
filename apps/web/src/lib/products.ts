// Demo-only product photography, keyed by keyword and matched against the flyer's own label (never the
// user's item_label — the user's wording can drift from what's actually on sale). Generic, unbranded
// photos only, so we never picture a different brand than the deal. Word-bounded so "eggplant" doesn't
// match "egg". Items with no match fall back to a plain monogram tile in DealCard.
const BY_KEYWORD: { test: RegExp; src: string }[] = [
  { test: /\bolive oil\b/i, src: "/products/olive-oil-bottle.jpg" },
  { test: /\bchicken\b/i, src: "/products/chicken-thighs.jpg" },
  { test: /\begg\b/i, src: "/products/eggs.jpg" },
  { test: /\bmilk\b/i, src: "/products/milk-detail.jpg" },
];

export function productImage(flyerLabel: string): string | null {
  return BY_KEYWORD.find((m) => m.test.test(flyerLabel))?.src ?? null;
}
