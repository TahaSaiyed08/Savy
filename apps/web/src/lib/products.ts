// Demo-only product photography, matched against the flyer's own label (never the user's item_label —
// the user's wording can drift from what's actually on sale). Generic items (eggs, chicken, olive oil)
// show no retail brand in the photo, so any flyer entry is safe. Milk is the exception: every bundled
// milk photo IS a specific real brand, so it's matched by brand name, not store or filename — "milk-
// nofrills.jpg" and "milk-saveonfoods.jpg" are misleadingly named (they show Dairyland and Island Farms,
// matching neither store's actual flyer brand in mock_data.py) and are intentionally not referenced here.
// mock_data.py's milk brands: Dairyland (Save-On-Foods), Lucerne (Safeway), Neilson (No Frills, Real
// Canadian Superstore) — there's no accurate photo for Neilson, so those fall back to the monogram tile.
const BY_KEYWORD: { test: RegExp; src: string }[] = [
  { test: /\bdairyland\b/i, src: "/products/milk-detail.jpg" },
  { test: /\blucerne\b/i, src: "/products/milk-safeway.jpg" },
  { test: /\bolive oil\b/i, src: "/products/olive-oil-bottle.jpg" },
  { test: /\bchicken\b/i, src: "/products/chicken-thighs.jpg" },
  { test: /\begg\b/i, src: "/products/eggs.jpg" },
];

export function productImage(flyerLabel: string): string | null {
  return BY_KEYWORD.find((m) => m.test.test(flyerLabel))?.src ?? null;
}
