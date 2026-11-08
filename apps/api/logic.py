"""Pure matching and basket rules. No I/O, so they are unit-tested in test_api.py.

Matching is exact: brand, item, variant and size must all be present on the user's item and equal the flyer's.
Words are compared as a set after lowercasing, stripping accents/punctuation and a trailing plural "s", so
"Dempster's®" == "dempsters" and "skinless boneless" == "boneless skinless", but "2%" != "1%" and
milk != chocolate milk.
Sizes may differ only by the imperial/metric rounding window in SIZE_WINDOW, except sold-by-weight listings.
"""
import re
import unicodedata
from statistics import median

from apps.api.models import Basket, Deal, ExtractedItem, FlyerItem, SplitLine, StoreTotal, UserItem
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
    size = f"{x.size_qty:g} {x.size_unit}" if x.size_qty and x.size_unit else ""
    return " ".join(p for p in (x.brand, x.item, x.variant, size) if p)


def _words(s: str | None) -> frozenset[str]:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().replace("'", "")
    s = re.sub(r"\s+%", "%", s)  # "2 %" (bilingual labels) == "2%"
    return frozenset(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w
                     for w in _WORD.findall(s))


def size_of(x: UserItem | FlyerItem) -> Size | None:
    return size_from(x.size_qty, x.size_unit)


def missing(u: UserItem) -> list[str]:
    """Fields the user still has to fill in before this item can match anything."""
    return [f for f in FIELDS if not (size_of(u) if f == "size" else _words(getattr(u, f)))]


def same_item(u: UserItem, f: FlyerItem) -> bool:
    if missing(u) or any(_words(getattr(u, k)) != _words(getattr(f, k)) for k in ("brand", "item", "variant")):
        return False
    want, have = size_of(u), size_of(f) or normalize_unit(f.raw_text or "")  # "$0.79 /lb" with no size field
    if have is None or have.unit != want.unit:
        return False
    if per_weight(f.raw_text or ""):  # "$0.69/lb": 2 lb of bananas is the same listing as 1 lb
        return True
    lo, hi = SIZE_WINDOW[want.unit]
    return lo <= have.qty / want.qty <= hi


def cost(listing: FlyerItem | Deal, user: UserItem) -> float:
    """What the user's size costs at this listing: unit price scaled to the user's size when known, else shelf price."""
    up = unit_price(1.0, size_of(user))  # (100 / qty) or (1 / count), so cost = unit_price / up[0]
    if listing.unit_price is not None and up and listing.unit == up[1]:
        return round(listing.unit_price / up[0], 2)
    return listing.price or 0.0


def deals_for(user_items: list[UserItem], flyer_items: list[FlyerItem]) -> list[Deal]:
    """Cheapest exact listing per (user item, store), with savings vs the cross-store median unit price."""
    out: list[Deal] = []
    for u in user_items:
        best: dict[str, FlyerItem] = {}
        for f in flyer_items:
            if f.price is not None and same_item(u, f) and (f.store not in best or cost(f, u) < cost(best[f.store], u)):
                best[f.store] = f
        prices = [f.unit_price for f in best.values() if f.unit_price is not None]
        mid = median(prices) if prices else None
        out += [Deal(
            user_id=u.user_id, user_item_id=u.user_item_id, flyer_item_id=f.item_id, store=f.store,
            price=f.price, unit_price=f.unit_price, unit=f.unit, cost=cost(f, u),
            savings_vs_median=None if mid is None or f.unit_price is None else round(mid - f.unit_price, 4),
            item_label=label(u), flyer_label=f.raw_text or label(f), week_start=f.week_start,
            page_id=f.page_id, page_no=f.page_no, bbox=f.bbox, valid_from=f.valid_from, valid_to=f.valid_to,
        ) for f in best.values()]
    return out


def cheapest(deals: list[Deal]) -> dict[str, Deal]:
    """user_item_id -> its cheapest listing across all stores (what tapping the item opens)."""
    best: dict[str, Deal] = {}
    for d in deals:
        if d.user_item_id not in best or d.cost < best[d.user_item_id].cost:
            best[d.user_item_id] = d
    return best


def basket(user_items: list[UserItem], deals: list[Deal]) -> Basket:
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
