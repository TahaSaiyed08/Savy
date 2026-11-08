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


# --- flyer_item_from ----------------------------------------------------------------


def test_flyer_item_from_computes_unit_price():
    from datetime import date

    x = flipp.to_extracted_item({"name": "4L milk", "price": "6.49"})
    fi = flipp.flyer_item_from(x, item_id="flipp-1", page_id="flipp:1", store="no_frills",
                               week_start=date(2026, 11, 5), raw_text=x.item)
    assert fi.unit_price == pytest.approx(0.1623, abs=1e-3) and fi.unit == "100ml"


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
    assert row["week_start"] == "2026-11-05"
    assert all(set(r) == set(flipp.FlyerItem.model_fields) for r in result["rows"])
    assert all(flipp.FlyerItem(**r).model_dump(mode="json") == r for r in result["rows"])
    assert all(r["price"] is not None for r in result["rows"])  # priceless rows were skipped


# --- split_name / _row ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("brand, name, want", [
    ("no name", "NO NAME® NATURALLY IMPERFECT MIXED SWEET PEPPERS, 2.5 LB",
     ("no name", "Naturally Imperfect Mixed Sweet Peppers", None)),
    ("Nestle", "NESTLÉ CHOCOLATE BARS, 4X42-50 G", ("Nestle", "Chocolate Bars", None)),
    ("MAPLE LEAF | SCHNEIDERS", "MAPLE LEAF NATURAL TOP DOGS or SCHNEIDERS CLASSIC WIENERS, 375 g",
     ("MAPLE LEAF", "Natural Top Dogs", None)),
    ("PC", "PC® OR BLUE MENU® ENTRÉES, 770 G-1.13 KG", ("PC", "Blue Menu Entrées", None)),
    (None, "CELERY", (None, "Celery", None)),
    ("Beatrice", "BEATRICE 2% MILK, 4 L", ("Beatrice", "Milk", "2%")),
])
def test_split_name(brand, name, want):
    assert flipp.split_name(brand, name) == want


FLYER = {"id": 7, "valid_from": "2026-11-05T00:00:00-08:00", "valid_to": "2026-11-11T23:59:59-08:00"}
PAGES = [{"left": 0.0, "right": 100.0, "top": 0.0, "bottom": -200.0, "page": 1},
         {"left": 100.0, "right": 200.0, "top": 0.0, "bottom": -200.0, "page": 2}]
TILE = {"id": 1, "name": "PC® MILK, 2 L", "brand": "PC", "price": "7.50", "left": 110.0, "right": 160.0, "top": -20.0,
        "bottom": -60.0, "cutout_image_url": "http://f.wishabi.net/page_items/1/extra_large.jpg"}


def _tile_row(detail=None, tile=None):
    from datetime import date

    return flipp._row(tile or TILE, detail or {}, FLYER, PAGES, "No Frills", date(2026, 11, 5))


def test_row_keeps_the_tile_position_dates_and_https_cutout():
    r = _tile_row()
    assert (r.page_id, r.page_no, r.page_aspect) == ("flipp-7-2", 2, 0.5)
    assert r.bbox == [0.1, 0.1, 0.6, 0.3]  # fractions of its own page, top-left origin, though Flipp's y points up
    assert (str(r.valid_from), str(r.valid_to)) == ("2026-11-05", "2026-11-11")
    assert r.image_url == "https://f.wishabi.net/page_items/1/extra_large.jpg"


def test_row_divides_a_multibuy_price_and_keeps_conditions():
    r = _tile_row({"pre_price_text": "2/", "sale_story": "Limit 4", "original_price": "5.00"})
    assert (r.price, r.conditions, r.regular_price) == (3.75, "Limit 4", 5.0)


def test_row_skips_a_tile_off_every_page_or_without_a_price():
    assert _tile_row(tile={**TILE, "left": 300.0, "right": 310.0}) is None
    assert _tile_row(tile={**TILE, "price": ""}) is None


# --- chain_flyers / display_name -----------------------------------------------------------------------------


def test_chain_flyers_keeps_real_grocery_chains_best_ranked_first():
    chains = flipp.chain_flyers(_load("flyers_v6t1z4.json")["flyers"])
    assert list(chains) == ["Safeway", "T&T", "Save-On-Foods", "Real Canadian Superstore", "No Frills"]
    assert chains["T&T"]["merchant"] == "T&T Supermarket"


def test_chain_flyers_skips_brand_flyers_clubs_and_non_grocery_and_takes_the_widest():
    flyers = [
        {"merchant": "President's Choice", "categories_csv": "Groceries", "priority": 1, "width": 9, "id": 1},
        {"merchant": "Costco", "categories_csv": "Groceries", "priority": 2, "width": 9, "id": 2},
        {"merchant": "Walmart", "categories_csv": "Groceries", "priority": 5, "width": 100, "id": 3},
        {"merchant": "Walmart", "categories_csv": "Groceries", "priority": 6, "width": 500, "id": 4},
        {"merchant": "Safeway", "categories_csv": "Toys", "priority": 0, "width": 9, "id": 5},
    ]
    assert {s: f["id"] for s, f in flipp.chain_flyers(flyers).items()} == {"Walmart": 4}
    assert list(flipp.chain_flyers(flyers * 1, limit=0)) == []


def test_fetch_flyer_downloads_item_details_concurrently_and_keeps_order(monkeypatch):
    import threading

    seen = set()
    items = [{**TILE, "id": n, "name": f"PC® MILK {n}, 2 L", "display_type": 1} for n in range(1, 21)]

    def fake_get(path, **params):
        if path == "/flyers/7":
            return {"items": items, "pages": PAGES}
        seen.add(threading.get_ident())
        return {"item": {"current_price": "3.00"}}

    monkeypatch.setattr(flipp, "_get", fake_get)
    got = flipp.fetch_flyer(FLYER, "No Frills")
    assert [r["item_id"] for r in got["rows"]] == [f"flipp-{n}" for n in range(1, 21)]
    assert got["item_count"] == 20 and got["sized_count"] == 20 and len(seen) > 1


def test_a_lone_flavour_before_or_does_not_become_the_product():
    got = flipp.split_name("PC", "PC® MILK OR DARK CHOCOLATE COVERED ALMONDS, 70 G")
    assert got == ("PC", "Milk or Dark Chocolate Covered Almonds", None)


def test_the_size_printed_once_after_two_products_belongs_to_the_first():
    row = _tile_row(tile={**TILE, "name": "MAPLE LEAF TOP DOGS or SCHNEIDERS WIENERS, 375 g", "brand": "MAPLE LEAF"})
    assert (row.size_qty, row.size_unit) == (375.0, "g") and row.item == "Top Dogs"


# --- links to the original flyer ------------------------------------------------------------------------------


@pytest.mark.parametrize("raw, want", [
    ("https://www.nofrills.ca/p/20921434001_EA", "https://www.nofrills.ca/p/20921434001_EA"),
    ("https://www.walmart.ca/en/ip/10285640?cmpid=DF_CA&utm_source=flipp#x", "https://www.walmart.ca/en/ip/10285640"),
    ("http://insecure.example/p/1", None),
    ("javascript:alert(1)", None),
    ("//evil.example/p/1", None),
    ("https://ad.doubleclick.net/ddm/trackclk/N1;dc_trk_aid=5", None),  # an ad tracker is not the store's page
    ("https://www.flipp.com/en-ca/item/1", None),
    ("https://notflipp.com/p/1", "https://notflipp.com/p/1"),
    ("", None),
    (None, None),
])
def test_store_url_keeps_the_page_and_drops_tracking_and_anything_but_https(raw, want):
    assert flipp.store_url(raw) == want


def test_row_carries_the_store_link():
    assert _tile_row({"ttm_url": "https://www.nofrills.ca/p/9?utm_source=Flipp"}).store_url == "https://www.nofrills.ca/p/9"
    assert _tile_row().store_url is None


# --- real flyer pages from image tiles ------------------------------------------------------------------------

LEVELS = [12.0, 8.1, 5.43, 3.7, 2.33, 1.55, 1.0]  # No Frills: a 28860 x 4096 strip


def test_plan_page_picks_the_sharpest_level_that_keeps_the_page_a_few_megapixels():
    plan = flipp.plan_page(28860, 4096, LEVELS, [0.0, 1560.0, 0.0, -4096.0])
    assert (plan.level, plan.scale) == (5, 1.55)  # 1.0 would be 6.4 MP, 1.55 is 2.7 MP
    assert plan.box == (0, 0, 1007, 2643) and plan.nrows == 11 and plan.pad == 173
    assert plan.cols == (0, 3) and plan.rows == (0, 10)
    wide = flipp.plan_page(88860, 2560, [8.0, 5.33, 3.7, 2.33, 1.55, 1.0], [0.0, 7523.0, 0.0, -2560.0])
    assert wide.scale == 2.33  # a 7,523 px wide page would be 19 MP at full size


def test_plan_page_columns_follow_the_page_along_the_strip_and_stop_at_the_last_tile():
    plan = flipp.plan_page(28860, 4096, LEVELS, [27000.0, 28860.0, 0.0, -4096.0])
    assert plan.cols[1] == 72 and plan.cols[0] == 27000 // 1.55 // 256  # the strip ends in tile column 72


def _png(color):
    import io

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (256, 256), color).save(out, "PNG")
    return out.getvalue()


def test_render_page_puts_tile_row_zero_at_the_bottom_of_the_flyer(monkeypatch):
    import io

    from PIL import Image

    asked = []

    def fake_tile(url):
        level, col, row = map(int, url.rsplit("/", 1)[1].removesuffix(".jpg").split("_"))
        asked.append((level, col, row))
        return _png((row * 20, col * 20, 0))  # each tile painted with where it is

    monkeypatch.setattr(flipp, "_tile", fake_tile)
    meta = {"path": "flyers/x/", "width": 28860, "height": 4096, "resolutions": LEVELS,
            "pages": {"1": [0.0, 1560.0, 0.0, -4096.0]}}
    page = Image.open(io.BytesIO(flipp.render_page(meta, 1))).convert("RGB")
    assert page.size == (1007, 2643)
    top, bottom = page.getpixel((10, 10)), page.getpixel((10, 2640))
    assert abs(top[0] - 10 * 20) < 6 and abs(bottom[0] - 0 * 20) < 6  # top of the page is tile row 10, bottom is row 0
    assert abs(page.getpixel((700, 10))[1] - 2 * 20) < 6  # x 700 is tile column 2
    assert {level for level, _, _ in asked} == {5} and len(asked) == 4 * 11


def test_render_page_is_none_without_tiles_or_page_info(monkeypatch):
    monkeypatch.setattr(flipp, "_tile", lambda url: None)
    meta = {"path": "flyers/x/", "width": 28860, "height": 4096, "resolutions": LEVELS,
            "pages": {"1": [0, 1560, 0, -4096]}}
    assert flipp.render_page(meta, 1) is None  # Flipp has no tiles for it
    assert flipp.render_page(meta, 2) is None  # no such page
    assert flipp.render_page({}, 1) is None


def test_fetch_flyer_keeps_what_drawing_a_page_needs(monkeypatch):
    items = [{**TILE, "id": 1, "display_type": 1}]
    flyer_detail = {"items": items, "pages": PAGES}
    monkeypatch.setattr(flipp, "_get", lambda path, **p: flyer_detail if path == "/flyers/7" else {"item": {}})
    flyer = {**FLYER, "path": "flyers/abc/", "width": 200.0, "height": 200.0, "resolutions": [2.0, 1.0]}
    meta = flipp.fetch_flyer(flyer, "No Frills")["meta"]
    assert meta["path"] == "flyers/abc/" and meta["pages"]["2"] == [100.0, 200.0, 0.0, -200.0]
