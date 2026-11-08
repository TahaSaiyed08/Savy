"""This week's fake flyers. Shapes match realdeal.core.flyer_items so mock and real modes are interchangeable.

FLYER_ITEMS loads apps/api/data/flipp_snapshot.json if it exists (made by `make flipp-snapshot`: real prices
from Flipp's public flyer API, see shared/flipp.py) and falls back to the small canned list below otherwise.
Mock mode never calls the network itself at request time -- the snapshot is a point-in-time file a human
refreshes by running the snapshot script, same spirit as the --from-dir screenshot fallback for fetchers.
"""
import json
import logging
from datetime import date
from pathlib import Path

from apps.api.models import FlyerItem
from shared.stores import STORES as _NAMES
from shared.units import normalize_unit, unit_price

log = logging.getLogger(__name__)
_SNAPSHOT = Path(__file__).parent / "data" / "flipp_snapshot.json"

WEEK = date(2026, 11, 5)
STORES = list(_NAMES.values())

_ROWS = [  # store, brand, item, variant, size text, price
    ("Save-On-Foods", "Dairyland", "milk", "2%", "4 L", 6.49),
    ("Safeway", "Lucerne", "milk", "2%", "4 L", 5.99),
    ("Real Canadian Superstore", "Neilson", "milk", "2%", "2 x 2 L", 6.79),
    ("No Frills", "Neilson", "milk", "2%", "4 L", 5.79),
    ("Save-On-Foods", None, "eggs", "large", "12 ea", 4.99),
    ("No Frills", "No Name", "eggs", "large", "12 ea", 3.99),
    ("T&T", None, "eggs", "large", "12 ea", 4.29),
    ("Safeway", None, "banana", None, "per lb", 0.69),
    ("T&T", None, "banana", None, "per lb", 0.59),
    ("Real Canadian Superstore", None, "banana", None, "per lb", 0.77),
    ("Real Canadian Superstore", "PC", "chicken thigh", "boneless skinless", "1 kg", 10.99),
    ("No Frills", "PC", "chicken thigh", "boneless skinless", "1 kg", 9.99),
    ("Save-On-Foods", "Western Family", "chicken thigh", "boneless skinless", "1 kg", 11.49),
    ("T&T", "Nissin", "instant noodle", "spicy", "5-pack 100 g", 3.99),
    ("Safeway", "Bertolli", "olive oil", "extra virgin", "1 L", 12.99),
    ("Save-On-Foods", "Bertolli", "olive oil", "extra virgin", "1 L", 13.99),
]


def _item(i: int, store, brand, item, variant, size_text, price) -> FlyerItem:
    size = normalize_unit(size_text)
    up = unit_price(price, size)
    return FlyerItem(
        item_id=f"mock-{i}", page_id=f"mock-{store[:4].lower()}-1", store=store, week_start=WEEK,
        brand=brand, item=item, variant=variant, size_qty=size.qty if size else None,
        size_unit=size.unit if size else None, price=price,
        unit_price=up[0] if up else None, unit=up[1] if up else None,
        raw_text=" ".join(p for p in (brand, item, variant, size_text) if p),
    )


def _load_flyer_items() -> list[FlyerItem]:
    if _SNAPSHOT.exists():
        try:
            data = json.loads(_SNAPSHOT.read_text())
            return [FlyerItem(**row) for row in data["rows"]]
        except Exception:
            log.warning("couldn't load %s; falling back to canned flyer data", _SNAPSHOT, exc_info=True)
    return [_item(i, *row) for i, row in enumerate(_ROWS)]


FLYER_ITEMS = _load_flyer_items()

# Every new device starts with these, pre-moved into the Basket, so Pantry/Add item(s)/Basket are never
# empty in a demo.
SEED_ITEMS = [
    dict(item="milk", variant="2%", size_qty=4, size_unit="l", in_basket=True),
    dict(item="eggs", variant="large", size_qty=12, size_unit="ea", in_basket=True),
    dict(item="banana", size_qty=2, size_unit="lb", in_basket=True),
    dict(brand="PC", item="chicken thigh", variant="boneless", size_qty=1, size_unit="kg", in_basket=True),
    dict(item="ramen", size_qty=None, size_unit=None, in_basket=True),  # no deal this week
]
