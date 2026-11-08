"""Data access. REALDEAL_MOCK=1 (the default without DATABRICKS_HOST) keeps everything in memory."""
import io
import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from uuid import UUID

from apps.api.mock_data import FLYER_ITEMS, SEED_ITEMS
from apps.api.models import Extraction, FlyerItem, ItemPatch, SaveItems, UserItem

log = logging.getLogger(__name__)
MOCK = os.getenv("REALDEAL_MOCK", "0" if os.getenv("DATABRICKS_HOST") else "1") == "1"
UPLOADS = "/Volumes/realdeal/core/uploads/receipts"
_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}
_MINE = "WHERE user_id = :user_id AND user_item_id = :user_item_id"  # every per-item write is scoped to its owner
_EDITABLE = ("brand", "item", "variant", "size_qty", "size_unit")
# Batches travel as one JSON string parameter and are expanded with inline(from_json(...)) in SQL.
_ITEM_ROWS = ("ARRAY<STRUCT<user_item_id: STRING, user_id: STRING, brand: STRING, item: STRING, variant: STRING, "
              "size_qty: DOUBLE, size_unit: STRING, source: STRING, added_at: STRING, last_bought_at: STRING>>")


def _new_item(user_id: UUID, source: str, bought_at: datetime | None = None, **fields) -> UserItem:
    return UserItem(user_item_id=str(uuid.uuid4()), user_id=user_id, source=source,
                    added_at=datetime.now(UTC), last_bought_at=bought_at, **fields)


# --- mock -----------------------------------------------------------------
# ponytail: process memory, lost on restart; fine for mock mode only.
_items: dict[UUID, list[UserItem]] = {}


def _mock_items(user_id: UUID) -> list[UserItem]:
    if user_id not in _items:
        _items[user_id] = [_new_item(user_id, "manual", **s) for s in SEED_ITEMS]
    return _items[user_id]


# --- flyers (both modes) ----------------------------------------------------
FLYER_TTL = 600.0  # flyers change weekly; every list read matches against this in-process copy
_flyer_cache: tuple[float, list[FlyerItem]] = (0.0, [])
_flyer_lock = threading.Lock()


def flyer_items() -> list[FlyerItem]:
    """Every listing still valid today, across all stores."""
    global _flyer_cache
    if MOCK:
        return FLYER_ITEMS
    from apps.api import databricks_sql as db

    with _flyer_lock:  # one warehouse query per TTL, not one per concurrent request
        if time.monotonic() - _flyer_cache[0] > FLYER_TTL:
            rows = db.query("SELECT * FROM flyer_items WHERE price IS NOT NULL "
                            "AND coalesce(valid_to, date_add(week_start, 6)) >= current_date()")
            _flyer_cache = (time.monotonic(), [FlyerItem(**r) for r in rows])
        return _flyer_cache[1]


def page_tiles(page_id: str) -> list[FlyerItem]:
    return [f for f in flyer_items() if f.page_id == page_id]


def page_image(path: str) -> bytes:
    from apps.api import databricks_sql as db

    return db._client().files.download(path).contents.read()


# --- interface used by main.py ---------------------------------------------


def list_items(user_id: UUID) -> list[UserItem]:
    if MOCK:
        return _mock_items(user_id)
    from apps.api import databricks_sql as db

    rows = db.query("SELECT u.*, b.user_item_id IS NOT NULL AS in_basket FROM user_items u "
                    "LEFT JOIN basket_items b ON b.user_item_id = u.user_item_id AND b.user_id = u.user_id "
                    "WHERE u.user_id = :user_id ORDER BY u.added_at DESC", user_id=str(user_id))
    return [UserItem(**r) for r in rows]


def add_items(user_id: UUID, req: SaveItems) -> list[UserItem]:
    new = [_new_item(user_id, req.source, req.bought_at, **i.model_dump(include=set(_EDITABLE))) for i in req.items]
    if MOCK:
        _mock_items(user_id)[:0] = new
        return new
    from apps.api import databricks_sql as db

    rows = json.dumps([{**u.model_dump(mode="json", exclude={"in_basket"}), "user_id": str(u.user_id)} for u in new])
    with ThreadPoolExecutor(max_workers=2) as pool:  # fixed statement count however many items
        writes = [
            pool.submit(db.execute,
                        "MERGE INTO users t USING (SELECT :user_id AS user_id) s ON t.user_id = s.user_id "
                        "WHEN NOT MATCHED THEN INSERT (user_id, created_at) VALUES (s.user_id, current_timestamp())",
                        user_id=str(user_id)),
            pool.submit(db.execute,
                        "INSERT INTO user_items (user_item_id, user_id, brand, item, variant, size_qty, size_unit, "
                        "source, added_at, last_bought_at) SELECT user_item_id, user_id, brand, item, variant, "
                        "size_qty, size_unit, source, CAST(added_at AS TIMESTAMP), CAST(last_bought_at AS TIMESTAMP) "
                        f"FROM (SELECT inline(from_json(:rows, '{_ITEM_ROWS}')))", rows=rows),
        ]
        for w in writes:
            w.result()  # a failed write must surface
    return new


def update_item(user_id: UUID, user_item_id: str, patch: ItemPatch) -> UserItem | None:
    """Edit fields and/or move to or from the basket. None if the user has no such item."""
    fields = {k: getattr(patch, k) for k in patch.model_fields_set if k in _EDITABLE}
    if MOCK:
        items = _mock_items(user_id)
        for n, i in enumerate(items):
            if i.user_item_id == user_item_id:
                in_basket = i.in_basket if patch.in_basket is None else patch.in_basket
                items[n] = i.model_copy(update={**fields, "in_basket": in_basket})
                return items[n]
        return None
    from apps.api import databricks_sql as db

    ids, mine = dict(user_id=str(user_id), user_item_id=user_item_id), _MINE
    if fields:  # keys come from _EDITABLE, never from the client
        db.execute(f"UPDATE user_items SET {', '.join(f'{k} = :{k}' for k in fields)} {mine}", **fields, **ids)
    if patch.in_basket:
        db.execute("INSERT INTO basket_items SELECT :user_id, :user_item_id, current_timestamp() WHERE "
                   f"EXISTS (SELECT 1 FROM user_items {mine}) "
                   f"AND NOT EXISTS (SELECT 1 FROM basket_items {mine})", **ids)
    elif patch.in_basket is False:
        db.execute(f"DELETE FROM basket_items {mine}", **ids)
    return next((i for i in list_items(user_id) if i.user_item_id == user_item_id), None)


def delete_item(user_id: UUID, user_item_id: str) -> None:
    if MOCK:
        items = _mock_items(user_id)
        _items[user_id] = [i for i in items if i.user_item_id != user_item_id]
        return
    from apps.api import databricks_sql as db

    for table in ("basket_items", "user_items"):
        db.execute(f"DELETE FROM {table} {_MINE}", user_id=str(user_id), user_item_id=user_item_id)


def save_receipt(user_id: UUID, image: bytes, x: Extraction) -> None:
    """Receipt photo to the uploads Volume plus a receipts row. Runs after the response; failures are only logged."""
    if MOCK:
        return
    from apps.api import databricks_sql as db
    from apps.api.extractors import sniff_media_type

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
