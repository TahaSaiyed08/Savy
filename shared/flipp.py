"""Client + parsers for Flipp's public flyer API (backflipp.wishabi.com/flipp). Unofficial and unauthenticated,
so this is a polite citizen: a generic User-Agent, a timeout, one retry, and a minimum gap between requests.

Verified live 2026-11-07 for postal code V6T1Z4 (near UBC):
- GET /flyers?locale=en-ca&postal_code=<postal> -> {"flyers": [...]}. Fields used: id, merchant, valid_from,
  valid_to, categories_csv. A merchant can have more than one flyer (e.g. Superstore also runs a Toy Book);
  the weekly grocery flyer is the one whose categories_csv contains "Groceries".
- GET /flyers/{id}?locale=en-ca -> {"items": [...], "pages": [...], "has_corrections": bool}. List items have
  `price` as a plain numeric string, empty for ~14% of items (confirmed live). `pages[]` entries
  (id, left, bottom, right, top, page, name) carry NO image URL, confirmed live on five different flyers.
- GET /items/{item_id} -> {"item": {...}}. Adds `description` (often not a size, sometimes null),
  `current_price` (plain numeric string, can be empty), `image_url` (a product photo, about 353x400, not the
  flyer page: `http://f.wishabi.net/page_pdf_images/...`).

Used by apps/api/snapshot_flipp.py (mock-mode demo data). The pipeline's Flipp rows come from
databricks/fetchers/flipp.py, which also keeps each item's tile box, page and valid dates.
"""
import logging
import time
from datetime import date

import httpx

from apps.api.models import ExtractedItem, FlyerItem
from shared.stores import STORES
from shared.units import normalize_unit, unit_price

log = logging.getLogger(__name__)

BASE = "https://backflipp.wishabi.com/flipp"
USER_AGENT = "RealDeal/1.0 (+https://github.com/krish-arora-88/SurRealDeal; hackathon project, polite use)"
DEFAULT_POSTAL = "V6T1Z4"  # near UBC
THROTTLE_SECONDS = 0.5
TIMEOUT_SECONDS = 20.0
GROCERY_CATEGORY = "Groceries"

# Flipp merchant name -> our store key (shared/stores.py), confirmed against the live /flyers response.
MERCHANT_TO_STORE_KEY = {
    "Save-On-Foods": "save_on_foods",
    "Real Canadian Superstore": "superstore",
    "No Frills": "no_frills",
    "Safeway": "safeway",
    "T&T Supermarket": "tnt",
}

_last_call = 0.0


def _get(path: str, **params) -> dict:
    """Throttled GET with one retry. Raises on a second failure."""
    global _last_call
    wait = THROTTLE_SECONDS - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    headers = {"User-Agent": USER_AGENT}
    url = f"{BASE}{path}"
    try:
        r = httpx.get(url, params=params, headers=headers, timeout=TIMEOUT_SECONDS)
        r.raise_for_status()
    except httpx.HTTPError:
        log.warning("Flipp request failed, retrying once: %s", url, exc_info=True)
        time.sleep(THROTTLE_SECONDS)
        r = httpx.get(url, params=params, headers=headers, timeout=TIMEOUT_SECONDS)
        r.raise_for_status()
    finally:
        _last_call = time.monotonic()
    return r.json()


def list_weekly_flyers(postal_code: str = DEFAULT_POSTAL) -> list[dict]:
    """All flyers for a postal code (~90 near UBC). Filter with grocery_flyer_for()."""
    return _get("/flyers", locale="en-ca", postal_code=postal_code).get("flyers", [])


def grocery_flyer_for(flyers: list[dict], merchant: str) -> dict | None:
    """The Groceries flyer for a merchant (a merchant can also run non-grocery flyers, e.g. a Toy Book)."""
    for f in flyers:
        if f.get("merchant") == merchant and GROCERY_CATEGORY in (f.get("categories_csv") or ""):
            return f
    return None


def get_flyer_detail(flyer_id: int) -> dict:
    """{'items': [...], 'pages': [...], 'has_corrections': bool} for one flyer."""
    return _get(f"/flyers/{flyer_id}", locale="en-ca")


def get_item_detail(item_id: int) -> dict:
    """Full item record: description, current_price, image_url (the full flyer page this item sits on), ..."""
    return _get(f"/items/{item_id}")["item"]


def _price(raw) -> float | None:
    if raw in (None, ""):
        return None
    if isinstance(raw, int | float):
        return float(raw)
    try:
        return float(str(raw).replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def to_extracted_item(item: dict, detail: dict | None = None) -> ExtractedItem | None:
    """Parse a Flipp item (+ optional /items/{id} detail) into the common extraction shape.

    Size comes from `description` first (often not a size string in practice — confirmed live it's as often
    "Selected varieties" as an actual size), falling back to parsing it out of `name`, which usually has it
    (e.g. "NO NAME NATURALLY IMPERFECT MIXED SWEET PEPPERS, 2.5 LB"). None if there's no usable price —
    callers should skip the row entirely rather than save a priceless deal.
    """
    price = _price((detail or {}).get("current_price"))
    if price is None:
        price = _price(item.get("price")) or _price(item.get("current_price"))
    if price is None:
        return None
    name = item.get("name") or ""
    size = normalize_unit((detail or {}).get("description") or "") or normalize_unit(name)
    return ExtractedItem(
        brand=item.get("brand") or None,
        item=name,
        variant=None,
        size_qty=size.qty if size else None,
        size_unit=size.unit if size else None,
        price=price,
        confidence=0.95,  # structured first-party data, not OCR off a photo
    )


def flyer_item_from(
    x: ExtractedItem, *, item_id: str, page_id: str, store: str, week_start: date, raw_text: str
) -> FlyerItem:
    """Wrap a parsed ExtractedItem into a FlyerItem row, mirroring apps/api/mock_data.py's _item() helper."""
    size = normalize_unit(f"{x.size_qty}{x.size_unit}") if x.size_qty and x.size_unit else None
    up = unit_price(x.price, size) if x.price is not None else None
    return FlyerItem(
        item_id=item_id, page_id=page_id, store=store, week_start=week_start,
        brand=x.brand, item=x.item, variant=x.variant, size_qty=x.size_qty, size_unit=x.size_unit,
        price=x.price, unit_price=up[0] if up else None, unit=up[1] if up else None, raw_text=raw_text,
    )


def flyer_items_table_row(fi: FlyerItem, confidence: float = 0.95) -> dict:
    """The literal realdeal.core.flyer_items row shape: FlyerItem plus confidence/match_text, which the real
    table has (from the ai_query pipeline output) but the frozen FlyerItem Pydantic model doesn't carry.
    JSON-serializable (week_start as an ISO string) for both the sidecar file and SQL array parameters.
    """
    row = {key: value for key, value in fi.model_dump(mode="json").items() if key in FLYER_ITEM_COLUMNS}
    row["confidence"] = confidence
    row["match_text"] = " ".join(p for p in (fi.brand, fi.item, fi.variant,
                                              f"{fi.size_qty:g}{fi.size_unit}" if fi.size_qty and fi.size_unit else "")
                                 if p)
    return row


def _needs_detail(extracted: ExtractedItem | None, item: dict) -> bool:
    """Whether to spend an extra /items/{id} call: only when the list alone couldn't give a price or a size."""
    if extracted is None:
        return True  # no price yet; detail's current_price is the other chance
    return extracted.size_qty is None  # list had a price but no parseable size; try detail's description


def fetch_grocery_flyer(merchant: str, store_key: str, postal: str = DEFAULT_POSTAL) -> dict:
    """Fetch one store's weekly grocery flyer end to end: list -> pick the Groceries one -> items (+ detail
    only where the list alone isn't enough) -> parsed, price-having rows ready for the flyer_items table shape.

    Returns {"week": date, "pages": list[bytes], "rows": list[dict], "item_count": int, "sized_count": int}.
    `pages` is always [] today: confirmed live that Flipp's `pages[]` carries no image URL, and item-detail
    image_url points at a shared full-page image we'd otherwise have to fetch for every item just to dedupe —
    too many extra calls to an unofficial API for what this integration needs. `rows` is the real value.
    """
    flyer = grocery_flyer_for(list_weekly_flyers(postal), merchant)
    if flyer is None:
        raise RuntimeError(f"no Groceries flyer found for merchant={merchant!r} near {postal}")
    week = date.fromisoformat(flyer["valid_from"][:10])
    detail = get_flyer_detail(flyer["id"])
    raw_items = detail.get("items", [])
    page_id = f"flipp:{flyer['id']}"
    # The app's canonical display name (e.g. "Save-On-Foods"), not the Volume/store_key slug and not Flipp's
    # own merchant string (diverges for T&T: "T&T Supermarket" there vs. "T&T" everywhere else in this app).
    store_name = STORES.get(store_key, store_key)

    rows, sized = [], 0
    for it in raw_items:
        extracted = to_extracted_item(it)
        if _needs_detail(extracted, it):
            try:
                item_detail = get_item_detail(it["id"])
            except httpx.HTTPError:
                log.warning("couldn't fetch detail for Flipp item %s; using list data only",
                           it.get("id"), exc_info=True)
                item_detail = None
            if item_detail is not None:
                extracted = to_extracted_item(it, item_detail)
        if extracted is None:
            continue  # no price anywhere: skip
        if extracted.size_qty is not None:
            sized += 1
        fi = flyer_item_from(
            extracted, item_id=f"flipp-{it['id']}", page_id=page_id, store=store_name,
            week_start=week, raw_text=extracted.item,
        )
        rows.append(fi.model_dump(mode="json"))

    return {"week": week, "pages": [], "rows": rows, "item_count": len(raw_items), "sized_count": sized}
