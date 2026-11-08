/** Maps a product name to one of five thumbnail tints (--cat-N-bg / --cat-N-fg in globals.css). 0 = none. */
const RULES: [number, RegExp][] = [
  [1, /milk|cheese|yogh?urt|butter|cream|kefir/i],
  [2, /egg|banana|apple|orange|berr|grape|fruit|lemon/i],
  [3, /chicken|beef|pork|turkey|steak|bacon|sausage|salmon|fish|shrimp|meat|ham\b/i],
  [4, /oil|lettuce|spinach|kale|tomato|cucumber|pepper|onion|carrot|broccoli|vegetable|salad|avocado/i],
  [5, /rice|pasta|bread|flour|cereal|oat|noodle|bean|lentil|sugar|cracker|chip|cookie/i],
];

export function categoryOf(name?: string | null): number {
  if (!name) return 0;
  return RULES.find(([, re]) => re.test(name))?.[0] ?? 0;
}
