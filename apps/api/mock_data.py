"""This week's fake flyers. Shapes match realdeal.core.flyer_items so mock and real modes are interchangeable.

The rows are chosen to show exact matching: near-misses (2 L vs 4 L, 1% vs 2%, chocolate, other brands) sit next to
true matches, including 2 x 1.89 L for 4 L and a per-lb price.
"""
from datetime import date, timedelta

from apps.api.models import FlyerItem
from shared.stores import STORES as _NAMES
from shared.units import normalize_unit, unit_price

WEEK = date(2026, 11, 5)
STORES = list(_NAMES.values())
ASPECT = 0.62  # a portrait flyer page
_COLS, _ROWS_PER_PAGE = 2, 4

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
    out, slots = [], {s: 0 for s in STORES}
    for i, (store, brand, item, variant, size_text, price) in enumerate(_ROWS):
        n, slots[store] = slots[store], slots[store] + 1
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

# Every new device starts with these so My List and Basket are never empty in a demo.
SEED_ITEMS = [
    dict(brand="Dairyland", item="milk", variant="2%", size_qty=4, size_unit="l", in_basket=True),
    dict(brand="Western Family", item="eggs", variant="large", size_qty=12, size_unit="ea", in_basket=True),
    dict(brand="Dole", item="banana", variant="organic", size_qty=2, size_unit="lb"),
    dict(brand="PC", item="chicken thigh", variant="boneless skinless", size_qty=1, size_unit="kg", in_basket=True),
    dict(item="ramen"),  # incomplete: matches nothing until brand, variant and size are filled in
]
