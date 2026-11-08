"""Pure matching and basket rules. No I/O, so they are unit-tested in test_api.py.

Matching is exact: brand, item, variant and size must all be present on the user's item and equal the flyer's.
Words are compared as a set after lowercasing, stripping accents/punctuation and a trailing plural "s", so
"Dempster's®" == "dempsters" and "skinless boneless" == "boneless skinless", but "2%" != "1%" and
milk != chocolate milk.
Sizes may differ only by the imperial/metric rounding window in SIZE_WINDOW, except sold-by-weight listings.
"""
import re
import unicodedata
from datetime import date
from functools import lru_cache
from statistics import median

from apps.api.models import (
    Basket,
    Deal,
    ExtractedItem,
    FlyerGroup,
    FlyerItem,
    FlyerListing,
    SplitLine,
    StoreTotal,
    UserItem,
)
from shared.units import Size, normalize_unit, per_weight, size_from, unit_price

# Allowed flyer size / wanted size, per base unit. Volume is asymmetric (-6 % / +10 %: a bit more is fine, noticeably
# less is not); mass allows about 10 % either way.
#   volume: 946 mL ~ 1 L, 1.89 L ~ 2 L, 3.78 L ~ 4 L (either way), but 750 mL != 1 L
#   mass:   454 g (1 lb) ~ 500 g, 907 g (2 lb) ~ 1 kg (either way)
#   count:  exact (a dozen is a dozen)
SIZE_WINDOW = {"ml": (0.94, 1.10), "g": (0.90, 1.11), "ea": (1.0, 1.0)}
FIELDS = ("brand", "item", "variant", "size")
_WORD = re.compile(r"[a-z0-9%]+")


def label(x: UserItem | FlyerItem | ExtractedItem) -> str:
    # The human-readable name shown everywhere: "Kraft Peanut Butter Smooth 1 kg", skipping whichever parts are blank.
    size = f"{x.size_qty:g} {x.size_unit}" if x.size_qty and x.size_unit else ""
    return " ".join(p for p in (x.brand, x.item, x.variant, size) if p)


@lru_cache(maxsize=50_000)  # every list read compares each item against every flyer tile
def _words(s: str | None) -> frozenset[str]:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().replace("'", "")
    s = re.sub(r"\s+%", "%", s)  # "2 %" (bilingual labels) == "2%"
    # Drop a trailing plural "s" so "eggs" == "egg", but keep "ss" words ("grass") and short words ("gas", "bus").
    return frozenset(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w
                     for w in _WORD.findall(s))


def size_of(x: UserItem | FlyerItem) -> Size | None:
    # The size as a base-unit quantity (millilitres, grams or each) so 2 L and 2000 mL are the same number.
    return size_from(x.size_qty, x.size_unit)


def missing(u: UserItem) -> list[str]:
    """Fields the user still has to fill in before this item can match anything.

    Empty for an item added from a flyer: its fields are the listing's, so a blank one means the flyer has none too.
    The API only keeps source="flyer" on items that are a listing (is_listing); clients can't claim it.
    """
    if u.source == "flyer":
        return []
    return [f for f in FIELDS if not (size_of(u) if f == "size" else _words(getattr(u, f)))]


def same_item(u: UserItem, f: FlyerItem) -> bool:
    # The one rule for "this listing is the person's item": every field filled in, and every field equal.
    return not missing(u) and _identical(u, f)


def is_listing(x: UserItem | ExtractedItem, flyers: list[FlyerItem]) -> bool:
    """Whether x really is a current listing. Only then may it be a source="flyer" item, which skips missing()."""
    return any(_identical(x, f) for f in flyers)


def _identical(u: UserItem | ExtractedItem, f: FlyerItem) -> bool:
    # Words must match exactly for brand/item/variant (so "2%" never matches "1%", and "milk" never matches
    # "chocolate milk"); only the size gets a tolerance window.
    if any(_words(getattr(u, k)) != _words(getattr(f, k)) for k in ("brand", "item", "variant")):
        return False
    want = size_of(u)
    if want is None:  # only a flyer-added item gets here: its size is its listing's, and that listing has none
        return size_of(f) is None
    # Some flyers only print the size inside the tile text, so fall back to reading it from there.
    have = size_of(f) or normalize_unit(f.raw_text or "")  # "$0.79 /lb" with no size field
    if have is None or have.unit != want.unit:
        return False
    if per_weight(f.raw_text or ""):  # "$0.69/lb": 2 lb of bananas is the same listing as 1 lb
        return True
    lo, hi = SIZE_WINDOW[want.unit]
    return lo <= have.qty / want.qty <= hi


def cost(listing: FlyerItem | Deal, user: UserItem) -> float:
    # Compare listings by what the person would actually pay for their amount: a bigger pack with a lower unit price
    # can win even when its sticker price is higher.
    """What the user's size costs at this listing: unit price scaled to the user's size when known, else shelf price."""
    up = unit_price(1.0, size_of(user))  # (100 / qty) or (1 / count), so cost = unit_price / up[0]
    if listing.unit_price is not None and up and listing.unit == up[1]:
        return round(listing.unit_price / up[0], 2)
    return listing.price or 0.0


def deals_for(user_items: list[UserItem], flyer_items: list[FlyerItem]) -> list[Deal]:
    """Cheapest exact listing per (user item, store), with savings vs the cross-store median unit price."""
    out: list[Deal] = []
    for u in user_items:
        # One deal per store: if a store lists the item twice (two pages), keep its cheaper listing.
        best: dict[str, FlyerItem] = {}
        for f in flyer_items:
            if f.price is not None and same_item(u, f) and (f.store not in best or cost(f, u) < cost(best[f.store], u)):
                best[f.store] = f
        # "Savings vs median" is how far under the typical store this one is, so it needs unit prices to compare.
        prices = [f.unit_price for f in best.values() if f.unit_price is not None]
        mid = median(prices) if prices else None
        out += [Deal(
            user_id=u.user_id, user_item_id=u.user_item_id, flyer_item_id=f.item_id, store=f.store,
            price=f.price, unit_price=f.unit_price, unit=f.unit, cost=cost(f, u),
            savings_vs_median=None if mid is None or f.unit_price is None else round(mid - f.unit_price, 4),
            item_label=label(u), flyer_label=f.raw_text or label(f), week_start=f.week_start,
            page_id=f.page_id, page_no=f.page_no, bbox=f.bbox, valid_from=f.valid_from, valid_to=f.valid_to,
            image_url=f.image_url, regular_price=f.regular_price, conditions=f.conditions,
            store_url=f.store_url,
        ) for f in best.values()]
    return out


def cheapest(deals: list[Deal]) -> dict[str, Deal]:
    # Ties keep whichever deal came first, so the result is stable between requests.
    """user_item_id -> its cheapest listing across all stores (what tapping the item opens)."""
    best: dict[str, Deal] = {}
    for d in deals:
        if d.user_item_id not in best or d.cost < best[d.user_item_id].cost:
            best[d.user_item_id] = d
    return best


def _browse_key(f: FlyerItem) -> tuple:
    """Groups listings of the same product across stores for the Flyers tab. Unlike same_item, this is flyer-vs-
    flyer: no size tolerance window (two listings need the same words and the same size to be "the same row"),
    since it's picking one browse row per product, not deciding whether a listing matches what a user typed."""
    size = size_of(f)
    return (_words(f.brand), _words(f.item), _words(f.variant), round(size.qty, 1) if size else None,
            size.unit if size else None)


def listing(f: FlyerItem) -> FlyerListing:
    return FlyerListing(
        label=label(f), store=f.store, price=f.price, unit_price=f.unit_price, unit=f.unit, flyer_item_id=f.item_id,
        page_id=f.page_id, page_no=f.page_no, bbox=f.bbox, valid_from=f.valid_from, valid_to=f.valid_to,
        image_url=f.image_url, regular_price=f.regular_price, conditions=f.conditions,
        store_url=f.store_url,
    )


def saves_vs_next(deals: list[Deal]) -> dict[str, float]:
    # The "$X less than the next store" badge: the gap between the cheapest and second-cheapest store.
    """user_item_id -> how much less its cheapest store is than the next one. Absent with one store or a tie."""
    costs: dict[str, list[float]] = {}
    for d in deals:
        costs.setdefault(d.user_item_id, []).append(d.cost)
    return {uid: round(c[1] - c[0], 2) for uid, c in ((u, sorted(v)) for u, v in costs.items())
            if len(c) > 1 and c[1] > c[0]}


_SIZE_WORD = re.compile(r"\d+(?:\.\d+)?(?:l|ml|g|kg|lb|lbs|oz|ea|ct|pk)?|l|ml|g|kg|lb|lbs|oz|ea|ct|pk|pack|x")


def _query_words(q: str | None) -> frozenset[str]:
    """What someone typed, as words, without the size ("milk 4 L" -> milk): sizes are compared separately."""
    return frozenset(w for w in _words(q) if not _SIZE_WORD.fullmatch(w))


def _listing_words(f: FlyerItem) -> frozenset[str]:
    return _words(" ".join(p for p in (f.brand, f.item, f.variant, f.raw_text) if p))


def _starts(tokens: frozenset[str], words: frozenset[str]) -> bool:
    """Every token begins some word, so results appear while the last word is still half typed."""
    return all(any(w.startswith(t) for w in words) for t in tokens)


def _split_query(q: frozenset[str]) -> tuple[frozenset[str], frozenset[str]]:
    """(required, preferred): the words that must be found, and numbers like "2%" that only rank listings higher,
    so "2% milk" still finds milk in a week with no 2%."""
    required = frozenset(w for w in q if w.isalpha())
    return (required, q - required) if required else (q, frozenset())


def _head_miss(q: frozenset[str], item: str) -> bool:
    """True when no typed word starts the item's last word. The last word is the thing itself: "Brown Eggs" is eggs,
    "Egg Nog" is not."""
    last = _words(item.split()[-1]) if item.split() else frozenset()
    return not any(w.startswith(t) for t in q for w in last)


def closest(u: UserItem, flyer_items: list[FlyerItem], n: int = 5) -> list[FlyerListing]:
    """Listings that name what the user typed, nearest first, for items with no exact listing.

    Only the item's words have to be found; a matching brand, variant and size rank a listing higher.
    """
    required, preferred = _split_query(_query_words(u.item))
    if not required:
        return []
    brand, variant, size = _query_words(u.brand), _query_words(u.variant), size_of(u)
    ranked = []
    for f in flyer_items:
        words = _listing_words(f)
        if f.price is None or not _starts(required, words):
            continue
        item_words, fsize = _words(f.item), size_of(f)
        ranked.append((
            (not _starts(required, item_words), _head_miss(required, f.item), not required <= item_words,
             bool(brand) and not _starts(brand, _words(f.brand)),
             bool(preferred | variant) and not _starts(preferred | variant, words),
             len(item_words - required - preferred), bool(size) and not (fsize and fsize.unit == size.unit), f.price),
            f.item_id, f))
    ranked.sort(key=lambda r: r[:2])
    named = [r for r in ranked if not r[0][0]]  # the item's own name has the words, not just the small print
    return [listing(f) for *_, f in (named if len(named) >= 2 else ranked)[:n]]


def _sort_key(sort: str, q: frozenset[str]):
    if sort == "relevance" and q:
        # Products named by the search come first, then the ones where it is the main noun, then the plainest
        # and most widely sold, then cheapest.
        required, preferred = _split_query(q)

        def relevance(g: FlyerGroup):
            name = _words(" ".join(p for p in (g.brand, g.item, g.variant) if p))
            item = _words(g.item)
            return (not _starts(required, item), _head_miss(required, g.item), not required <= item,
                    bool(preferred) and not _starts(preferred, name), len(item - q), -g.store_count,
                    g.cheapest.price or 0)

        return relevance
    return {
        "price": lambda g: g.cheapest.price or 0,
        "ends": lambda g: g.cheapest.valid_to or date.max,
        "az": lambda g: 0,
    }.get(sort, lambda g: -(g.saves_vs_next or 0))


def browse_flyers(flyer_items: list[FlyerItem], q: str | None = None, store: str | None = None,
                  sort: str = "savings", category: str | None = None) -> list[FlyerGroup]:
    """Every priced listing as one row per product with its cheapest store. store limits rows to what it carries."""
    groups: dict[tuple, list[FlyerItem]] = {}
    for f in flyer_items:
        if f.price is not None:
            groups.setdefault(_browse_key(f), []).append(f)

    q_words = _query_words(q)
    if q and q.strip() and not q_words:  # only a size was typed: nothing to look for
        return []
    needed = _split_query(q_words)[0] if sort == "relevance" else q_words  # relevance only requires the plain words
    out = []
    for rows in groups.values():
        if category and rows[0].category != category:
            continue
        shown = [f for f in rows if not store or f.store == store]
        if not shown or (needed and not _starts(needed, _listing_words(rows[0]))):
            continue
        best = min(shown, key=lambda f: f.price)
        others = [f.price for f in rows if f.store != best.store]
        # Only comparable when the size is known: a sizeless "Bathroom Tissue" is a different pack at each store.
        saves = round(min(others) - best.price, 2) if others and best.size_qty and min(others) > best.price else None
        out.append(FlyerGroup(
            brand=best.brand, item=best.item, variant=best.variant, size_qty=best.size_qty, size_unit=best.size_unit,
            store_count=len({f.store for f in rows}), saves_vs_next=saves, cheapest=listing(best),
            category=best.category,
        ))
    if sort == "relevance" and needed:  # "Soy Sauce, great for ramen" is not a ramen: small print only fills gaps
        named = [g for g in out if _starts(needed, _words(g.item))]
        out = named if len(named) >= 2 else out
    primary = _sort_key(sort, q_words)
    out.sort(key=lambda g: (primary(g), g.item.lower(), (g.brand or "").lower(), (g.variant or "").lower(),
                            g.size_qty or 0))
    return out


def basket(user_items: list[UserItem], deals: list[Deal]) -> Basket:
    # Prices the whole list two ways: all at one store (a store missing items ranks below one that has them all), or
    # split so each item is bought at its cheapest store. `delta` is what splitting saves over the best single store.
    by_item = {u.user_item_id: u for u in user_items}
    stores = sorted({d.store for d in deals if d.user_item_id in by_item})
    per_store: dict[str, dict[str, float]] = {s: {} for s in stores}
    for d in deals:
        if d.user_item_id in by_item:
            per_store[d.store][d.user_item_id] = min(d.cost, per_store[d.store].get(d.user_item_id, d.cost))

    totals = sorted(
        (StoreTotal(store=s, total=round(sum(v.values()), 2), matched=len(v), missing=len(by_item) - len(v))
         for s, v in per_store.items()),
        key=lambda t: (t.missing, t.total),
    )
    split = []
    for uid, u in by_item.items():
        offers = [(per_store[s][uid], s) for s in stores if uid in per_store[s]]
        if offers:
            c, s = min(offers)
            split.append(SplitLine(user_item_id=uid, item_label=label(u), store=s, cost=c))
    split_total = round(sum(line.cost for line in split), 2)
    best = totals[0] if totals else None
    return Basket(
        stores=totals,
        cheapest_store=best.store if best else None,
        split=split,
        split_total=split_total,
        # Apples to apples: split-shopping only the items the cheapest single store also carries.
        delta=round(best.total - sum(x.cost for x in split if x.user_item_id in per_store[best.store]), 2)
        if best else 0.0,
        unmatched=[label(u) for uid, u in by_item.items() if not any(uid in v for v in per_store.values())],
    )
