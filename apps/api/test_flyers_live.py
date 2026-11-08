import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from apps.api import flyers_live
from apps.api.main import app
from apps.api.models import FlyerItem

c = TestClient(app)


def _row(store="No Frills", flyer=1, page=1, item="milk", **kw):
    base = dict(item_id=f"flipp-{store}-{item}", page_id=f"flipp-{flyer}-{page}", store=store, week_start="2026-11-05",
                item=item, price=2.0, page_no=page, valid_to="2999-01-01")
    return FlyerItem(**{**base, **kw})


@pytest.fixture
def feeds(monkeypatch, tmp_path):
    """Live flyers on, an empty cache, saved copies in a temp dir, and no network: fetches are recorded and faked."""
    monkeypatch.setattr(flyers_live, "ENABLED", True)
    monkeypatch.setattr(flyers_live, "_feeds", {})
    monkeypatch.setattr(flyers_live, "DATA", tmp_path)
    monkeypatch.setattr(flyers_live, "LEGACY_SNAPSHOT", tmp_path / "legacy.json")
    state = {"listed": {}, "fetched": [], "spawned": [], "fail": set()}

    def fetch_flyer(flyer, store):
        if store in state["fail"]:
            raise RuntimeError("flipp down")
        state["fetched"].append(store)
        return {"rows": [_row(store, flyer["id"]).model_dump(mode="json")], "meta": {"path": f"flyers/{flyer['id']}/"}}

    monkeypatch.setattr(flyers_live.flipp, "grocery_flyers_for", lambda postal: state["listed"])
    monkeypatch.setattr(flyers_live.flipp, "fetch_flyer", fetch_flyer)
    monkeypatch.setattr(flyers_live, "_spawn", state["spawned"].append)
    return state


@pytest.mark.parametrize("raw, want", [
    ("V6T1Z4", "V6T1Z4"), ("v6t 1z4", "V6T1Z4"), (" M5V-2T6 ", "M5V2T6"), ("12345", None), ("V6T1Z", None),
    ("", None), (None, None), ("D6T1Z4X", None),
])
def test_normalize(raw, want):
    assert flyers_live.normalize(raw) == want


def test_first_ask_starts_one_download_and_returns_nothing_yet(feeds):
    assert flyers_live.items("A1A1A1") == [] and feeds["spawned"] == ["A1A1A1"]
    assert not flyers_live.ready("A1A1A1")
    feeds["listed"] = {"No Frills": {"id": 1}}
    flyers_live.refresh("A1A1A1")
    assert [r.store for r in flyers_live.items("A1A1A1")] == ["No Frills"] and flyers_live.ready("A1A1A1")
    assert feeds["spawned"] == ["A1A1A1"]  # a second ask does not start another


def test_refresh_only_downloads_stores_whose_flyer_changed(feeds):
    feeds["listed"] = {"No Frills": {"id": 1}, "Safeway": {"id": 2}}
    flyers_live.refresh("A1A1A1")
    assert sorted(feeds["fetched"]) == ["No Frills", "Safeway"]
    feeds["fetched"].clear()
    flyers_live.refresh("A1A1A1")  # nothing changed, and the copy is fresh: no downloads at all
    assert feeds["fetched"] == []
    feeds["listed"] = {"No Frills": {"id": 1}, "Safeway": {"id": 3}}  # Safeway's new week
    flyers_live.refresh("A1A1A1")
    assert feeds["fetched"] == ["Safeway"]
    assert {r.page_id for r in flyers_live.items("A1A1A1")} == {"flipp-1-1", "flipp-3-1"}


def test_a_day_old_copy_is_downloaded_again_in_full(feeds):
    feeds["listed"] = {"No Frills": {"id": 1}}
    flyers_live.refresh("A1A1A1")
    flyers_live.feed("A1A1A1").fetched_at = datetime.now(UTC) - timedelta(hours=25)
    feeds["fetched"].clear()
    flyers_live.refresh("A1A1A1")
    assert feeds["fetched"] == ["No Frills"]


def test_a_failed_download_keeps_the_previous_copy(feeds):
    feeds["listed"] = {"No Frills": {"id": 1}, "Safeway": {"id": 2}}
    flyers_live.refresh("A1A1A1")
    feeds["listed"] = {"No Frills": {"id": 9}, "Safeway": {"id": 2}}
    feeds["fail"] = {"No Frills"}
    flyers_live.refresh("A1A1A1")
    assert {r.page_id for r in flyers_live.items("A1A1A1")} == {"flipp-1-1", "flipp-2-1"}  # old No Frills kept
    feeds["listed"] = {}  # Flipp answering with nothing must not wipe it either
    flyers_live.refresh("A1A1A1")
    assert len(flyers_live.items("A1A1A1")) == 2 and flyers_live.feed("A1A1A1").error


def test_a_postal_code_with_no_flyers_is_ready_but_empty_and_not_retried_per_request(feeds):
    flyers_live.refresh("A1A1A1")
    assert flyers_live.ready("A1A1A1") and flyers_live.items("A1A1A1") == [] and feeds["spawned"] == []
    assert flyers_live.feed("A1A1A1").error


def test_the_copy_survives_a_restart(feeds, monkeypatch):
    feeds["listed"] = {"No Frills": {"id": 1}}
    flyers_live.refresh("A1A1A1")
    monkeypatch.setattr(flyers_live, "_feeds", {})  # a new process
    assert [r.store for r in flyers_live.items("A1A1A1")] == ["No Frills"]
    assert flyers_live.feed("A1A1A1").flyers == {"No Frills": 1} and feeds["spawned"] == []


def test_expired_flyers_are_not_served(feeds):
    flyers_live.put("A1A1A1", [_row(valid_to="2020-01-01"), _row(store="Safeway")])
    assert [r.store for r in flyers_live.items("A1A1A1")] == ["Safeway"]


def test_postal_code_header_picks_the_flyers_and_is_validated(feeds):
    flyers_live.put("A1A1A1", [_row(store="Calgary Co-op", item="celery")])
    flyers_live.put(flyers_live.DEFAULT_POSTAL, [_row(store="Safeway", item="celery")])
    h = {"X-User-Id": str(uuid.uuid4())}
    near = c.get("/flyer-items", headers={**h, "X-Postal-Code": "a1a 1a1"}).json()
    assert near["stores"] == ["Calgary Co-op"] and near["ready"]
    assert c.get("/flyer-items", headers=h).json()["stores"] == ["Safeway"]  # no header: the default postal code
    assert c.get("/flyer-items", headers={**h, "X-Postal-Code": "nope"}).status_code == 422
    s = c.get("/flyers/status", headers={"X-Postal-Code": "A1A1A1"}).json()
    assert (s["postal"], s["ready"], s["listings"], s["source"]) == ("A1A1A1", True, 1, "flipp")
    assert s["stores"] == ["Calgary Co-op"]


def test_status_says_not_ready_while_the_first_download_runs(feeds):
    s = c.get("/flyers/status", headers={"X-Postal-Code": "B2B2B2"}).json()
    assert (s["ready"], s["listings"]) == (False, 0) and feeds["spawned"] == ["B2B2B2"]
    assert c.get("/flyer-items", headers={"X-Postal-Code": "B2B2B2"}).json()["ready"] is False


def test_a_new_device_is_seeded_from_the_real_flyers_near_it(feeds):
    rows = [_row(store=s, item="milk", brand="Beatrice", size_qty=4000, size_unit="ml", price=p)
            for s, p in (("No Frills", 5.0), ("Safeway", 6.0))]
    flyers_live.put("A1A1A1", rows)
    h = {"X-User-Id": str(uuid.uuid4()), "X-Postal-Code": "A1A1A1"}
    items = c.get("/items", headers=h).json()
    milk = next(i for i in items if i["item"] == "milk")
    assert milk["source"] == "flyer" and milk["cheapest"]["store"] == "No Frills" and milk["saves_vs_next"] == 1.0
    assert not any(i["cheapest"] for i in items if i["item"] == "ramen")


def test_canned_flyers_ignore_the_postal_code():
    s = c.get("/flyers/status", headers={"X-Postal-Code": "A1A1A1"}).json()
    assert s["source"] == "canned" and s["ready"] and s["listings"] > 0


def test_a_stale_saved_copy_refreshes_when_asked_but_not_on_every_request(feeds):
    flyers_live.put("A1A1A1", [_row()])
    flyers_live.feed("A1A1A1").fetched_at = datetime.now(UTC) - timedelta(days=3)
    assert len(flyers_live.items("A1A1A1")) == 1 and feeds["spawned"] == ["A1A1A1"]  # served now, refreshed behind it
    flyers_live.items("A1A1A1")
    assert feeds["spawned"] == ["A1A1A1"]  # not again for 10 minutes
    flyers_live.feed("A1A1A1").tried_at = datetime.now(UTC) - timedelta(minutes=11)
    flyers_live.items("A1A1A1")
    assert feeds["spawned"] == ["A1A1A1", "A1A1A1"]


def test_a_copy_saved_by_an_older_parser_is_served_but_downloaded_again(feeds, monkeypatch):
    feeds["listed"] = {"No Frills": {"id": 1}}
    flyers_live.refresh("A1A1A1")
    path = flyers_live._path("A1A1A1")
    import json
    saved = json.loads(path.read_text())
    saved["parser"] = flyers_live.flipp.PARSER_VERSION - 1
    path.write_text(json.dumps(saved))
    monkeypatch.setattr(flyers_live, "_feeds", {})  # a new process
    assert len(flyers_live.items("A1A1A1")) == 1 and feeds["spawned"] == ["A1A1A1"]  # old rows now, fresh ones coming
    feeds["fetched"].clear()
    flyers_live.refresh("A1A1A1")
    assert feeds["fetched"] == ["No Frills"]  # everything again, though Flipp's flyer id is unchanged


def _live_page(monkeypatch, feeds):
    """Postal A1A1A1 with one Flipp flyer (id 7) that has real page images available for its page 1."""
    monkeypatch.setattr(flyers_live, "_page_locks", {})
    row = _row(item_id="flipp-70", page_id="flipp-7-1", valid_to="2999-01-01")
    feed = flyers_live.feed("A1A1A1")
    meta = {7: {"path": "flyers/x/", "pages": {"1": [0, 1000, 0, -2000]}}}
    feed.load([row], {"No Frills": 7}, datetime.now(UTC), meta)
    return row


def test_a_page_is_drawn_once_from_flipp_then_served_from_disk(feeds, monkeypatch):
    _live_page(monkeypatch, feeds)
    drawn = []
    monkeypatch.setattr(flyers_live.flipp, "render_page", lambda meta, n: drawn.append(n) or b"\xff\xd8jpeg")
    assert flyers_live.page_aspect("flipp-7-1") == 0.5
    assert flyers_live.page_jpeg("flipp-7-1") == b"\xff\xd8jpeg"
    assert flyers_live.page_jpeg("flipp-7-1") == b"\xff\xd8jpeg"
    assert drawn == [1]  # the second request came from the saved copy
    assert flyers_live.page_jpeg("flipp-7-2") is None and flyers_live.page_aspect("flipp-7-2") is None  # no such page
    assert flyers_live.page_jpeg("mock-nofr-1") is None and flyers_live.page_jpeg("flipp-99-1") is None


def test_page_endpoints_serve_the_real_image_and_say_where_it_is(feeds, monkeypatch):
    _live_page(monkeypatch, feeds)
    monkeypatch.setattr(flyers_live.flipp, "render_page", lambda meta, n: b"\xff\xd8jpeg")
    page = c.get("/flyer-pages/flipp-7-1").json()
    assert page["image_url"] == "/flyer-pages/flipp-7-1/image" and page["aspect"] == 0.5
    r = c.get("/flyer-pages/flipp-7-1/image")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content.startswith(b"\xff\xd8")
    monkeypatch.setattr(flyers_live.flipp, "render_page", lambda meta, n: None)
    flyers_live._page_file("flipp-7-1").unlink()
    assert c.get("/flyer-pages/flipp-7-1/image").status_code == 404  # Flipp had no tiles: the app falls back


def test_a_page_without_real_image_info_keeps_the_rebuilt_layout(feeds):
    flyers_live.put("A1A1A1", [_row(item_id="flipp-70", page_id="flipp-7-1")])  # no image info saved for flyer 7
    page = c.get("/flyer-pages/flipp-7-1").json()
    assert page["image_url"] is None
    assert c.get("/flyer-pages/flipp-7-1/image").status_code == 404


def test_saved_page_images_of_flyers_that_ended_are_removed(feeds, monkeypatch):
    _live_page(monkeypatch, feeds)
    monkeypatch.setattr(flyers_live.flipp, "render_page", lambda meta, n: b"\xff\xd8jpeg")
    flyers_live.page_jpeg("flipp-7-1")
    old = flyers_live.DATA / "pages" / "99-3.jpg"
    old.write_bytes(b"old")
    flyers_live._prune_pages()
    assert flyers_live._page_file("flipp-7-1").exists() and not old.exists()


def test_refresh_keeps_each_flyers_image_info_and_saves_it(feeds, monkeypatch):
    feeds["listed"] = {"No Frills": {"id": 1}}
    meta = {"path": "flyers/x/", "pages": {"1": [0, 1, 0, -2]}}
    monkeypatch.setattr(flyers_live.flipp, "fetch_flyer", lambda flyer, store: {
        "rows": [_row(store, flyer["id"]).model_dump(mode="json")], "meta": meta})
    flyers_live.refresh("A1A1A1")
    monkeypatch.setattr(flyers_live, "_feeds", {})  # a new process
    assert flyers_live.feed("A1A1A1").meta == {1: meta}


def test_a_flyer_saved_without_page_image_info_is_downloaded_again_even_if_unchanged(feeds):
    feeds["listed"] = {"No Frills": {"id": 1}}
    flyers_live.refresh("A1A1A1")
    flyers_live.feed("A1A1A1").meta = {}  # saved by an older version
    feeds["fetched"].clear()
    flyers_live.refresh("A1A1A1")
    assert feeds["fetched"] == ["No Frills"] and 1 in flyers_live.feed("A1A1A1").meta


# --- the AI refiner inside a refresh, and refreshes that find nothing new ---------------------------------------


@pytest.fixture
def ai(feeds, monkeypatch):
    """Refining on, with a fake model, and a record of every save and Databricks push."""
    from apps.api import refine

    monkeypatch.setattr(refine, "enabled", lambda: True)
    asked, synced, saves = [], [], []

    def apply(rows):
        asked.append([r.item_id for r in rows])
        label = {"category": "Produce", "item": "Potatoes"}
        return [r.model_copy(update=label) if r.category is None else r for r in rows]

    monkeypatch.setattr(refine, "apply", apply)
    monkeypatch.setattr(flyers_live, "_sync",
                        lambda postal, rows, fetched_at: synced.append([r.category for r in rows]))
    real_save = flyers_live._save
    monkeypatch.setattr(flyers_live, "_save", lambda f: saves.append(1) or real_save(f))
    feeds["listed"] = {"No Frills": {"id": 1}}
    return NS(asked=asked, synced=synced, saves=saves)


class NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_new_flyers_are_visible_before_the_ai_has_named_them_and_pushed_once_it_has(ai, feeds, monkeypatch):
    from apps.api import refine

    seen_by_visitors = []
    real = refine.apply
    monkeypatch.setattr(refine, "apply", lambda rows: seen_by_visitors.append(
        [r.category for r in flyers_live.items("A1A1A1")]) or real(rows))
    flyers_live.refresh("A1A1A1")
    assert seen_by_visitors == [[None]]  # the flyer was already being served, unlabelled, while the model worked
    assert [r.category for r in flyers_live.items("A1A1A1")] == ["Produce"]
    assert ai.synced == [["Produce"]]  # Databricks got one push, with the labels


def test_labels_are_saved_with_the_flyers(ai, monkeypatch):
    flyers_live.refresh("A1A1A1")
    monkeypatch.setattr(flyers_live, "_feeds", {})  # a new process
    assert [(r.category, r.item) for r in flyers_live.items("A1A1A1")] == [("Produce", "Potatoes")]


def test_a_check_that_finds_nothing_new_saves_nothing_and_leaves_databricks_alone(ai):
    flyers_live.refresh("A1A1A1")
    stamp = flyers_live.feed("A1A1A1").fetched_at
    ai.synced.clear(), ai.saves.clear()
    for _ in range(3):  # three hourly checks
        flyers_live.refresh("A1A1A1")
    assert ai.saves == [] and ai.synced == []
    assert flyers_live.feed("A1A1A1").fetched_at == stamp  # the download time is when it was downloaded, not checked


def test_the_daily_full_download_really_happens_and_updates_the_time(ai, feeds):
    flyers_live.refresh("A1A1A1")
    old = datetime.now(UTC) - timedelta(hours=25)
    flyers_live.feed("A1A1A1").fetched_at = old
    feeds["fetched"].clear(), ai.synced.clear()
    flyers_live.refresh("A1A1A1")
    assert feeds["fetched"] == ["No Frills"] and flyers_live.feed("A1A1A1").fetched_at > old
    assert len(ai.synced) == 1


def test_a_store_whose_flyer_ended_is_dropped_and_pushed(ai, feeds):
    feeds["listed"] = {"No Frills": {"id": 1}, "Safeway": {"id": 2}}
    flyers_live.refresh("A1A1A1")
    ai.synced.clear()
    feeds["listed"] = {"No Frills": {"id": 1}}
    flyers_live.refresh("A1A1A1")
    assert [r.store for r in flyers_live.items("A1A1A1")] == ["No Frills"] and len(ai.synced) == 1


def test_listings_the_model_missed_are_labelled_on_a_later_check_without_downloading_again(ai, feeds, monkeypatch):
    from apps.api import refine

    monkeypatch.setattr(refine, "apply", lambda rows: rows)  # model down on the first run
    flyers_live.refresh("A1A1A1")
    assert [r.category for r in flyers_live.items("A1A1A1")] == [None]
    assert ai.synced == [[None]]  # the download is pushed anyway, just without labels
    feeds["fetched"].clear()

    def working(rows):
        return [r.model_copy(update={"category": "Dairy & eggs"}) for r in rows]

    monkeypatch.setattr(refine, "apply", working)  # model back
    flyers_live.refresh("A1A1A1")
    assert feeds["fetched"] == []  # no download
    assert [r.category for r in flyers_live.items("A1A1A1")] == ["Dairy & eggs"]
    assert ai.synced == [[None], ["Dairy & eggs"]]  # pushed again, now with its labels


def test_a_model_that_throws_cannot_break_a_refresh(ai, monkeypatch):
    from apps.api import refine

    def boom(rows):
        raise RuntimeError("model endpoint exploded")

    monkeypatch.setattr(refine, "apply", boom)
    flyers_live.refresh("A1A1A1")
    assert len(flyers_live.items("A1A1A1")) == 1  # the download itself still counts


def test_the_flyers_tab_can_filter_by_category_and_lists_the_categories_present(feeds):
    rows = [_row("No Frills", item_id="a", item="Milk", category="Dairy & eggs"),
            _row("Safeway", item_id="b", item="Bread", category="Bakery"),
            _row("Safeway", item_id="c", item="Cheese", category="Dairy & eggs"),
            _row("Safeway", item_id="d", item="Mystery")]
    flyers_live.put(flyers_live.DEFAULT_POSTAL, rows)
    got = c.get("/flyer-items", params={"page_size": 100}).json()
    assert got["categories"] == ["Dairy & eggs", "Bakery"]  # busiest first; unlabelled ones aren't a category
    dairy = c.get("/flyer-items", params={"category": "Dairy & eggs", "page_size": 100}).json()
    assert sorted(g["item"] for g in dairy["items"]) == ["Cheese", "Milk"]
    assert all(g["category"] == "Dairy & eggs" for g in dairy["items"])
    assert c.get("/flyer-items", params={"category": "Frozen"}).json()["items"] == []
