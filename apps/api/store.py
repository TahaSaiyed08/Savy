"""Data access. REALDEAL_MOCK=1 (the default without DATABRICKS_HOST) keeps everything in memory."""
import logging
import os
import uuid
from datetime import UTC, datetime
from uuid import UUID

from apps.api import logic
from apps.api.mock_data import FLYER_ITEMS, SEED_ITEMS
from apps.api.models import Deal, SaveItems, UserItem

log = logging.getLogger(__name__)
MOCK = os.getenv("REALDEAL_MOCK", "0" if os.getenv("DATABRICKS_HOST") else "1") == "1"
INDEX = "realdeal.core.flyer_items_idx"


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


def _match_and_store(u: UserItem) -> None:
    """Top-3 from AI Search, brand rule + threshold, written to user_item_matches (read by my_deals)."""
    from apps.api import databricks_sql as db

    try:
        r = db._client().vector_search_indexes.query_index(
            index_name=INDEX, columns=["item_id", "brand", "item", "variant"],
            query_text=logic.label(u), num_results=3,
        )
        rows = [(row[0], row[1], row[-1]) for row in (r.result.data_array or [])]  # score is last
    except Exception:
        log.warning("AI Search unavailable, falling back to LIKE", exc_info=True)
        rows = [(x["item_id"], x["brand"], 0.75) for x in db.query(
            "SELECT item_id, brand FROM flyer_items WHERE week_start = (SELECT max(week_start) FROM flyer_items)"
            " AND lower(item) LIKE concat('%', lower(:item), '%') LIMIT 3", item=u.item)]
    for item_id, brand, score in rows:
        if float(score) < logic.MATCH_THRESHOLD or (u.brand and (brand or "").lower() != u.brand.lower()):
            continue
        db.execute(
            "INSERT INTO user_item_matches VALUES (:user_item_id, :flyer_item_id, :score, current_timestamp())",
            user_item_id=u.user_item_id, flyer_item_id=item_id, score=float(score),
        )


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

    db.execute("MERGE INTO users t USING (SELECT :user_id AS user_id) s ON t.user_id = s.user_id "
               "WHEN NOT MATCHED THEN INSERT (user_id, created_at) VALUES (s.user_id, current_timestamp())",
               user_id=str(user_id))
    for u in new:  # ponytail: one INSERT per item; batch it if receipts get long
        db.execute(
            "INSERT INTO user_items VALUES (:user_item_id, :user_id, :brand, :item, :variant, :size_qty, "
            ":size_unit, :source, :added_at, :last_bought_at)",
            **{**u.model_dump(), "user_id": str(u.user_id)},
        )
        _match_and_store(u)
    return new


def list_deals(user_id: UUID) -> list[Deal]:
    if MOCK:
        return logic.deals_for(_mock_items(user_id), FLYER_ITEMS)
    from apps.api import databricks_sql as db

    rows = db.query(
        "SELECT d.*, concat_ws(' ', u.brand, u.item, u.variant) AS item_label, "
        "concat_ws(' ', f.brand, f.item, f.variant) AS flyer_label, f.unit "
        "FROM my_deals d JOIN user_items u USING (user_item_id) JOIN flyer_items f ON f.item_id = d.flyer_item_id "
        "WHERE d.user_id = :user_id", user_id=str(user_id))
    return [Deal(**r) for r in rows]
