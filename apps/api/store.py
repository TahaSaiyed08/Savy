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

from apps.api import logic
from apps.api.mock_data import FLYER_ITEMS, SEED_ITEMS
from apps.api.models import Deal, Extraction, SaveItems, UserItem

log = logging.getLogger(__name__)
MOCK = os.getenv("REALDEAL_MOCK", "0" if os.getenv("DATABRICKS_HOST") else "1") == "1"
INDEX = "realdeal.core.flyer_items_idx"
UPLOADS = "/Volumes/realdeal/core/uploads/receipts"
_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}
# Batches travel as one JSON string parameter and are expanded with inline(from_json(...)) in SQL.
_ITEM_ROWS = ("ARRAY<STRUCT<user_item_id: STRING, user_id: STRING, brand: STRING, item: STRING, variant: STRING, "
              "size_qty: DOUBLE, size_unit: STRING, source: STRING, added_at: STRING, last_bought_at: STRING>>")
_MATCH_ROWS = "ARRAY<STRUCT<user_item_id: STRING, flyer_item_id: STRING, match_score: DOUBLE>>"
_LIKE_ROWS = "ARRAY<STRUCT<user_item_id: STRING, brand: STRING, item: STRING>>"


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


# --- databricks -----------------------------------------------------------


def _match_and_store(items: list[UserItem]) -> None:
    """Top-3 per store per item from AI Search (one LIKE query for any it misses), brand rule + threshold, one INSERT.

    Matches land in user_item_matches, which my_deals reads.
    """
    from apps.api import databricks_sql as db

    with ThreadPoolExecutor(max_workers=8) as pool:
        found = dict(zip((u.user_item_id for u in items), pool.map(_search, items), strict=True))
    if any(found.values()):  # the index holds every week, so keep only current-flyer hits
        current = _current_flyers()
        found = {k: None if v is None else _current_top(v, current) for k, v in found.items()}
    missed = [u for u in items if found[u.user_item_id] is None]
    if missed:
        found.update(_like_fallback(missed))
    matches = [
        {"user_item_id": u.user_item_id, "flyer_item_id": item_id, "match_score": float(score)}
        for u in items for item_id, brand, score in found.get(u.user_item_id) or []
        if float(score) >= logic.MATCH_THRESHOLD and not (u.brand and (brand or "").lower() != u.brand.lower())
    ]
    if matches:
        # One atomic MERGE, not check-then-insert: Delta's optimistic concurrency fails one of two concurrent
        # MERGEs that would insert the same pair (the failure takes the normal retry path), so no duplicates.
        db.execute(
            f"MERGE INTO user_item_matches t USING (SELECT DISTINCT * FROM (SELECT inline(from_json(:rows, "
            f"'{_MATCH_ROWS}')))) s ON t.user_item_id = s.user_item_id AND t.flyer_item_id = s.flyer_item_id "
            "WHEN NOT MATCHED THEN INSERT (user_item_id, flyer_item_id, match_score, matched_at) "
            "VALUES (s.user_item_id, s.flyer_item_id, s.match_score, current_timestamp())",
            rows=json.dumps(matches))


# Items whose matching failed, retried on the user's next /deals or /basket. Process memory, so a restart drops
# them; rematch_if_new_week below is the durable sweep.
RETRY_AFTER = 60.0
_unmatched: dict[UUID, tuple[float, list[UserItem]]] = {}
_unmatched_lock = threading.Lock()


def _queue_rematch(user_id: UUID, items: list[UserItem], delay: float = 0.0) -> None:
    """delay=0 retries on the next /deals; a failed retry backs off RETRY_AFTER so an outage doesn't slow every call."""
    with _unmatched_lock:
        _, pending = _unmatched.get(user_id, (0.0, []))
        _unmatched[user_id] = (time.monotonic() + delay, pending + items)


def _retry_rematch(user_id: UUID) -> None:
    now = time.monotonic()
    with _unmatched_lock:
        due, pending = _unmatched.get(user_id, (0.0, []))
        if not pending or now < due:
            return
        del _unmatched[user_id]  # claimed, so concurrent requests don't retry the same items
    try:
        _match_and_store(pending)
    except Exception:
        log.warning("re-match failed for %d items; will retry", len(pending), exc_info=True)
        _queue_rematch(user_id, pending, RETRY_AFTER)


# Weekly re-match (plan WS2 step 8). main.py polls this every REMATCH_EVERY_SECONDS. It does real work only when
# some store's current flyer changed since the last sweep, or on the first poll after a restart (which also covers
# items whose in-memory retry was lost). "Changed" includes more pages or corrected rows for the same week, not just
# a new week. It re-matches every item, because an item already matched at one store still needs matching against
# another store's new rows; the MERGE in _match_and_store keeps that duplicate-free. Its reads (and matching's) use
# fresh=True: a cached snapshot would be recorded as swept and the items missing from it never retried.
REMATCH_BATCH = 100
_swept_flyers: str | None = None
# A store's current flyer is its own latest week_start: chains start flyers on different days.
_CURRENT_FLYERS = "(SELECT * FROM flyer_items QUALIFY week_start = max(week_start) OVER (PARTITION BY store))"
# Per store: week, row count and an order-independent hash (bit_xor can't overflow) of the matching-relevant columns.
_FLYER_SIGNATURE = (
    "SELECT concat_ws(',', sort_array(collect_list(sig))) AS sig FROM (SELECT concat(store, '=', "
    "CAST(max(week_start) AS STRING), ':', count(*), ':', bit_xor(xxhash64(item_id, brand, item, variant, "
    f"size_qty, size_unit, price, unit_price, unit))) AS sig FROM {_CURRENT_FLYERS} f GROUP BY store)")


def rematch_if_new_week() -> int:
    """Re-match every user item when any store's current flyer changes. Returns how many items were matched.

    The flyers are only marked swept when every batch succeeds, so a failure is retried on the next poll. The
    signature is read before matching, so rows landing mid-sweep change it and trigger another sweep.
    """
    global _swept_flyers
    if MOCK:
        return 0
    from apps.api import databricks_sql as db

    sig = db.query(_FLYER_SIGNATURE, fresh=True)[0]["sig"]
    if not sig or sig == _swept_flyers:
        return 0
    items = [UserItem(**r) for r in db.query("SELECT * FROM user_items", fresh=True)]
    for i in range(0, len(items), REMATCH_BATCH):
        _match_and_store(items[i:i + REMATCH_BATCH])
    _swept_flyers = sig
    log.info("re-matched %d items for flyers %s", len(items), sig)
    return len(items)


def _search(u: UserItem) -> list[tuple] | None:
    """AI Search candidates as (item_id, brand, score) across all weeks, or None if the index is unavailable."""
    from apps.api import databricks_sql as db

    try:
        r = db._client().vector_search_indexes.query_index(
            index_name=INDEX, columns=["item_id", "brand", "item", "variant"],
            query_text=logic.label(u), num_results=SEARCH_CANDIDATES,
        )
    except Exception as e:
        log.warning("AI Search unavailable, falling back to LIKE: %s", e)
        return None
    return [(row[0], row[1], row[-1]) for row in (r.result.data_array or [])]  # score is last, best first


# The index covers every week and can't filter on week_start, so over-fetch and keep current-flyer rows.
SEARCH_CANDIDATES = 50
TOP_PER_STORE = 3


def _current_flyers() -> dict[str, str]:
    """item_id -> store for every item in each store's current flyer."""
    from apps.api import databricks_sql as db

    return {r["item_id"]: r["store"]
            for r in db.query(f"SELECT item_id, store FROM {_CURRENT_FLYERS} f", fresh=True)}


def _current_top(hits: list[tuple], current: dict[str, str]) -> list[tuple]:
    """Drop hits from past weeks, then keep the best TOP_PER_STORE per store (hits arrive best first)."""
    kept: list[tuple] = []
    per_store: dict[str, int] = {}
    for hit in hits:
        store = current.get(hit[0])
        if store is not None and per_store.get(store, 0) < TOP_PER_STORE:
            per_store[store] = per_store.get(store, 0) + 1
            kept.append(hit)
    return kept


def _like_fallback(items: list[UserItem]) -> dict[str, list[tuple]]:
    """One query for all items: top-3 per store from each store's current flyer, same brand ranked first."""
    from apps.api import databricks_sql as db

    rows = db.query(
        f"WITH u AS (SELECT inline(from_json(:rows, '{_LIKE_ROWS}'))) "
        f"SELECT u.user_item_id, f.item_id, f.brand FROM u JOIN {_CURRENT_FLYERS} f "
        "ON lower(f.item) LIKE concat('%', lower(u.item), '%') "
        "QUALIFY row_number() OVER (PARTITION BY u.user_item_id, f.store "
        "ORDER BY coalesce(lower(f.brand) = lower(u.brand), false) DESC, f.item_id) <= 3",
        rows=json.dumps([{"user_item_id": u.user_item_id, "brand": u.brand, "item": u.item} for u in items]),
        fresh=True,
    )
    out: dict[str, list[tuple]] = {u.user_item_id: [] for u in items}
    for x in rows:
        out[x["user_item_id"]].append((x["item_id"], x["brand"], 0.75))
    return out


# --- interface used by main.py ---------------------------------------------


def list_items(user_id: UUID) -> list[UserItem]:
    if MOCK:
        return _mock_items(user_id)
    from apps.api import databricks_sql as db

    rows = db.query("SELECT * FROM user_items WHERE user_id = :user_id ORDER BY added_at DESC",
                    user_id=str(user_id))
    return [UserItem(**r) for r in rows]


def add_items(user_id: UUID, req: SaveItems) -> list[UserItem]:
    new = [_new_item(user_id, req.source, req.bought_at,
                     **i.model_dump(include={"brand", "item", "variant", "size_qty", "size_unit"}))
           for i in req.items]
    if MOCK:
        _mock_items(user_id)[:0] = new
        return new
    from apps.api import databricks_sql as db

    rows = json.dumps([{**u.model_dump(mode="json"), "user_id": str(u.user_id)} for u in new])
    # Fixed statement count however many items, and the three independent ones run concurrently.
    with ThreadPoolExecutor(max_workers=3) as pool:
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
        matching = pool.submit(_match_and_store, new)
        for w in writes:
            w.result()  # a failed write must surface
        try:
            matching.result()
        except Exception:  # the items are saved; matching is retried on the user's next /deals or /basket
            log.warning("matching failed; saved %d items without matches", len(new), exc_info=True)
            _queue_rematch(user_id, new)
    return new


def delete_item(user_id: UUID, user_item_id: str) -> None:
    if MOCK:
        items = _mock_items(user_id)
        _items[user_id] = [i for i in items if i.user_item_id != user_item_id]
        return
    from apps.api import databricks_sql as db

    db.execute("DELETE FROM user_items WHERE user_id = :user_id AND user_item_id = :user_item_id",
               user_id=str(user_id), user_item_id=user_item_id)


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


def list_deals(user_id: UUID) -> list[Deal]:
    if MOCK:
        return logic.deals_for(_mock_items(user_id), FLYER_ITEMS)
    from apps.api import databricks_sql as db

    _retry_rematch(user_id)
    rows = db.query(
        "SELECT d.*, concat_ws(' ', u.brand, u.item, u.variant) AS item_label, "
        "concat_ws(' ', f.brand, f.item, f.variant) AS flyer_label, f.unit "
        "FROM my_deals d JOIN user_items u USING (user_item_id) JOIN flyer_items f ON f.item_id = d.flyer_item_id "
        "WHERE d.user_id = :user_id", user_id=str(user_id))
    return [Deal(**r) for r in rows]
