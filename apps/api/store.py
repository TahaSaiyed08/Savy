"""Data access. REALDEAL_MOCK=1 (the default without DATABRICKS_HOST) keeps everything in memory."""
import io
import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from pydantic import ValidationError

from apps.api import flyers_live
from apps.api.mock_data import FLYER_ITEMS, seed_items
from apps.api.models import Extraction, FlyerItem, ItemPatch, SaveItems, UserItem

log = logging.getLogger(__name__)
# Two backends behind one set of functions. MOCK keeps the person's list in this process's memory (lost on restart,
# fine for demos and tests); the other mode reads and writes Databricks tables through the SQL warehouse. main.py
# never needs to know which one it is talking to. Without DATABRICKS_HOST, MOCK is on by default.
MOCK = os.getenv("REALDEAL_MOCK", "0" if os.getenv("DATABRICKS_HOST") else "1") == "1"
# Where receipt photos are kept in Databricks (a Unity Catalog Volume), one folder per user.
UPLOADS = "/Volumes/realdeal/core/uploads/receipts"
_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}
# The only item columns a client may change. Anything else in a PATCH is ignored rather than written.
_EDITABLE = ("brand", "item", "variant", "size_qty", "size_unit")

# Every statement is a fixed literal; all values travel as named parameters. Per-item writes are scoped to their
# owner (user_id = :user_id AND user_item_id = :user_item_id).
# EXISTS, not a join: two racing "Move to Basket" taps can leave duplicate basket rows. Named columns, not u.*:
# catalogs that ran PR #10's ALTER also have an in_basket column on user_items.
_LIST_ITEMS = (
    "SELECT u.user_item_id, u.user_id, u.brand, u.item, u.variant, u.size_qty, u.size_unit, u.source, u.added_at, "
    "u.last_bought_at, EXISTS (SELECT 1 FROM basket_items b WHERE b.user_item_id = u.user_item_id "
    "AND b.user_id = u.user_id) AS in_basket, EXISTS (SELECT 1 FROM basket_items b WHERE b.user_item_id = "
    "u.user_item_id AND b.user_id = u.user_id AND b.done_at IS NOT NULL) AS done FROM user_items u "
    "WHERE u.user_id = :user_id ORDER BY u.added_at DESC")
_ADD_USER = ("MERGE INTO users t USING (SELECT :user_id AS user_id) s ON t.user_id = s.user_id "
             "WHEN NOT MATCHED THEN INSERT (user_id, created_at) VALUES (s.user_id, current_timestamp())")
# The batch travels as one JSON string parameter and is expanded with inline(from_json(...)).
_ADD_ITEMS = (
    "INSERT INTO user_items (user_item_id, user_id, brand, item, variant, size_qty, size_unit, source, added_at, "
    "last_bought_at) SELECT user_item_id, user_id, brand, item, variant, size_qty, size_unit, source, "
    "CAST(added_at AS TIMESTAMP), CAST(last_bought_at AS TIMESTAMP) FROM (SELECT inline(from_json(:rows, "
    "'ARRAY<STRUCT<user_item_id: STRING, user_id: STRING, brand: STRING, item: STRING, variant: STRING, "
    "size_qty: DOUBLE, size_unit: STRING, source: STRING, added_at: STRING, last_bought_at: STRING>>')))")
# Partial update with a fixed statement: set_<field> says whether the client sent that field (it may be sent as null).
_UPDATE_ITEM = (
    "UPDATE user_items SET brand = IF(:set_brand, :brand, brand), item = IF(:set_item, :item, item), "
    "variant = IF(:set_variant, :variant, variant), size_qty = IF(:set_size_qty, CAST(:size_qty AS DOUBLE), size_qty), "
    "size_unit = IF(:set_size_unit, :size_unit, size_unit) WHERE user_id = :user_id AND user_item_id = :user_item_id")
_SET_SOURCE = "UPDATE user_items SET source = :source WHERE user_id = :user_id AND user_item_id = :user_item_id"
_ADD_TO_BASKET = (
    "INSERT INTO basket_items SELECT :user_id, :user_item_id, current_timestamp(), NULL WHERE EXISTS (SELECT 1 FROM "
    "user_items WHERE user_id = :user_id AND user_item_id = :user_item_id) AND NOT EXISTS (SELECT 1 FROM "
    "basket_items WHERE user_id = :user_id AND user_item_id = :user_item_id)")
_SET_DONE = ("UPDATE basket_items SET done_at = IF(:done, current_timestamp(), NULL) "
             "WHERE user_id = :user_id AND user_item_id = :user_item_id")
_REMOVE_FROM_BASKET = "DELETE FROM basket_items WHERE user_id = :user_id AND user_item_id = :user_item_id"
_DELETE_ITEM = "DELETE FROM user_items WHERE user_id = :user_id AND user_item_id = :user_item_id"


def _new_item(user_id: UUID, source: str, bought_at: datetime | None = None, **fields) -> UserItem:
    return UserItem(user_item_id=str(uuid.uuid4()), user_id=user_id, source=source,
                    added_at=datetime.now(UTC), last_bought_at=bought_at, **fields)


# --- mock -----------------------------------------------------------------
# One list per user id, created the first time that user is seen.
# ponytail: process memory, lost on restart; fine for mock mode only.
_items: dict[UUID, list[UserItem]] = {}


def _mock_items(user_id: UUID, postal: str | None = None) -> list[UserItem]:
    # A new user starts with a few pantry items picked from this week's real flyers, so the app has something to show
    # (and match) on first open instead of an empty screen.
    if user_id not in _items:
        try:
            seeds = seed_items(flyer_items(postal))
        except Exception:  # flyers being down must not fail the list
            log.warning("flyers unavailable; starting an empty pantry", exc_info=True)
            seeds = []
        _items[user_id] = [_new_item(user_id, **{"source": "manual", **s}) for s in seeds]
    return _items[user_id]


# --- flyers (both modes) ----------------------------------------------------
# Databricks mode only: the flyer table is read at most once every 10 minutes and shared by all requests. (Mock mode
# has its own, richer freshness logic in flyers_live.)
FLYER_TTL = 600.0  # flyers change weekly; every list read matches against this in-process copy
FLYER_RETRY = 60.0  # after a failed refresh, keep serving the old copy and try again this soon
_flyer_cache: tuple[float, list[FlyerItem]] = (float("-inf"), [])  # -inf: monotonic() can be < TTL after boot
_flyer_lock = threading.Lock()


def flyer_items(postal: str | None = None) -> list[FlyerItem]:
    """Every priced listing still valid today, across all stores.

    Mock mode serves this week's real Flipp flyers near `postal` (default: DEFAULT_POSTAL_CODE), or the canned
    FLYER_ITEMS when live flyers are off. Databricks mode reads the table, which has no postal code.
    Raises only if the very first load fails; after that a failed refresh keeps the previous copy (logged).
    """
    # Three sources: live Flipp feeds, the canned demo flyers, or the Databricks table. Callers just get a list.
    global _flyer_cache
    if MOCK:
        return flyers_live.items(postal or flyers_live.DEFAULT_POSTAL) if flyers_live.ENABLED else FLYER_ITEMS
    from apps.api import databricks_sql as db

    with _flyer_lock:  # one warehouse query per TTL, not one per concurrent request
        loaded, items = _flyer_cache
        if time.monotonic() - loaded <= FLYER_TTL:
            return items
        try:
            # Validity is checked here, not in SQL, so this also reads flyer_items built before valid_to existed.
            rows = db.query("SELECT * FROM flyer_items WHERE price IS NOT NULL "
                            "AND week_start >= date_sub(current_date(), 30)", fallback=False)
        except Exception:
            if not items:
                raise
            log.warning("flyer refresh failed; serving the copy from %.0f s ago", time.monotonic() - loaded,
                        exc_info=True)
            _flyer_cache = (time.monotonic() - FLYER_TTL + FLYER_RETRY, items)
            return items
        # Rows that don't fit the model are dropped and counted, never allowed to fail the whole load.
        today, fresh, bad = date.today(), [], 0
        for r in rows:
            try:
                fresh.append(FlyerItem(**r))
            except ValidationError:
                bad += 1
        if bad:
            log.warning("skipped %d of %d flyer_items rows that don't fit FlyerItem", bad, len(rows))
        _flyer_cache = (time.monotonic(),
                        [f for f in fresh if (f.valid_to or f.week_start + timedelta(days=6)) >= today])
        return _flyer_cache[1]


def page_tiles(page_id: str) -> list[FlyerItem]:
    # Every tile on one flyer page: what the Price Match screen draws its highlight from.
    if MOCK and flyers_live.ENABLED:
        return flyers_live.page(page_id)  # page ids are globally unique, so no postal code is needed
    return [f for f in flyer_items() if f.page_id == page_id]


def flyer_pages(tile: FlyerItem) -> list[str]:
    """page_ids of the flyer a tile is on, in page order."""
    if MOCK and flyers_live.ENABLED:
        return flyers_live.sibling_pages(tile)
    pages = {f.page_id: f.page_no or 0 for f in flyer_items()
             if f.store == tile.store and f.week_start == tile.week_start}
    return sorted(pages, key=lambda p: pages[p])


def page_image(path: str) -> bytes | None:
    """The page image from the Volume, or None if it isn't there (anymore)."""
    from databricks.sdk.errors import NotFound

    from apps.api import databricks_sql as db

    try:
        return db._client().files.download(path).contents.read()
    except NotFound:
        log.warning("page image %s is in flyer_items but not in the Volume", path)
        return None


# --- interface used by main.py ---------------------------------------------


def list_items(user_id: UUID, fresh: bool = False, postal: str | None = None) -> list[UserItem]:
    # `fresh` matters because the SQL layer can fall back to its last good answer if the warehouse is slow; right after
    # a write that would show stale data, so writes read back with fresh=True.
    """fresh=True right after a write: never served from the last-good cache."""
    if MOCK:
        return _mock_items(user_id, postal)
    from apps.api import databricks_sql as db

    rows = db.query(_LIST_ITEMS, fallback=not fresh, user_id=str(user_id))
    return [UserItem(**r) for r in rows]


def add_items(user_id: UUID, req: SaveItems, postal: str | None = None) -> list[UserItem]:
    # Ids and timestamps are made here on the server, never trusted from the client.
    new = [_new_item(user_id, req.source, req.bought_at, **i.model_dump(include=set(_EDITABLE))) for i in req.items]
    if MOCK:
        _mock_items(user_id, postal)[:0] = new
        return new
    from apps.api import databricks_sql as db

    rows = json.dumps([{**u.model_dump(mode="json", exclude={"in_basket", "done"}), "user_id": str(u.user_id)}
                       for u in new])
    # Two statements however many items: register the user if new, and insert every item as one batch (as JSON that
    # the warehouse expands into rows). They run side by side to save a round trip.
    with ThreadPoolExecutor(max_workers=2) as pool:  # fixed statement count however many items
        writes = [pool.submit(db.execute, _ADD_USER, user_id=str(user_id)),
                  pool.submit(db.execute, _ADD_ITEMS, rows=rows)]
        for w in writes:
            w.result()  # a failed write must surface
    return new


def update_item(user_id: UUID, user_item_id: str, patch: ItemPatch, postal: str | None = None) -> UserItem | None:
    """Edit fields and/or move to or from the basket. None if the user has no such item."""
    # Only fields the client sent, and only editable ones. In mock mode the basket and "done" flags live on the item;
    # in Databricks mode they are rows in a separate basket_items table.
    fields = {k: getattr(patch, k) for k in patch.model_fields_set if k in _EDITABLE}
    if MOCK:
        items = _mock_items(user_id, postal)
        for n, i in enumerate(items):
            if i.user_item_id == user_item_id:
                in_basket = i.in_basket if patch.in_basket is None else patch.in_basket
                # An item can only be "done" while it is in the basket; removing it from the basket clears done.
                done = in_basket and (i.done if patch.done is None else patch.done)
                items[n] = i.model_copy(update={**fields, "in_basket": in_basket, "done": done})
                return items[n]
        return None
    from apps.api import databricks_sql as db

    ids = dict(user_id=str(user_id), user_item_id=user_item_id)
    if fields:
        db.execute(_UPDATE_ITEM, **ids, **{k: fields.get(k) for k in _EDITABLE},
                   **{f"set_{k}": k in fields for k in _EDITABLE})
    if patch.in_basket:
        db.execute(_ADD_TO_BASKET, **ids)
    elif patch.in_basket is False:
        db.execute(_REMOVE_FROM_BASKET, **ids)
    if patch.done is not None:
        db.execute(_SET_DONE, done=patch.done, **ids)
    return next((i for i in list_items(user_id, fresh=True) if i.user_item_id == user_item_id), None)


def set_source(user_id: UUID, user_item_id: str, source: str, postal: str | None = None) -> UserItem | None:
    if MOCK:
        items = _mock_items(user_id, postal)
        for n, i in enumerate(items):
            if i.user_item_id == user_item_id:
                items[n] = i.model_copy(update={"source": source})
                return items[n]
        return None
    from apps.api import databricks_sql as db

    db.execute(_SET_SOURCE, source=source, user_id=str(user_id), user_item_id=user_item_id)
    return next((i for i in list_items(user_id, fresh=True) if i.user_item_id == user_item_id), None)


def delete_item(user_id: UUID, user_item_id: str) -> None:
    if MOCK:
        items = _mock_items(user_id)
        _items[user_id] = [i for i in items if i.user_item_id != user_item_id]
        return
    from apps.api import databricks_sql as db

    # Basket row first, then the item, so a half-finished delete never leaves a basket entry pointing at nothing.
    for sql in (_REMOVE_FROM_BASKET, _DELETE_ITEM):
        db.execute(sql, user_id=str(user_id), user_item_id=user_item_id)


def save_receipt(user_id: UUID, image: bytes, x: Extraction) -> None:
    """Receipt photo to the uploads Volume plus a receipts row. Runs after the response; failures are only logged."""
    if MOCK:
        return
    from apps.api import databricks_sql as db
    from apps.api.extractors import sniff_media_type

    # The file type comes from sniffing the bytes, not from the client's claimed content type.
    receipt_id = str(uuid.uuid4())
    path = f"{UPLOADS}/{user_id}/{receipt_id}.{_EXT.get(sniff_media_type(image) or '', 'bin')}"
    try:
        db._client().files.upload(path, io.BytesIO(image), overwrite=False)
        db.execute(
            "INSERT INTO receipts (receipt_id, user_id, store, total, bought_at, image_path) "
            "VALUES (:receipt_id, :user_id, :store, :total, :bought_at, :image_path)",
            receipt_id=receipt_id, user_id=str(user_id), store=x.store, total=x.total,
            bought_at=_iso_date(x.bought_at), image_path=path,
        )
    except Exception:
        log.warning("couldn't save receipt %s for %s", receipt_id, user_id, exc_info=True)


def _iso_date(s: str | None) -> date | None:
    try:
        return date.fromisoformat(s[:10]) if s else None
    except ValueError:
        return None
