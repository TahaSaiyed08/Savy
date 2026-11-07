"""Pure matching and basket rules from the spec. No I/O, so they are unit-tested in test_api.py."""
import re
from statistics import median

from apps.api.models import Basket, Deal, ExtractedItem, FlyerItem, SplitLine, StoreTotal, UserItem
from shared.units import Size, normalize_unit, unit_price

MATCH_THRESHOLD = 0.75
_WORD = re.compile(r"[a-z0-9%]+")


def label(x: UserItem | FlyerItem | ExtractedItem) -> str:
    size = f"{x.size_qty:g} {x.size_unit}" if x.size_qty and x.size_unit else ""
    return " ".join(p for p in (x.brand, x.item, x.variant, size) if p)


def match_score(user: UserItem, flyer: FlyerItem) -> float:
    """Fraction of the user's item words present in the flyer item; 0 if a named brand differs.

    ponytail: word overlap stands in for AI Search in mock mode; the brand rule applies to both.
    """
    if user.brand and (flyer.brand or "").lower() != user.brand.lower():
        return 0.0
    want = set(_WORD.findall(f"{user.item} {user.variant or ''}".lower()))
    have = set(_WORD.findall(f"{flyer.item} {flyer.variant or ''} {flyer.raw_text or ''}".lower()))
    return len(want & have) / len(want) if want else 0.0


def deals_for(user_items: list[UserItem], flyer_items: list[FlyerItem]) -> list[Deal]:
    """Best match per (user item, store) above threshold, with savings vs the cross-store median."""
    out: list[Deal] = []
    for u in user_items:
        best: dict[str, tuple[float, FlyerItem]] = {}
        for f in flyer_items:
            s = match_score(u, f)
            if s >= MATCH_THRESHOLD and (f.store not in best or s > best[f.store][0]):
                best[f.store] = (s, f)
        prices = [f.unit_price for _, f in best.values() if f.unit_price is not None]
        mid = median(prices) if prices else None
        for s, f in best.values():
            out.append(Deal(
                user_id=u.user_id, user_item_id=u.user_item_id, flyer_item_id=f.item_id, store=f.store,
                price=f.price, unit_price=f.unit_price, unit=f.unit, match_score=round(s, 3),
                savings_vs_median=None if mid is None or f.unit_price is None else round(mid - f.unit_price, 4),
                item_label=label(u), flyer_label=f.raw_text or label(f),
            ))
    return out


def cost(deal: Deal, user: UserItem) -> float:
    """What this item costs at this store: unit price scaled to the user's size when known, else shelf price."""
    size = None
    if user.size_qty and user.size_unit:
        size = (Size(user.size_qty, "ea") if user.size_unit == "ea"
                else normalize_unit(f"{user.size_qty}{user.size_unit}"))
    up = unit_price(1.0, size)  # (100 / qty) or (1 / count), so cost = unit_price / up[0]
    if deal.unit_price is not None and up and deal.unit == up[1]:
        return round(deal.unit_price / up[0], 2)
    return deal.price or 0.0


def basket(user_items: list[UserItem], deals: list[Deal]) -> Basket:
    by_item = {u.user_item_id: u for u in user_items}
    stores = sorted({d.store for d in deals})
    per_store: dict[str, dict[str, float]] = {s: {} for s in stores}
    for d in deals:
        c = cost(d, by_item[d.user_item_id])
        per_store[d.store][d.user_item_id] = min(c, per_store[d.store].get(d.user_item_id, c))

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
    cheapest = totals[0] if totals else None
    return Basket(
        stores=totals,
        cheapest_store=cheapest.store if cheapest else None,
        split=split,
        split_total=split_total,
        # Apples to apples: split-shopping only the items the cheapest single store also carries.
        delta=round(cheapest.total - sum(x.cost for x in split if x.user_item_id in per_store[cheapest.store]), 2)
        if cheapest else 0.0,
        unmatched=[label(u) for uid, u in by_item.items() if not any(uid in v for v in per_store.values())],
    )
