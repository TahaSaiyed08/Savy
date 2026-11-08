"""Keeps the live flyers in Unity Catalog, so Genie can answer questions about them and prices build a history.

After every download, flyers_live pushes that postal code's listings here:
  realdeal.core.live_listings  what is on sale now, one row per listing, replaced per postal code
  realdeal.core.price_history  every listing ever seen, one row per (postal code, flyer item), kept week after week

Opt in only: nothing is written to the workspace unless REALDEAL_DATABRICKS_SYNC=1 and the credentials are set. A
failed push is logged and never stops a refresh: the app serves from its own copy.
"""
import json
import logging
import os
import time
from datetime import UTC, datetime

from apps.api.models import FlyerItem

log = logging.getLogger(__name__)

LISTINGS = "realdeal.core.live_listings"
HISTORY = "realdeal.core.price_history"
_NEEDS = ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_WAREHOUSE_ID")

# Column comments matter: Genie reads them to understand the table.
_CATEGORY_COMMENT = (
    "One of: Dairy & eggs, Produce, Meat & seafood, Bakery, Pantry, Snacks & sweets, Frozen, Drinks, Household, "
    "Health & beauty, Other. Null until the AI refiner has labelled the listing")
_LISTING_COLUMNS = f"""
  item_id STRING COMMENT 'Flipp id of the listing, unique per flyer item',
  postal STRING COMMENT 'Postal code the flyers were fetched for, e.g. V6T1Z4',
  store STRING COMMENT 'Grocery chain, e.g. No Frills, Safeway, Real Canadian Superstore',
  week_start DATE COMMENT 'First day the flyer is valid',
  valid_from DATE COMMENT 'First day of the sale price',
  valid_to DATE COMMENT 'Last day of the sale price; a listing is on sale today when valid_to >= current_date()',
  brand STRING COMMENT 'Brand, e.g. Kraft, PC, no name',
  item STRING COMMENT 'What the product is, e.g. Milk, Brown Eggs, Peanut Butter',
  variant STRING COMMENT 'e.g. 2%, organic, lactose free, large',
  category STRING COMMENT '{_CATEGORY_COMMENT}',
  size_qty DOUBLE COMMENT 'Package size in the unit of size_unit; null when the flyer does not say',
  size_unit STRING COMMENT 'ml, g or ea (each). Litres and kilograms are converted, so 2 L is 2000 ml',
  price DOUBLE COMMENT 'Sale price in Canadian dollars for the whole package',
  regular_price DOUBLE COMMENT 'Regular price when the flyer prints one, else null',
  unit_price DOUBLE COMMENT 'Price per 100 g or per 100 ml, or per each. Only compare rows with the same unit',
  unit STRING COMMENT '100g, 100ml or ea: what unit_price is per',
  conditions STRING COMMENT 'Fine print such as Limit 4 or bonus points offers',
  raw_text STRING COMMENT 'The product name exactly as printed in the flyer',
  page_no INT COMMENT 'Page of the flyer the listing is on',
  image_url STRING COMMENT 'Picture of the listing from the flyer',
  flyer_url STRING COMMENT 'The whole original flyer on Flipp',
  item_url STRING COMMENT 'The original flyer opened at this item',
  store_url STRING COMMENT 'The store own page for the product, when known',
  fetched_at TIMESTAMP COMMENT 'When this listing was downloaded'
"""

_CREATE_LISTINGS = (
    f"CREATE TABLE IF NOT EXISTS {LISTINGS} ({_LISTING_COLUMNS}) "
    "COMMENT 'This week''s grocery flyer listings near each postal code, from Flipp. One row per advertised product.'"
)
_CREATE_HISTORY = (
    f"CREATE TABLE IF NOT EXISTS {HISTORY} ("
    "postal STRING COMMENT 'Postal code the flyers were fetched for', store STRING COMMENT 'Grocery chain', "
    "week_start DATE COMMENT 'First day of the flyer week', item_id STRING COMMENT 'Flipp id of the listing', "
    "brand STRING, item STRING COMMENT 'What the product is', variant STRING, size_qty DOUBLE, "
    "size_unit STRING COMMENT 'ml, g or ea', price DOUBLE COMMENT 'Sale price in CAD', "
    "regular_price DOUBLE, unit_price DOUBLE COMMENT 'Per 100 g, per 100 ml or per each', unit STRING, "
    "first_seen TIMESTAMP COMMENT 'When this listing was first downloaded') "
    "COMMENT 'Every flyer listing ever downloaded, one row per postal code and flyer item, kept week after week. "
    "Use it to see how a price moves between weeks.'"
)

_SCHEMA = ("ARRAY<STRUCT<item_id: STRING, store: STRING, week_start: STRING, valid_from: STRING, valid_to: STRING, "
           "brand: STRING, item: STRING, variant: STRING, category: STRING, size_qty: DOUBLE, size_unit: STRING, "
           "price: DOUBLE, regular_price: DOUBLE, unit_price: DOUBLE, unit: STRING, conditions: STRING, "
           "raw_text: STRING, page_no: INT, image_url: STRING, flyer_url: STRING, item_url: STRING, "
           "store_url: STRING>>")
_BATCH = f"SELECT inline(from_json(:rows, '{_SCHEMA}'))"

_LISTING_NAMES = (
    "item_id, postal, store, week_start, valid_from, valid_to, brand, item, variant, category, size_qty, size_unit, "
    "price, regular_price, unit_price, unit, conditions, raw_text, page_no, image_url, flyer_url, item_url, "
    "store_url, fetched_at"
)  # named in the INSERT: a table made before categories has category last, and a positional insert would misfile it
_SELECT_LISTINGS = (
    "SELECT item_id, :postal, store, CAST(week_start AS DATE), CAST(valid_from AS DATE), CAST(valid_to AS DATE), "
    "brand, item, variant, category, size_qty, size_unit, price, regular_price, unit_price, unit, conditions, "
    f"raw_text, page_no, image_url, flyer_url, item_url, store_url, CAST(:fetched_at AS TIMESTAMP) FROM ({_BATCH})"
)
_REPLACE_LISTINGS = (  # first chunk
    f"INSERT INTO {LISTINGS} ({_LISTING_NAMES}) REPLACE WHERE postal = :postal {_SELECT_LISTINGS}"
)
_APPEND_LISTINGS = f"INSERT INTO {LISTINGS} ({_LISTING_NAMES}) {_SELECT_LISTINGS}"  # the rest
_MERGE_HISTORY = (
    f"MERGE INTO {HISTORY} t USING (SELECT item_id, :postal AS postal, store, CAST(week_start AS DATE) AS week_start, "
    "brand, item, variant, size_qty, size_unit, price, regular_price, unit_price, unit, "
    f"CAST(:fetched_at AS TIMESTAMP) AS seen FROM ({_BATCH})) s "
    "ON t.postal = s.postal AND t.item_id = s.item_id AND t.week_start = s.week_start "
    "WHEN MATCHED AND (t.price <> s.price OR t.regular_price IS DISTINCT FROM s.regular_price) THEN UPDATE SET "
    "t.price = s.price, t.regular_price = s.regular_price, t.unit_price = s.unit_price "
    "WHEN NOT MATCHED THEN INSERT (postal, store, week_start, item_id, brand, item, variant, size_qty, size_unit, "
    "price, regular_price, unit_price, unit, first_seen) VALUES (s.postal, s.store, s.week_start, s.item_id, "
    "s.brand, s.item, s.variant, s.size_qty, s.size_unit, s.price, s.regular_price, s.unit_price, s.unit, s.seen)"
)


def enabled() -> bool:
    return os.getenv("REALDEAL_DATABRICKS_SYNC") == "1" and all(os.getenv(k) for k in _NEEDS)


def _row(f: FlyerItem) -> dict:
    return {
        "item_id": f.item_id, "store": f.store, "week_start": str(f.week_start),
        "valid_from": str(f.valid_from) if f.valid_from else None, "valid_to": str(f.valid_to) if f.valid_to else None,
        "brand": f.brand, "item": f.item, "variant": f.variant, "category": f.category, "size_qty": f.size_qty,
        "size_unit": f.size_unit,
        "price": f.price, "regular_price": f.regular_price, "unit_price": f.unit_price, "unit": f.unit,
        "conditions": f.conditions, "raw_text": f.raw_text, "page_no": f.page_no, "image_url": f.image_url,
        "flyer_url": None, "item_url": None, "store_url": f.store_url,  # the app doesn't link out to the flyer source
    }


def run(sql: str, timeout: float = 300.0, **params) -> list[list]:
    """One statement on the SQL warehouse. A cold serverless warehouse takes a while to start, so unlike the request
    path (5 s, then give up) this waits, polling, up to `timeout` seconds."""
    from databricks.sdk.service.sql import (
        ExecuteStatementRequestOnWaitTimeout,
        StatementParameterListItem,
        StatementState,
    )

    from apps.api import databricks_sql as db

    api = db._client().statement_execution
    r = api.execute_statement(
        statement=sql, warehouse_id=os.environ["DATABRICKS_WAREHOUSE_ID"], catalog="realdeal", schema="core",
        parameters=[StatementParameterListItem(name=k, value=None if v is None else str(v), type="STRING")
                    for k, v in params.items()],
        wait_timeout="50s", on_wait_timeout=ExecuteStatementRequestOnWaitTimeout.CONTINUE,
    )
    deadline = time.monotonic() + timeout
    while r.status.state in (StatementState.PENDING, StatementState.RUNNING) and time.monotonic() < deadline:
        time.sleep(3)
        r = api.get_statement(r.statement_id)
    if r.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"statement {r.status.state}: {r.status.error}")
    return (r.result.data_array or []) if r.result else []


_ADD_CATEGORY = f"ALTER TABLE {LISTINGS} ADD COLUMNS (category STRING COMMENT '{_CATEGORY_COMMENT}')"


def ensure_tables() -> None:
    run(_CREATE_LISTINGS)
    run(_CREATE_HISTORY)
    # Tables made before categories existed lack the column, and CREATE TABLE IF NOT EXISTS won't add it.
    if not any(row[0] == "category" for row in run(f"DESCRIBE TABLE {LISTINGS}")):
        run(_ADD_CATEGORY)


MAX_PARAMETER_CHARS = 800_000  # Databricks refuses statements whose parameters total over 1,048,576 characters


def chunks(rows: list[dict]) -> list[str]:
    """The rows as JSON strings, each small enough to travel as one statement parameter."""
    out, cur, size = [], [], 2
    for row in rows:
        n = len(json.dumps(row)) + 1
        if cur and size + n > MAX_PARAMETER_CHARS:
            out.append(json.dumps(cur))
            cur, size = [], 2
        cur.append(row)
        size += n
    return [*out, json.dumps(cur)]  # an empty feed still sends "[]", which clears the postal code's old rows


def push(postal: str, rows: list[FlyerItem], fetched_at: datetime) -> None:
    """Replace this postal code's live listings and add anything new to the price history."""
    ensure_tables()
    # A copy saved by an older parser carries a placeholder time (year 1) to mark it stale; don't record that.
    when = (fetched_at if fetched_at.year > 2000 else datetime.now(UTC)).isoformat()
    for n, batch in enumerate(chunks([_row(f) for f in rows if f.price is not None])):
        run(_REPLACE_LISTINGS if n == 0 else _APPEND_LISTINGS, postal=postal, rows=batch, fetched_at=when)
        run(_MERGE_HISTORY, postal=postal, rows=batch, fetched_at=when)
    log.info("synced %d listings near %s to Databricks", len(rows), postal)
