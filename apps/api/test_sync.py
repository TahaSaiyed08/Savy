import json
import threading
from datetime import UTC, datetime

import pytest

from apps.api import databricks_sync as ds
from apps.api import flyers_live
from apps.api.models import FlyerItem

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)


def _row(**kw):
    base = dict(item_id="flipp-70", page_id="flipp-7-1", store="No Frills", week_start="2026-11-05", item="Milk",
                price=5.0, valid_to="2026-11-11", store_url="https://www.nofrills.ca/p/1")
    return FlyerItem(**{**base, **kw})


@pytest.fixture
def statements(monkeypatch):
    """Every statement push sends, recorded. The table already has its category column."""
    seen = []

    def fake(sql, timeout=300.0, **params):
        seen.append((sql, params))
        return [["category", "string", ""]] if sql.startswith("DESCRIBE") else []

    monkeypatch.setattr(ds, "run", fake)
    return seen


def data(statements):
    """Just the statements that carry listings: listings then history, for each chunk."""
    return [s for s in statements if not s[0].startswith(("CREATE", "DESCRIBE", "ALTER"))]


def test_push_creates_tables_replaces_the_postal_codes_listings_and_merges_history(statements):
    ds.push("V6T1Z4", [_row(), _row(item_id="flipp-71", price=None)], NOW)
    assert statements[0][0].startswith("CREATE TABLE IF NOT EXISTS realdeal.core.live_listings")
    assert statements[1][0].startswith("CREATE TABLE IF NOT EXISTS realdeal.core.price_history")
    replace, merge = data(statements)
    assert "REPLACE WHERE postal = :postal" in replace[0]
    assert merge[0].startswith("MERGE INTO realdeal.core.price_history")
    for _, params in (replace, merge):
        assert params["postal"] == "V6T1Z4" and params["fetched_at"] == NOW.isoformat()
    rows = json.loads(replace[1]["rows"])
    assert [r["item_id"] for r in rows] == ["flipp-70"]  # the priceless listing is not sent
    assert rows[0]["flyer_url"] == "https://flipp.com/en-ca/flyer/7"
    assert rows[0]["item_url"] == "https://flipp.com/en-ca/item/70"
    assert rows[0]["store_url"] == "https://www.nofrills.ca/p/1"


def test_every_statement_is_a_fixed_literal_with_values_as_parameters(statements):
    ds.push("V6T1Z4", [_row(item="x'; DROP TABLE y; --")], NOW)
    for sql, _ in data(statements):  # the two that carry data
        assert "DROP" not in sql and "V6T1Z4" not in sql and "x'" not in sql
    assert "DROP TABLE y" in data(statements)[0][1]["rows"]  # it travels as data


@pytest.mark.parametrize("flag, creds, want", [
    (None, True, False), ("0", True, False), ("1", False, False), ("1", True, True),
])
def test_sync_only_happens_when_switched_on_and_configured(monkeypatch, flag, creds, want):
    for k in ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_WAREHOUSE_ID"):
        monkeypatch.setenv(k, "x") if creds else monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("REALDEAL_DATABRICKS_SYNC", flag) if flag is not None else monkeypatch.delenv(
        "REALDEAL_DATABRICKS_SYNC", raising=False)
    assert ds.enabled() is want


def test_a_refresh_hands_its_listings_to_databricks_in_the_background_and_survives_a_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(flyers_live, "_feeds", {})
    monkeypatch.setattr(flyers_live, "DATA", tmp_path)
    monkeypatch.setattr(flyers_live, "LEGACY_SNAPSHOT", tmp_path / "legacy.json")
    monkeypatch.setattr(flyers_live.flipp, "grocery_flyers_for", lambda postal: {"No Frills": {"id": 7}})
    monkeypatch.setattr(flyers_live.flipp, "fetch_flyer", lambda flyer, store: {
        "rows": [_row().model_dump(mode="json")], "meta": {"path": "flyers/x/", "pages": {}}})
    pushed, done = [], threading.Event()
    monkeypatch.setattr(ds, "enabled", lambda: True)

    def push(postal, rows, fetched_at):
        pushed.append((postal, len(rows)))
        done.set()
        raise RuntimeError("warehouse is down")

    monkeypatch.setattr(ds, "push", push)
    flyers_live.refresh("A1A1A1")
    assert done.wait(5) and pushed == [("A1A1A1", 1)]
    assert len(flyers_live.items("A1A1A1")) == 1 and flyers_live.feed("A1A1A1").error is None  # refresh unharmed


def test_no_sync_when_it_is_off(monkeypatch, tmp_path):
    monkeypatch.setattr(flyers_live, "_feeds", {})
    monkeypatch.setattr(flyers_live, "DATA", tmp_path)
    monkeypatch.setattr(flyers_live.flipp, "grocery_flyers_for", lambda postal: {"No Frills": {"id": 7}})
    row = _row().model_dump(mode="json")
    monkeypatch.setattr(flyers_live.flipp, "fetch_flyer", lambda flyer, store: {"rows": [row]})
    monkeypatch.setattr(ds, "push", lambda *a: pytest.fail("pushed while sync is off"))
    flyers_live.refresh("A1A1A1")


def test_big_feeds_are_sent_in_chunks_that_fit_databricks_parameter_limit(statements, monkeypatch):
    monkeypatch.setattr(ds, "MAX_PARAMETER_CHARS", 1500)
    rows = [_row(item_id=f"flipp-{n}", raw_text="x" * 200) for n in range(20)]
    ds.push("V6T1Z4", rows, NOW)
    sent = data(statements)  # listings then history, for each chunk
    listing_statements = sent[0::2]
    first, rest = listing_statements[0][0], [sql for sql, _ in listing_statements[1:]]
    assert " REPLACE WHERE postal" in first  # the first chunk clears the postal code
    assert all(" REPLACE WHERE" not in sql and "SELECT" in sql for sql in rest)  # the rest only add
    assert all(f"INSERT INTO {ds.LISTINGS} (item_id, postal, store" in sql for sql in [first, *rest])  # columns named
    assert len(listing_statements) > 3
    ids = [r["item_id"] for _, p in listing_statements for r in json.loads(p["rows"])]
    assert ids == [f"flipp-{n}" for n in range(20)]  # every row once, in order
    assert all(len(p["rows"]) <= 1500 for _, p in listing_statements)
    assert [sql[:11] for sql, _ in sent[1::2]] == ["MERGE INTO "] * len(listing_statements)


def test_an_empty_feed_still_clears_the_postal_codes_old_rows(statements):
    ds.push("V6T1Z4", [], NOW)
    assert "REPLACE WHERE" in data(statements)[0][0] and data(statements)[0][1]["rows"] == "[]"


def test_a_placeholder_stale_time_is_not_recorded_as_the_download_time(statements):
    ds.push("V6T1Z4", [_row()], datetime.min.replace(tzinfo=UTC))
    assert data(statements)[0][1]["fetched_at"].startswith(str(datetime.now(UTC).year))


def test_a_table_made_before_categories_gets_the_column_added(monkeypatch):
    seen = []
    monkeypatch.setattr(ds, "run", lambda sql, timeout=300.0, **p: seen.append(sql) or (
        [["item", "string", ""], ["price", "double", ""]] if sql.startswith("DESCRIBE") else []))
    ds.ensure_tables()
    assert seen[-1].startswith(f"ALTER TABLE {ds.LISTINGS} ADD COLUMNS (category STRING")


def test_listings_carry_their_category_to_databricks(statements):
    ds.push("V6T1Z4", [_row(category="Dairy & eggs")], NOW)
    assert json.loads(data(statements)[0][1]["rows"])[0]["category"] == "Dairy & eggs"
    assert "category: STRING" in ds._SCHEMA and "category" in data(statements)[0][0]
