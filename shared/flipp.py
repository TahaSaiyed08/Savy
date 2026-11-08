"""Client + parsers for Flipp's public flyer API (backflipp.wishabi.com/flipp). Unofficial and unauthenticated,
so this is a polite citizen: an identifying User-Agent, a timeout, one retry, and at most WORKERS requests in flight.

Verified live 2026-11-07 for postal code V6T1Z4 (near UBC):
- GET /flyers?locale=en-ca&postal_code=<postal> -> {"flyers": [...]}. Fields used: id, merchant, valid_from,
  valid_to, categories_csv. A merchant can have more than one flyer (e.g. Superstore also runs a Toy Book);
  the weekly grocery flyer is the one whose categories_csv contains "Groceries".
- GET /flyers/{id}?locale=en-ca -> {"items": [...], "pages": [...], "has_corrections": bool}. List items have
  `price` as a plain numeric string, empty for ~14% of items (confirmed live). `pages[]` entries
  (id, left, bottom, right, top, page, name) carry NO image URL of their own. The flyer record instead has a `path`,
  `width`, `height` and `resolutions`, from which the page picture is stitched out of 256 px tiles (render_page).
- GET /items/{item_id} -> {"item": {...}}. Adds `description` (often not a size, sometimes null),
  `current_price` (plain numeric string, can be empty), `image_url` (a product photo, about 353x400, not the
  flyer page: `http://f.wishabi.net/page_pdf_images/...`).

Used by apps/api/flyers_live.py, which keeps each postal code's flyers fresh while the API runs. The pipeline's
Flipp rows come from databricks/fetchers/flipp.py, which also keeps each item's tile box, page and valid dates.
"""
import io
import logging
import math
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import NamedTuple

import httpx
from PIL import Image

from apps.api.models import ExtractedItem, FlyerItem, clean_store_url
from shared.stores import STORES
from shared.units import normalize_unit, unit_price

log = logging.getLogger(__name__)

# Where things live. BASE is the JSON API; TILES is a separate image host. Neither needs a key, which is also why
# the limits below (timeout, one retry, a small worker pool) are kept modest.
BASE = "https://backflipp.wishabi.com/flipp"
TILES = "https://f.wishabi.net"  # flyer images: a zoom pyramid of 256 px tiles, <path><level>_<col>_<row>.jpg
USER_AGENT = "Savy/1.0 (+https://github.com/krish-arora-88/SurRealDeal; hackathon project, polite use)"
DEFAULT_POSTAL = "V6T1Z4"  # near UBC
RETRY_SECONDS = 0.5
TIMEOUT_SECONDS = 20.0
WORKERS = 6  # item details in flight at once: a whole flyer in seconds, without hammering an unofficial API
TILE = 256
# A stitched page is the sharpest zoom level that stays under these limits, so a page is always a ~1 MB JPEG whether
# the flyer was cut for phones or for print.
PAGE_MAX_PIXELS = 4_000_000  # a stitched page stays about 1 MB however big the flyer
PAGE_MAX_HEIGHT = 2700
# Keeping ten stores per postal code bounds both the download time and the size of the saved copy.
MAX_STORES = 10  # flyers kept per postal code, best-ranked by Flipp first
GROCERY_CATEGORY = "Groceries"
# Saved feeds record the version of the parser that made them (see flyers_live._read), so improving how names or
# sizes are read only needs this number raised to roll the improvement out to every cached copy.
PARSER_VERSION = 4  # bump when name/size parsing changes: saved flyers from an older parser are downloaded again

# Grocery chains worth showing (Flipp merchant names, case-insensitive). Flipp also lists brand flyers ("President's
# Choice"), warehouse clubs and corner shops, which would crowd out the stores a shopper can price-match at.
CHAINS = {c.casefold() for c in (
    "Save-On-Foods", "Real Canadian Superstore", "No Frills", "Safeway", "T&T Supermarket", "Walmart", "Loblaws",
    "Zehrs", "Fortinos", "Provigo", "Maxi", "Valu-mart", "Your Independent Grocer", "Metro", "Food Basics", "Super C",
    "FreshCo", "Sobeys", "IGA", "Foodland", "Farm Boy", "Thrifty Foods", "Giant Tiger", "Calgary Co-op",
    "Buy-Low Foods", "PriceSmart Foods", "Longo's", "Choices Markets", "Nesters Market", "Urban Fare",
    "Whole Foods Market",
)}
# Flipp's merchant names are sometimes longer than the name shoppers know; these are shown instead.
DISPLAY_NAMES = {"t&t supermarket": "T&T", "pricesmart foods": "PriceSmart Foods"}

# Flipp merchant name -> our store key (shared/stores.py), confirmed against the live /flyers response.
MERCHANT_TO_STORE_KEY = {
    "Save-On-Foods": "save_on_foods",
    "Real Canadian Superstore": "superstore",
    "No Frills": "no_frills",
    "Safeway": "safeway",
    "T&T Supermarket": "tnt",
}

# Name-parsing patterns used by split_name below, each tuned against real flyer text:
#   _MULTI    a multi-buy price ("2/ $7.50") applies to that many units
#   _OR       "X or Y" tiles advertise several products under one price and size
#   _SIZE_TAIL the trailing "2.5 LB" / "375 g" that belongs to the size, not the name
#   _VARIANTS  qualifiers (2%, organic, boneless...) that go in the variant column rather than the item name
_MULTI = re.compile(r"^\s*(\d+)\s*(?:/|for\b)", re.I)  # pre_price_text "2/" or "2 for"
_OR = re.compile(r"\s+or\s+", re.I)
_MARKS = re.compile("[®™©]")
_SMALL = {"or", "and", "with", "of", "the", "in", "for"}
_COUNT_S = re.compile(r"(\d+)'s\b", re.I)  # "4'S" -> 4 ea
_SIZE_TAIL = re.compile(r"\s*\d[\d./x×=-]*\s*(?:kg|mg|g|ml|l|lbs?|oz|'s|pack|pk|ct|ea)\b.*$", re.I)
_VARIANTS = re.compile(
    r"\b(?:\d(?:\.\d+)?\s*%|skim|homogenized|organic|free[- ]range|boneless|skinless|extra virgin|unsalted|salted"
    r"|lactose[- ]free|large|medium|small)(?![a-z])", re.I)


def _fold(s: str) -> str:
    # Lowercase with accents flattened, so "Crème" compares equal to "creme" when checking whether a name starts with
    # its brand.
    return unicodedata.normalize("NFKD", s).encode("ascii", "replace").decode().lower()


# One shared client (connection pooling), safe across threads. The pool is sized a little above WORKERS so a retry
# never has to wait for a free connection.
_http = httpx.Client(timeout=TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}, follow_redirects=True,
                     limits=httpx.Limits(max_connections=WORKERS + 2))


def _get(path: str, **params) -> dict:
    """GET with one retry. Raises on a second failure. Safe to call from several threads."""
    url = f"{BASE}{path}"
    try:
        r = _http.get(url, params=params)
        r.raise_for_status()
    except httpx.HTTPError:
        log.warning("Flipp request failed, retrying once: %s", url, exc_info=True)
        time.sleep(RETRY_SECONDS)
        r = _http.get(url, params=params)
        r.raise_for_status()
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


def display_name(merchant: str) -> str:
    return DISPLAY_NAMES.get(merchant.casefold(), merchant)


# Which of the ~90 flyers near a postal code to show: only real grocery chains (CHAINS), and per chain the widest
# grocery flyer, because a chain can publish several (weekly, regional, a themed catalogue).
def chain_flyers(flyers: list[dict], limit: int = MAX_STORES) -> dict[str, dict]:
    """store display name -> that chain's widest grocery flyer, best-ranked chains first. Flipp's `priority` is its
    own ranking for the postal code; a chain can run several grocery flyers, and the widest is the weekly one."""
    best: dict[str, dict] = {}
    for f in sorted(flyers, key=lambda f: f.get("priority", 99)):
        merchant = f.get("merchant") or ""
        if merchant.casefold() not in CHAINS or GROCERY_CATEGORY not in (f.get("categories_csv") or ""):
            continue
        store = display_name(merchant)
        if store not in best or f.get("width", 0) > best[store].get("width", 0):
            best[store] = f
    return dict(list(best.items())[:limit])


def grocery_flyers_for(postal_code: str = DEFAULT_POSTAL) -> dict[str, dict]:
    """One request: the grocery chains' current flyers near a postal code, keyed by store name."""
    return chain_flyers(list_weekly_flyers(postal_code))


def get_flyer_detail(flyer_id: int) -> dict:
    """{'items': [...], 'pages': [...], 'has_corrections': bool} for one flyer."""
    return _get(f"/flyers/{flyer_id}", locale="en-ca")


def get_item_detail(item_id: int) -> dict:
    """Full item record: description, current_price, image_url (the full flyer page this item sits on), ..."""
    return _get(f"/items/{item_id}")["item"]


def _price(raw) -> float | None:
    # Flipp prices arrive as strings ("3.99", "$3.99", "") or numbers; anything unreadable is "no price", never zero.
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
    # Prefer the item's detail record, whose price is the up-to-date one; fall back to the flyer list's own copy.
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
        confidence=0.95,  # structured first-party data, not OCR off a photo (so the app never asks to confirm it)
    )


def flyer_item_from(
    x: ExtractedItem, *, item_id: str, page_id: str, store: str, week_start: date, raw_text: str, **placement
) -> FlyerItem:
    """Wrap a parsed ExtractedItem into a FlyerItem row, mirroring apps/api/mock_data.py's _item() helper."""
    # Unit price (per 100 g, per 100 ml or per each) is what makes a 2 L and a 4 L jug comparable.
    size = normalize_unit(f"{x.size_qty}{x.size_unit}") if x.size_qty and x.size_unit else None
    up = unit_price(x.price, size) if x.price is not None else None
    return FlyerItem(
        item_id=item_id, page_id=page_id, store=store, week_start=week_start,
        brand=x.brand, item=x.item, variant=x.variant, size_qty=x.size_qty, size_unit=x.size_unit,
        price=x.price, unit_price=up[0] if up else None, unit=up[1] if up else None, raw_text=raw_text, **placement,
    )


def _title(item: str) -> str:
    words = item.split()
    return " ".join(w.lower() if i and w.lower() in _SMALL else w.capitalize() for i, w in enumerate(words))


def split_name(brand: str | None, name: str) -> tuple[str | None, str, str | None]:
    """(brand, item, variant) from Flipp's one free-text name. A tile can advertise several products; the first wins.

    "NO NAME® MIXED SWEET PEPPERS, 2.5 LB" -> ("no name", "Mixed Sweet Peppers", None)
    "PC® MILK OR DARK CHOCOLATE COVERED ALMONDS, 70 G" is one product, not "Milk": a lone word before "or" is a
    flavour, not a product.
    """
    # Strip the trademark symbols, then split "A or B" into candidate products; the first product names the row.
    brand = _MARKS.sub("", (brand or "").split("|")[0]).strip() or None
    clean = _MARKS.sub("", name)
    products = _OR.split(clean)

    def head(text: str) -> str:
        return _SIZE_TAIL.sub("", text.split(",")[0]).strip()

    def unbranded(text: str) -> str:
        return text[len(brand):].strip() if brand and _fold(text).startswith(_fold(brand)) else text

    # The three cases below are the real-world shapes seen in flyers: a brand-only first part, a one-word flavour
    # before "or", and the ordinary case where the first product is simply the first.
    first = unbranded(head(products[0]))
    if not first and len(products) > 1:  # "PC OR BLUE MENU ENTREES": the product is named after the "or"
        first = head(products[1])
    elif len(first.split()) == 1 and len(products) > 1 and len(head(products[1]).split()) >= 3:
        first = unbranded(head(clean))
    first = first or clean.split(",")[0].strip()
    # Pull qualifiers like "2%" or "organic" out of the name into `variant`, so "Organic Milk" and "Milk" are not equal.
    variants = [" ".join(m.group(0).lower().split()) for m in _VARIANTS.finditer(first)]
    item = " ".join(_VARIANTS.sub(" ", first).split()) or first
    if item.isupper():  # flyers shout in capitals; show Title Case, keeping small words like "of" lower
        item = _title(item)
    return brand, item, " ".join(variants) or None


def store_url(raw: str | None) -> str | None:
    """The store's own page for an item, from Flipp's ttm_url (see models.clean_store_url)."""
    return clean_store_url(raw)


def _size_of_name(name: str):
    """The size printed in a tile's name. "X or Y, 375 g" prints it once, after the last product, for all of them."""
    return normalize_unit(_COUNT_S.sub(r"\1 ea", _OR.split(name)[0])) or normalize_unit(_COUNT_S.sub(r"\1 ea", name))


def _placement(item: dict, flyer: dict, pages: list[dict]) -> dict | None:
    """Where the tile sits on its page, as fractions with the origin top-left. Flipp's y axis points up."""
    # A tile belongs to the page its horizontal centre falls in. Flipp lays all pages side by side in one coordinate
    # space, and a tile can straddle a page edge.
    cx = (item["left"] + item["right"]) / 2
    page = next((p for p in pages if p["left"] <= cx < p["right"]), None)
    if page is None:
        return None
    # Convert to fractions of the page. The y axis points up in Flipp and down on screens, hence top/bottom swapped.
    w, h = page["right"] - page["left"], page["top"] - page["bottom"]
    box = [(item["left"] - page["left"]) / w, (page["top"] - item["top"]) / h,
           (item["right"] - page["left"]) / w, (page["top"] - item["bottom"]) / h]
    return {
        "page_id": f"flipp-{flyer['id']}-{page['page']}", "page_no": page["page"], "page_aspect": round(w / h, 4),
        "bbox": [round(min(max(v, 0.0), 1.0), 4) for v in box],
        "valid_from": flyer["valid_from"][:10], "valid_to": flyer["valid_to"][:10],
        # The product's own cutout picture, upgraded to https so the app never loads mixed content.
        "image_url": (item.get("cutout_image_url") or "").replace("http://", "https://", 1) or None,
    }


def _row(item: dict, detail: dict, flyer: dict, pages: list[dict], store: str, week: date) -> FlyerItem | None:
    """A priced flyer tile as a FlyerItem, or None when it has no price or isn't on a page."""
    where = _placement(item, flyer, pages)
    price = _price(detail.get("current_price")) or _price(item.get("price"))
    if where is None or price is None:
        return None
    # "2 for $7.50" is $3.75 each: store the per-unit price so comparisons and savings are in the same terms.
    multi = _MULTI.match(detail.get("pre_price_text") or "")
    if multi and int(multi[1]) > 1:  # "2/ $7.50": the price is for that many units
        price = round(price / int(multi[1]), 2)
    name = item.get("name") or ""
    brand, product, variant = split_name(item.get("brand"), name)
    # The name usually carries the size; the item's description is only a fallback (it is often "Selected varieties").
    size = _size_of_name(name) or normalize_unit(detail.get("description") or "")
    x = ExtractedItem(brand=brand, item=product, variant=variant, size_qty=size.qty if size else None,
                      size_unit=size.unit if size else None, price=price, confidence=0.95)
    # Keep the text exactly as printed (name plus price text): some sizes and "/lb" rules are only readable from it.
    raw = " ".join(p for p in (name, detail.get("price_text")) if p)
    return flyer_item_from(
        x, item_id=f"flipp-{item['id']}", store=store, week_start=week, raw_text=raw,
        regular_price=_price(detail.get("original_price")), conditions=detail.get("sale_story") or None,
        store_url=store_url(detail.get("ttm_url")), **where,
    )


def fetch_flyer(flyer: dict, store: str) -> dict:
    """One flyer as flyer_items rows, each with its tile box, page, dates and cutout image.

    Every tile needs its /items/{id} detail: without pre_price_text a "2/ $7.50" price would read as one unit's.
    The details are fetched WORKERS at a time, so a 300-item flyer takes seconds, not minutes.
    Returns {"week": date, "rows": list[dict], "item_count": int, "sized_count": int}.
    """
    # Two kinds of requests: one for the flyer's tile list, then one per tile for its detail, in parallel batches.
    week = date.fromisoformat(flyer["valid_from"][:10])
    detail = get_flyer_detail(flyer["id"])
    raw_items = detail.get("items", [])
    pages = sorted(detail.get("pages", []), key=lambda p: p["left"])
    products = [it for it in raw_items if it.get("display_type") == 1]  # not banners or page furniture

    # A tile whose detail can't be fetched is skipped, not guessed: without it we can't tell a "2 for" price.
    def one(it: dict) -> FlyerItem | None:
        try:
            item_detail = get_item_detail(it["id"])
        except httpx.HTTPError:
            log.warning("skipping Flipp item %s: no detail, so its price can't be trusted", it.get("id"), exc_info=True)
            return None
        return _row(it, item_detail, flyer, pages, store, week)

    with ThreadPoolExecutor(WORKERS) as pool:
        rows = [r for r in pool.map(one, products) if r is not None]
    return {"week": week, "rows": [r.model_dump(mode="json") for r in rows], "item_count": len(raw_items),
            "sized_count": sum(r.size_qty is not None for r in rows), "meta": flyer_meta(flyer, pages)}


def flyer_meta(flyer: dict, pages: list[dict]) -> dict:
    """What it takes to draw one of this flyer's pages later: where its image tiles live, and where each page sits.

    Flipp's coordinates are pixels of the full-size flyer image, which lays every page side by side.
    """
    return {
        "path": flyer.get("path"), "width": flyer.get("width"), "height": flyer.get("height"),
        "resolutions": flyer.get("resolutions") or [],
        "pages": {str(p["page"]): [p["left"], p["right"], p["top"], p["bottom"]] for p in pages},
    }


# Page images, step 1 of 2: plan. A flyer image is a pyramid of 256 px tiles at several zoom levels. plan_page picks
# the level and the tile range that cover one page; render_page fetches and stitches them.
class PagePlan(NamedTuple):
    level: int  # index into the flyer's resolutions; 0 is the smallest image
    scale: float  # full-size pixels per pixel at this level
    box: tuple[int, int, int, int]  # the page in the level's image, from its top left: left, top, right, bottom
    cols: tuple[int, int]  # first and last tile column to fetch
    rows: tuple[int, int]  # first and last row of the tile canvas, from the top
    nrows: int  # tile rows in the whole level: row k from the top is tile number nrows - 1 - k
    pad: int  # blank pixels above the image in the top tile row (the image sits at the bottom of the tile grid)


def plan_page(width: float, height: float, resolutions: list[float], rect: list[float]) -> PagePlan:
    """Which zoom level and tiles draw a page: the sharpest level that keeps the page near a few megapixels.

    Flipp numbers tile rows from the BOTTOM of the flyer (row 0 is its bottom edge) and columns from the left, so
    the grid is anchored bottom-left and the partial tile, when there is one, is at the top.
    """
    left, right, top, bottom = rect
    pw, ph = right - left, top - bottom
    # Walk from the sharpest level down and stop at the first one small enough to keep the page light.
    level = 0
    for z in range(len(resolutions) - 1, -1, -1):  # sharpest first
        if pw * ph / resolutions[z] ** 2 <= PAGE_MAX_PIXELS and ph / resolutions[z] <= PAGE_MAX_HEIGHT:
            level = z
            break
    # Convert the page rectangle from full-size pixels to this level's pixels, then to tile columns and rows. `pad`
    # accounts for the partial tile row, which sits at the top because rows are counted from the bottom.
    scale = resolutions[level]
    level_h = math.ceil(height / scale)
    nrows = math.ceil(level_h / TILE)
    pad = nrows * TILE - level_h
    x0, x1 = math.floor(left / scale), math.ceil(right / scale)
    y0, y1 = math.floor(-top / scale), math.ceil(-bottom / scale)
    max_col = math.ceil(width / scale / TILE) - 1
    cols = (x0 // TILE, min((x1 - 1) // TILE, max_col))
    rows = ((y0 + pad) // TILE, min((y1 + pad - 1) // TILE, nrows - 1))
    return PagePlan(level, scale, (x0, y0, x1, y1), cols, rows, nrows, pad)


# Step 2 of 2: render. Missing tiles are normal (Flipp never cuts empty edge tiles), so they stay white rather than
# failing the whole page.
def _tile(url: str) -> bytes | None:
    """One image tile, or None when it isn't there (an edge tile Flipp never cut) or can't be fetched."""
    try:
        r = _http.get(url)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.content
    except httpx.HTTPError:
        time.sleep(RETRY_SECONDS)
        try:
            r = _http.get(url)
            return r.content if r.status_code == 200 else None
        except httpx.HTTPError:
            log.warning("couldn't fetch flyer tile %s", url, exc_info=True)
            return None


def render_page(meta: dict, page_no: int) -> bytes | None:
    """The real printed page as a JPEG, stitched from Flipp's image tiles. None when Flipp doesn't have it."""
    rect = (meta.get("pages") or {}).get(str(page_no))
    if not (rect and meta.get("path") and meta.get("width") and meta.get("height") and meta.get("resolutions")):
        return None
    plan = plan_page(meta["width"], meta["height"], meta["resolutions"], rect)
    wanted = [(c, k) for k in range(plan.rows[0], plan.rows[1] + 1) for c in range(plan.cols[0], plan.cols[1] + 1)]

    # Flipp numbers tile rows from the bottom, while the canvas below is built from the top, so flip the row number.
    def url(ck: tuple[int, int]) -> str:
        return f"{TILES}/{meta['path']}{plan.level}_{ck[0]}_{plan.nrows - 1 - ck[1]}.jpg"

    with ThreadPoolExecutor(WORKERS) as pool:
        fetched = list(pool.map(lambda ck: _tile(url(ck)), wanted))
    if not any(fetched):
        return None
    # Paste the tiles onto one big white canvas, then crop to exactly the page's rectangle (tiles overshoot its edges).
    c0, k0 = plan.cols[0], plan.rows[0]
    canvas = Image.new("RGB", ((plan.cols[1] - c0 + 1) * TILE, (plan.rows[1] - k0 + 1) * TILE), "white")
    for (c, k), data in zip(wanted, fetched, strict=True):
        if data:
            canvas.paste(Image.open(io.BytesIO(data)).convert("RGB"), ((c - c0) * TILE, (k - k0) * TILE))
    x0, y0, x1, y1 = plan.box
    ox, oy = c0 * TILE, k0 * TILE - plan.pad
    page = canvas.crop((x0 - ox, y0 - oy, x1 - ox, y1 - oy))
    out = io.BytesIO()
    # Quality 82 + progressive: small enough to load fast on a phone, sharp enough to read the fine print when zoomed.
    page.save(out, "JPEG", quality=82, optimize=True, progressive=True)
    return out.getvalue()


def fetch_grocery_flyer(merchant: str, store_key: str, postal: str = DEFAULT_POSTAL) -> dict:
    """One named store's weekly grocery flyer, by merchant name. Only the tests call this today: the live API goes
    through flyers_live -> grocery_flyers_for -> fetch_flyer, and the Databricks pipeline has its own fetcher in
    databricks/fetchers/flipp.py. `pages` is always []: real page pictures are stitched on demand by render_page."""
    flyer = grocery_flyer_for(list_weekly_flyers(postal), merchant)
    if flyer is None:
        raise RuntimeError(f"no Groceries flyer found for merchant={merchant!r} near {postal}")
    # The app's canonical display name (e.g. "Save-On-Foods"), not the Volume/store_key slug and not Flipp's
    # own merchant string (diverges for T&T: "T&T Supermarket" there vs. "T&T" everywhere else in this app).
    return {**fetch_flyer(flyer, STORES.get(store_key, store_key)), "pages": []}
