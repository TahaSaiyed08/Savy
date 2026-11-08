"""This week's fake flyers. Shapes match realdeal.core.flyer_items so mock and real modes are interchangeable.

These canned flyers are what the API serves when live flyers are off (REALDEAL_LIVE_FLYERS=0: tests and CI);
otherwise apps/api/flyers_live.py supplies this week's real ones from Flipp.
"""
import re
from datetime import date, timedelta

from apps.api.models import FlyerItem
from shared.stores import STORES as _NAMES
from shared.units import normalize_unit, unit_price

# The canned flyers are laid out on a fake printed page: a 2-column, 4-row grid of tiles, ASPECT wide to tall, so the
# Price Match screen can highlight a tile even with no real picture behind it.
WEEK = date(2026, 11, 5)
STORES = list(_NAMES.values())
ASPECT = 0.62  # a portrait flyer page
_COLS, _ROWS_PER_PAGE = 2, 4

# Deliberately chosen cases for the matcher and the tests: the same item at several stores and sizes, "2 x 1.89 L" vs
# "4 L", words in a different order ("boneless skinless"), a sizeless banana sold per lb, and a "1%" milk next to "2%".
_ROWS = [  # store, brand, item, variant, size text, price
    ("Save-On-Foods", "Dairyland", "milk", "2%", "4 L", 6.49),
    ("Save-On-Foods", "Dairyland", "milk", "2%", "2 L", 4.29),
    ("Save-On-Foods", "Dairyland", "milk", "chocolate", "4 L", 6.99),
    ("Safeway", "Dairyland", "milk", "2%", "4 L", 5.99),
    ("Safeway", "Lucerne", "milk", "2%", "4 L", 5.49),
    ("Real Canadian Superstore", "Dairyland", "milk", "2%", "2 x 1.89 L", 6.79),
    ("No Frills", "Dairyland", "milk", "1%", "4 L", 5.29),
    ("Save-On-Foods", "Western Family", "eggs", "large", "12 ea", 4.99),
    ("No Frills", "No Name", "eggs", "large", "12 ea", 3.99),
    ("T&T", "Western Family", "eggs", "large", "18 ea", 6.29),
    ("Safeway", "Dole", "banana", "organic", "per lb", 0.99),
    ("T&T", "Dole", "banana", "organic", "per lb", 0.89),
    ("Real Canadian Superstore", "Dole", "banana", None, "per lb", 0.77),
    ("Real Canadian Superstore", "PC", "chicken thigh", "boneless skinless", "1 kg", 10.99),
    ("No Frills", "PC", "chicken thigh", "skinless boneless", "1 kg", 9.99),
    ("Save-On-Foods", "Western Family", "chicken thigh", "boneless skinless", "1 kg", 11.49),
    ("T&T", "Nissin", "instant noodle", "spicy", "5-pack 100 g", 3.99),
    ("Safeway", "Bertolli", "olive oil", "extra virgin", "1 L", 12.99),
    ("Save-On-Foods", "Bertolli", "olive oil", "extra virgin", "1 L", 13.99),
    ("Save-On-Foods", "Bertolli", "olive oil", "extra virgin", "500 mL", 7.99),
]


def _items() -> list[FlyerItem]:
    # Each store fills its own pages in order: `slots` counts how many tiles that store has placed so far.
    out, slots = [], {s: 0 for s in STORES}
    for i, (store, brand, item, variant, size_text, price) in enumerate(_ROWS):
        n, slots[store] = slots[store], slots[store] + 1
        # From the running count, work out which page and which grid cell this tile is in, then its box on the page.
        page_no, cell = n // (_COLS * _ROWS_PER_PAGE) + 1, n % (_COLS * _ROWS_PER_PAGE)
        x, y = cell % _COLS / _COLS, cell // _COLS / _ROWS_PER_PAGE
        size, raw = normalize_unit(size_text), " ".join(p for p in (brand, item, variant, size_text) if p)
        up = unit_price(price, size)
        out.append(FlyerItem(
            item_id=f"mock-{i}", page_id=f"mock-{store[:4].lower()}-{page_no}", store=store, week_start=WEEK,
            brand=brand, item=item, variant=variant, size_qty=size.qty if size else None,
            size_unit=size.unit if size else None, price=price,
            unit_price=up[0] if up else None, unit=up[1] if up else None, raw_text=raw,
            bbox=[round(x + 0.02, 3), round(y + 0.02, 3), round(x + 1 / _COLS - 0.02, 3),
                  round(y + 1 / _ROWS_PER_PAGE - 0.02, 3)],
            page_no=page_no, valid_from=WEEK, valid_to=WEEK + timedelta(days=6), page_aspect=ASPECT,
        ))
    return out


FLYER_ITEMS = _items()

# Every new device starts with these, pre-moved into the Basket, so Pantry and Basket are never empty in a demo.
SEED_ITEMS = [
    dict(brand="Dairyland", item="milk", variant="2%", size_qty=4, size_unit="l", in_basket=True),
    dict(brand="Western Family", item="eggs", variant="large", size_qty=12, size_unit="ea", in_basket=True),
    dict(brand="Dole", item="banana", variant="organic", size_qty=2, size_unit="lb", in_basket=True),
    dict(brand="PC", item="chicken thigh", variant="boneless skinless", size_qty=1, size_unit="kg", in_basket=True),
    dict(item="ramen", in_basket=True),  # incomplete: matches nothing until brand, variant and size are filled in
]


# Pantry staples worth starting a new user with, so the first screen shows real savings instead of an empty list.
_STAPLES = re.compile(r"\b(milk|eggs?|chicken|yogurt|bread|coffee|rice|cheese|butter)\b", re.I)


def _staple_seeds(flyers: list[FlyerItem]) -> list[dict]:
    """Staples from real listings, preferring ones several stores carry, so a new device's Pantry opens on real
    prices with a real "less than next store" gap."""
    stores: dict[tuple, set[str]] = {}
    for f in flyers:
        stores.setdefault((f.brand, f.item, f.variant, f.size_qty, f.size_unit), set()).add(f.store)
    # Rank by how many stores carry the product (more stores = a more meaningful "cheaper than the next store"),
    # and take one product per staple word, so there is one milk, one eggs, and so on.
    seeds, seen = [], set()
    ranked = sorted((k for k in stores if k[0] and k[3] and _STAPLES.search(k[1])),
                    key=lambda k: (-len(stores[k]), k[1]))
    for brand, item, variant, qty, unit in ranked:
        staple = _STAPLES.search(item).group(1).lower().rstrip("s")
        if staple in seen:
            continue
        seen.add(staple)
        seeds.append(dict(source="flyer", brand=brand, item=item, variant=variant, size_qty=qty, size_unit=unit,
                          in_basket=len(seeds) < 3))
        if len(seeds) == 5:
            break
    # The incomplete "ramen" item shows what an unfinished entry looks like, and exercises the closest-match list.
    return seeds + [dict(item="ramen", in_basket=True)]  # typed: shows the closest-match path


def seed_items(flyers: list[FlyerItem]) -> list[dict]:
    """What a new device starts with: the canned set for canned flyers, staples for live ones, nothing yet when the
    first fetch for its postal code hasn't landed."""
    if not flyers:
        return []
    return SEED_ITEMS if flyers[0].item_id.startswith("mock-") else _staple_seeds(flyers)
