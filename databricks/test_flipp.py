"""databricks/fetchers/flipp.py against canned Flipp JSON (no network): prices, tile boxes, flyer choice."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "fetchers"))
import flipp  # noqa: E402

FLYER = {"id": 1, "valid_from": "2026-11-05T02:00:00-05:00", "valid_to": "2026-11-11T23:59:59-05:00"}
PAGES = [  # side by side, y axis up: top 0, bottom -2000
    {"page": 1, "left": 0, "right": 1000, "top": 0, "bottom": -2000},
    {"page": 2, "left": 1000, "right": 2000, "top": 0, "bottom": -2000},
]


def _item(id_, left, right, top=-100, bottom=-500, price="7.50"):
    return {"id": id_, "display_type": 1, "brand": "Ocean Spray", "name": "Cranberry Cocktail", "price": price,
            "left": left, "right": right, "top": top, "bottom": bottom, "cutout_image_url": "http://f.wishabi.net/x.jpg"}


def _stub(monkeypatch, items, details):
    def get(path, **_):
        if path == "flyers/1":
            return {"pages": PAGES, "items": items}
        id_ = path.removeprefix("items/")
        return {"item": details[id_]} if id_ in details else {}
    monkeypatch.setattr(flipp, "_get", get)


@pytest.mark.parametrize("pre, current, price, keeps_pre", [
    ("2/", "7.50", 3.75, False),
    ("2 for", "7.50", 3.75, False),
    ("1/", "7.50", 7.5, True),
    (None, None, 7.5, False),  # no current_price: falls back to the listing price
])
def test_multi_buy_price_is_per_unit(monkeypatch, pre, current, price, keeps_pre):
    _stub(monkeypatch, [_item(10, 100, 400)],
          {"10": {"description": "1.89 L", "pre_price_text": pre, "current_price": current}})
    (r,) = flipp.rows("safeway", FLYER, None)
    assert r["price"] == price
    if pre:
        assert (pre in r["raw_text"]) is keeps_pre
    assert "1.89 L" in r["raw_text"]


def test_bbox_is_top_left_fraction_of_the_page_holding_its_center(monkeypatch):
    straddler = _item(11, 900, 1300, top=-1000, bottom=-2100)  # center x 1100: page 2; bottom past the page
    _stub(monkeypatch, [_item(10, 1100, 1500), straddler], {"10": {"x": 1}, "11": {"x": 1}})
    a, b = flipp.rows("safeway", FLYER, None)
    assert (a["page_no"], a["bbox"]) == (2, [0.1, 0.05, 0.5, 0.25])
    assert a["page_id"] == "flipp-1-2" and a["page_aspect"] == 0.5 and a["image_url"].startswith("https://")
    assert b["page_no"] == 2 and b["bbox"] == [0.0, 0.5, 0.3, 1.0]  # clamped to the page
    assert (a["week_start"], a["valid_to"]) == ("2026-11-05", "2026-11-11")


def test_items_without_detail_are_dropped(monkeypatch, capsys):
    _stub(monkeypatch, [_item(10, 100, 400), _item(12, 100, 400)], {"10": {"description": "1 L"}})
    assert [r["flipp_id"] for r in flipp.rows("safeway", FLYER, None)] == ["10"]
    assert "skipped 1 items with no detail" in capsys.readouterr().err


def test_grocery_flyer_per_store_widest_wins(monkeypatch):
    flyers = [
        {"id": 1, "merchant": "Real Canadian Superstore", "categories_csv": "All Flyers,General Merchandise",
         "width": 99999},
        {"id": 2, "merchant": "Real Canadian Superstore", "categories_csv": "All Flyers,Groceries", "width": 500},
        {"id": 3, "merchant": "Real Canadian Superstore", "categories_csv": "Groceries", "width": 900},
        {"id": 4, "merchant": "Walmart", "categories_csv": "Groceries", "width": 9999},
    ]
    monkeypatch.setattr(flipp, "_get", lambda path, **_: {"flyers": flyers})
    assert {k: v["id"] for k, v in flipp.grocery_flyers().items()} == {"superstore": 3}
