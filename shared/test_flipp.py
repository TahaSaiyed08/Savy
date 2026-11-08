"""Offline tests for shared/flipp.py: fixtures recorded live 2026-11-07 for postal code V6T1Z4, no network
calls here or in CI. _get is monkeypatched for the one test that exercises orchestration end to end.
"""
import json
from pathlib import Path

import pytest

from shared import flipp

FIXTURES = Path(__file__).parent / "tests" / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


# --- grocery_flyer_for -------------------------------------------------------------------------------------


def test_grocery_flyer_for_picks_the_groceries_one():
    flyers = _load("flyers_v6t1z4.json")["flyers"]
    f = flipp.grocery_flyer_for(flyers, "Real Canadian Superstore")
    assert f is not None
    assert "Groceries" in f["categories_csv"]  # not the General Merchandise flyer, confirmed live


def test_grocery_flyer_for_none_when_merchant_absent():
    flyers = _load("flyers_v6t1z4.json")["flyers"]
    assert flipp.grocery_flyer_for(flyers, "Not A Real Store") is None


# --- to_extracted_item --------------------------------------------------------------------------------------


def test_to_extracted_item_skips_rows_with_no_price():
    it = {"name": "ALL FRUITS AND VEGETABLES", "brand": None, "price": ""}
    assert flipp.to_extracted_item(it) is None


def test_to_extracted_item_parses_price_from_list_and_size_from_name():
    # Real fixture row: description is "Selected varieties" (not a size), size has to come from name.
    it = {"name": "BECEL MARGARINE, 637/800 g", "brand": "Becel", "price": "6.99"}
    detail = {"current_price": "6.99", "description": "Selected varieties"}
    x = flipp.to_extracted_item(it, detail)
    assert x is not None
    assert x.brand == "Becel" and x.price == 6.99
    assert x.size_unit == "g" and x.size_qty == 800.0  # "637/800 g": takes the second number, not a crash
    assert x.confidence == 0.95


def test_to_extracted_item_handles_search_shape_price_as_float():
    # /items/search returns current_price as a float, not a string, unlike the other two endpoints.
    it = {"name": "Island Farms 6% milk 4 L", "current_price": 8.98}
    x = flipp.to_extracted_item(it)
    assert x is not None
    assert x.price == 8.98 and x.size_qty == 4000.0 and x.size_unit == "ml"


def test_to_extracted_item_none_when_price_is_empty_string_in_detail_too():
    it = {"name": "NO NAME HOT CHOCOLATE MIX, 1.8 KG", "brand": "no name", "price": ""}
    detail = {"current_price": "", "description": None}  # confirmed live: some items have no price anywhere
    assert flipp.to_extracted_item(it, detail) is None


# --- flyer_item_from / flyer_items_table_row ----------------------------------------------------------------


def test_flyer_item_from_computes_unit_price():
    from datetime import date

    x = flipp.to_extracted_item({"name": "4L milk", "price": "6.49"})
    fi = flipp.flyer_item_from(x, item_id="flipp-1", page_id="flipp:1", store="no_frills",
                               week_start=date(2026, 11, 5), raw_text=x.item)
    assert fi.unit_price == pytest.approx(0.1623, abs=1e-3) and fi.unit == "100ml"


def test_flyer_items_table_row_adds_confidence_and_match_text():
    from datetime import date

    x = flipp.to_extracted_item({"name": "milk", "brand": "Dairyland", "price": "5.99"})
    fi = flipp.flyer_item_from(x, item_id="flipp-2", page_id="flipp:1", store="safeway",
                               week_start=date(2026, 11, 5), raw_text=x.item)
    row = flipp.flyer_items_table_row(fi)
    assert row["confidence"] == 0.95
    assert row["match_text"] == "Dairyland milk"
    assert set(row) == set(flipp.FLYER_ITEM_COLUMNS)


# --- fetch_grocery_flyer (orchestration, _get monkeypatched) --------------------------------------------------


def test_fetch_grocery_flyer_end_to_end(monkeypatch):
    flyers = _load("flyers_v6t1z4.json")
    flyer_detail = _load("flyer_8214584.json")
    item_detail = _load("item_1051494121.json")["item"]

    def fake_get(path, **params):
        if path == "/flyers":
            return flyers
        if path == "/flyers/8214584":
            return flyer_detail
        if path.startswith("/items/"):
            return {"item": item_detail}
        raise AssertionError(f"unexpected path {path}")

    monkeypatch.setattr(flipp, "_get", fake_get)
    result = flipp.fetch_grocery_flyer("No Frills", "no_frills")

    assert result["week"].isoformat() == "2026-11-05"
    assert result["pages"] == []  # confirmed live: pages[] carries no image URL
    assert result["item_count"] == 15  # the trimmed fixture's item count
    assert len(result["rows"]) > 0
    row = result["rows"][0]
    assert row["store"] == "No Frills" and row["item_id"].startswith("flipp-")  # display name, not the slug
    assert all(r["price"] is not None for r in result["rows"])  # priceless rows were skipped
